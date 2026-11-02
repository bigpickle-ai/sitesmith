"""Revisa la web generada ejecutando el comprobador dentro de la caja.

El programa de comprobación no corre en este proceso: se manda al sandbox como
texto y se ejecuta allí, sin red y sin acceso a `/home`. Así el informe sirve
de prueba de que el agente *ejecuta* código, no solo escribe ficheros.

    from sandbox import Sandbox
    from validador import validar
    informe = validar(Sandbox(), html)      # {"ok": True, "problemas": [], ...}
"""

from __future__ import annotations

import json

from sandbox import Resultado, Sandbox

__all__ = ["validar", "PROGRAMA", "revisar"]

# Programa que se ejecuta dentro del sandbox. Debe valerse por sí solo: solo
# usa la biblioteca estándar y lee `sitio/index.html` del directorio actual.
PROGRAMA = r'''
import json, re, sys
from html.parser import HTMLParser

VACIAS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
          "link", "meta", "param", "source", "track", "wbr"}


class Revisor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pila, self.errores, self.etiquetas = [], [], []
        self.titulo, self.metas, self.texto = "", {}, []
        self._dentro_titulo = False

    def handle_starttag(self, etiqueta, atributos):
        self.etiquetas.append(etiqueta)
        if etiqueta == "title":
            self._dentro_titulo = True
        if etiqueta == "meta":
            datos = dict(atributos)
            if datos.get("name"):
                self.metas[datos["name"].lower()] = datos.get("content", "")
        if etiqueta not in VACIAS:
            self.pila.append(etiqueta)

    def handle_endtag(self, etiqueta):
        if etiqueta == "title":
            self._dentro_titulo = False
        if etiqueta in VACIAS:
            return
        if not self.pila:
            self.errores.append(f"</{etiqueta}> sin apertura")
        elif self.pila[-1] != etiqueta:
            self.errores.append(f"</{etiqueta}> cierra <{self.pila[-1]}>")
            if etiqueta in self.pila:
                while self.pila and self.pila.pop() != etiqueta:
                    pass
        else:
            self.pila.pop()

    def handle_data(self, datos):
        if self._dentro_titulo:
            self.titulo += datos
        trozo = datos.strip()
        if trozo:
            self.texto.append(trozo)


def main():
    try:
        html = open("sitio/index.html", encoding="utf-8").read()
    except OSError as error:
        print(json.dumps({"ok": False, "problemas": [f"no se pudo leer el HTML: {error}"]}))
        return 1

    revisor = Revisor()
    revisor.feed(html)
    problemas = list(revisor.errores)
    etiquetas = set(revisor.etiquetas)

    # 1. Estructura
    for obligatoria in ("html", "head", "body", "title", "h1", "main"):
        if obligatoria not in etiquetas:
            problemas.append(f"falta <{obligatoria}>")
    if revisor.pila:
        problemas.append("sin cerrar: " + ", ".join(revisor.pila))

    # 2. Restos de plantilla
    restos = sorted(set(re.findall(r"\{[a-z_][a-z0-9_]*\}", html)))
    if restos:
        problemas.append("marcadores sin sustituir: " + ", ".join(restos))

    # 3. Textos y metadatos
    if len(revisor.titulo.strip()) < 10:
        problemas.append("el <title> es demasiado corto")
    if not revisor.metas.get("description"):
        problemas.append("falta <meta name=description>")
    if not revisor.metas.get("viewport"):
        problemas.append("falta la etiqueta viewport (móvil)")
    if len(" ".join(revisor.texto)) < 120:
        problemas.append("hay muy poco texto visible")

    # 4. Idioma y aviso legal
    if 'lang="es"' not in html:
        problemas.append('el <html> no declara lang="es"')
    if "aviso legal" not in html.lower():
        problemas.append("no hay enlace al aviso legal")

    # 5. Datos para Google (JSON-LD)
    datos_google = "ausente"
    for bloque in re.findall(
        r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S
    ):
        try:
            objeto = json.loads(bloque)
        except json.JSONDecodeError as error:
            problemas.append(f"JSON-LD inválido: {error}")
            continue
        if isinstance(objeto, dict) and objeto.get("@type"):
            datos_google = str(objeto.get("@type"))
            if not objeto.get("name"):
                problemas.append("JSON-LD sin nombre del negocio")

    # 6. Contacto
    if "wa.me/" not in html and "api.whatsapp.com" not in html:
        problemas.append("no hay enlace de WhatsApp")
    if "tel:" not in html:
        problemas.append("no hay teléfono marcable")

    # 7. Nada de rastreo de terceros
    for rastreador in ("googletagmanager", "google-analytics", "facebook.net"):
        if rastreador in html:
            problemas.append(f"incluye rastreo de terceros: {rastreador}")

    print(json.dumps({
        "ok": not problemas,
        "problemas": problemas,
        "bytes": len(html.encode()),
        "etiquetas": len(revisor.etiquetas),
        "titulo": revisor.titulo.strip(),
        "datos_google": datos_google,
    }, ensure_ascii=False))
    return 0 if not problemas else 2


sys.exit(main())
'''


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
