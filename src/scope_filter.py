from __future__ import annotations
from typing import List, Dict
import re

def _normalize(s: str) -> str:
    return (s or "").lower()

def _contains_any(text: str, keywords: List[str]) -> bool:
    t = _normalize(text)
    return any(k.lower() in t for k in (keywords or []))

def filter_by_scope(items: List[Dict], include_keywords: List[str], exclude_keywords: List[str]) -> List[Dict]:
    """Garde les items dont (title+summary) matchent include_keywords et n'ont pas d'exclude_keywords."""
    out = []
    for it in items:
        title = it.get("title","")
        summ  = it.get("summary","") or it.get("content","")
        blob = f"{title} {summ}"
        if exclude_keywords and _contains_any(blob, exclude_keywords):
            continue
        if include_keywords and not _contains_any(blob, include_keywords):
            continue
        out.append(it)
    return out



"""Filtrage premium falcutative (payante en token openAI mais peu chère)"""
from openai import OpenAI

def gpt_filter_titles(api_key: str, model: str, section_title: str, scope: str, items: List[Dict]) -> List[Dict]:
    if not items:
        return []
    client = OpenAI(api_key=api_key)
    titles = [it.get("title","") for it in items]
    prompt = (
        f"Section: {section_title}\n"
        f"Scope: {scope}\n"
        "Pour chaque titre ci-dessous, réponds OUI si pertinent pour cette section, sinon NON. "
        "Réponds une liste de OUI/NON, une par ligne, dans le même ordre, sans autre texte."
        "\nTitres:\n- " + "\n- ".join(titles)
    )
    resp = client.chat.completions.create(
        model=model, temperature=0, max_tokens=100,
        messages=[{"role":"system","content":"Tu es un classifieur binaire très strict."},
                  {"role":"user","content":prompt}]
    )
    lines = [l.strip().upper() for l in resp.choices[0].message.content.strip().splitlines() if l.strip()]
    keep = []
    for it, ans in zip(items, lines):
        if ans.startswith("OUI"): keep.append(it)
    return keep