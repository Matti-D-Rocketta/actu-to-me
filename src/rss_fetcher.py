from __future__ import annotations
from typing import Dict, List, Any
from datetime import datetime, timezone
import feedparser

from .utils import item_uid, clean_url
from .content_extractor import extract_fulltext

def _get_content_encoded(entry) -> str:
    # RSS "riches" -> content:encoded
    try:
        if hasattr(entry, "content") and entry.content:
            return entry.content[0].get("value", "") or ""
    except Exception:
        pass
    try:
        return getattr(entry, "summary", "") or ""
    except Exception:
        return ""

def fetch_section(section_name: str, feeds: List[str], since_dt: datetime) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    seen = set()
    for url in feeds:
        try:
            d = feedparser.parse(url)
        except Exception:
            continue
        for e in d.entries:
            title = getattr(e, 'title', '') or ''
            link  = getattr(e, 'link', '') or ''
            summary = getattr(e, 'summary', '') or ''
            published_parsed = getattr(e, 'published_parsed', None) or getattr(e, 'updated_parsed', None)
            dt = datetime(*published_parsed[:6], tzinfo=timezone.utc) if published_parsed else datetime.now(timezone.utc)
            if dt < since_dt:
                continue
            uid = item_uid(title, link)
            if uid in seen:
                continue
            seen.add(uid)

            # 1) on prend content:encoded s’il existe
            content_rss = _get_content_encoded(e)
            fulltext = ""
            # 2) sinon on récupère le texte complet sur la page
            if not content_rss or len(content_rss) < 600:
                fulltext = extract_fulltext(link)

            items.append({
                'title': title.strip(),
                'link': clean_url(link),
                'summary': (summary or "").strip(),
                'content': fulltext or content_rss,   # <- priorité au texte complet
                'published': dt.isoformat(),
                'source': getattr(d.feed, 'title', '') or getattr(e, 'source', {}).get('title', ''),
                'section': section_name,
            })
    items.sort(key=lambda x: x['published'], reverse=True)
    return items
