"""Cache disque des résumés d'articles (V2 passe 1), pour ne pas repayer l'API.

Clé = hash(modèle + lien + contenu + contexte de section + version du prompt) :
si l'un de ces éléments change, l'article est résumé à nouveau.
Seuls les résumés réussis sont mis en cache ; les entrées expirent après `ttl_days`.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import hashlib
import json
import logging
import os

log = logging.getLogger(__name__)

# À incrémenter quand le prompt de summarize_article change, pour invalider le cache.
PROMPT_VERSION = "1"
DEFAULT_PATH = ".cache/article_summaries.json"


def cache_key(model: str, item: Dict[str, Any], section_scope: str = "") -> str:
    parts = [
        PROMPT_VERSION,
        model or "",
        (item.get("link") or "").strip(),
        (item.get("content") or "").strip(),
        section_scope or "",
    ]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


class SummaryCache:
    def __init__(self, path: str | os.PathLike = DEFAULT_PATH, ttl_days: int = 30):
        self.path = Path(path)
        self.ttl = timedelta(days=ttl_days)
        self.hits = 0
        self.misses = 0
        self._data: Dict[str, Dict[str, Any]] = {}
        self._dirty = False
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("Cache illisible (%s), ignoré : %s", exc, self.path)
            return
        cutoff = datetime.now(timezone.utc) - self.ttl
        for k, entry in raw.items():
            try:
                if datetime.fromisoformat(entry["cached_at"]) >= cutoff:
                    self._data[k] = entry
                else:
                    self._dirty = True  # entrée expirée -> purgée au prochain save
            except (KeyError, TypeError, ValueError):
                self._dirty = True

    def __len__(self) -> int:
        return len(self._data)

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        entry = self._data.get(key)
        if entry is None:
            self.misses += 1
            return None
        self.hits += 1
        return dict(entry["result"])

    def put(self, key: str, result: Dict[str, Any]) -> None:
        if not result.get("available"):
            return  # on ne fige pas un échec (quota, réseau…)
        self._data[key] = {
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "result": result,
        }
        self._dirty = True

    def save(self) -> None:
        if not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)  # écriture atomique
        self._dirty = False


def summarize_with_cache(cache: Optional[SummaryCache], summarize_fn, model: str, api_key: str,
                         item: Dict[str, Any], section_scope: str = "") -> Dict[str, Any]:
    """Appelle summarize_fn(model, api_key, item, section_scope=...) sauf si le résultat est en cache."""
    if cache is None:
        return summarize_fn(model, api_key, item, section_scope=section_scope)
    key = cache_key(model, item, section_scope)
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = summarize_fn(model, api_key, item, section_scope=section_scope)
    cache.put(key, result)
    return result
