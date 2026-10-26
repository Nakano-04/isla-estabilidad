"""
toolchain.py — Descubrimiento del toolchain y ejecución de procesos.

Responsabilidades:
  * localizar clang + herramientas LLVM (size/strip/objcopy/readobj)
  * capturar el entorno de vcvars64 (INCLUDE/LIB/LIBPATH/PATH) en Windows
  * centralizar la invocación de procesos con entorno y captura de E/S

El objetivo es que el experimento sea REPRODUCIBLE: el mismo código, en la
misma máquina, debe producir el mismo binario bit a bit.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Rutas de Visual Studio conocidas en esta máquina (se pueden sobrescribir
# con la variable de entorno ISLA_VS_ROOT).
VS_ROOTS_CANDIDATOS = [
    r"C:\Program Files\Microsoft Visual Studio\18\Community",
    r"C:\Program Files\Microsoft Visual Studio\2022\Community",
    r"C:\Program Files\Microsoft Visual Studio\2022\Professional",
    r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise",
]


class ErrorToolchain(RuntimeError):
    """Falla al localizar o preparar la cadena de herramientas."""


@dataclass
class Toolchain:
    clang: str
    lld_link: str
    llvm_size: str
    llvm_strip: str
    llvm_objcopy: str
    llvm_readobj: str
    objetivo: str
    entorno: dict[str, str] = field(default_factory=dict)
    version: str = ""

    def describe(self) -> dict:
        return {
            "clang": self.clang,
            "lld_link": self.lld_link,
            "llvm_size": self.llvm_size,
            "llvm_strip": self.llvm_strip,
            "objetivo": self.objetivo,
            "version": self.version,
        }


# ----------------------------------------------------------------------
# Entorno
# ----------------------------------------------------------------------

def _parsear_entorno_set(salida: str) -> dict[str, str]:
    """Parsea la salida de `cmd /c "vcvars64.bat && set"`.

    Ignora las variables pseudo (las que empiezan por '=') y las que
    contienen caracteres no imprimibles.

    Nota: en Windows los nombres de variables NO distinguen mayusculas, pero
    `set` las imprime con el caso con el que fueron almacenadas (p.ej. `Path`,
    `ProgramFiles`). Se normalizan a mayusculas para poder compararlas con
    `os.environ`, que tambien las normaliza.
    """
    env: dict[str, str] = {}
    for linea in salida.splitlines():
        if "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        if not clave or clave.startswith("="):
            continue
        if clave != clave.strip():
            continue
        if os.name == "nt":
            clave = clave.upper()
        env[clave] = valor.rstrip("\r")
    return env


def capturar_entorno_vcvars() -> dict[str, str]:
    """Devuelve el entorno de compilación de VS (Windows).

    En Linux/macOS devuelve una copia del entorno actual.
    """
    if os.name != "nt":
        return dict(os.environ)

    raices: list[str] = []
    if os.environ.get("ISLA_VS_ROOT"):
        raices.append(os.environ["ISLA_VS_ROOT"])
    raices.extend(VS_ROOTS_CANDIDATOS)

    for raiz in raices:
        bat = Path(raiz) / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
        if not bat.exists():
            continue
        # cmd.exe no parses bien las comillas anidadas en `cmd /c "..."`, asi que
        # se delega en un .bat temporal.
        with tempfile.TemporaryDirectory(prefix="isla_vcvars_") as tmp:
            guion = Path(tmp) / "capturar.bat"
            guion.write_text(
                "@echo off\r\n"
                f'call "{bat}" >nul 2>&1\r\n'
                "set\r\n",
                encoding="ascii",
            )
            try:
                proc = subprocess.run(
                    ["cmd", "/c", str(guion)],
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
        env = _parsear_entorno_set(proc.stdout)
        if env.get("PATH"):
            return env
    return dict(os.environ)


def _combinar_entorno(extra: dict[str, str]) -> dict[str, str]:
    env = dict(os.environ)
    for k, v in extra.items():
        env[k] = v
    return env


# ----------------------------------------------------------------------
# Ejecución de procesos
# ----------------------------------------------------------------------

def ejecutar(
    cmd: list[str],
    *,
    entorno: dict[str, str] | None = None,
    cwd: Path | None = None,
    timeout: float | None = 300.0,
    entrada: bytes | None = None,
) -> subprocess.CompletedProcess:
    """Ejecuta un comando capturando stdout/stderr en binario."""
    env = entorno if entorno is not None else dict(os.environ)
    return subprocess.run(
        cmd,
        capture_output=True,
        input=entrada,
        cwd=str(cwd) if cwd else None,
        env=env,
        timeout=timeout,
    )


def decodificar(datos: bytes | None) -> str:
    if not datos:
        return ""
    return datos.decode("utf-8", errors="replace")


# ----------------------------------------------------------------------
# Descubrimiento
# ----------------------------------------------------------------------

def _primer_existente(nombres: list[str], path_env: str) -> str | None:
    for n in nombres:
        p = shutil.which(n, path=path_env)
        if p:
            return p
    return None


def descubrir_toolchain(entorno_extra: dict[str, str] | None = None) -> Toolchain:
    """Localiza clang y las herramientas LLVM necesarias."""
    extra = entorno_extra if entorno_extra is not None else capturar_entorno_vcvars()
    env = _combinar_entorno(extra)
    path_env = env.get("PATH", os.environ.get("PATH", ""))

    clang = _primer_existente(["clang"], path_env)
    if clang is None:
        raise ErrorToolchain(
            "No se encontro 'clang' en el PATH. En Windows, instala LLVM o "
            "expone ISLA_VS_ROOT apuntando a la instalacion de Visual Studio."
        )

    def _opt(nombre: str) -> str:
        p = shutil.which(nombre, path=path_env)
        if p is None:
            raise ErrorToolchain(f"Falta la herramienta LLVM requerida: {nombre}")
        return p

    objetivo = "x86_64-pc-windows-msvc" if os.name == "nt" else "x86_64-unknown-linux-gnu"

    proc = ejecutar([clang, "--version"], entorno=env, timeout=60)
    version = decodificar(proc.stdout).splitlines()[0] if proc.stdout else "desconocida"

    return Toolchain(
        clang=clang,
        lld_link=_opt("lld-link") if os.name == "nt" else _opt("ld.lld"),
        llvm_size=_opt("llvm-size"),
        llvm_strip=_opt("llvm-strip"),
        llvm_objcopy=_opt("llvm-objcopy"),
        llvm_readobj=_opt("llvm-readobj"),
        objetivo=objetivo,
        entorno=env,
        version=version,
    )


# ----------------------------------------------------------------------
# Utilidades de E/S de resultados
# ----------------------------------------------------------------------

def escribir_json(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")


def leer_json(ruta: Path):
    return json.loads(ruta.read_text(encoding="utf-8"))


def escribir_csv(ruta: Path, filas: list[dict], columnas: list[str]) -> None:
    import csv

    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columnas)
        w.writeheader()
        for f in filas:
            w.writerow({c: f.get(c, "") for c in columnas})


def registro_entorno(tc: Toolchain) -> dict:
    """Metadatos del entorno, para archivarlos junto a los resultados."""
    import platform

    info = {
        "fecha_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(timespec="seconds"),
        "hostname": platform.node(),
        "sistema": platform.platform(),
        "procesador": platform.processor(),
        "python": sys.version.split()[0],
        "toolchain": tc.describe(),
    }
    try:
        import os as _os

        info["nucleos_logicos"] = _os.cpu_count()
    except Exception:
        pass
    return info
