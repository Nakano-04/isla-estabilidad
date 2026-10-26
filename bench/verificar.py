"""
verificar.py — Auto-comprobacion de los resultados.

Un banco de pruebas que no se autocomprueba es un banco de pruebas que no se
puede fiar. Este modulo comprueba, sobre `resultados.json`:

  1. Coherencia del oraculo: todos los artefactos validos reproducen el digest.
  2. Coherencia de las mediciones: n esperado, digests correctos, IC ordenados.
  3. Coherencia de la frontera: los puntos de la frontera no se dominan entre si
     y todo punto no dominado del conjunto esta en la frontera.
  4. Coherencia de la significatividad: el numero de pares distinguibles
     coincide con el recuento real.
  5. Coherencia del SVG: los puntos dibujados corresponden a los medidos.

Uso:
    python -m bench.verificar [DIR_RESULTADOS]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .pareto import domina


def _verificar_oraculo(res) -> list[str]:
    err = []
    digest = res.get("oraculo", {}).get("digest", "")
    if not digest:
        return ["el oraculo no tiene digest"]
    for a in res.get("artefactos", []):
        if a.get("valido") and a.get("digest") != digest:
            err.append(f"artefacto valido con digest distinto: {a['variante_id']}::{a['postproceso']}")
    return err


def _verificar_avisos(res) -> list[str]:
    """Ninguna variante marcada como valida puede llevar avisos del toolchain.

    Es el control que impide que un nulo falso vuelva a colarse: un
    enlazador que ignora una opcion produce un resultado plausible y falso.
    """
    err = []
    for a in res.get("artefactos", []):
        avisos = (a.get("meta") or {}).get("avisos") or []
        if avisos and a.get("valido"):
            err.append(
                f"variante valida con avisos del toolchain: "
                f"{a['variante_id']}::{a['postproceso']} -> {avisos[:2]}"
            )
    return err


def _verificar_mediciones(res) -> list[str]:
    err = []
    n_cribado = res.get("config", {}).get("rep cribado")
    n_med = res.get("config", {}).get("rep medicion")
    for k, m in res.get("medicion", {}).items():
        if n_med and m.get("n") != n_med:
            err.append(f"{k}: n={m.get('n')} distinto del configurado ({n_med})")
        if m.get("digests_ok") != m.get("digests_total"):
            err.append(f"{k}: no todas las corridas reproducen el digest")
        if m.get("ci_bajo", 0) > m.get("ci_alto", 0):
            err.append(f"{k}: intervalo de confianza invertido")
        if m.get("mediana", 0) < m.get("ci_bajo", 0) or m.get("mediana", 0) > m.get("ci_alto", 0):
            err.append(f"{k}: la mediana queda fuera de su propio IC")
        if m.get("cv", 0) < 0:
            err.append(f"{k}: CV negativo")
    return err


def _verificar_frontera(res) -> list[str]:
    err = []
    fr = res.get("frontera", [])
    for i, a in enumerate(fr):
        for j, b in enumerate(fr):
            if i != j:
                from bench.pareto import Punto

                pa = Punto(a["etiqueta"], a["x"], a["y"])
                pb = Punto(b["etiqueta"], b["x"], b["y"])
                if domina(pb, pa):
                    err.append(f"la frontera contiene un punto dominado: {a['etiqueta']}")
    medidas = res.get("medicion", {})
    artefactos = {a["variante_id"] + "::" + a["postproceso"]: a for a in res.get("artefactos", [])}

    def _factible(k):
        # Sin campo 'factible' (corridas antiguas) se asume que todo es
        # factible, que es el caso normal de un ensayo concluyente. La
        # factibilidad (CV dentro de umbral y digest estable) EXCLUYE puntos
        # de la frontera: comprobar la completitud sobre el conjunto entero
        # daria falsos positivos cuando el ensayo es ruidoso.
        return bool(medidas.get(k, {}).get("factible", True))

    no_dominados = set()
    for k, m in medidas.items():
        art = artefactos.get(k)
        if not art or not art.get("valido") or not _factible(k):
            continue
        from bench.pareto import Punto

        p = Punto(k, art["tamano_bytes"], m["mediana"])
        if not any(
            domina(Punto(o, artefactos[o]["tamano_bytes"], medidas[o]["mediana"]), p)
            for o in medidas
            if o != k and o in artefactos
            and medidas[o].get("estable", True) and _factible(o)
        ):
            no_dominados.add(k)
    en_frontera = {f["etiqueta"] for f in fr}
    faltan = no_dominados - en_frontera
    if faltan:
        err.append(
            f"puntos no dominados ausentes de la frontera: {sorted(faltan)[:5]}"
        )

    # Contraste entre las dos implementaciones de la frontera (O(n^2) y O(n log n)):
    # deben coincidir en el conjunto de etiquetas.
    from bench.pareto import Punto, frontera as fr_o2, soluciones_pareto

    pts = []
    for k, m in medidas.items():
        art = artefactos.get(k)
        if art and art.get("valido"):
            pts.append(Punto(k, art["tamano_bytes"], m["mediana"]))
    if pts:
        a = {p.etiqueta for p in fr_o2(pts)}
        b = {p.etiqueta for p in soluciones_pareto(pts)}
        if a != b:
            err.append(
                f"las dos implementaciones de Pareto discrepan: "
                f"solo en O(n^2)={sorted(a - b)[:3]}, solo en O(n log n)={sorted(b - a)[:3]}"
            )
    return err


def _verificar_significatividad(res) -> list[str]:
    err = []
    sig = res.get("significatividad", {})
    if not sig:
        return []
    n = sum(1 for p in sig.get("pares", []) if p.get("distinguibles"))
    if n != sig.get("n_distinguibles"):
        err.append("el recuento de pares distinguibles no coincide con la lista")
    if sig.get("n_total") != len(sig.get("pares", [])):
        err.append("el total de pares no coincide con la lista")
    return err


def _verificar_svg(res_dir: Path, res) -> list[str]:
    err = []
    svg_p = res_dir / "frontera.svg"
    if not svg_p.exists():
        return ["falta frontera.svg"]
    svg = svg_p.read_text(encoding="utf-8")
    rects = re.findall(r'<rect x="([\d.]+)" y="([\d.]+)"', svg)
    if len(rects) != 2:
        err.append(f"el SVG deberia tener 2 paneles, tiene {len(rects)}")
    circulos = len(re.findall(r'<circle cx="[\d.]+" cy="[\d.]+" r="[\d.]+" fill="#[0-9a-f]{6}"[^>]*>\s*<title>', svg))
    esperado = len(res.get("medicion", {})) * 2
    if circulos != esperado:
        err.append(f"el SVG dibuja {circulos} puntos, se esperaban {esperado}")
    return err


def verificar(dir_resultados: Path) -> tuple[list[str], dict]:
    ruta = dir_resultados / "resultados.json"
    if not ruta.exists():
        return ([f"no existe {ruta}"], {})
    res = json.loads(ruta.read_text(encoding="utf-8"))
    errores: list[str] = []
    errores += _verificar_oraculo(res)
    errores += _verificar_avisos(res)
    errores += _verificar_mediciones(res)
    errores += _verificar_frontera(res)
    errores += _verificar_significatividad(res)
    errores += _verificar_svg(dir_resultados, res)
    resumen = {
        "artefactos": len(res.get("artefactos", [])),
        "mediciones": len(res.get("medicion", {})),
        "frontera": len(res.get("frontera", [])),
        "concluyente": res.get("calidad_ensayo", {}).get("concluyente"),
    }
    return errores, resumen


def fuzz_pareto(n_trials: int = 5000, semilla: int = 20260920) -> list[str]:
    """Contraste aleatorio entre las dos implementaciones de la frontera.

    `frontera` (O(n^2), fuerza bruta) es la referencia; `soluciones_pareto`
    (O(n log n), barrido) es la versión rápida. Si divergen, la rápida tiene un
    bug. Se comparan los CONJUNTOS de etiquetas, no el orden.
    """
    import random

    from bench.pareto import Punto, frontera as fr_o2, soluciones_pareto

    rng = random.Random(semilla)
    for trial in range(n_trials):
        n = rng.randint(1, 40)
        pts = [
            Punto(str(i), rng.randint(1, 15), rng.randint(1, 15))
            for i in range(n)
        ]
        a = {p.etiqueta for p in fr_o2(pts)}
        b = {p.etiqueta for p in soluciones_pareto(pts)}
        if a != b:
            return [
                f"fuzz de Pareto: discrepancia en el trial {trial} "
                f"(solo O(n^2)={sorted(a - b)[:3]}, solo O(n log n)={sorted(b - a)[:3]})"
            ]
    return []


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    raiz = Path(__file__).resolve().parent.parent
    destino = Path(argv[0]) if argv else raiz / "resultados" / "estandar"
    errores, resumen = verificar(destino)
    print(f"[verificar] {destino}")
    print(f"[verificar] {json.dumps(resumen, ensure_ascii=False)}")
    if "--fuzz" in argv:
        n = 5000
        if "--fuzz" in argv:
            try:
                n = int(argv[argv.index("--fuzz") + 1])
            except (IndexError, ValueError):
                pass
        f = fuzz_pareto(n)
        print(f"[verificar] fuzz de Pareto: {n} trials -> "
              + ("OK" if not f else "FALLO"))
        errores += f
    if errores:
        print("[verificar] FALLOS:")
        for e in errores:
            print("  -", e)
        return 1
    print("[verificar] OK: todas las coherencias se cumplen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
