"""
medir.py — Medicion de tiempo y verificacion de la repetibilidad.

Decisiones metodologicas (y por que):

1. TIEMPO INTERNO + TIEMPO EXTERNO.
   En Windows el arranque de un proceso (CreateProcess + carga de DLLs) cuesta
   10-40 ms, del mismo orden que la carga de trabajo. Medir solo tiempo de
   pared mezcla el coste del sistema operativo con el del programa. Por eso el
   binario reporta su propio tiempo (QueryPerformanceCounter alrededor de la
   region de computo) y el arnes mide los dos. El analisis principal usa el
   tiempo INTERNO; el externo se reporta como coste real de despliegue.

2. INTERCALADO (round-robin).
   Todas las variantes se ejecutan en el mismo orden ciclico: no "todas las
   repeticiones de A, luego todas las de B". Si la maquina se calienta o
   aparece un proceso competidor a mitad del ensayo, el sesgo se reparte
   equitativamente entre variantes en lugar de concentrarse en una. El
   diagnostico `deriva_pct` cuantifica ese efecto.

3. DESCARTAR EL ARRANQUE.
   Las primeras ejecuciones paginan el binario a disco y calientan la cache de
   codigo. Se ejecuta una pasada de calentamiento que se descarta.

4. VERIFICAR LA SALIDA EN CADA CORRIDA.
   Un binario puede ser rapido y aun asi no ser determinista. Cada corrida
   comprueba que el digest sigue coincidiendo con el oraculo: si no, la
   variante queda marcada como inestable aunque su tiempo sea bueno.

5. AFINIDAD DE CPU (opcional).
   Fijar la mascara de afinidad en el proceso padre ANTES de lanzar a los
   hijos (que la heredan) reduce la migracion entre nucleos. Se ofrece como
   opcion porque reduce el paralelismo real disponible.

6. ROTACION DEL ORDEN (anti-sesgo posicional).
   Dentro de cada ronda el orden de los candidatos rota. Sin esto, una
   degradacion monotona de la maquina penaliza siempre a las mismas
   variantes, que ocupan siempre la misma posicion.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import toolchain as tc_mod
from .construir import Artefacto

RE_METRICAS = re.compile(r"(\w+)=([-\d.]+)")


@dataclass
class Corrida:
    artefacto_id: str
    ronda: int
    t_externo_ms: float
    t_interno_ms: float
    mem_pico_kb: float
    digest_ok: bool


@dataclass
class Medida:
    artefacto_id: str
    etiqueta: str
    postproceso: str
    variante_id: str
    t_externo_ms: list[float] = field(default_factory=list)
    t_interno_ms: list[float] = field(default_factory=list)
    mem_pico_kb: list[float] = field(default_factory=list)
    digests_ok: int = 0
    digests_total: int = 0
    fallos: list[str] = field(default_factory=list)

    @property
    def estable(self) -> bool:
        return self.digests_total > 0 and self.digests_ok == self.digests_total


# ----------------------------------------------------------------------
# Afinidad de CPU
# ----------------------------------------------------------------------

def fijar_afinidad(nucleo: int = 0) -> bool:
    """Fija la afinidad del proceso actual (y por herencia, de los hijos).

    Devuelve True si se aplico. En sistemas no-Windows o sin permisos se
    ignora silenciosamente: es una mejora opcional, no un requisito.
    """
    if os.name != "nt":
        try:
            os.sched_setaffinity(0, {nucleo})
            return True
        except (OSError, AttributeError):
            return False
    try:
        import ctypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        mascara = 1 << nucleo
        k32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        k32.SetProcessAffinityMask.restype = ctypes.c_int
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        return bool(k32.SetProcessAffinityMask(k32.GetCurrentProcess(), mascara))
    except Exception:
        return False


# ----------------------------------------------------------------------
# Ejecucion medida
# ----------------------------------------------------------------------

def _ejecutar_una(tc: tc_mod.Toolchain, exe: Path, escala: int, timeout: float):
    inicio = time.perf_counter_ns()
    proc = subprocess.run(
        [str(exe), "--escala", str(escala)],
        capture_output=True,
        env=tc.entorno,
        timeout=timeout,
    )
    fin = time.perf_counter_ns()
    t_ext = (fin - inicio) / 1e6
    salida = tc_mod.decodificar(proc.stdout)
    m = re.search(r"^digest=([0-9a-f]+)\s*$", salida, re.MULTILINE)
    digest = m.group(1) if m else ""
    metricas = {k: float(v) for k, v in RE_METRICAS.findall(tc_mod.decodificar(proc.stderr))}
    return (
        t_ext,
        metricas.get("t_interno_ms", float("nan")),
        metricas.get("mem_pico_kb", float("nan")),
        digest,
        proc.returncode,
    )


def medir_lote(
    tc: tc_mod.Toolchain,
    artefactos: list[Artefacto],
    digest_esperado: str,
    *,
    escala: int = 1,
    repeticiones: int = 25,
    calentamiento: int = 1,
    timeout: float = 600.0,
    progreso=None,
) -> dict[str, Medida]:
    """Mide un conjunto de artefactos de forma intercalada."""
    medidas: dict[str, Medida] = {}
    for art in artefactos:
        aid = f"{art.variante_id}::{art.postproceso}"
        medidas[aid] = Medida(
            artefacto_id=aid,
            etiqueta=art.etiqueta,
            postproceso=art.postproceso,
            variante_id=art.variante_id,
        )

    validos = [a for a in artefactos if a.valido]

    # --- calentamiento (se descarta) ---
    for _ in range(max(0, calentamiento)):
        for art in validos:
            _ejecutar_una(tc, art.ruta, escala, timeout)

    # --- medicion intercalada ---
    # El orden dentro de cada ronda ROTA. Sin rotacion, cada variante ocupa
    # siempre la misma posicion dentro de la ronda; si la maquina se degrada
    # de forma monotonica a lo largo del ensayo, esa posicionua queda
    # sistemáticamente penalizada. Rotando, cada variante recorre todas las
    # posiciones y el sesgo posicional se promedia a cero.
    total = len(validos) * repeticiones
    hecho = 0
    for ronda in range(repeticiones):
        desplazamiento = ronda % max(1, len(validos))
        orden = validos[desplazamiento:] + validos[:desplazamiento]
        for art in orden:
            t_ext, t_int, mem, digest, rc = _ejecutar_una(
                tc, art.ruta, escala, timeout
            )
            m = medidas[f"{art.variante_id}::{art.postproceso}"]
            m.t_externo_ms.append(t_ext)
            m.t_interno_ms.append(t_int)
            m.mem_pico_kb.append(mem)
            m.digests_total += 1
            if digest and digest == digest_esperado and rc == 0:
                m.digests_ok += 1
            else:
                m.fallos.append(
                    f"ronda {ronda}: rc={rc} digest={digest or '<ausente>'}"
                )
            hecho += 1
            if progreso:
                progreso(hecho, total)

    return medidas
