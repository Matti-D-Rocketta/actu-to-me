from __future__ import annotations
from datetime import datetime, timedelta, timezone
import hashlib, re

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def parse_since(s: str) -> timedelta:
    s = s.strip().lower()
    if s.endswith("h"):
        return timedelta(hours=int(s[:-1]))
    if s.endswith("d"):
        return timedelta(days=int(s[:-1]))
    raise ValueError("Format invalide pour --since (ex: 24h, 2d)")

def normalize_url(u: str) -> str:
    return re.sub(r"[\/#?&]+$", "", u or "").strip()

def item_uid(title: str, link: str) -> str:
    base = (title or "") + "|" + (link or "")
    return hashlib.sha1(base.encode("utf-8")).hexdigest()

def clamp_text(txt: str, max_chars: int) -> str:
    txt = txt.strip()
    if len(txt) <= max_chars:
        return txt
    return txt[:max_chars] + "\n[...]"

from urllib.parse import urlparse, urlunparse

def clean_url(u: str) -> str:
    """Garde schéma+host+path, supprime query/fragments (utm…)."""
    try:
        p = urlparse(u or "")
        return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
    except Exception:
        return normalize_url(u)
