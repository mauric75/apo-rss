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
    # Versión interactiva: la página carga episodes.json vía JS
    # para tener búsqueda, filtros, paginación y más.
    html = r'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1.0">
    <title>Los cuentos de Alejandro Apo</title>
    <style>
        :root {
            --bg: #0d0d0d; --fg: #e8e8e8; --accent: #ff6b35;
            --card: #1a1a1a; --meta: #999; --border: #2a2a2a;
            --rn: #ff6b35; --anchor: #1db954; --rc: #3b82f6; --yt: #ef4444;
        }
        *{margin:0;padding:0;box-sizing:border-box}
        body{background:var(--bg);color:var(--fg);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;line-height:1.6}
        header{background:linear-gradient(135deg,var(--accent)0%,#ff8c42 100%);color:#fff;padding:2.5rem 2rem 2rem;text-align:center}
        .header-content{display:flex;align-items:center;justify-content:center;gap:1.5rem;flex-wrap:wrap;max-width:700px;margin:0 auto}
        .header-photo{width:100px;height:100px;border-radius:50%;border:3px solid rgba(255,255,255,.5);object-fit:cover;box-shadow:0 4px 20px rgba(0,0,0,.3)}
        .header-text{text-align:left}
        .header-text h1{font-size:2rem;margin-bottom:.2rem}
        .header-text p{opacity:.9;font-size:1rem}
        .subscribe{display:flex;gap:.75rem;justify-content:center;flex-wrap:wrap;margin-top:1rem}
        .subscribe a{background:rgba(255,255,255,.15);color:#fff;padding:.5rem 1.2rem;border-radius:50px;text-decoration:none;font-size:.85rem;border:1px solid rgba(255,255,255,.25);transition:all .2s}
        .subscribe a:hover{background:rgba(255,255,255,.3)}
        .stats{max-width:900px;margin:1.5rem auto 0;display:flex;gap:1rem;justify-content:center;flex-wrap:wrap;font-size:.85rem;opacity:.8}
        .stats span{background:var(--card);padding:.3rem .8rem;border-radius:50px}
        .toolbar{max-width:900px;margin:1.5rem auto;padding:0 1rem;display:flex;gap:.75rem;flex-wrap:wrap;align-items:center}
        #search{flex:1;min-width:180px;background:var(--card);border:1px solid var(--border);color:var(--fg);padding:.6rem 1rem;border-radius:8px;font-size:.9rem;outline:none}
        #search:focus{border-color:var(--accent)}
        select{background:var(--card);border:1px solid var(--border);color:var(--fg);padding:.6rem .8rem;border-radius:8px;font-size:.85rem;cursor:pointer;outline:none}
        select:focus{border-color:var(--accent)}
        .authors-bar{max-width:900px;margin:0 auto 1rem;padding:0 1rem;display:flex;gap:.4rem;flex-wrap:wrap;max-height:120px;overflow-y:auto}
        .authors-bar button{background:var(--card);border:1px solid var(--border);color:var(--meta);padding:.2rem .7rem;border-radius:50px;font-size:.75rem;cursor:pointer;white-space:nowrap;transition:all .2s}
        .authors-bar button:hover,.authors-bar button.active{background:var(--accent);color:#fff;border-color:var(--accent)}
        main{max-width:900px;margin:0 auto;padding:1rem}
        .ep{background:var(--card);border-left:4px solid var(--accent);padding:1.25rem;margin-bottom:1rem;border-radius:0 6px 6px 0;transition:transform .15s}
        .ep:hover{transform:translateX(2px)}
        .ep h3{font-size:1.05rem;margin-bottom:.4rem;color:var(--fg)}
        .ep .meta{font-size:.8rem;color:var(--meta);margin-bottom:.6rem;display:flex;gap:.5rem;flex-wrap:wrap;align-items:center}
        .badge{font-size:.65rem;padding:.15rem .5rem;border-radius:50px;color:#fff;font-weight:600;text-transform:uppercase;letter-spacing:.3px}
        .badge-rn{background:var(--rn)}.badge-anchor{background:var(--anchor)}.badge-rc{background:var(--rc)}.badge-yt{background:var(--yt)}
        .ep p{font-size:.85rem;color:var(--meta);margin-bottom:.75rem;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
        .ep audio{width:100%;height:32px;margin-top:.5rem;border-radius:6px}
        .ep audio::-webkit-media-controls-panel{background:var(--border)}
        .load-more{text-align:center;margin:1.5rem 0}
        .load-more button{background:var(--accent);color:#fff;border:none;padding:.7rem 2rem;border-radius:50px;font-size:.9rem;cursor:pointer;transition:opacity .2s}
        .load-more button:hover{opacity:.85}
        .no-results{text-align:center;color:var(--meta);padding:3rem}
        footer{background:var(--card);text-align:center;padding:1rem;border-top:1px solid var(--border);font-size:.8rem;color:var(--meta);margin-top:2rem}
        footer a{color:var(--accent);text-decoration:none}
        @media(max-width:600px){.header-content{flex-direction:column;text-align:center}.header-text{text-align:center}.header-text h1{font-size:1.4rem}.toolbar{flex-direction:column}#search{width:100%}}
    </style>
</head>
<body>
<header>
<div class="header-content">
<img class="header-photo" src="cover.jpg" alt="Alejandro Apo">
<div class="header-text">
    <h1>Los cuentos de Alejandro Apo</h1>
    <p>Colección automática de cuentos narrados por Alejandro Apo desde fuentes públicas argentinas.</p>
</div>
</div>
    <div class="subscribe">
        <a href="rss.xml">📻 RSS Feed</a>
        <a href="podcast.opml">📋 OPML</a>
        <a href="https://podcasts.apple.com/us/podcast/id1508165282">🎧 Apple Podcasts</a>
        <a href="https://open.spotify.com/show/alejandro-apo-am750">🟢 Spotify</a>
    </div>
    <div class="stats">
        <span id="stat-episodes">··· episodios</span>
        <span id="stat-authors">··· autores</span>
        <span id="stat-sources">··· fuentes</span>
        <span id="stat-range">····–····</span>
    </div>
</header>
<div class="toolbar">
    <input type="text" id="search" placeholder="🔍 Buscar por título, autor, fuente...">
    <select id="sort"><option value="newest">Más nuevos</option><option value="oldest">Más viejos</option><option value="az">Autor A-Z</option><option value="longest">Más largos</option></select>
    <select id="source-filter"><option value="all">Todas las fuentes</option></select>
</div>
<div class="authors-bar" id="authors-bar"></div>
<main id="episodes"></main>
<div class="load-more" id="load-more" style="display:none"><button onclick="loadMore()">Cargar más episodios</button></div>
<div class="no-results" id="no-results" style="display:none">😕 No se encontraron episodios con esos filtros.</div>
<footer>
    Feed independiente — <a href="https://github.com/mauric75/apo-rss">GitHub</a>
</footer>
<script>
const PER_PAGE = 25;
let allEpisodes = [];
let filtered = [];
let shown = 0;
let authorFilter = null;

function sourceBadge(fuente){
    const f = fuente.toLowerCase();
    if(f.includes("radio nacional")) return '<span class="badge badge-rn">RN</span>';
    if(f.includes("anchor")) return '<span class="badge badge-anchor">Anchor</span>';
    if(f.includes("radiocut")) return '<span class="badge badge-rc">RadioCut</span>';
    if(f.includes("youtube")) return '<span class="badge badge-yt">YT</span>';
    return '';
}

function fmtDuration(s){
    if(!s||s<=0)return'';
    const h=Math.floor(s/3600),m=Math.floor(s%3600/60);
    return h?h+':'+String(m).padStart(2,'0'):m+' min';
}

function renderEpisode(ep){
    const audio = ep.mp3_url ? `<audio controls preload="none"><source src="${ep.mp3_url}" type="audio/mpeg"></audio>` : '';
    const autor = ep.autor_cuento ? `<span>✍ ${ep.autor_cuento}</span>` : '';
    const badge = sourceBadge(ep.fuente);
    return `<article class="ep">
        <h3>${ep.titulo}</h3>
        <div class="meta">${badge} ${autor} <span>📅 ${ep.fecha||'?'}</span> <span>⏱ ${fmtDuration(ep.duracion)}</span></div>
        <p>${ep.descripcion||''}</p>
        ${audio}
        <div class="meta" style="margin-top:.5rem"><a href="${ep.fuente_url||'#'}" target="_blank" style="color:var(--accent);text-decoration:none">🔗 ${ep.fuente}</a></div>
    </article>`;
}

function filterAndSort(){
    const q = document.getElementById("search").value.toLowerCase();
    const srcFilter = document.getElementById("source-filter").value;
    const sort = document.getElementById("sort").value;
    
    filtered = allEpisodes.filter(ep => {
        if(authorFilter && ep.autor_cuento !== authorFilter) return false;
        if(srcFilter !== 'all'){
            const f = ep.fuente.toLowerCase();
            if(srcFilter === 'rn' && !f.includes('radio nacional')) return false;
            if(srcFilter === 'anchor' && !f.includes('anchor')) return false;
            if(srcFilter === 'rc' && !f.includes('radiocut')) return false;
            if(srcFilter === 'yt' && !f.includes('youtube')) return false;
        }
        if(q){
            const txt = (ep.titulo+' '+ep.autor_cuento+' '+ep.fuente+' '+ep.descripcion).toLowerCase();
            if(!txt.includes(q)) return false;
        }
        return true;
    });
    
    if(sort === 'newest') filtered.sort((a,b) => (b.fecha||'').localeCompare(a.fecha||''));
    else if(sort === 'oldest') filtered.sort((a,b) => (a.fecha||'').localeCompare(b.fecha||''));
    else if(sort === 'az') filtered.sort((a,b) => (a.titulo||'').localeCompare(b.titulo||''));
    else if(sort === 'longest') filtered.sort((a,b) => (b.duracion||0)-(a.duracion||0));
    
    shown = 0;
    document.getElementById("episodes").innerHTML = '';
    document.getElementById("no-results").style.display = 'none';
    loadMore();
}

function loadMore(){
    const container = document.getElementById("episodes");
    const toShow = filtered.slice(shown, shown + PER_PAGE);
    toShow.forEach(ep => container.innerHTML += renderEpisode(ep));
    shown += toShow.length;
    
    document.getElementById("load-more").style.display = shown < filtered.length ? '' : 'none';
    if(filtered.length === 0 && shown === 0){
        document.getElementById("no-results").style.display = '';
        document.getElementById("load-more").style.display = 'none';
    }
}

function buildAuthorBar(){
    const authors = {};
    allEpisodes.forEach(ep => {
        if(ep.autor_cuento){
            authors[ep.autor_cuento] = (authors[ep.autor_cuento]||0)+1;
        }
    });
    const sorted = Object.entries(authors).sort((a,b) => b[1]-a[1]);
    const bar = document.getElementById("authors-bar");
    bar.innerHTML = '<button class="active" onclick="authorFilter=null;updateAuthorButtons();filterAndSort()">Todos</button>';
    sorted.forEach(([author, count]) => {
        bar.innerHTML += `<button onclick="authorFilter='${author.replace(/'/g,"\\'")}';updateAuthorButtons();filterAndSort()">${author} (${count})</button>`;
    });
}

function updateAuthorButtons(){
    document.querySelectorAll("#authors-bar button").forEach(btn => {
        btn.classList.toggle("active", btn.textContent.startsWith(authorFilter||'Todos'));
    });
}

function buildSourceFilter(){
    const sources = {};
    allEpisodes.forEach(ep => {
        const f = ep.fuente.toLowerCase();
        if(f.includes('radio nacional')) sources['rn'] = (sources['rn']||0)+1;
        else if(f.includes('anchor')) sources['anchor'] = (sources['anchor']||0)+1;
        else if(f.includes('radiocut')) sources['rc'] = (sources['rc']||0)+1;
        else if(f.includes('youtube')) sources['yt'] = (sources['yt']||0)+1;
    });
    const sel = document.getElementById("source-filter");
    if(sources['rn']) sel.innerHTML += `<option value="rn">Radio Nacional (${sources['rn']})</option>`;
    if(sources['anchor']) sel.innerHTML += `<option value="anchor">Anchor.fm (${sources['anchor']})</option>`;
    if(sources['rc']) sel.innerHTML += `<option value="rc">RadioCut (${sources['rc']})</option>`;
    if(sources['yt']) sel.innerHTML += `<option value="yt">YouTube (${sources['yt']})</option>`;
}

async function init(){
    try{
        const resp = await fetch('episodes.json');
        allEpisodes = await resp.json();
    }catch(e){
        document.getElementById("episodes").innerHTML = '<div class="no-results">Error al cargar episodios 😞</div>';
        return;
    }
    
    // Stats
    const autores = new Set(allEpisodes.map(e=>e.autor_cuento).filter(Boolean));
    const fuentes = new Set(allEpisodes.map(e=>e.fuente.split(' - ')[0]));
    const dates = allEpisodes.map(e=>e.fecha).filter(Boolean).sort();
    document.getElementById("stat-episodes").textContent = allEpisodes.length+' episodios';
    document.getElementById("stat-authors").textContent = autores.size+' autores';
    document.getElementById("stat-sources").textContent = fuentes.size+' fuentes';
    document.getElementById("stat-range").textContent = (dates[0]||'?')+' – '+(dates[dates.length-1]||'?');
    
    buildAuthorBar();
    buildSourceFilter();
    filterAndSort();
    
    document.getElementById("search").addEventListener("input", filterAndSort);
    document.getElementById("sort").addEventListener("change", filterAndSort);
    document.getElementById("source-filter").addEventListener("change", filterAndSort);
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
