#!/usr/bin/env python3
import json, logging, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from mutagen.mp3 import MP3, HeaderNotFoundError
from dateutil import parser as date_parser

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
    m = re.search(r",\s*de\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,3})", titulo)
    if m: return m.group(1).strip()
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

def _item_mp3(item, base_url):
    enclosure = item.find("enclosure")
    if enclosure and enclosure.get("url") and ".mp3" in enclosure["url"].lower():
        return urljoin(base_url, enclosure["url"])
    content = item.find("encoded") or item.find("description")
    if content:
        m = re.search(r'https?://[^\s"\'<>]+\.mp3[^\s"\'<>]*', content.get_text())
        if m: return m.group(0)
    return ""

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

    # 1. Radio Nacional (Feed RSS nativo - Ultra eficiente)
    try:
        _agregar(scrape_wp_tag_feed("https://www.radionacional.com.ar/tag/alejandro-apo/feed/", "Radio Nacional Argentina"))
    except Exception as e:
        log.error("Error en Radio Nacional (Feed): %s", e)

    # 2. Pagina/12 (incluye AM750: el dominio am750.com.ar quedo dado de baja,
    # y su contenido ahora vive DENTRO de pagina12.com.ar/am750/).
    # El buscador (?q=... / ?s=...) es 100% client-side y nunca devuelve
    # resultados reales via HTML plano -- confirmado en corridas reales del
    # 2026-07-12, donde recorria el menu generico del sitio sin encontrar
    # nada. En cambio, la pagina de TAG real (con id numerico propio del CMS
    # de Pagina/12) si lista contenido real con fecha, y cubre tanto notas de
    # Pagina/12 como de AM750 porque ambos comparten el mismo sistema de tags.
    scrapers = [
        ("https://www.pagina12.com.ar/tags/7116-alejandro-apo", "pagina12.com.ar", "Página/12 / AM750"),
    ]
    for url, dom, name in scrapers:
        try:
            _agregar(scrape_source(url, dom, name))
        except Exception as e: log.error("Error en %s: %s", name, e)
    
    if all_new:
        existing.extend(all_new)
        save_episodes(existing)
        log.info("Se agregaron %d episodios nuevos.", len(all_new))
    else: log.info("Sin episodios nuevos.")
    log.info("=== Fin ===")

if __name__ == "__main__": main()