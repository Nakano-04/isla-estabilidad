# Protocolo experimental — «Isla de estabilidad»

Banco de pruebas reproducible para medir, sobre un programa benigno y
determinista, la frontera entre **tamaño**, **tiempo** y **variabilidad** de un
binario compilado, y para decidir qué diferencias observadas son reales y
cuáles son ruido de máquina.

Este documento es el contrato del experimento. El código lo implementa; este
documento explica por qué lo implementa así, y sobre todo **qué habría que
cambiar para que los números fueran incorrectos**.

La teoría que se deriva de los resultados está en **`docs/TEORIA.md`**: por
qué el término «isla» debe reformularse, cómo se cuantifica la resolución de
la medición, y por qué un resultado nulo de optimización puede ser falso.

---

## 1. Pregunta

¿Existe una región del espacio de configuraciones de compilación en la que un
programa sea simultáneamente más pequeño, más rápido y más repetible que en
las configuraciones vecinas — de modo que el conjunto de configuraciones
«aceptables» tenga forma de isla y no de un continuo indiferenciado?

## 2. Hipótesis

**H1 (existe la isla).** El espacio de configuraciones se particiona en
regiones; en una de ellas, reducir el tamaño no degrada el tiempo más allá de
un umbral, y la variabilidad entre ejecuciones permanece por debajo de ese
umbral.

**H2 (el tamaño tiene un suelo de entropía).** Existe un mínimo de bytes por
debajo del cual el programa no puede mantener su capacidad. Por debajo de ese
suelo, cualquier reducción de tamaño se paga en corrección o en tiempo.

**H3 (la frontera de Pareto es informative).** La frontera (S, T) no es un
subconjunto arbitrario: identifica un conjunto pequeño de configuraciones
dominantes cuyo número de elementos es mucho menor que el del espacio
explorado.

**H4 (las diferencias pequeñas son ruido).** Una fracción relevante de las
diferencias de tiempo observadas entre configuraciones vecinas no son
distinguibles del ruido de medición, y un protocolo sin control de ruido
produciría un ranking falso.

## 3. Sistema bajo prueba (SUT)

`src/carga.c` + `src/aux.c`. Programa benigno, sin E/S, sin red, sin aleatoriedad
no sembrada y **sin punto flotante**.

Propiedades exigidas al SUT:

| Propiedad | Por qué |
|---|---|
| Aritmética entera de 64 bits con semántica bien definida | Que ninguna optimización pueda cambiar el resultado: el programa debe ser bit-idéntico entre `-O0` y `-Oz` |
| PRNG con **semillas independientes por componente** | Desacopla el orden de consumo de números aleatorios entre componentes, lo que permite una reimplementación independiente que produzca exactamente la misma salida |
| Salida = un `digest` estable (FNV-1a sobre una cadena canónica de campos) | Permite comparación byte a byte entre variantes, y por tanto detección de no-determinismo |
| Carga de trabajo heterogénea | Que el tamaño y el tiempo respondan de forma distinta a cada palanca: ordenación (memoria + ramas), multiplicación de matrices (FLOPs), procesamiento de texto (memoria secuencial), búsquedas binarias (dependencia de datos) |
| Segunda unidad de traducción con código duplicado | Sin funciones idénticas que plegar ni código muerto que eliminar, `--gc-sections` e ICF darían un resultado nulo trivial que no informa nada |

## 4. Métricas

| Símbolo | Métrica | Definición | Instrumento |
|---|---|---|---|
| **S** | Tamaño en disco | bytes del ejecutable | `stat` del `.exe` |
| **S′** | Tamaño total desplegado | `.exe` + `.pdb` + `.ilk` | suma de la huella real |
| **S_cod** | Código en la imagen | `text + data` del PE | `llvm-size` |
| **S_obj** | Código propio del programa | `text + data` de los `.obj` | `llvm-size` sobre los `.obj` |
| **T_int** | Tiempo interno de cómputo | del inicio al fin de la región de cómputo, **excluyendo el arranque del proceso** | `QueryPerformanceCounter` dentro del binario |
| **T_ext** | Tiempo de pared total | incluye `CreateProcess` + carga de DLL | `perf_counter_ns` alrededor del `subprocess` |
| **V** | Variabilidad | CV = σ/μ entre corridas; además IQR, MAD, P05/P95 | estadística sobre las N corridas |
| **D** | Deriva | pendiente de la regresión de T sobre el índice de corrida | regresión lineal |

**Por qué S_obj además de S.** En Windows/PE, el ejecutable incluye un fondo
fijo (cabecera PE, tabla de imports, arranque del CRT) que no depende del
código que estamos optimizando. Con CRT estático ese fondo es de ~145 KB y
aplasta el efecto real: `-Oz` frente a `-O0` pasa de 48 % menos de código a
«1 % menos de archivo». `S_obj` aísla la magnitud que la optimización
controla; `S` describe la realidad de despliegue.

**Por qué T_int además de T_ext.** En Windows el arranque de un proceso cuesta
10–40 ms, del mismo orden que la carga de trabajo. Medir sólo tiempo de pared
mezcla el coste del sistema operativo con el del programa. `T_int` es la
métrica de comparación entre configuraciones; `T_ext` es la de coste real de
despliegue.

**Por qué V es una dimensión y no un residuo.** La literatura de tuning trata
la varianza como fuente de ruido a eliminar. Aquí es un eje que se reporta y
que se usa como filtro de factibilidad: una configuración cuyo resultado
depende de la-alignación de caché o de la paginación no es una configuración
estable, por rápida que sea.

## 5. Oráculo de corrección

Un artefacto sólo entra en la frontera de Pareto si **reproduce el digest
exacto** del oráculo en *todas* las corridas.

El oráculo se valida por **doble implementación independiente**:

- **(a)** el binario C compilado a `-O0` (semántica ingenua, sin optimización);
- **(b)** una reimplementación completa en Python (`src/referencia.py`), escrita
  desde la especificación y no desde el código.

Que ambas coincidan byte a byte es lo que cierra el defecto clásico del
*differential testing*: si ambas implementaciones compartieran un error, el
test no lo detectaría. Si discrepan, el experimento **se aborta** antes de
medir nada.

> Esto ya finds un bug real: la reimplementación en Python reinicializaba el
> generador de números pseudoaleatorios antes de llenar la matriz B, mientras
> el C continuaba el flujo. La discrepancia fue detectada por el oráculo, no
> por la revisión de código.

**Invariantes metamórficos** comprobados implícitamente al comparar digests:
`suma_quicksort == suma_heapsort` (dos algoritmos de ordenación independientes
deben producir la misma suma) y el digest must ser idéntico con y sin
optimización.

## 6. Espacio de búsqueda

Producto cartesiano declarativo de cuatro ejes (ver `bench/espacio.py`):

| Eje | Valores | Dimensión de la teoría |
|---|---|---|
| `nivel_opt` | `-O0 -O1 -O2 -O3 -Os -Oz` | B — optimización de código |
| `desenrollado` | con / sin tablas de desenrollado | C — estructura del binario |
| `enlace` | defecto / `--gc-sections` / LTO thin / LTO thin + ICF | B+C |
| `depuracion` | sin info / `-gline-tables-only` / `-g` | C — metadatos |

Eje post-proceso (fuera del grid, aplicado a cada artefacto): conservar /
`llvm-strip --strip-all`.

El espacio es **declarativo, no aleatorio**: cada variante es auditable y el
conjunto completo se puede reconstruir a partir del manifiesto. Un generador
de mutaciones al azar daría una muestra no reproducible del espacio.

**Decisiones de toolchain, y su porqué:**

- **Driver GNU de clang** (`clang --target=x86_64-pc-windows-msvc`), no
  `clang-cl`: `clang-cl` no reconoce `/O3` ni `/Oz` (los reenvía al enlazador),
  y el rango completo de niveles de optimización es justamente lo que se quiere
  explorar.
- **CRT dinámico explícito** (`/NODEFAULTLIB:libcmt` + `/DEFAULTLIB:msvcrt,ucrt,vcruntime`):
  el driver GNU ignora `-MD` sobre el target MSVC y enlaza siempre `libcmt`
  estático. Medido: 159 744 B → 14 848 B con el mismo código.
- **`/Brepro`** en lld-link: sin esto el PE lleva marca de tiempo y `S` es
  ruido entre dos compilaciones idénticas.
- **`-ffile-prefix-map`**: elimina la ruta absoluta del directorio de
  compilación del binario.
- **`-Werror`**: que ninguna variante compile con avisos, para que las
  comparaciones sean entre iguales.

## 7. Protocolo de medición

### 7.1 Dos fases: cribado y caracterización

1. **Cribado.** Todas las variantes se construyen y se miden con pocas
   repeticiones (5). Se calcula la frontera de Pareto de los datos de
   cribado y se seleccionan losasternas: los no dominados, más el mejor de
   cada nivel de optimización, más el mejor de cada nivel por `S_obj`.
2. **Caracterización.** Sólo los finalistas se miden con N = 40 repeticiones.

Motivo: medir 288 artefactos × 40 repeticiones costaría ~35 minutos de tiempo
de máquina. El cribado es la técnica estándar de SBSE para reducir el coste
sin perder la frontera.

### 7.2 Intercalado y rotado

Todas las variantes se ejecutan en el mismo orden cíclico, no «todas las
repeticiones de A, luego todas las de B». Además, **el orden dentro de cada
ronda rota**: sin rotación, cada variante ocupa siempre la misma posición, y
una degradación monótona de la máquina penaliza sistemáticamente a las
mismas variantes.

### 7.3 Calentamiento

Una pasada de calentamiento por artefacto, descartada. Las primeras
ejecuciones pagan la paginación del binario a disco y el calentamiento de la
caché de código.

### 7.4 Afinidad de CPU

Se fija la máscara de afinidad del proceso padre (los hijos la heredan).
Medido en esta máquina (i7-13700, 24 hilos lógicos = 8 P-cores con HT + 8
E-cores):

| Núcleos | Mediana | Nota |
|---|---|---|
| 0–15 | 35,2 – 38,0 ms | P-cores |
| 16–23 | 52,8 – 55,5 ms | E-cores |

Fijar el proceso en un E-core infla el tiempo un 50 % y deforma todas las
comparaciones. **Medir esto antes de medir nada** no es un detalle: es la
diferencia entre un experimento válido y uno que compara rendimiento de
núcleos en vez de rendimiento de código.

### 7.5 Asentamiento

Tras construir decenas de ejecutables, el antivirus del sistema los escanea.
Se deja un margen (`settle_segundos`) antes de medir: medir durante esa
ventana produce una degradación monótona que ningún ajuste estadístico
arregla.

## 8. Control de ruido y validez del ensayo

El arnés no publica resultados de una máquina ruidosa: **rechaza el ensayo**.

| Señal | Umbral | Significado |
|---|---|---|
| `D` (deriva) | ≤ 3 %/corrida | La máquina no se degrada de forma monótona durante el ensayo |
| `CV` | ≤ 0,20 | La dispersión relativa entre corridas es acotada |
| Estabilidad del digest | 100 % | Toda corrida de toda variante reproduce el digest |

Si `D` o `CV` exceden el umbral, el informe marca el ensayo como **NO
CONCLUYENTE** y los artefactos quedan fuera de la frontera de Pareto por
factibilidad. Esto ya ocurrió en una corrida de desarrollo: la deriva llegó a
1,9 %/corrida y el CV a 0,30, y el arnés devolvió «0 de 16 artefactos
factibles» en lugar de publicar un ranking de tiempos claramente contaminado
por Chrome ejecutándose en segundo plano.

### 8.1 Avisos del toolchain: una palanca puede no aplicarse en silencio

Un enlazador que recibe una opción que no reconoce **la ignora, avisa y
sigue**. El resultado experimental es entonces un nulo plausible pero falso:
«ICF no ahorra nada» era en realidad «el flag nunca se aplicó».

Por eso `bench/construir.py` analiza la salida del enlazador y **descarta la
variante** si aparece un aviso del tipo `ignoring unknown argument`. Una
variante descartada no entra en la frontera de Pareto, de modo que un nulo
falso no puede volver a colarse. `bench/verificar.py` comprueba además que
ninguna variante marcada como válida lleve avisos.

Esta regla tiene más valor que el resultado que.protector: en cualquier
benchmark que mida el efecto de una herramienta, el primer control no es
«¿cuánto ahorra?» sino «**¿se aplicó?**».

### 8.2 Significatividad

Dos configuraciones son **estadísticamente distinguibles** si sus intervalos
de confianza bootstrap al 95 % (2 000 remuestreos de la mediana) **no se
solapan**. Es un criterio más conservador que un test con p-valor y no
presupone normalidad con n finito. El informe lista explícitamente los pares
**no** separables: esos son los que un protocolo ingenuo habría presentado
como «-O2 es más rápido que -O1».

## 9. Análisis

- **Frontera de Pareto** sobre (S, T_int), restringida a los puntos factibles
  (CV dentro de umbral y digest estable). No se ordena por un escalar: el
  objetivo es la *curva de compromiso*, y ordenar por tamaño aplana
  precisamente la información que se busca.
- **Codo de la frontera**: punto de mayor distancia perpendicular a la recta
  que une los extremos. Es el compromiso más equilibrado.
- **Frontera secundaria sobre `S_obj`**, que excluye las variantes con LTO
  (su `.obj` es bitcode y el código pre-enlazado no es medible).
- **Hipervolumen** y tablas depercentage comparaciones por nivel.

## 9.1 Estabilidad de la frontera

La frontera de Pareto se calcula sobre estimaciones. Si el ruido es comparable
a las diferencias entre variantes, **la composición de la frontera es en sí
misma una afirmación estadística**.

El protocolo la cuantifica: `bench/pareto.py: estabilidad_frontera` remuestrea
cada variante con reemplazo de sus corridas medidas (500 remuestreos),
recalcula la mediana y la frontera, y cuenta la frecuencia de selección de cada
variante. Se reportan tres clases:

| Frecuencia | Clase | Lectura |
|---|---|---|
| ≥ 90 % | estable | hallazgo |
| 10–90 % | marginal | su pertenencia la decide el ruido: **no citar** |
| < 10 % | nunca | descartada |

Resultado de la corrida de referencia: de 13 variantes medidas, **1 estable,
3 marginales, 9 nunca**. La frontera puntual declara 3 puntos, pero sólo uno
es reproducible.

## 10. Reproducibilidad

El arnés **reconstruye** tres variantes al final y compara el SHA-256 del
ejecutable con el original. Un build no reproducible es un build en el que `S`
no significa nada. Los mecanismos: `/Brepro`, `-ffile-prefix-map`, CRT
dinámico, dos pasos compile→link.

## 10.1 Autocomprobación

`bench/verificar.py` es parte del protocolo, no un extra. Comprueba:

1. que todo artefacto marcado como válido reproduce el digest del oráculo;
2. que cada medición tiene el número de repeticiones configurado, su IC
   ordenado y su mediana dentro del IC;
3. que la frontera no contiene puntos dominados **y que todo punto no
   dominado del conjunto está en ella** (si no, la frontera estaría
   incompleta);
4. que el recuento de significatividad cuadra con la lista de pares;
5. que el SVG dibuja exactamente los puntos medidos;
6. (`--fuzz`) que las dos implementaciones de la frontera de Pareto —fuerza
   bruta O(n²) y barrido O(n log n— producen el mismo conjunto.

Esta comprobación encontró dos bugs reales durante el desarrollo:

- **La reimplementación Python reinicializaba el PRNG** antes de llenar la
  matriz B, mientras que el C continuaba el flujo. El oráculo de doble
  implementación abortó el experimento antes de medir nada. Un protocolo con
  una sola implementación habría publicado un resultado con la mitad de los
  valores de matriz equivocados.
- **La versión «optimizada» de la frontera de Pareto descartaba puntos** y
  trataba mal los duplicados exactos. El contraste contra la fuerza bruta lo
  detectó; se confirmó después con 20 000 casos aleatorios.

Que el banco de pruebas encuentre errores en sí mismo es un requisito, no un
extra: un instrumento que nunca se ha puesto a prueba no es un instrumento.

## 11. Amenazas a la validez

| Amenaza | Tipo | Mitigación / estado |
|---|---|---|
| El SUT no es representativo | Externa | Un único programa, una sola arquitectura. Los números de tamaño **no** se generalizan; la *metodología* sí |
| CRT de fondo fijo | Constructiva | Se mide `S_obj` además de `S` para aislar el efecto |
| Arranque del proceso en la medición | Constructiva | Se mide `T_int` además de `T_ext` |
| Ruido de la máquina | Interna | Intercalado + rotación + IC bootstrap + deriva + umbral de validez |
| Sesgo del conjunto de tests | Constructiva | Oráculo de doble implementación + invariantes metamórficos |
| El optimizador puede encontrar atajos que rompen casos no cubiertos | Externa | Los tests son de equivalencia de salida completa (digest), no un subconjunto; un atajo que altere cualquier campo observable cambia el digest |
| Auto-selección del subconjunto medido | Interna | La selección de finalistas usa sólo datos de cribado; el conjunto final se mide aparte |
| E-core vs P-core | Interna | Medido y documentado antes de fijar la afinidad |

## 12. Resultados obtenidos

Ver `resultados/*/INFORME.md` para los números de cada corrida,
`resultados/*/frontera.svg` para la representación gráfica y
`docs/TEORIA.md` para el desarrollo theoretical.

Hallazgos de esta implementación (plataforma Windows/PE):

1. **El nivel de optimización es la palanca dominante.** El código propio pasa
   de 7 348 B (`-O0`) a 3 781 B (`-Oz`): **−48,5 %**. En el ejecutable completo
   el efecto es mucho menor (−16,7 %) porque el fondo fijo del runtime no se
   mueve.
2. **`-Oz` es el más pequeño y el más lento.** Es la observación central: la
   reducción de tamaño tiene un precio en tiempo, y el precio no es
   monótono en el nivel de optimización (`-O3` es más grande *y* no más rápido
   que `-O2`).
3. **El intercambio no es uniforme.** La tasa marginal cambia de orden de
   magnitud a lo largo de la misma frontera (~28 ms/KB en el tramo `-Oz`→`-Os`
   frente a ~0,5 ms/KB en los tramos con metadatos).
4. **La frontera es una distribución, no un conjunto.** Bootstrap de 500
   remuestreos: de 13 variantes, **1 estable**, 3 marginales, 9 nunca.
5. **`llvm-strip --strip-all` es un no-op sobre PE/COFF.** Los ejecutables
   Windows no llevan tabla de símbolos. La palanca equivalente en PE es el
   directorio CodeView y el `.pdb` externo.
6. **La información de depuración se va al `.pdb`**, no al ejecutable: el
   `.exe` crece ~3,5 KB mientras el `.pdb` añade **~470 KB**. La huella total
   desplegada pasa de 16 KB a ~485 KB (30×).
7. **El plegado de código idéntico en PE lo produce la semántica COMDAT**, no
   ICF: `-ffunction-sections` (que emite cada función en su propia sección
   COMDAT) basta, y `/OPT:ICF` no añade nada. El ICF de ELF (`--icf=all`) y
   `--gc-sections` son banderas inválidas en `lld-link`, que las ignora con un
   aviso. Ver `docs/TEORIA.md` §5.
8. **El ruido de medición es proporcional, no aditivo.** La hipótesis «ruido
   absoluto ⇒ CV ~ k/T» queda refutada por un factor 52 al variar la carga
   39×. La resolución depende sólo de n: `ancho_IC95 ≈ 4,91·CV/√n`.

## 13. Lo que este banco NO es

Este trabajo mide **tamaño, tiempo y variabilidad de binarios benignos**. No
diseña empaquetadores, ni busca variantes para evadir EDR/XDR, ni construye
implantes.

La relación entre las tres métricas que el usuario llamaba «métrica de
detectabilidad» y las dos que aquí se miden es **no universal**: reducir el
tamaño en disco no reduce la probabilidad de que un control de seguridad
identifique el archivo o su comportamiento. Los empaquetadores son, de hecho,
una señal de detección por sí mismos (firmas de secciones anómalas,
transiciones de protección de memoria, código generado dinámicamente) y hoy
suelen **aumentar** la detectabilidad respecto del binario original. Véase
`CITAS.md`, área 8.

## 14. Trabajo futuro

- Replicar el protocolo sobre `clang`/`gcc` en Linux con ELF, donde las
  palancas de formato (`--strip`, `--gc-sections`, ICF, `objcopy`) sí tienen
  efecto, y comparar el contraste con PE.
- Sustituir el cribado por una búsqueda local con vecindad explícita
  (hill climbing sobre el grid) y comprobar si converge al mismo conjunto.
- Extender el oráculo con una tercera implementación independiente y con
  *property-based testing* sobre las invariantes.
- Medir el eje de «capacidad útil por byte» (§2H2): el suelo de entropía
  exige una noción de capacidad, no sólo de tamaño.
