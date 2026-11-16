import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import hashlib
import re

# === CONFIGURACIÓN DEL EQUIPO ===
TEAM_NAME = 'C.D. Virgen Inmaculada "F"'
TEAM_CODE = "22903000"
CLUB_CODE = "1313"
TEMPORADA = "22"
COMPETICION = "22880369"
GRUPO = "23105615"

OUTPUT_FILE = "virgen-inmaculada-f.ics"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
}

def make_uid(date_str, teams):
    """Genera un UID estable para que Google Calendar actualice en vez de duplicar"""
    raw = f"{date_str}-{teams}"
    return hashlib.md5(raw.encode()).hexdigest() + "@asturfutbol-cal"

def parse_matches_from_list(html):
    """Intenta extraer partidos de la página de listado"""
    soup = BeautifulSoup(html, "lxml")
    matches = []
    
    # Buscamos filas de tabla que contengan el nombre del equipo
    text = soup.get_text(" ", strip=True)
    
    # Patrón aproximado basado en lo que vimos
    # Ejemplo: 21-11-2026 ... C.D. Virgen Inmaculada "F" 5 As F.S. "A" ... 11:45
    pattern = re.compile(
        r"(\d{2}-\d{2}-\d{4}).{0,80}?" + re.escape(TEAM_NAME) + r".{0,80}?(\d{1,2}:\d{2})",
        re.IGNORECASE | re.DOTALL
    )
    
    for match in pattern.finditer(text):
        date_str = match.group(1)
        time_str = match.group(2)
        # Intentamos sacar el rival de forma simple
        snippet = match.group(0)
        rival = "Rival por confirmar"
        if "vs" in snippet.lower() or "-" in snippet:
            parts = re.split(r"vs|–|-", snippet, flags=re.IGNORECASE)
            for p in parts:
                if TEAM_NAME.lower() not in p.lower() and len(p.strip()) > 5:
                    rival = p.strip()[:60]
                    break
        
        matches.append({
            "date": date_str,
            "time": time_str,
            "rival": rival,
            "campo": "Ver en Asturfutbol",
            "raw": snippet[:120]
        })
    
    return matches

def fetch_upcoming_matches():
    """Intenta varias estrategias para obtener partidos"""
    all_matches = []
    
    # Estrategia 1: Listado de partidos con rangos de fechas
    base_url = "https://www.asturfutbol.es/pnfg/NPcd/NFG_LstPartidos"
    
    today = datetime.now()
    for i in range(0, 60, 14):  # Próximos 60 días en trozos de 14
        start = today + timedelta(days=i)
        end = start + timedelta(days=13)
        
        params = {
            "cod_primaria": "1000121",
            "Consulta": "1",
            "Sch_Fecha_Desde": start.strftime("%d-%m-%Y"),
            "Sch_Fecha_Desde_input": start.strftime("%Y-%m-%d"),
            "Sch_Fecha_Hasta": end.strftime("%d-%m-%Y"),
            "Sch_Fecha_Hasta_input": end.strftime("%Y-%m-%d"),
            "Sch_Cod_Temporada": TEMPORADA,
            "Sch_Clave_Acceso_Club": CLUB_CODE,
            "Club": CLUB_CODE,
            "Sch_Codigo_Equipo": TEAM_CODE,
            "NPcd_PageLines": "50"
        }
        
        try:
            r = requests.get(base_url, params=params, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                found = parse_matches_from_list(r.text)
                all_matches.extend(found)
                print(f"Rango {start.date()} → {end.date()}: {len(found)} partidos")
        except Exception as e:
            print(f"Error en rango {start.date()}: {e}")
    
    # Estrategia 2: Páginas de jornada (más estable a veces)
    for jornada in range(1, 25):
        url = (
            f"https://www.asturfutbol.es/pnfg/NPcd/NFG_CmpJornada"
            f"?cod_primaria=1000120&CodCompeticion={COMPETICION}"
            f"&CodGrupo={GRUPO}&CodTemporada={TEMPORADA}"
            f"&CodJornada={jornada}&Sch_Tipo_Juego=3&cod_agrupacion=1"
        )
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200 and TEAM_NAME in r.text:
                found = parse_matches_from_list(r.text)
                all_matches.extend(found)
                print(f"Jornada {jornada}: encontrado")
        except Exception as e:
            print(f"Error jornada {jornada}: {e}")
    
    # Quitar duplicados
    unique = {}
    for m in all_matches:
        key = f"{m['date']}-{m['time']}"
        unique[key] = m
    
    return list(unique.values())

def generate_ics(matches):
    """Genera el contenido del archivo .ics"""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Asturfutbol Cal//Virgen Inmaculada F//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:C.D. Virgen Inmaculada F - 3ª Benjamín",
        "X-WR-TIMEZONE:Europe/Madrid",
    ]
    
    for m in matches:
        try:
            dt = datetime.strptime(f"{m['date']} {m['time']}", "%d-%m-%Y %H:%M")
            dt_end = dt + timedelta(hours=1, minutes=15)  # Duración estimada
            
            dtstart = dt.strftime("%Y%m%dT%H%M%S")
            dtend = dt_end.strftime("%Y%m%dT%H%M%S")
            
            uid = make_uid(m['date'], m.get('rival', ''))
            summary = f"{TEAM_NAME} vs {m.get('rival', 'Rival')}"
            location = m.get('campo', '')
            
            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTART;TZID=Europe/Madrid:{dtstart}",
                f"DTEND;TZID=Europe/Madrid:{dtend}",
                f"SUMMARY:{summary}",
                f"LOCATION:{location}",
                f"DESCRIPTION:Partido de 3ª Benjamín - Generado automáticamente desde Asturfutbol",
                "END:VEVENT",
            ])
        except Exception as e:
            print(f"Error generando evento: {e}")
    
    lines.append("END:VCALENDAR")
    return "\n".join(lines)

def main():
    print("Buscando partidos de", TEAM_NAME)
    matches = fetch_upcoming_matches()
    print(f"Total partidos únicos encontrados: {len(matches)}")
    
    for m in matches:
        print(f"  → {m['date']} {m['time']} | {m.get('rival', '')}")
    
    ics_content = generate_ics(matches)
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(ics_content)
    
    print(f"Archivo generado: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
