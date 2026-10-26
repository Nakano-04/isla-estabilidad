"""
pareto.py — Optimización multiobjetivo: dominancia, frontera, codo, volumen.

Se implementa la definición estándar: un punto p es DOMINADO por q si q no es
peor en ninguna dimensión y es estrictamente mejor en al menos una. La
FRONTERA de Pareto es el conjunto de puntos no dominados.

La frontera se calcula aquí en lugar de ordenar por un escalar, porque el
objetivo del experimento no es "el más pequeño" sino "la curva de compromiso
entre tamaño y tiempo", con la variabilidad como filtro de factibilidad.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Punto:
    """Punto del espacio de objetivos. Se minimizan todos los ejes."""

    etiqueta: str
    x: float   # tamaño (bytes)
    y: float   # tiempo (ms)
    meta: dict | None = None

    def como_dict(self) -> dict:
        return {
            "etiqueta": self.etiqueta,
            "x": self.x,
            "y": self.y,
            "meta": self.meta or {},
        }


def domina(a: Punto, b: Punto) -> bool:
    """True si `a` domina a `b` (a <= b en todo eje y a < b en alguno)."""
    mejor_o_igual = a.x <= b.x and a.y <= b.y
    estrictamente_mejor = a.x < b.x or a.y < b.y
    return mejor_o_igual and estrictamente_mejor


def frontera(puntos: list[Punto]) -> list[Punto]:
    """Puntos no dominados, ordenados por x ascendente (y descendente)."""
    no_dominados = [
        p for p in puntos if not any(domina(q, p) for q in puntos if q is not p)
    ]
    no_dominados.sort(key=lambda p: (p.x, p.y))
    return no_dominados


def soluciones_pareto(puntos: list[Punto]) -> list[Punto]:
    """Subconjunto no dominado de forma eficiente: barrido en O(n log n).

    Algoritmo: se ordena por x ascendente (y a empate, y ascendente) y se
    recorre manteniendo el mejor y visto hasta ahora. Un punto es no dominado
    si su y es estrictamente menor que el de todos los puntos con x menor.
    Entre los puntos que comparten la misma x, sólo sobreviven los de menor y.

    Detalle sutil: dos puntos con el par (x, y) IDÉNTICO no se dominan entre
    sí (ninguno es estrictamente mejor), así que ambos pertenecen a la
    frontera. Por eso se conservan todos los del grupo que empatan en y, no
    sólo el primero.

    `frontera` calcula lo mismo por fuerza bruta O(n^2). `bench/verificar.py`
    contrasta ambas implementaciones: una versión "optimizada" que no coincide
    con la de referencia es un bug silencioso.
    """
    if not puntos:
        return []
    ordenados = sorted(puntos, key=lambda p: (p.x, p.y))
    res: list[Punto] = []
    mejor_y = math.inf
    i = 0
    while i < len(ordenados):
        x = ordenados[i].x
        j = i
        while j < len(ordenados) and ordenados[j].x == x:
            j += 1
        grupo = ordenados[i:j]
        y_min = grupo[0].y
        if y_min < mejor_y:
            # todos los del grupo con y == y_min sobreviven (son duplicados
            # exactos entre si: ninguno domina al otro)
            res.extend(p for p in grupo if p.y == y_min)
            mejor_y = y_min
        i = j
    return res


def hipervolumen(puntos: list[Punto], ref_x: float, ref_y: float) -> float:
    """Volumen hipervolumen en 2D respecto al punto de referencia (ref_x, ref_y).

    Mide el area dominada por el conjunto de puntos hasta el peor punto de
    referencia. Es un escalar util para comparar dos frentes de Pareto de
    distintas corridas: mas hipervolumen = mejor cobertura del espacio de
    compromisos (con la misma referencia).
    """
    fr = sorted(frontera(puntos), key=lambda p: p.x)
    hv = 0.0
    y_previo = ref_y
    for p in fr:
        if p.x >= ref_x or p.y >= ref_y:
            continue
        hv += (ref_x - p.x) * (y_previo - p.y)
        y_previo = p.y
    return hv


def codo(frontera_pareto: list[Punto]) -> Punto | None:
    """Punto "codo" (knee): el de mayor distancia perpendicular a la recta
    que une los extremos de la frontera. Es el compromiso más equilibrado
    entre los dos objetivos."""
    if len(frontera_pareto) < 3:
        return None
    puntos = sorted(frontera_pareto, key=lambda p: p.x)
    x1, y1 = puntos[0].x, puntos[0].y
    x2, y2 = puntos[-1].x, puntos[-1].y
    dx, dy = x2 - x1, y2 - y1
    norma = math.hypot(dx, dy)
    if norma == 0:
        return None
    mejor = None
    mejor_dist = -1.0
    for p in puntos[1:-1]:
        dist = abs(dy * (p.x - x1) - dx * (p.y - y1)) / norma
        if dist > mejor_dist:
            mejor_dist = dist
            mejor = p
    return mejor


def estabilidad_frontera(
    medidas: dict[str, dict],
    n_boot: int = 500,
    semilla: int = 20260920,
    umbral_estable: float = 0.90,
    umbral_marginal: float = 0.10,
) -> dict:
    """¿Qué puntos de la frontera están REALMENTE en ella?

    La frontera de Pareto se calcula sobre estimaciones (la mediana de N
    corridas). Si el ruido es comparable a las diferencias entre variantes,
    la COMPOSICION de la frontera es en sí misma una afirmacion estadistica:
    una variante puede aparecer o desaparecer de la frontera segun la
    realization del ruido.

    Aqui se cuantifica. Para cada remuestreo bootstrap:
      1. se remuestrea cada variante con reemplazo de sus corridas medidas;
      2. se recalcula la mediana de cada una;
      3. se recalcula la frontera de Pareto;
      4. se cuenta que variantes aparecen en ella.

    El resultado es la FRECUENCIA DE SELECCION de cada variante: la
    probabilidad de que belonging a la frontera. Una variante con frecuencia
    baja no es un hallazgo, es ruido con apariencia de hallazgo.
    """
    import random

    rng = random.Random(semilla)
    etiquetas = list(medidas.keys())
    muestras = {
        k: (medidas[k].get("muestras") or []) for k in etiquetas
    }
    # si no hay muestras crudas, se sintetiza una desde la mediana y el CV
    for k in etiquetas:
        if not muestras[k]:
            m = medidas[k]
            cv = m.get("cv", 0.0) or 0.0
            med = m.get("mediana", 0.0)
            n = max(5, int(m.get("n", 30)))
            muestras[k] = [med * (1.0 + rng.gauss(0, cv)) for _ in range(n)]

    conteo = {k: 0 for k in etiquetas}
    for _ in range(n_boot):
        puntos = []
        for k in etiquetas:
            xs = muestras[k]
            remuestreo = [xs[rng.randrange(len(xs))] for _ in range(len(xs))]
            remuestreo.sort()
            med = remuestreo[len(remuestreo) // 2]
            puntos.append(Punto(k, medidas[k]["x"], med))
        for p in frontera(puntos):
            conteo[p.etiqueta] += 1

    frec = {k: conteo[k] / n_boot for k in etiquetas}
    estables = sorted(k for k, f in frec.items() if f >= umbral_estable)
    marginales = sorted(
        k for k, f in frec.items() if umbral_marginal <= f < umbral_estable
    )
    nunca = sorted(k for k, f in frec.items() if f < umbral_marginal)
    return {
        "n_boot": n_boot,
        "frecuencias": {k: round(v, 4) for k, v in sorted(frec.items(), key=lambda kv: -kv[1])},
        "estables": estables,
        "marginales": marginales,
        "nunca": nunca,
        "resumen": (
            f"{len(estables)} variantes están en la frontera de forma estable "
            f"(frecuencia >= {umbral_estable:.0%}); "
            f"{len(marginales)} son marginales y {len(nunca)} nunca aparecen. "
            "Las marginales no deben citarse como hallazgos: su pertenencia a "
            "la frontera la decide el ruido de medicion."
        ),
    }


def mejoras_porcentuales(puntos: list[Punto], etiqueta_referencia: str) -> dict:
    ref = next((p for p in puntos if p.etiqueta == etiqueta_referencia), None)
    if ref is None:
        return {}
    out = {}
    for p in puntos:
        out[p.etiqueta] = {
            "reduccion_tamano_pct": round(100.0 * (ref.x - p.x) / ref.x, 2) if ref.x else 0.0,
            "reduccion_tiempo_pct": round(100.0 * (ref.y - p.y) / ref.y, 2) if ref.y else 0.0,
        }
    return out
