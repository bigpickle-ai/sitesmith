"""Pruebas de la mini aplicación web.

    cd ~/sitios/agente && python3 -m unittest -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import servidor  # noqa: E402
from sandbox import bwrap_disponible  # noqa: E402

BUENOS = {
    "nombre": "Bar La Encina",
    "lema": "Tapas y cocina casera",
    "direccion": "Calle Vista Alegre, 13 - Ponferrada",
    "telefono": "987 000 000",
    "whatsapp": "34600000000",
}


class SlugTest(unittest.TestCase):
    def test_quita_acentos_y_simbolos(self):
        self.assertEqual(servidor.nombre_a_slug("Bar La Encina"), "bar-la-encina")
        self.assertEqual(servidor.nombre_a_slug("Café Ñandú / 2º"), "cafe-nandu-2o")
        self.assertEqual(servidor.nombre_a_slug("¡¡!!"), "negocio")
        self.assertLessEqual(len(servidor.nombre_a_slug("x" * 90)), 40)


@unittest.skipUnless(bwrap_disponible(), "bubblewrap no está instalado")
class ServidorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporal = tempfile.TemporaryDirectory(prefix="sitios-web-")
        cls.anterior = servidor.Servidor.raiz
        cls.http = servidor.crear(0, raiz=Path(cls.temporal.name))
        cls.base = f"http://127.0.0.1:{cls.http.server_port}"
        cls.hilo = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.hilo.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        servidor.Servidor.raiz = cls.anterior
        cls.temporal.cleanup()

    # -- ayudas ------------------------------------------------------------

    def pedir(self, ruta: str, datos: dict | None = None) -> tuple[int, str]:
        if datos is None:
            peticion = urllib.request.Request(self.base + ruta)
        else:
            cuerpo = urllib.parse.urlencode(datos).encode()
            peticion = urllib.request.Request(self.base + ruta, data=cuerpo)
        try:
            with urllib.request.urlopen(peticion, timeout=30) as respuesta:
                return respuesta.status, respuesta.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode("utf-8", "replace")

    # -- pruebas -----------------------------------------------------------

    def test_1_el_formulario_se_ve(self):
        estado, cuerpo = self.pedir("/")
        self.assertEqual(estado, 200)
        self.assertIn("Generar la web", cuerpo)
        for campo in ("nombre", "lema", "direccion", "telefono", "whatsapp"):
            self.assertIn(f'name="{campo}"', cuerpo)

    def test_2_genera_y_revisa(self):
        estado, cuerpo = self.pedir("/generar", BUENOS)
        self.assertEqual(estado, 200)
        self.assertIn("Todo correcto", cuerpo)
        self.assertIn("revisar en sandbox", cuerpo)
        salida = servidor.Servidor.raiz / "bar-la-encina"
        self.assertTrue((salida / "index.html").is_file())
        informe = json.loads((salida / "informe.json").read_text(encoding="utf-8"))
        self.assertTrue(informe["ok"], informe["problemas"])
        self.assertEqual(informe["negocio"], "Bar La Encina")

    def test_3_la_vista_previa_y_el_informe_se_sirven(self):
        self.pedir("/generar", BUENOS)
        estado, cuerpo = self.pedir("/vista/bar-la-encina/")
        self.assertEqual(estado, 200)
        self.assertIn("<main>", cuerpo)
        estado, cuerpo = self.pedir("/informe/bar-la-encina/informe.json")
        self.assertEqual(estado, 200)
        self.assertEqual(json.loads(cuerpo)["negocio"], "Bar La Encina")

    def test_4_faltan_campos(self):
        incompletos = dict(BUENOS, telefono="")
        estado, cuerpo = self.pedir("/generar", incompletos)
        self.assertEqual(estado, 400)
        self.assertIn("Falta rellenar", cuerpo)
        self.assertIn("Teléfono", cuerpo)
        self.assertIn('value="Bar La Encina"', cuerpo)   # no pierde lo escrito

    def test_5_rutas_traviesas_y_desconocidas(self):
        for ruta in ("/vista/../sistema/", "/vista/..%2f..%2fetc/",
                     "/vista/no-existe/", "/inventada"):
            estado, _ = self.pedir(ruta)
            self.assertIn(estado, (404,), f"{ruta} devolvió {estado}")

    def test_6_cuerpo_demasiado_grande(self):
        estado, _ = self.pedir("/generar", dict(BUENOS, nombre="x" * (servidor.LIMITE_CUERPO)))
        self.assertEqual(estado, 413)

    def test_7_solo_atiende_local(self):
        self.assertEqual(self.http.server_address[0], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
