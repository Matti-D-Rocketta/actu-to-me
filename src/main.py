from __future__ import annotations
import argparse, os, sys, yaml
from datetime import datetime
from dotenv import load_dotenv

from .utils import now_utc, parse_since
from .rss_fetcher import fetch_section
from .summarizer import summarize_section  # V1 (synthèse directe)
from .renderer import render_html, render_text
from .article_summarizer import summarize_article   # V2 étape 1 (article->résumé)
from .section_synthesizer import synthesize_section, select_top_links  # V2 étape 2 + liens pertinents
from .scope_filter import filter_by_scope, gpt_filter_titles  # filtrage scope + (option) GPT titres


def load_sources(yaml_path: str):
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def main():
    load_dotenv()  # .env
    parser = argparse.ArgumentParser(description="Generate a daily brief from RSS with GPT summary.")
    parser.add_argument('--since', default='24h', help='Fenêtre: ex 24h, 48h, 7d')
    parser.add_argument('--sections', nargs='*', help='Ex: hydro energy world (défaut: toutes)')
    parser.add_argument('--out', default='out/brief.html', help='Fichier de sortie HTML si --html')
    parser.add_argument('--text-out', default='out/brief.txt', help='Fichier de sortie texte brut')
    parser.add_argument('--model', default=os.getenv('MODEL_NAME', 'gpt-5'), help='Nom du modèle OpenAI (défaut .env)')
    parser.add_argument('--html', action='store_true', help='Générer aussi un HTML')
    parser.add_argument('--include-overview', action='store_true', help='Ajouter un paragraphe de vue d’ensemble en tête')
    parser.add_argument('--max-per-section', type=int, default=12, help='Clamp d’items passés à l’IA par section')
    parser.add_argument('--max-chars', type=int, default=int(os.getenv('MAX_CHARS_PER_SECTION', '12000')))

    # V2 – deux passes GPT
    parser.add_argument('--v2', action='store_true', help='Active la V2 : 2 passes GPT (article->section)')
    parser.add_argument('--export-articles', action='store_true', help='Exporte les résumés article par article')
    parser.add_argument('--links-per-section-max', type=int, default=10, help='Nb max de liens clés affichés (1..10)')
    parser.add_argument('--gpt-filter-titles', action='store_true', help='Filtre de pertinence par titres avec GPT (optionnel)')

    args = parser.parse_args()

    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    if not OPENAI_API_KEY:
        print("Erreur: OPENAI_API_KEY manquant (voir .env)", file=sys.stderr)
        sys.exit(1)

    cfg = load_sources('config/sources.yaml')
    all_sections = cfg.get('sections', {})
    chosen = args.sections or list(all_sections.keys())

    since_dt = now_utc() - parse_since(args.since)

    summaries: dict[str, str] = {}
    picks: dict[str, list[dict]] = {}                 # V1 fallback: liste brute d'items par section
    top_links_by_section: dict[str, list[dict]] = {}  # V2: liens clés (1..10) par section
    unavailable_by_section: dict[str, list[dict]] = {}# V2: articles non traités (contenu indisponible)
    articles_export_map: dict[str, list[dict]] = {}   # V2: pour le rendu "articles détaillés"

    for key in chosen:
        meta = all_sections.get(key)
        if not meta:
            continue

        section_title = meta.get('title', key)
        section_scope = meta.get('scope', '')                # contexte de section (optionnel)
        inc = meta.get('include_keywords', []) or []
        exc = meta.get('exclude_keywords', []) or []
        feeds = meta.get('feeds', [])

        # Fetch RSS (triés du plus récent au plus ancien)
        items_raw = fetch_section(section_title, feeds, since_dt)

        # Étape 0 — filtre heuristique gratuit par scope (titre + snippet)
        items_scoped = filter_by_scope(items_raw, inc, exc) if (inc or exc) else items_raw

        # Étape 0bis — filtre GPT sur titres (optionnel, seulement en V2 pour limiter le coût)
        if args.v2 and args.gpt_filter_titles and items_scoped:
            items_scoped = gpt_filter_titles(OPENAI_API_KEY, args.model, section_title, section_scope, items_scoped)

        # Ce que l'on garde comme "picks" pour le renderer (V1 fallback si besoin)
        picks[section_title] = items_scoped

        # =========================
        # V1 (synthèse directe)
        # =========================
        if not args.v2:
            items_for_ai = items_scoped[:max(args.max_per_section, 1)]
            if not items_for_ai:
                summaries[section_title] = "Aucune actualité dans la fenêtre sélectionnée."
                continue
            summary = summarize_section(
                args.model, OPENAI_API_KEY, section_title, items_for_ai, max_chars=args.max_chars
            )
            summaries[section_title] = summary
            continue

        # =========================
        # V2 (deux passes)
        # Étape 1 : résumer chaque article si contenu complet disponible
        # =========================
        article_summaries: list[dict] = []
        unavailable_list: list[dict] = []
        for it in items_scoped[:max(args.max_per_section, 1)]:
            res = summarize_article(args.model, OPENAI_API_KEY, it, section_scope=section_scope)
            if res.get("available"):
                article_summaries.append(res)  # article OK -> résumé IA
            else:
                # contenu incomplet/non dispo -> listé en bas de section
                unavailable_list.append({
                    "title": res.get("title", ""),
                    "link": res.get("link", ""),
                    "snippet": res.get("snippet", "")  # mini résumé RSS si dispo
                })

        unavailable_by_section[section_title] = unavailable_list
        # pour l'export "articles détaillés" (les non traités auront summary_ai vide)
        articles_export_map[section_title] = article_summaries + unavailable_list

        # =========================
        # V2 Étape 2 : synthèse de section (sur la base des résumés d'articles disponibles)
        # =========================
        available_for_synthesis = [a for a in article_summaries if a.get("summary_ai")]
        if not available_for_synthesis:
            summaries[section_title] = "Aucune actualité suffisante pour établir une synthèse cette période."
        else:
            synth_text = synthesize_section(
                args.model, OPENAI_API_KEY, section_title, available_for_synthesis, section_scope=section_scope
            )
            summaries[section_title] = synth_text

        # Liens clés pertinents (1..10) – calculés sur les items SCOPÉS (fraîcheur/densité/mots-clés)
        top_links_by_section[section_title] = select_top_links(items_scoped, max_links=args.links_per_section_max)

    # En-tête
    title = "Brief quotidien – Hydrogène & Énergie"
    window_str = f" • Couverture : {args.since}"
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M") + window_str

    # Sortie texte (format .txt inchangé)
    out_text_dir = os.path.dirname(args.text_out) or "."
    os.makedirs(out_text_dir, exist_ok=True)
    with open(args.text_out, 'w', encoding='utf-8') as f:
        f.write(render_text(title, date_str, summaries, picks))

    # Sortie HTML
    if args.html:
        out_html_dir = os.path.dirname(args.out) or "."
        os.makedirs(out_html_dir, exist_ok=True)
        if args.v2:
            html = render_html(
                title, date_str, summaries, picks,
                top_links_by_section=top_links_by_section,
                unavailable_by_section=unavailable_by_section
            )
        else:
            html = render_html(title, date_str, summaries, picks)
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write(html)

    # Export optionnel "articles détaillés" (V2 uniquement)
    if args.v2 and args.export_articles:
        from .renderer import render_articles_html, render_articles_text  # import tardif
        base_html = args.out.rsplit(".", 1)[0]
        base_txt = args.text_out.rsplit(".", 1)[0]
        art_html_path = f"{base_html}_articles.html"
        art_txt_path = f"{base_txt}_articles.txt"

        with open(art_html_path, 'w', encoding='utf-8') as f:
            f.write(render_articles_html("Articles détaillés", date_str, articles_export_map))
        with open(art_txt_path, 'w', encoding='utf-8') as f:
            f.write(render_articles_text("Articles détaillés", date_str, articles_export_map))

    print(f"✅ Brief généré → {args.text_out}" + (f" et {args.out}" if args.html else ""))


if __name__ == '__main__':
    main()
