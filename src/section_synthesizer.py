from __future__ import annotations
from typing import List, Dict, Any
from datetime import datetime, timezone
from openai import OpenAI

# Mots-clés servant au score de pertinence des liens
KEYWORDS = [
    "GW","MW","électrolyse","electrolyzer","PEM","SOEC","pile à combustible","fuel cell",
    "capex","financement","subsidy","policy","réglementation","contrat","offtake",
    "pipeline","corridor","stockage","ammonia","NH3","H2","hydrogène","hydrogen",
    "France","EU","Europe","Canada","USA","Chine","Allemagne","UK"
]

SYSTEM_PROMPT_SECTION_BASE = (
    "Tu es un analyste énergie spécialisé hydrogène/énergie. "
    "Tu écris des synthèses de section en 5 à 8 phrases, claires, rigoureuses, pour un lecteur non spécialiste mais exigeant. "
    "Explique les tendances, enjeux, acteurs/pays, ordres de grandeur et signaux faibles. "
    "Pas de marketing, pas de spéculation. "
    "Sortie TEXTE BRUT uniquement (pas de Markdown, pas d'emoji). "
    "N'invente jamais de chiffres : si l'information n'apparaît pas dans les résumés fournis, ne l'ajoute pas."
)

def _parse_dt(s: str) -> datetime:
    """Parsage tolérant d'une date ISO; fallback = now() pour éviter les plantages."""
    if not s:
        return datetime.now(timezone.utc)
    try:
        # accepte 'Z' et sans TZ
        if s.endswith("Z"):
            s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.now(timezone.utc)

def _score_item(it: Dict[str, Any]) -> float:
    """Score simple = récence + densité + mots-clés."""
    score = 0.0

    # Récence
    dt = _parse_dt(it.get("published", ""))
    days = max(0.1, (datetime.now(timezone.utc) - dt).days + 0.1)
    score += 5.0 / days  # plus récent = meilleur

    # Densité (contenu ou snippet)
    content_len = len((it.get("content") or it.get("summary") or ""))
    score += min(content_len / 2000.0, 3.0)

    # Mots-clés
    hay = f"{it.get('title','')} {(it.get('content') or it.get('summary') or '')}".lower()
    hits = sum(1 for kw in KEYWORDS if kw.lower() in hay)
    score += min(hits * 0.5, 5.0)

    return score

def select_top_links(items: List[Dict[str, Any]], max_links: int = 10) -> List[Dict[str, Any]]:
    """Renvoie entre 1 et max_links liens pertinents selon un score simple."""
    if max_links < 1:
        max_links = 1
    ranked = sorted(items, key=_score_item, reverse=True)
    seen = set()
    out: List[Dict[str, Any]] = []
    for it in ranked:
        key = (it.get("title","").strip(), it.get("link","").strip())
        if key in seen:
            continue
        seen.add(key)
        out.append({"title": (it.get("title","") or "").strip(),
                    "link":  (it.get("link","") or "").strip()})
        if len(out) >= min(max_links, 10):
            break
    # si aucune entrée, on renvoie liste vide (le renderer gère)
    return out

def synthesize_section(
    model: str,
    api_key: str,
    section_title: str,
    article_summaries: List[Dict[str, Any]],
    section_scope: str = ""
) -> str:
    """
    article_summaries : liste de dicts {'title','link','source','summary_ai'} (only available=True).
    Retourne une synthèse texte brut (5–8 phrases) dans le périmètre de la section.
    """
    if not article_summaries:
        return "Aucune actualité suffisante pour établir une synthèse cette période."

    # Prépare un bloc compact avec les résumés d'articles
    bullets: List[str] = []
    for a in article_summaries:
        t = a.get("title", "")
        src = a.get("source", "")
        summ = a.get("summary_ai") or ""
        if not summ:
            continue
        bullets.append(f"- {t} — {src}\n{summ}")
    content = "\n\n".join(bullets)[:12000]

    # Construit le message système en ajoutant le contexte de section
    system_msg = SYSTEM_PROMPT_SECTION_BASE
    if section_scope:
        system_msg += f" Contexte de section : {section_scope}"

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            temperature=0.2,
            max_tokens=600,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user",
                 "content": f"Synthétise la section « {section_title} » en 5 à 8 phrases (texte brut) à partir des résumés suivants :\n\n{content}"}
            ],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return f"Synthèse indisponible pour cette section ({type(e).__name__})."
