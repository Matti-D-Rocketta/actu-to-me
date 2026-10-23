from __future__ import annotations
from typing import Dict, List
import re

def _html_head(title: str) -> str:
    # Pas de .format() ici pour ne pas casser les { } du CSS
    return f"""<!doctype html><html lang='fr'><meta charset='utf-8'>
<title>{title}</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;line-height:1.5;margin:24px;color:#111}}
h1{{font-size:22px;margin:0 0 8px}}
h2{{font-size:18px;margin:20px 0 6px}}
small{{color:#666}}
.section{{padding:14px 0;border-top:1px solid #e8e8e8}}
p{{margin:8px 0 12px}}
ul{{margin:0 0 6px 18px}}
a{{color:#0b57d0;text-decoration:none}}
</style>
<body>
"""

def _markdown_to_html(text: str) -> str:
    """Nettoyage léger du markdown courant + retours à la ligne."""
    if not text:
        return ""
    # Remplacements simples markdown -> HTML
    clean = text
    clean = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", clean)   # **gras**
    clean = re.sub(r"\*(.+?)\*", r"<em>\1</em>", clean)               # *italique*
    # Listes numérotées -> <ol>
    lines = [l for l in clean.splitlines()]
    num_lines = [l for l in lines if re.match(r"^\s*\d+\.\s+", l)]
    if len(num_lines) >= 2:
        # On essaie de garder un éventuel paragraphe d'intro au-dessus
        intro = []
        items = []
        for l in lines:
            m = re.match(r"^\s*\d+\.\s+(.*)$", l)
            if m:
                items.append(m.group(1).strip())
            else:
                if l.strip():
                    intro.append(l)
        html = ""
        if intro:
            html += "<p>" + "<br/>".join(intro) + "</p>"
        html += "<ol>" + "".join(f"<li>{it}</li>" for it in items) + "</ol>"
        return html
    # Par défaut, on respecte juste les retours à la ligne
    return clean.replace("\n", "<br/>")

def render_html(
    title: str,
    date_str: str,
    summaries: Dict[str,str],
    picks: Dict[str,List[dict]],
    # NEW: liens clés pertinents (1..10) si fournis par V2
    top_links_by_section: Dict[str, List[dict]] | None = None,
    # NEW: articles non traités (contenu indisponible)
    unavailable_by_section: Dict[str, List[dict]] | None = None
) -> str:
    parts = [_html_head(title)]
    parts.append(f"<h1>{title}</h1><small>{date_str}</small>")
    for key, text in summaries.items():
        parts.append("<div class='section'>")
        parts.append(f"<h2>{key}</h2>")
        parts.append(f"<p>{_markdown_to_html(text)}</p>")

        # Liens clés (V2 si fournis, sinon V1 => fallback à picks[:3])
        links = []
        if top_links_by_section and key in top_links_by_section and top_links_by_section[key]:
            links = top_links_by_section[key]
        elif picks.get(key):
            links = [{"title": it["title"], "link": it["link"]} for it in picks[key][:3]]  # V1 fallback

        if links:
            parts.append("<ul>")
            for it in links:
                parts.append(
                    f"<li><a href='{it['link']}' target='_blank' rel='noopener noreferrer'>{it['title']}</a></li>"
                )
            parts.append("</ul>")

        # Bloc "contenu indisponible" (si fourni)
        if unavailable_by_section and key in unavailable_by_section and unavailable_by_section[key]:
            parts.append("<div style='margin-top:8px'>")
            parts.append("<small><strong>Articles non traités (contenu indisponible) :</strong></small>")
            parts.append("<ul>")
            for it in unavailable_by_section[key]:
                title = it.get("title","")
                link = it.get("link","")
                snippet = (it.get("snippet","") or "")[:220]
                parts.append(
                    f"<li><a href='{link}' target='_blank' rel='noopener noreferrer'>{title}</a>"
                    + (f" — {snippet}" if snippet else "")
                    + "</li>"
                )
            parts.append("</ul></div>")

        parts.append("</div>")
    parts.append("</body></html>")
    return "".join(parts)


def render_text(title: str, date_str: str, summaries: Dict[str,str], picks: Dict[str,List[dict]]) -> str:
    lines = [f"{title}\n{date_str}\n" + ("="*60)]
    for key, text in summaries.items():
        lines.append(f"\n{key}\n--\n{text}\n")
        if picks.get(key):
            lines.append("Liens clés:")
            for it in picks[key][:3]:
                lines.append(f"- {it['title']}\n  {it['link']}")
    return "\n".join(lines)


def render_articles_html(title: str, date_str: str, per_section: Dict[str, List[dict]]) -> str:
    parts = [_html_head(title)]
    parts.append(f"<h1>{title}</h1><small>{date_str}</small>")
    for key, items in per_section.items():
        if not items:
            continue
        parts.append("<div class='section'>")
        parts.append(f"<h2>{key}</h2>")
        parts.append("<ul>")
        for a in items:
            t = a.get("title","")
            link = a.get("link","")
            src = a.get("source","")
            summ = (a.get("summary_ai") or a.get("snippet") or "").replace("\n","<br/>")
            parts.append(
                f"<li><strong>{t}</strong> — {src}<br/>"
                f"<a href='{link}' target='_blank' rel='noopener noreferrer'>{link}</a><br/>{summ}</li>"
            )
        parts.append("</ul></div>")
    parts.append("</body></html>")
    return "".join(parts)


def render_articles_text(title: str, date_str: str, per_section: Dict[str, List[dict]]) -> str:
    lines = [f"{title}\n{date_str}\n" + ("="*60)]
    for key, items in per_section.items():
        if not items:
            continue
        lines.append(f"\n{key}\n" + "-"*len(key))
        for a in items:
            t = a.get("title","")
            link = a.get("link","")
            src = a.get("source","")
            summ = a.get("summary_ai") or a.get("snippet") or ""
            lines.append(f"* {t} — {src}\n  {link}\n  {summ}\n")
    return "\n".join(lines)
