import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# === CONFIGURACIÓN DEL EQUIPO ===
TEAM_NAME = 'C.D. Virgen Inmaculada "F"'
TEAM_CODE = "22903000"
TEMPORADA = "22"
COMPETICION = "22880369"
GRUPO = "23105615"
NUM_JORNADAS = 30
OUTPUT_FILE = "virgen-inmaculada-f.ics"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
}

DATE_RE = re.compile(r"\d{2}-\d{2}-\d{4}")
TIME_RE = re.compile(r"\d{1,2}:\d{2}")
RUIDO_RE = re.compile(r"^[\d\s:\-–]*$")


def norm(s):
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def fetch_jornada(j):
    url = (
        "https://www.asturfutbol.es/pnfg/NPcd/NFG_CmpJornada"
        f"?cod_primaria=1000120&CodCompeticion={COMPETICION}"
        f"&CodGrupo={GRUPO}&CodTemporada={TEMPORADA}"
        f"&CodJornada={j}&Sch_Tipo_Juego=3&cod_agrupacion=1"
    )
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")


def bloques_partido(soup):
    """Elementos más pequeños que contienen a nuestro equipo y una sola fecha."""
    candidatos = []
    for tag in soup.find_all(True):
        flat = norm(tag.get_text(" ", strip=True))
        if TEAM_NAME in flat and len(DATE_RE.findall(flat)) == 1:
            candidatos.append(tag)
    ids = {id(t) for t in candidatos}
    return [t for t in candidatos if not any(id(d) in ids for d in t.find_all(True))]


def parse_block(tag, jornada):
    flat = norm(tag.get_text(" ", strip=True))
    tokens = [norm(t) for t in tag.get_text("|", strip=True).split("|")]
    tokens = [t for t in tokens if t]

    date_str = DATE_RE.search(flat).group(0)
    resto = flat[flat.find(date_str) + len(date_str):].strip()
    tm = TIME_RE.match(resto)
    time_str = tm.group(0) if tm else None

    di = next(i for i, t in enumerate(tokens) if date_str in t)
    antes = [t for t in tokens[:di] if not RUIDO_RE.match(t) and t != "Descansa"]
    despues = [t for t in tokens[di + 1:] if not RUIDO_RE.match(t)]

    en_casa = flat.find(TEAM_NAME) < flat.find(date_str)
    if en_casa:
        rival = despues[0] if despues else ""
    else:
        rival = antes[-1] if antes else ""
    campo = despues[1] if len(despues) > 1 else ""

    if not rival or TEAM_NAME in rival or len(rival) > 60:
        rival = "Rival por confirmar"
    if campo.startswith("Árbitro"):
        campo = ""

    return {
        "jornada": jornada,
        "date": date_str,
        "time": time_str,
        "rival": rival,
        "campo": campo,
        "en_casa": en_casa,
        "tokens": tokens,
    }


def esc(s):
    return (
        s.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


VTIMEZONE = [
    "BEGIN:VTIMEZONE",
    "TZID:Europe/Madrid",
    "BEGIN:DAYLIGHT",
    "TZOFFSETFROM:+0100",
    "TZOFFSETTO:+0200",
    "TZNAME:CEST",
    "DTSTART:19700329T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
    "END:DAYLIGHT",
    "BEGIN:STANDARD",
    "TZOFFSETFROM:+0200",
    "TZOFFSETTO:+0100",
    "TZNAME:CET",
    "DTSTART:19701025T030000",
    "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
    "END:STANDARD",
    "END:VTIMEZONE",
]


def generate_ics(partidos):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Asturfutbol Cal//Virgen Inmaculada F//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:C.D. Virgen Inmaculada F - 3ª Benjamín",
        "X-WR-TIMEZONE:Europe/Madrid",
    ]
    lines += VTIMEZONE

    for p in partidos:
        d = datetime.strptime(p["date"], "%d-%m-%Y")
        if p["en_casa"]:
            local, visitante = TEAM_NAME, p["rival"]
        else:
            local, visitante = p["rival"], TEAM_NAME
        summary = f"J{p['jornada']}: {local} vs {visitante}"

        lines += [
            "BEGIN:VEVENT",
            f"UID:j{p['jornada']}-{TEAM_CODE}@asturfutbol-cal",
            "DTSTAMP:20260101T000000Z",
        ]
        if p["time"]:
            dt = datetime.strptime(f"{p['date']} {p['time']}", "%d-%m-%Y %H:%M")
            fin = dt + timedelta(hours=1, minutes=15)
            lines += [
                f"DTSTART;TZID=Europe/Madrid:{dt.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND;TZID=Europe/Madrid:{fin.strftime('%Y%m%dT%H%M%S')}",
            ]
        else:
            summary += " (hora por confirmar)"
            lines += [
                f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}",
            ]
        lines += [
            f"SUMMARY:{esc(summary)}",
            f"LOCATION:{esc(p['campo'])}",
            f"DESCRIPTION:{esc('Jornada ' + str(p['jornada']) + ' - 3ª Benjamín. Generado automáticamente desde Asturfutbol')}",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main():
    print("Buscando partidos de", TEAM_NAME)
    partidos = []
    for j in range(1, NUM_JORNADAS + 1):
        try:
            soup = fetch_jornada(j)
            bloques = bloques_partido(soup)
            if not bloques:
                print(f"Jornada {j}: sin partido (descansa o aún no publicado)")
            else:
                p = parse_block(bloques[0], j)
                partidos.append(p)
                print(
                    f"Jornada {j}: {p['date']} {p['time'] or '--:--'} | "
                    f"{'CASA' if p['en_casa'] else 'FUERA'} | {p['rival']} | {p['campo']}"
                )
                print("    tokens:", p["tokens"])
        except Exception as e:
            print(f"Jornada {j}: ERROR {e}")
        time.sleep(0.5)

    print(f"Total partidos encontrados: {len(partidos)}")
    if not partidos:
        raise SystemExit("No se encontraron partidos; no se modifica el calendario.")

    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        f.write(generate_ics(partidos))
    print(f"Archivo generado: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
