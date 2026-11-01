# SiteSmith

Genera la web completa de un negocio local a partir de un archivo de texto
(JSON) y la deja lista para publicar.

**Demo en vivo:** <https://bigpickle-ai.github.io/sitesmith-demo/>
(negocio inventado, con aviso de que es un ejemplo).

Un solo comando produce **un único archivo `index.html`**: sin base de datos,
sin cookies, sin JavaScript, sin dependencias. Funciona en GitHub Pages, en
cualquier hosting o abriéndolo desde el propio ordenador.

## Uso

```bash
cd ~/sitios
python3 sitio.py negocios/bar-ejemplo.json
# -> salidas/bar-ejemplo/index.html
```

Se puede elegir la carpeta de salida:

```bash
python3 sitio.py negocios/bar-ejemplo.json salidas/mi-bar
```

## Qué incluye la web

- Portada con nombre y lema del negocio.
- Menú de navegación fijo con las secciones que existan.
- **Carta** por secciones, con descripción y precio de cada plato.
- **Horario** en tabla, con los días cerrados marcados.
- **Dónde estamos**: dirección, enlace al mapa y botón de llamada.
- Botón de **WhatsApp** en la portada y flotante en la esquina.
- **Datos para Google** (JSON-LD de tipo `LocalBusiness`): nombre, teléfono,
  dirección y horarios, para que el buscador lo entienda.
- Modo claro y **modo oscuro** automáticos, según el sistema.
- Colores accesibles: el texto siempre contrasta con el fondo (se comprueba
  la luminancia y se elige blanco o negro, y el color de la marca se aclara
  en modo oscuro si hace falta).
- Letra grande, botones amplios y foco visible con el teclado.
- Aviso legal: no usa cookies ni recoge datos.

## El archivo del negocio

Todo lo que necesita saber el generador está en el JSON. Solo `nombre` es
obligatorio; el resto de secciones desaparecen si no se ponen.

```json
{
  "nombre": "Bar La Encina",
  "lema": "Cocina casera del Bierzo en el centro de Ponferrada.",
  "sector": "Bar de tapas",
  "tipo_negocio": "BarOrPub",
  "titular": "Nombre fiscal del titular",
  "telefono": "987 000 000",
  "whatsapp": "34600000000",
  "direccion": "Calle del Reloj, 12, 24401 Ponferrada, León",
  "mapa": "",
  "colores": { "acento": "#7a1f1f" },
  "nota_horario": "En agosto cerramos del 10 al 20.",
  "horario": [["Lunes", "Cerrado"], ["Martes", "08:00 – 16:00"]],
  "carta": [
    {
      "nombre": "Para picar",
      "platos": [
        { "nombre": "Patatas bravas", "descripcion": "Con alioli", "precio": "5,50 €" }
      ]
    }
  ]
}
```

Notas de los campos:

- `whatsapp`: solo números, con prefijo de país y **sin** `+` ni espacios.
- `mapa`: si se deja vacío, se construye un enlace de búsqueda con la
  dirección.
- `colores.acento`: color de la marca. Se comprueba el contraste; en modo
  oscuro se aclara solo si hace falta.
- `tipo_negocio`: tipo de schema.org (`BarOrPub`, `Restaurant`, `HairSalon`,
  `Bakery`, `Store`…). Por defecto `LocalBusiness`.
- `horario`: pares `["Día", "horas"]`. Si las horas son «Cerrado», el día se
  marca y no se manda a Google como horario de apertura.

## Comprobar el resultado

```bash
# abrir la web en el navegador
xdg-open ~/sitios/salidas/bar-ejemplo/index.html

# o servirla en local, para probar en el móvil
cd ~/sitios/salidas/bar-ejemplo && python3 -m http.server 8080
```

Antes de entregar una web a un cliente conviene revisar:

1. Que el teléfono y el WhatsApp funcionan (llamar y escribir de prueba).
2. Que la dirección del mapa lleva al sitio correcto.
3. Que los precios y el horario están al día.
4. Que el nombre del `titular` del aviso legal es el real.

## Estructura

```
sitios/
├── sitio.py                  generador (Python 3, sin dependencias)
├── negocios/                 un JSON por negocio
│   └── bar-ejemplo.json
└── salidas/
    └── bar-ejemplo/
        └── index.html        web lista para publicar
```

## Publicar en GitHub Pages

```bash
cd ~/sitios/salidas/bar-ejemplo
git init -b main
git add index.html
git commit -m "Web de Bar La Encina"
gh repo create bigpickle-ai/bar-la-encina --public --source=. --push
gh api -X POST repos/bigpickle-ai/bar-la-encina/pages \
  -f 'source[branch]=main' -f 'source[path]=/'
```

Queda en `https://bigpickle-ai.github.io/bar-la-encina/`.

## Requisitos

Python 3.8 o superior. Nada más: no usa librerías externas.
