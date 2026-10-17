"""HTML frame for account mails in the colours of the app's PrimeNG theme (Aura, zinc).
Table layout with inline styles, since mail clients ignore most of modern CSS."""

from html import escape

_FONT = "system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
_PAGE = "#f4f4f5"
_CARD = "#ffffff"
_BORDER = "#e4e4e7"
_TEXT = "#3f3f46"
_HEADING = "#09090b"
_MUTED = "#71717a"
_PRIMARY = "#09090b"


def render(
    *, brand: str, title: str, greeting: str, intro: str, action: str, link: str, outro: str
) -> str:
    """A full HTML document: heading, text, one call-to-action button and a fallback link."""
    brand, title, greeting, intro, action, outro = map(
        escape, (brand, title, greeting, intro, action, outro)
    )
    href = escape(link)
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<title>{title}</title>
</head>
<body style="margin:0;padding:0;background-color:{_PAGE};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{intro}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:{_PAGE};">
<tr><td align="center" style="padding:32px 16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:480px;">
<tr><td style="padding:0 4px 16px;font-family:{_FONT};font-size:15px;font-weight:600;color:{_HEADING};">{brand}</td></tr>
<tr><td style="background-color:{_CARD};border:1px solid {_BORDER};border-radius:12px;padding:32px 28px;font-family:{_FONT};">
<h1 style="margin:0 0 20px;font-size:22px;line-height:1.3;font-weight:600;color:{_HEADING};">{title}</h1>
<p style="margin:0 0 12px;font-size:15px;line-height:1.6;color:{_TEXT};">{greeting}</p>
<p style="margin:0 0 24px;font-size:15px;line-height:1.6;color:{_TEXT};">{intro}</p>
<table role="presentation" cellpadding="0" cellspacing="0" border="0">
<tr><td style="border-radius:6px;background-color:{_PRIMARY};">
<a href="{href}" target="_blank" style="display:inline-block;padding:11px 20px;font-family:{_FONT};font-size:15px;font-weight:500;line-height:1;color:#ffffff;text-decoration:none;border-radius:6px;">{action}</a>
</td></tr>
</table>
<p style="margin:24px 0 0;font-size:14px;line-height:1.6;color:{_MUTED};">{outro}</p>
<hr style="margin:24px 0;border:0;border-top:1px solid {_BORDER};">
<p style="margin:0 0 6px;font-size:13px;line-height:1.5;color:{_MUTED};">Falls der Button nicht funktioniert, öffne diesen Link im Browser:</p>
<p style="margin:0;font-size:13px;line-height:1.5;word-break:break-all;"><a href="{href}" target="_blank" style="color:{_TEXT};">{href}</a></p>
</td></tr>
<tr><td style="padding:16px 4px 0;font-family:{_FONT};font-size:12px;line-height:1.5;color:{_MUTED};">Diese Mail wurde automatisch verschickt. Antworten darauf kommen nicht an.</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
"""
