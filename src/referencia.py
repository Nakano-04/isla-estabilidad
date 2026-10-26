"""
referencia.py — Implementación INDEPENDIENTE en Python de la especificación de
`src/carga.c`.

Su proposito no es el rendimiento sino proporcionar un oracle realmente
independiente para el testing diferencial: si el binario de referencia en C
(compilado a -O0) y esta implementacion coinciden byte a byte, tenemos dos
implementaciones distintas que concuerdan, lo cual cierra el defecto clasico
del differential testing ("ambas implementaciones pueden compartir el mismo bug").

El harness compara, para cada variante:
    salida(variante) == salida(referencia C a -O0) == salida(referencia Python)

Salida: mismo formato que carga.c, en stdout.

Uso:
    python referencia.py [--escala N]
"""

from __future__ import annotations

import argparse
import sys

M64 = (1 << 64) - 1
M32 = (1 << 32) - 1

FNV_OFFSET = 14695981039346656037
FNV_PRIME = 1099511628211

SEMILLA_ARRAY = 0x9E3779B97F4A7C15
SEMILLA_MATRIZ = 0xD1B54A32D192ED03
SEMILLA_TEXTO = 0x2545F4914F6CDD1D
SEMILLA_BUSQUEDA = 0xBF58476D1CE4E5B9
SEMILLA_DIGEST = 0x94D049BB133111EB

DIM = 64


# --- Funciones auxiliares (especificacion de src/aux.c) -----------------
# Implementadas aqui de forma independiente; no comparten codigo con el C.
def aux_cala(x: int) -> int:
    return (x * 3 + 1) & M32


def aux_mix(x: int) -> int:
    return (((x ^ 0x9E3779B9) * 2654435761) + 7) & M32


class Xorshift64Star:
    """Réplica exacta de xorshift64* con aritmética de 64 bits."""

    __slots__ = ("estado",)

    def __init__(self, semilla: int) -> None:
        self.estado = semilla & M64

    def siguiente(self) -> int:
        x = self.estado
        x ^= x >> 12
        x &= M64
        x ^= (x << 25) & M64
        x ^= x >> 27
        self.estado = x
        return (x * 0x2545F4914F6CDD1D) & M64


def fnv1a(datos: bytes) -> int:
    h = FNV_OFFSET
    for b in datos:
        h ^= b
        h = (h * FNV_PRIME) & M64
    return h


def quicksort_rango(a: list[int], lo: int, hi: int) -> None:
    """Quicksort in-place con rango explícito (equivalente a la de C).
    Reimplementación con estilo distinto pero misma semántica observable."""
    while lo < hi:
        if hi - lo < 24:
            for i in range(lo + 1, hi + 1):
                v = a[i]
                j = i - 1
                while j >= lo and a[j] > v:
                    a[j + 1] = a[j]
                    j -= 1
                a[j + 1] = v
            return
        mid = (lo + hi) // 2
        if a[lo] < a[mid]:
            piv = a[mid] if a[mid] < a[hi] else (a[hi] if a[lo] < a[hi] else a[lo])
        else:
            piv = a[lo] if a[lo] < a[hi] else (a[hi] if a[mid] < a[hi] else a[mid])
        i, j = lo, hi
        while i <= j:
            while a[i] < piv:
                i += 1
            while a[j] > piv:
                j -= 1
            if i <= j:
                a[i], a[j] = a[j], a[i]
                i += 1
                j -= 1
        if j - lo < hi - i:
            quicksort_rango(a, lo, j)
            lo = i
        else:
            quicksort_rango(a, i, hi)
            hi = j


def heapsort(a: list[int]) -> None:
    n = len(a)

    def sift(i: int, size: int) -> None:
        while True:
            mayor = i
            izq, der = 2 * i + 1, 2 * i + 2
            if izq < size and a[izq] > a[mayor]:
                mayor = izq
            if der < size and a[der] > a[mayor]:
                mayor = der
            if mayor == i:
                return
            a[i], a[mayor] = a[mayor], a[i]
            i = mayor

    for i in range(n // 2 - 1, -1, -1):
        sift(i, n)
    for i in range(n - 1, 0, -1):
        a[0], a[i] = a[i], a[0]
        sift(0, i)


def buscar_binario(a: list[int], clave: int) -> bool:
    lo, hi = 0, len(a) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if a[mid] == clave:
            return True
        if a[mid] < clave:
            lo = mid + 1
        else:
            hi = mid - 1
    return False


def ejecutar(escala: int) -> str:
    # --- Componente 1 ---
    n_elem = 65536 * escala
    r = Xorshift64Star(SEMILLA_ARRAY)
    arr = [r.siguiente() % 1000 for _ in range(n_elem)]
    arr2 = list(arr)

    quicksort_rango(arr, 0, n_elem - 1)
    heapsort(arr2)

    suma_qs = sum(arr) & M64
    suma_hs = sum(arr2) & M64

    r = Xorshift64Star(SEMILLA_BUSQUEDA)
    coincidencias = 0
    for _ in range(20000 * escala):
        clave = r.siguiente() % 1000
        if buscar_binario(arr, clave):
            coincidencias += 1

    # --- Componente 2: matrices ---
    # OJO: un unico flujo de PRNG para A y luego B (como en carga.c). No se
    # reinicia el generador: B es la CONTINUACION del flujo, no una repeticion.
    r = Xorshift64Star(SEMILLA_MATRIZ)
    ma = [[r.siguiente() >> 32 for _ in range(DIM)] for _ in range(DIM)]
    mb = [[r.siguiente() >> 32 for _ in range(DIM)] for _ in range(DIM)]

    suma_mat = 0
    for _ in range(32 * escala):
        mc = [[0] * DIM for _ in range(DIM)]
        for i in range(DIM):
            for k in range(DIM):
                av = ma[i][k]
                fila_c, fila_b = mc[i], mb[k]
                for j in range(DIM):
                    fila_c[j] = (fila_c[j] + av * fila_b[j]) & M32
        for fila in mc:
            suma_mat = (suma_mat + sum(fila)) & M64

    # --- Componente 3: texto ---
    n_texto = 1048576 * escala
    r = Xorshift64Star(SEMILLA_TEXTO)
    buf = bytearray(n_texto)
    for i in range(n_texto):
        b = 33 + (r.siguiente() % 90)
        if i % 11 == 5:
            b = 32
        buf[i] = b
    hash_texto = fnv1a(bytes(buf))

    palabras = 0
    chars_no_espacio = 0
    en_palabra = False
    for b in buf:
        if b == 32:
            en_palabra = False
        else:
            chars_no_espacio += 1
            if not en_palabra:
                palabras += 1
                en_palabra = True

    # --- Componente 4 ---
    r = Xorshift64Star(SEMILLA_DIGEST)
    suma_prng = 0
    for _ in range(4096):
        suma_prng = (suma_prng + r.siguiente()) & M64

    a1 = aux_cala(suma_prng & M32)
    a2 = aux_cala((suma_prng >> 32) & M32)
    a3 = aux_cala(suma_qs & M32)
    am = aux_mix(a1 ^ a2 ^ a3)

    canon = (
        f"{suma_prng}|{suma_qs}|{suma_hs}|{coincidencias}|{suma_mat}|"
        f"{hash_texto:x}|{palabras}|{chars_no_espacio}|{n_texto}|{n_elem}|{am}"
    )
    digest = fnv1a(canon.encode("ascii"))

    lineas = [
        f"#carga v1 escala={escala}",
        f"digest={digest:016x}",
        f"prng_suma={suma_prng}",
        f"suma_quicksort={suma_qs}",
        f"suma_heapsort={suma_hs}",
        f"coincidencias_binarias={coincidencias}",
        f"suma_matriz={suma_mat}",
        f"fnv1a_texto={hash_texto:016x}",
        f"palabras={palabras}",
        f"caracteres_no_espacio={chars_no_espacio}",
        f"longitud_texto={n_texto}",
        f"longitud_arreglo={n_elem}",
        f"aux_mix={am}",
    ]
    return "\n".join(lineas) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--escala", type=int, default=1)
    args = ap.parse_args()
    sys.stdout.write(ejecutar(max(1, args.escala)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
