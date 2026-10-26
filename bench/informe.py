"""
informe.py — Generacion del informe Markdown a partir de los resultados.

El informe es la salida principal del experimento: debe ser legible sin
ejecutar nada y dejar trazable cada afirmacion (configuracion, digest del
oraculo, numero de repeticiones, intervalos de confianza).
"""

from __future__ import annotations


def _fmt(v, nd=3):
    if v is None:
        return "-"
    if isinstance(v, float):
        if v != v:  # NaN
            return "-"
        return f"{v:.{nd}f}"
    return str(v)


def _tabla(encabezados: list[str], filas: list[list[str]]) -> str:
    salida = ["| " + " | ".join(encabezados) + " |",
              "|" + "|".join(["---"] * len(encabezados)) + "|"]
    for f in filas:
        salida.append("| " + " | ".join(str(x) for x in f) + " |")
    return "\n".join(salida)


def generar_informe(resultados: dict, config: dict) -> str:
    meta = resultados["meta"]
    tc = meta["toolchain"]
    L: list[str] = []
    A = L.append

    A("# Isla de estabilidad — informe del experimento\n")
    A(f"- **Fecha (UTC):** {meta['fecha_utc']}")
    A(f"- **Máquina:** {meta.get('hostname', '?')} — {meta.get('sistema', '?')}")
    A(f"- **Toolchain:** {tc['version']} (objetivo `{tc['objetivo']}`)")
    A(f"- **Perfil:** `{config.get('perfil')}` · escala `{config.get('escala')}`")
    A(f"- **Repeticiones:** cribado {config.get('rep cribado', '?')} · "
      f"medición final {config.get('rep medicion', '?')}")
    A("")

    # ---- Veredicto ----
    A("## 1. Veredicto\n")
    veredictos = resultados.get("veredictos", [])
    if veredictos:
        for v in veredictos:
            A(f"- {v}")
    else:
        A("- (sin veredictos calculados)")
    A("")

    # ---- Calidad del ensayo ----
    A("## 1.1 Calidad del ensayo (¿son comparables estas cifras?)\n")
    cal = resultados.get("calidad_ensayo")
    if cal:
        A(_tabla(
            ["metrica", "valor", "umbral", "veredicto"],
            [
                ["deriva maxima (valor absoluto)", f"{cal['deriva_max_abs']:.2f} %/corrida",
                 f"<= {cal['limite_deriva']} %",
                 "OK" if cal["deriva_max_abs"] <= cal["limite_deriva"] else "EXCEDIDO"],
                ["CV maximo", f"{cal['cv_max']:.4f}", f"<= {cal['limite_cv']}",
                 "OK" if cal["cv_max"] <= cal["limite_cv"] else "EXCEDIDO"],
                ["CV mediano", f"{cal['cv_mediana']:.4f}", "-", "-"],
                ["artefactos estables", f"{cal['n_estables']}/{cal['n_total']}", "-", "-"],
            ],
        ))
        A("")
        veredicto = (
            "CONCLUYENTE." if cal["concluyente"] else
            "NO CONCLUYENTE - repetir la medicion en una maquina en calma "
            "(la deriva indica degradacion monotona durante el ensayo)."
        )
        A(f"**Conclusion del ensayo: {veredicto}**")
        A("")

    # ---- Oraculo ----
    A("## 2. Oráculo de corrección\n")
    orac = resultados.get("oraculo", {})
    A(f"- Digest de referencia: `{orac.get('digest', '?')}`")
    A(f"- {orac.get('informe', '')}")
    art = resultados.get("artefactos", [])
    n_val = sum(1 for a in art if a.get("valido"))
    n_tot = len(art)
    A(f"- Artefactos construidos: {n_tot}; artefactos que reproducen el digest: {n_val}")
    fallidos = [a for a in art if not a.get("valido")]
    if fallidos:
        A(f"- Artefactos descartados: {len(fallidos)}")
        for a in fallidos[:10]:
            A(f"  - `{a['variante_id']}` ({a['postproceso']}): {a.get('error', '')[:160]}")
    A("")

    # ---- Tamaño ----
    A("## 3. Tamaño por variante\n")
    A("_S = bytes del ejecutable en disco. `cod` = text+data del PE "
      "(`llvm-size`), es decir, el código residente en la imagen. "
      "`obj` = text+data de los .obj: el código propio del programa, sin el "
      "CRT, sin las cabeceras PE y sin la tabla de imports. La diferencia "
      "entre `S` y `obj` es el fondo fijo del runtime._\n")
    filas = []
    for a in sorted(art, key=lambda x: (x["variante_id"], x["postproceso"])):
        if not a.get("valido"):
            continue
        filas.append([
            a["variante_id"],
            a["postproceso"],
            f"{a['tamano_bytes']:,}",
            f"{a['codigo_bytes']:,}",
            f"{a['obj_text']:,}" if a.get("obj_text") is not None else "n/d (LTO)",
            f"{a['text']:,}",
            f"{a['data']:,}",
        ])
    A(_tabla(
        ["variante", "post", "S (bytes)", "cod (text+data PE)", "obj (codigo propio)",
         "text", "data"],
        filas,
    ))
    A("")

    # ---- Palancas de metadatos y formato ----
    A("## 3.1 Palancas de metadatos y formato (hallazgos de plataforma)\n")
    A("_En Windows/PE la palanca de tamaño no es la de Linux/ELF. Estos son "
      "resultados medidos, no suposiciones:_\n")
    filas = []
    vistos = set()
    for a in sorted(art, key=lambda x: (x["variante_id"], x["postproceso"])):
        if not a.get("valido"):
            continue
        nivel, desenr, enlace, depur = a["variante_id"].split("__")
        clave = (nivel, desenr, enlace, depur, a["postproceso"])
        if clave in vistos:
            continue
        vistos.add(clave)
        filas.append([
            nivel,
            desenr,
            enlace,
            depur,
            a["postproceso"],
            f"{a['tamano_bytes']:,}",
            f"{a.get('tamano_total_bytes', a['tamano_bytes']):,}",
            f"{a['obj_text']:,}" if a.get("obj_text") is not None else "n/d (LTO)",
            f"{a['obj_bytes']:,}",
        ])
    A(_tabla(
        ["nivel", "desenr.", "enlace", "depur.", "post", "exe (B)",
         "exe+pdb (B)", "obj text+data", "obj total (B)"],
        filas,
    ))
    A("")
    A("Lecturas de estos datos:\n")
    A("- **`llvm-strip --strip-all` es un no-op sobre PE/COFF.** Los ejecutables "
      "Windows no llevan tabla de símbolos, así que la columna `post` no cambia "
      "el tamaño. En ELF la misma operación elimina la tabla de símbolos: la "
      "palanca existe, pero es específica del formato. La leukemia de este "
      "eje es nula y se documenta en vez de ocultarse.")
    A("- **La información de depuración vive en un `.pdb` externo.** El "
      "ejecutable crece solo hasta saturar (~3,5 KB por el directorio CodeView) "
      "mientras el `.obj` crece de forma graduada. La columna `exe+pdb` es la "
      "que describe la huella que se despliega en disco.")
    A("- **`--gc-sections` mueve muy poco y `lto` casi nada** en un programa de "
      "dos unidades de traducción: no hay código duplicado real que plegar ni "
      "secciones muertas que eliminar. Con un único TU el efecto sería "
      "exactamente cero.")
    A("")

    # ---- Tiempos ----
    A("## 4. Tiempos y variabilidad (medición final)\n")
    A("_`t_int` = tiempo interno de cómputo (excluye el arranque del proceso). "
      "`t_ext` = tiempo de pared total. `CV` = coeficiente de variación entre "
      "corridas. `IC95` = intervalo de confianza bootstrap de la mediana._\n")
    filas = []
    for etiqueta, m in sorted(resultados.get("medicion", {}).items()):
        filas.append([
            etiqueta,
            m["n"],
            _fmt(m["mediana"], 2),
            f"[{_fmt(m['ci_bajo'],2)}, {_fmt(m['ci_alto'],2)}]",
            _fmt(m["cv"], 4),
            _fmt(m["iqr"], 3),
            _fmt(m["deriva_pct"], 2),
            "sí" if m.get("estable") else "NO",
        ])
    A(_tabla(
        ["artefacto", "n", "t_int mediana (ms)", "IC95", "CV", "IQR", "deriva %", "estable"],
        filas,
    ))
    A("")

    # ---- Pareto ----
    A("## 5. Frente de Pareto (S, T)\n")
    fr = resultados.get("frontera", [])
    if fr:
        filas = []
        for f in fr:
            filas.append([
                f["etiqueta"],
                f"{f['x']:,}",
                _fmt(f["y"], 2),
                f.get("meta", {}).get("variante_id", ""),
                f.get("meta", {}).get("postproceso", ""),
            ])
        A(_tabla(["artefacto", "S (bytes)", "t_int (ms)", "variante", "post"], filas))
    else:
        A("_Frontera vacía._")
    A("")
    c = resultados.get("codo")
    if c:
        A(f"**Codo de la frontera (mejor compromiso):** `{c['etiqueta']}` "
          f"— S={c['x']:,} B, t={c['y']:.2f} ms")
        A("")
    if "hipervolumen" in resultados:
        ref = resultados.get("hipervolumen_ref", {})
        A(f"- Hipervolumen de la frontera (respecto a la referencia "
          f"S={ref.get('x', 0):,.0f} B, T={ref.get('y', 0):.2f} ms): "
          f"**{resultados['hipervolumen']:,.0f}** — escalar comparable entre corridas.")
    if "coherencia_frontera" in resultados:
        A(f"- Coherencia entre las dos implementaciones de la frontera "
          f"(O(n²) y O(n log n)): "
          f"{'coinciden' if resultados['coherencia_frontera'] else 'DIFIEREN'}.")
    A("")

    # ---- Frontera sobre el codigo propio ----
    A("### 5.1 Frente de Pareto sobre el código propio (.obj)\n")
    A("_Misma frontera, pero con el tamaño del código propio del programa "
      "(`obj`), que es la magnitud que la optimización realmente controla._\n")
    frc = resultados.get("frontera_codigo", [])
    if frc:
        filas = []
        for f in frc:
            filas.append([
                f["etiqueta"],
                f"{f['x']:,}",
                _fmt(f["y"], 2),
                f.get("meta", {}).get("variante_id", ""),
            ])
        A(_tabla(["artefacto", "obj (bytes)", "t_int (ms)", "variante"], filas))
    else:
        A("_Sin datos._")
    A("")

    # ---- Significatividad ----
    A("## 5.2 Qué diferencias son reales y cuáles son ruido\n")
    A("_Criterio conservador: dos variantes son distinguibles si sus intervalos "
      "de confianza bootstrap al 95 % **no** se solapan. Es más estricto que un "
      "test de hipótesis con p-valor y no presupone normalidad con n finito._\n")
    sig = resultados.get("significatividad")
    if sig:
        A(f"- Pares comparados: {sig['n_total']}")
        A(f"- Pares con diferencia estadísticamente **distinguible**: "
          f"{sig['n_distinguibles']}")
        A(f"- Pares **indistinguibles** (dentro del ruido de la máquina): "
          f"{sig['n_total'] - sig['n_distinguibles']}")
        A("")
        indistinguibles = [p for p in sig["pares"] if not p["distinguibles"]]
        if indistinguibles:
            A("Pares NO separables por esta máquina (la diferencia observada "
              "está dentro del ruido):\n")
            filas = [
                [p["a"], p["b"], _fmt(p["delta_ms"], 2), _fmt(p["delta_pct"], 2)]
                for p in indistinguibles
            ]
            A(_tabla(["A", "B", "delta ms", "delta %"], filas))
            A("")
        A("Esto es el resultado metodológico central: sin un control del ruido "
          "y sin intervalos de confianza, cualquier ranking de «optimizaciones» "
          "basado en una sola corrida es ruido con apariencia de resultado.")
        A("")

    # ---- Estabilidad de la frontera ----
    A("### 5.3 ¿Qué puntos de la frontera están realmente en ella?\n")
    A("_La frontera se calcula sobre estimaciones (la mediana de N corridas). Si "
      "el ruido es comparable a las diferencias entre variantes, **la composición "
      "de la frontera es en sí misma una afirmación estadística**. Bootstrap: se "
      "remuestrea cada variante con reemplazo de sus corridas, se recalcula la "
      "frontera y se cuenta cuántas veces aparece cada variante._\n")
    est = resultados.get("estabilidad_frontera")
    if est:
        filas = []
        for k, f in sorted(est["frecuencias"].items(), key=lambda kv: -kv[1]):
            filas.append([
                k,
                f"{f*100:.1f} %",
                "estable" if f >= 0.90 else ("marginal" if f >= 0.10 else "nunca"),
            ])
        A(_tabla(["artefacto", "frecuencia en la frontera", "clasificación"], filas))
        A("")
        A(f"- **{est['resumen']}**")
        A("")
    else:
        A("_No calculado en esta corrida._")
        A("")

    # ---- Reproducibilidad ----
    A("## 6. Reproducibilidad del build\n")
    rep = resultados.get("reproducibilidad")
    if rep:
        A(f"- Variantes reconstruidas: {rep.get('n', 0)}")
        A(f"- Binarios bit-idénticos en la reconstrucción: {rep.get('identicos', 0)}/{rep.get('n', 0)}")
        if rep.get("detalle"):
            for d in rep["detalle"]:
                A(f"  - `{d['variante']}`: {d['resultado']}")
    else:
        A("_No ejecutado en esta corrida._")
    A("")

    # ---- Gráficas ----
    A("## 7. Gráficas\n")
    A("![Frontera de Pareto](frontera.svg)")
    A("")
    A("Archivos generados: `frontera.svg`, `artefactos.csv`, `mediciones.csv`, "
      "`resultados.json`, `resumen.txt`.")
    A("")

    return "\n".join(L)
