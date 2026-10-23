from __future__ import annotations
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import logging

import feedparser
import requests

from .utils import item_uid, clean_url
from .content_extractor import extract_fulltext

log = logging.getLogger(__name__)

FEED_TIMEOUT = 15  # secondes par flux
# Même en-têtes que feedparser : certains sites refusent un UA de navigateur sans cookies (403)
FEED_HEADERS = {
    "User-Agent": feedparser.USER_AGENT,
    "Accept": "application/atom+xml,application/rdf+xml,application/rss+xml,application/xml;q=0.9,*/*;q=0.1",
}


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


def download_feed(url: str, timeout: int = FEED_TIMEOUT):
    """Télécharge et parse un flux. Lève une exception si le flux est inutilisable.

    On passe par requests (avec timeout) plutôt que feedparser.parse(url),
    qui n'a pas de timeout et peut bloquer tout le brief sur un flux mort.
    """
    resp = requests.get(url, headers=FEED_HEADERS, timeout=timeout)
    resp.raise_for_status()
    d = feedparser.parse(resp.content)
    if d.bozo and not d.entries:
        raise ValueError(f"flux illisible ({type(d.bozo_exception).__name__})")
    return d


def _entry_to_item(e, d, section_name: str, since_dt: datetime) -> Optional[Dict[str, Any]]:
    title = getattr(e, 'title', '') or ''
    link = getattr(e, 'link', '') or ''
    summary = getattr(e, 'summary', '') or ''
    published_parsed = getattr(e, 'published_parsed', None) or getattr(e, 'updated_parsed', None)
    dt = datetime(*published_parsed[:6], tzinfo=timezone.utc) if published_parsed else datetime.now(timezone.utc)
    if dt < since_dt:
        return None

    # 1) on prend content:encoded s’il existe
    content_rss = _get_content_encoded(e)
    fulltext = ""
    # 2) sinon on récupère le texte complet sur la page
    if not content_rss or len(content_rss) < 600:
        fulltext = extract_fulltext(link)

    source = getattr(d.feed, 'title', '') or (getattr(e, 'source', None) or {}).get('title', '')
    return {
        'title': title.strip(),
        'link': clean_url(link),
        'summary': summary.strip(),
        'content': fulltext or content_rss,   # <- priorité au texte complet
        'published': dt.isoformat(),
        'source': source,
        'section': section_name,
    }


def fetch_section(
    section_name: str,
    feeds: List[str],
    since_dt: datetime,
    errors: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, Any]]:
    """Récupère les items de tous les flux d'une section.

    Un flux en erreur (réseau, HTTP, XML illisible) ou une entrée malformée est
    ignoré et journalisé : il ne fait jamais échouer la section. Si `errors` est
    fourni, chaque flux en échec y est ajouté ({'feed', 'error'}).
    """
    items: List[Dict[str, Any]] = []
    seen = set()
    for url in feeds:
        try:
            d = download_feed(url)
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            log.warning("[%s] flux ignoré %s — %s", section_name, url, msg)
            if errors is not None:
                errors.append({"feed": url, "error": msg})
            continue

        for e in d.entries:
            try:
                uid = item_uid(getattr(e, 'title', '') or '', getattr(e, 'link', '') or '')
                if uid in seen:
                    continue
                item = _entry_to_item(e, d, section_name, since_dt)
            except Exception as exc:
                log.warning("[%s] entrée ignorée dans %s — %s", section_name, url, exc)
                continue
            if item is None:
                continue
            seen.add(uid)
            items.append(item)
    items.sort(key=lambda x: x['published'], reverse=True)
    return items
