import html
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

DIAS_A_REVISAR = 7
LISTAS = ("NotasMatutinas", "NotasVespertinas", "NotasExtraordinarias")
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
         "Septiembre", "Octubre", "Noviembre", "Diciembre"]

ECONOMIA_TEMAS = [
    "comercio exterior", "arancel", "impuestos generales de importacion", "cuota compensatoria",
    "cuotas compensatorias", "antidumping", "examen de vigencia", "lamina rolada",
    "laminas roladas", "lamina de acero", "hierro", "acero", "aluminio", "hojalata",
    "norma oficial mexicana", "nom-",
]
DECRETO_TEMAS = [
    "industria", "industrial", "economia", "economica", "economico", "comercio exterior",
    "arancel", "impuestos generales de importacion", "inversion extranjera",
]
SALUD_NORMAS = ["nom-120", "nom-130", "nom-251"]
EXCLUIR = ["construccion", "edificacion", "edificaciones", "cemento", "concreto"]


def simple(texto):
    sin_acentos = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn").lower()


def contiene(texto, frases):
    return any(re.search(r"(?<![a-z0-9])" + re.escape(frase), texto) for frase in frases)


def clasificar(nota):
    titulo = simple(nota.get("titulo"))
    organismo = simple(f"{nota.get('codOrgaDos') or ''} {nota.get('nombreCodOrgaUno') or ''}")
    if not titulo:
        return None
    if "salud" in organismo:
        return "Salud" if contiene(titulo, SALUD_NORMAS) else None
    if "presidencia" in organismo or titulo.startswith("decreto"):
        if contiene(titulo, DECRETO_TEMAS) and not contiene(titulo, EXCLUIR):
            return "Presidencia / decretos"
    if "economia" in organismo:
        if contiene(titulo, ECONOMIA_TEMAS) and not contiene(titulo, EXCLUIR):
            return "Economía"
    return None


def fecha_larga(fecha):
    dia, mes, anio = fecha.split("-")
    return f"{int(dia)}-{MESES[int(mes) - 1]}-{anio}"


def nombre_organismo(nombre):
    conocidos = {
        "secretaria de economia": "Secretaría de Economía",
        "secretaria de salud": "Secretaría de Salud",
        "presidencia de la republica": "Presidencia de la República",
    }
    return conocidos.get(simple(nombre).strip(), (nombre or "Diario Oficial").strip().title())


def enlace(nota):
    dia, mes, anio = nota["fecha"].split("-")
    return (f"https://www.dof.gob.mx/nota_detalle.php?codigo={nota['codNota']}"
            f"&fecha={dia}/{mes}/{anio}")


def cuadro(nota):
    titulo = html.escape(re.sub(r"^\S+", lambda m: m.group().upper(), nota["titulo"].strip()))
    pie = html.escape(f"{fecha_larga(nota['fecha'])} {nombre_organismo(nota.get('codOrgaDos') or nota.get('nombreCodOrgaUno'))}")
    url = html.escape(enlace(nota), quote=True)
    return (
        '<table role="presentation" width="94%" align="center" cellpadding="0" cellspacing="0" border="0" '
        'style="background:#B0B0B0;border:1px solid #000000;margin-bottom:12px;">\n'
        '  <tr><td style="padding:16px 18px;font-family:Arial,sans-serif;font-size:15px;'
        f'line-height:22px;color:#000000;text-align:justify;">{titulo}</td></tr>\n'
        '  <tr><td align="right" style="padding:0 18px 16px;font-family:Arial,sans-serif;'
        f'font-size:15px;font-style:italic;"><a href="{url}" style="color:#006F7A;">{pie}</a>'
        '</td></tr>\n</table>'
    )


def informe(notas, inicio, fin):
    encabezado = f"Revisión del DOF del {fecha_larga(inicio)} al {fecha_larga(fin)}."
    if not notas:
        return encabezado + "\n\nNo se encontraron notas de los segmentos de CANAFEM."
    partes = [encabezado + f"\n\n**{len(notas)} candidata(s).** Copia el código de las que elijas."]
    for nota in notas:
        partes.append(
            f"---\n### {nota['segmento']} · {fecha_larga(nota['fecha'])}\n\n{nota['titulo'].strip()}\n\n"
            f"[Abrir nota]({enlace(nota)})\n\n```html\n{cuadro(nota)}\n```"
        )
    return "\n\n".join(partes)


def pedir(url, datos=None, encabezados=None):
    peticion = urllib.request.Request(url, data=datos, headers=encabezados or {})
    with urllib.request.urlopen(peticion, timeout=60) as respuesta:
        return json.load(respuesta)


def notas_del_dia(fecha):
    url = f"https://sidof.segob.gob.mx/dof/sidof/notas/{fecha}"
    try:
        datos = pedir(url, encabezados={"User-Agent": "revision-boletin"})
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return []
        raise
    return [n for lista in LISTAS for n in (datos.get(lista) or [])]


def crear_aviso(titulo, cuerpo):
    repo, token = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"]
    pedir(f"https://api.github.com/repos/{repo}/issues",
          json.dumps({"title": titulo, "body": cuerpo}).encode("utf-8"),
          {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
           "Content-Type": "application/json", "User-Agent": "revision-boletin"})


def main():
    hoy = datetime.now(ZoneInfo("America/Mexico_City"))
    fechas = [(hoy - timedelta(days=d)).strftime("%d-%m-%Y") for d in range(DIAS_A_REVISAR, -1, -1)]
    encontradas, revisadas, vistas = [], 0, set()
    for fecha in fechas:
        try:
            notas = notas_del_dia(fecha)
        except Exception as error:
            print("Error al consultar", fecha, error)
            continue
        revisadas += 1
        for nota in notas:
            segmento = clasificar(nota)
            if segmento and nota["codNota"] not in vistas:
                vistas.add(nota["codNota"])
                nota.setdefault("fecha", fecha)
                nota["segmento"] = segmento
                encontradas.append(nota)
    if revisadas == 0:
        sys.exit("No se pudo consultar el DOF.")
    cuerpo = informe(encontradas[:40], fechas[0], fechas[-1])
    print(cuerpo)
    crear_aviso(f"Notas del DOF: {fecha_larga(fechas[-1])}", cuerpo)


if __name__ == "__main__":
    main()
