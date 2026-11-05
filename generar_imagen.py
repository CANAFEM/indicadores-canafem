import json
import os
import sys
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

TIPOS = {
    158: "DÓLAR",
    159: "UDIS",
    165: "TIIE 28 DÍAS",
    166: "TIIE 91 DÍAS",
    174: "TIIE 182 DÍAS",
    175: "TIIE DE FONDEO",
}
FUENTE = "/usr/share/fonts/truetype/liberation/LiberationSans-%s.ttf"
VERDE, OSCURO, FONDO, LINEA = (21, 110, 62), (35, 35, 35), (240, 240, 240), (205, 205, 205)


def leer_datos(hoy):
    if len(sys.argv) > 1:  # Solo para pruebas con un archivo local
        with open(sys.argv[1], encoding="utf-8") as archivo:
            return json.load(archivo)
    url = f"https://sidof.segob.gob.mx/dof/sidof/indicadores/{hoy}"
    peticion = urllib.request.Request(url, headers={"User-Agent": "indicadores-boletin"})
    with urllib.request.urlopen(peticion, timeout=60) as respuesta:
        return json.load(respuesta)


def dibujar(fecha, valores, destinos):
    escala = 2
    ancho, alto = 480 * escala, 280 * escala
    letra = lambda estilo, tam: ImageFont.truetype(FUENTE % estilo, tam * escala)
    imagen = Image.new("RGB", (ancho, alto), FONDO)
    lienzo = ImageDraw.Draw(imagen)
    lienzo.rectangle((0, 0, ancho - 1, alto - 1), outline=LINEA, width=escala)
    lienzo.rectangle((0, 0, ancho, 44 * escala), fill=VERDE)
    lienzo.text((22 * escala, 12 * escala), "INDICADORES", font=letra("Bold", 20), fill="white")
    lienzo.text((22 * escala, 58 * escala), f"Tipo de Cambio y Tasas al {fecha}",
                font=letra("Bold", 17), fill=OSCURO)
    for i, (codigo, nombre) in enumerate(TIPOS.items()):
        x = (22 if i % 2 == 0 else 250) * escala
        y = (92 + (i // 2) * 54) * escala
        lienzo.text((x, y), nombre, font=letra("Bold", 15), fill=VERDE)
        lienzo.text((x, y + 19 * escala), valores[codigo], font=letra("Regular", 20), fill=OSCURO)
    lienzo.text((ancho - 22 * escala, 258 * escala), "Fuente: Diario Oficial de la Federación",
                font=letra("Regular", 11), fill=(95, 95, 95) anchor="ra")
    for destino in destinos:
        imagen.save(destino, optimize=True)


def main():
    hoy = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%d-%m-%Y")
    lista = leer_datos(hoy).get("ListaIndicadores") or []
    if not lista:
        print("Sin datos para hoy; se conserva la imagen anterior.")
        return
    valores = {dato["codTipoIndicador"]: dato["valor"] for dato in lista}
    faltantes = [nombre for codigo, nombre in TIPOS.items() if not valores.get(codigo)]
    if faltantes:
        sys.exit("Faltan indicadores: " + ", ".join(faltantes))
    fecha = lista[0]["fecha"]
    dia, mes, anio = fecha.split("-")
    os.makedirs("imagenes", exist_ok=True)
    dibujar(f"{dia}/{mes}/{anio}", valores,
            ["imagenes/indicadores.png", f"imagenes/indicadores-{anio}-{mes}-{dia}.png"])
    print("Imagen creada:", fecha)


if __name__ == "__main__":
    main()
