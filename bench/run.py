"""
run.py — Orquestador del experimento.

Uso:
    python -m bench.run todo              # pipeline completo
    python -m bench.run construir          # solo construir
    python -m bench.run informe            # regenera el informe desde resultados.json

Opciones comunes:
    --perfil rapido|estandar|completo
    --escala N
    --repeticiones N      (override de la medicion final)
    --salida DIR
"""

from __future__ import annotations

import argparse
import hashlib
import time
from pathlib import Path

from . import construir as mod_construir
from . import estadistica as est
from . import grafica as graf
from . import informe as inf
from . import medir as mod_medir
from . import pareto as par
from . import toolchain as tc_mod
from .espacio import generar_variantes, flags_base_compilacion, flags_base_enlace

RAIZ = Path(__file__).resolve().parent.parent


def _log(msg: str) -> None:
    print(f"[isla] {msg}", flush=True)


def _cargar_config(ruta: Path) -> dict:
    return tc_mod.leer_json(ruta)


# ----------------------------------------------------------------------
# Pipeline
# ----------------------------------------------------------------------

def ejecutar_todo(args) -> int:
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)

    cfg = _cargar_config(RAIZ / "config" / "experimento.json")
    perfil = args.perfil or cfg["perfil_por_defecto"]
    p = cfg["perfiles"][perfil]
    escala = args.escala if args.escala is not None else cfg["escala"]
    rep_cribado = (
        args.rep_cribado if args.rep_cribado is not None else cfg["cribado"]["repeticiones"]
    )
    rep_medicion = (
        args.repeticiones if args.repeticiones is not None else cfg["medicion"]["repeticiones"]
    )
    max_finales = cfg["seleccion"]["maximo_finales"]

    _log(f"perfil={perfil} escala={escala} cribado={rep_cribado} medicion={rep_medicion}")

    # --- toolchain ---
    tc = tc_mod.descubrir_toolchain()
    _log(f"toolchain: {tc.version}")

    if cfg.get("fijar_afinidad"):
        ok = mod_medir.fijar_afinidad(cfg.get("nucleo_afinidad", 0))
        _log(f"afinidad de CPU fijada: {ok}")

    # --- oraculo ---
    _log("calculando el oraculo de correccion (doble implementacion)...")
    digest_esperado, informe_oraculo = mod_construir.calcular_oraculo(
        tc, RAIZ, escala=escala
    )
    if not digest_esperado:
        _log("ERROR: " + informe_oraculo)
        return 2
    _log(informe_oraculo)

    # --- espacio de busqueda ---
    base_c = flags_base_compilacion(tc.objetivo, RAIZ)
    base_e = flags_base_enlace()
    variantes = generar_variantes(
        p["niveles"], p["desenrollados"], p["enlaces"], p["depuraciones"], base_c, base_e
    )
    _log(f"espacio de busqueda: {len(variantes)} variantes")

    # --- construccion ---
    _log("construyendo...")
    t0 = time.perf_counter()
    artefactos: list[mod_construir.Artefacto] = []
    for i, v in enumerate(variantes, 1):
        artefactos.extend(mod_construir.construir_variante(tc, v, RAIZ, escala=escala))
        if i % 12 == 0 or i == len(variantes):
            _log(f"  {i}/{len(variantes)} variantes")
    validos = [a for a in artefactos if a.valido]
    _log(
        f"construccion terminada en {time.perf_counter()-t0:.1f}s: "
        f"{len(validos)}/{len(artefactos)} artefactos validos"
    )

    # --- asentar la maquina antes de medir ---
    # Tras construir decenas de ejecutables, el antivirus del sistema y el
    # gestor de archivos los escanean. Medir durante esa ventana produce una
    # degradacion monotona que el diagnostico de deriva detecta pero no
    # arregla. Se deja un margen de calma antes de medir.
    settle = int(cfg.get("settle_segundos", 0))
    if settle > 0:
        _log(f"asentando la maquina {settle}s (escaneo del AV, caches, termica)...")
        time.sleep(settle)

    # --- cribado ---
    _log(f"cribado: {rep_cribado} repeticiones por artefacto...")
    medidas_cribado = mod_medir.medir_lote(
        tc, validos, digest_esperado,
        escala=escala, repeticiones=rep_cribado,
        calentamiento=cfg["cribado"]["calentamiento"],
    )
    resumen_cribado = {
        k: est.resumir(v.t_interno_ms).como_dict() for k, v in medidas_cribado.items()
    }

    # --- seleccion de finalistas ---
    puntos_cribado = []
    for a in validos:
        k = f"{a.variante_id}::{a.postproceso}"
        r = resumen_cribado.get(k)
        if not r:
            continue
        puntos_cribado.append(
            par.Punto(
                etiqueta=k,
                x=a.tamano_bytes,
                y=r["mediana"],
                meta={"nivel": a.variante_id.split("__")[0],
                      "codigo": a.codigo_bytes,
                      "obj_text": a.obj_text},
            )
        )
    fr_cribado = par.frontera(puntos_cribado)
    seleccionados = {p.etiqueta for p in fr_cribado}

    if cfg["seleccion"].get("incluir_mejor_por_nivel"):
        mejor_por_nivel: dict[str, par.Punto] = {}
        for p in puntos_cribado:
            niv = p.meta["nivel"]
            if niv not in mejor_por_nivel or p.x < mejor_por_nivel[niv].x:
                mejor_por_nivel[niv] = p
        seleccionados |= {p.etiqueta for p in mejor_por_nivel.values()}

        # Ademas, el mejor de cada nivel por CODIGO PROPIO: si no, un nivel
        # puede quedar sin representante medible (p.ej. si su mejor binario es
        # una variante con LTO, cuyo .obj es bitcode y no se puede medir).
        mejor_por_nivel_cod: dict[str, par.Punto] = {}
        for p in puntos_cribado:
            obj = p.meta.get("obj_text")
            if obj is None:
                continue
            niv = p.meta["nivel"]
            actual = mejor_por_nivel_cod.get(niv)
            if actual is None or obj < actual.meta["obj_text"]:
                mejor_por_nivel_cod[niv] = p
        seleccionados |= {p.etiqueta for p in mejor_por_nivel_cod.values()}

    if len(seleccionados) > max_finales:
        seleccionados = set(sorted(seleccionados)[:max_finales])
    _log(f"finalistas para la medicion rigurosa: {len(seleccionados)}")

    finalistas = [
        a for a in validos if f"{a.variante_id}::{a.postproceso}" in seleccionados
    ]

    # --- medicion rigurosa ---
    _log(f"medicion rigurosa: {rep_medicion} repeticiones intercaladas...")
    t0 = time.perf_counter()
    last = [0]

    def prog(hecho, total):
        if hecho - last[0] >= max(1, total // 20) or hecho == total:
            last[0] = hecho
            _log(f"  {hecho}/{total} corridas")

    medidas = mod_medir.medir_lote(
        tc, finalistas, digest_esperado,
        escala=escala, repeticiones=rep_medicion,
        calentamiento=cfg["medicion"]["calentamiento"],
        progreso=prog,
    )
    _log(f"medicion terminada en {time.perf_counter()-t0:.1f}s")

    resumen_medicion = {}
    for k, m in medidas.items():
        r = est.resumir(m.t_interno_ms).como_dict()
        r["estable"] = m.estable
        r["digests_ok"] = m.digests_ok
        r["digests_total"] = m.digests_total
        r["t_externo_mediana"] = round(est.mediana(m.t_externo_ms), 3)
        r["t_externo_cv"] = round(est.coeficiente_variacion(m.t_externo_ms), 4)
        r["mem_pico_kb"] = round(est.mediana(m.mem_pico_kb), 1)
        r["etiqueta"] = m.etiqueta
        r["postproceso"] = m.postproceso
        r["variante_id"] = m.variante_id
        r["fallos"] = m.fallos[:5]
        r["muestras"] = [round(x, 4) for x in m.t_interno_ms]
        resumen_medicion[k] = r
    # --- reproducibilidad del build ---
    _log("verificando reproducibilidad del build...")
    rep = _verificar_reproducibilidad(tc, finalistas[:3], RAIZ)

    # --- frontera final ---
    puntos_sz = []
    puntos_sv = []
    puntos_cod = []
    for a in finalistas:
        k = f"{a.variante_id}::{a.postproceso}"
        r = resumen_medicion.get(k)
        if not r:
            continue
        limite_cv = cfg["limites"]["cv_max"]
        meta = {
            "variante_id": a.variante_id,
            "postproceso": a.postproceso,
            "nivel": a.variante_id.split("__")[0],
            "codigo_bytes": a.codigo_bytes,
            "obj_text": a.obj_text,
            "cv": r["cv"],
            "estable": r["estable"],
            "factible": (r["cv"] <= limite_cv) and r["estable"],
        }
        puntos_sz.append(par.Punto(k, a.tamano_bytes, r["mediana"], meta))
        puntos_sv.append(par.Punto(k, a.tamano_bytes, r["cv"], meta))
        if a.obj_text is not None:
            puntos_cod.append(par.Punto(k, a.obj_text, r["mediana"], meta))

    factibles = [p for p in puntos_sz if p.meta.get("factible")]
    fr_final = par.frontera(factibles if factibles else puntos_sz)
    # Propagar la factibilidad a las mediciones: el verificador la necesita
    # para comprobar que la frontera es COMPLETA entre los puntos factibles.
    for p in puntos_sz:
        resumen_medicion[p.etiqueta]["factible"] = bool(p.meta.get("factible"))
    punto_codo = par.codo(fr_final)
    # La frontera sobre codigo propio excluye las variantes con LTO: su .obj es
    # bitcode y no se puede medir el codigo del programa antes del enlazado.
    fr_codigo = par.frontera(
        [p for p in puntos_cod if p.meta.get("factible")]
        or list(puntos_cod)
    )

    significatividad = _comparar_significatividad(resumen_medicion)
    # Estabilidad de la frontera: que puntos siguen en ella si el ruido cambia.
    medidas_para_frontera = {
        k: {"x": next((a.tamano_bytes for a in finalistas
                       if f"{a.variante_id}::{a.postproceso}" == k), 0),
            "mediana": v["mediana"], "cv": v["cv"], "n": v["n"],
            "muestras": v.get("muestras", [])}
        for k, v in resumen_medicion.items()
    }
    estabilidad = par.estabilidad_frontera(medidas_para_frontera, n_boot=500)
    # Hipervolumen de la frontera: escalar comparable entre corridas. La
    # referencia es el peor punto del conjunto medido (mayor S, mayor T).
    ref_x = max((p.x for p in puntos_sz), default=1.0) * 1.05
    ref_y = max((p.y for p in puntos_sz), default=1.0) * 1.05
    hv = par.hipervolumen(factibles if factibles else puntos_sz, ref_x, ref_y)
    # Contraste entre las dos implementaciones de la frontera (O(n^2) y O(n log n)).
    fr_rapida = par.soluciones_pareto(factibles if factibles else puntos_sz)
    coherencia_frontera = {
        p.etiqueta for p in fr_final
    } == {p.etiqueta for p in fr_rapida}
    calidad = _calidad_del_ensayo(resumen_medicion, cfg)
    if not calidad["concluyente"]:
        veredictos_previo = [
            "ENSAYO NO CONCLUYENTE: la maquina estuvo demasiado ruidosa durante "
            "la medicion (deriva o variabilidad por encima del umbral). Los "
            "artefactos se conservan como datos, pero las comparaciones de "
            "tiempo de esta corrida NO deben interpretarse hasta repetirla "
            "en una maquina en calma.",
        ]
    else:
        veredictos_previo = []

    veredictos = veredictos_previo + _veredictos(
        puntos_sz, fr_final, punto_codo, resumen_medicion, cfg
    )
    veredictos += _veredictos_codigo(puntos_cod, cfg)
    veredictos.append(
        f"Diferencias de tiempo estadisticamente distinguibles (IC95 sin solape): "
        f"{significatividad['n_distinguibles']}/{significatividad['n_total']} pares "
        f"entre los {len(resumen_medicion)} artefactos medidos."
    )

    resultados = {
        "meta": tc_mod.registro_entorno(tc),
        "config": {
            "perfil": perfil,
            "escala": escala,
            "rep cribado": rep_cribado,
            "rep medicion": rep_medicion,
            "limites": cfg["limites"],
            "variantes": len(variantes),
        },
        "oraculo": {"digest": digest_esperado, "informe": informe_oraculo},
        "artefactos": [a.como_dict() for a in artefactos],
        "cribado": resumen_cribado,
        "medicion": resumen_medicion,
        "frontera": [p.como_dict() for p in fr_final],
        "frontera_codigo": [p.como_dict() for p in fr_codigo],
        "hipervolumen": round(hv, 2),
        "hipervolumen_ref": {"x": ref_x, "y": ref_y},
        "coherencia_frontera": coherencia_frontera,
        "estabilidad_frontera": estabilidad,
        "codo": punto_codo.como_dict() if punto_codo else None,
        "reproducibilidad": rep,
        "significatividad": significatividad,
        "calidad_ensayo": calidad,
        "veredictos": veredictos,
    }

    _escribir_salidas(
        salida,
        resultados=resultados,
        puntos_sz=puntos_sz,
        puntos_sv=puntos_sv,
        fr_final=fr_final,
        destacar={p.etiqueta for p in (fr_final + ([punto_codo] if punto_codo else []))},
    )

    _log(f"resultados en {salida}")
    for v in veredictos:
        _log("  " + v)
    return 0


def _veredictos(puntos, fr, codo, resumen, cfg) -> list[str]:
    vs: list[str] = []
    if not puntos:
        return ["No se obtuvo ninguna medida valida."]

    mejor_tam = min(puntos, key=lambda p: p.x)
    mejor_t = min(puntos, key=lambda p: p.y)
    vs.append(
        f"Menor binario: `{mejor_tam.etiqueta}` con {mejor_tam.x:,} B "
        f"y {mejor_tam.y:.2f} ms internos."
    )
    vs.append(
        f"Menor tiempo: `{mejor_t.etiqueta}` con {mejor_t.y:.2f} ms "
        f"y {mejor_t.x:,} B."
    )
    if codo:
        vs.append(
            f"Codo de la frontera (compromiso): `{codo.etiqueta}` "
            f"— {codo.x:,} B / {codo.y:.2f} ms."
        )
    vs.append(f"La frente de Pareto contiene {len(fr)} puntos.")

    por_nivel: dict[str, list] = {}
    for p in puntos:
        por_nivel.setdefault(p.meta["nivel"], []).append(p)
    if "O0" in por_nivel and "Oz" in por_nivel:
        o0 = min(por_nivel["O0"], key=lambda p: p.x)
        oz = min(por_nivel["Oz"], key=lambda p: p.x)
        red_t = 100.0 * (o0.x - oz.x) / o0.x if o0.x else 0.0
        vs.append(
            f"Reduccion de tamano frente a -O0 (mejor de cada nivel): "
            f"{o0.x:,} B -> {oz.x:,} B ({red_t:.1f} % menos)."
        )
    vs.append(
        f"La variabilidad se mantiene por debajo del umbral CV<={cfg['limites']['cv_max']} "
        f"en {sum(1 for p in puntos if p.meta.get('factible'))}/{len(puntos)} "
        f"artefactos factibles."
    )
    return vs


def _calidad_del_ensayo(resumen_medicion, cfg) -> dict:
    """Diagnostico de si la maquina estaba en condiciones de medir.

    Dos senales, complementarias:
      * deriva: pendiente de la regresion del tiempo sobre el indice de la
        corrida. Una deriva alta significa que la maquina se degrade de
        forma monotona durante el ensayo (termica, AV, competencia).
      * CV: dispersion relativa entre corridas de una misma variante.
    """
    derivas = [r["deriva_pct"] for r in resumen_medicion.values()]
    cvs = [r["cv"] for r in resumen_medicion.values()]
    deriva_max = max((abs(d) for d in derivas), default=0.0)
    cv_max = max(cvs, default=0.0)
    limite_deriva = cfg["limites"].get("deriva_pct_max", 3.0)
    limite_cv = cfg["limites"]["cv_max"]
    factibles = sum(1 for r in resumen_medicion.values() if r.get("estable"))
    concluyente = deriva_max <= limite_deriva and cv_max <= limite_cv
    return {
        "deriva_max_abs": round(deriva_max, 3),
        "deriva_mediana": round(est.mediana(derivas), 3) if derivas else 0.0,
        "cv_max": round(cv_max, 4),
        "cv_mediana": round(est.mediana(cvs), 4) if cvs else 0.0,
        "limite_deriva": limite_deriva,
        "limite_cv": limite_cv,
        "n_estables": factibles,
        "n_total": len(resumen_medicion),
        "concluyente": concluyente,
    }


def _comparar_significatividad(resumen_medicion) -> dict:
    """¿Que diferencias de tiempo son REALES y cuales son ruido?

    Criterio conservador: dos variantes son estadisticamente distinguibles si
    sus intervalos de confianza bootstrap al 95 % NO se solapan. Es mas
    estricto que un test de hipotesis con p-valor, pero no depende de una
    asuncion de normalidad que no esta garantizada con n=25.
    """
    claves = sorted(resumen_medicion)
    pares = []
    for i, a in enumerate(claves):
        for b in claves[i + 1:]:
            ra, rb = resumen_medicion[a], resumen_medicion[b]
            solapa = not (ra["ci_alto"] < rb["ci_bajo"] or rb["ci_alto"] < ra["ci_bajo"])
            pares.append({
                "a": a,
                "b": b,
                "distinguibles": not solapa,
                "delta_ms": round(ra["mediana"] - rb["mediana"], 3),
                "delta_pct": round(
                    100.0 * (ra["mediana"] - rb["mediana"]) / rb["mediana"], 2
                ) if rb["mediana"] else 0.0,
            })
    return {
        "pares": pares,
        "n_distinguibles": sum(1 for p in pares if p["distinguibles"]),
        "n_total": len(pares),
    }


def _veredictos_codigo(puntos, cfg) -> list[str]:
    """Veredictos sobre el codigo propio (.obj), sin el ruido del CRT/PE."""
    medibles = [p for p in puntos if p.meta.get("obj_text") is not None]
    if not medibles:
        return []
    vs = []
    por_nivel: dict[str, list] = {}
    for p in medibles:
        por_nivel.setdefault(p.meta["nivel"], []).append(p)
    if "O0" in por_nivel and "Oz" in por_nivel:
        o0 = min(por_nivel["O0"], key=lambda p: p.meta["obj_text"])
        oz = min(por_nivel["Oz"], key=lambda p: p.meta["obj_text"])
        red = 100.0 * (o0.meta["obj_text"] - oz.meta["obj_text"]) / o0.meta["obj_text"]
        vs.append(
            f"Codigo propio (.obj, text+data): {o0.meta['obj_text']:,} B en -O0 -> "
            f"{oz.meta['obj_text']:,} B en -Oz ({red:.1f} % menos). Esta es la magnitud "
            f"real del efecto de optimizacion, sin el fondo fijo del CRT ni de las "
            f"cabeceras PE."
        )
    if "O2" in por_nivel and "Os" in por_nivel:
        o2 = min(por_nivel["O2"], key=lambda p: p.meta["obj_text"])
        os_ = min(por_nivel["Os"], key=lambda p: p.meta["obj_text"])
        vs.append(
            f"-Os frente a -O2 en codigo propio: {o2.meta['obj_text']:,} B -> "
            f"{os_.meta['obj_text']:,} B "
            f"({100.0*(o2.meta['obj_text']-os_.meta['obj_text'])/o2.meta['obj_text']:.1f} % menos)."
        )
    if "O2" in por_nivel and "Oz" in por_nivel:
        o2 = min(por_nivel["O2"], key=lambda p: p.meta["obj_text"])
        oz = min(por_nivel["Oz"], key=lambda p: p.meta["obj_text"])
        vs.append(
            f"-Oz frente a -O2 en codigo propio: {o2.meta['obj_text']:,} B -> "
            f"{oz.meta['obj_text']:,} B "
            f"({100.0*(o2.meta['obj_text']-oz.meta['obj_text'])/o2.meta['obj_text']:.1f} % menos); "
            f"pero -Oz es el mas lento medido."
        )
    return vs


def _verificar_reproducibilidad(tc, artefactos, raiz) -> dict:
    """Reconstruye algunas variantes y compara hashes bit a bit."""
    detalle = []
    identicos = 0
    n = 0
    for art in artefactos:
        n += 1
        fc = art.meta.get("flags_compilacion", [])
        fe = art.meta.get("flags_enlace", [])
        if not fc:
            continue
        dir_out = raiz / "build" / "_repro" / art.variante_id
        dir_out.mkdir(parents=True, exist_ok=True)
        objetos = []
        ok = True
        for fuente in mod_construir.FUENTES:
            obj = dir_out / fuente.replace(".c", ".obj")
            proc = tc_mod.ejecutar(
                [tc.clang, *fc, "-c", str(raiz / "src" / fuente), "-o", str(obj)],
                entorno=tc.entorno, cwd=raiz, timeout=600,
            )
            if proc.returncode != 0:
                ok = False
                break
            objetos.append(obj)
        if not ok:
            detalle.append({"variante": art.variante_id, "resultado": "fallo al reconstruir"})
            continue
        exe = dir_out / "carga.exe"
        proc = tc_mod.ejecutar(
            [tc.clang, *fc, *fe, *[str(o) for o in objetos], "-o", str(exe)],
            entorno=tc.entorno, cwd=raiz, timeout=600,
        )
        if proc.returncode != 0:
            detalle.append({"variante": art.variante_id, "resultado": "fallo al reenlazar"})
            continue
        h1 = hashlib.sha256(art.ruta.read_bytes()).hexdigest()
        h2 = hashlib.sha256(exe.read_bytes()).hexdigest()
        igual = h1 == h2
        identicos += int(igual)
        detalle.append({
            "variante": art.variante_id,
            "resultado": "bit-identico" if igual else f"DIFIERE ({h1[:12]} vs {h2[:12]})",
        })
    return {"n": n, "identicos": identicos, "detalle": detalle}


def _escribir_salidas(salida, resultados, puntos_sz, puntos_sv, fr_final, destacar) -> None:
    tc_mod.escribir_json(salida / "resultados.json", resultados)

    filas_art = []
    for a in resultados["artefactos"]:
        filas_art.append({
            "variante_id": a["variante_id"],
            "postproceso": a["postproceso"],
            "etiqueta": a["etiqueta"],
            "tamano_bytes": a["tamano_bytes"],
            "tamano_total_bytes": a.get("tamano_total_bytes", a["tamano_bytes"]),
            "codigo_bytes": a["codigo_bytes"],
            "obj_text": a["obj_text"],
            "obj_bytes": a["obj_bytes"],
            "text": a["text"],
            "data": a["data"],
            "bss": a["bss"],
            "valido": a["valido"],
            "digest": a["digest"],
            "mem_pico_kb": a["mem_pico_kb"],
            "error": a["error"],
        })
    tc_mod.escribir_csv(
        salida / "artefactos.csv",
        filas_art,
        ["variante_id", "postproceso", "etiqueta", "tamano_bytes", "tamano_total_bytes",
         "codigo_bytes", "obj_text", "obj_bytes", "text", "data", "bss", "valido",
         "digest", "mem_pico_kb", "error"],
    )

    filas_med = []
    for k, r in sorted(resultados["medicion"].items()):
        filas_med.append({
            "artefacto": k,
            "n": r["n"],
            "t_interno_mediana": r["mediana"],
            "ci_bajo": r["ci_bajo"],
            "ci_alto": r["ci_alto"],
            "t_interno_media": r["media"],
            "cv": r["cv"],
            "iqr": r["iqr"],
            "mad": r["mad"],
            "deriva_pct": r["deriva_pct"],
            "t_externo_mediana": r["t_externo_mediana"],
            "t_externo_cv": r["t_externo_cv"],
            "mem_pico_kb": r["mem_pico_kb"],
            "estable": r["estable"],
            "digests_ok": r["digests_ok"],
            "digests_total": r["digests_total"],
        })
    tc_mod.escribir_csv(
        salida / "mediciones.csv",
        filas_med,
        ["artefacto", "n", "t_interno_mediana", "ci_bajo", "ci_alto", "t_interno_media",
         "cv", "iqr", "mad", "deriva_pct", "t_externo_mediana", "t_externo_cv",
         "mem_pico_kb", "estable", "digests_ok", "digests_total"],
    )

    svg = graf.renderizar_svg(
        [graf.PuntoGrafica(p.etiqueta, p.x, p.y, p.meta["nivel"], p.meta) for p in puntos_sz],
        [graf.PuntoGrafica(p.etiqueta, p.x, p.y, p.meta["nivel"], p.meta) for p in puntos_sv],
        [graf.PuntoGrafica(p.etiqueta, p.x, p.y, p.meta["nivel"], p.meta) for p in fr_final],
        titulo="Isla de estabilidad - frente de Pareto (S, T)",
        subtitulo="Cada punto es un binario; la linea discontinua son los puntos no dominados.",
        destacar=destacar,
    )
    (salida / "frontera.svg").write_text(svg, encoding="utf-8")

    md = inf.generar_informe(resultados, resultados["config"])
    (salida / "INFORME.md").write_text(md, encoding="utf-8")

    (salida / "resumen.txt").write_text(
        "\n".join(resultados["veredictos"]) + "\n", encoding="utf-8"
    )


# ----------------------------------------------------------------------
# Subcomandos
# ----------------------------------------------------------------------

def _cmd_construir(args) -> int:
    cfg = _cargar_config(RAIZ / "config" / "experimento.json")
    perfil = args.perfil or cfg["perfil_por_defecto"]
    p = cfg["perfiles"][perfil]
    tc = tc_mod.descubrir_toolchain()
    digest, informe = mod_construir.calcular_oraculo(tc, RAIZ, escala=cfg["escala"])
    if not digest:
        _log("ERROR: " + informe)
        return 2
    base_c = flags_base_compilacion(tc.objetivo, RAIZ)
    base_e = flags_base_enlace()
    variantes = generar_variantes(
        p["niveles"], p["desenrollados"], p["enlaces"], p["depuraciones"], base_c, base_e
    )
    arts = []
    for i, v in enumerate(variantes, 1):
        arts.extend(mod_construir.construir_variante(tc, v, RAIZ, escala=cfg["escala"]))
        if i % 12 == 0 or i == len(variantes):
            _log(f"  {i}/{len(variantes)}")
    tc_mod.escribir_json(
        Path(args.salida) / "artefactos.json", [a.como_dict() for a in arts]
    )
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bench.run")
    ap.add_argument("comando", choices=["todo", "construir", "informe"])
    ap.add_argument("--perfil", choices=["rapido", "estandar", "completo"])
    ap.add_argument("--escala", type=int)
    ap.add_argument("--repeticiones", type=int)
    ap.add_argument("--rep-cribado", dest="rep_cribado", type=int)
    ap.add_argument("--salida", default=str(RAIZ / "resultados"))
    args = ap.parse_args(argv)

    if args.comando == "todo":
        return ejecutar_todo(args)
    if args.comando == "construir":
        return _cmd_construir(args)
    if args.comando == "informe":
        ruta = Path(args.salida) / "resultados.json"
        if not ruta.exists():
            _log(f"No existe {ruta}")
            return 2
        res = tc_mod.leer_json(ruta)
        md = inf.generar_informe(res, res["config"])
        (Path(args.salida) / "INFORME.md").write_text(md, encoding="utf-8")
        _log("informe regenerado")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
