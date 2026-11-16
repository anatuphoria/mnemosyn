from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from .design import rich
from .views.about_dialog import app_version

ISSUES_URL = "https://github.com/anatuphoria/mnemosyn/issues/new"
LINK_TEXT = "Report a mistake in this text"
BODY = """**Where**
{where}

**What is wrong**


**What it should say, and a source if you have one**


Mnemosyn {version}, atlas {atlas}. This text is {status}."""


def mistake_url(where: str, atlas, status: str) -> str:
    package = f"{atlas.metadata.get('name', '')} {atlas.metadata.get('version', '')}".strip()
    body = BODY.format(where=where, version=app_version(), atlas=package or "unknown",
                       status="reviewed" if status == "reviewed" else "a draft")
    query = urlencode({"template": "mistake.md", "title": f"Mistake: {where}", "body": body})
    return f"{ISSUES_URL}?{query}"


def mistake_link(where: str, atlas, status: str) -> str:
    url = escape(mistake_url(where, atlas, status), quote=True)
    return rich.secondary(f"<a href='{url}'>{LINK_TEXT}</a>")


def status_html(status: str, review: str) -> str:
    if status == "reviewed":
        return f"{rich.chip('Reviewed', 'success')} {escape(review)}".strip()
    return f"{rich.chip('Draft', 'edited')} · not yet reviewed"
