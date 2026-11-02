/*
 * SiteSmith en el navegador.
 *
 * No hay servidor: Pyodide baja Python compilado a WebAssembly y ejecuta
 * `sito.py` (el generador) y `agente/revisor.py` (el comprobador). Son los
 * mismos ficheros que usa la versión de consola, no una copia.
 *
 * Coste: la primera vez descarga unos 10 MB de Python. Después queda en caché.
 */

const VERSION_PYODIDE = "v0.26.4";
const CDN = `https://cdn.jsdelivr.net/pyodide/${VERSION_PYODIDE}/full/`;

const CAMPOS = ["nombre", "lema", "direccion", "telefono", "whatsapp"];
const OBLIGATORIOS = ["nombre", "lema", "direccion", "telefono"];
const EJEMPLO = {
  nombre: "Bar La Encina",
  lema: "Tapas y cocina casera",
  direccion: "Calle Vista Alegre, 13 - Ponferrada",
  telefono: "987 000 000",
  whatsapp: "34600000000",
};

const $ = (id) => document.getElementById(id);
let pyodide = null;
let urlVista = null;

/* -- gancho de prueba ----------------------------------------------------- */

/* Con ?reporte=/resultado la página cuenta al servidor local qué ha pasado.
   Sirve para comprobarla sin mirar la pantalla; en uso normal no hace nada. */
function reportar(datos) {
  const destino = new URLSearchParams(location.search).get("reporte");
  if (!destino) return;
  fetch(destino, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(datos),
  }).catch(() => {});
}

window.addEventListener("error", (evento) =>
  reportar({ fase: "error", mensaje: String(evento.message) })
);
window.addEventListener("unhandledrejection", (evento) =>
  reportar({ fase: "rechazo", mensaje: String(evento.reason) })
);

/* -- utilidades de pantalla ------------------------------------------------ */

function estado(texto) {
  $("estado").textContent = texto;
}

function mostrar(id, si = true) {
  $(id).classList.toggle("oculto", !si);
}

function aviso(titulo, problemas = []) {
  const caja = document.createElement("div");
  caja.className = "aviso";
  const fuerte = document.createElement("strong");
  fuerte.textContent = titulo;
  caja.appendChild(fuerte);
  if (problemas.length) {
    const lista = document.createElement("ul");
    for (const problema of problemas) {
      const punto = document.createElement("li");
      punto.textContent = problema;
      lista.appendChild(punto);
    }
    caja.appendChild(lista);
  }
  $("pasos").replaceChildren(caja);
}

function tablaPasos(pasos) {
  const tabla = document.createElement("table");
  const cabecera = document.createElement("tr");
  for (const titulo of ["Paso", "Resultado", "Tiempo"]) {
    const celda = document.createElement("th");
    celda.textContent = titulo;
    cabecera.appendChild(celda);
  }
  tabla.appendChild(cabecera);
  for (const paso of pasos) {
    const fila = document.createElement("tr");
    for (const valor of [paso.accion, paso.ok ? "sí" : "no", `${paso.ms} ms`]) {
      const celda = document.createElement("td");
      celda.textContent = valor;
      fila.appendChild(celda);
    }
    tabla.appendChild(fila);
  }
  $("pasos").replaceChildren(tabla);
}

/* -- Python --------------------------------------------------------------- */

async function cargarPython() {
  if (pyodide) return pyodide;
  estado("Descargando Python (una sola vez, unos 10 MB)…");

  await new Promise((listo, fallo) => {
    const etiqueta = document.createElement("script");
    etiqueta.src = `${CDN}pyodide.js`;
    etiqueta.onload = listo;
    etiqueta.onerror = () => fallo(new Error("no se pudo cargar Pyodide"));
    document.head.appendChild(etiqueta);
  });

  pyodide = await loadPyodide({ indexURL: CDN });
  reportar({ fase: "pyodide-listo" });

  estado("Cargando el generador y el comprobador…");
  const [generador, comprobador] = await Promise.all([
    traer("../sitio.py"),
    traer("../agente/revisor.py"),
  ]);
  pyodide.FS.writeFile("/sitio.py", generador);
  pyodide.FS.writeFile("/revisor.py", comprobador);
  return pyodide;
}

async function traer(ruta) {
  const respuesta = await fetch(ruta, { cache: "no-cache" });
  if (!respuesta.ok) {
    throw new Error(`no se pudo leer ${ruta} (HTTP ${respuesta.status})`);
  }
  return respuesta.text();
}

function generarWeb(datos) {
  pyodide.FS.writeFile("/negocio.json", JSON.stringify(datos));
  return pyodide.runPython(`
import json
from pathlib import Path

ns = {"__name__": "sitio"}
exec(open("/sitio.py", encoding="utf-8").read(), ns)
datos = json.loads(open("/negocio.json", encoding="utf-8").read())
ns["generar"](datos, Path("/salida"))
open("/salida/index.html", encoding="utf-8").read()
`);
}

function revisarWeb() {
  return pyodide.runPython(`
import contextlib, io, os

os.makedirs("/salida/sitio", exist_ok=True)
open("/salida/sitio/index.html", "w", encoding="utf-8").write(
    open("/salida/index.html", encoding="utf-8").read()
)
os.chdir("/salida")

salida = io.StringIO()
ns = {"__name__": "__main__"}
with contextlib.redirect_stdout(salida):
    try:
        exec(open("/revisor.py", encoding="utf-8").read(), ns)
    except SystemExit:
        pass          # el comprobador termina con sys.exit(0) o sys.exit(2)
salida.getvalue().strip()
`);
}

/* -- acción principal ----------------------------------------------------- */

async function alPulsar() {
  const datos = {};
  for (const campo of CAMPOS) datos[campo] = $(campo).value.trim();
  datos.tipo_negocio = "BarOrPub";
  datos.demo = true;

  const faltan = OBLIGATORIOS.filter((campo) => !datos[campo]);
  if (faltan.length) {
    aviso("Falta rellenar: " + faltan.join(", "));
    return;
  }

  $("generar").disabled = true;
  $("pasos").replaceChildren();
  mostrar("vista", false);
  mostrar("abrir", false);
  mostrar("descargar", false);
  mostrar("informe", false);
  mostrar("titulo-informe", false);

  try {
    const arranque = performance.now();
    await cargarPython();
    const pasos = [{ accion: "leer datos", ok: true, ms: Math.round(performance.now() - arranque) }];

    let t0 = performance.now();
    const html = generarWeb(datos);
    pasos.push({ accion: "generar web", ok: true, ms: Math.round(performance.now() - t0) });

    t0 = performance.now();
    const informe = JSON.parse(revisarWeb());
    pasos.push({ accion: "revisar la web", ok: informe.ok, ms: Math.round(performance.now() - t0) });

    tablaPasos(pasos);

    const resumen = document.createElement("div");
    resumen.className = "aviso" + (informe.ok ? " bien" : "");
    resumen.textContent = informe.ok
      ? "Todo correcto: la web está lista y revisada."
      : "Hay que corregir esto: " + informe.problemas.join("; ");
    $("pasos").prepend(resumen);

    if (urlVista) URL.revokeObjectURL(urlVista);
    urlVista = URL.createObjectURL(new Blob([html], { type: "text/html" }));
    $("vista").src = urlVista;
    $("abrir").href = urlVista;
    $("descargar").href = urlVista;
    mostrar("vista");
    mostrar("abrir");
    mostrar("descargar");

    $("informe").textContent = JSON.stringify(informe, null, 2);
    mostrar("informe");
    mostrar("titulo-informe");

    estado(`Listo. ${informe.etiquetas} etiquetas, ${informe.bytes} bytes.`);

    reportar({ fase: "fin", ok: informe.ok, informe, bytes: html.length, pasos });
  } catch (fallo) {
    reportar({ fase: "fallo", mensaje: String(fallo && fallo.stack || fallo) });
    aviso("No se pudo generar: " + fallo.message);
    estado("Revisa la conexión: la primera vez hay que descargar Python.");
  } finally {
    $("generar").disabled = false;
  }
}

function rellenarEjemplo() {
  for (const campo of CAMPOS) $(campo).value = EJEMPLO[campo] || "";
  estado("Ejemplo cargado. Pulsa «Generar la web».");
}

$("generar").addEventListener("click", alPulsar);
$("ejemplo").addEventListener("click", rellenarEjemplo);

/* Si la página se abre con ?auto=1 (para pruebas), se lanza sola. */
if (new URLSearchParams(location.search).get("auto") === "1") {
  rellenarEjemplo();
  setTimeout(alPulsar, 300);
}
