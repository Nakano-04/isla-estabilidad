/*
 * carga.c — Carga de trabajo benigna y determinista.
 *
 * Diseñado para el experimento "isla de estabilidad" (ver docs/PROTOCOLO.md).
 *
 * Reglas de diseño (verificadas por el arnés):
 *   1. Sin E/S, sin red, sin aleatoriedad no sembrada, sin punto flotante.
 *   2. Toda la aritmética es entera y de semántica bien definida (uint32/uint64
 *      con wraparound explícito). Ningún nivel de optimización puede cambiar
 *      el resultado: el programa debe ser bit-idéntico entre -O0 y -Oz.
 *   3. Cada componente usa una SEMILLA INDEPENDIENTE del PRNG, de modo que el
 *      orden de consumo de números aleatorios no acopla los componentes. Esto
 *      permite una reimplementación independiente en Python que produzca
 *      exactamente la misma salida (testing diferencial real, no circular).
 *   4. La salida a stdout es un "digest" estable, suitable para comparación
 *      byte a byte entre variantes.
 *   5. Las métricas del propio proceso (tiempo interno, pico de memoria) van a
 *      stderr, para no contaminar el digest.
 *
 * Compilación de referencia (driver GNU de clang sobre target MSVC):
 *   clang --target=x86_64-pc-windows-msvc -MD -fuse-ld=lld -O2 carga.c -o carga.exe
 */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "aux_header.h"

#if defined(_WIN32)
#  include <windows.h>
#  define IS_WIN32 1
#else
#  include <time.h>
#  define IS_WIN32 0
#endif

/* ------------------------------------------------------------------ */
/* PRNG: xorshift64* (Marsaglia). Determinista y portable bit a bit.   */
/* ------------------------------------------------------------------ */

typedef struct {
    uint64_t estado;
} prng_t;

static void prng_iniciar(prng_t *p, uint64_t semilla) {
    p->estado = semilla;
}

static uint64_t prng_siguiente(prng_t *p) {
    uint64_t x = p->estado;
    x ^= x >> 12;
    x ^= x << 25;
    x ^= x >> 27;
    p->estado = x;
    return x * 0x2545F4914F6CDD1DULL;
}

/* Semillas independientes por componente. */
#define SEMILLA_ARRAY    0x9E3779B97F4A7C15ULL
#define SEMILLA_MATRIZ   0xD1B54A32D192ED03ULL
#define SEMILLA_TEXTO    0x2545F4914F6CDD1DULL
#define SEMILLA_BUSQUEDA 0xBF58476D1CE4E5B9ULL
#define SEMILLA_DIGEST   0x94D049BB133111EBULL

/* ------------------------------------------------------------------ */
/* Utilidades de hashing                                               */
/* ------------------------------------------------------------------ */

#define FNV_OFFSET 14695981039346656037ULL
#define FNV_PRIME  1099511628211ULL

static uint64_t fnv1a(const uint8_t *buf, size_t n) {
    uint64_t h = FNV_OFFSET;
    for (size_t i = 0; i < n; i++) {
        h ^= (uint64_t)buf[i];
        h *= FNV_PRIME;
    }
    return h;
}

/* ------------------------------------------------------------------ */
/* Ordenación                                                          */
/* ------------------------------------------------------------------ */

/* Quicksort con pivote mediana-de-tres, corte a inserción y recursión
 * sobre la mitad menor (limita la profundidad de pila a O(log n)). */
static void ordenar_quicksort(uint32_t *a, int64_t lo, int64_t hi) {
    while (lo < hi) {
        if (hi - lo < 24) {
            for (int64_t i = lo + 1; i <= hi; i++) {
                uint32_t v = a[i];
                int64_t j = i - 1;
                while (j >= lo && a[j] > v) { a[j + 1] = a[j]; j--; }
                a[j + 1] = v;
            }
            return;
        }
        int64_t mid = lo + (hi - lo) / 2;
        uint32_t piv;
        if (a[lo] < a[mid]) {
            piv = (a[mid] < a[hi]) ? a[mid] : ((a[lo] < a[hi]) ? a[hi] : a[lo]);
        } else {
            piv = (a[lo] < a[hi]) ? a[lo] : ((a[mid] < a[hi]) ? a[hi] : a[mid]);
        }
        int64_t i = lo, j = hi;
        while (i <= j) {
            while (a[i] < piv) i++;
            while (a[j] > piv) j--;
            if (i <= j) {
                uint32_t t = a[i]; a[i] = a[j]; a[j] = t;
                i++; j--;
            }
        }
        if (j - lo < hi - i) {
            ordenar_quicksort(a, lo, j);
            lo = i;
        } else {
            ordenar_quicksort(a, i, hi);
            hi = j;
        }
    }
}

static void heap_sift(uint32_t *a, int64_t n, int64_t i) {
    for (;;) {
        int64_t mayor = i;
        int64_t izq = 2 * i + 1;
        int64_t der = 2 * i + 2;
        if (izq < n && a[izq] > a[mayor]) mayor = izq;
        if (der < n && a[der] > a[mayor]) mayor = der;
        if (mayor == i) return;
        uint32_t t = a[i]; a[i] = a[mayor]; a[mayor] = t;
        i = mayor;
    }
}

static void ordenar_heapsort(uint32_t *a, int64_t n) {
    for (int64_t i = n / 2 - 1; i >= 0; i--) heap_sift(a, n, i);
    for (int64_t i = n - 1; i > 0; i--) {
        uint32_t t = a[0]; a[0] = a[i]; a[i] = t;
        heap_sift(a, i, 0);
    }
}

static uint64_t suma_arreglo(const uint32_t *a, int64_t n) {
    uint64_t s = 0;
    for (int64_t i = 0; i < n; i++) s += (uint64_t)a[i];
    return s;
}

/* Búsqueda binaria; devuelve 1 si encuentra la clave. */
static int buscar_binario(const uint32_t *a, int64_t n, uint32_t clave) {
    int64_t lo = 0, hi = n - 1;
    while (lo <= hi) {
        int64_t mid = lo + (hi - lo) / 2;
        if (a[mid] == clave) return 1;
        if (a[mid] < clave) lo = mid + 1; else hi = mid - 1;
    }
    return 0;
}

/* ------------------------------------------------------------------ */
/* Matrices                                                            */
/* ------------------------------------------------------------------ */

#define DIM 64

static void mult_matriz(uint32_t c[DIM][DIM],
                        const uint32_t a[DIM][DIM],
                        const uint32_t b[DIM][DIM]) {
    for (int i = 0; i < DIM; i++) {
        for (int k = 0; k < DIM; k++) {
            uint32_t av = a[i][k];
            for (int j = 0; j < DIM; j++) {
                c[i][j] += av * b[k][j];   /* uint32: wraparound bien definido */
            }
        }
    }
}

static uint64_t suma_matriz(const uint32_t c[DIM][DIM]) {
    uint64_t s = 0;
    for (int i = 0; i < DIM; i++)
        for (int j = 0; j < DIM; j++)
            s += (uint64_t)c[i][j];
    return s;
}

/* ------------------------------------------------------------------ */
/* Temporización y memoria                                             */
/* ------------------------------------------------------------------ */

#if IS_WIN32
static double ahora_ns(void) {
    LARGE_INTEGER f, t;
    QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&t);
    return (double)t.QuadPart * 1e9 / (double)f.QuadPart;
}

typedef struct {
    DWORD cb;
    DWORD PageFaultCount;
    SIZE_T PeakWorkingSetSize;
    SIZE_T WorkingSetSize;
    SIZE_T QuotaPeakPagedPoolUsage;
    SIZE_T QuotaPagedPoolUsage;
    SIZE_T QuotaPeakNonPagedPoolUsage;
    SIZE_T QuotaNonPagedPoolUsage;
    SIZE_T PagefileUsage;
    SIZE_T PeakPagefileUsage;
} PROC_MEM_CTR;

static uint64_t pico_memoria_kb(void) {
    HMODULE k32 = GetModuleHandleA("kernel32.dll");
    if (!k32) return 0;
    typedef BOOL (WINAPI *PFN)(HANDLE, PROC_MEM_CTR *, DWORD);
    PFN fn = (PFN)GetProcAddress(k32, "K32GetProcessMemoryInfo");
    if (!fn) return 0;
    PROC_MEM_CTR c;
    memset(&c, 0, sizeof(c));
    c.cb = (DWORD)sizeof(c);
    if (!fn(GetCurrentProcess(), &c, (DWORD)sizeof(c))) return 0;
    return (uint64_t)(c.PeakWorkingSetSize / 1024);
}
#else
#include <sys/resource.h>
static double ahora_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec * 1e9 + (double)ts.tv_nsec;
}
static uint64_t pico_memoria_kb(void) {
    struct rusage ru;
    if (getrusage(RUSAGE_SELF, &ru) != 0) return 0;
    return (uint64_t)ru.ru_maxrss / 1024;
}
#endif

/* ------------------------------------------------------------------ */
/* Programa principal                                                  */
/* ------------------------------------------------------------------ */

int main(int argc, char **argv) {
    int64_t escala = 1;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--escala") == 0 && i + 1 < argc) {
            escala = strtoll(argv[++i], NULL, 10);
            if (escala < 1) escala = 1;
        } else if (strcmp(argv[i], "--ayuda") == 0) {
            printf("uso: carga [--escala N]\n");
            return 0;
        }
    }

    double t0 = ahora_ns();

    /* --- Componente 1: relleno + dos ordenaciones + búsquedas binarias --- */
    const int64_t n_elem = 65536 * escala;
    uint32_t *arr = (uint32_t *)malloc((size_t)n_elem * sizeof(uint32_t));
    uint32_t *arr2 = (uint32_t *)malloc((size_t)n_elem * sizeof(uint32_t));
    if (!arr || !arr2) { fprintf(stderr, "carga: falta memoria\n"); return 2; }

    prng_t p;
    prng_iniciar(&p, SEMILLA_ARRAY);
    for (int64_t i = 0; i < n_elem; i++) {
        arr[i] = (uint32_t)(prng_siguiente(&p) % 1000u);
    }
    memcpy(arr2, arr, (size_t)n_elem * sizeof(uint32_t));

    ordenar_quicksort(arr, 0, n_elem - 1);
    ordenar_heapsort(arr2, n_elem);

    uint64_t suma_qs = suma_arreglo(arr, n_elem);
    uint64_t suma_hs = suma_arreglo(arr2, n_elem);

    const int64_t n_sondas = 20000 * escala;
    prng_iniciar(&p, SEMILLA_BUSQUEDA);
    uint64_t coincidencias = 0;
    for (int64_t i = 0; i < n_sondas; i++) {
        uint32_t clave = (uint32_t)(prng_siguiente(&p) % 1000u);
        coincidencias += (uint64_t)buscar_binario(arr, n_elem, clave);
    }

    /* --- Componente 2: multiplicación de matrices --- */
    static uint32_t ma[DIM][DIM], mb[DIM][DIM], mc[DIM][DIM];
    prng_iniciar(&p, SEMILLA_MATRIZ);
    for (int i = 0; i < DIM; i++)
        for (int j = 0; j < DIM; j++)
            ma[i][j] = (uint32_t)(prng_siguiente(&p) >> 32);
    for (int i = 0; i < DIM; i++)
        for (int j = 0; j < DIM; j++)
            mb[i][j] = (uint32_t)(prng_siguiente(&p) >> 32);

    uint64_t suma_mat = 0;
    const int64_t reps_mat = 32 * escala;
    for (int64_t r = 0; r < reps_mat; r++) {
        memset(mc, 0, sizeof(mc));
        mult_matriz(mc, ma, mb);
        suma_mat += suma_matriz(mc);
    }

    /* --- Componente 3: texto (hash + tokenización) --- */
    const size_t n_texto = (size_t)1048576 * (size_t)escala;
    uint8_t *texto = (uint8_t *)malloc(n_texto ? n_texto : 1);
    if (!texto) { fprintf(stderr, "carga: falta memoria\n"); return 2; }
    prng_iniciar(&p, SEMILLA_TEXTO);
    for (size_t i = 0; i < n_texto; i++) {
        texto[i] = (uint8_t)(33u + (uint32_t)(prng_siguiente(&p) % 90u));
        if (i % 11 == 5) texto[i] = (uint8_t)' ';
    }
    uint64_t hash_texto = fnv1a(texto, n_texto);

    uint64_t palabras = 0;
    uint64_t chars_no_espacio = 0;
    int en_palabra = 0;
    for (size_t i = 0; i < n_texto; i++) {
        if (texto[i] == (uint8_t)' ') {
            en_palabra = 0;
        } else {
            chars_no_espacio++;
            if (!en_palabra) { palabras++; en_palabra = 1; }
        }
    }

    /* --- Componente 4: digest auxiliar + funciones auxiliares --- */
    prng_iniciar(&p, SEMILLA_DIGEST);
    uint64_t suma_prng = 0;
    for (int i = 0; i < 4096; i++) suma_prng += prng_siguiente(&p);

    /* Las tres funciones identicas se llaman una vez cada una: el ICF puede
     * plegarlas, pero el optimizador no puede eliminarlas al inlinarlas. */
    uint32_t a1 = aux_cala1((uint32_t)suma_prng);
    uint32_t a2 = aux_cala2((uint32_t)(suma_prng >> 32));
    uint32_t a3 = aux_cala3((uint32_t)suma_qs);
    uint32_t am = aux_mix(a1 ^ a2 ^ a3);

    double t1 = ahora_ns();

    /* --- Digest canónico: FNV-1a sobre la concatenación de los campos --- */
    char canon[512];
    int len = snprintf(canon, sizeof(canon),
                       "%llu|%llu|%llu|%llu|%llu|%llx|%llu|%llu|%llu|%llu|%llu",
                       (unsigned long long)suma_prng,
                       (unsigned long long)suma_qs,
                       (unsigned long long)suma_hs,
                       (unsigned long long)coincidencias,
                       (unsigned long long)suma_mat,
                       (unsigned long long)hash_texto,
                       (unsigned long long)palabras,
                       (unsigned long long)chars_no_espacio,
                       (unsigned long long)n_texto,
                       (unsigned long long)n_elem,
                       (unsigned long long)am);
    uint64_t digest = fnv1a((const uint8_t *)canon, (size_t)len);

    printf("#carga v1 escala=%lld\n", (long long)escala);
    printf("digest=%016llx\n", (unsigned long long)digest);
    printf("prng_suma=%llu\n", (unsigned long long)suma_prng);
    printf("suma_quicksort=%llu\n", (unsigned long long)suma_qs);
    printf("suma_heapsort=%llu\n", (unsigned long long)suma_hs);
    printf("coincidencias_binarias=%llu\n", (unsigned long long)coincidencias);
    printf("suma_matriz=%llu\n", (unsigned long long)suma_mat);
    printf("fnv1a_texto=%016llx\n", (unsigned long long)hash_texto);
    printf("palabras=%llu\n", (unsigned long long)palabras);
    printf("caracteres_no_espacio=%llu\n", (unsigned long long)chars_no_espacio);
    printf("longitud_texto=%llu\n", (unsigned long long)n_texto);
    printf("longitud_arreglo=%llu\n", (unsigned long long)n_elem);
    printf("aux_mix=%llu\n", (unsigned long long)am);

    fprintf(stderr, "t_interno_ms=%.4f\n", (t1 - t0) / 1e6);
    fprintf(stderr, "mem_pico_kb=%llu\n", (unsigned long long)pico_memoria_kb());

    free(texto);
    free(arr2);
    free(arr);
    return 0;
}
