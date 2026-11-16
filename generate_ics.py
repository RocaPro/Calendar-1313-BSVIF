import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
}

def mostrar(etiqueta, r):
    print("=" * 50)
    print(etiqueta)
    print("Estado:", r.status_code, "| bytes:", len(r.text))
    html = r.text
    print("'Virgen' en el HTML:", "Virgen" in html)
    print("'&quot;' en el HTML:", "&quot;" in html)
    texto = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    print("TEXTO (primeros 800):")
    print(texto[:800])
    i = texto.find("Virgen")
    if i >= 0:
        print("ALREDEDOR DE VIRGEN:")
        print(texto[max(0, i - 200):i + 400])

def probar(etiqueta, url, params=None):
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=20)
        mostrar(etiqueta, r)
    except Exception as e:
        print(etiqueta, "ERROR:", e)

hoy = datetime.now()
fin = hoy + timedelta(days=13)
probar(
    "LISTADO",
    "https://www.asturfutbol.es/pnfg/NPcd/NFG_LstPartidos",
    {
        "cod_primaria": "1000121",
        "Consulta": "1",
        "Sch_Fecha_Desde": hoy.strftime("%d-%m-%Y"),
        "Sch_Fecha_Desde_input": hoy.strftime("%Y-%m-%d"),
        "Sch_Fecha_Hasta": fin.strftime("%d-%m-%Y"),
        "Sch_Fecha_Hasta_input": fin.strftime("%Y-%m-%d"),
        "Sch_Cod_Temporada": "22",
        "Sch_Clave_Acceso_Club": "1313",
        "Club": "1313",
        "Sch_Codigo_Equipo": "22903000",
        "NPcd_PageLines": "50",
    },
)

for j in (1, 10):
    probar(
        f"JORNADA {j}",
        "https://www.asturfutbol.es/pnfg/NPcd/NFG_CmpJornada"
        f"?cod_primaria=1000120&CodCompeticion=22880369"
        f"&CodGrupo=23105615&CodTemporada=22"
        f"&CodJornada={j}&Sch_Tipo_Juego=3&cod_agrupacion=1",
    )
