#!/usr/bin/env python3
"""SiteSmith — genera la web completa de un negocio a partir de un JSON.

Uso:
    python3 sitio.py negocios/bar-ejemplo.json [carpeta_salida]

Escribe un único index.html autosuficiente (sin dependencias, sin cookies),
pensado para publicarse tal cual en GitHub Pages o en cualquier hosting.
"""

from __future__ import annotations

import colorsys
import html
import json
import sys
from pathlib import Path

BASE_CSS = """
:root{
  --tinta:#1a1613; --papel:#fbf8f3; --suave:#6f6459; --linea:#e2d9cc;
  --acento:#7a1f1f; --acento-texto:#ffffff; --tarjeta:#ffffff;
}
@media (prefers-color-scheme: dark){
  :root{ --tinta:#f3ede4; --papel:#14110f; --suave:#b6a99a; --linea:#332c26;
         --acento:#e0705f; --acento-texto:#1a1210; --tarjeta:#1d1917; }
}
*{box-sizing:border-box}
html{font-size:19px;scroll-behavior:smooth}
body{margin:0;background:var(--papel);color:var(--tinta);
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;line-height:1.6}
h1,h2,h3{font-family:Georgia,"Times New Roman",serif;line-height:1.2;margin:0 0 .4em}
h1{font-size:2.6rem}h2{font-size:1.9rem}h3{font-size:1.25rem}
a{color:var(--acento)}
img{max-width:100%;height:auto;border-radius:12px}
.envoltorio{max-width:960px;margin:0 auto;padding:0 20px}
header.portada{background:var(--acento);color:var(--acento-texto);padding:56px 0 48px}
header.portada p{margin:.4em 0 1.4em;font-size:1.15rem;opacity:.92}
nav.saltar a{color:inherit}
.boton{display:inline-block;padding:16px 26px;border-radius:12px;font-weight:700;
  text-decoration:none;background:var(--acento);color:var(--acento-texto);
  border:2px solid currentColor;font-size:1.05rem}
header.portada .boton{background:var(--acento-texto);color:var(--acento);border-color:transparent}
.boton.secundario{background:transparent;color:var(--acento)}
section{padding:52px 0;border-top:1px solid var(--linea)}
nav.menu{position:sticky;top:0;background:var(--papel);border-bottom:1px solid var(--linea);z-index:5}
nav.menu ul{display:flex;gap:6px;list-style:none;margin:0;padding:10px 0;overflow-x:auto}
nav.menu a{padding:10px 14px;border-radius:10px;text-decoration:none;color:var(--tinta);white-space:nowrap}
nav.menu a:hover{background:var(--linea)}
.rejilla{display:grid;gap:18px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}
.tarjeta{background:var(--tarjeta);border:1px solid var(--linea);border-radius:14px;padding:18px}
.plato{display:flex;justify-content:space-between;gap:16px;padding:10px 0;border-bottom:1px dotted var(--linea)}
.plato:last-child{border-bottom:0}
.plato strong{font-weight:600}
.plato span.precio{white-space:nowrap;font-variant-numeric:tabular-nums}
.plato small{display:block;color:var(--suave);font-size:.9rem}
table.horario{width:100%;border-collapse:collapse}
table.horario td{padding:8px 0;border-bottom:1px solid var(--linea)}
table.horario td:last-child{text-align:right;color:var(--suave)}
tr.cerrado td{color:var(--suave);font-style:italic}
a:focus-visible,.boton:focus-visible,nav.menu a:focus-visible{
  outline:3px solid var(--acento);outline-offset:3px;border-radius:8px}
.aviso-demo{background:#fff3cd;color:#4a3b00;border-bottom:3px solid #e0a800;
  padding:14px 20px;font-size:1rem;text-align:center;line-height:1.5}
@media (prefers-color-scheme: dark){
  .aviso-demo{background:#3a2f00;color:#ffe9a8;border-bottom-color:#e0a800}
}
footer{padding:36px 0 120px;color:var(--suave);font-size:.9rem;border-top:1px solid var(--linea)}
.boton-flotante{position:fixed;right:18px;bottom:18px;z-index:20;border-radius:999px;
  padding:16px 22px;background:var(--acento);color:var(--acento-texto);
  text-decoration:none;font-weight:700;box-shadow:0 8px 24px rgba(0,0,0,.28)}
@media (max-width:600px){ html{font-size:18px} h1{font-size:2rem} header.portada{padding:40px 0 34px} }
@media (prefers-reduced-motion: reduce){ html{scroll-behavior:auto} }
""".strip()


def e(texto: object) -> str:
    return html.escape(str(texto), quote=True)


def precio_o_vacio(valor: object) -> str:
    return e(valor) if valor not in (None, "") else ""


def tarjetas_carta(carta: list[dict]) -> str:
    trozos = []
    for seccion in carta:
        platos = []
        for plato in seccion.get("platos", []):
            desc = f"<small>{e(plato['descripcion'])}</small>" if plato.get("descripcion") else ""
            platos.append(
                f'<div class="plato"><strong>{e(plato["nombre"])}{desc}</strong>'
                f'<span class="precio">{precio_o_vacio(plato.get("precio"))}</span></div>'
            )
        trozos.append(
            f'<article class="tarjeta"><h3>{e(seccion.get("nombre", "Carta"))}</h3>'
            f'{"".join(platos)}</article>'
        )
    return "".join(trozos)


def filas_horario(horario: list) -> str:
    filas = []
    for dia, horas in horario:
        clases = ' class="cerrado"' if str(horas).lower() in {"cerrado", "cerrada", ""} else ""
        filas.append(f"<tr{clases}><td>{e(dia)}</td><td>{e(horas)}</td></tr>")
    return "".join(filas)


def horario_schema(horario: list, nombre: str) -> str:
    dias = {
        "lunes": "Monday", "martes": "Tuesday", "miércoles": "Wednesday",
        "miercoles": "Wednesday", "jueves": "Thursday", "viernes": "Friday",
        "sábado": "Saturday", "sabado": "Saturday", "domingo": "Sunday",
    }
    especificaciones = []
    for dia, horas in horario:
        ingles = dias.get(str(dia).strip().lower())
        if not ingles or str(horas).lower().startswith("cerrad"):
            continue
        especificaciones.append({
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": f"https://schema.org/{ingles}",
            "description": str(horas),
        })
    return json.dumps(especificaciones, ensure_ascii=False)


def _canales(hexadecimal: str) -> tuple[int, int, int]:
    valor = hexadecimal.strip().lstrip("#")
    if len(valor) == 3:
        valor = "".join(c * 2 for c in valor)
    return tuple(int(valor[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _luminancia(rgb: tuple[int, int, int]) -> float:
    """Luminancia relativa según la fórmula de accesibilidad web (WCAG)."""
    def lineal(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (lineal(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def color_legible_sobre_fondo(hexadecimal: str) -> str:
    """Devuelve '#ffffff' o '#12100e' según lo que se lea mejor encima.

    El umbral 0,18 es el punto de contraste equivalente de la norma WCAG
    (a partir de ahí, el texto oscuro se lee mejor que el blanco).
    """
    try:
        return "#ffffff" if _luminancia(_canales(hexadecimal)) < 0.18 else "#12100e"
    except (ValueError, IndexError):
        return "#ffffff"


def aclarar_para_fondo_oscuro(hexadecimal: str, objetivo: float = 0.32) -> str:
    """Aclara el color (mismo tono y saturación) hasta que se lea sobre negro."""
    try:
        rojo, verde, azul = (c / 255 for c in _canales(hexadecimal))
    except (ValueError, IndexError):
        return hexadecimal
    if _luminancia(_canales(hexadecimal)) >= objetivo:
        return hexadecimal
    tono, luz, saturacion = colorsys.rgb_to_hls(rojo, verde, azul)
    while luz < 1:
        luz = min(1.0, luz + 0.01)
        rgb = tuple(round(c * 255) for c in colorsys.hls_to_rgb(tono, luz, saturacion))
        if _luminancia(rgb) >= objetivo:
            return "#" + "".join(f"{c:02x}" for c in rgb)
    return "#ffffff"


def generar(datos: dict, salida: Path) -> Path:
    nombre = datos["nombre"]
    lema = datos.get("lema", "")
    telefono = datos.get("telefono", "")
    whatsapp = str(datos.get("whatsapp", "")).replace(" ", "").replace("+", "")
    direccion = datos.get("direccion", "")
    mapa = datos.get("mapa") or (
        "https://www.google.com/maps/search/?api=1&query=" + direccion.replace(" ", "+")
    )
    tipo = datos.get("tipo_negocio", "LocalBusiness")
    acento = datos.get("colores", {}).get("acento")
    if acento:
        claro = aclarar_para_fondo_oscuro(acento)
        color_css = (
            f":root{{--acento:{e(acento)};--acento-texto:{color_legible_sobre_fondo(acento)}}}"
            f"@media (prefers-color-scheme: dark){{:root{{--acento:{e(claro)};"
            f"--acento-texto:{color_legible_sobre_fondo(claro)}}}}}"
        )
    else:
        color_css = ""

    enlaces_nav = []
    # El nombre de la sección se adapta al sector: «Nuestra carta» en bares y
    # restaurantes, «Servicios» o «Cuotas» en peluquerías y gimnasios.
    titulo_carta = datos.get("titulo_carta") or "Nuestra carta"
    etiqueta_carta = datos.get("etiqueta_carta") or (
        "Carta" if titulo_carta == "Nuestra carta" else titulo_carta
    )

    for ancla, etiqueta in (("#carta", etiqueta_carta), ("#horario", "Horario"),
                            ("#donde", "Dónde estamos")):
        if ancla == "#carta" and not datos.get("carta"):
            continue
        enlaces_nav.append(f'<li><a href="{ancla}">{etiqueta}</a></li>')

    seccion_carta = ""
    if datos.get("carta"):
        seccion_carta = (
            f'<section id="carta"><div class="envoltorio"><h2>{e(titulo_carta)}</h2>'
            f'<div class="rejilla">{tarjetas_carta(datos["carta"])}</div></div></section>'
        )

    seccion_horario = ""
    if datos.get("horario"):
        nota = f'<p>{e(datos["nota_horario"])}</p>' if datos.get("nota_horario") else ""
        seccion_horario = (
            '<section id="horario"><div class="envoltorio"><h2>Horario</h2>'
            f'<table class="horario">{filas_horario(datos["horario"])}</table>{nota}</div></section>'
        )

    boton_wa = ""
    if whatsapp:
        boton_wa = (
            f'<a class="boton" href="https://wa.me/{e(whatsapp)}">Escribir por WhatsApp</a>'
        )
    aviso_demo = ""
    if datos.get("demo"):
        aviso_demo = (
            '<div class="aviso-demo"><strong>Web de ejemplo.</strong> El negocio, '
            "la dirección y el teléfono son inventados. La hace un programa "
            "a partir de los datos reales del negocio.</div>"
        )
    elif datos.get("muestra"):
        # Muestra preparada para un negocio real que todavía no ha dicho que sí.
        aviso_demo = (
            '<div class="aviso-demo"><strong>Muestra gratuita.</strong> Esta web '
            "está preparada para que veas cómo quedaría la tuya. Todavía no "
            "tiene tus fotos ni tu carta de verdad: dime qué cambio y la dejo "
            "lista.</div>"
        )
    # Ni los ejemplos ni las muestras deben aparecer en Google: hablan de
    # negocios que no las han encargado.
    robots = (
        '<meta name="robots" content="noindex">' if datos.get("demo") or datos.get("muestra") else ""
    )
    flotante = (
        f'<a class="boton-flotante" href="https://wa.me/{e(whatsapp)}">WhatsApp</a>'
        if whatsapp else ""
    )
    boton_tel = (
        f'<p><a class="boton secundario" href="tel:{e(telefono.replace(" ", ""))}">'
        f'Llamar al {e(telefono)}</a></p>' if telefono else ""
    )

    schema = {
        "@context": "https://schema.org",
        "@type": tipo,
        "name": nombre,
        "description": lema,
        "telephone": telefono,
        "address": {"@type": "PostalAddress", "streetAddress": direccion, "addressCountry": "ES"},
        "url": "./",
        "hasMenu": "#carta" if datos.get("carta") else None,
        "openingHoursSpecification": json.loads(horario_schema(datos.get("horario", []), nombre)),
    }
    schema = {k: v for k, v in schema.items() if v not in (None, "", [])}

    documento = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(nombre)} — {e(datos.get("sector", "Ponferrada"))}</title>
<meta name="description" content="{e(lema)}">
<meta property="og:title" content="{e(nombre)}">
<meta property="og:description" content="{e(lema)}">
<meta property="og:type" content="website">
{robots}
<meta name="theme-color" content="{e(acento or "#7a1f1f")}">
<style>{BASE_CSS}
{color_css}</style>
</head>
<body>
{aviso_demo}<header class="portada">
  <div class="envoltorio">
    <h1>{e(nombre)}</h1>
    <p>{e(lema)}</p>
    {boton_wa}
  </div>
</header>
<nav class="menu" aria-label="Secciones">
  <div class="envoltorio"><ul>{"".join(enlaces_nav)}</ul></div>
</nav>
<main>
{seccion_carta}
{seccion_horario}
<section id="donde">
  <div class="envoltorio">
    <h2>Dónde estamos</h2>
    <p>{e(direccion)}</p>
    <p><a class="boton secundario" href="{e(mapa)}">Ver en el mapa</a></p>
    {boton_tel}
  </div>
</section>
</main>
<footer>
  <div class="envoltorio">
    <p><strong>{e(nombre)}</strong> · {e(direccion)} · {e(telefono)}</p>
    <p>Aviso legal: esta web no usa cookies ni recoge datos personales.
    Titular: {e(datos.get("titular", nombre))}.</p>
    <p>Web hecha por SiteSmith.</p>
  </div>
</footer>
{flotante}
<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>
</body>
</html>
"""
    salida.mkdir(parents=True, exist_ok=True)
    destino = salida / "index.html"
    destino.write_text(documento, encoding="utf-8")
    return destino


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    origen = Path(argv[1])
    datos = json.loads(origen.read_text(encoding="utf-8"))
    salida = Path(argv[2]) if len(argv) > 2 else Path("salidas") / origen.stem
    destino = generar(datos, salida)
    print(f"Web generada: {destino} ({destino.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
