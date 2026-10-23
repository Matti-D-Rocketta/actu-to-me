from __future__ import annotations
from typing import Dict, Any
from openai import OpenAI

# Seuil minimum de texte article pour considérer qu'un résumé fiable est possible
MIN_CONTENT_CHARS = 800

SYSTEM_PROMPT = """Tu es un analyste énergie spécialisé hydrogène/énergie.
Tu rédiges des résumés article par article en 5 à 7 phrases, factuels, neutres, en français.
Priorité : qui / quand / où / quoi / chiffres / acteurs / impacts / portée.
Pas de jargon marketing, pas de spéculation.
Sortie TEXTE BRUT uniquement : pas de Markdown, pas de gras, pas d’emoji.
Si un chiffre n’est pas présent dans le texte, ne l’invente pas.
Si une partie est hors périmètre de la section, ignore-la.
"""

def summarize_article(
    model: str,
    api_key: str,
    item: Dict[str, Any],
    section_scope: str = ""
) -> Dict[str, Any]:
    """
    item attendu:
      {'title','link','summary','content','published','source','section'}
    Retourne:
      {
        'title','link','source','published',
        'summary_ai' (ou ""), 'available': bool,
        'fallback_note': "Contenu complet non disponible (source tronquée)" ou message d'erreur,
        'snippet': snippet RSS éventuel
      }
    """
    title = (item.get("title") or "").strip()
    link = (item.get("link") or "").strip()
    source = (item.get("source") or "").strip()
    published = item.get("published") or ""
    content = (item.get("content") or "").strip()
    snippet = (item.get("summary") or "").strip()

    # Pas assez de contenu -> ne pas appeler l'IA (évite résumés faux)
    if len(content) < MIN_CONTENT_CHARS:
        return {
            "title": title,
            "link": link,
            "source": source,
            "published": published,
            "summary_ai": "",
            "available": False,
            "fallback_note": "Contenu complet non disponible (source tronquée)",
            "snippet": snippet[:400],
        }

    # Prépare le prompt avec le contexte de section
    scope_line = f"Contexte de section: {section_scope}\n" if section_scope else ""
    user_prompt = (
        f"{scope_line}"
        f"Titre: {title}\n"
        f"Source: {source}\n"
        f"Texte:\n{content[:12000]}\n"
        "---\n"
        "Consigne: résume l'article en 5 à 7 phrases claires et factuelles, "
        "dans le périmètre de la section ci-dessus. Texte brut."
    )

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            temperature=0.2,
            max_tokens=500,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        summary = (resp.choices[0].message.content or "").strip()
        return {
            "title": title,
            "link": link,
            "source": source,
            "published": published,
            "summary_ai": summary,
            "available": True,
            "fallback_note": "",
            "snippet": "",
        }
    except Exception as e:
        # Fallback propre si l'appel IA échoue (quota, réseau, etc.)
        return {
            "title": title,
            "link": link,
            "source": source,
            "published": published,
            "summary_ai": "",
            "available": False,
            "fallback_note": f"Résumé IA indisponible ({type(e).__name__})",
            "snippet": snippet[:400],
        }
