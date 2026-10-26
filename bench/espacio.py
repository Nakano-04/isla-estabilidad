"""
espacio.py — Definicion del espacio de busqueda (variantes de compilacion).

El espacio es ORTOGONAL y declarativo: cada variante es la combinacion de un
nivel de cada eje. Esto hace que el "espacio de busqueda" sea auditable y
reproducible (a diferencia de generar mutaciones al azar).

Ejes
----
nivel_opt    : -O0 -O1 -O2 -O3 -Os -Oz       (B — optimizacion de codigo)
desenrollado : con / sin tablas de desenrollado  (C — estructura del binario)
enlace       : defecto / gc_secciones / lto_thin / lto_thin_icf  (B+C)
depuracion   : sin_info / con_info            (C — metadatos)

Eje post-proceso (fuera del grid, aplicado a cada artefacto):
                conservar / llvm-strip --strip-all   (C — formato)

Notas metodologicas (ver docs/PROTOCOLO.md)
-------------------------------------------
* CRT DINAMICO. El driver GNU de clang ignora `-MD` sobre el target MSVC y
  enlaza siempre `libcmt` (estatico), que aporta ~145 KB constantes. Con ese
  fondo, el efecto de -Os/-Oz sobre el codigo propio queda aplastado (1 % en
  vez de ~30 %). Por eso se fuerza el CRT dinamico explicitamente:
  /NODEFAULTLIB:libcmt + /DEFAULTLIB:msvcrt,ucrt,vcruntime.
  Medido: 159 744 B -> 14 848 B con el mismo codigo.
* /Brepro en lld-link: sin esto el PE lleva marca de tiempo y S seria ruido
  entre dos compilaciones identicas.
* -ffile-prefix-map: elimina la ruta absoluta del directorio de compilacion.
* La construccion es en DOS PASOS (compile -> .obj, link -> .exe) para poder
  medir por separado el codigo propio (.obj) y el artefacto final (.exe).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Ejes -----------------------------------------------------------------
NIVELES_OPT = {
    "O0": ["-O0"],
    "O1": ["-O1"],
    "O2": ["-O2"],
    "O3": ["-O3"],
    "Os": ["-Os"],
    "Oz": ["-Oz"],
}

DESENROLLADO = {
    "con": ([], []),
    "sin": (
        ["-fno-unwind-tables", "-fno-asynchronous-unwind-tables"],
        [],
    ),
}

ENLACE = {
    "defecto": ([], []),
    # `-ffunction-sections` en target COFF hace que clang emita cada funcion
    # en su propia seccion COMDAT. Es la palanca REAL de plegado de codigo
    # identico en PE: la semántica de seleccion COMDAT del formato deduplica
    # secciones identicas por su cuenta, sin necesidad de ninguna opcion ICF.
    "func_secciones": (
        ["-ffunction-sections", "-fdata-sections"],
        [],
    ),
    "gc_secciones": (
        ["-ffunction-sections", "-fdata-sections"],
        # /OPT:REF es la sintaxis valida de lld-link (--gc-sections es de
        # lld-ELF y la ignora). Control informativo: lld-link hace GC de
        # secciones muertas POR DEFECTO, asi que /OPT:REF no debe anadir nada.
        ["-Wl,/OPT:REF"],
    ),
    "lto_thin": (["-flto=thin"], ["-flto=thin"]),
    # Control negativo: ICF correcto (/OPT:ICF es la sintaxis de lld-link;
    # --icf=all es de lld-ELF y lld-link la IGNORA con un warning) pero SIN
    # COMDAT. Sirve para demostrar que el plegado no lo produce ICF.
    "lto_thin_icf_sin_comdat": (
        ["-flto=thin"],
        ["-flto=thin", "-Wl,/OPT:ICF"],
    ),
    # Combinacion completa: COMDAT (precondicion) + ICF + GC.
    "lto_thin_icf": (
        ["-flto=thin", "-ffunction-sections", "-fdata-sections"],
        ["-flto=thin", "-Wl,/OPT:ICF", "-Wl,--gc-sections"],
    ),
}

DEPURACION = {
    "sin_info": ([], []),
    # En PE la informacion de depuracion no va dentro del ejecutable sino a un
    # .pdb externo, con un directorio CodeView en la cabecera. Por eso el coste
    # en el .obj es graduado (line tables < completa) pero en el .exe satura.
    "line_tables": (["-gline-tables-only"], []),
    "con_info": (["-g"], []),
}

POSTPROCESO = {
    "conservar": [],
    # En ELF esto elimina la tabla de simbolos. En PE/COFF los ejecutables NO
    # llevan tabla de simbolos: llvm-strip --strip-all es un no-op. Se mantiene
    # el eje para documentar ese resultado negativo en vez de ocultarlo.
    "strip": ["--strip-all"],
}


@dataclass(frozen=True)
class Variante:
    id: str
    nivel_opt: str
    desenrollado: str
    enlace: str
    depuracion: str
    flags_compilacion: list[str] = field(default_factory=list)
    flags_enlace: list[str] = field(default_factory=list)

    @property
    def etiqueta(self) -> str:
        return (
            f"{self.nivel_opt} | {self.desenrollado} | {self.enlace} | {self.depuracion}"
        )

    def como_dict(self) -> dict:
        return {
            "id": self.id,
            "nivel_opt": self.nivel_opt,
            "desenrollado": self.desenrollado,
            "enlace": self.enlace,
            "depuracion": self.depuracion,
            "flags_compilacion": list(self.flags_compilacion),
            "flags_enlace": list(self.flags_enlace),
            "etiqueta": self.etiqueta,
        }


def _slug(texto: str) -> str:
    return texto.replace("/", "-").replace(" ", "_")


def generar_variantes(
    niveles: list[str],
    desenrollados: list[str],
    enlaces: list[str],
    depuraciones: list[str],
    base_compilacion: list[str],
    base_enlace: list[str],
) -> list[Variante]:
    """Producto cartesiano de los ejes declarados."""
    variantes: list[Variante] = []
    for n in niveles:
        for d in desenrollados:
            for e in enlaces:
                for p in depuraciones:
                    fc, fe = DESENROLLADO[d]
                    ec, ee = ENLACE[e]
                    dc, _ = DEPURACION[p]
                    variantes.append(
                        Variante(
                            id="__".join([_slug(n), _slug(d), _slug(e), _slug(p)]),
                            nivel_opt=n,
                            desenrollado=d,
                            enlace=e,
                            depuracion=p,
                            flags_compilacion=list(base_compilacion)
                            + NIVELES_OPT[n]
                            + fc
                            + ec
                            + dc,
                            flags_enlace=list(base_enlace) + ee,
                        )
                    )
    return variantes


def flags_base_compilacion(objetivo: str, raiz: Path) -> list[str]:
    return [
        f"--target={objetivo}",
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-Werror",                     # que ninguna variante compile con avisos
        f"-ffile-prefix-map={raiz}=.",  # ruta -> ruta relativa (determinismo)
    ]


def flags_base_enlace() -> list[str]:
    return [
        "-fuse-ld=lld",
        "-Wl,/Brepro",                 # PE sin marcas de tiempo (determinismo)
        # CRT dinamico explicito (ver nota metodologica de este modulo)
        "-Wl,/NODEFAULTLIB:libcmt",
        "-Wl,/DEFAULTLIB:msvcrt",
        "-Wl,/DEFAULTLIB:ucrt",
        "-Wl,/DEFAULTLIB:vcruntime",
    ]
