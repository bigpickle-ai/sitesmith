"""Agente que hace la web de un negocio y la comprueba ejecutando código.

Es la versión de consola del agente del hackatón: lee los datos del negocio,
escribe la web con `sitio.py` y después *ejecuta* un comprobador dentro de una
caja aislada (sin red, sin acceso a `/home`). Deja un `informe.json` con todo
lo que ha hecho, paso a paso, para poder demostrar el resultado.

Uso:
    python3 agente.py negocios/bar-ejemplo.json
    python3 agente.py negocios/bar-ejemplo.json -o salidas/bar-ejemplo
    python3 agente.py negocios/bar-ejemplo.json --json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ))

import sitio  # noqa: E402  (el generador que ya existía)

from sandbox import ErrorSandbox, Sandbox, bwrap_disponible  # noqa: E402
from validador import validar  # noqa: E402

__all__ = ["trabajar", "OBLIGATORIOS"]

# Sin estos campos la web saldría vacía o rota.
OBLIGATORIOS = ("nombre", "lema", "direccion", "telefono")


def _paso(nombre: str, ok: bool, segundos: float, detalle: str = "") -> dict:
    return {"accion": nombre, "ok": ok, "segundos": round(segundos, 3),
            "detalle": detalle}


def trabajar(datos: dict, salida: Path, caja: Sandbox | None = None) -> dict:
    """Genera la web de un negocio y la revisa. Devuelve el informe."""
    informe: dict = {
        "negocio": datos.get("nombre", "(sin nombre)"),
        "salida": str(salida),
        "fecha": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "pasos": [],
        "problemas": [],
        "ok": False,
    }

    # 1. Comprobar los datos de entrada.
    inicio = time.monotonic()
    faltan = [campo for campo in OBLIGATORIOS if not str(datos.get(campo, "")).strip()]
    if faltan:
        informe["pasos"].append(_paso("leer datos", False, time.monotonic() - inicio,
                                      "faltan: " + ", ".join(faltan)))
        informe["problemas"].append("faltan datos obligatorios: " + ", ".join(faltan))
        return informe
    informe["pasos"].append(_paso("leer datos", True, time.monotonic() - inicio,
                                  f"{len(datos)} campos"))

    # 2. Escribir la web.
    inicio = time.monotonic()
    try:
        destino = sitio.generar(datos, salida)
    except Exception as fallo:  # el generador puede tropezar con datos raros
        informe["pasos"].append(_paso("generar web", False, time.monotonic() - inicio,
                                      str(fallo)))
        informe["problemas"].append(f"no se pudo generar la web: {fallo}")
        return informe
    informe["web"] = str(destino)
    informe["bytes"] = destino.stat().st_size
    informe["pasos"].append(_paso("generar web", True, time.monotonic() - inicio,
                                  f"{informe['bytes']} bytes"))

    # 3. Revisarla dentro de la caja.
    inicio = time.monotonic()
    try:
        caja = caja or Sandbox()
        revision = validar(caja, destino.read_text(encoding="utf-8"))
    except ErrorSandbox as fallo:
        informe["pasos"].append(_paso("revisar en sandbox", False,
                                      time.monotonic() - inicio, str(fallo)))
        informe["problemas"].append(f"el sandbox no está disponible: {fallo}")
        return informe
    segundos = time.monotonic() - inicio
    problemas = revision.get("problemas", [])
    informe["pasos"].append(_paso("revisar en sandbox", revision.get("ok", False),
                                  segundos, f"{len(problemas)} problema(s)"))
    informe["revision"] = {k: v for k, v in revision.items() if k != "ejecucion"}
    informe["ejecucion"] = revision.get("ejecucion", {})
    informe["problemas"] += problemas
    informe["ok"] = bool(revision.get("ok"))
    return informe


def main(argv: list[str]) -> int:
    argumentos = [a for a in argv[1:] if not a.startswith("-")]
    if not argumentos:
        print(__doc__)
        return 2

    origen = Path(argumentos[0])
    if not origen.is_file():
        print(f"No existe el fichero: {origen}", file=sys.stderr)
        return 2

    if "-o" in argv:
        salida = Path(argv[argv.index("-o") + 1])
    elif len(argumentos) > 1:
        salida = Path(argumentos[1])
    else:
        salida = RAIZ / "salidas" / origen.stem

    if not bwrap_disponible():
        print("Aviso: falta 'bubblewrap'; la revisión no se puede aislar.",
              file=sys.stderr)

    try:
        datos = json.loads(origen.read_text(encoding="utf-8"))
    except json.JSONDecodeError as fallo:
        print(f"El JSON del negocio está mal: {fallo}", file=sys.stderr)
        return 2

    informe = trabajar(datos, salida)

    # El informe queda junto a la web, para poder enseñarlo.
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "informe.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if "--json" in argv:
        print(json.dumps(informe, ensure_ascii=False, indent=2))
    else:
        print(f"Negocio:  {informe['negocio']}")
        print(f"Web:      {informe.get('web', '(no generada)')}")
        print(f"Revisión: {'correcta' if informe['ok'] else 'con problemas'}")
        for problema in informe["problemas"]:
            print(f"  - {problema}")
        print(f"Informe:  {salida / 'informe.json'}")

    return 0 if informe["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
