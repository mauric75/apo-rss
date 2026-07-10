#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from feedgen.feed import FeedGenerator

DATA_FILE = Path("episodes.json")
PODCAST_TITLE = "Los cuentos de Alejandro Apo"
PODCAST_SUBTITLE = "RSS independiente"
PODCAST_DESCRIPTION = "Coleccion automatica de cuentos narrados por Alejandro Apo, reunidos desde fuentes publicas: Radio Nacional Argentina, AM 750 y Pagina/12."
PODCAST_AUTHOR = "Alejandro Apo"
PODCAST_EMAIL = "contacto@ejemplo.com"
PODCAST_LINK = "https://mauric75.github.io/apo-rss/"
PODCAST_LANGUAGE = "es-ar"
PODCAST_COPYRIGHT = "CC BY-NC-SA 4.0"
PODCAST_IMAGE = "https://mauric75.github.io/apo-rss/cover.jpg"

def load_episodes():
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))

def duracion_str(s):
    if not s or s <= 0: return ""
    h, m, s = int(s//3600), int(s%3600//60), int(s%60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def build_rss(eps):
    fg = FeedGenerator()
    fg.load_extension("podcast")
    fg.title(PODCAST_TITLE)
    fg.subtitle(PODCAST_SUBTITLE)
    fg.description(PODCAST_DESCRIPTION)
    fg.author(name=PODCAST_AUTHOR, email=PODCAST_EMAIL)
    fg.link(href=PODCAST_LINK, rel="alternate")
    fg.link(href=f"{PODCAST_LINK}rss.xml", rel="self", type="application/rss+xml")
    fg.language(PODCAST_LANGUAGE)
    fg.copyright(PODCAST_COPYRIGHT)
    fg.image(url=PODCAST_IMAGE, title=PODCAST_TITLE, link=PODCAST_LINK)
    fg.podcast.itunes_category("Arts", "Literature")
    fg.podcast.itunes_owner(name=PODCAST_AUTHOR, email=PODCAST_EMAIL)
    fg.podcast.itunes_explicit("no")
    fg.podcast.itunes_image(PODCAST_IMAGE)
    fg.podcast.itunes_summary(PODCAST_DESCRIPTION)
    fg.podcast.itunes_type("episodic")
    
    for ep in eps:
        fe = fg.add_entry()
        fe.id(ep.get("guid", ep.get("mp3_url", "")))
        fe.title(ep["titulo"])
        desc = ep.get("descripcion", "")
        fe.description(desc)
        fe.content(desc)
        fe.published(datetime.fromisoformat(ep["fecha"]).replace(tzinfo=timezone.utc) if ep.get("fecha") else datetime.now(timezone.utc))
        if ep.get("mp3_url"): fe.enclosure(ep["mp3_url"], str(ep.get("duracion", 0)), "audio/mpeg")
        fe.podcast.itunes_duration(duracion_str(ep.get("duracion", 0)))
        fe.podcast.itunes_summary(desc)
        fe.podcast.itunes_episode_type("full")
        img = ep.get("imagen", PODCAST_IMAGE)
        if img: fe.podcast.itunes_image(img)
        html_c = f'<img src="{img}" alt="" /><p>{desc}</p>'
        if ep.get("autor_cuento"): html_c += f'<p>Autor: <strong>{ep["autor_cuento"]}</strong></p>'
        html_c += f'<p>Fuente: <a href="{ep.get("fuente_url","")}">{ep.get("fuente","")}</a></p>'
        fe.content(html_c, type="html")
        
    fg.rss_file("rss.xml", encoding="utf-8", xml_declaration=True)

def build_json(eps):
    items = []
    for ep in eps:
        item = {"id": ep.get("guid",""), "url": ep.get("fuente_url",""), "title": ep["titulo"], "content_html": ep.get("descripcion",""), "date_published": datetime.fromisoformat(ep["fecha"]).isoformat() if ep.get("fecha") else datetime.now(timezone.utc).isoformat(), "authors": [{"name": "Alejandro Apo"}], "attachments": []}
        if ep.get("mp3_url"): item["attachments"].append({"url": ep["mp3_url"], "mime_type": "audio/mpeg", "duration_in_seconds": ep.get("duracion", 0)})
        if ep.get("imagen"): item["image"] = ep["imagen"]
        items.append(item)
    Path("feed.json").write_text(json.dumps({"version": "https://jsonfeed.org/version/1.1", "title": PODCAST_TITLE, "home_page_url": PODCAST_LINK, "feed_url": f"{PODCAST_LINK}feed.json", "description": PODCAST_DESCRIPTION, "icon": PODCAST_IMAGE, "items": items}, ensure_ascii=False, indent=2), encoding="utf-8")

def build_opml():
    Path("podcast.opml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><opml version="2.0"><head><title>{PODCAST_TITLE}</title></head><body><outline text="{PODCAST_TITLE}" type="rss" xmlUrl="{PODCAST_LINK}rss.xml" htmlUrl="{PODCAST_LINK}" /></body></opml>', encoding="utf-8")

def build_metadatos(eps):
    autores = sorted({ep["autor_cuento"] for ep in eps if ep.get("autor_cuento")})
    Path("metadatos.json").write_text(json.dumps({"podcast": {"titulo": PODCAST_TITLE, "rss": f"{PODCAST_LINK}rss.xml"}, "estadisticas": {"total_episodios": len(eps), "autores_unicos": len(autores), "lista_autores": autores}}, ensure_ascii=False, indent=2), encoding="utf-8")

def build_indice(eps):
    lines = [f"# {PODCAST_TITLE}", "", "| # | Titulo | Autor | Fuente | Duracion |", "|---|--------|-------|--------|----------|"]
    for i, ep in enumerate(eps, 1): lines.append(f"| {i} | {ep['titulo']} | {ep.get('autor_cuento', '-')} | {ep.get('fuente', '-')} | {duracion_str(ep.get('duracion', 0))} |")
    Path("INDICE.md").write_text("\n".join(lines), encoding="utf-8")

def build_html(eps):
    html = f'''<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>{PODCAST_TITLE}</title><style>:root{{--bg:#0d0d0d;--card:#1a1a1a;--border:#2a2a2a;--fg:#e0e0e0;--muted:#888;--accent:#c9a84c}}*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg);line-height:1.6}}header{{text-align:center;padding:3rem 1rem;border-bottom:1px solid var(--border)}}header h1{{font-size:2rem;color:var(--accent);margin-top:1rem}}header p{{color:var(--muted);margin-top:.5rem}}.feeds{{display:flex;justify-content:center;gap:1rem;margin-top:1.5rem;flex-wrap:wrap}}.feeds a{{padding:.5rem 1rem;background:var(--accent);color:#000;text-decoration:none;border-radius:6px;font-weight:600}}.feeds a.sec{{background:transparent;border:1px solid var(--border);color:var(--fg)}}main{{max-width:800px;margin:0 auto;padding:2rem 1rem}}.ep{{padding:1rem 0;border-bottom:1px solid var(--border)}}.ep h3{{margin-bottom:.2rem}}.meta{{font-size:.8rem;color:var(--muted)}}.meta strong{{color:var(--accent)}}footer{{text-align:center;padding:2rem;color:var(--muted);font-size:.8rem;border-top:1px solid var(--border);margin-top:2rem}}</style></head><body><header><h1>{PODCAST_TITLE}</h1><p>{PODCAST_SUBTITLE}</p><p style="max-width:600px;margin:1rem auto">{PODCAST_DESCRIPTION}</p><div class="feeds"><a href="rss.xml">RSS</a><a href="feed.json" class="sec">JSON</a><a href="podcast.opml" class="sec">OPML</a></div></header><div style="text-align:center;padding:1rem;color:var(--muted);font-size:.85rem;border-bottom:1px solid var(--border)">{len(eps)} episodios</div><main>'''
    for ep in eps:
        html += f'<article class="ep"><h3>{ep["titulo"]}</h3><div class="meta">{ep.get("autor_cuento","-")} | {ep.get("fecha","-")} | {duracion_str(ep.get("duracion",0))}</div><div style="font-size:.9rem;opacity:.8;margin-top:.5rem">{ep.get("descripcion","")[:200]}</div><div class="meta" style="margin-top:.3rem">Fuente: {ep.get("fuente","")}</div></article>'
    html += f'</main><footer>Feed independiente. Credito a fuentes originales en cada episodio.</footer></body></html>'
    Path("index.html").write_text(html, encoding="utf-8")

def main():
    eps = load_episodes()
    build_rss(eps)
    build_json(eps)
    build_opml()
    build_metadatos(eps)
    build_indice(eps)
    build_html(eps)
    print("Archivos generados correctamente.")

if __name__ == "__main__": main()