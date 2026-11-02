"""Mini aplicación web de SiteSmith: formulario, vista previa e informe.

Solo biblioteca estándar. Escucha en 127.0.0.1 (no en internet) y sirve para
enseñar el agente funcionando: se rellenan cuatro datos y aparece la web
generada, ya revisada dentro de la caja aislada, con el registro de lo que se
ha ejecutado.

    python3 agente/servidor.py                # http://127.0.0.1:8099
    python3 agente/servidor.py --abrir        # y abre el navegador
    python3 agente/servidor.py --puerto 8100
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(RAIZ))

import agente  # noqa: E402,M8

from sandbox import ErrorSandbox, Sandbox  # noqa: E402

__all__ = ["Servidor", "crear", "nombre_a_slug", "CAMPOS", "LIMITE_CUERPO"]

LIMITE_CUERPO = 64 * 1024          # 64 KB: de sobra para cinco campos
SLUG_VALIDO = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")

# (nombre del campo, etiqueta, ejemplo, obligatorio)
CAMPOS = (
    ("nombre", "Nombre del negocio", "Bar La Encina", True),
    ("lema", "Una frase corta", "Tapas y cocina casera", True),
    ("direccion", "Dirección", "Calle Vista Alegre, 13 - Ponferrada", True),
    ("telefono", "Teléfono", "987 000 000", True),
    ("whatsapp", "WhatsApp (opcional)", "34600000000", False),
)


def nombre_a_slug(nombre: str) -> str:
    """Convierte «Bar La Encina» en `bar-la-encina` (solo a-z, 0-9 y guiones)."""
    plano = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    limpio = re.sub(r"[^a-z0-9]+", "-", plano.lower()).strip("-")
    return (limpio[:40].strip("-") or "negocio")


# -- plantillas ------------------------------------------------------------

ESTILOS = """
:root{color-scheme:dark;--fondo:#141519;--panel:#1d1f26;--texto:#f2f3f5;
--tenue:#b9bdc7;--acento:#5b9dff;--borde:#343844;--bien:#39c07c;--mal:#ff6b6b}
*{box-sizing:border-box}
body{margin:0;padding:24px;background:var(--fondo);color:var(--texto);
font:1.15rem/1.6 system-ui,"Segoe UI",Roboto,sans-serif}
main,header,footer{max-width:900px;margin:0 auto}
h1{font-size:2rem;margin:0 0 8px}
h2{font-size:1.4rem;margin:28px 0 10px}
p.tenue{color:var(--tenue)}
label{display:block;font-weight:600;margin:20px 0 6px}
small{display:block;color:var(--tenue);font-weight:400;margin-bottom:6px}
input{width:100%;padding:14px 16px;font-size:1.15rem;border-radius:12px;
border:2px solid var(--borde);background:#0f1014;color:var(--texto)}
input:focus{outline:3px solid var(--acento);outline-offset:2px}
button,.boton{display:inline-block;margin-top:26px;padding:16px 28px;font-size:1.25rem;
font-weight:700;border:0;border-radius:14px;background:var(--acento);color:#06101f;
cursor:pointer;text-decoration:none}
button:hover,.boton:hover{filter:brightness(1.12)}
.boton.secundario{background:var(--panel);color:var(--texto);border:2px solid var(--borde)}
.aviso{padding:16px 18px;border-radius:12px;border-left:6px solid var(--mal);
background:#2a1a1d;margin:18px 0}
.bien{border-left-color:var(--bien);background:#16261f}
table{border-collapse:collapse;width:100%;margin-top:10px}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--borde)}
th{color:var(--tenue);font-weight:600}
ul{margin:8px 0 0 20px}
iframe{width:100%;height:620px;border:2px solid var(--borde);border-radius:14px;
background:#fff;margin-top:12px}
"""

PLANTILLA_FORMULARIO = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SiteSmith — web para tu negocio</title><style>{estilos}</style></head>
<body><main>
<h1>Web para tu negocio</h1>
<p class="tenue">Rellena los datos y la web se escribe sola. Tarda un segundo.</p>
{aviso}
<form method="post" action="/generar">
{campos}
<button type="submit">Generar la web</button>
</form>
</main></body></html>
"""

PLANTILLA_RESULTADO = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SiteSmith — {negocio}</title><style>{estilos}</style></head>
<body><main>
<h1>{negocio}</h1>
<div class="aviso {clase}"><strong>{titular}</strong>
{problemas}</div>

<h2>Paso a paso</h2>
<table><tr><th>Paso</th><th>Resultado</th><th>Tiempo</th><th>Detalle</th></tr>
{pasos}
</table>

<h2>Vista previa</h2>
<iframe src="/vista/{slug}/" title="Vista previa de la web"></iframe>

<p><a class="boton" href="/vista/{slug}/" target="_blank">Abrir a pantalla completa</a>
<a class="boton secundario" href="/informe/{slug}/informe.json">Ver el informe</a>
<a class="boton secundario" href="/">Hacer otra</a></p>
</main></body></html>
"""

PLANTILLA_ERROR = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SiteSmith — error</title><style>{estilos}</style></head>
<body><main>
<h1>No se pudo generar</h1>
<div class="aviso"><strong>{mensaje}</strong></div>
<p><a class="boton" href="/">Volver al formulario</a></p>
</main></body></html>
"""


def _campos_html(valores: dict | None = None) -> str:
    valores = valores or {}
    trozos = []
    for clave, etiqueta, ejemplo, obligatorio in CAMPOS:
        marca = " (obligatorio)" if obligatorio else ""
        requerido = " required" if obligatorio else ""
        trozos.append(
            f'<label for="{clave}">{html.escape(etiqueta)}{marca}</label>'
            f'<small>{html.escape(ejemplo)}</small>'
            f'<input id="{clave}" name="{clave}" value="{html.escape(str(valores.get(clave, "")))}"'
            f'{requerido} autocomplete="off">'
        )
    return "\n".join(trozos)


def _html_formulario(aviso: str = "", valores: dict | None = None) -> bytes:
    bloque = f'<div class="aviso">{html.escape(aviso)}</div>' if aviso else ""
    return PLANTILLA_FORMULARIO.format(
        estilos=ESTILOS, aviso=bloque, campos=_campos_html(valores)
    ).encode()


def _html_resultado(informe: dict, slug: str) -> bytes:
    ok = informe.get("ok")
    pasos = "".join(
        "<tr><td>{accion}</td><td>{estado}</td><td>{segundos} s</td><td>{detalle}</td></tr>".format(
            accion=html.escape(paso["accion"]),
            estado="sí" if paso["ok"] else "no",
            segundos=f'{paso["segundos"]:.2f}',
            detalle=html.escape(paso["detalle"] or ""),
        )
        for paso in informe.get("pasos", [])
    )
    problemas = "".join(f"<li>{html.escape(p)}</li>" for p in informe.get("problemas", []))
    return PLANTILLA_RESULTADO.format(
        estilos=ESTILOS,
        negocio=html.escape(informe.get("negocio", "(sin nombre)")),
        slug=slug,
        clase="bien" if ok else "",
        titular="Todo correcto: la web está lista y revisada." if ok
        else "Hay que corregir esto:",
        problemas=f"<ul>{problemas}</ul>" if problemas else "",
        pasos=pasos or "<tr><td colspan=4>sin pasos</td></tr>",
    ).encode()


def _html_error(mensaje: str) -> bytes:
    return PLANTILLA_ERROR.format(estilos=ESTILOS, mensaje=html.escape(mensaje)).encode()


# -- servidor --------------------------------------------------------------


class Servidor(BaseHTTPRequestHandler):
    """Atiende el formulario, genera la web y sirve las salidas."""

    raiz = RAIZ / "salidas"
    caja = None  # tipo Sandbox, se asigna al arrancar

    # silencio: el registro de cada petición no aporta nada aquí
    def log_message(self, formato: str, *args) -> None:  # noqa: A003
        pass

    # -- utilidades --------------------------------------------------------

    def _responder(self, cuerpo: bytes, estado: int = 200,
                   tipo: str = "text/html; charset=utf-8") -> None:
        self.send_response(estado)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(cuerpo)

    def _ruta(self) -> str:
        return urllib.parse.urlparse(self.path).path

    def _slug_de_la_ruta(self, prefijo: str) -> str | None:
        """Saca el `slug` de `/prefijo/<slug>/...` y comprueba que es válido."""
        resto = self._ruta()[len(prefijo):].strip("/")
        trozo = resto.split("/")[0] if resto else ""
        return trozo if SLUG_VALIDO.match(trozo) else None

    # -- peticiones --------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        ruta = self._ruta()
        if ruta in ("/", "/index.html"):
            self._responder(_html_formulario())
            return

        if ruta.startswith("/vista/"):
            slug = self._slug_de_la_ruta("/vista/")
            fichero = self.raiz / slug / "index.html" if slug else None
            if fichero and fichero.is_file():
                self._responder(fichero.read_bytes())
            else:
                self._responder(_html_error("Esa web no existe todavía."), 404)
            return

        if ruta.startswith("/informe/"):
            slug = self._slug_de_la_ruta("/informe/")
            fichero = self.raiz / slug / "informe.json" if slug else None
            if fichero and fichero.is_file():
                self._responder(fichero.read_bytes(), tipo="application/json; charset=utf-8")
            else:
                self._responder(b'{"error":"sin informe"}', 404,
                                "application/json; charset=utf-8")
            return

        self._responder(_html_error("Página no encontrada."), 404)

    def do_POST(self) -> None:  # noqa: N802
        if self._ruta() != "/generar":
            self._responder(_html_error("Página no encontrada."), 404)
            return

        try:
            largo = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            largo = 0
        if largo <= 0 or largo > LIMITE_CUERPO:
            self._responder(_html_error("Los datos enviados no son válidos."), 413)
            return

        crudo = self.rfile.read(largo).decode("utf-8", "replace")
        valores = {clave: valor.strip() for clave, valor in
                   urllib.parse.parse_qsl(crudo, keep_blank_values=True)}

        datos = {clave: valores.get(clave, "") for clave, _, _, _ in CAMPOS}
        datos["tipo_negocio"] = "BarOrPub"
        datos["demo"] = True          # banda de aviso: el negocio es de ejemplo

        faltan = [etiqueta for clave, etiqueta, _, obligatorio in CAMPOS
                  if obligatorio and not datos.get(clave)]
        if faltan:
            self._responder(
                _html_formulario("Falta rellenar: " + ", ".join(faltan), valores), 400
            )
            return

        slug = nombre_a_slug(datos["nombre"])
        salida = self.raiz / slug
        try:
            informe = agente.trabajar(datos, salida, self.caja)
            agente.guardar(informe, salida)
        except ErrorSandbox as fallo:
            self._responder(_html_error(f"No se pudo revisar la web: {fallo}"), 503)
            return
        except Exception as fallo:  # noqa: BLE001  (mejor un error legible que una traza)
            self._responder(_html_error(f"Fallo inesperado: {fallo}"), 500)
            return

        self._responder(_html_resultado(informe, slug))

    do_HEAD = do_GET  # noqa: N815


def crear(puerto: int = 8099, host: str = "127.0.0.1",
          raiz: Path | None = None) -> ThreadingHTTPServer:
    """Crea (sin arrancar) el servidor con la caja ya preparada."""
    Servidor.caja = Sandbox()
    Servidor.raiz = Path(raiz) if raiz else RAIZ / "salidas"
    Servidor.raiz.mkdir(parents=True, exist_ok=True)
    return ThreadingHTTPServer((host, puerto), Servidor)


def main(argv: list[str]) -> int:
    analizador = argparse.ArgumentParser(description="Mini aplicación web de SiteSmith")
    analizador.add_argument("--puerto", type=int, default=8099)
    analizador.add_argument("--host", default="127.0.0.1",
                            help="por defecto solo este equipo (127.0.0.1)")
    analizador.add_argument("--abrir", action="store_true", help="abrir el navegador")
    opciones = analizador.parse_args(argv[1:])

    try:
        servidor = crear(opciones.puerto, opciones.host)
    except ErrorSandbox as fallo:
        print(f"Error: {fallo}", file=sys.stderr)
        return 1
    except OSError as fallo:
        print(f"No se pudo abrir el puerto {opciones.puerto}: {fallo}", file=sys.stderr)
        return 1

    direccion = f"http://{opciones.host}:{opciones.puerto}/"
    print(f"SiteSmith escuchando en {direccion}  (Ctrl+C para parar)")
    if opciones.abrir:
        webbrowser.open(direccion)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nParado.")
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
