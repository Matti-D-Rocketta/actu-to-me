"""End-to-end run of the CLI with network and OpenAI mocked."""
import sys

import pytest

from src import main as main_mod

LONG = "contenu " * 200  # above MIN_CONTENT_CHARS


def _fake_fetch(section_title, feeds, since_dt, errors=None):
    if errors is not None:
        errors.append({"feed": "https://dead.example/feed", "error": "ConnectionError: down"})
    return [
        {"title": "Electrolyzer deal", "link": "https://ex.com/a", "summary": "hydrogen", "content": LONG,
         "published": "2026-10-22T08:00:00+00:00", "source": "Src", "section": section_title},
        {"title": "Short news", "link": "https://ex.com/b", "summary": "hydrogen", "content": "trop court",
         "published": "2026-10-22T07:00:00+00:00", "source": "Src", "section": section_title},
    ]


@pytest.fixture
def run_cli(monkeypatch, tmp_path):
    calls = {"article": 0}

    def fake_summarize(model, api_key, item, section_scope=""):
        # Mirrors summarize_article: short content is rejected without any API call.
        base = {"title": item["title"], "link": item["link"], "source": item["source"], "published": ""}
        if len(item["content"]) < 800:
            return {**base, "summary_ai": "", "available": False, "fallback_note": "tronqué", "snippet": "s"}
        calls["article"] += 1  # counts billed API calls only
        return {**base, "summary_ai": "résumé IA", "available": True, "fallback_note": "", "snippet": ""}

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main_mod, "load_dotenv", lambda: None)
    monkeypatch.setattr(main_mod, "fetch_section", _fake_fetch)
    monkeypatch.setattr(main_mod, "summarize_article", fake_summarize)
    monkeypatch.setattr(main_mod, "synthesize_section", lambda *a, **k: "Synthèse de section.")

    def run(*extra):
        argv = ["src.main", "--v2", "--html", "--sections", "hydro",
                "--out", str(tmp_path / "brief.html"), "--text-out", str(tmp_path / "brief.txt"),
                "--cache-path", str(tmp_path / "cache.json"), *extra]
        monkeypatch.setattr(sys, "argv", argv)
        main_mod.main()

    return run, calls, tmp_path


def test_v2_run_writes_outputs_and_reports_dead_feeds(run_cli, capsys):
    run, calls, tmp = run_cli
    run()
    html = (tmp / "brief.html").read_text(encoding="utf-8")
    assert "Synthèse de section." in html
    assert "Short news" in html  # listed as unavailable (content too short)
    assert calls["article"] == 1  # only the long article is sent to the summarizer
    err = capsys.readouterr().err
    assert "https://dead.example/feed" in err


def test_second_run_uses_cache(run_cli):
    run, calls, _ = run_cli
    run()
    run()
    assert calls["article"] == 1


def test_no_cache_flag(run_cli):
    run, calls, _ = run_cli
    run("--no-cache")
    run("--no-cache")
    assert calls["article"] == 2


def test_missing_api_key_exits_cleanly(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(main_mod, "load_dotenv", lambda: None)
    monkeypatch.setattr(sys, "argv", ["src.main"])
    with pytest.raises(SystemExit) as exc:
        main_mod.main()
    assert exc.value.code == 1
    assert "OPENAI_API_KEY" in capsys.readouterr().err
