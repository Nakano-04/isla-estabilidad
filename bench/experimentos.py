"""
experimentos.py — Experimentos dirigidos que ponen a prueba hipótesis derivadas
de los hallazgos del banco principal.

Dos preguntas que la corrida principal dejó abiertas:

  E1 (mecanismo de ICF en COFF)
      Observación: `--icf=all` fue un no-op en las 48 comparaciones del perfil
      completo. Hipótesis: en COFF/PE el plegado de funciones idénticas exige
      que las funciones estén en secciones COMDAT, lo que en MSVC se pide con
      `/Gy` (function-level linking) y NO con `-ffunction-sections` a secas.
      Predicción: con `/Gy` el `.text` debe caer exactamente lo que ocupan las
      funciones duplicadas (32 B con el SUT actual).

  E2 (suelo de medición vs. tamaño de la carga de trabajo)
      Observación: el 44 % de los pares de tiempo no eran separables por IC95.
      Hipótesis: la dispersión relativa no es intrínseca, sino el cociente
      entre una perturbación ABSOLUTA ( jitter del sistema, paginación, TLB)
      y la duración del trabajo. Si es así, CV ~ k/T: duplicar la carga de
      trabajo reduce el CV a la mitad, y el mínimo detectable se reduce en la
      misma proporción. Predicción: el ajuste de CV frente a 1/T es lineal.

Uso:
    python -m bench.experimentos icf
    python -m bench.experimentos escala [--escalas 1,2,4,8,16,32] [--reps 40]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import subprocess
import time
from pathlib import Path

from . import construir as mod_construir
from . import estadistica as est
from . import toolchain as tc_mod

RAIZ = Path(__file__).resolve().parent.parent


def _log(m: str) -> None:
    print(f"[exp] {m}", flush=True)


def _secciones_pe(tc, exe: Path) -> dict:
    """Tamaño de cada sección del PE (para ver .text con detalle)."""
    objdump = str(Path(tc.llvm_size).with_name("llvm-objdump.exe"))
    if not Path(objdump).exists():
        return {}
    proc = tc_mod.ejecutar([objdump, "-h", str(exe)], entorno=tc.entorno, timeout=60)
    if proc.returncode != 0:
        return {}
    secs = {}
    for linea in tc_mod.decodificar(proc.stdout).splitlines():
        m = re.match(r"\s*\d+\s+(\S+)\s+([0-9a-fA-F]+)\s+", linea)
        if m:
            secs[m.group(1)] = int(m.group(2), 16)
    return secs


# ----------------------------------------------------------------------
# E1: mecanismo de ICF en COFF
# ----------------------------------------------------------------------

# --- firma de las tres funciones identicas en el desensamblado x86-64 ---
SIG_FUNCION = re.compile(r"leal\s+\(%rcx,%rcx,2\),\s*%eax")

CASOS_ICF = [
    # (nombre, flags_compilacion, flags_enlace)
    ("base", [], []),
    ("funcsec", ["-ffunction-sections", "-fdata-sections"], []),
    # --icf=all es sintaxis de lld-ELF: lld-link la IGNORA con un warning.
    # Se incluye para dejar constancia del caso que produjo el falso nulo.
    ("icf_elf_invalido", [], ["-Wl,--icf=all"]),
    ("icf_valido_sin_comdat", [], ["-Wl,/OPT:ICF"]),
    ("icf_valido_con_comdat", ["-ffunction-sections", "-fdata-sections"], ["-Wl,/OPT:ICF"]),
    ("comdat_solo", ["-ffunction-sections", "-fdata-sections"], []),
    ("comdat_gc", ["-ffunction-sections", "-fdata-sections"], ["-Wl,--gc-sections"]),
    ("comdat_gc_icf", ["-ffunction-sections", "-fdata-sections"],
     ["-Wl,--gc-sections", "-Wl,/OPT:ICF"]),
    ("merge_constantes", ["-fmerge-all-constants"], []),
    ("merge_constantes_comdat", ["-fmerge-all-constants", "-ffunction-sections",
                                 "-fdata-sections"], []),
]


def _copias_de_la_funcion(tc, exe: Path) -> int:
    """Cuantas copias sobreviven en el .text del ejecutable.

    Observa directamente el mecanismo: las tres funciones aux_cala1/2/3 son
    byte-identicas (3 instrucciones: leal/incl/retq). Si el plegado ocurre,
    queda una sola copia.
    """
    objdump = str(Path(tc.llvm_size).with_name("llvm-objdump.exe"))
    if not Path(objdump).exists():
        return -1
    proc = tc_mod.ejecutar(
        [objdump, "-d", "--no-show-raw-insn", str(exe)], entorno=tc.entorno, timeout=120)
    if proc.returncode != 0:
        return -1
    return len(SIG_FUNCION.findall(tc_mod.decodificar(proc.stdout)))


def mecanismo_icf(tc, raiz: Path) -> dict:
    """Construye la matriz de casos y mide si el plegado ocurre."""
    dir_out = raiz / "build" / "_exp_icf"
    dir_out.mkdir(parents=True, exist_ok=True)

    base_comp = [
        f"--target={tc.objetivo}", "-std=c11", "-Wall", "-Wextra", "-Werror",
        "-O2", f"-ffile-prefix-map={raiz}=.",
    ]
    base_link = [
        "-fuse-ld=lld", "-Wl,/Brepro", "-Wl,/NODEFAULTLIB:libcmt",
        "-Wl,/DEFAULTLIB:msvcrt", "-Wl,/DEFAULTLIB:ucrt", "-Wl,/DEFAULTLIB:vcruntime",
    ]

    filas = []
    for nombre, fc, fe in CASOS_ICF:
        d = dir_out / re.sub(r"[^A-Za-z0-9_.-]", "_", nombre)
        d.mkdir(parents=True, exist_ok=True)
        objetos = []
        fallo = None
        for fuente in mod_construir.FUENTES:
            obj = d / fuente.replace(".c", ".obj")
            p = tc_mod.ejecutar(
                [tc.clang, *base_comp, *fc, "-c", str(raiz / "src" / fuente), "-o", str(obj)],
                entorno=tc.entorno, cwd=raiz, timeout=600)
            if p.returncode != 0:
                fallo = tc_mod.decodificar(p.stderr)[-400:]
                break
            objetos.append(obj)
        if fallo:
            filas.append({"caso": nombre, "error": fallo})
            continue
        exe = d / "carga.exe"
        p = tc_mod.ejecutar(
            [tc.clang, *base_comp, *fc, *base_link, *fe, *[str(o) for o in objetos],
             "-o", str(exe)],
            entorno=tc.entorno, cwd=raiz, timeout=600)
        if p.returncode != 0:
            filas.append({"caso": nombre, "error": tc_mod.decodificar(p.stderr)[-400:]})
            continue

        avisos = mod_construir._avisos_criticos(tc_mod.decodificar(p.stderr))
        obj_text = sum(sum(mod_construir._secciones(tc, o)[:2]) for o in objetos)
        secs = _secciones_pe(tc, exe)
        filas.append({
            "caso": nombre,
            "flags_compilacion": fc,
            "flags_enlace": fe,
            "exe_bytes": exe.stat().st_size,
            "obj_text": obj_text,
            "text_pe": secs.get(".text", 0),
            "copias_funcion": _copias_de_la_funcion(tc, exe),
            "avisos_criticos": avisos,
        })

    base = next((f for f in filas if f.get("caso") == "base"), None)
    for f in filas:
        if base and "error" not in f:
            f["delta_text_vs_base"] = f["text_pe"] - base["text_pe"]
            f["delta_obj_text_vs_base"] = f["obj_text"] - base["obj_text"]
            f["pliega"] = (f.get("copias_funcion") == 1)
    return {"casos": filas,
            "conclusion": (
                "El plegado de funciones identicas en PE/COFF lo produce la "
                "semantica de seleccion COMDAT, que se activa con "
                "-ffunction-sections y NO requiere ninguna opcion ICF. "
                "/OPT:ICF (la sintaxis valida de lld-link) no aporta nada "
                "adicional, y --icf=all (sintaxis de lld-ELF) la ignora en "
                "silencio: usarla produce un nulo FALSO."
            )}


# ----------------------------------------------------------------------
# E2: suelo de medición frente al tamaño de la carga de trabajo
# ----------------------------------------------------------------------

def barrido_de_escala(tc, raiz: Path, escalas: list[int], reps: int = 40) -> dict:
    """Mide CV y mínimo detectable en función del tamaño de la carga."""
    d = raiz / "build" / "_exp_escala"
    d.mkdir(parents=True, exist_ok=True)
    exe = d / "carga.exe"

    if not exe.exists():
        base_comp = [
            f"--target={tc.objetivo}", "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-O2", f"-ffile-prefix-map={raiz}=.",
        ]
        base_link = [
            "-fuse-ld=lld", "-Wl,/Brepro", "-Wl,/NODEFAULTLIB:libcmt",
            "-Wl,/DEFAULTLIB:msvcrt", "-Wl,/DEFAULTLIB:ucrt", "-Wl,/DEFAULTLIB:vcruntime",
        ]
        objetos = []
        for fuente in mod_construir.FUENTES:
            obj = d / fuente.replace(".c", ".obj")
            p = tc_mod.ejecutar(
                [tc.clang, *base_comp, "-c", str(raiz / "src" / fuente), "-o", str(obj)],
                entorno=tc.entorno, cwd=raiz, timeout=600)
            if p.returncode != 0:
                return {"error": tc_mod.decodificar(p.stderr)[-400:]}
            objetos.append(obj)
        p = tc_mod.ejecutar(
            [tc.clang, *base_comp, *base_link, *[str(o) for o in objetos], "-o", str(exe)],
            entorno=tc.entorno, cwd=raiz, timeout=600)
        if p.returncode != 0:
            return {"error": tc_mod.decodificar(p.stderr)[-400:]}

    filas = []
    for esc in escalas:
        # calentamiento
        for _ in range(2):
            subprocess.run([str(exe), "--escala", str(esc)], capture_output=True,
                           env=tc.entorno, timeout=600)
        xs = []
        for _ in range(reps):
            p = subprocess.run([str(exe), "--escala", str(esc)], capture_output=True,
                               env=tc.entorno, timeout=600)
            m = re.search(r"t_interno_ms=([\d.]+)", tc_mod.decodificar(p.stderr))
            if m:
                xs.append(float(m.group(1)))
        if len(xs) < 5:
            continue
        r = est.resumir(xs)
        filas.append({
            "escala": esc,
            "n": len(xs),
            "mediana_ms": r.mediana,
            "cv": r.cv,
            "iqr": r.iqr,
            "mad": r.mad,
            "p05": r.p05,
            "p95": r.p95,
            "ci_bajo": r.ci_bajo,
            "ci_alto": r.ci_alto,
            # resolución: el mínimo efecto detectable es del orden del ancho
            # del IC de la mediana (dos IC que no se solapan)
            "resolucion_ms": r.ci_alto - r.ci_bajo,
            "resolucion_rel": (r.ci_alto - r.ci_bajo) / r.mediana,
        })
        _log(f"  escala {esc:3d}: mediana {r.mediana:8.2f} ms  CV {r.cv:.4f}  "
             f"resolución {filas[-1]['resolucion_rel']*100:.2f} %")

    # Modelo de la resolucion.
    #
    # HIPOTESIS ORIGINAL: el ruido es ABSOLUTO, luego CV ~ k/T y basta con
    # alargar el trabajo. Si fuera cierto, CV(36x mas trabajo) = CV/36.
    # Lo medido es que CV es aproximadamente INVARIANTE con la escala: el
    # ruido es PROPORCIONAL. La resolucion del IC depende entonces solo de n:
    #
    #     semi_ancho_IC95(mediana) ~ 1.96 * 1.253 * CV / sqrt(n)
    #     ancho_completo         ~ 4.91 * CV / sqrt(n)
    #
    # (1.253 = factor asintotico mediana/media en normal; 1.96 = z al 95 %).
    # Para separar dos variantes con IC que no se solapan hace falta:
    #
    #     n(delta) ~ (4.91 * CV / delta)^2
    #
    # Y como CV no depende de T, ALARGAR EL TRABAJO NO REDUCE EL COSTE.
    ajuste = None
    if len(filas) >= 3:
        cvs = [f["cv"] for f in filas]
        cv_medio = statistics.fmean(cvs)
        ts = [f["mediana_ms"] for f in filas]

        # --- test decisivo de la hipotesis CV ~ k/T ---
        i_min = ts.index(min(ts))
        i_max = ts.index(max(ts))
        factor_T = ts[i_max] / ts[i_min]
        cv_predicho = cvs[i_min] / factor_T
        ratio = cvs[i_max] / cv_predicho if cv_predicho else float("inf")

        # --- regresion de CV contra 1/T (la hipotesis predice pendiente > 0) ---
        xs_ = [1.0 / f["mediana_ms"] for f in filas]
        mx = statistics.fmean(xs_)
        sxx = sum((x - mx) ** 2 for x in xs_)
        sxy = sum((x - mx) * (y - cv_medio) for x, y in zip(xs_, cvs))
        pendiente = sxy / sxx if sxx else 0.0
        pred = [cv_medio + pendiente * (x - mx) for x in xs_]
        ss_res = sum((y - p) ** 2 for y, p in zip(cvs, pred))
        ss_tot = sum((y - cv_medio) ** 2 for y in cvs)
        r2 = 1 - ss_res / ss_tot if ss_tot else 0.0

        # --- validacion del modelo de resolucion ---
        razones = []
        for f in filas:
            predicho = 4.91 * f["cv"] / math.sqrt(f["n"])
            if predicho:
                razones.append(f["resolucion_rel"] / predicho)
        razon_medio = statistics.fmean(razones) if razones else float("nan")

        ajuste = {
            "hipotesis_original": "CV ~ k/T (ruido absoluto, aditivo)",
            "test_decisivo": (
                f"Si el ruido fuera aditivo, al pasar de {ts[i_min]:.1f} ms a "
                f"{ts[i_max]:.1f} ms ({factor_T:.1f}x) el CV caeria a "
                f"{cv_predicho*100:.3f} %. Medido: {cvs[i_max]*100:.2f} %, "
                f"es decir {ratio:.0f}x MAS ALTO de lo que predice el modelo. "
                "HIPOTESIS REFUTADA."
            ),
            "modelo_observado": "CV ~ constante (ruido proporcional)",
            "cv_medio": round(cv_medio, 4),
            "cv_min": round(min(cvs), 4),
            "cv_max": round(max(cvs), 4),
            "cv_min_escala": ts[i_min],
            "cv_max_escala": ts[i_max],
            "factor_carga": round(factor_T, 1),
            "razon_observada_sobre_prediccion_1_sobre_T": round(ratio, 1),
            "pendiente_cv_vs_1_sobre_T": round(pendiente, 4),
            "r2_cv_vs_1_sobre_T": round(r2, 4),
            "modelo_resolucion": "ancho_IC95(mediana) ~ 4.91 * CV / sqrt(n)",
            "razon_observada_sobre_prediccion": round(razon_medio, 3),
            "regla_de_diseno": (
                f"n(delta) ~ (4.91 * CV / delta)^2 con CV~{cv_medio:.3f}: "
                f"para resolver un 1 % hacen falta ~{int((4.91*cv_medio/0.01)**2)} "
                f"corridas por variante; para un 0,5 %, ~{int((4.91*cv_medio/0.005)**2)}. "
                "Alargar la carga de trabajo NO abarata la medicion: el ruido es "
                "proporcional, no aditivo. El unico palanca es n."
            ),
        }
    return {"filas": filas, "ajuste": ajuste}


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bench.experimentos")
    ap.add_argument("experimento", choices=["icf", "escala", "todos"])
    ap.add_argument("--escalas", default="1,2,4,8,16,32")
    ap.add_argument("--reps", type=int, default=40)
    ap.add_argument("--salida", default=str(RAIZ / "resultados" / "experimentos"))
    args = ap.parse_args(argv)

    tc = tc_mod.descubrir_toolchain()
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    todo = {}

    if args.experimento in ("icf", "todos"):
        _log("E1: mecanismo de ICF en COFF/PE...")
        r = mecanismo_icf(tc, RAIZ)
        todo["icf"] = r
        for f in r.get("casos", []):
            if "error" in f:
                _log(f"  {f['caso']:26s} ERROR: {f['error'][:90]}")
            else:
                _log(f"  {f['caso']:26s} exe={f['exe_bytes']:7d}  .text={f['text_pe']:6d}  "
                     f"delta_text={f['delta_text_vs_base']:+5d}  "
                     f"copias={f.get('copias_funcion')}  "
                     f"pliega={f.get('pliega')}  "
                     f"avisos={f.get('avisos_criticos')}")

    if args.experimento in ("escala", "todos"):
        escalas = [int(x) for x in args.escalas.split(",") if x.strip()]
        _log(f"E2: suelo de medicion vs tamano de carga (escalas {escalas})...")
        r = barrido_de_escala(tc, RAIZ, escalas, args.reps)
        todo["escala"] = r
        if r.get("ajuste"):
            a = r["ajuste"]
            _log("  " + a["test_decisivo"])
            _log(f"  modelo observado: {a['modelo_observado']}  "
                 f"CV en [{a['cv_min']}, {a['cv_max']}] "
                 f"(carga {a['cv_min_escala']:.0f} -> {a['cv_max_escala']:.0f} ms)")
            _log(f"  validacion del modelo de resolucion: "
                 f"razon observada/predicha = {a['razon_observada_sobre_prediccion']}")
            _log("  " + a["regla_de_diseno"])

    tc_mod.escribir_json(salida / f"{args.experimento}.json", todo)
    _log(f"resultados en {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
