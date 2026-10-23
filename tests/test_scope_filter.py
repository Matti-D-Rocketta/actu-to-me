from src.scope_filter import filter_by_scope

ITEMS = [
    {"title": "New PEM electrolyzer plant", "summary": "hydrogen project in France"},
    {"title": "Hydrogen stocks rally", "summary": "bourse et spéculation"},
    {"title": "Football results", "summary": "sport"},
    {"title": "Fuel cell bus", "summary": "", "content": "a new H2 bus line"},
]


def test_include_and_exclude():
    out = filter_by_scope(ITEMS, ["hydrogen", "fuel cell"], ["bourse"])
    assert [it["title"] for it in out] == ["New PEM electrolyzer plant", "Fuel cell bus"]


def test_case_insensitive_and_content_fallback():
    out = filter_by_scope(ITEMS, ["H2 BUS"], [])
    assert [it["title"] for it in out] == ["Fuel cell bus"]


def test_no_keywords_keeps_everything():
    assert filter_by_scope(ITEMS, [], []) == ITEMS
