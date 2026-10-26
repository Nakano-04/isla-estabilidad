"""
estadistica.py — Estadística descriptiva para mediciones ruidosas.

Contiene las herramientas que separan "diferencia real" de "ruido de máquina":
mediana robusta, MAD, coeficiente de variación, intervalos de confianza por
bootstrap sobre la mediana, y un diagnóstico de deriva temporal (para saber si
la máquina se calentó o se apareció un proceso competidor durante el ensayo).

Referencia conceptual: la variabilidad es una dimensión de primer orden en
tuning empírico (ver CITAS.md, área 3), no un simple residuo a eliminar.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass


def mediana(xs: list[float]) -> float:
    return statistics.median(xs)


def percentil(xs: list[float], q: float) -> float:
    if not xs:
        return float("nan")
    ys = sorted(xs)
    if len(ys) == 1:
        return ys[0]
    pos = q * (len(ys) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ys[int(pos)]
    return ys[lo] + (ys[hi] - ys[lo]) * (pos - lo)


def mad(xs: list[float]) -> float:
    """Median Absolute Deviation (robusto frente a outliers)."""
    if not xs:
        return float("nan")
    m = statistics.median(xs)
    return statistics.median([abs(x - m) for x in xs])


def desviacion(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    return statistics.stdev(xs)


def coeficiente_variacion(xs: list[float]) -> float:
    """CV = sigma / media. Métrica canónica de inestabilidad relativa."""
    if not xs:
        return float("nan")
    m = statistics.fmean(xs)
    if m == 0:
        return float("nan")
    return desviacion(xs) / m


def rango_intercuartil(xs: list[float]) -> float:
    return percentil(xs, 0.75) - percentil(xs, 0.25)


def bootstrap_ci(
    xs: list[float],
    *,
    n_boot: int = 2000,
    alpha: float = 0.05,
    semilla: int = 20260920,
    estadistico=mediana,
) -> tuple[float, float]:
    """IC percentil para el estadistico indicado (por defecto, la mediana)."""
    if len(xs) < 3:
        return (float("nan"), float("nan"))
    rng = random.Random(semilla)
    n = len(xs)
    muestras = []
    for _ in range(n_boot):
        remuestreo = [xs[rng.randrange(n)] for _ in range(n)]
        muestras.append(estadistico(remuestreo))
    muestras.sort()
    lo = percentil(muestras, alpha / 2)
    hi = percentil(muestras, 1 - alpha / 2)
    return (lo, hi)


def solape_ci(a: tuple[float, float], b: tuple[float, float]) -> bool:
    """¿Los dos intervalos de confianza se solapan? (test conservador)"""
    if any(math.isnan(x) for x in (*a, *b)):
        return True
    return not (a[1] < b[0] or b[1] < a[0])


def deriva(xs: list[float]) -> float:
    """Pendiente relativa de una regresión lineal sobre el índice de la corrida.

    Diagnostico de calidad del ensayo: un valor alto indica deriva temporal
    (calentamiento, competencia por CPU) y por tanto mediciones poco fiables.
    Se expresa como porcentaje de cambio por unidad de índice normalizado.
    """
    n = len(xs)
    if n < 3:
        return 0.0
    mx = (n - 1) / 2
    my = statistics.fmean(xs)
    if my == 0:
        return 0.0
    sxx = sum((i - mx) ** 2 for i in range(n))
    if sxx == 0:
        return 0.0
    sxy = sum((i - mx) * (xs[i] - my) for i in range(n))
    pendiente = sxy / sxx
    # pendiente por paso, expresada como % de la media
    return 100.0 * pendiente / my


@dataclass
class Resumen:
    n: int
    mediana: float
    media: float
    minimo: float
    maximo: float
    p05: float
    p95: float
    desviacion: float
    mad: float
    iqr: float
    cv: float
    ci_bajo: float
    ci_alto: float
    deriva_pct: float

    def como_dict(self) -> dict:
        return {
            "n": self.n,
            "mediana": round(self.mediana, 6),
            "media": round(self.media, 6),
            "min": round(self.minimo, 6),
            "max": round(self.maximo, 6),
            "p05": round(self.p05, 6),
            "p95": round(self.p95, 6),
            "desviacion": round(self.desviacion, 6),
            "mad": round(self.mad, 6),
            "iqr": round(self.iqr, 6),
            "cv": round(self.cv, 6),
            "ci_bajo": round(self.ci_bajo, 6),
            "ci_alto": round(self.ci_alto, 6),
            "deriva_pct": round(self.deriva_pct, 4),
        }


def resumir(xs: list[float], *, n_boot: int = 2000) -> Resumen:
    if not xs:
        nan = float("nan")
        return Resumen(0, nan, nan, nan, nan, nan, nan, nan, nan, nan, nan, nan, nan, 0.0)
    lo, hi = bootstrap_ci(xs, n_boot=n_boot)
    return Resumen(
        n=len(xs),
        mediana=mediana(xs),
        media=statistics.fmean(xs),
        minimo=min(xs),
        maximo=max(xs),
        p05=percentil(xs, 0.05),
        p95=percentil(xs, 0.95),
        desviacion=desviacion(xs),
        mad=mad(xs),
        iqr=rango_intercuartil(xs),
        cv=coeficiente_variacion(xs),
        ci_bajo=lo,
        ci_alto=hi,
        deriva_pct=deriva(xs),
    )
