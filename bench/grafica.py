"""
grafica.py — Renderizado de la frontera de Pareto en SVG (sin dependencias).

Dos paneles:
  (1) tamano (bytes) vs tiempo interno (ms)  -> la frontera de Pareto
  (2) tamano (bytes) vs variabilidad (CV)     -> el eje V del experimento

Ambas ejes usan escala logaritmica: el rango de tamano entre variantes es de
un orden de magnitud (los bits de depuracion y la instrumentacion dwarfan al
codigo optimizado), y una escala lineal aplastaria la zona interesante.

SVG porque es texto: se abre en cualquier navegador, se versiona en git sin
binarios opacos y se puede regenerar de forma determinista.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

COLORES_NIVEL = {
    "O0": "#d1495b",
    "O1": "#e8a33d",
    "O2": "#2a9d8f",
    "O3": "#3a86ff",
    "Os": "#9b5de5",
    "Oz": "#00bbf9",
}


@dataclass
class PuntoGrafica:
    etiqueta: str
    x: float
    y: float
    nivel: str
    meta: dict


def _log(v: float) -> float:
    return math.log10(max(v, 1e-12))


def _escala_log(v: float, vmin: float, vmax: float, p0: float, p1: float) -> float:
    if vmax <= vmin:
        return (p0 + p1) / 2
    t = (_log(v) - _log(vmin)) / (_log(vmax) - _log(vmin))
    t = max(0.0, min(1.0, t))
    return p0 + t * (p1 - p0)


def _formato_bytes(v: float) -> str:
    if v >= 1024 * 1024:
        return f"{v/1024/1024:.2f} MB"
    if v >= 1024:
        return f"{v/1024:.1f} KB"
    return f"{v:.0f} B"


def _escapar(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def _panel(
    svg: list[str],
    *,
    x0: float,
    y0: float,
    w: float,
    h: float,
    puntos: list[PuntoGrafica],
    frontera: list[PuntoGrafica],
    titulo: str,
    etiqueta_x: str,
    etiqueta_y: str,
    formato_x,
    formato_y,
    ver_x=lambda p: True,
    ver_y=lambda p: True,
    destacar: set[str] | None = None,
) -> None:
    xs = [p.x for p in puntos]
    ys = [p.y for p in puntos]
    if not xs:
        return
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    # margen logaritmico
    lx, ly = _log(xmax) - _log(xmin), _log(ymax) - _log(ymin)
    xmin = 10 ** (_log(xmin) - max(0.12, lx * 0.10))
    xmax = 10 ** (_log(xmax) + max(0.12, lx * 0.10))
    ymin = 10 ** (_log(ymin) - max(0.12, ly * 0.10))
    ymax = 10 ** (_log(ymax) + max(0.12, ly * 0.10))

    px = lambda v: x0 + _escala_log(v, xmin, xmax, 0, w)
    py = lambda v: y0 + h - _escala_log(v, ymin, ymax, 0, h)

    svg.append(
        f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'fill="#fbfbfd" stroke="#d7d7de"/>'
    )
    svg.append(
        f'<text x="{x0:.1f}" y="{y0-14:.1f}" font-family="Segoe UI,Arial,sans-serif" '
        f'font-size="15" font-weight="600" fill="#1d1d1f">{_escapar(titulo)}</text>'
    )

    # rejilla + ticks
    for e in range(-1, 8):
        for k in range(1, 10):
            v = k * (10 ** e)
            if not (xmin <= v <= xmax):
                continue
            X = px(v)
            svg.append(
                f'<line x1="{X:.1f}" y1="{y0:.1f}" x2="{X:.1f}" y2="{y0+h:.1f}" '
                f'stroke="#e8e8ee" stroke-width="1"/>'
            )
            svg.append(
                f'<text x="{X:.1f}" y="{y0+h+16:.1f}" font-family="Segoe UI,Arial,sans-serif" '
                f'font-size="10" fill="#6b6b74" text-anchor="middle">{_escapar(formato_x(v))}</text>'
            )
    for e in range(-1, 8):
        for k in range(1, 10):
            v = k * (10 ** e)
            if not (ymin <= v <= ymax):
                continue
            Y = py(v)
            svg.append(
                f'<line x1="{x0:.1f}" y1="{Y:.1f}" x2="{x0+w:.1f}" y2="{Y:.1f}" '
                f'stroke="#e8e8ee" stroke-width="1"/>'
            )
            svg.append(
                f'<text x="{x0-8:.1f}" y="{Y+3:.1f}" font-family="Segoe UI,Arial,sans-serif" '
                f'font-size="10" fill="#6b6b74" text-anchor="end">{_escapar(formato_y(v))}</text>'
            )

    # ejes
    svg.append(
        f'<line x1="{x0:.1f}" y1="{y0+h:.1f}" x2="{x0+w:.1f}" y2="{y0+h:.1f}" '
        f'stroke="#9a9aa3" stroke-width="1.2"/>'
    )
    svg.append(
        f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x0:.1f}" y2="{y0+h:.1f}" '
        f'stroke="#9a9aa3" stroke-width="1.2"/>'
    )
    svg.append(
        f'<text x="{x0+w/2:.1f}" y="{y0+h+36:.1f}" font-family="Segoe UI,Arial,sans-serif" '
        f'font-size="12" fill="#3a3a3c" text-anchor="middle">{_escapar(etiqueta_x)}</text>'
    )
    svg.append(
        f'<text x="{x0-56:.1f}" y="{y0+h/2:.1f}" font-family="Segoe UI,Arial,sans-serif" '
        f'font-size="12" fill="#3a3a3c" text-anchor="middle" '
        f'transform="rotate(-90 {x0-56:.1f} {y0+h/2:.1f})">{_escapar(etiqueta_y)}</text>'
    )

    # frontera (escalera)
    if len(frontera) >= 2:
        pts = " ".join(f"{px(p.x):.1f},{py(p.y):.1f}" for p in frontera)
        svg.append(
            f'<polyline points="{pts}" fill="none" stroke="#111" stroke-width="2" '
            f'stroke-dasharray="6 4" opacity="0.75"/>'
        )

    # puntos
    for p in puntos:
        if not (ver_x(p) and ver_y(p)):
            continue
        color = COLORES_NIVEL.get(p.nivel, "#666")
        r = 4.5
        if destacar and p.etiqueta in destacar:
            r = 7
            svg.append(
                f'<circle cx="{px(p.x):.1f}" cy="{py(p.y):.1f}" r="{r+4:.1f}" '
                f'fill="none" stroke="{color}" stroke-width="1.6" opacity="0.85"/>'
            )
        svg.append(
            f'<circle cx="{px(p.x):.1f}" cy="{py(p.y):.1f}" r="{r:.1f}" fill="{color}" '
            f'fill-opacity="0.82" stroke="#ffffff" stroke-width="0.8">'
            f'<title>{_escapar(p.etiqueta)}</title></circle>'
        )


def _leyenda(svg: list[str], niveles: list[str], x: float, y: float) -> None:
    svg.append(
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Segoe UI,Arial,sans-serif" '
        f'font-size="12" font-weight="600" fill="#1d1d1f">Nivel de optimizacion</text>'
    )
    yy = y + 18
    for niv in niveles:
        color = COLORES_NIVEL.get(niv, "#666")
        svg.append(
            f'<circle cx="{x+5:.1f}" cy="{yy-4:.1f}" r="4.5" fill="{color}" fill-opacity="0.85"/>'
        )
        svg.append(
            f'<text x="{x+18:.1f}" y="{yy:.1f}" font-family="Segoe UI,Arial,sans-serif" '
            f'font-size="11" fill="#3a3a3c">-{_escapar(niv)}</text>'
        )
        yy += 16


def renderizar_svg(
    puntos_sz: list[PuntoGrafica],
    puntos_sv: list[PuntoGrafica],
    frontera_sz: list[PuntoGrafica],
    *,
    titulo: str = "Frontera de estabilidad",
    subtitulo: str = "",
    destacar: set[str] | None = None,
) -> str:
    W, H = 1080, 1000
    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="Segoe UI,Arial,sans-serif">',
        f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
        f'<text x="46" y="40" font-family="Segoe UI,Arial,sans-serif" font-size="22" '
        f'font-weight="700" fill="#111113">{_escapar(titulo)}</text>',
    ]
    if subtitulo:
        svg.append(
            f'<text x="46" y="64" font-family="Segoe UI,Arial,sans-serif" font-size="12.5" '
            f'fill="#6b6b74">{_escapar(subtitulo)}</text>'
        )

    # panel 1
    _panel(
        svg,
        x0=110, y0=120, w=W - 190, h=360,
        puntos=puntos_sz,
        frontera=frontera_sz,
        titulo="(1) Tamano vs tiempo — frente de Pareto",
        etiqueta_x="Tamano del ejecutable (bytes, escala log)",
        etiqueta_y="Tiempo interno (ms, escala log)",
        formato_x=_formato_bytes,
        formato_y=lambda v: f"{v:.1f}",
        destacar=destacar,
    )

    # panel 2
    _panel(
        svg,
        x0=110, y0=580, w=W - 190, h=330,
        puntos=puntos_sv,
        frontera=[],
        titulo="(2) Tamano vs variabilidad (CV entre corridas)",
        etiqueta_x="Tamano del ejecutable (bytes, escala log)",
        etiqueta_y="Coeficiente de variacion del tiempo (CV)",
        formato_x=_formato_bytes,
        formato_y=lambda v: f"{v:.3f}",
        destacar=destacar,
    )

    niveles = sorted({p.nivel for p in puntos_sz + puntos_sv})
    _leyenda(svg, niveles, W - 190, 120)
    svg.append(
        f'<text x="{W-190:.1f}" y="330" font-family="Segoe UI,Arial,sans-serif" font-size="11" '
        f'fill="#6b6b74">Linea discontinua = frente de Pareto</text>'
    )
    svg.append(
        f'<text x="{W-190:.1f}" y="348" font-family="Segoe UI,Arial,sans-serif" font-size="11" '
        f'fill="#6b6b74">(minimiza tamano y tiempo)</text>'
    )
    svg.append("</svg>")
    return "\n".join(svg)
