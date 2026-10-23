from datetime import datetime, timezone

import pytest
import requests

RSS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>{feed_title}</title>
{items}
</channel></rss>"""

ITEM_TEMPLATE = """<item><title>{title}</title><link>{link}</link>
<description>{desc}</description><pubDate>{date}</pubDate></item>"""


def make_rss(entries, feed_title="Test Feed"):
    items = "".join(
        ITEM_TEMPLATE.format(
            title=e["title"], link=e["link"], desc=e.get("desc", "snippet"),
            date=e.get("date", "Thu, 22 Oct 2026 08:00:00 GMT"),
        )
        for e in entries
    )
    return RSS_TEMPLATE.format(feed_title=feed_title, items=items).encode("utf-8")


class FakeResponse:
    def __init__(self, content=b"", status_code=200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


@pytest.fixture
def since_dt():
    return datetime(2026, 10, 20, tzinfo=timezone.utc)
