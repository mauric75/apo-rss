#!/usr/bin/env python3
"""Actualiza radiocut_urls.json desde los sitemaps de RadioCut.
   Busca audiocuts relacionados con Alejandro Apo.
   Ejecutar semanalmente o cuando se quieran descubrir nuevos audiocuts."""

import re, json, time
from pathlib import Path
import requests

SITEMAP_TEMPLATES = [
    "https://radiocut.fm/sitemap-cuts.xml",
] + [f"https://radiocut.fm/sitemap-cuts-p{i}.xml" for i in range(2, 15)]

OUTPUT_FILE = Path("radiocut_urls.json")
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; apo-rss-bot/1.0)"
})

def main():
    all_urls = set()
    
    for i, url in enumerate(SITEMAP_TEMPLATES):
        print(f"Sitemap {i+1}/{len(SITEMAP_TEMPLATES)}...", end=" ", flush=True)
        try:
            resp = SESSION.get(url, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"ERROR: {e}")
            continue
        
        urls = re.findall(r'<loc>https://radiocut\.fm/audiocut/([^<]+)</loc>', resp.text)
        
        # Filtrar URLs relacionadas con Apo
        count = 0
        for u in urls:
            ul = u.lower()
            if ('alejandro-apo' in ul or 'alejandroapo' in ul or
                'unsenorcuento' in ul or 'un-senor-cuento' in ul or
                'senor-cuento' in ul or 'senorcuento' in ul):
                all_urls.add(f"https://radiocut.fm/audiocut/{u}")
                count += 1
        
        print(f"{len(urls)} urls, {count} de Apo")
        time.sleep(1)
    
    sorted_urls = sorted(all_urls)
    OUTPUT_FILE.write_text(json.dumps(sorted_urls, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTotal: {len(sorted_urls)} URLs guardadas en {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
