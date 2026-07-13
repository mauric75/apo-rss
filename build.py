#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
from feedgen.feed import FeedGenerator

DATA_FILE = Path("episodes.json")
PODCAST_TITLE = "Los cuentos de Alejandro Apo"
PODCAST_SUBTITLE = "RSS independiente"
PODCAST_DESCRIPTION = "Coleccion automatica de cuentos narrados por Alejandro Apo, reunidos desde fuentes publicas: Radio Nacional Argentina y Los cuentos de Apo (Anchor.fm / Grupo Octubre)."
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
    fg.podcast.itunes_category("Arts", "Books")
    fg.podcast.itunes_owner(name=PODCAST_AUTHOR, email=PODCAST_EMAIL)
    fg.podcast.itunes_explicit("no")
    fg.podcast.itunes_image(PODCAST_IMAGE)
    fg.podcast.itunes_summary(PODCAST_DESCRIPTION)
    fg.podcast.itunes_type("episodic")
    fg.podcast.itunes_author(PODCAST_AUTHOR)
    fg.lastBuildDate(datetime.now(timezone.utc))
    fg.pubDate(datetime.now(timezone.utc))
    fg.generator("apo-rss (python-feedgen)")
    
    for ep in eps:
        fe = fg.add_entry()
        fe.id(ep.get("guid", ep.get("mp3_url", "")))
        fe.title(ep["titulo"])
        desc = ep.get("descripcion", "")
        fe.description(desc)
        fe.published(datetime.fromisoformat(ep["fecha"]).replace(tzinfo=timezone.utc) if ep.get("fecha") else datetime.now(timezone.utc))
        if ep.get("mp3_url"): fe.enclosure(ep["mp3_url"], str(int(ep.get("duracion", 0))), "audio/mpeg")
        fe.podcast.itunes_duration(duracion_str(ep.get("duracion", 0)))
        fe.podcast.itunes_summary(desc)
        fe.podcast.itunes_episode_type("full")
        if ep.get("autor_cuento"):
            fe.podcast.itunes_author(ep["autor_cuento"])
        else:
            fe.podcast.itunes_author(PODCAST_AUTHOR)
        img = ep.get("imagen", PODCAST_IMAGE)
        if img: fe.podcast.itunes_image(img)
        # Contenido HTML enriquecido
        html_parts = [f'<img src="{img}" alt="" style="max-width:100%;border-radius:8px" />'] if img else []
        html_parts.append(f'<p style="font-size:1.1em">{desc}</p>')
        if ep.get("autor_cuento"):
            html_parts.append(f'<p>✍ <strong>{ep["autor_cuento"]}</strong></p>')
        html_parts.append(f'<p>📅 {ep.get("fecha","")} · ⏱ {duracion_str(ep.get("duracion", 0))}</p>')
        if ep.get("fuente_url"):
            html_parts.append(f'<p>🔗 <a href="{ep["fuente_url"]}">{ep.get("fuente","")}</a></p>')
        html_parts.append(f'<hr><p><small>Narrado por Alejandro Apo · Feed independiente · <a href="{PODCAST_LINK}">{PODCAST_TITLE}</a></small></p>')
        fe.content("\n".join(html_parts), type="html")
        
    fg.rss_file("rss.xml", encoding="utf-8", xml_declaration=True)

def build_json(eps):
    items = []
    for ep in eps:
        item = {
            "id": ep.get("guid", ""),
            "url": ep.get("fuente_url", ""),
            "title": ep["titulo"],
            "content_html": ep.get("descripcion", ""),
            "date_published": datetime.fromisoformat(ep["fecha"]).isoformat() if ep.get("fecha") else datetime.now(timezone.utc).isoformat(),
            "attachments": []
        }
        if ep.get("mp3_url"): item["attachments"].append({"url": ep["mp3_url"], "mime_type": "audio/mpeg", "duration_in_seconds": ep.get("duracion", 0)})
        if ep.get("imagen"): item["image"] = ep["imagen"]
        items.append(item)
    Path("feed.json").write_text(json.dumps({
        "version": "https://jsonfeed.org/version/1.1",
        "title": PODCAST_TITLE,
        "home_page_url": PODCAST_LINK,
        "feed_url": f"{PODCAST_LINK}feed.json",
        "description": PODCAST_DESCRIPTION,
        "items": items
    }, ensure_ascii=False, indent=2), encoding="utf-8")

def build_opml():
    Path("podcast.opml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<opml version="2.0">'
        f'<head><title>{PODCAST_TITLE}</title></head>'
        f'<body>'
        f'<outline text="{PODCAST_TITLE}" type="rss" xmlUrl="{PODCAST_LINK}rss.xml" />'
        f'</body>'
        f'</opml>',
        encoding="utf-8"
    )

def build_metadatos(eps):
    autores = sorted({ep["autor_cuento"] for ep in eps if ep.get("autor_cuento")})
    fuentes = sorted({ep["fuente"] for ep in eps if ep.get("fuente")})
    Path("metadatos.json").write_text(json.dumps({
        "podcast": {
            "titulo": PODCAST_TITLE,
            "rss": f"{PODCAST_LINK}rss.xml",
            "generado": datetime.now(timezone.utc).isoformat()
        },
        "estadisticas": {
            "total_episodios": len(eps),
            "autores_unicos": len(autores),
            "fuentes": len(fuentes),
            "duracion_total_segundos": sum(ep.get("duracion", 0) for ep in eps)
        },
        "autores": autores,
        "fuentes": fuentes
    }, ensure_ascii=False, indent=2), encoding="utf-8")

def build_indice(eps):
    lines = [f"# {PODCAST_TITLE}", "", "| # | Titulo | Autor | Fuente | Duracion |", "|---|--------|-------|--------|----------|"]
    for i, ep in enumerate(eps, 1):
        lines.append(f"| {i} | {ep['titulo']} | {ep.get('autor_cuento', '-')} | {ep.get('fuente', '-')} | {duracion_str(ep.get('duracion', 0))} |")
    Path("INDICE.md").write_text("\n".join(lines), encoding="utf-8")

def build_html(eps):
    html = r'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache">
<title>Los cuentos de Alejandro Apo</title>
<meta name="description" content="Colección de 400+ cuentos narrados por Alejandro Apo desde radios argentinas.">
<meta property="og:title" content="Los cuentos de Alejandro Apo">
<meta property="og:description" content="Colección de cuentos narrados por Alejandro Apo. RSS, Apple Podcasts, Spotify.">
<meta property="og:image" content="https://mauric75.github.io/apo-rss/cover.jpg">
<link rel="icon" href="cover.jpg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,500;0,700;0,900;1,500&family=DM+Sans:ital,wght@0,400;0,500;0,700;1,400&display=swap" rel="stylesheet">
<style>
:root{
--bg:#0a0a0c;--surface:#131316;--card:#1a1a1e;--fg:#e4e4e4;--accent:#f59e0b;--accent2:#d97706;
--muted:#888;--border:#252530;--glow:rgba(245,158,11,.08);--rn:#f59e0b;--anchor:#10b981;--rc:#3b82f6;--yt:#ef4444;
}
body.light{--bg:#faf8f5;--surface:#fff;--card:#fff;--fg:#1a1a1a;--accent:#d97706;--accent2:#b45309;--muted:#666;--border:#e5e0d8;--glow:rgba(217,119,6,.05)}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font-family:"DM Sans",-apple-system,sans-serif;line-height:1.6;transition:background .4s,color .4s;overflow-x:hidden}
body::before{content:'';position:fixed;top:-50%;left:-50%;width:200%;height:200%;background:radial-gradient(circle at 50% 0%,var(--glow) 0%,transparent 60%);pointer-events:none;z-index:0}
/* Masthead */
.masthead{position:relative;z-index:1;max-width:1100px;margin:0 auto;padding:3rem 1.5rem 2rem;text-align:center;border-bottom:1px solid var(--border)}
.masthead-top{display:flex;align-items:center;justify-content:center;gap:.6rem;margin-bottom:.5rem}
.onair-dot{width:9px;height:9px;background:#ef4444;border-radius:50%;animation:pulse 2s infinite;box-shadow:0 0 10px #ef4444}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.onair-text{font-size:.65rem;text-transform:uppercase;letter-spacing:.2em;color:#ef4444;font-weight:700}
.freq-bar{display:flex;align-items:center;justify-content:center;gap:.4rem;margin-bottom:1.5rem;font-size:.65rem;color:var(--muted);letter-spacing:.15em}
.freq-bar span{color:var(--accent);font-weight:700;font-size:.85rem}
.freq-line{flex:1;max-width:200px;height:1px;background:linear-gradient(90deg,transparent,var(--accent),transparent)}
.masthead-inner{display:flex;align-items:center;justify-content:center;gap:1.5rem;flex-wrap:wrap}
.masthead-photo{width:90px;height:90px;border-radius:50%;object-fit:cover;border:2px solid var(--accent);box-shadow:0 0 30px var(--glow)}
.masthead-title{font-family:"Playfair Display",Georgia,serif;font-size:2.8rem;font-weight:900;line-height:1;letter-spacing:-1px}
.masthead-title span{color:var(--accent)}
.masthead-sub{font-size:.85rem;color:var(--muted);margin-top:.5rem;font-style:italic;font-weight:400}
.masthead-links{display:flex;gap:1rem;justify-content:center;flex-wrap:wrap;margin-top:1.2rem;font-size:.72rem}
.masthead-links a{color:var(--muted);text-decoration:none;padding:.25rem .6rem;border:1px solid var(--border);transition:all .2s;letter-spacing:.03em}
.masthead-links a:hover{color:var(--accent);border-color:var(--accent)}
/* Stats */
.stats-bar{max-width:1100px;margin:1rem auto;padding:0 1.5rem;text-align:center;font-size:.68rem;color:var(--muted);letter-spacing:.06em;position:relative;z-index:1}
.stats-bar span{margin:0 .6rem}
.stats-bar .update{color:var(--accent);font-weight:600}
/* Top bar */
.top-bar{display:flex;justify-content:flex-end;max-width:1100px;margin:.5rem auto 0;padding:0 1.5rem;gap:.3rem;position:relative;z-index:1}
.icon-btn{background:var(--surface);border:1px solid var(--border);color:var(--muted);padding:.35rem .8rem;cursor:pointer;font-size:.68rem;font-family:"DM Sans",sans-serif;transition:all .2s;letter-spacing:.04em}
.icon-btn:hover{color:var(--accent);border-color:var(--accent);background:var(--card)}
/* Toolbar */
.toolbar{max-width:1100px;margin:1.2rem auto;padding:0 1.5rem;display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;position:relative;z-index:1}
#search{flex:1;min-width:180px;background:var(--surface);border:1px solid var(--border);color:var(--fg);padding:.6rem .9rem;font-size:.82rem;outline:none;font-family:"DM Sans",sans-serif;transition:border .2s}
#search:focus{border-color:var(--accent)}
#search::placeholder{color:var(--muted)}
select{background:var(--surface);border:1px solid var(--border);color:var(--fg);padding:.5rem .7rem;font-size:.75rem;cursor:pointer;outline:none;font-family:"DM Sans",sans-serif}
/* Chips */
.chip-bar{max-width:1100px;margin:0 auto .5rem;padding:0 1.5rem;display:flex;gap:.25rem;flex-wrap:wrap;max-height:100px;overflow-y:auto;position:relative;z-index:1}
.chip-bar button{background:var(--surface);border:1px solid var(--border);color:var(--muted);padding:.15rem .7rem;font-size:.65rem;cursor:pointer;font-family:"DM Sans",sans-serif;transition:all .2s;letter-spacing:.03em}
.chip-bar button:hover,.chip-bar button.active{background:var(--accent);color:#000;border-color:var(--accent);font-weight:600}
/* Episodes grid */
main{max-width:1100px;margin:1.5rem auto;padding:0 1.5rem;display:flex;flex-direction:column;gap:.5rem;position:relative;z-index:1}
.ep{background:var(--card);border:1px solid var(--border);padding:1.2rem;transition:all .25s;position:relative;overflow:hidden}
.ep::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--accent),transparent);opacity:0;transition:opacity .3s}
.ep:hover::before{opacity:1}
.ep:hover{border-color:var(--accent);transform:translateY(-2px);box-shadow:0 8px 30px rgba(0,0,0,.3)}
.ep:first-child h3{font-size:1.15rem}

.ep h3{font-family:"Playfair Display",Georgia,serif;font-size:1rem;font-weight:700;line-height:1.3;margin-bottom:.4rem;color:var(--fg)}
.ep h3 a{color:inherit;text-decoration:none}
.ep .meta{font-size:.65rem;color:var(--muted);margin-bottom:.6rem;display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;letter-spacing:.03em}
.source-dot{width:7px;height:7px;border-radius:50%;display:inline-block;flex-shrink:0}
.s-rn{background:var(--rn)}.s-anchor{background:var(--anchor)}.s-rc{background:var(--rc)}.s-yt{background:var(--yt)}
.ep .desc{font-size:.78rem;color:var(--muted);margin-bottom:.8rem;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;line-height:1.5}
.ep audio{width:100%;height:34px;margin-top:.5rem;border-radius:2px}
.ep audio::-webkit-media-controls-panel{background:var(--surface)}
.ep audio::-webkit-media-controls-current-time-display,
.ep audio::-webkit-media-controls-time-remaining-display{color:var(--fg);font-family:"DM Sans",sans-serif}
.ep-actions{display:flex;gap:.35rem;flex-wrap:wrap;align-items:center;margin-top:.6rem}
.ep-actions a,.ep-actions button{color:var(--muted);text-decoration:none;background:var(--surface);border:1px solid var(--border);padding:.2rem .55rem;cursor:pointer;font-family:"DM Sans",sans-serif;font-size:.62rem;transition:all .2s;letter-spacing:.03em}
.ep-actions a:hover,.ep-actions button:hover{color:var(--accent);border-color:var(--accent)}
.ep-actions .speed-select{padding:.15rem .3rem;font-size:.6rem;background:var(--surface);border:1px solid var(--border);color:var(--muted)}
.listened-badge{color:#10b981;font-weight:600;font-size:.6rem;letter-spacing:.04em}
.ep.listened{opacity:.5}
.ep.listened:hover{opacity:.8}
/* Float elements */
.queue-panel{position:fixed;bottom:0;right:0;width:300px;max-height:45vh;background:var(--card);border:1px solid var(--border);border-bottom:none;box-shadow:0 -4px 30px rgba(0,0,0,.4);z-index:150;transform:translateY(100%);transition:transform .35s cubic-bezier(.4,0,.2,1);overflow-y:auto}
.queue-panel.open{transform:translateY(0)}
.queue-panel h4{position:sticky;top:0;background:var(--accent);color:#000;padding:.5rem .8rem;font-size:.75rem;display:flex;justify-content:space-between;align-items:center;z-index:1;font-weight:700;letter-spacing:.04em}
.queue-panel h4 button{background:none;border:none;color:#000;cursor:pointer;font-size:1.1rem}
.queue-item{display:flex;align-items:center;gap:.4rem;padding:.45rem .8rem;border-bottom:1px solid var(--border);font-size:.7rem;cursor:pointer;transition:background .15s}
.queue-item:hover{background:var(--surface)}
.queue-item .remove{color:var(--muted);font-size:1rem;flex-shrink:0;cursor:pointer}
.queue-item .remove:hover{color:#ef4444}
.queue-badge{position:fixed;bottom:1.5rem;right:5rem;background:var(--accent);color:#000;border:none;width:42px;height:42px;cursor:pointer;box-shadow:0 4px 20px rgba(0,0,0,.4);z-index:149;display:none;font-weight:700;font-size:.65rem;letter-spacing:.03em}
.queue-count{position:absolute;top:-5px;right:-5px;background:#ef4444;color:#fff;font-size:.55rem;width:17px;height:17px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700}
#top-btn{position:fixed;bottom:1.5rem;right:1.5rem;background:var(--surface);color:var(--fg);border:1px solid var(--border);width:42px;height:42px;cursor:pointer;display:none;box-shadow:0 4px 20px rgba(0,0,0,.4);z-index:100;font-size:.8rem;transition:all .2s}
#top-btn:hover{border-color:var(--accent);color:var(--accent)}
/* Audio-only mode */
body.audio-only .ep .desc,body.audio-only .ep .meta,body.audio-only .ep-actions,body.audio-only .toolbar,body.audio-only #timeline,body.audio-only #authors-bar,body.audio-only #top-authors,body.audio-only .masthead-links,body.audio-only .stats-bar,body.audio-only footer{display:none!important}
body.audio-only main{padding-top:.3rem;display:block;max-width:700px}
body.audio-only .ep{padding:.6rem 1rem;margin-bottom:.3rem}

body.audio-only .ep h3{font-size:.85rem}
/* Top authors */
.top-authors{max-width:1100px;margin:2rem auto 0;padding:1.5rem 1.5rem 0;border-top:1px solid var(--border);position:relative;z-index:1}
.top-authors h3{font-family:"Playfair Display",Georgia,serif;font-size:.85rem;color:var(--muted);margin-bottom:.8rem;text-align:center;letter-spacing:.08em;font-weight:400}
.top-authors ol{display:flex;flex-wrap:wrap;gap:.3rem 1.5rem;justify-content:center;list-style:none;font-size:.7rem;color:var(--muted)}
.top-authors li{cursor:pointer;transition:color .2s}
.top-authors li:hover{color:var(--accent)}
.no-results{text-align:center;color:var(--muted);padding:4rem;font-style:italic;grid-column:1/-1}
.toast{position:fixed;bottom:5rem;left:50%;transform:translateX(-50%);background:var(--accent);color:#000;padding:.4rem 1.2rem;font-size:.75rem;z-index:200;opacity:0;transition:opacity .3s;pointer-events:none;font-weight:600;letter-spacing:.03em}
.toast.show{opacity:1}
footer{text-align:center;padding:2rem 1rem;font-size:.65rem;color:var(--muted);border-top:1px solid var(--border);margin-top:2rem;max-width:1100px;margin-left:auto;margin-right:auto;letter-spacing:.06em;position:relative;z-index:1}
footer a{color:var(--accent);text-decoration:none}
footer a:hover{text-decoration:underline}
@media(max-width:650px){
.masthead-title{font-size:1.8rem}
main{grid-template-columns:1fr}
.toolbar{flex-direction:column}#search{width:100%}
.masthead-inner{flex-direction:column;text-align:center}
}
</style>
</head>
<body>
<div class="masthead">
<div class="masthead-top">
<div class="onair-dot"></div>
<div class="onair-text">En el aire</div>
</div>
<div class="freq-bar"><span>AM</span><div class="freq-line"></div><span>750</span><div class="freq-line"></div><span>FM</span></div>
<div class="masthead-inner">
<img class="masthead-photo" src="cover.jpg" alt="Alejandro Apo">
<div>
<div class="masthead-title"><span>Los</span> cuentos de<br>Alejandro Apo</div>
<div class="masthead-sub">Archivo independiente — narraciones desde radios argentinas</div>
</div>
</div>
<div class="masthead-links">
<a href="rss.xml">RSS</a>
<a href="podcast.opml">OPML</a>
<a href="https://podcasts.apple.com/us/podcast/id1508165282">Apple Podcasts</a>
<a href="https://open.spotify.com/show/alejandro-apo-am750">Spotify</a>
<a href="https://pca.st/itunes/1508165282">Pocket Casts</a>
<a href="https://validator.w3.org/feed/check.cgi?url=https%3A%2F%2Fmauric75.github.io%2Fapo-rss%2Frss.xml">Validar</a>
</div>
</div>
<div class="stats-bar" id="stats-bar">
<span id="stat-episodes">··· cuentos</span>
<span id="stat-authors">··· autores</span>
<span id="stat-sources">··· fuentes</span>
<span id="stat-range">···· – ····</span>
<span class="update" id="stat-updated">Actualizado: ···</span>
</div>
<div class="top-bar">
<button class="icon-btn" id="theme-btn" onclick="toggleTheme()">☀</button>
<button class="icon-btn" id="random-btn" onclick="randomEpisode()">Al azar</button>
<button class="icon-btn" id="audio-mode-btn" onclick="toggleAudioMode()">Solo audio</button>
<button class="icon-btn" id="listened-filter-btn" onclick="toggleListenedFilter()">No escuchados</button>
</div>
<div class="toolbar">
<input type="text" id="search" placeholder="Buscar por título, autor o fuente...">
<select id="sort"><option value="newest">Más nuevos</option><option value="oldest">Más viejos</option><option value="az">Autor A–Z</option><option value="longest">Más largos</option></select>
<select id="source-filter"><option value="all">Todas las fuentes</option></select>
</div>
<div class="chip-bar" id="timeline"></div>
<div class="chip-bar" id="authors-bar"></div>
<main id="episodes"></main>
<div class="no-results" id="no-results" style="display:none">No se encontraron episodios.</div>
<div class="top-authors" id="top-authors"></div>
<button id="top-btn" onclick="window.scrollTo({top:0,behavior:'smooth'})">↑</button>
<div class="toast" id="toast"></div>
<div class="queue-panel" id="queue-panel">
<h4>Cola de reproducción <button onclick="toggleQueue()">×</button></h4>
<div id="queue-list" style="font-size:.7rem;color:var(--muted);padding:1rem;text-align:center">Agregá episodios con + Cola</div>
</div>
<button class="queue-badge" id="queue-badge" onclick="toggleQueue()">COLA<span class="queue-count" id="queue-count" style="display:none">0</span></button>
<footer>
Feed independiente · <a href="https://github.com/mauric75/apo-rss">GitHub</a> · <span style="cursor:pointer" onclick="randomEpisode()">Cuento al azar</span>
</footer>
<script>
const PER_PAGE=25;
let allEpisodes=[],filtered=[],shown=0,authorFilter=null,yearFilter=null,currentAudio=null;
function sourceDot(f){
const l=f.toLowerCase();
if(l.includes("radio nacional"))return'<span class="source-dot s-rn" title="Radio Nacional"></span> RN';
if(l.includes("anchor"))return'<span class="source-dot s-anchor" title="Anchor.fm"></span> Anchor';
if(l.includes("radiocut"))return'<span class="source-dot s-rc" title="RadioCut"></span> RadioCut';
if(l.includes("youtube"))return'<span class="source-dot s-yt" title="YouTube"></span> YT';
return'';
}
function fmtDuration(s){
if(!s||s<=0)return'';const h=Math.floor(s/3600),m=Math.floor(s%3600/60),sec=Math.floor(s%60);
return h?h+':'+String(m).padStart(2,'0')+'h':m+':'+String(sec).padStart(2,'0')+' min';
}
function toast(msg){const t=document.getElementById("toast");t.textContent=msg;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),2000);}
function renderEpisode(ep,i){
const id='ep-'+i,listened=listenedSet.has(ep.guid||ep.mp3_url),cls=listened?' listened':'';
const lBadge=listened?' <span class="listened-badge">Escuchado</span>':'';
const audio=ep.mp3_url?`<audio id="${id}" controls preload="none" onplay="onAudioPlay(this)" onended="onAudioEnded(this)"><source src="${ep.mp3_url}" type="audio/mpeg"></audio>`:'';
const autor=ep.autor_cuento?`<span>— ${ep.autor_cuento}</span>`:'',dot=sourceDot(ep.fuente);
return`<article class="ep${cls}" data-guid="${ep.guid||ep.mp3_url||''}"><div class="ep-body">
<h3>${ep.titulo}${lBadge}</h3>
<div class="meta">${dot} ${autor} &nbsp; ${ep.fecha||'?'} &nbsp; ${fmtDuration(ep.duracion)}</div>
<div class="desc">${ep.descripcion||''}</div>
${audio}
<div class="ep-actions">
${ep.mp3_url?`<a href="${ep.mp3_url}" target="_blank">Abrir audio</a>`:""}
<select class="speed-select" onchange="changeSpeed('${id}',this.value)"><option value="1">1x</option><option value="1.25">1.25x</option><option value="1.5">1.5x</option><option value="2">2x</option></select>
<a href="https://wa.me/?text=${encodeURIComponent(ep.titulo)}%20${encodeURIComponent(ep.fuente_url||'')}" target="_blank">WhatsApp</a>
<button onclick="copyLink('${ep.fuente_url||''}')">Copiar link</button>
<button onclick="addToQueue('${id}','${ep.titulo.replace(/'/g,"\\'")}','${ep.autor_cuento||''}')">+ Cola</button>
${listened?'<button onclick="markUnlistened(\''+(ep.guid||ep.mp3_url)+'\')">Pendiente</button>':'<button onclick="markListened(\''+(ep.guid||ep.mp3_url)+'\')">Escuchado</button>'}
<a href="${ep.fuente_url||'#'}" target="_blank">Fuente</a>
</div></div></article>`;
}
function onAudioPlay(audio){if(currentAudio&&currentAudio!==audio)currentAudio.pause();currentAudio=audio;}
function onAudioEnded(audio){currentAudio=null;const all=[...document.querySelectorAll('main audio')];const idx=all.indexOf(audio);if(idx>=0&&idx<all.length-1){all[idx+1].scrollIntoView({behavior:'smooth',block:'center'});all[idx+1].play();}}
function changeSpeed(id,val){const a=document.getElementById(id);if(a)a.playbackRate=parseFloat(val);}
function copyLink(url){navigator.clipboard.writeText(url).then(()=>toast('Link copiado'));}
function randomEpisode(){if(!filtered.length)return;const ep=filtered[Math.floor(Math.random()*filtered.length)];document.getElementById("search").value='';authorFilter=null;yearFilter=null;updateButtons();filterAndSort();setTimeout(()=>{const audios=[...document.querySelectorAll('main audio')];const idx=allEpisodes.indexOf(ep);if(idx>=0&&audios[idx]){audios[idx].scrollIntoView({behavior:'smooth',block:'center'});audios[idx].play();toast(ep.titulo.substring(0,60)+'...');}},300);}
function filterAndSort(){
const q=document.getElementById("search").value.toLowerCase(),srcFilter=document.getElementById("source-filter").value,sort=document.getElementById("sort").value;
filtered=allEpisodes.filter(ep=>{
if(authorFilter&&ep.autor_cuento!==authorFilter)return false;if(yearFilter&&(ep.fecha||'').substring(0,4)!==yearFilter)return false;
if(srcFilter!=='all'){const f=ep.fuente.toLowerCase();if(srcFilter==='rn'&&!f.includes('radio nacional'))return false;if(srcFilter==='anchor'&&!f.includes('anchor'))return false;if(srcFilter==='rc'&&!f.includes('radiocut'))return false;if(srcFilter==='yt'&&!f.includes('youtube'))return false;}
if(q){const t=(ep.titulo+' '+ep.autor_cuento+' '+ep.fuente+' '+ep.descripcion).toLowerCase();if(!t.includes(q))return false;}
if(hideListened&&listenedSet.has(ep.guid||ep.mp3_url))return false;return true;
});
if(sort==='newest')filtered.sort((a,b)=>(b.fecha||'').localeCompare(a.fecha||''));else if(sort==='oldest')filtered.sort((a,b)=>(a.fecha||'').localeCompare(b.fecha||''));else if(sort==='az')filtered.sort((a,b)=>(a.titulo||'').localeCompare(b.titulo||''));else if(sort==='longest')filtered.sort((a,b)=>(b.duracion||0)-(a.duracion||0));
shown=0;document.getElementById("episodes").innerHTML='';document.getElementById("no-results").style.display='none';currentAudio=null;loadMore();
}
function loadMore(){const c=document.getElementById("episodes");const startIdx=shown,toShow=filtered.slice(shown,shown+PER_PAGE);toShow.forEach((ep,i)=>c.innerHTML+=renderEpisode(ep,startIdx+i));shown+=toShow.length;document.getElementById("no-results").style.display=(filtered.length===0&&shown===0)?'':'none';}
let scrollTimeout;window.addEventListener('scroll',()=>{clearTimeout(scrollTimeout);scrollTimeout=setTimeout(()=>{document.getElementById("top-btn").style.display=window.scrollY>500?'':'none';if(shown<filtered.length&&window.innerHeight+window.scrollY>=document.body.offsetHeight-400)loadMore();},100);});
document.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT'||e.target.tagName==='SELECT')return;if(e.key==='r'||e.key==='R')randomEpisode();if(e.key==='f'||e.key==='F')document.getElementById("search").focus();if(e.key==='ArrowLeft')window.scrollBy({top:-400,behavior:'smooth'});if(e.key==='ArrowRight')window.scrollBy({top:400,behavior:'smooth'});});
function toggleTheme(){const isLight=document.body.classList.toggle('light');document.getElementById("theme-btn").textContent=isLight?'🌙':'☀';localStorage.setItem('theme',isLight?'light':'dark');}
function buildTimeline(){const years={};allEpisodes.forEach(ep=>{const y=(ep.fecha||'????').substring(0,4);years[y]=(years[y]||0)+1;});const sorted=Object.keys(years).sort().reverse();const t=document.getElementById("timeline");t.innerHTML='<button class="active" onclick="yearFilter=null;updateButtons();filterAndSort()">Todos los años</button>';sorted.forEach(y=>{t.innerHTML+=`<button onclick="yearFilter='${y}';updateButtons();filterAndSort()">${y} (${years[y]})</button>`;});}
function buildAuthorBar(){const authors={};allEpisodes.forEach(ep=>{if(ep.autor_cuento)authors[ep.autor_cuento]=(authors[ep.autor_cuento]||0)+1;});const sorted=Object.entries(authors).sort((a,b)=>b[1]-a[1]);const bar=document.getElementById("authors-bar");bar.innerHTML='<button class="active" onclick="authorFilter=null;updateButtons();filterAndSort()">Todos los autores</button>';sorted.forEach(([a,c])=>{bar.innerHTML+=`<button onclick="authorFilter='${a.replace(/'/g,"\\'")}';updateButtons();filterAndSort()">${a} (${c})</button>`;});const top=document.getElementById("top-authors");top.innerHTML='<h3>Autores con más cuentos</h3><ol>'+sorted.slice(0,10).map(([a,c])=>`<li onclick="authorFilter='${a.replace(/'/g,"\\'")}';updateButtons();filterAndSort();window.scrollTo({top:300,behavior:'smooth'})">${a} (${c})</li>`).join('')+'</ol>';}
function updateButtons(){document.querySelectorAll("#authors-bar button,#timeline button").forEach(b=>{const t=b.textContent;b.classList.toggle("active",t.startsWith(authorFilter||'Todos')||t.startsWith(yearFilter||'Todos'));});}
function buildSourceFilter(){const s={};allEpisodes.forEach(ep=>{const f=ep.fuente.toLowerCase();if(f.includes('radio nacional'))s['rn']=(s['rn']||0)+1;else if(f.includes('anchor'))s['anchor']=(s['anchor']||0)+1;else if(f.includes('radiocut'))s['rc']=(s['rc']||0)+1;else if(f.includes('youtube'))s['yt']=(s['yt']||0)+1;});const sel=document.getElementById("source-filter");if(s['rn'])sel.innerHTML+='<option value="rn">Radio Nacional ('+s['rn']+')</option>';if(s['anchor'])sel.innerHTML+='<option value="anchor">Anchor.fm ('+s['anchor']+')</option>';if(s['rc'])sel.innerHTML+='<option value="rc">RadioCut ('+s['rc']+')</option>';if(s['yt'])sel.innerHTML+='<option value="yt">YouTube ('+s['yt']+')</option>';}
let queue=[];function addToQueue(audioId,title,author){queue.push({audioId,title,author});renderQueue();document.getElementById("queue-badge").style.display='';toast('+ Cola: '+title.substring(0,50));}
function removeFromQueue(idx){queue.splice(idx,1);renderQueue();if(!queue.length)document.getElementById("queue-badge").style.display='none';}
function renderQueue(){const list=document.getElementById("queue-list"),count=document.getElementById("queue-count");if(!queue.length){list.innerHTML='<div style="padding:1rem;text-align:center;color:var(--muted)">Cola vacía</div>';count.style.display='none';}else{list.innerHTML=queue.map((q,i)=>`<div class="queue-item" onclick="playFromQueue(${i})"><span class="remove" onclick="event.stopPropagation();removeFromQueue(${i})">×</span><span style="flex:1">${q.title.substring(0,50)}</span><span style="color:var(--muted);font-size:.6rem">${(q.author||'').substring(0,20)}</span></div>`).join('');count.textContent=queue.length;count.style.display='';}}
function playFromQueue(idx){const q=queue[idx];const a=document.getElementById(q.audioId);if(a){a.scrollIntoView({behavior:'smooth',block:'center'});a.play();}queue.splice(idx,1);renderQueue();}
function toggleQueue(){document.getElementById("queue-panel").classList.toggle("open");}
function toggleAudioMode(){const isOn=document.body.classList.toggle("audio-only");document.getElementById("audio-mode-btn").textContent=isOn?'Vista completa':'Solo audio';localStorage.setItem('audioOnly',isOn?'1':'0');}
let listenedSet=new Set(JSON.parse(localStorage.getItem('listened')||'[]')),hideListened=false;
function markListened(guid){listenedSet.add(guid);saveListened();refreshDisplay();}
function markUnlistened(guid){listenedSet.delete(guid);saveListened();refreshDisplay();}
function saveListened(){localStorage.setItem('listened',JSON.stringify([...listenedSet]));}
function toggleListenedFilter(){hideListened=!hideListened;document.getElementById("listened-filter-btn").textContent=hideListened?'Mostrar todos':'No escuchados';refreshDisplay();}
function refreshDisplay(){filterAndSort();renderQueue();}
async function init(){
try{const r=await fetch('episodes.json');allEpisodes=await r.json();}catch(e){document.getElementById("episodes").innerHTML='<div class="no-results">Error al cargar episodios.</div>';return;}
const autores=new Set(allEpisodes.map(e=>e.autor_cuento).filter(Boolean)),fuentes=new Set(allEpisodes.map(e=>e.fuente.split(' - ')[0]));
const dates=allEpisodes.map(e=>e.fecha).filter(Boolean).sort();
document.getElementById("stat-episodes").textContent=allEpisodes.length+' cuentos';
document.getElementById("stat-authors").textContent=autores.size+' autores';
document.getElementById("stat-sources").textContent=fuentes.size+' fuentes';
document.getElementById("stat-range").textContent=(dates[0]||'?')+' – '+(dates[dates.length-1]||'?');
const extraidos=allEpisodes.map(e=>e.extraido).filter(Boolean).sort().reverse();const lastUpdate=extraidos[0];
let updateText='Actualizado: ';if(lastUpdate){const diff=Date.now()-new Date(lastUpdate).getTime();const hours=Math.floor(diff/3600000),days=Math.floor(hours/24);updateText+=days>0?'hace '+days+' día'+(days>1?'s':''):hours>0?'hace '+hours+'h':'ahora';}else updateText+='desconocido';
document.getElementById("stat-updated").textContent=updateText;
if(localStorage.getItem('theme')==='light'){document.body.classList.add('light');document.getElementById("theme-btn").textContent='🌙';}
if(localStorage.getItem('audioOnly')==='1'){document.body.classList.add('audio-only');document.getElementById("audio-mode-btn").textContent='Vista completa';}
buildTimeline();buildAuthorBar();buildSourceFilter();filterAndSort();
document.getElementById("search").addEventListener("input",filterAndSort);
document.getElementById("sort").addEventListener("change",filterAndSort);
document.getElementById("source-filter").addEventListener("change",filterAndSort);
}
init();
</script>
</body>
</html>'''
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
