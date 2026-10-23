from src.renderer import render_articles_text, render_html, render_text

SUMMARIES = {"Hydro": "Ligne 1\n**Point clé** important"}
PICKS = {"Hydro": [{"title": f"Article {i}", "link": f"https://ex.com/{i}"} for i in range(5)]}


def test_html_v1_uses_three_picks_and_markdown():
    html = render_html("Brief", "2026-10-23", SUMMARIES, PICKS)
    assert html.startswith("<!doctype html>")
    assert "<h2>Hydro</h2>" in html
    assert "<strong>Point clé</strong>" in html
    assert "Ligne 1<br/>" in html
    assert html.count("<li>") == 3


def test_html_v2_top_links_and_unavailable():
    html = render_html(
        "Brief", "2026-10-23", SUMMARIES, PICKS,
        top_links_by_section={"Hydro": [{"title": "Top", "link": "https://ex.com/top"}]},
        unavailable_by_section={"Hydro": [{"title": "Tronqué", "link": "https://ex.com/t", "snippet": "extrait"}]},
    )
    assert "https://ex.com/top" in html
    assert "https://ex.com/0" not in html  # V2 top links replace V1 picks
    assert "contenu indisponible" in html
    assert "Tronqué</a> — extrait" in html


def test_numbered_list_becomes_ol():
    html = render_html("B", "d", {"S": "Intro\n1. un\n2. deux"}, {})
    assert "<ol><li>un</li><li>deux</li></ol>" in html


def test_text_output():
    txt = render_text("Brief", "2026-10-23", SUMMARIES, PICKS)
    assert txt.splitlines()[0] == "Brief"
    assert "Liens clés:" in txt
    assert "https://ex.com/2" in txt and "https://ex.com/3" not in txt


def test_articles_text_skips_empty_sections():
    txt = render_articles_text("Articles", "d", {
        "Vide": [],
        "Hydro": [{"title": "A", "link": "https://ex.com/a", "source": "S", "summary_ai": "résumé"}],
    })
    assert "Vide" not in txt
    assert "* A — S" in txt and "résumé" in txt
