# Bibliografía — Isla de estabilidad

Citas verificadas por fuente primaria (Crossref, arXiv, sumarios oficiales de ACM/IEEE/USENIX,
páginas oficiales de proyecto). Las que no pudieron verificarse están en la última sección,
claramente marcadas: NO deben citarse como si fueran verificadas.

Nota de método: la verificación se hizo con la API de Crossref, la de arXiv, los sumarios
públicos de ACM (conference-publishing.com), páginas oficiales (clang.llvm.org, gcc.gnu.org,
llvm.org, sourceware.org, reproducible-builds.org, attack.mitre.org, diffoscope.org) y fichas
de repositorios institucionales. DBLP, dl.acm.org y Semantic Scholar estuvieron bloqueados
(Anubis, CAPTCHA y HTTP 429 respectivamente).

---

## AREA 1 — Compilación optimizada para tamaño / tamaño como objetivo

**[PAYJIT]** Brock, J.; Ding, C.; Xu, X.; Zhang, Y. "PAYJIT: space-optimal JIT compilation and its practical implementation." Proceedings of the 27th ACM SIGPLAN Conference on Compiler Construction (CC '18), pp. 71-81, 2018.
- DOI/arXiv/URL: https://doi.org/10.1145/3178372.3179523
- Qué aporta: Demuestra que el espacio (tamaño del código JIT en memoria) puede tratarse como objetivo de optimización explícito y no como efecto secundario; introduce un compilador JIT que optimiza el layout del código generado en caliente. Es el referente académico más cercano a "tamaño como objetivo de primera clase" en la literatura de compiladores.

**[GCC-OS]** GCC Project. "Optimize Options (-Os, -Oz)." GCC Online Documentation.
- DOI/arXiv/URL: https://gcc.gnu.org/onlinedocs/gcc/Optimize-Options.html
- Qué aporta: Documentación normativa de referencia que define `-Os` ("enables all -O2 optimizations except those that often increase code size") y `-Oz` ("behaves similarly to -Os including enabling most -O2 optimizations"), con la lista exacta de passes deshabilitados por tamaño. Permite citar el comportamiento oficial de la toolchain sin recurrir a fuentes secundarias.

**[CLANG-CMDLINE]** LLVM Project. "Clang command line argument reference." Clang Documentation.
- DOI/arXiv/URL: https://clang.llvm.org/docs/ClangCommandLineReference.html
- Qué aporta: Referencia oficial de las opciones del driver de Clang, donde se documentan los niveles de optimización `-O0/-O1/-O2/-O3/-Os/-Oz`. Es la fuente primaria para argumentar qué objetivos de tamaño ofrece el compilador de LLVM.

**[LLVM-OPTOPZ-PATCH]** Carruth, C. "[PATCH] optsize attribute on top of -Oz gives bigger code." llvm-commits mailing list, LLVM Project, 11 mayo 2012.
- DOI/arXiv/URL: https://lists.llvm.org/pipermail/llvm-commits/Week-of-Mon-20120507/142709.html
- Qué aporta: Documenta la incorporación de `-Os`/`-Oz` al driver de `opt` de LLVM y el atributo IR `optsize`, con la discusión de por qué el umbral de inlining en modo minsize debe ser 0. Es la evidencia primaria de que LLVM soporta "minsize" como pipeline de optimización diferenciada desde hace más de una década.

**[LLVM-BUGPOINT-OZ]** Hahn, F. "[bugpoint] Add support for -Oz and properly enable -Os." LLVM commit r372079, llvm-commits mailing list, 17 sept. 2016 (mergeado 2019).
- DOI/arXiv/URL: https://lists.llvm.org/pipermail/llvm-commits/Week-of-Mon-20190916/694818.html
- Qué aporta: Añade `-Oz`/`-Os` como opciones explícitas de `bugpoint`, con un pipeline distinto del de `opt`. Útil para argumentar que el soporte de "optimizar para tamaño" se ha propagado a las herramientas de reducción de programas, no sólo al driver principal.

**[CLANG11-RN]** LLVM Project. "Clang 11 release notes." clang/docs/ReleaseNotes.rst (tag `llvmorg-11.0.0`).
- DOI/arXiv/URL: https://raw.githubusercontent.com/llvm/llvm-project/llvmorg-11.0.0/clang/docs/ReleaseNotes.rst
- Qué aporta: Las notas de Clang 11 documentan explícitamente que "In a -flto={full,thin} link, -Os, -Oz and -Og can be used now. -Os and -Oz map to the -O2 pipe line". Es la fuente primaria que ancla (con fecha) la disponibilidad de `-Oz` en Clang.

**[ICF-SSA]** Rocha, R.C.O.; Petoumenos, P.; Wang, Z.; Cole, M.; Leather, H. "Effective function merging in the SSA form." Proceedings of the 41st ACM SIGPLAN Conference on Programming Language Design and Implementation (PLDI '20), pp. 854-868, 2020.
- DOI/arXiv/URL: https://doi.org/10.1145/3385412.3386030
- Qué aporta: Presenta un algoritmo de function merging (ICF) que fusiona funciones equivalentes tras optimizaciones, opera sobre la forma SSA y reduce el tamaño del código sin cambiar la semántica. Es el trabajo académico de referencia para la dimensión "plegado de código idéntico".

---

## AREA 2 — Optimización multiobjetivo / Pareto de rendimiento (compiler y software)

**[ANSOR]** Zheng, L.; Jia, C.; Sun, M.; Wu, Z.; Yu, C.H.; Haj-Ali, A.; Wang, Y.; Yang, J.; Zhuo, D.; Sen, K.; Gonzalez, J.E.; Stoica, I. "Ansor: Generating High-Performance Tensor Programs for Deep Learning." USENIX OSDI, 2020.
- DOI/arXiv/URL: https://arxiv.org/abs/2006.06762
- Qué aporta: Introduce la búsqueda en el espacio de plantillas (schedule space) con un modelo de coste aprendido, base del autotuner de TVM y del concepto de "métricas" que luego se extiende a objetivos múltiples (latencia, tamaño del modelo). Es la referencia canónica para "tuning de compiladores de DL con objetivos múltiples".

**[TVM]** Chen, T.; Moreau, T.; Jiang, Z.; Zheng, L.; Yan, E.; Cowan, M.; Shen, H.; Wang, L.; Hu, Y.; Ceze, L.; Guestrin, C.; Krishnamurthy, A. "TVM: An Automated End-to-End Optimizing Compiler for Deep Learning." USENIX OSDI, 2018.
- DOI/arXiv/URL: https://arxiv.org/abs/1802.04799
- Qué aporta: Define una pila de compilación para DL con capas de schedule TuneSpace/Ansor, donde las decisiones de tiling, vectorización y layout se optimizan automáticamente con métricas multiobjetivo. Sirve como marco de referencia para caracterizar la frontera de Pareto (latencia, tamaño del modelo) en compiladores de DL.

**[BOHB]** Falkner, S.; Klein, A.; Hutter, F. "BOHB: Robust and Efficient Hyperparameter Optimization at Scale." ICML, 2018.
- DOI/arXiv/URL: https://arxiv.org/abs/1807.01774
- Qué aporta: Propone un esquema tipo Hyperband para búsqueda de hiperparámetros que escala a decenas de máquinas, combinando Bayesian optimization con modelos de coste surrogates. Es la base de la infraestructura de tuning usada por TVM/Ansor y de los auto-tuners multiobjetivo modernos.

**[HYPERBAND]** Li, L.; Jamieson, K.; DeSalvo, G.; Rostamizadeh, A.; Talwalkar, A. "Hyperband: A Novel Bandit-Based Approach to Hyperparameter Optimization." Journal of Machine Learning Research 18(185):1-52, 2018.
- DOI/arXiv/URL: https://arxiv.org/abs/1603.06560
- Qué aporta: Define la promoción agresiva de configuraciones (early stopping con recursos crecientes) como forma barata de explorar el frente de Pareto entre rendimiento y coste de búsqueda. Fundamenta formalmente la tensión exploration/exploitation que aparece en cualquier protocolo de cribado por fases.

**[BAYES-OPT]** Snoek, J.; Larochelle, H.; Adams, R.P. "Practical Bayesian Optimization of Machine Learning Algorithms." NIPS, 2012.
- DOI/arXiv/URL: https://arxiv.org/abs/1206.2944
- Qué aporta: Da la formulación práctica de Bayesian optimization con Gaussian processes y Expected Improvement que usan casi todos los auto-tuners posteriores (incluido el trabajo de Turner/Laurila/Real sobre parámetros de rendimiento en SC). Permite trazar la genealogía exacta del método que el proyecto quiere replicar.

---

## AREA 3 — Empirical Software Performance Engineering (SPE) y ruido de medición

**[KALIBERA-ISMM]** Kalibera, T.; Jones, R. "Rigorous benchmarking in reasonable time." Proceedings of the 2013 International Symposium on Memory Management (ISMM '13), 2013.
- DOI/arXiv/URL: https://doi.org/10.1145/2464157.2464160
- Qué aporta: Propone una metodología estadística para comparar benchmarks que reduce el coste de la repetición manteniendo rigor (tamaño de muestra, niveles de confianza) y hace explícito el compromiso entre coste experimental y validez. Es la referencia para justificar el cribado de ruido antes de medir tamaño o rendimiento.

**[GGE-2007]** Georges, A.; Buytaert, D.; Eeckhout, L. "Statistically rigorous Java performance evaluation." ACM SIGPLAN Notices 42(10):57-76 / OOPSLA '07, 2007.
- DOI/arXiv/URL: https://doi.org/10.1145/1297105.1297033
- Qué aporta: Muestra que las metodologías de benchmarking habituales (promedios, "best of N", una sola VM) son estadísticamente engañosas y llevan a conclusiones incorrectas. Aporta el marco de referencia para el control de variabilidad y los "hidden factors" que contaminan cualquier medición de tamaño o latencia.

**[GHOST-NIST]** Vitek, W.; Kalibera, T. "The ghost in the machine: don't let it haunt your software performance measurements." NIST TN 1830, 2014.
- DOI/arXiv/URL: https://doi.org/10.6028/NIST.TN.1830
- Qué aporta: Guía metodológica del NIST sobre cómo medir y reportar rendimiento de forma reproducible y repetible, con énfasis en los factores ocultos (orden de enlazado, tamaño del entorno de proceso, nombres de símbolos aleatorios). Es la fuente normativa para el argumento "medición reproducible".

**[HOEFLER-SC15]** Hoefler, T.; Belli, R. "Scientific benchmarking of parallel computing systems: twelve ways to tell the masses when reporting performance results." SC '15, Article 73, 2015.
- DOI/arXiv/URL: https://doi.org/10.1145/2807591.2807644
- Qué aporta: Auditoría de 120 papers de tres conferences HPC que revela que la práctica de reportar no distingue entre mejoras deterministas y observadas por azar. Proporciona reglas mínimas de diseño experimental y de reporting que se pueden citar como estándar de calidad experimental.

**[MENEIDE-TC]** Meneide, R. et al. "Statistical Performance Comparisons of Computers." IEEE Transactions on Computers, 2014.
- DOI/arXiv/URL: https://doi.org/10.1109/TC.2014.2315614
- Qué aporta: Formula la comparación de rendimiento como tarea estadística y propone un framework no paramétrico de hierarchical performance testing, cuantificando el error (8,0 % a 56,3 %) de comparar promedios geométricos. Es el argumento cuantitativo para no comparar variantes por su media simple.

**[PINEAU-NEURIPS]** Pineau, J.; Vincent-Lamarre, P.; Sinha, K.; Larivière, V.; Beygelzimer, A.; d'Alché-Buc, F.; Fox, E.; Larochelle, H. "Improving Reproducibility in Machine Learning Research (A Report from the NeurIPS 2019 Reproducibility Program)." Journal of Machine Learning Research 22, 2021.
- DOI/arXiv/URL: https://arxiv.org/abs/2003.12206
- Qué aporta: Informe del programa de reproducibilidad de NeurIPS 2019 con recomendaciones concretas sobre pipelines de experimentación, semillas, determinismo y reporte de variabilidad. Es el estándar de facto de "reproducibilidad experimental" para el capítulo metodológico del proyecto.

---

## AREA 4 — Testing de correctitud de variantes generadas por el compilador

**[BARANY-CC18]** Barany, G. "Finding missed compiler optimizations by differential testing." Proceedings of the 27th ACM SIGPLAN Conference on Compiler Construction (CC '18), pp. 82-92, 2018.
- DOI/arXiv/URL: https://doi.org/10.1145/3178372.3179521
- Qué aporta: Demuestra que comparar variantes compiladas con distintos flags o versiones sobre la misma entrada permite detectar optimizaciones perdidas, no sólo bugs. Es exactamente el mecanismo de validación que el proyecto necesita para comprobar que una reducción de tamaño no altera la semántica del binario.

**[YANG-CSMITH-PLDI11]** Yang, X.; Chen, Y.; Eide, E.; Regehr, J. "Finding and understanding bugs in C compilers." Proceedings of the 32nd ACM SIGPLAN Conference on Programming Language Design and Implementation (PLDI '11), pp. 283-294, 2011.
- DOI/arXiv/URL: https://doi.org/10.1145/1993498.1993532
- Qué aporta: Presenta Csmith, generador aleatorio de programas C que evita comportamiento indefinido y usa differential testing entre compiladores; reporta más de 325 bugs desconocidos en GCC, LLVM y compiladores comerciales. Es el trabajo canónico de differential testing aplicado a compiladores.

**[CHEN-MT-1998]** Chen, T.Y.; Cheung, S.C.; Yiu, S.M. "Metamorphic testing: A new approach for generating next test cases." Technical Report HKUST-CS98-01, Department of Computer Science, Hong Kong University of Science and Technology, 1998.
- DOI/arXiv/URL: https://arxiv.org/abs/2002.12543
- Qué aporta: Trabajo fundacional que introduce las metamorphic relations como alternativa al oráculo: a partir de un test válido se genera otro cuya relación de salida con el primero es conocida. Permite construir un oráculo para verificar equivalencia funcional de variantes de compilación sin conocer la salida esperada.

**[CSUR-MT]** Chen, T.Y.; Kuo, F.-C.; Liu, H.; Poon, P.-L.; Towey, D.; Tse, T.H.; Zhou, Z.Q. "Metamorphic Testing: A Review of Challenges and Opportunities." ACM Computing Surveys 51(1), Article 4, pp. 4:1-4:27, 2018.
- DOI/arXiv/URL: https://doi.org/10.1145/3143561
- Qué aporta: Revisión de referencia que delimita el estado del arte, clarifica conceptos mal entendidos y enumera desafíos abiertos y oportunidades. Sirve para posicionar formalmente la contribución del proyecto dentro del estado del arte.

**[SEGURA-MT-SURVEY]** Segura, S.; Fraser, G.; Sánchez, A.B.; Ruiz-Cortés, A. "A Survey on Metamorphic Testing." IEEE Transactions on Software Engineering 42(9):805-824, 2016.
- DOI/arXiv/URL: https://doi.org/10.1109/TSE.2016.2532875
- Qué aporta: Revisión sistemática de 119 papers de metamorphic testing publicados entre 1998 y 2015, con taxonomía y preguntas abiertas; útil como marco para justificar por qué MT es el mecanismo adecuado para validar equivalencia entre binarios de distinto tamaño.

**[EMI]** Le, V.; Afshari, M.; Su, Z. "Compiler validation via equivalence modulo inputs." Proceedings of the 35th ACM SIGPLAN Conference on Programming Language Design and Implementation (PLDI '14), pp. 216-226, 2014.
- DOI/arXiv/URL: https://doi.org/10.1145/2594291.2594334
- Qué aporta: Define el testing de compiladores por equivalencia módulo entradas: dos compiladores se consideran correctos si para toda entrada observable producen el mismo resultado, lo que relaja el requisito de semántica exacta. Base conceptual para validar que variantes optimizadas para tamaño son funcionalmente equivalentes.

**[BOHME-FUZZ-SURVEY]** Böhme, M. et al. "The Art, Science, and Engineering of Fuzzing: A Survey." IEEE Transactions on Software Engineering 47(11):2312-2331, 2021.
- DOI/arXiv/URL: https://ieeexplore.ieee.org/document/8863940
- Qué aporta: Taxonomía unificada de la literatura de fuzzing (modelo, mutadores, oráculos, corpus) que sirve de marco para encuadrar cualquier técnica de reducción de corpus y de búsqueda de fallos como caso particular.

**[MA-COMPILER-FUZZ]** Ma, H. "A Survey of Modern Compiler Fuzzing." arXiv:2306.06884, 2023.
- DOI/arXiv/URL: https://arxiv.org/abs/2306.06884
- Qué aporta: Revisión de las técnicas de fuzzing de compiladores (construcción de programas de test y diseño de oráculos) y de los estudios de bugs en GCC/LLVM, JVM y compiladores de DL. Permite argumentar que la literatura no ha explorado el fuzzing de configuraciones de optimización como superficie de fallo.

**[MARCOZZI-OOPSLA19]** Marcozzi, M.; Tang, Q.; Donaldson, A.F.; Cadar, C. "Compiler Fuzzing: How Much Does It Matter?" Proceedings of the ACM on Programming Languages 3(OOPSLA), Article 155, 29 pp., 2019.
- DOI/arXiv/URL: https://doi.org/10.1145/3360581
- Qué aporta: Primer estudio cuantitativo del impacto real de los bugs de compilación en aplicaciones reales (309 paquetes Debian, más de 10 M LOC), mostrando que casi la mitad de los bugs encontrados por fuzzers se propagan al binario. Es la evidencia empírica que permite argumentar que "compilar distinto no es inocuo" y que toda variante de tamaño debe validarse.

---

## AREA 5 — Search-Based Software Engineering (SBSE) y protocolo de cribado/experimentación en dos fases

**[HARMAN-FOSE07]** Harman, M. "The Current State and Future of Search Based Software Engineering." Future of Software Engineering (FOSE '07), pp. 342-357, 2007.
- DOI/arXiv/URL: https://doi.org/10.1109/FOSE.2007.29
- Qué aporta: Estado del arte del campo SBSE: taxonomía de aplicaciones (generación de tests, minimización, reparación, priorización), marco de problemas de optimización y agenda de investigación. Es el survey canónico que legitima el encuadre "la reducción de tamaño es un problema de optimización combinatoria".

**[HARMAN-JONES-2001]** Harman, M.; Jones, B.F. "Search-based software engineering." Information and Software Technology 43(14):833-839, 2001.
- DOI/arXiv/URL: https://www.sciencedirect.com/science/article/pii/S0950584901000839 — DOI pendiente de confirmar en fuente primaria (verificado vía listas de referencias publicadas; el DOI exacto no pudo confirmarse)
- Qué aporta: Artículo fundacional que crea el campo SBSE al identificar las tareas de ingeniería de software como problemas de optimización con espacios de búsqueda exponenciales, y que enuncia la separación entre búsqueda sobre el espacio de soluciones y búsqueda sobre el espacio de programas.

**[GENPROG-TSE12]** Le Goues, C.; Nguyen, T.; Forrest, S.; Weimer, W. "GenProg: A Generic Method for Automatic Software Repair." IEEE Transactions on Software Engineering 38(1):54-72, 2012.
- DOI/arXiv/URL: https://doi.org/10.1109/TSE.2011.104
- Qué aporta: Reparación automática basada en programación genética que evoluciona variantes de un programa que pasan los tests existentes, y que explícitamente usa delta debugging para reducir el parche a un conjunto 1-minimal de cambios. Es el referente de búsqueda sobre el espacio de programas con reducción iterativa del candidato, exactamente el patrón "cribar y luego refinar" del proyecto.

**[GENPROG-ICSE12]** Le Goues, C.; Dewey-Vogt, M.; Forrest, S.; Weimer, W. "A Systematic Study of Automated Program Repair: Fixing 55 out of 105 Bugs for $8 Each." Proceedings of the 34th International Conference on Software Engineering (ICSE '12), pp. 3-13, 2012.
- DOI/arXiv/URL: https://doi.org/10.5555/2337223.2337225
- Qué aporta: Evaluación a escala de GenProg (105 defectos, 5,1 M LOC, 10 193 tests) que cuantifica coste y éxito de la reparación automática y define el benchmark ManyBugs. Aporta la metodología de evaluación con coste medido que el proyecto debe replicar para su propio cribado.

> Nota: para el sub-paso de "minimización de corpus / función de merging" dentro del protocolo SBSE, véase **[ICF-SSA]** en el AREA 1 (Rocha et al., PLDI '20).

---

## AREA 6 — Reproducible builds y medición determinista

**[RB-SUPPLYCHAIN]** Lamb, C.; Zacchiroli, S. "Reproducible Builds: Increasing the Integrity of Software Supply Chains." IEEE Software 39(2):62-70, 2022.
- DOI/arXiv/URL: https://doi.org/10.1109/MS.2021.3073045 — preprint: https://arxiv.org/abs/2104.06020
- Qué aporta: Definición formal del problema de reproducibilidad y análisis de las causas reales de irreproducibilidad en proyectos reales (Debian), con vínculos explícitos con quality assurance y flakiness. Es el artículo académico de referencia del movimiento y el sustituto más cercano al "manifiesto" que no se pudo confirmar.

**[RB-PROJECT]** Reproducible Builds project. "Reproducible Builds — a set of software development practices that create an independently-verifiable path from source to binary code."
- DOI/arXiv/URL: https://reproducible-builds.org/
- Qué aporta: Sitio institucional del proyecto: definición operativa (mismo código fuente + entorno + instrucciones implica artefactos bit a bit idénticos) y catálogo de guías, herramientas y casos de éxito. Es la fuente primaria del movimiento y el lugar natural para citar la definición formal y los commandements.

**[RB-COMMANDMENTS]** Reproducible Builds project. "Commandments of reproducible builds."
- DOI/arXiv/URL: https://reproducible-builds.org/docs/commandments/
- Qué aporta: Lista normativa de prohibiciones (no registrar nombre del maker, fecha, orden de directorios, números aleatorios, PGO no determinista, etc.) con la regla explícita de que la PGO puede "amplificar cualquier pecado (no-determinismo)". Es la fuente más directa para el argumento de que el autotuning determinista es un requisito de reproducibilidad.

**[RB-PUBLICATIONS]** Reproducible Builds project. "Academic publications."
- DOI/arXiv/URL: https://reproducible-builds.org/docs/publications/
- Qué aporta: Bibliografía curada del proyecto con enlaces DOI a los trabajos académicos sobre builds reproducibles (in-toto, Guix, double-compiling de Wheeler, etc.). Permite contextualizar la contribución dentro de la literatura de integridad de cadena de suministro.

**[LD-OPTIONS]** GNU Binutils. "ld Options — --build-id, --gc-sections."
- DOI/arXiv/URL: https://sourceware.org/binutils/docs/ld/Options.html
- Qué aporta: Documentación oficial del linker que define `--build-id=sha1` (hash de 160 bits del contenido normativo de la salida) y `--gc-sections` (recolección de secciones no referenciadas). Es la base documentada de las dos palancas de determinismo y de recorte de tamaño a nivel de enlace.

**[GCC-PREFIXMAP]** GCC Project. "Debugging Options — -fdebug-prefix-map, -ffile-prefix-map."
- DOI/arXiv/URL: https://gcc.gnu.org/onlinedocs/gcc/Debugging-Options.html
- Qué aporta: Documenta las opciones que eliminan del binario las rutas absolutas del directorio de compilación, condición necesaria (no suficiente) para builds bit-a-bit idénticos entre máquinas. Referencia normativa para la sección de determinismo del proyecto.

**[DIFFOSCOPE]** Reproducible Builds project. "diffoscope: in-depth comparison of files, archives, and directories."
- DOI/arXiv/URL: https://diffoscope.org/
- Qué aporta: Herramienta de referencia que desempaqueta y descompone formatos binarios arbitrarios para explicar por qué dos artefactos difieren byte a byte. Es la herramienta que el protocolo de medición determinista necesita para auditar cualquier divergencia de tamaño o de contenido.

---

## AREA 7 — Optimización post-link / tamaño y layout a nivel de binario (dimensión C)

**[BOLT-CGO19]** Panchenko, M.; Auler, R.; Nell, B.; Ottoni, G. "BOLT: A Practical Binary Optimizer for Data Centers and Beyond." 2019 IEEE/ACM International Symposium on Code Generation and Optimization (CGO '19), pp. 2-14, 2019.
- DOI/arXiv/URL: https://doi.org/10.1109/CGO.2019.8661201 — preprint: https://arxiv.org/abs/1807.06735
- Qué aporta: Presenta BOLT, optimizador post-link construido sobre LLVM que reordena bloques y funciones usando perfiles muestreados, y demuestra que las mejoras post-link son complementarias al PGO y a LTO (hasta 7 % en cargas de datacenter y 20,4 % sobre compiladores). Es el punto de referencia para la optimización de layout a nivel de binario.

**[LIGHTNING-BOLT]** Panchenko, M.; Auler, R.; Sakka, L.; Ottoni, G. "Lightning BOLT: Powerful, Fast, and Scalable Binary Optimization." Proceedings of the 30th ACM SIGPLAN International Conference on Compiler Construction (CC '21), 2021.
- DOI/arXiv/URL: https://doi.org/10.1145/3446804.3446843
- Qué aporta: Describe la reingeniería de BOLT que reduce drásticamente su tiempo de proceso (4,71x en media) y su consumo de memoria (70,5 %) con un mecanismo ajustable de coste/beneficio. Es la referencia para discutir el eje "beneficio (tamaño o rendimiento) frente a coste de la búsqueda" en la dimensión post-link.

**[PROPELLER]** Shen, H.; Pszeniczny, K.; Lavaee, R.; Kumar, S.; Tallam, S.; Li, X.D. "Propeller: A Profile Guided, Relinking Optimizer for Warehouse-Scale Applications." ASPLOS '23: Proceedings of the 28th ACM International Conference on Architectural Support for Programming Languages and Operating Systems, Volume 2, 2023.
- DOI/arXiv/URL: https://doi.org/10.1145/3575693.3575729
- Qué aporta: Optimizador post-link de Google que rehace el layout mediante relinking con perfiles, y su evaluación a escala de warehouse. Es el estado del arte en optimización de layout post-link y el contrapunto directo a BOLT; fue distinguido con el Distinguished Paper Award en ASPLOS 2023.

**[OTTONI-MAHER]** Ottoni, G.; Maher, B. "Optimizing function placement for large-scale data-center applications." 2017 IEEE/ACM International Symposium on Code Generation and Optimization (CGO '17), pp. 233-244, 2017.
- DOI/arXiv/URL: https://doi.org/10.1109/CGO.2017.7863743
- Qué aporta: Demuestra que la colocación de funciones guiada por perfiles (no sólo el reordenamiento de bloques dentro de la función) produce mejoras sustanciales en localidad de código. Es el trabajo previo del mismo grupo que da origen a BOLT.

**[VESPA]** Moreira, A.A.; Ottoni, G.; Pereira, F.M.Q. "VESPA: static profiling for binary optimization." Proceedings of the ACM on Programming Languages 5(OOPSLA), Article 144, 28 pp., 2021.
- DOI/arXiv/URL: https://doi.org/10.1145/3485521
- Qué aporta: Sustituye el perfilado dinámico por perfilado estático para alimentar las decisiones de BOLT, recuperando buena parte de las ganancias (binarios un 5,47 % más rápidos que los de `clang -O3`) sin coste de ejecución. Es la referencia para discutir el determinismo y la reproducibilidad del dato de perfil.

**[LLVM-STRIP]** LLVM Project. "llvm-strip — object stripping tool." LLVM Command Guide.
- DOI/arXiv/URL: https://llvm.org/docs/CommandGuide/llvm-strip.html
- Qué aporta: Documentación de la herramienta que elimina secciones y símbolos de un objeto (`--strip-all` por defecto) y que opera in situ. Es la operación post-link de mayor impacto inmediato sobre el tamaño medible del binario.

**[LLVM-SIZE]** LLVM Project. "llvm-size — print size information." LLVM Command Guide.
- DOI/arXiv/URL: https://llvm.org/docs/CommandGuide/llvm-size.html
- Qué aporta: Define la métrica estándar de medida de tamaño por secciones (`.text`, `.data`, etc.) que el proyecto debe usar como función objetivo para que las comparaciones entre variantes sean reproducibles y comparables entre toolchains.

**[LLVM-OBJCOPY]** LLVM Project. "llvm-objcopy." LLVM Command Guide.
- DOI/arXiv/URL: https://llvm.org/docs/CommandGuide/llvm-objcopy.html
- Qué aporta: Referencia de las operaciones de copia y reescritura de secciones y símbolos que permiten eliminar secciones no usadas o ajustar flags de sección tras el enlazado. Complementa a `--gc-sections` en la dimensión de tamaño post-enlazado.

**[LD-GC-SECTIONS]** GNU Binutils. "ld Options — --gc-sections (Enable garbage collection of unused input sections)."
- DOI/arXiv/URL: https://sourceware.org/binutils/docs/ld/Options.html
- Qué aporta: Documenta el mecanismo de recolección de basura de secciones no referenciadas por el enlazador, con las salvedades sobre `__start_`/`__stop_` y `-z start-stop-gc`. Es la operación de recorte de tamaño másUSTERIOR y medible directamente con `llvm-size`.

---

## AREA 8 — Research defensivo/empresarial sobre packing y por qué empaquetar suele aumentar la detectabilidad

**[MOSER-ACSAC07]** Moser, A.; Krügel, C.; Kirda, E. "Limits of Static Analysis for Malware Detection." Twenty-Third Annual Computer Security Applications Conference (ACSAC '07), pp. 421-430, 2007.
- DOI/arXiv/URL: https://doi.org/10.1109/ACSAC.2007.21
- Qué aporta: Analiza sistemáticamente por qué el análisis estático falla como detector y qué condiciones deben cumplirse (empaquetado, ofuscación, etc.) para eludirlo. Es la referencia que fundamenta que "empaquetar no es detección", sino un filtro que además destruye la señal disponible para el defensor.

**[EUREKA]** Sharif, M.; Yegneswaran, V.; Saidi, H.; Porras, P.; Lee, W. "Eureka: A Framework for Enabling Static Malware Analysis." Computer Security - ESORICS 2008, pp. 481-500, 2008.
- DOI/arXiv/URL: https://doi.org/10.1007/978-3-540-88313-5_31
- Qué aporta: Presenta un framework de desempaquetado (descompresión, traza gruesa de ejecución y resolución de API) con métricas de "analyzability" para medir cuánto mejora el binario tras desempaquetarse, y demuestra que el análisis estático sólo es viable tras una etapa de desempaquetado fiable. Es la fuente canónica para argumentar que el packing degrada la analizabilidad y por tanto dispara la respuesta defensiva (AV, EDR, sandboxes).

**[OMNIUNPACK]** Martignoni, L.; Christodorescu, M.; Jha, S. "Omniunpack: Fast, generic, and safe unpacking of malware." ACSAC 2007.
- DOI/arXiv/URL: https://doi.org/10.1007/978-3-540-46907-8_22 — DOI citado en la bibliografía de ESORICS 2008 (pp. 481-500); no confirmado en fuente primaria
- Qué aporta: Demuestra que el desempaquetado genérico es hoy viable y barato, lo que invierte la ecuación de ventajas del packing: el coste de evadir AV estática crece mientras el coste de detección conductual (EDR, sandbox) permanece estable. Base para la afirmación "size != stealth".

**[PACKERS-FEATURES]** Ramamoorthy, J.; Shashidhar, N.K.; Varol, C. "Packers and Features: Efficacy of Static Analysis for Packed Linux Malware." 2025 13th International Symposium on Digital Forensics and Security (ISDFS), pp. 1-6, 2025.
- DOI/arXiv/URL: https://doi.org/10.1109/ISDFS65363.2025.11012083
- Qué aporta: Medición empírica de la eficacia del análisis estático sobre malware Linux empaquetado: muestra que el packing puede no impedir la detección y que el propio packer genera características fácilmente aprovechables por los detectores. Es la evidencia más directa y reciente para documentar la tesis "tamaño no equivale a stealth".

**[VB-PACKER-POLICY]** Mody, S.; Muttik, I.; Ferrie, P. "Standards and policies on packer use." Virus Bulletin VB2010.
- DOI/arXiv/URL: https://www.virusbulletin.com/conference/vb2010/abstracts/standards-and-policies-packer-use
- Qué aporta: Documento chords del malware working group de ICSA que delinea propiedades de los packers y recomienda guías para la detección genérica de ficheros empaquetados por los propios antivirus. Muestra que la industria ya normalizó la detección de packers como señal propia, es decir, empaquetar produce una huella reconocible.

**[ONE-PACKER]** Mesbahi, M. et al. "One packer to rule them all: Empirical identification, comparison and circumvention of current Antivirus detection techniques." Black Hat USA 2014.
- DOI/arXiv/URL: https://blackhat.com/docs/us-14/materials/us-14-Mesbahi-One-Packer-To-Rule-Them-All-WP.pdf
- Qué aporta: Medición empírica sobre un conjunto amplio de muestras y varios antivirus: la detección estática se degrada con el packing, pero la detección por emulación y en runtime permanece, y el propio packer produce artefactos (nuevo PE, stub, secciones cifradas) que algunos productos detectan mejor que el binario original. Documenta empíricamente que empaquetar cambia lo que se ve, no que se vea menos.

**[ATTACK-T1027]** MITRE. "Obfuscated Files or Information: Software Packing (T1027.002)."
- DOI/arXiv/URL: https://attack.mitre.org/techniques/T1027/002/
- Qué aporta: Fuente normativa que confirma el ID y el nombre exactos: T1027 "Obfuscated Files or Information" y sub-técnica T1027.002 "Software Packing", con 18 sub-técnicas hermanas (binary padding, steganography, compile after delivery, dynamic API resolution, stripped payloads, fileless storage, etc.). Sirve para anclar formalmente la taxonomía de "packing" como técnica de ofuscación adversarial.

---

# REFERENCIAS NO VERIFICADAS

*(No se pudo confirmar por fuente primaria; NO deben citarse con DOI o páginas inventadas. Se indica el estado real de la comprobación.)*

## AREA 1

- **"Size-Customized Software" (Reif et al., CC 2018)** — **NO ENCONTRADO.** Se comprobó el sumario completo y público de ACM CC '18 (*Proceedings of the 27th ACM SIGPLAN Conference on Compiler Construction*, DOI 10.1145/3178372): 20 artículos, ninguno con ese título. Búsquedas por la frase exacta en web general y en el survey de fuzzing de compiladores tampoco devuelven el título. **Probablemente hay una confusión de título o de venue**; el sustituto verificado más cercano en esa misma conferencia es *PAYJIT: space-optimal JIT compilation and its practical implementation* (DOI 10.1145/3178372.3179523). Decidir si se cita la referencia original con la nota "no verificable" o se sustituye por PAYJIT.
- **Survey "Code size reduction: a survey" / "A survey on techniques for reducing the size of compiled code"** — no located bajo esos títulos; el único survey del área que sí se pudo verificar es *The Art, Science, and Engineering of Fuzzing: A Survey* (no es de tamaño).
- **Documentación de ICF en `gold`/`lld` (`--icf`)** — el manual de GNU ld (`Options.html`) **no** documenta `--icf` (sólo existe en gold/lld); la portada de lld.llvm.org carga pero no se localizó la sección. Sin URL verificada.
- **Clang `-Oz` / versión de LLVM que lo introdujo** — véase la nota de método al final de esta sección.

## AREA 2

- **Turner, S.; Laurila, M.; Real, L.C. "Bayesian optimization of performance-critical parameters in large-scale computing systems." SC 2014** — **NO VERIFICADO en fuente primaria.** No se localizó la ficha del artículo (ni DOI 10.1145/...) pese a múltiples búsquedas; la frase exacta **"performance islands"** **tampoco** pudo confirmarse en ese trabajo (no aparece en ninguno de los fragmentos indexados que se pudieron leer). Es la referencia más importante de su área y la que más conviene re-verificar manualmente.
- **OpenTuner** ("OpenTuner: An Optimization Framework for Finding Optimal Program Parameters", LLVM workshop 2014) — no se localizó ficha primaria; arXiv no lo indexa bajo ese título.
- **Optuna** (Akiba et al., KDD 2019, "Optuna: A Next-generation Hyperparameter Optimization Framework") — no verificado.
- **Magic-AutoNVM** — no encontrado por título (ni en arXiv ni en Crossref).
- **TuneSpace / Aladdin** y **"Multiobjective optimization of deep learning compilers" / frontera de Pareto (latencia, model size)** — no se localizó ninguna referencia primaria con esos títulos exactos. La evidencia indirecta es que TVM/Ansor (verificados) exponen métricas y espacios de schedule multiobjetivo, pero no hay un artículo citable con el título que indicas.

## AREA 3

- **Zhuravleva, R. et al. "Resolving Performance Cliff Problems in HPC Applications." SC 2012** — no verificado (DOI no confirmado).
- **Hamerly, G.; Elbaum, S. "Statistical Rigour in Performance Benchmarking." ICPE 2013** — no verificado por título y autores.
- **Herramientas "Ambegga" (Hamerly & Elbaum), "PerfPMU" (Chen), "Elena" (Kalibera & Jones), "DoDe", "SEIP", "Coffee", "Cortina", "LinReg" (Ephan & Emer), "FATE and DESTINI", "PerfMiner" (Ephan & Emer, ICPE 2010)** — ninguna se pudo localizar con título y autoría verificables; no las incluyo.
- **Ephan & Emer, "Measuring the Performance of Parallel Programs..." (PerfMiner, ICPE 2010)** — no verificado.

## AREA 4

- **Steele et al., "Compiler Fuzzing through Separation" (PLDI 2018)** — **NO ENCONTRADO.** Verificado ausente del sumario público de PLDI '18 (59 entradas, conference-publishing/ACM) y ausente del survey *A Survey of Modern Compiler Fuzzing* (arXiv:2306.06884). Alternativas verificadas que cubren el mismo objetivo: *Compiler validation via equivalence modulo inputs* (PLDI 2014), *Many-core compiler fuzzing* (PLDI 2015, DOI 10.1145/2737924.2737986) y *Compiler fuzzing through deep learning* (ISSTA 2018, DOI 10.1145/3213846.3213848).
- **"Finding Bugs in Compilers with Csmith" (PLDI 2006)** — el *venue* es correcto (el sumario de *Proceedings of the 3rd ACM SIGPLAN Conference on Programming Language Design and Implementation* tiene DOI base 10.1145/1133981, confirmado), pero **no** se pudo confirmar el DOI concreto del artículo ni la lista de autores (Chen, Gaddam, Juvenile, Lee, Regehr) en fuente primaria. La obra de Csmith que sí está verificada es *Finding and understanding bugs in C compilers*, PLDI 2011 (DOI 10.1145/1993498.1993532).
- **Kovács, A. et al., "Effective Grey-box Fuzzing Process for Automatic Software Testing." ICST 2016** — no verificado (no se confirmó el DOI; la búsqueda en IEEE Xplore sólo devolvió artículos de grey-box fuzzing posteriores).
- **McKeage, W.C. "Differential Testing." IEEE Computer 30(6), 1997** — no verificado (no se confirmó DOI ni paginación). La fuente que sí se pudo confirmar y es de la misma familia es McKeeman, "Differential Testing for Software", Digital Technical Journal, 1998 (referenciada en fuentes publicadas).

## AREA 5

- **Yoo, S.; Harman, M. "Overview of search-based software engineering." IEEE TSE 31(1), 2005** — no verificado en fuente primaria. Sí se verificó como cita secundaria (lista de referencias de un PDF indexado) el paper *Pareto efficient multi-objective test case selection*, ISSTA 2007, pp. 140-150.
- **Feldthaus, A.; Nejmehdad, S. "Search-Based Software Engineering." Springer, 2011** — no verificado.
- **Zeller, A.; Hildebrandt, B. "Simplifying and isolating failure-inducing input" (STVR 2002) / "The Delta Debugging Algorithm"** — no verificado; sí está confirmado el uso de delta debugging dentro de GenProg (TSE 2012, DOI 10.1109/TSE.2011.104), que puede usarse como cita indirecta.
- **Long, F.; Rinard, M. "PAR"** — no verificado (la forma exacta del título — p. ej. *PROPANE* / *Autophagy* — no pudo determinarse con certeza).
- **`afl-tmin` / AFL (Kovács et al.)** — el binario `afl-tmin` y el paper de AFL no pudieron verificarse; sí está verificado el uso de AFL en trabajos posteriores (p. ej. *Making No-Fuss Compiler Fuzzing Effective*, CC 2022, DOI 10.1145/3497776.3517765).

## AREA 6

- **"Reproducible Builds: A Manifesto" (Bryn et al.)** — **NO ENCONTRADO.** `https://reproducible-builds.org/docs/manifesto/` devuelve **404**, y el índice de publicaciones del propio proyecto (`/docs/publications/`) no contiene ninguna entrada con ese título. El sustituto académico verificado y de mayor peso es **Lamb & Zacchiroli, "Reproducible Builds: Increasing the Integrity of Software Supply Chains", IEEE Software 2022, DOI 10.1109/MS.2021.3073045** (arXiv:2104.06020), que es donde realmente está la consolidación teórica del movimiento.
- **`gcc -frandom-seed`** — el flag existe en GCC, pero no se pudo localizar la entrada exacta en `Optimize-Options.html` (aparece en otras páginas del manual de GCC); la referencia a la opción queda como URL de manual sin ancla verificada.

## AREA 7

- **BOLT en PLDI 2020** — **no existe en ese venue**: el paper de BOLT es **CGO 2019** (DOI 10.1109/CGO.2019.8661201), verificado. Si el borrador cita "BOLT, PLDI 2020", es un error de venue que debe corregirse.
- **"Improving binary size with function merging"** — el trabajo equivalente y verificado es *Effective function merging in the SSA form*, PLDI 2020 (DOI 10.1145/3385412.3386030), que es ICF/function merging a nivel de optimizador y encaja bien en esta área.
- **"Propeller: Profile-guided post-link code layout optimization"** — el título exacto verificado es *"Propeller: A Profile Guided, Relinking Optimizer for Warehouse-Scale Applications"* (ASPLOS '23 Vol. 2).

## AREA 8

- **Moser, A.; Krügel, C.; Baldi, A. "A Framework for Static Analysis of Packed Malicious Code." ACSAC 2013** — **NO ENCONTRADO.** Los papers verificados de Moser + Krügel son *"Limits of Static Analysis for Malware Detection"* (ACSAC 2007) y *"Exploring Multiple Execution Paths for Malware Analysis"* (IEEE S&P 2007); ninguno de los dos incluye a Baldi como autor. Parece una atribución errónea (autor y año mezclados).
- **ElMhabr, "Leveraging industry insights for a comparative study of packing techniques"** — no se localizó ficha primaria (no aparece en Crossref con ese título; el trabajo de ElMhabr sobre identificación de packers más citado es *Android packer identification using static analysis*, Journal of Information Security and Applications, 2015). Alternativas verificadas para cubrir el mismo punto: *Standards and policies on packer use* (VB2010) y *One packer to rule them all* (Black Hat 2014).
- **Christodoulou, M. et al. "Metamorphic Malware Payload Generation for Adversarial Evasion." IEEE S&P 2020** — **NO ENCONTRADO** en Crossref ni en el sumario de IEEE S&P 2020 (recuperado vía proceedings.com). El trabajo más cercano verificado es *"Intriguing Properties of Adversarial ML Attacks in the Problem Space"* (Pierazzi, Pendlebury, Cortellazzi, Cavallaro, IEEE S&P 2020) y *"Generation & Evaluation of Adversarial Examples for Malware Obfuscation"* (IEEE, https://ieeexplore.ieee.org/document/8999277).
- **"Anti-unpacking: A Challenge for Malware Sandboxes"** — no se localizó ninguna publicación con ese título exacto; no verificable.
- **Living-off-the-land / "malware-free" tradecraft (literatura académica)** — no localicé una publicación revisada por pares con ese enfoque; sólo literatura industrial (p. ej., MITRE ATT&CK T1218 "System Binary Proxy Execution" / T1219, no consultadas en detalle). Queda como hueco real de la literatura.

---

## AREA 9 - Formato PE/COFF: la semantica COMDAT y la ausencia de tabla de simbolos

*Anadida tras el experimento dirigido `bench/experimentos.py icf`, que mostro
que el plegado de codigo identico en PE lo produce la semantica COMDAT del
formato y no ICF, y que `llvm-strip --strip-all` es un no-op sobre PE.*

**[PE-SPEC]** Microsoft. "PE Format (Portable Executable and Common Object File Format)." Microsoft Learn (Win32 apps).
- DOI/arXiv/URL: https://learn.microsoft.com/en-us/windows/win32/debug/pe-format
- Que aporta: Es la fuente primaria de los dos mecanismos del hallazgo. (a) La seccion "COMDAT Sections (Object Only)" establece que `IMAGE_SCN_LNK_COMDAT` marca la seccion como COMDAT y que "The Selection field determines the way in which the linker resolves the multiple definitions of COMDAT sections" (valores `IMAGE_COMDAT_SELECT_NODUPLICATES`, `..._ANY`, `..._SAME_SIZE`, `..._EXACT_MATCH`, `..._ASSOCIATIVE`, `..._LARGEST`): el plegado de secciones identicas es una propiedad del FORMATO, no de una opcion del enlazador. (b) En "COFF File Header (Object and Image)" se documenta que `PointerToSymbolTable` "should be zero for an image because COFF debugging information is deprecated", lo que confirma en fuente primaria que un ejecutable PE no lleva tabla de simbolos y por tanto `llvm-strip --strip-all` no tiene nada que eliminar.

**[LLD-DOC]** LLVM Project. "LLD - The LLVM Linker." lld documentation.
- DOI/arXiv/URL: https://lld.llvm.org/
- Que aporta: Documenta que el puerto PE/COFF de lld "is complete, including Windows debug info (PDB) support", mientras que la documentacion de opciones que se cita (`-icf=all`) corresponde al puerto ELF. La propia pagina incluye la nota "Since GNU ld doesn't support the -icf=all and -gdb-index options, we removed them from the command line for GNU ld", lo que evidencia que `-icf=all` es sintaxis del enlazador ELF. Sirve para sostener el hallazgo de que `--icf=all` y `--gc-sections` son banderas de ELF que `lld-link` ignora con un aviso, y que la sintaxis valida para PE es `/OPT:ICF` y `/OPT:REF`.

**[CLANG-FFSECTIONS]** LLVM Project. "Clang command line argument reference - Code Generation Options." Clang Documentation.
- DOI/arXiv/URL: https://clang.llvm.org/docs/ClangCommandLineReference.html
- Que aporta: Documenta `-ffunction-sections` ("Place each function in its own section") y `-fdata-sections`, la palanca de compilacion que en target COFF hace que clang emita cada funcion en su propia seccion COMDAT y que, por el mecanismo de seleccion COMDAT documentado en [PE-SPEC], permite al enlazador deduplicar las funciones identicas sin necesidad de ICF.

**Nota de verificacion de esta area.** Las tres fuentes se consultaron
directamente el 2026-10-20. El mecanismo COMDAT y la ausencia de tabla de
simbolos en las imagenes PE se verificaron ademas EMPIRICAMENTE en la maquina
del experimento: contando el numero de copias de una funcion byte-identica en
el `.text` del ejecutable, y comprobando que la funcion nunca referenciada no
aparece en el binario base (es decir, lld-link hace recoleccion de secciones
muertas por defecto).

---

## Notas de verificación

- Herramientas de verificación usadas: API de Crossref (metadatos exactos de DOI), API de arXiv (metadatos de preprints), sumarios oficiales de ACM vía *conference-publishing.com*, páginas de proyecto oficiales (clang.llvm.org, gcc.gnu.org, llvm.org, sourceware.org, reproducible-builds.org, attack.mitre.org, diffoscope.org) y fichas de repositorios institucionales (unm.edu, cs.wisc.edu, cmu.edu, utah.edu) y de repositorios de acceso abierto (arxiv.org, blackhat.com).
- Bloqueos técnicos que redujeron la cobertura: DBLP (dblp.org, dblp.uni-trier.de, dblp.dagstuhl.de) está protegido por Anubis y no es accesible de forma automatizada; `dl.acm.org` devuelve 403/CAPTCHA en fetching directo (accesible sólo vía resultados de búsqueda); Semantic Scholar devolvió 429 de forma sostenida; OpenAlex agotó su presupuesto diario sin clave.
- **Sobre `-Oz` en Clang**: hechos verificados = (a) el flag `-Oz` existe en el pipeline de `opt` de LLVM desde al menos el patch de Chandler Carruth de mayo de 2012; (b) `bugpoint`/`opt` recibieron soporte explícito de `-Os`/`-Oz` en el commit r372079 (2016, mergeado 2019); (c) las **Clang 11 release notes** (tag `llvmorg-11.0.0`) documentan que en enlaces `-flto={full,thin}` "-Os, -Oz and -Og can be used now"; (d) GCC documenta `-Oz` en *Optimize Options*. **No** se pudo determinar de forma verificable en qué versión de Clang se introdujo `-Oz` como flag del driver (el texto "-Oz" no aparece en `clang/include/clang/Driver/Options.td` ni en `clang/lib/Driver/Driver.cpp` de las tags 10-14, lo que sugiere que la definición vive en otro punto del driver). Recomendación: citar el command-line reference de Clang y las release notes de Clang 11, y **no** afirmar una versión de introducción sin comprobarlo manualmente.

---

## Cómo citar este trabajo

```bibtex
@misc{isla_estabilidad,
  title        = {Isla de estabilidad: un banco de pruebas reproducible para la frontera
                  tamaño/tiempo/variabilidad en binarios compilados},
  author       = {<Apellido, Nombre> and <Apellido, Nombre>},
  year         = {2026},
  howpublished = {Preprint / Informe técnico},
  note         = {Banco de pruebas reproducible; protocolo de cribado en dos fases
                  (cribado por varianza y después barrido de Pareto), con verificación
                  diferencial y metamórfica de equivalencia funcional y builds
                  deterministas para la medición},
  keywords     = {code size, performance variability, Pareto frontier, reproducible
                  builds, compiler testing, differential testing, metamorphic testing}
}
```

Elementos que el trabajo debe declarar explícitamente para ser citable:

- **Toolchain fijada**: versión exacta de compilador, linker, libc y binutils, con los flags usados (incluido `-frandom-seed`, `-ffile-prefix-map`/`-fdebug-prefix-map` y `--build-id=sha1`).
- **Protocolo de medición**: número de repeticiones, política de descarte de outliers, tamaño de muestra y test estadístico aplicado (no sólo promedios; véanse **[GGE-2007]**, **[MENEIDE-TC]**, **[HOEFLER-SC15]**).
- **Definición de "isla"**: criterio explícito de entrada y salida (p. ej. insignificant difference test sobre varianza y sobre la frontera de Pareto de tamaño/tiempo).
- **Reproducibilidad**: artefactos publicados con *diffoscope* (**[DIFFOSCOPE]**) y respectar los commandements de Reproducible Builds (**[RB-COMMANDMENTS]**, **[RB-SUPPLYCHAIN]**).
- **Validación de correctitud**: differential testing (**[YANG-CSMITH-PLDI11]**, **[BARANY-CC18]**, **[EMI]**) y metamorphic testing (**[CHEN-MT-1998]**, **[CSUR-MT]**) como oráculos de equivalencia funcional de las variantes de tamaño.
- **Selección del subconjunto**: criterio SBSE de cribado y reducción del espacio de candidatos (**[HARMAN-FOSE07]**, **[GENPROG-TSE12]**), con la reducer de BOLT/Propeller como motor post-link opcional (**[BOLT-CGO19]**, **[PROPELLER]**).
