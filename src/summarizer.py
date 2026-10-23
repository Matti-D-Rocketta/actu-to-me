from __future__ import annotations
from typing import List, Dict
from openai import OpenAI

SYSTEM_PROMPT = """Tu es un analyste énergie spécialisé hydrogène.
Tu écris des résumés ultra concis, factuels et neutres en français, lisibles en 30–45 secondes.
Priorité aux faits vérifiables (investissements, projets, politiques publiques, percées techno), dates, ordres de grandeur, acteurs.
Évite la langue promo. 3–6 phrases maximum par section.
**Sortie strictement en texte brut : pas de Markdown, pas de gras, pas d’italiques, pas d’emojis.**
"""

def format_context_for_section(section_title: str, items: List[Dict], max_chars: int) -> str:
    lines = []
    for it in items:
        body = (it.get('content') or it.get('summary') or '').strip()
        if len(body) > 1200:
            body = body[:1200] + ' [...]'
        line = f"- {it['title']}\n{body}\nSource: {it.get('source','')}\nLien: {it['link']}"
        lines.append(line.strip())
    ctx = "\n\n".join(lines)
    if len(ctx) > max_chars:
        ctx = ctx[:max_chars] + "\n[...]"
    return f"Section: {section_title}\n\nArticles:\n{ctx}"


def summarize_section(model: str, api_key: str, section_title: str, items: List[Dict], max_chars: int = 12000) -> str:
    content = format_context_for_section(section_title, items, max_chars)
    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            temperature=0.3,
            max_tokens=300,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Résume en 3–6 phrases claires et factuelles.\n\n{content}"}
            ]
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        # Fallback sans IA : 3 titres clés + liens (pour ne pas bloquer ta routine)
        top = items[:3]
        if not top:
            return "Aucune actualité disponible."
        bullets = [f"• {it['title']} — {it.get('source','')}\n  {it['link']}" for it in top]
        return "[Fallback sans IA – quota indisponible]\n" + "\n".join(bullets)

