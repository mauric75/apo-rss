#!/usr/bin/env python3
import json, logging, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from mutagen.mp3 import MP3, HeaderNotFoundError
from dateutil import parser as date_parser
try:
    import yt_dlp
    HAS_YT_DLP = True
except ImportError:
    HAS_YT_DLP = False

DATA_FILE = Path("episodes.json")
LOG_FILE = Path("scrape.log")
SESSION_TIMEOUT = 30
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5

TERMS_PATTERNS = [
    r"Alejandro\s+Apo", r"Dondequiera\s+que\s+estés", r"Dondequiera\s+que\s+estes",
    r"Un\s+Señor\s+Cuento", r"Un\s+Seor\s+Cuento", r"Todo\s+con\s+Afecto", 
    r"Los\s+cuentos\s+de\s+Apo", r"cuentos\s+de\s+Apo"
]

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"})

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] %(message)s", 
    handlers=[logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"), logging.StreamHandler()]
)
log = logging.getLogger(__name__)
COVER_URL = "https://raw.githubusercontent.com/mauric75/apo-rss/main/cover.jpg"

# --- Utilidades ---
def safe_get(url, timeout=SESSION_TIMEOUT):
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            r = session.get(url, timeout=timeout, allow_redirects=True)
            r.raise_for_status()
            return r
        except requests.RequestException as exc:
            log.warning("Intento %d/%d fallo para %s", attempt, RETRY_ATTEMPTS, url)
            if attempt < RETRY_ATTEMPTS: time.sleep(RETRY_DELAY)
    return None

def verify_mp3(url):
    duracion = 0.0
    try:
        r = session.get(url, timeout=60, stream=True, allow_redirects=True)
        r.raise_for_status()
        chunk = b""
        for i, data in enumerate(r.iter_content(chunk_size=65536)):
            chunk += data
            if len(chunk) > 524288 or i > 8: break
        if chunk:
            mp3 = MP3()
            mp3.info = MP3._read_info(chunk)
            duracion = mp3.info.length
        return True, duracion
    except: return True, duracion

def text_clean(html_str):
    if not html_str: return ""
    return BeautifulSoup(html_str, "lxml").get_text(separator=" ", strip=True)

# --- Filtros Inteligentes ---
STORY_CONTEXT_PATTERNS = [r"cuento", r"relato", r"narr[oaó]", r"\blee\b", r"leyendo", r"voz\s+de\s+apo"]
INTERVIEW_TITLE_PATTERNS = [
    r"entrevista", r"dialog[oó]\s+con", r"habl[oó]\s+con", r"convers[oó]\s+con",
    r"mano\s+a\s+mano", r"cara\s+a\s+cara", r"reportaje\s+a", r"charla\s+con",
]
# Titulo tipo "'El Pampa' de Roberto Fontanarrosa": el patron real y confiable
# de un cuento genuino (obra entre comillas + atribucion de autoria).
STORY_TITLE_STRONG_RE = re.compile(r'[\'"\u201c][^\'"\u201d]{3,90}[\'"\u201d]\s*,?\s*de\s+[A-ZÁÉÍÓÚÑ]')
# Titulo tipo 'Alejandro Apo: "Estoy cumpliendo 68 anos..."': cita/declaracion
# periodistica, nunca es el titulo de un cuento narrado.
QUOTE_TITLE_RE = re.compile(r':\s*[\'"\u201c]')

def is_interview_title(titulo):
    t = titulo.lower()
    return any(re.search(p, t, re.IGNORECASE) for p in INTERVIEW_TITLE_PATTERNS)

def matches_apo(text, titulo=""):
    t = text.lower()
    has_apo = any(re.search(p, t, re.IGNORECASE) for p in TERMS_PATTERNS)
    if not has_apo: return False
    if titulo:
        if is_interview_title(titulo): return False
        if STORY_TITLE_STRONG_RE.search(titulo): return True
        if QUOTE_TITLE_RE.search(titulo): return False
        if any(re.search(p, titulo.lower(), re.IGNORECASE) for p in TERMS_PATTERNS):
            # Menciona su nombre pero no tiene forma de titulo de cuento ni de
            # cita: exigir igual contexto real de narracion en el cuerpo.
            return any(re.search(p, t, re.IGNORECASE) for p in STORY_CONTEXT_PATTERNS)
    return any(re.search(p, t, re.IGNORECASE) for p in STORY_CONTEXT_PATTERNS)

def parse_fecha(txt):
    if not txt: return ""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try: return datetime.strptime(txt.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError: continue
    try:
        dt = date_parser.parse(txt, fuzzy=True, dayfirst=True)
        if 2000 < dt.year < datetime.now().year + 1: return dt.strftime("%Y-%m-%d")
    except: pass
    return ""

def make_guid(title, author=""):
    return re.sub(r"\s+", "-", f"{title}|{author}".strip("|").lower())

def load_existing():
    if DATA_FILE.exists():
        try: return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except: pass
    return []

def save_episodes(episodes):
    episodes.sort(key=lambda e: e.get("fecha", ""), reverse=True)
    DATA_FILE.write_text(json.dumps(episodes, ensure_ascii=False, indent=2), encoding="utf-8")

def dedup(episodes, new):
    mp3, guid = new.get("mp3_url", ""), new.get("guid", "")
    t, a = new.get("titulo", ""), new.get("autor_cuento", "")
    for e in episodes:
        if mp3 and mp3 == e.get("mp3_url"): return True
        if guid and guid == e.get("guid"): return True
        if t and a and t == e.get("titulo") and a == e.get("autor_cuento"): return True
    return False

# --- Extractores de HTML ---
def _find_mp3(soup, base_url):
    for src in soup.find_all("source", attrs={"type": re.compile(r"audio", re.I)}):
        url = src.get("src", "")
        if url and ".mp3" in url.lower(): return urljoin(base_url, url)
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "")
        if not src: continue
        src = urljoin(base_url, src)
        resp = safe_get(src)
        if resp:
            inner = BeautifulSoup(resp.text, "lxml")
            for s in inner.find_all("source", attrs={"type": re.compile(r"audio", re.I)}):
                u = s.get("src", "")
                if u and ".mp3" in u.lower(): return urljoin(src, u)
    for a in soup.find_all("a", href=re.compile(r"\.mp3", re.I)): return urljoin(base_url, a["href"])
    for tag in soup.find_all(True):
        for attr in ("src", "href", "data-src", "data-url", "data-file"):
            val = tag.get(attr, "")
            if isinstance(val, str) and ".mp3" in val.lower(): return urljoin(base_url, val)
    return ""

def _find_image(soup, base_url):
    og = soup.find("meta", property="og:image")
    if og and og.get("content"): return urljoin(base_url, og["content"])
    fig = soup.find("figure")
    if fig:
        img = fig.find("img")
        if img and img.get("src"): return urljoin(base_url, img["src"])
    return ""

def _find_date(soup):
    t = soup.find("time")
    if t:
        dt = t.get("datetime") or t.get_text(strip=True)
        if dt: return parse_fecha(dt)
    for prop in ("article:published_time", "datePublished"):
        m = soup.find("meta", property=prop)
        if m and m.get("content"): return parse_fecha(m["content"])
    return ""

def _guess_author(titulo, body):
    # Patron con coma: "'El Pampa', de Roberto Fontanarrosa"
    m = re.search(r",\s*de\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,3})", titulo)
    if m: return m.group(1).strip()
    # Patron sin coma: "Amor en el Parque Rivadavia de Roberto Arlt"
    m = re.search(r"\s+de\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,3})$", titulo)
    if m:
        candidate = m.group(1).strip()
        # Verificar que no sea parte del titulo (ej: "El fin de Jorge Luis Borges" -> ok,
        # pero "La guerra de Malvinas" -> no)
        if not re.search(rf"\b{candidate}\b", titulo[:-len(candidate)-4], re.I):
            return candidate
    for pattern in [r"cuento\s+de\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,3})", r"relato\s+de\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,3})"]:
        m = re.search(pattern, body[:1500])
        if m:
            c = m.group(1).strip()
            if "apo" not in c.lower(): return c
    return ""

def _extract(url, fuente):
    resp = safe_get(url)
    if not resp: return None
    soup = BeautifulSoup(resp.text, "lxml")
    titulo = ""
    h1 = soup.find("h1")
    if h1: titulo = h1.get_text(strip=True)
    if not titulo:
        og = soup.find("meta", property="og:title")
        if og: titulo = og.get("content", "")
    if not titulo: return None
    if not matches_apo(soup.get_text(separator=" ", strip=True), titulo): return None
    mp3 = _find_mp3(soup, url)
    if not mp3: return None
    autor_cuento = _guess_author(titulo, soup.get_text(separator=" ", strip=True))
    desc_el = soup.find("div", class_=re.compile(r"entry|content|post-body|article-body", re.I))
    descripcion = text_clean(desc_el.get_text()[:800]) if desc_el else ""
    ok, dur = verify_mp3(mp3)
    if not ok: return None
    imagen = _find_image(soup, url) or COVER_URL
    return {
        "titulo": titulo, "autor_cuento": autor_cuento, "narrador": "Alejandro Apo",
        "descripcion": descripcion, "fecha": _find_date(soup), "duracion": round(dur, 1),
        "imagen": imagen, "mp3_url": mp3, "fuente": fuente, "fuente_url": url,
        "guid": make_guid(titulo, autor_cuento),
        "extraido": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

# --- Scrapers Específicos ---
def _rss_items(xml_text):
    soup = BeautifulSoup(xml_text, "xml")
    return soup.find_all("item")

def _item_audio(item, base_url):
    """Extrae URL de audio del item RSS (soporta .mp3 y .m4a)."""
    enclosure = item.find("enclosure")
    if enclosure and enclosure.get("url"):
        enc_url = enclosure["url"].lower()
        if ".mp3" in enc_url or ".m4a" in enc_url or ".m4b" in enc_url:
            return urljoin(base_url, enclosure["url"])
    content = item.find("encoded") or item.find("description")
    if content:
        m = re.search(r'https?://[^\s"\'<>]+\.(mp3|m4a|m4b)[^\s"\'<>]*', content.get_text(), re.I)
        if m: return m.group(0)
    return ""

def _item_mp3(item, base_url):
    """Compatibilidad hacia atrás: usa _item_audio internamente."""
    return _item_audio(item, base_url)

def scrape_wp_tag_feed(feed_url, fuente, max_pages=5):
    """Lee el feed RSS nativo de WordPress del tag de Apo en Radio Nacional."""
    results = []
    seen_guids = set()
    for page in range(1, max_pages + 1):
        url = feed_url if page == 1 else f"{feed_url}?paged={page}"
        log.info("Leyendo feed RN: %s", url)
        resp = safe_get(url)
        if not resp: break
        items = _rss_items(resp.text)
        if not items: break
        for item in items:
            titulo_el = item.find("title")
            titulo = titulo_el.get_text(strip=True) if titulo_el else ""
            link_el = item.find("link")
            link = link_el.get_text(strip=True) if link_el else ""
            guid_el = item.find("guid")
            item_guid = guid_el.get_text(strip=True) if guid_el else link
            if not item_guid or item_guid in seen_guids: continue
            seen_guids.add(item_guid)
            if not titulo: continue
            desc_el = item.find("description")
            body_text = text_clean(desc_el.get_text()) if desc_el else ""
            if not matches_apo(f"{titulo} {body_text}", titulo): continue
            mp3 = _item_mp3(item, link or url)
            if not mp3: continue
            pubdate_el = item.find("pubDate")
            fecha = parse_fecha(pubdate_el.get_text(strip=True)) if pubdate_el else ""
            autor_cuento = _guess_author(titulo, body_text)
            ok, dur = verify_mp3(mp3)
            if not ok: continue
            log.info("  OK RN Feed: %s", titulo)
            results.append({
                "titulo": titulo, "autor_cuento": autor_cuento, "narrador": "Alejandro Apo",
                "descripcion": body_text[:800], "fecha": fecha, "duracion": round(dur, 1),
                "imagen": COVER_URL, "mp3_url": mp3, "fuente": fuente, "fuente_url": link or url,
                "guid": make_guid(titulo, autor_cuento),
                "extraido": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
            time.sleep(1)
    return results

# --- Scraper Genérico de Feed RSS de Podcast ---
# Para feeds RSS completos tipo podcast (Apple Podcasts, etc.) que incluyen
# todos los episodios en un solo XML, sin paginacion. No verifica cada MP3
# porque son feeds oficiales y confiables.

def scrape_podcast_feed(feed_url, fuente, max_pages=1):
    """Lee un feed RSS de podcast. Si max_pages > 1, pagina con ?paged=N.
    No verifica el audio (se asume que el feed oficial es confiable)."""
    results = []
    seen_guids = set()
    
    for page in range(1, max_pages + 1):
        url = feed_url if page == 1 else f"{feed_url}?paged={page}"
        log.info("Leyendo feed podcast: %s", url)
        resp = safe_get(url)
        if not resp:
            if page == 1:
                log.error("No se pudo acceder al feed: %s", feed_url)
            break
        
        soup = BeautifulSoup(resp.text, "xml")
        items = soup.find_all("item")
        if not items:
            break
        
        if page == 1:
            log.info("Feed podcast: %d items en pagina 1", len(items))
        
        for item in items:
            titulo_el = item.find("title")
            titulo = titulo_el.get_text(strip=True) if titulo_el else ""
            if not titulo:
                continue
            
            guid_el = item.find("guid")
            item_guid = guid_el.get_text(strip=True) if guid_el else ""
            if item_guid and item_guid in seen_guids:
                continue
            if item_guid:
                seen_guids.add(item_guid)
            
            desc_el = item.find("description")
            body_text = text_clean(desc_el.get_text()) if desc_el else ""
            
            if not matches_apo(f"{titulo} {body_text}", titulo):
                continue
            
            audio_url = _item_audio(item, url)
            if not audio_url:
                continue
            
            pubdate_el = item.find("pubDate")
            fecha = parse_fecha(pubdate_el.get_text(strip=True)) if pubdate_el else ""
            
            dur_el = item.find("itunes:duration")
            dur_secs = 0.0
            if dur_el:
                dur_str = dur_el.get_text(strip=True)
                parts = dur_str.split(":")
                if len(parts) == 3:
                    dur_secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                elif len(parts) == 2:
                    dur_secs = int(parts[0]) * 60 + int(parts[1])
                elif dur_str.isdigit():
                    dur_secs = float(dur_str)
            
            autor_cuento = _guess_author(titulo, body_text)
            
            link_el = item.find("link")
            ep_link = link_el.get_text(strip=True) if link_el else url
            
            log.info("  OK %s: %s", fuente, titulo[:70])
            results.append({
                "titulo": titulo,
                "autor_cuento": autor_cuento,
                "narrador": "Alejandro Apo",
                "descripcion": body_text[:800],
                "fecha": fecha,
                "duracion": round(dur_secs, 1),
                "imagen": COVER_URL,
                "mp3_url": audio_url,
                "fuente": fuente,
                "fuente_url": ep_link,
                "guid": item_guid or make_guid(titulo, autor_cuento),
                "extraido": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
    
    return results

# URL del feed podcast oficial de Radio Nacional (Apple Podcasts).
# Contiene 300 episodios en un solo XML, mucho mas completo y rapido
# que el feed paginado del blog.
RN_PODCAST_FEED = "https://www.radionacional.com.ar/category/buenos-aires/lra-1-buenos-aires/todo-con-afecto/feed/podcast/"

# --- Scraper Anchor.fm (Spotify for Creators) ---
# El feed original de "Los cuentos de Apo" en Anchor.fm, con 51 episodios.
# Fuente: https://anchor.fm/s/612a6550/podcast/rss
# Vinculado desde TuneIn: https://tunein.com/podcasts/Books--Literature/Los-cuentos-de-Apo-p2783793/

ANCHOR_RSS_URL = "https://anchor.fm/s/612a6550/podcast/rss"
ANCHOR_FUENTE = "Los cuentos de Apo (Anchor.fm / Grupo Octubre)"

def _parse_anchor_title(full_title, body_text=""):
    """Extrae titulo del cuento y autor desde el titulo de Anchor.fm.
    
    Formato tipico:
      "Los cuentos de Apo - La noche de Mantequilla, de Julio Cortazar"
      "Los cuentos de Apo- La trampa, de Rodolfo Walsh"
      "Los cuentos de Apo - Un señor muy viejo... de Gabriel Garcia Marquez"
    
    Retorna (titulo_cuento, autor_cuento).
    """
    # Quitar prefijo "Los cuentos de Apo" con posibles variantes
    titulo = re.sub(r'^Los\s+cuentos\s+de\s+Apo\s*[-–—]\s*', '', full_title, flags=re.IGNORECASE).strip()
    autor = _guess_author(titulo, body_text)
    return titulo, autor

def _parse_youtube_title(full_title):
    """Extrae titulo del cuento y autor desde titulo de video de YouTube.
    
    Formatos tipicos:
      '"La Guerra y la Paz" de Mario Benedetti (Alejandro Apo)'
      '"Trenes" de Osvaldo Soriano por (Alejandro Apo)'
    
    Retorna (titulo_cuento, autor_cuento).
    """
    titulo = full_title.strip()
    titulo = re.sub(r'\s*(por\s*)?[,(]\s*Alejandro\s+Apo\s*\)?\s*$', '', titulo, flags=re.IGNORECASE).strip()
    titulo = titulo.strip('\u201c\u201d"\'').strip()
    autor = _guess_author(titulo, "")
    if not autor:
        m = re.search(r',?\s*de\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,4})\s*$', titulo)
        if m:
            autor = m.group(1).strip()
            prefix = titulo[:m.start()].strip().rstrip(',').strip()
            if len(prefix) > 5:
                titulo = prefix
    return titulo, autor

def scrape_anchor_feed():
    """Lee el feed RSS de Anchor.fm (Spotify for Creators) del podcast
    'Los cuentos de Apo' y devuelve los episodios encontrados."""
    results = []
    log.info("Leyendo feed Anchor.fm: %s", ANCHOR_RSS_URL)
    resp = safe_get(ANCHOR_RSS_URL)
    if not resp:
        log.error("No se pudo acceder al feed de Anchor.fm")
        return results
    
    soup = BeautifulSoup(resp.text, "xml")
    items = soup.find_all("item")
    log.info("Feed Anchor.fm: %d items encontrados", len(items))
    
    for item in items:
        titulo_el = item.find("title")
        full_title = titulo_el.get_text(strip=True) if titulo_el else ""
        if not full_title:
            continue
        
        # Parsear titulo del cuento y autor
        desc_el = item.find("description")
        body_text = text_clean(desc_el.get_text()) if desc_el else ""
        titulo, autor_cuento = _parse_anchor_title(full_title, body_text)
        if not matches_apo(f"{full_title} {body_text}", full_title):
            continue
        
        # Obtener audio (.m4a via Anchor.fm proxy)
        audio_url = _item_audio(item, ANCHOR_RSS_URL)
        if not audio_url:
            continue
        
        # Fecha desde pubDate (formato RFC 2822)
        pubdate_el = item.find("pubDate")
        fecha = parse_fecha(pubdate_el.get_text(strip=True)) if pubdate_el else ""
        
        # Duracion desde <itunes:duration> (formato HH:MM:SS)
        dur_el = item.find("itunes:duration")
        dur_secs = 0.0
        if dur_el:
            dur_str = dur_el.get_text(strip=True)
            parts = dur_str.split(":")
            if len(parts) == 3:
                dur_secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:
                dur_secs = int(parts[0]) * 60 + int(parts[1])
            elif dur_str.isdigit():
                dur_secs = float(dur_str)
        
        # El feed de Anchor es confiable: ya incluye duracion en <itunes:duration>.
        # No verificamos el audio con HEAD/verify_mp3 para no ralentizar.
        
        # GUID
        guid_el = item.find("guid")
        item_guid = guid_el.get_text(strip=True) if guid_el else ""
        
        # Link al episodio en Spotify for Creators
        link_el = item.find("link")
        ep_link = link_el.get_text(strip=True) if link_el else ""
        
        log.info("  OK Anchor.fm: %s", titulo)
        results.append({
            "titulo": titulo,
            "autor_cuento": autor_cuento,
            "narrador": "Alejandro Apo",
            "descripcion": body_text[:800],
            "fecha": fecha,
            "duracion": round(dur_secs, 1),
            "imagen": COVER_URL,
            "mp3_url": audio_url,
            "fuente": ANCHOR_FUENTE,
            "fuente_url": ep_link or ANCHOR_RSS_URL,
            "guid": item_guid or make_guid(titulo, autor_cuento),
            "extraido": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        time.sleep(0.2)  # Ser amable con el servidor, pero el feed es ligero
    
    return results

# --- Scraper YouTube (via yt-dlp) ---
# Busca playlists de YouTube con cuentos de Apo y extrae audio con yt-dlp.
# Las URLs de audio expiran en ~24h, por eso el scraper debe correr seguido.

# Playlists curadas de cuentos de Alejandro Apo en YouTube
YT_PLAYLISTS = [
    ("PLoxVsJWn3DIbdI-yp_CjdG35mF3fYoBfv", "Alejandro Apo, El Cuento de la tarde"),
    ("PLbleEK5UfTEUAlhfk5E-4_7DG-YS9pXzv",  "Y el fútbol contó un cuento"),
    ("PLuXU-g7mjkKOXlptwpDhUp4HpGz3f1cX1",  "Cuentos por Alejandro Apo"),
    ("PLiikv-x97RDJDMqAtcVD8gvqMXVJcQ75x",  "Fontanarrosa por Apo"),
    ("PLRq2HHwFPBf3LhIKFJMZTFGW0hJe4e-Hv",  "Todo con Afecto - Cuentos de fútbol"),
    ("PLvnTVNZIelOs32hx35Y1X8SnDGwP6MOfC",  "Todo con afecto (Apo)"),
    ("PLDHL1yN56dYj4VdHfFXbZH2S1OUUJMF1t",  "Cuentos y Relatos"),
    ("PLTaR_galnfke4wBGOmWmXozEGNF55Z4YH",  "Cuentos (varios)"),
    # Nuevas playlists descubiertas Jul 2026
    ("PLLyLbC_ogAAnkkUq1kmZyMUS6oUhI_upC", "Textos: Cuentos y Poemas"),
    ("PLUFV5AyZUZBNl1smaVulLxZh2-JpuE4ed", "Un cuento de futbol"),
    ("PLWvIyAjX0z3bJjMjRchx3FNP0Y6XfAQoO", "Detrás de la Red - Cuentos de Fútbol"),
    ("PLdh4DfiUr1LXpXvP5GWJAfXBQ2SUv3vJ8", "Alejandro Apo y Futbol"),
    ("PLkqWGWgjhlTRpQb5aePCoM47yo6sGLz2r", "ALEJANDRO APO"),
    ("PLpOyvRgjpkJ4UI-mS4JxgQpPcr8fdjV5j", "Y el fútbol contó un cuento"),
]

YT_FUENTE = "YouTube"

def _get_youtube_audio(video_url):
    """Usa yt-dlp para obtener URL de audio y duracion de un video de YouTube.
    Retorna (audio_url, duracion_segundos) o (None, 0) si falla."""
    if not HAS_YT_DLP:
        log.warning("yt-dlp no instalado, omitiendo %s", video_url)
        return None, 0
    try:
        ydl_opts = {"quiet": True, "format": "bestaudio", "no_warnings": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return info.get("url"), info.get("duration", 0)
    except Exception as e:
        log.warning("yt-dlp fallo para %s: %s", video_url, str(e)[:100])
        return None, 0

def scrape_youtube_playlist(playlist_id, playlist_name):
    """Lee el RSS de una playlist de YouTube y extrae audio con yt-dlp."""
    results = []
    if not HAS_YT_DLP:
        log.warning("yt-dlp no disponible, saltando playlist %s", playlist_name)
        return results
    
    rss_url = f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"
    log.info("Leyendo playlist YouTube: %s", playlist_name)
    resp = safe_get(rss_url)
    if not resp:
        log.error("No se pudo acceder al RSS de la playlist %s", playlist_name)
        return results
    
    soup = BeautifulSoup(resp.text, "xml")
    entries = soup.find_all("entry")
    log.info("Playlist '%s': %d videos", playlist_name, len(entries))
    
    for entry in entries:
        title_el = entry.find("title")
        full_title = title_el.get_text(strip=True) if title_el else ""
        if not full_title:
            continue
        
        # Filtrar: debe mencionar a Apo o ser claramente un cuento narrado
        if not matches_apo(full_title, full_title):
            # Tambien aceptar si tiene pinta de cuento (autor conocido + Apo en el titulo)
            if "apo" not in full_title.lower() and "alejandro" not in full_title.lower():
                continue
        
        link_el = entry.find("link")
        video_url = link_el.get("href", "") if link_el else ""
        if not video_url:
            continue
        
        # Parsear titulo (formato: "'Cuento' de Autor (Alejandro Apo)")
        titulo, autor_cuento = _parse_youtube_title(full_title)
        if not autor_cuento:
            autor_cuento = _guess_author(full_title, "")
        
        # Obtener audio con yt-dlp
        audio_url, duracion = _get_youtube_audio(video_url)
        if not audio_url:
            continue
        
        pubdate_el = entry.find("published")
        fecha = parse_fecha(pubdate_el.get_text(strip=True)) if pubdate_el else ""
        
        # Descripcion desde media:description
        desc_el = entry.find("media:description") or entry.find("description")
        descripcion = text_clean(desc_el.get_text())[:500] if desc_el else ""
        if not descripcion:
            desc_el = entry.find("media:group")
            if desc_el:
                md = desc_el.find("media:description")
                if md: descripcion = text_clean(md.get_text())[:500]
        
        # Video ID como guid
        vid_el = entry.find("yt:videoId")
        video_id = vid_el.get_text(strip=True) if vid_el else ""
        
        log.info("  OK YT: %s", titulo[:70])
        results.append({
            "titulo": titulo,
            "autor_cuento": autor_cuento,
            "narrador": "Alejandro Apo",
            "descripcion": descripcion[:800],
            "fecha": fecha,
            "duracion": round(float(duracion), 1) if duracion else 0.0,
            "imagen": COVER_URL,
            "mp3_url": audio_url,
            "fuente": f"{YT_FUENTE} - {playlist_name}",
            "fuente_url": video_url,
            "guid": f"yt-{video_id}" if video_id else make_guid(titulo, autor_cuento),
            "extraido": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        time.sleep(1)  # No saturar yt-dlp
    
    return results

# --- Scraper RadioCut.fm ---
# Extrae audiocuts de RadioCut usando los sitemaps y el HTML.
# Cada pagina de audiocut expone datos en <li> elements y JSON-LD.

RC_FUENTE = "RadioCut.fm"

def scrape_radiocut_url(audiocut_url):
    """Extrae datos de un audiocut individual de RadioCut.
    Retorna un dict de episodio o None si falla/no es relevante."""
    resp = safe_get(audiocut_url)
    if not resp:
        return None
    
    html = resp.text
    
    # Extraer titulo
    title_match = re.search(r'<h1[^>]*id="cut_title"[^>]*>(.*?)</h1>', html, re.DOTALL)
    titulo = ""
    if title_match:
        titulo = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
    if not titulo:
        og_title = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', html)
        if og_title: titulo = og_title.group(1)
    if not titulo:
        return None
    
    # Filtrar
    body = BeautifulSoup(html, "lxml").get_text(separator=" ", strip=True)[:2000]
    if not matches_apo(f"{titulo} {body}", titulo):
        return None
    
    # Datos de audio
    station = re.findall(r'<li class="audio_station">([^<]+)</li>', html)
    seconds = re.findall(r'<li class="audio_seconds">([^<]+)</li>', html)
    base_url = re.findall(r'<li class="audio_base_url">([^<]+)</li>', html)
    
    # URL de audio desde JSON-LD (preferido) o construido
    audio_url = ""
    ld_urls = re.findall(r'"contentUrl"\s*:\s*"([^"]+)"', html)
    if ld_urls:
        audio_url = ld_urls[0]
    elif station and seconds and base_url:
        # Fallback: construir URL (menos preciso pero funciona)
        dur_match = re.findall(r'<li class="audio_duration">([^<]+)</li>', html)
        dur = dur_match[0] if dur_match else seconds[0]
        audio_url = f"{base_url[0]}/server/get_unified_file/{station[0]}/{seconds[0]}.0/{dur}"
    
    if not audio_url:
        return None
    
    # Fecha desde JSON-LD o meta
    fecha = ""
    ld_dates = re.findall(r'"uploadDate"\s*:\s*"([^"]+)"', html)
    if ld_dates:
        fecha = parse_fecha(ld_dates[0][:10])
    if not fecha:
        og_date = re.search(r'<meta[^>]*property="article:published_time"[^>]*content="([^"]+)"', html)
        if og_date: fecha = parse_fecha(og_date.group(1)[:10])
    if not fecha:
        ld_mod = re.findall(r'"dateModified"\s*:\s*"([^"]+)"', html)
        if ld_mod: fecha = parse_fecha(ld_mod[0][:10])
    
    # Duracion ISO 8601 -> segundos (PT1H30M20S, PT24M20S, PT45S)
    dur_secs = 0.0
    ld_dur = re.findall(r'"duration"\s*:\s*"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"', html)
    if ld_dur:
        h, m, s = ld_dur[0]
        dur_secs = int(h or 0) * 3600 + int(m or 0) * 60 + int(s or 0)
    else:
        # Intentar desde <li class="audio_duration">
        dur_li = re.findall(r'<li class="audio_duration">(\d+)</li>', html)
        if dur_li:
            dur_secs = float(dur_li[0])
    
    # Descripcion
    desc_match = re.search(r'"description"\s*:\s*"([^"]+)"', html)
    descripcion = desc_match.group(1)[:800] if desc_match else ""
    
    # Autor desde el titulo
    autor_cuento = _guess_author(titulo, body)
    
    # GUID: usar la URL como identificador unico
    guid = f"rc-{audiocut_url.split('/')[-2]}" if audiocut_url.endswith('/') else f"rc-{audiocut_url.split('/')[-1]}"
    
    return {
        "titulo": titulo,
        "autor_cuento": autor_cuento,
        "narrador": "Alejandro Apo",
        "descripcion": descripcion[:800],
        "fecha": fecha,
        "duracion": round(dur_secs, 1),
        "imagen": COVER_URL,
        "mp3_url": audio_url,
        "fuente": RC_FUENTE,
        "fuente_url": audiocut_url,
        "guid": guid,
        "extraido": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

# URLs de audiocuts de Apo descubiertas via sitemaps de RadioCut.
# Se cargan desde radiocut_urls.json (generado con scrape_sitemaps.py).
RC_URLS_FILE = Path("radiocut_urls.json")

def load_radiocut_urls():
    """Carga la lista de URLs de RadioCut desde el archivo JSON."""
    if RC_URLS_FILE.exists():
        try:
            return json.loads(RC_URLS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Fallback: lista minima hardcodeada
    return [
        "https://radiocut.fm/audiocut/te-digo-mas-roberto-fontanarrosa-por-alejandro-apo/",
        "https://radiocut.fm/audiocut/alejandro-apo-lee-a-eduardo-sacheri/",
        "https://radiocut.fm/audiocut/unsenorcuento-en-la-casa-invita-por-am750-hoy-una-sonrisa-exactamente-asi-eduardo-sacheri/",
        "https://radiocut.fm/audiocut/alejandro-apo-dondequiera-estes-lecturas-y-cuentos-jueves-19-10-2023/",
    ]

# --- Scraper Genérico (AM750 y Página/12) ---
# Nota: "am750" y "tags" fueron sacados de esta lista. AM750 ahora vive DENTRO
# de pagina12.com.ar/am750/ (el dominio am750.com.ar quedo dado de baja), y la
# pagina de tag real (pagina12.com.ar/tags/...) es justamente la fuente que
# ahora usamos en vez del buscador roto, asi que no puede estar bloqueada.
NAV_PATH_EXCLUDE = re.compile(
    r"/(contacto|politica-de-privacidad|terminos|socios|usuarios|rss|"
    r"especiales|publico|opinion|cash|salta12|cordoba12|radar|soy|las12|"
    r"negrx|ciencia|universidad|psicologia|comunicacion-y-periodismo|plastica|"
    r"entrevistas|verano12|latinoamerica-piensa|malena|argentina12|"
    r"edicion-impresa|mundial-2026|el-pais|economia|sociedad|"
    r"cultura-y-espectaculos|deportes|el-mundo|recordatorios|buenos-aires12|"
    r"rosario12|contratapa|50-anos-del-golpe|radar-libros)(/|\?|$)",
    re.IGNORECASE,
)
MAX_URLS_PER_SOURCE = 40

def _is_candidate_url(full, domain):
    p = urlparse(full)
    if domain not in p.netloc: return False
    if NAV_PATH_EXCLUDE.search(p.path): return False
    return True

def scrape_source(base_search, domain, fuente):
    results, visited, to_visit = [], set(), []
    resp = safe_get(base_search)
    if resp:
        soup = BeautifulSoup(resp.text, "lxml")
        for a in soup.find_all("a", href=True):
            full = urljoin(base_search, a["href"])
            if _is_candidate_url(full, domain) and full not in visited: to_visit.append(full)
    for url in to_visit:
        if len(visited) >= MAX_URLS_PER_SOURCE: break
        if url in visited: continue
        visited.add(url)
        if "?s=" in url or "/buscar" in url or "/page/" in url or "?page=" in url:
            r2 = safe_get(url)
            if r2:
                s2 = BeautifulSoup(r2.text, "lxml")
                for a in s2.find_all("a", href=True):
                    full = urljoin(url, a["href"])
                    if _is_candidate_url(full, domain) and full not in visited: to_visit.append(full)
            continue
        log.info("Procesando: %s", url)
        ep = _extract(url, fuente)
        if ep:
            results.append(ep)
            log.info("  OK: %s", ep["titulo"])
        time.sleep(1)
    return results

# --- Ejecución Principal ---
def main():
    log.info("=== Inicio de scraping ===")
    existing = load_existing()
    all_new = []

    def _agregar(eps):
        for ep in eps:
            if not dedup(existing, ep) and not dedup(all_new, ep):
                a = ep["autor_cuento"]
                ep["descripcion"] = f'Alejandro Apo lee "{ep["titulo"]}"{f", cuento de {a}" if a else ""}.\n\nFuente original:\n{ep["fuente"]}.\n\n{ep["descripcion"]}'
                all_new.append(ep)

    # 1. Radio Nacional — feed podcast oficial (Apple Podcasts).
    # 300 episodios en un solo XML (2020-2023), sin paginacion y sin
    # necesidad de verify_mp3 porque es el feed oficial de podcasting.
    # Mucho mas rapido y completo que el viejo feed /feed/ paginado.
    try:
        _agregar(scrape_podcast_feed(RN_PODCAST_FEED, "Radio Nacional Argentina"))
    except Exception as e:
        log.error("Error en Radio Nacional (feed podcast): %s", e)

    # 2. Radio Nacional — feed del tag "alejandro-apo".
    # Complementa al feed podcast: cubre hasta abril 2024 (vs dic 2023 del otro).
    # Mismos episodios en su mayoria, pero el dedup se encarga.
    try:
        _agregar(scrape_podcast_feed("https://www.radionacional.com.ar/tag/alejandro-apo/feed/", "Radio Nacional Argentina", max_pages=15))
    except Exception as e:
        log.error("Error en Radio Nacional (feed tag): %s", e)

    # 3. YouTube — playlists curadas de cuentos de Apo.
    # Usa yt-dlp para extraer audio. Las URLs expiran en ~24h, por eso
    # el scraper debe ejecutarse diariamente via GitHub Actions.
    if HAS_YT_DLP:
        for pl_id, pl_name in YT_PLAYLISTS:
            try:
                _agregar(scrape_youtube_playlist(pl_id, pl_name))
            except Exception as e:
                log.error("Error en YouTube playlist %s: %s", pl_name[:40], e)
    else:
        log.warning("yt-dlp no instalado. Saltando YouTube. Instalar con: pip install yt-dlp")

    # 4. RadioCut.fm — audiocuts individuales descubiertos via sitemaps.
    # Contiene contenido reciente (2024-2025) de AM750 no disponible en RSS.
    try:
        for rc_url in load_radiocut_urls():
            ep = scrape_radiocut_url(rc_url)
            if ep and not dedup(existing, ep) and not dedup(all_new, ep):
                a = ep["autor_cuento"]
                ep["descripcion"] = f'Alejandro Apo lee "{ep["titulo"]}"{f", cuento de {a}" if a else ""}.\n\nFuente original:\n{ep["fuente"]}.\n\n{ep["descripcion"]}'
                all_new.append(ep)
                log.info("  OK RadioCut: %s", ep["titulo"][:70])
    except Exception as e:
        log.error("Error en RadioCut: %s", e)

    # 5. Anchor.fm (Spotify for Creators) — feed oficial del podcast
    # "Los cuentos de Apo" por Grupo Octubre. Contiene 51 episodios (2021).
    # Es la fuente original que TuneIn agrega en:
    #   https://tunein.com/podcasts/Books--Literature/Los-cuentos-de-Apo-p2783793/
    try:
        _agregar(scrape_anchor_feed())
    except Exception as e:
        log.error("Error en Anchor.fm: %s", e)

    # 6. Pagina/12 (incluye AM750): DESHABILITADO otra vez, esta vez por un
    # motivo distinto y definitivo. El dominio am750.com.ar murio y su
    # contenido se mudo a pagina12.com.ar/am750/, y la pagina de tag real
    # (pagina12.com.ar/tags/7116-alejandro-apo) SI lista notas reales sobre
    # los cuentos de Apo (a diferencia del buscador, que nunca funciono).
    # Pero se verifico bajando el HTML completo de una de esas notas
    # (819153-alejandro-apo-lee-el-pichon-de-cristo-de-fontanarrosa) y NO hay
    # ningun reproductor de audio ni link a mp3: son notas de texto que
    # acompañan la lectura al aire, no el archivo de audio en si. El audio
    # real de "Donde quiera que estes" vive unicamente en Radio Nacional, que
    # ya se cubre bien con el feed RSS. No es un bug de extraccion (no es que
    # el mp3 este cargado por JS y no se vea): no hay audio para extraer en
    # esa pagina, nunca lo hubo. No tiene sentido re-habilitar esto salvo que
    # aparezca evidencia de que alguna nota puntual si incluya audio propio.
    
    if all_new:
        existing.extend(all_new)
        save_episodes(existing)
        log.info("Se agregaron %d episodios nuevos.", len(all_new))
    else: log.info("Sin episodios nuevos.")
    log.info("=== Fin ===")

if __name__ == "__main__": main()