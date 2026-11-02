"""Pruebas de la caja de arena y del agente.

    cd ~/sitios/agente && python3 -m unittest -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

import agente  # noqa: E402
from sandbox import Sandbox, bwrap_disponible  # noqa: E402
from validador import PROGRAMA, revisar  # noqa: E402

RAIZ = AQUI.parent
EJEMPLO = RAIZ / "negocios" / "bar-ejemplo.json"

sin_bwrap = unittest.skipUnless(
    bwrap_disponible(), "bubblewrap no está instalado"
)


@sin_bwrap
class CajaTest(unittest.TestCase):
    """Lo que la caja tiene que impedir."""

    def test_ejecuta_y_devuelve_la_salida(self):
        resultado = Sandbox().ejecutar("print(6 * 7)")
        self.assertTrue(resultado.ok, resultado.errores)
        self.assertEqual(resultado.salida.strip(), "42")
        self.assertLess(resultado.segundos, 10)

    def test_la_red_esta_cortada(self):
        programa = (
            "import socket\n"
            "socket.setdefaulttimeout(3)\n"
            "try:\n"
            "    socket.create_connection(('1.1.1.1', 53), 3)\n"
            "except OSError as fallo:\n"
            "    print('sin red:', type(fallo).__name__)\n"
            "else:\n"
            "    print('CONECTADO')\n"
        )
        resultado = Sandbox().ejecutar(programa)
        self.assertTrue(resultado.ok, resultado.errores)
        self.assertIn("sin red", resultado.salida)

    def test_no_se_ve_home_ni_el_sistema_entero(self):
        programa = (
            "import os\n"
            "print('home', os.path.isdir('/home/oem'))\n"
            "print('etc', os.path.isdir('/etc'))\n"
            "print('memoria', os.path.isfile('/home/oem/.config/opencode/memory.md'))\n"
            "print('raiz', sorted(os.listdir('/')))\n"
        )
        resultado = Sandbox().ejecutar(programa)
        self.assertTrue(resultado.ok, resultado.errores)
        self.assertIn("home False", resultado.salida)
        self.assertIn("etc False", resultado.salida)
        self.assertIn("memoria False", resultado.salida)
        raiz = resultado.salida.split("raiz", 1)[1]
        for prohibida in ("home", "root", "media", "mnt"):
            self.assertNotIn(f"'{prohibida}'", raiz)

    def test_se_corta_por_tiempo(self):
        resultado = Sandbox(segundos=2).ejecutar("while True: pass")
        self.assertFalse(resultado.ok)
        self.assertTrue(resultado.agotado or resultado.codigo != 0)

    def test_se_corta_por_memoria(self):
        resultado = Sandbox(memoria_mb=128).ejecutar(
            "try:\n    x = bytearray(1 << 31)\nexcept MemoryError:\n    print('sin memoria')\n"
        )
        self.assertIn("sin memoria", resultado.salida + resultado.errores)

    def test_no_deja_escribir_fuera_del_trabajo(self):
        with self.assertRaises(ValueError):
            Sandbox().ejecutar("print('hola')", {"../fuera.txt": "no"})

    def test_el_trabajo_es_temporal(self):
        resultado = Sandbox().ejecutar(
            "import os\nopen('nota.txt','w').write('hola')\nprint(os.listdir('.'))\n"
        )
        self.assertTrue(resultado.ok, resultado.errores)
        self.assertIn("nota.txt", resultado.salida)
        self.assertFalse((AQUI / "nota.txt").exists())


@sin_bwrap
class ValidadorTest(unittest.TestCase):
    """El comprobador ejecutado dentro de la caja."""

    def test_detecta_html_roto(self):
        resultado = Sandbox().ejecutar(PROGRAMA, {"sitio/index.html": "<html><body><h1>Hola"})
        informe = revisar(resultado)
        self.assertFalse(informe["ok"])
        self.assertTrue(any("title" in p for p in informe["problemas"]))
        self.assertTrue(any("sin cerrar" in p for p in informe["problemas"]))
        self.assertEqual(informe["ejecucion"]["codigo"], 2)

    def test_detecta_marcadores_y_rastreo(self):
        html = (
            '<html lang="es"><head><title>Bar de prueba en Ponferrada</title>'
            '<meta name="description" content="x"><meta name="viewport" content="w">'
            '</head><body><main><h1>Bar</h1><p>{nombre}</p>'
            '<script src="https://www.googletagmanager.com/x.js"></script>'
            '<a href="aviso-legal.html">Aviso legal</a></main></body></html>'
        )
        informe = revisar(Sandbox().ejecutar(PROGRAMA, {"sitio/index.html": html}))
        self.assertFalse(informe["ok"])
        self.assertTrue(any("marcadores" in p for p in informe["problemas"]))
        self.assertTrue(any("rastreo" in p for p in informe["problemas"]))


@sin_bwrap
class AgenteTest(unittest.TestCase):
    """El recorrido completo: datos → web → revisión ejecutada."""

    def test_genera_y_revisa_el_ejemplo(self):
        datos = json.loads(EJEMPLO.read_text(encoding="utf-8"))
        salida = Path("/tmp/opencode/prueba-agente")
        informe = agente.trabajar(datos, salida)
        self.assertTrue(informe["ok"], informe["problemas"])
        self.assertTrue((salida / "index.html").is_file())
        self.assertEqual([p["accion"] for p in informe["pasos"]],
                         ["leer datos", "generar web", "revisar en sandbox"])
        self.assertTrue(all(p["ok"] for p in informe["pasos"]))
        self.assertIn("ejecucion", informe)
        self.assertIn("bwrap", informe["ejecucion"]["orden"][0])

    def test_frena_si_faltan_datos(self):
        informe = agente.trabajar({"nombre": "Solo nombre"}, Path("/tmp/opencode/prueba-vacia"))
        self.assertFalse(informe["ok"])
        self.assertEqual(informe["pasos"][0]["accion"], "leer datos")
        self.assertFalse(informe["pasos"][0]["ok"])
        self.assertIn("tel", " ".join(informe["problemas"]))

    def test_todos_los_ejemplos_se_generan_y_pasan_la_revision(self):
        """Cada JSON de `negocios/` tiene que salir bien: es lo que se publica."""
        ejemplos = sorted((RAIZ / "negocios").glob("*.json"))
        self.assertGreaterEqual(len(ejemplos), 4)
        for fichero in ejemplos:
            datos = json.loads(fichero.read_text(encoding="utf-8"))
            informe = agente.trabajar(datos, Path("/tmp/opencode/prueba-ejemplos") / fichero.stem)
            self.assertTrue(informe["ok"], f"{fichero.name}: {informe['problemas']}")

    def test_el_titulo_de_seccion_se_adapta_al_sector(self):
        """Una peluquería no tiene «carta»: tiene «servicios y precios»."""
        datos = json.loads((RAIZ / "negocios" / "peluqueria-luz.json").read_text(encoding="utf-8"))
        salida = Path("/tmp/opencode/prueba-titulo")
        agente.trabajar(datos, salida)
        html = (salida / "index.html").read_text(encoding="utf-8")
        self.assertIn("<h2>Servicios y precios</h2>", html)
        self.assertIn('href="#carta">Servicios</a>', html)
        self.assertNotIn("Nuestra carta", html)

    def test_la_muestra_avisa_y_no_se_indexa(self):
        """Una muestra es para un negocio real que aún no ha dicho que sí:
        tiene que avisar de que es una muestra y no salir en Google."""
        datos = json.loads(EJEMPLO.read_text(encoding="utf-8"))
        del datos["demo"]
        datos["muestra"] = True
        salida = Path("/tmp/opencode/prueba-muestra")
        agente.trabajar(datos, salida)
        html = (salida / "index.html").read_text(encoding="utf-8")
        self.assertIn("Muestra gratuita", html)
        self.assertIn('<meta name="robots" content="noindex">', html)
        self.assertNotIn("Web de ejemplo", html)

    def test_un_negocio_de_verdad_no_lleva_aviso_ni_noindex(self):
        """La web que se entrega al cliente que paga va limpia."""
        datos = json.loads(EJEMPLO.read_text(encoding="utf-8"))
        del datos["demo"]
        salida = Path("/tmp/opencode/prueba-cliente")
        agente.trabajar(datos, salida)
        html = (salida / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("aviso-demo", html.split("</style>", 1)[1])
        self.assertNotIn("noindex", html)
        self.assertNotIn("inventados", html)


if __name__ == "__main__":
    unittest.main()
