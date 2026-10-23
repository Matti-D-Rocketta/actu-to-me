from __future__ import annotations
import requests
from bs4 import BeautifulSoup
from readability import Document
from newspaper import Article

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

def _clean_text(txt: str) -> str:
    if not txt:
        return ""
    return " ".join(txt.split())

def extract_fulltext(url: str, timeout: int = 12) -> str:
    if not url:
        return ""
    # 1) newspaper3k
    try:
        art = Article(url, keep_article_html=False, language="en")
        art.download()
        art.parse()
        txt = _clean_text(getattr(art, "text", "") or "")
        if len(txt) > 400:
            return txt
    except Exception:
        pass
    # 2) readability + BeautifulSoup
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
        if not (200 <= resp.status_code < 300):
            return ""
        doc = Document(resp.text)
        summary_html = doc.summary()
        soup = BeautifulSoup(summary_html, "lxml")
        for tag in soup(["script", "style", "nav", "aside", "footer", "header"]):
            tag.decompose()
        txt = _clean_text(soup.get_text(separator=" "))
        return txt
    except Exception:
        return ""
