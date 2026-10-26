# Isla de estabilidad

Banco de pruebas **reproducible** para el experimento «isla de estabilidad»:
medir la frontera entre **tamaño (S)**, **tiempo (T)** y **variabilidad (V)** de
un binario compilado, y decidir qué diferencias observadas son reales y cuáles
son ruido de máquina.

No es un empaquetador, ni un generador de variantes para evadir EDR/XDR, ni
construye implantes. Es un laboratorio de ingeniería de rendimiento y tamaño
sobre un programa **benigno y determinista**, con oráculo de corrección
verificado y control estadístico del ruido.

---

## Resultados de la corrida de referencia

Perfil `estandar`, 72 variantes construidas (144 artefactos), 13 finalistas
caracterizados con 40 repeticiones intercaladas.

| Métrica | Valor |
|---|---|
| Ensayo | **CONCLUYENTE** (deriva máx. 0,17 %/corrida · CV máx. 0,077) |
| Reproducibilidad del build | 3/3 ejecutables **bit-idénticos** al reconstruir |
| Oráculo | C(`-O0`) y reimplementación Python coinciden: `digest=a3b3830f37ff94a0` |
| Estabilidad | 13/13 artefactos reproducen el digest en todas las corridas |
| Código propio (`-O0` → `-Oz`) | 7 348 B → 3 781 B (**−48,5 %**) |
| Ejecutable completo (`-O0` → `-Oz`) | 15 360 B → 12 800 B (−16,7 %) |
| Distingibles estadísticamente | 61/78 pares de tiempo (IC95 sin solape) |
| **Estabilidad de la frontera** | **1 variante estable, 3 marginales, 9 nunca** |

**Frente de Pareto puntual (S, T)** — 3 puntos:

| Artefacto | S (bytes) | T interno (ms) | Frecuencia en la frontera |
|---|---:|---:|---:|
| `Oz__sin__defecto__sin_info` | 12 800 | 53,34 | 81,8 % (marginal) |
| `Os__sin__lto_thin__sin_info` | 13 312 | 39,10 | **100 % (estable)** |
| `O2__sin__defecto__sin_info` | 14 848 | 38,28 | 88,0 % (marginal) |

**El único hallazgo estructural de la frontera es `Os__sin__lto_thin__sin_info`:
13 312 B / 39,10 ms.** Las otras dos pertenecen a la frontera sólo en el 82–88 %
de los remuestreos bootstrap: su posición la decide el ruido, no el diseño.

El perfil `completo` (144 variantes, 288 artefactos, 20 finalistas, incluye
ICF y `-g` completo) está también en `resultados/completo/`, y los
experimentos dirigidos en `resultados/experimentos/`.

### Hallazgos que sólo aparecen al ejecutar el experimento

1. **El nivel de optimización es la palanca dominante; el resto es ruido.**
   `-Oz` reduce el código propio un 48,5 %, pero `--gc-sections`, LTO e ICF
   mueven décimas de byte. En un programa real el tamaño está donde está el
   código, no en los trucos de enlazado.
2. **`-Oz` es el más pequeño y el más lento.** La reducción de tamaño tiene
   precio en tiempo, y el precio **no es monótono** en el nivel de
   optimización: `-O3` es más grande *y* no más rápido que `-O2`.
3. **`llvm-strip --strip-all` es un no-op sobre PE/COFF.** Los ejecutables
   Windows no llevan tabla de símbolos. La palanca equivalente en PE es el
   directorio CodeView y el `.pdb` externo. El eje se conserva precisamente
   para documentar ese resultado negativo.
4. **La información de depuración se va al `.pdb`, no al ejecutable — y el
   `.pdb` es enorme.** El ejecutable sólo crece ~3,5 KB (de 16 384 a
   18 432 B), pero el `.pdb` añade **~470 KB**: la huella total pasa de 16 KB
   a **~485 KB**, es decir, 30× el binario. Quien despliegue con información
   de depuración despliega medio megabyte, no dieciséis kilobytes. Medir sólo
   el `.exe` escondía el 97 % del coste.
5. **El «ICF no ahorra nada» del primer perfil era un resultado FALSO, y el
   control que lo detecta es leer los warnings del toolchain.** Dos banderas
   del primer perfil (`--icf=all`, `--gc-sections`) son sintaxis de
   **lld-ELF**; `lld-link` las **ignora con un warning** y sigue. Midiendo el
   *mecanismo* (contando copias de una función byte-idéntica en el `.text`),
   la realidad es otra: el plegado lo produce la **semántica de selección
   COMDAT de PE**, que se activa con `-ffunction-sections` y **no necesita
   ninguna opción de ICF**. `/OPT:ICF` (la sintaxis válida) no añade nada,
   porque el trabajo ya lo había hecho el formato. Y **lld-link hace
   recolección de secciones muertas por defecto**, así que `--gc-sections` era
   doblemente redundante.
   → El protocolo ahora **descarta cualquier variante cuyo enlazador emita un
   aviso de «opción ignorada»**.
6. **`--gc-sections` y LTO mueven poco** en un programa de dos unidades de
   traducción sin código duplicado real. Resultado nulo, pero no trivial: dice
   algo sobre dónde está el tamaño en un programa real.
7. **El fondo fijo del runtime puede invertir el resultado.** Con CRT estático
   (`libcmt`, ~145 KB) el efecto de `-Oz` sobre el archivo es del 1 %; con CRT
   dinámico es del 17 %. Elegir mal el runtime hace que el experimento mida
   el runtime en vez del código.
8. **Casi la mitad de las comparaciones de tiempo son ruido.** En el perfil
   completo, 83 de 190 pares (44 %) no son separables por IC95 — incluidas
   diferencias entre `-O2` y `-O3`, que son de 0,2–0,4 ms. Un protocolo de
   una sola corrida habría producido un ranking falso.

### Lo que dijo el experimento y lo que dijo la teoría

Cuatro hallazgos que van más allá de los números:

- **La frontera no es un conjunto, es una distribución sobre conjuntos.**
  Bootstrap de 500 remuestreos sobre las corridas medidas: de 13 variantes,
  **sólo una** pertenece a la frontera de forma estable (frecuencia ≥ 90 %),
  dos son marginales (82–88 %) y nueve nunca aparecen. «La frontera contiene
  3 puntos» es una afirmación sin barra de error, y es falsa en el 12–18 % de
  las realizaciones. La forma publicable es *«cuáles la pertenecen con
  frecuencia alta»*, no *«cuáles son»*.
- **El intercambio tamaño/tiempo no es uniforme.** La tasa marginal cambia de
  orden de magnitud a lo largo de la misma frontera: ~28 ms/KB en el tramo
  `-Oz` → `-Os` frente a ~0,5 ms/KB en los tramos con metadatos. No hay «un
  punto óptimo» que buscar: hay tramos.
- **El ruido de medición es proporcional, no aditivo.** Alargar la carga de
  trabajo **39×** deja el CV igual (≈0,05). La hipótesis «ruido absoluto ⇒
  CV ~ k/T» queda refutada por un factor 52. Consecuencia práctica: sólo
  `n` abarata la medición — resolver un 1 % exige ~650 corridas por variante.
- **Elegir la métrica de tamaño cambia lo que se ve.** `r(S_total, T) = +0,09`
  frente a `r(S_código, T) = +0,45`: agrupar «código» y «metadatos» en
  «bytes» destruye la señal.

Todo esto está desarrollado en **`docs/TEORIA.md`**, con los experimentos que
lo someten a prueba.

---

## Estructura

```
isla-estabilidad/
├── README.md              este documento
├── CITAS.md               bibliografía verificada (54 entradas, 8 áreas)
├── config/
│   └── experimento.json   perfiles, límites, parámetros de medición
├── docs/
│   ├── PROTOCOLO.md       el contrato experimental: qué, por qué y amenazas
│   ├── TEORIA.md          qué significa realmente una «isla», y sus límites
├── src/
│   ├── carga.c            carga de trabajo benigna y determinista
│   ├── aux.c / aux.h      segunda TU: código duplicado + código muerto
│   └── referencia.py      reimplementación independiente en Python (oráculo)
├── bench/
│   ├── toolchain.py       descubrimiento de clang + entorno de vcvars
│   ├── espacio.py         definición del espacio de búsqueda
│   ├── construir.py       build en dos pasos y medición de tamaño
│   ├── medir.py           medición intercalada y rotada
│   ├── estadistica.py     mediana, MAD, CV, IC bootstrap, deriva
│   ├── pareto.py          dominancia, frontera, codo, hipervolumen
│   ├── grafica.py         renderizado SVG (sin dependencias)
│   ├── informe.py         informe Markdown
│   ├── verificar.py       auto-comprobación de coherencia de los resultados
│   ├── experimentos.py    experimentos dirigidos (mecanismo ICF, ruido vs carga)
│   └── run.py             orquestador
└── resultados/            salidas (INFORME.md, frontera.svg, *.csv, *.json)
```

**Sin dependencias externas**: sólo la biblioteca estándar de Python.

---

## Uso

```bash
cd isla-estabilidad

python -m bench.run todo --perfil estandar       # pipeline completo
python -m bench.run todo --perfil rapido         # ~4x más rápido
python -m bench.run todo --perfil completo       # incluye ICF y -g completo
python -m bench.run construir                    # sólo construye
python -m bench.run informe                      # regenera INFORME.md
python -m bench.verificar resultados/estandar    # auto-comprobación
python -m bench.verificar resultados/estandar --fuzz 20000   # + fuzz de Pareto
python -m bench.experimentos icf                 # E1: mecanismo del plegado
python -m bench.experimentos escala --reps 60     # E2: ruido vs carga de trabajo
```

Opciones: `--perfil`, `--escala N`, `--repeticiones N`, `--rep-cribado N`,
`--salida DIR`.

`bench/verificar.py` comprueba sobre `resultados.json` que el oráculo es
coherente, que cada medición tiene el número de repeticiones configurado y
su digest correcto, que la frontera no contiene puntos dominados y que **todo**
punto no dominado está en ella, que el recuento de significatividad cuadra, y
que el SVG dibuja exactamente los puntos medidos. Con `--fuzz` contrasta
además las dos implementaciones de la frontera de Pareto (fuerza bruta O(n²) y
barrido O(n log n)) sobre miles de casos aleatorios.

### El arnés encontró sus propios bugs

Tres de ellos sólo aparecieron al añadir controles, y son ilustrativos del
tipo de error que un laboratorio sin controles arrastra:

| Bug | Cómo se detectó |
|---|---|
| La reimplementación Python reinicializaba el PRNG antes de la matriz B (el C continuaba el flujo) | El **oráculo de doble implementación** abortó el experimento antes de medir nada |
| La versión "optimizada" de la frontera de Pareto (`soluciones_pareto`, barrido O(n log n)) descartaba puntos y manejava mal los duplicados exactos | El **contraste contra la fuerza bruta** (O(n²)) en `verificar.py`; confirmado después con 20 000 casos aleatorios |
| Dos banderas del espacio de búsqueda (`--icf=all`, `--gc-sections`) son **sintaxis de lld-ELF** que `lld-link` ignora con un warning → un «nulo» falso sobre el plegado de código | El experimento dirigido `bench.experimentos icf`, que midió el **mecanismo** (copias de la función) en vez del tamaño, y el nuevo control que **descarta variantes con avisos del enlazador** |

---

## Qué hace el arnés, paso a paso

1. **Descubre el toolchain** y captura el entorno de compilación.
2. **Valida el oráculo**: compila la referencia a `-O0` y la compara con la
   reimplementación en Python. Si discrepan, **aborta**.
3. **Construye** el producto cartesiano de los cuatro ejes, en dos pasos
   (compile → `.obj`, link → `.exe`), y mide `S`, `S'`, `S_cod`, `S_obj`.
4. **Criba** todas las variantes con pocas repeticiones y selecciona las
   finalistas por no dominancia + mejor de cada nivel.
5. **Caracteriza** a las finalistas con 40 repeticiones intercaladas y
   rotadas, midiendo `T_int`, `T_ext`, `V` y verificando el digest en *cada*
   corrida.
6. **Verifica la reproducibilidad** del build reconstruyendo tres variantes y
   comparando SHA-256.
7. **Analiza**: frontera de Pareto, codo, hipervolumen, significatividad por
   solapamiento de IC y diagnóstico de calidad del ensayo.
8. **Publica** `INFORME.md`, `frontera.svg`, `artefactos.csv`,
   `mediciones.csv`, `resultados.json`.

---

## Los controles que importan

| Control | Qué evita |
|---|---|
| Oráculo de **doble implementación** | Reportar una variante que cambia el comportamiento (el differential testing con una sola implementación no lo detecta) |
| Medición **intercalada y rotada** | Penalizar siempre a las mismas variantes por la posición en la ronda |
| **IC bootstrap** sobre la mediana | Reportar diferencias que son ruido |
| **Diagnóstico de deriva** + umbral de validez | Publicar un ranking de tiempos contaminado por la deriva térmica o por el antivirus del sistema |
| `T_int` además de `T_ext` | Medir el arranque del proceso en vez del programa |
| `S_obj` además de `S` | Medir el CRT en vez del código |
| `/Brepro` + verificación SHA-256 | Medir marcas de tiempo en vez de código |
| **Afinidad de CPU medida antes de fijar** | Comparar el rendimiento de un E-core con el de un P-core (50 % de diferencia) |

---

## Alcance y límites

Este trabajo mide tamaño, tiempo y variabilidad de **binarios benignos**.

No hay relación universal entre «el archivo ocupa menos bytes» y «es menos
detectable». Los empaquetadores son en sí mismos una señal (secciones
anómalas, transiciones de protección de memoria, código generado dinámicamente)
y hoy suelen **aumentar** la detectabilidad respecto del binario original —
véase `CITAS.md`, área 8, y la técnica MITRE ATT&CK **T1027.002
(Software Packing)**.

Lo que sí es transferible a un contexto defensivo: la caracterización de
fronteras de fallo entre hosts, la caracterización de configuraciones que
**producen** comportamiento no determinista, y la disciplina de medir antes
de afirmar.

Véase `docs/PROTOCOLO.md` §11 (amenazas a la validez) y §13 (lo que este banco
no es).
