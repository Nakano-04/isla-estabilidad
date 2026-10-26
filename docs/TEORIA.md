# Teoría — qué es realmente una «isla de estabilidad»

Documento derivado de los resultados del banco de pruebas. Cada afirmación
teórica de aquí está anclada en una medición concreta, y se indica cómo
refutarla.

Los hallazgos que motivan la teoría son cuatro, y ninguno era evidente antes
de medir:

- **H-A.** El «intercambio» entre tamaño y tiempo **no es uniforme**: la tasa
  marginal cambia de orden de magnitud a lo largo de la frontera.
- **H-B.** El ruido de medición es **proporcional**, no aditivo: alargar la
  carga de trabajo 39× no mejora la resolución **ni un 0,1 %**.
- **H-C.** Un resultado nulo de una palanca de tamaño puede ser **falso**: en
  este banco, dos banderas inválidas produjeron un «ICF no ahorra nada»
  convincentemente equivocado.
- **H-D.** La **frontera misma es una afirmación estadística**: bootstrap de
  500 remuestreos deja **una sola** variante establemente en ella, de 13
  medidas.

---

## 1. El error categorial: tres cosas distintas que se llaman «isla»

La expresión «isla de estabilidad» mezcla tres objetos matemáticos
distintos, con propiedades distintas:

| Objeto | Definición | ¿Tiene estructura? |
|---|---|---|
| **Paisaje de aptitud** (fitness landscape) | Conjunto de óptimos locales rodeados de cuencas | Islas = cuencas aisladas; hay que subir y bajar |
| **Frente de Pareto** | Configuraciones no dominadas en (S, T) | Es una *franja* 1-dimensional, no un blob aislado |
| **Región factible** | {x : T(x) ≤ T_max ∧ V(x) ≤ V_max ∧ correcto(x)} | Es una porción del espacio, delimitada por umbrales |

La literatura de *islas de estabilidad* (evolvability, tuning bayesiano)
usa el primer sentido: cuencas locales en un espacio de búsqueda. Eso es lo
que se está buscando cuando se habla de «encontrar una isla». Pero ese
sentido **no es el que describe el compromiso tamaño/tiempo**, que es un
problema de **eficiencia multiobjetivo**, no de landscape.

**Lo que se midió empíricamente es el segundo objeto: una franja (frente de
Pareto) que separa un interior dominado de un exterior inviable.** No hay
islas porque no hay saltos: el espacio de configuraciones de compilación es
casi conexo, y el compromiso se optimiza de forma continua.

> **Reformulación.** Si «isla» debe significar algo, que signifique la
> **región ε-Pareto**: el conjunto de configuraciones cuyo resultado no es
> peor que el de la frontera más que una tolerancia ε. Es una *banda* alrededor
> de la frontera, y su anchura la fija la resolución del instrumento, no el
> programa. Se desarrolla en §4.

## 2. Geometría de la frontera: el intercambio no es uniforme

### 2.1 La tasa marginal cambia de orden de magnitud

Sobre la frontera medida (`resultados/estandar`):

| Segmento | ΔS (B) | ΔT (ms) | tasa marginal (ms por KB) |
|---|---:|---:|---:|
| `-Oz` → `-Os` | 512 | −14,24 | **28,5** |
| `-Os` → `-O2` | 1 536 | −0,82 | 0,55 |

En corridas donde la frontera incluye el tramo con metadatos, la tasa baja
hasta **0,013 ms/KB**: la razón entre el tramo más caro y el más barato llega
a **1819×**. La cifra concreta depende de qué puntos caen en la frontera — y
eso mismo es un hallazgo (§2.3).

**El «intercambio» no es uniforme.** Hay tramos donde el tamaño es casi gratis
y tramos donde cuesta orders of magnitud más. Esto invalida el modelo mental
de «hay un punto óptimo que se busca con una búsqueda local»: no hay un
óptimo, hay una curva con pendientes muy distintas en tramos distintos.

Interpretación de los dos regímenes:

- **Tramo caro** (`-Oz` → `-Os`, ~28 ms/KB): el optimizador ha desactivado
  desenrollado, inlining y vectorización. Comprar 512 B cuesta 14 ms.
- **Tramo barato** (`-Os` → `-O2`+debug, ~0,01 ms/KB): 3,5 KB de metadatos no
  cuestan prácticamente nada en tiempo.

Consecuencia práctica: **el «compromiso» no es una constante del problema**,
depende del tramo. Una pregunta operativa («¿cuál es el punto que maximiza
X?») sólo tiene respuesta después de decir *en qué tramo* se busca.

### 2.2 Por qué el eje de tamaño no puede ser uno solo

La correlación entre tamaño y tiempo depende **de qué métrica de tamaño se
use**, y no poco:

| Métrica | r(S, T) sobre el conjunto medido |
|---|---:|
| S = tamaño total del `.exe` | **+0,09** |
| S = código en la imagen (`text+data` del PE) | +0,11 |
| S = código propio (`text+data` de los `.obj`) | **+0,45** |

Elegir la métrica cambia la correlación observada **5×**. La razón es
estructural: el tamaño total mezcla dos cosas de naturaleza distinta —código
que se ejecuta y metadatos que no— y la segunda no correlaciona con el
tiempo.

> **Principio de descomposición de ejes.** Un eje de medida que agrupa
> magnitudes de naturaleza distinta destruye la señal: aquí, agrupar «código» y
> «metadatos» en «bytes» ocultó la correlación que explica el comportamiento
> del binario.

Es el mismo error, en otro nivel, que el del CRT estático (§5.2).

### 2.3 La frontera es una distribución, no un conjunto

**Éste es el resultado más fuerte del banco.** La frontera de Pareto se
calcula sobre *estimaciones* (la mediana de N corridas). Si el ruido es
comparable a las diferencias entre variantes — y lo es (§3) —, entonces
**la composición de la frontera es en sí misma una afirmación estadística**: una
variante puede aparecer o desaparecer de la frontera según la realización del
ruido.

Se cuantifica con bootstrap (`bench/pareto.py: estabilidad_frontera`): se
remuestrea cada variante con reemplazo de sus corridas medidas, se recalcula
la mediana, se recalcula la frontera, y se cuenta cuántas veces aparece cada
variante (500 remuestreos).

Resultado sobre 13 variantes medidas:

| Artefacto | Frecuencia en la frontera | Clasificación |
|---|---:|---|
| `Os__sin__lto_thin__sin_info` | **100,0 %** | estable |
| `O2__sin__defecto__sin_info` | 88,0 % | marginal |
| `Oz__sin__defecto__sin_info` | 81,8 % | marginal |
| `Oz__con__lto_thin__sin_info` | 18,2 % | marginal |
| resto (9 variantes) | 0–8 % | nunca |

**De 13 variantes medidas, sólo UNA está en la frontera de forma estable.**
Las dos restantes que la frontera puntual declara no dominadas aparecen en
sólo el 82–88 % de los remuestreos: su pertenencia la decide el ruido.

> **Consecuencia.** «La frente de Pareto contiene 3 puntos» es una afirmación
> sin barra de error, y es falsa en el 12–18 % de las realizaciones. La
> formulación correcta no es *«cuáles son los puntos de la frontera»* sino
> *«cuáles la pertenecen con frecuencia alta»*.
>
> La frontera de un experimento ruidoso **debe publicarse como una
> distribución sobre conjuntos de puntos**, no como un conjunto. Sólo sus
> vértices de alta frecuencia son hallazgos.

Esto explica también la aparente inconsistencia entre corridas del §2.1: la
razón entre la tasa marginal máxima y mínima (1819× en una corrida, 76× en
otra) no es ruido de las cifras: es que **distintos puntos entran y salen de
la frontera**.

## 3. H-B: el suelo de medición es proporcional, no aditivo

### 3.1 La hipótesis y su refutación

Hipótesis original (implícita en la intuición de «haz el trabajo más largo
para medir mejor»): el ruido de medición es **aditivo** —una perturbación
absoluta del sistema—, luego

```
CV(T) ≈ k / T
```

**Medición** (`bench/experimentos.py escala`, 60 repeticiones por punto,
mismo binario, sólo cambia la escala de trabajo):

| escala | mediana (ms) | CV | resolución (ancho IC95, %) |
|---:|---:|---:|---:|
| 1 | 12,3 | 0,049 | 2,92 |
| 2 | 24,2 | 0,053 | 1,47 |
| 4 | 49,5 | 0,043 | 1,96 |
| 8 | 97,5 | 0,031 | 1,55 |
| 16 | 225,3 | 0,070 | 2,39 |
| 32 | 479,3 | 0,058 | 2,86 |

**Test decisivo.** Si el ruido fuera aditivo, al pasar de 12,3 ms a 479,3 ms
(39×) el CV caería a 0,112 %. **Medido: 5,8 % — 52× más alto de lo que
predice el modelo.** Hipótesis **refutada**.

El modelo que sí se sostiene es el opuesto:

```
CV(T) ≈ constante    (ruido proporcional)
```

### 3.2 El modelo de resolución, validado

Si el CV es invariante con la escala, la resolución depende sólo del número
de repeticiones. Para la mediana de una muestra normal, el error estándar
asintótico es `1,253·σ/√n`, luego el ancho del IC al 95 % es

```
ancho_IC95(mediana) ≈ 4,91 · CV / √n
```

Contraste con los datos: razón observada/predicha = **0,74** (el modelo es
conservador, que es la dirección correcta para un diseño de medición).

### 3.3 La regla de diseño que se deriva

Para que dos variantes sean separables (IC95 sin solape) hace falta que el
semiancho sea ≤ δ/2:

```
n(δ) ≈ (4,91 · CV / δ)²
```

Con el CV observado (~0,05):

| Diferencia a resolver δ | Corridas por variante | Coste con 18 variantes |
|---|---:|---:|
| 2 % | ~65 | ~20 min |
| 1 % | ~650 | ~3,9 h |
| 0,5 % | ~2 600 | ~15,6 h |

**Ésta es la conclusión accionable de H-B:** *alargar el programa no abarata
la medición; sólo lo hace `n`.* Y como el CV es proporcionalmente estable,
ese coste no se puede eludir haciendo el trabajo más pesado: es un coste
fijo en tiempo de máquina por resolución.

> **Por qué el ruido es proporcional.** Si la perturbación fuese un coste
> fijo (arranque, paginación), el efecto sería aditivo. Que sea proporcional
> sugiere que la fuente dominante no es un coste sino un **estado fluctuante
> que afecta a una fracción del trabajo**: frecuencia de CPU, estado de caché
> y TLB, preempción del planificador, o posición del código en la caché de
> instrucciones. Es una hipótesis con mecanismo, refutable, y que este banco
> **no** ha separado todavía (véase §7).

## 4. La «isla-ε» y por qué su área la fija el instrumento

Formalicemos lo que sí existe. Sea `X` el espacio de configuraciones, y
`f(x) = (S(x), T(x))` el vector de objetivos, con `V(x)` la variabilidad.

- **Región factible**: `F = {x ∈ X : V(x) ≤ V_max ∧ correcto(x)}`.
- **Frente de Pareto**: `P = {x ∈ F : ∄ y ∈ F con f(y) ≤ f(x) y f(y) ≠ f(x)}`.
- **Región ε-Pareto** (la «isla», si el término debe significar algo):

```
P_ε = { x ∈ F : ∃ y ∈ P,  S(y) − S(x) ≤ ε_S  ∧  T(y) − T(x) ≤ ε_T }
```

`P_ε` es una **banda** alrededor de `P`. Su anchura en la dirección del tiempo
está determinada por la resolución del instrumento:

```
ε_T ≈ resolución ≈ 4,91 · CV / √n
```

**Corolario.** El «tamaño» de la isla no es una propiedad del programa: es una
propiedad del **instrumento y del presupuesto de medición**. Con 40
repeticiones, la banda temporal es de ~3 %; con 650, de ~0,5 %. La frontera
no cambia; lo que cambia es cuántas de sus distinciones son resolubles.

Esto tiene una consecuencia sobre el uso del término: decir «existe una isla
de estabilidad» sin decir «con qué resolución y qué presupuesto» es un
enunciado vacuo.

## 5. H-C: un nulo puede ser falso, y aquí lo fue

### 5.1 El caso

La primera versión del banco mendía la conclusión: *«ICF y `--gc-sections` no
ahorran nada en PE/COFF»*. Las 48 comparaciones del perfil completo lo
respaldaban. Era **falso**, y por dos capas independientes:

**Capa 1 — la bandera no existe en ese enlazador.** `--icf=all` y
`--gc-sections` son sintaxis de **lld-ELF**. `lld-link` (el enlazador de
Windows) las **ignora con un warning** y continúa. El warning estaba en la
salida del enlazador; el protocolo no lo leía.

**Capa 2 — la palanca real no es ICF.** Con la sintaxis correcta
(`/OPT:ICF`, `/OPT:REF`) el plegado sigue sin ocurrir… hasta que se mide el
**mecanismo**, no el tamaño.

### 5.2 El mecanismo, medido directamente

Las tres funciones `aux_cala1/2/3` del SUT son byte-idénticas (3
instrucciones: `leal (%rcx,%rcx,2),%eax; incl %eax; retq`). Contando
**copias de la función** en el `.text` del ejecutable:

| enlazador | COMDAT (`-ffunction-sections`) | flag ICF | copias | plegado |
|---|---|---|---:|---|
| lld-link | no | — | 3 | no |
| lld-link | no | `/OPT:ICF` | 3 | **no** |
| lld-link | **sí** | — | **1** | **sí** |
| lld-link | sí | `/OPT:ICF` | 1 | sí |
| link.exe | no | `/OPT:ICF` | 3 | **no** |
| link.exe | **sí** | — | **1** | **sí** |
| link.exe | sí | `/OPT:ICF` | 1 | sí |

**El plegado lo produce la semántica de selección COMDAT del formato PE**,
que deduplica secciones COMDAT idénticas por su cuenta. `-ffunction-sections`
es lo que hace que clang emita cada función en su propia sección COMDAT. **No
hace falta ninguna opción de ICF.** Y `/OPT:ICF` no añade nada: el trabajo ya
lo había hecho el formato.

Comprobación adicional: `aux_no_usada` (nunca referenciada) **no aparece** en
el binario base, sin ninguna bandera de GC → **lld-link hace recolección de
secciones muertas por defecto** (`/OPT:REF` implícito), que es por lo que
`--gc-sections` (inválido) no cambiaba nada.

### 5.3 La lección generalizable

Un resultado nulo en un experimento de optimización tiene **tres**
explicaciones, y la tercera es indistinguible de la primera si no se leen los
avisos del toolchain:

| # | Explicación | Cómo se descarta |
|---|---|---|
| 1 | La palanca no existe en esta plataforma | Comparar con otra plataforma |
| 2 | La palanca existe pero no aplica a este caso | Probar un caso donde sí aplique |
| 3 | **La palanca no se aplicó** (bandera inválida, ignorada) | **Leer los warnings** |

> **Control añadido al protocolo:** `bench/construir.py` analiza la salida del
> enlazador y **descarta la variante** si aparece un aviso del tipo «ignoring
> unknown argument». Una variante descartada no entra en la frontera, de modo
> que un nulo falso no puede volver a colarse.

**Corolario general.** En cualquier benchmark que mida el efecto de una
herramienta, el primer control no es «¿cuánto ahorra?» sino «**¿se aplicó?**».
Un ahorro de 0 bytes es indistinguible de un ahorro que no se midió.

## 6. El principio del fondo fijo (offset)

Repetido por tres ejes distintos, merece enunciarse aparte:

> Si la magnitud medida es `S = F + Δ`, donde `F` es un término fijo
> independiente de lo que se optimiza, el **efecto relativo** que se observa
> sobre `S` es `Δ/(F+Δ)`, no `Δ`. Elegir la escala de medida equivocada
> **comprime** el efecto hasta hacerlo invisible.

Manifestaciones medidas en este banco:

| Fondo fijo `F` | Elegir mal la escala | Efecto real | Efecto observado |
|---|---|---|---|
| CRT estático (~145 KB) | medir el `.exe` con `libcmt` | −48,5 % de código | **−1 %** de archivo |
| cabecera PE + imports + arranque | medir el `.exe` | 3 781 B de código propio | 12 800 B de archivo |
| metadatos del PDB | medir el `.exe` | ~470 KB de PDB | 3,5 KB en el `.exe` |

El control es siempre el mismo: **medir el término variable**, o **restar el
fondo**, o **cambiar la escala de medida** para que el fondo sea
despreciable.

## 7. Lo que queda abierto (y cómo cerrarlo)

| Pregunta | Estado | Experimento que la cerraría |
|---|---|---|
| ¿Cuál es la fuente dominante del ruido proporcional? | Hipótesis: estado fluctuante (frecuencia, caché/TLB, preempción) | Fijar frecuencia de CPU, medir con y sin preempción, comparar CV |
| ¿Existe un suelo de entropía (H2 del protocolo)? | No medido: falta la noción de «capacidad útil» | Definir capacidad y trazar capacidad-vs-S; el codo de esa curva es el suelo |
| ¿El ruido es el mismo en otro hardware? | No medido | Repetir en un servidor sin carga de escritorio; comparar CV |
| ¿La frontera es la misma en ELF? | No medido | Repetir en Linux; las palancas de formato difieren (aquí: COMDAT, allí: `--strip`, ICF, `--gc-sections` reales) |
| ¿La correlación S–T es universal? | No: depende de la métrica (§2.1) | Replicar con carga de trabajo dominada por E/S |
| ¿Las conclusiones de tamaño se generalizan a otro programa? | No: un solo SUT | Repetir con un segundo SUT de perfil distinto |

## 8. Resumen de la teoría

1. Lo que existe no es una «isla» sino una **franja de Pareto** con
   pendientes no uniformes (el intercambio cambia de orden de magnitud a lo
   largo de la misma frontera). Buscar «el punto óptimo» es ill-posed; la
   pregunta correcta es *en qué tramo*.
2. **La frontera no es un conjunto, es una distribución sobre conjuntos.**
   De 13 variantes medidas, sólo **una** pertenece a la frontera de forma
   estable (frecuencia bootstrap ≥ 90 %); dos más son marginales y nueve nunca
   aparecen. La formulación publicable no es «cuáles son los puntos de la
   frontera» sino «cuáles la pertenecen con frecuencia alta».
3. La «isla» sólo tiene sentido como **región ε-Pareto**, y su anchura la
   fija la resolución del instrumento, no el programa.
4. La resolución se cuantifica: `ancho_IC95 ≈ 4,91·CV/√n`, con `CV` casi
   invariante con la carga de trabajo (hipótesis «CV ~ k/T» **refutada** por
   un factor 52). **Sólo `n` abarata la medición**: resolver un 1 % exige
   ~650 corridas por variante; alargar el programa no sirve de nada.
5. Un nulo de optimización tiene tres explicaciones, y la más probable en la
   práctica es que **la palanca no se aplicó**. El control barato para
   descartarla es leer los warnings del toolchain.
6. Toda magnitud medida tiene un fondo fijo; medir el término equivocado
   puede comprimir el efecto hasta volverlo invisible (aquí: 48,5 % → 1 %).

**Lo que esto deja de la idea original.** «Isla de estabilidad» es una metáfora
tomada de los paisajes de aptitud, donde describe cuencas locales aisladas.
El problema de tamaño/tiempo no es de ese tipo: es de eficiencia multiobjetivo
sobre un espacio casi conexo. Lo que sí existe, y lo que este banco mide, es
una **franja con estructura y con bordes borrosos** — y medir cuánto de borroso
es parte del resultado.
