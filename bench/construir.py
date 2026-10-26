"""
construir.py — Construccion de las variantes y medicion de su tamano.

Para cada variante:
  1. compila `src/*.c` -> .obj (un .obj por unidad de traduccion)
  2. mide el .obj con llvm-size  -> S_codigo_propio (atribucion pura)
  3. enlaza los .obj -> .exe      -> S_archivo y S_codigo (text+data del exe)
  4. produce la variante "strip" con `llvm-strip --strip-all`
  5. ejecuta una vez y captura el digest (stdout) y las metricas (stderr)

El digest se compara contra el oraculo: el build de referencia a -O0 y la
implementacion independiente en Python (`src/referencia.py`). Una variante que
no reproduce el digest EXACTO se marca como NO CORRECTA y queda fuera de la
frontera de Pareto, por mas pequena que sea.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import toolchain as tc_mod
from .espacio import POSTPROCESO, Variante

RE_METRICAS = re.compile(r"(\w+)=([-\d.]+)")

FUENTES = ["carga.c", "aux.c"]

# --- CONTROL CRITICO: el toolchain no puede avisar y que se le ignore ---
#
# Un enlazador que recibe una opcion que no reconoce la IGNORA en silencio y
# sigue. El resultado experimental es entonces un nulo plausible pero falso:
# el benchmark "ICF no ahorra nada" era en realidad "el flag nunca se aplico".
#
# Se detectan los avisos que invalidan la medicion y se convierte la variante
# en NO VALIDA, para que no contamine la frontera de Pareto. Los avisos de
# compilacion ya estan cubiertos por -Werror; aqui se cubren los del
# ENLAZADOR, que son los que slipped through.
RE_AVISOS_CRITICOS = re.compile(
    r"(ignoring unknown argument"
    r"|unknown argument"
    r"|ignoring unknown option"
    r"|unknown option"
    r"|ignoring /link"
    r"|warning:.*\bignor(?:ed|es)\b)",
    re.IGNORECASE,
)


def _avisos_criticos(texto: str) -> list[str]:
    return [m.group(0).strip() for m in RE_AVISOS_CRITICOS.finditer(texto)]


@dataclass
class Artefacto:
    """Un binario concreto con sus medidas de tamano."""

    variante_id: str
    etiqueta: str
    postproceso: str
    ruta: Path
    tamano_bytes: int          # S_archivo
    text: int                 # seccion .text del ejecutable
    data: int                 # seccion .data del ejecutable
    bss: int
    obj_bytes: int            # S_codigo_propio: tamano total de los .obj
    obj_text: int | None       # text+data de los .obj (codigo propio puro).
                               # None si el .obj es bitcode (LTO): no medible.
    sha256: str
    tamano_total_bytes: int = 0   # ejecutable + .pdb + .ilk: la huella real
    valido: bool = True
    error: str = ""
    digest: str = ""
    t_interno_ms: float = 0.0
    mem_pico_kb: float = 0.0
    meta: dict = field(default_factory=dict)

    @property
    def codigo_bytes(self) -> int:
        """Codigo residente en la imagen (text+data del ejecutable)."""
        return self.text + self.data

    def como_dict(self) -> dict:
        return {
            "variante_id": self.variante_id,
            "etiqueta": self.etiqueta,
            "postproceso": self.postproceso,
            "tamano_bytes": self.tamano_bytes,
            "text": self.text,
            "data": self.data,
            "bss": self.bss,
            "codigo_bytes": self.codigo_bytes,
            "obj_bytes": self.obj_bytes,
            "obj_text": self.obj_text,
            "sha256": self.sha256,
            "tamano_total_bytes": self.tamano_total_bytes,
            "valido": self.valido,
            "error": self.error,
            "digest": self.digest,
            "t_interno_ms": round(self.t_interno_ms, 4),
            "mem_pico_kb": round(self.mem_pico_kb, 1),
            "meta": self.meta,
        }


def _sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _secciones(tc: tc_mod.Toolchain, ruta: Path) -> tuple[int, int, int]:
    """(text, data, bss) usando llvm-size. (0,0,0) si no se puede leer."""
    proc = tc_mod.ejecutar([tc.llvm_size, str(ruta)], entorno=tc.entorno, timeout=60)
    if proc.returncode != 0:
        return (0, 0, 0)
    lineas = tc_mod.decodificar(proc.stdout).strip().splitlines()
    if not lineas:
        return (0, 0, 0)
    campos = lineas[-1].split()
    if len(campos) < 3:
        return (0, 0, 0)
    try:
        return (int(campos[0]), int(campos[1]), int(campos[2]))
    except ValueError:
        return (0, 0, 0)


def _huella_total(exe: Path) -> int:
    """Bytes del artefacto desplegable: ejecutable + .pdb + .ilk asociados.

    En PE la informacion de depuracion vive en un .pdb externo, asi que el
    tamano del .exe por solo NO es la huella que se despliega en disco.
    """
    total = exe.stat().st_size
    for patron in ("*.pdb", "*.ilk"):
        for extra in exe.parent.glob(patron):
            if extra.name.lower().startswith(exe.stem.lower()):
                total += extra.stat().st_size
    return total


def _parsear_stderr(texto: str) -> dict:
    return {k: float(v) for k, v in RE_METRICAS.findall(texto)}


def construir_variante(
    tc: tc_mod.Toolchain,
    variante: Variante,
    raiz: Path,
    *,
    escala: int = 1,
    verificar: bool = True,
    timeout: float = 600.0,
) -> list[Artefacto]:
    """Compila y enlaza una variante; devuelve sus artefactos (raw y strip)."""
    dir_out = raiz / "build" / variante.id
    dir_out.mkdir(parents=True, exist_ok=True)
    exe = dir_out / "carga.exe"

    # --- paso 1: compilar cada TU a .obj ---
    objetos: list[Path] = []
    for fuente in FUENTES:
        obj = dir_out / (fuente.replace(".c", ".obj"))
        cmd = [
            tc.clang,
            *variante.flags_compilacion,
            "-c",
            str(raiz / "src" / fuente),
            "-o",
            str(obj),
        ]
        proc = tc_mod.ejecutar(cmd, entorno=tc.entorno, cwd=raiz, timeout=timeout)
        if proc.returncode != 0:
            err = tc_mod.decodificar(proc.stderr)[-2000:]
            return [
                Artefacto(
                    variante_id=variante.id,
                    etiqueta=variante.etiqueta,
                    postproceso="conservar",
                    ruta=exe,
                    tamano_bytes=0,
                    text=0,
                    data=0,
                    bss=0,
                    obj_bytes=0,
                    obj_text=None,
                    sha256="",
                    valido=False,
                    error=f"fallo de compilacion de {fuente}: {err}",
                    meta={"flags_compilacion": variante.flags_compilacion},
                )
            ]
        objetos.append(obj)

    obj_bytes = sum(o.stat().st_size for o in objetos)
    # El .obj de una variante con LTO es BITCODE, no un objeto: llvm-size no
    # puede medirlo. En ese caso obj_text queda como None (no como 0, que
    # seria falsamente "el mas pequeno").
    secciones_objs = [_secciones(tc, o) for o in objetos]
    obj_es_bitcode = any(s == (0, 0, 0) for s in secciones_objs)
    obj_text = None if obj_es_bitcode else sum(s[0] + s[1] for s in secciones_objs)

    # --- paso 2: enlazar ---
    cmd_link = [
        tc.clang,
        *variante.flags_compilacion,
        *variante.flags_enlace,
        *[str(o) for o in objetos],
        "-o",
        str(exe),
    ]
    proc = tc_mod.ejecutar(cmd_link, entorno=tc.entorno, cwd=raiz, timeout=timeout)
    if proc.returncode != 0:
        err = tc_mod.decodificar(proc.stderr)[-2000:]
        return [
            Artefacto(
                variante_id=variante.id,
                etiqueta=variante.etiqueta,
                postproceso="conservar",
                ruta=exe,
                tamano_bytes=0,
                text=0,
                data=0,
                bss=0,
                obj_bytes=obj_bytes,
                obj_text=obj_text,
                sha256="",
                valido=False,
                error=f"fallo de enlazado: {err}",
                meta={"flags_compilacion": variante.flags_compilacion,
                      "flags_enlace": variante.flags_enlace},
            )
        ]

    # --- CONTROL: el enlazador no puede ignorar opciones en silencio ---
    avisos = _avisos_criticos(tc_mod.decodificar(proc.stderr))
    if avisos:
        return [
            Artefacto(
                variante_id=variante.id,
                etiqueta=variante.etiqueta,
                postproceso="conservar",
                ruta=exe,
                tamano_bytes=0,
                text=0,
                data=0,
                bss=0,
                obj_bytes=obj_bytes,
                obj_text=obj_text,
                sha256="",
                valido=False,
                error=(
                    "el enlazador emitio avisos criticos (posiblemente opciones "
                    f"ignoradas): {avisos[:4]}. La variante se descarta porque "
                    "el resultado medido no corresponde a la configuracion "
                    "declarada."
                ),
                meta={"flags_compilacion": variante.flags_compilacion,
                      "flags_enlace": variante.flags_enlace,
                      "avisos": avisos},
            )
        ]

    artefactos: list[Artefacto] = []
    for post, flags_post in (("conservar", []), ("strip", POSTPROCESO["strip"])):
        if post == "strip":
            proc_s = tc_mod.ejecutar(
                [tc.llvm_strip, *flags_post, str(exe), "-o", str(dir_out / "carga.strip.exe")],
                entorno=tc.entorno,
                timeout=timeout,
            )
            if proc_s.returncode != 0:
                continue
        ruta = exe if post == "conservar" else dir_out / "carga.strip.exe"
        artefactos.append(
            Artefacto(
                variante_id=variante.id,
                etiqueta=variante.etiqueta,
                postproceso=post,
                ruta=ruta,
                tamano_bytes=ruta.stat().st_size,
                tamano_total_bytes=_huella_total(ruta),
                text=0,
                data=0,
                bss=0,
                obj_bytes=obj_bytes,
                obj_text=obj_text,
                sha256=_sha256(ruta),
                meta={
                    "flags_compilacion": variante.flags_compilacion,
                    "flags_enlace": variante.flags_enlace,
                },
            )
        )

    # --- secciones del ejecutable y verificacion funcional ---
    for art in artefactos:
        art.text, art.data, art.bss = _secciones(tc, art.ruta)
        if verificar:
            digest, t_int, mem_kb, err = ejecutar_digest(tc, art.ruta, escala, timeout)
            art.digest = digest
            art.t_interno_ms = t_int
            art.mem_pico_kb = mem_kb
            if err:
                art.valido = False
                art.error = err

    return artefactos


def ejecutar_digest(
    tc: tc_mod.Toolchain, exe: Path, escala: int, timeout: float = 600.0
) -> tuple[str, float, float, str]:
    """Ejecuta el binario una vez. Devuelve (digest, t_interno_ms, mem_kb, error)."""
    proc = tc_mod.ejecutar(
        [str(exe), "--escala", str(escala)], entorno=tc.entorno, timeout=timeout
    )
    if proc.returncode != 0:
        return ("", 0.0, 0.0, f"ejecucion fallo rc={proc.returncode}")
    salida = tc_mod.decodificar(proc.stdout)
    m = re.search(r"^digest=([0-9a-f]+)\s*$", salida, re.MULTILINE)
    digest = m.group(1) if m else ""
    metricas = _parsear_stderr(tc_mod.decodificar(proc.stderr))
    return (
        digest,
        float(metricas.get("t_interno_ms", 0.0)),
        float(metricas.get("mem_pico_kb", 0.0)),
        "" if digest else "digest ausente en la salida",
    )


def calcular_oraculo(
    tc: tc_mod.Toolchain, raiz: Path, *, escala: int = 1
) -> tuple[str, str]:
    """Construye el oraculo de correccion.

    Devuelve (digest_referencia, informe). El digest debe coincidir entre:
      (a) el build C de referencia a -O0 (semantica ingenua, sin optimizacion)
      (b) la reimplementacion independiente en Python

    Si ambos coinciden, la correccion de las variantes se evalua contra un
    oraculo que no depende de una unica linea base de codigo.
    """
    dir_ref = raiz / "build" / "_referencia"
    dir_ref.mkdir(parents=True, exist_ok=True)
    exe = dir_ref / "carga_ref.exe"

    fc = [
        f"--target={tc.objetivo}",
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-O0",
        f"-ffile-prefix-map={raiz}=.",
    ]
    fe = [
        "-fuse-ld=lld",
        "-Wl,/Brepro",
        "-Wl,/NODEFAULTLIB:libcmt",
        "-Wl,/DEFAULTLIB:msvcrt",
        "-Wl,/DEFAULTLIB:ucrt",
        "-Wl,/DEFAULTLIB:vcruntime",
    ]
    objetos = []
    for fuente in FUENTES:
        obj = dir_ref / fuente.replace(".c", ".obj")
        p = tc_mod.ejecutar(
            [tc.clang, *fc, "-c", str(raiz / "src" / fuente), "-o", str(obj)],
            entorno=tc.entorno,
            cwd=raiz,
            timeout=600,
        )
        if p.returncode != 0:
            return ("", f"fallo al compilar la referencia: {tc_mod.decodificar(p.stderr)[-800:]}")
        objetos.append(obj)

    p = tc_mod.ejecutar(
        [tc.clang, *fc, *fe, *[str(o) for o in objetos], "-o", str(exe)],
        entorno=tc.entorno,
        cwd=raiz,
        timeout=600,
    )
    if p.returncode != 0:
        return ("", f"fallo al enlazar la referencia: {tc_mod.decodificar(p.stderr)[-800:]}")

    digest_c, _, _, err_c = ejecutar_digest(tc, exe, escala)
    if err_c:
        return ("", f"la referencia C no ejecuta: {err_c}")

    # --- oraculo independiente en Python ---
    ref_py = raiz / "src" / "referencia.py"
    proc_py = tc_mod.ejecutar(
        ["python", str(ref_py), "--escala", str(escala)],
        entorno=tc.entorno,
        cwd=raiz,
        timeout=3600,
    )
    if proc_py.returncode != 0:
        return (digest_c, f"la referencia Python fallo: {tc_mod.decodificar(proc_py.stderr)[-800:]}")
    m = re.search(
        r"^digest=([0-9a-f]+)\s*$", tc_mod.decodificar(proc_py.stdout), re.MULTILINE
    )
    digest_py = m.group(1) if m else ""

    if not digest_py:
        return (digest_c, "la referencia Python no produjo digest")
    if digest_py != digest_c:
        return (
            "",
            "DISCREPANCIA entre la referencia C (-O0) y la reimplementacion "
            f"independiente en Python: {digest_c} != {digest_py}. "
            "El oraculo no es fiable; revisar la especificacion antes de medir.",
        )

    informe = (
        "Oraculo validado por doble implementacion: C(-O0) y Python coinciden "
        f"en digest={digest_c}."
    )
    return (digest_c, informe)
