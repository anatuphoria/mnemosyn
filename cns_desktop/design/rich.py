from __future__ import annotations

from cns_desktop.design.tokens import COLOURS, TYPE


def _font(role: str) -> str:
    size, _line, weight = TYPE[role]
    return f"font-size: {size}px; font-weight: {weight}"


def document_css() -> str:
    c = COLOURS
    return "\n".join((
        f"body {{ color: {c['text']}; {_font('body')}; }}",
        f"h2 {{ {_font('title')}; color: {c['text']}; margin-top: 4px; margin-bottom: 4px; }}",
        f"h3 {{ {_font('heading')}; color: {c['text']}; margin-top: 12px; margin-bottom: 4px; }}",
        f"h4 {{ {_font('data')}; color: {c['text2']}; text-transform: uppercase; "
        "margin-top: 16px; margin-bottom: 4px; }",
        f"p {{ color: {c['text']}; margin-top: 0px; margin-bottom: 8px; }}",
        f"li {{ color: {c['text2']}; {_font('secondary')}; margin-bottom: 4px; }}",
        f"a {{ color: {c['accent_text']}; text-decoration: none; }}",
    ))


def heading(text: str) -> str:
    return f"<h4>{text}</h4>"


def secondary(html: str) -> str:
    return f"<p style='color: {COLOURS['text2']}; {_font('secondary')}'>{html}</p>"


def chip(text: str, role: str) -> str:
    return f"<span style='color: {COLOURS[role]}; {_font('data')}'>{text}</span>"


def card(html: str) -> str:
    return (f"<table width='100%' cellpadding='12' cellspacing='0' bgcolor='{COLOURS['s2']}'>"
            f"<tr><td style='color: {COLOURS['text2']}; {_font('secondary')}'>{html}</td></tr>"
            "</table>")
