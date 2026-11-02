"""Revisa la web generada ejecutando el comprobador dentro de la caja.

El programa de comprobación no corre en este proceso: se manda al sandbox como
texto y se ejecuta allí, sin red y sin acceso a `/home`. Así el informe sirve
de prueba de que el agente *ejecuta* código, no solo escribe ficheros.

El código del comprobador vive en `revisor.py`, un programa independiente: el
mismo fichero se lanza en la consola, dentro del sandbox y (con Pyodide) en el
navegador. Una sola versión, tres sitios donde corre.

    from sandbox import Sandbox
    from validador import validar
    informe = validar(Sandbox(), html)      # {"ok": True, "problemas": [], ...}
"""

from __future__ import annotations

import json
from pathlib import Path

from sandbox import Resultado, Sandbox

__all__ = ["validar", "revisar", "PROGRAMA", "RUTA_PROGRAMA"]

RUTA_PROGRAMA = Path(__file__).resolve().parent / "revisor.py"

# El programa que se ejecuta dentro de la caja (fuente única: revisor.py).
PROGRAMA = RUTA_PROGRAMA.read_text(encoding="utf-8")


def validar(caja: Sandbox, html: str) -> dict:
    """Pasa la revisión al HTML dentro del sandbox y devuelve el informe."""
    resultado: Resultado = caja.ejecutar(PROGRAMA, {"sitio/index.html": html})
    return revisar(resultado)


def revisar(resultado: Resultado) -> dict:
    """Interpreta la salida del comprobador (o el fallo del propio sandbox)."""
    if resultado.agotado:
        return {
            "ok": False,
            "problemas": [f"la revisión tardó más de {resultado.segundos:.1f} s y se canceló"],
            "ejecucion": resultado.como_diccionario(),
        }
    linea = (resultado.salida or "").strip().splitlines()
    if not linea:
        return {
            "ok": False,
            "problemas": ["el comprobador no devolvió nada"],
            "errores_sandbox": resultado.errores[-800:],
            "ejecucion": resultado.como_diccionario(),
        }
    try:
        informe = json.loads(linea[-1])
    except json.JSONDecodeError:
        return {
            "ok": False,
            "problemas": ["la salida del comprobador no es JSON"],
            "salida": resultado.salida[-800:],
            "ejecucion": resultado.como_diccionario(),
        }
    informe["ejecucion"] = resultado.como_diccionario()
    return informe
