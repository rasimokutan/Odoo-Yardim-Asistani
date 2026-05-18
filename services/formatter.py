import re


def markdown_to_html(text: str) -> str:
    """Convert LLM markdown output to Odoo-safe HTML.

    Handles: bold, italic, inline-code, ordered lists, unordered lists,
    blank-line paragraph breaks.  All user-supplied characters are HTML-escaped
    before our own tags are inserted, so XSS is not possible.
    """
    if not text:
        return ""

    lines = text.strip().split("\n")
    result = []
    in_ul = False
    in_ol = False

    for line in lines:
        stripped = line.strip()
        ol_match = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        ul_match = re.match(r"^[-*]\s+(.+)$", stripped)

        if ol_match:
            if not in_ol:
                if in_ul:
                    result.append("</ul>")
                    in_ul = False
                result.append("<ol>")
                in_ol = True
            result.append(f"<li>{_inline(ol_match.group(2))}</li>")

        elif ul_match:
            if not in_ul:
                if in_ol:
                    result.append("</ol>")
                    in_ol = False
                result.append("<ul>")
                in_ul = True
            result.append(f"<li>{_inline(ul_match.group(1))}</li>")

        else:
            if in_ol:
                result.append("</ol>")
                in_ol = False
            if in_ul:
                result.append("</ul>")
                in_ul = False

            if not stripped:
                # Blank line becomes a visual spacer between paragraphs
                if result and result[-1] != "<br>":
                    result.append("<br>")
            else:
                result.append(f"<p>{_inline(stripped)}</p>")

    if in_ol:
        result.append("</ol>")
    if in_ul:
        result.append("</ul>")

    return "\n".join(result)


def _inline(text: str) -> str:
    """Apply inline formatting: bold, italic, inline-code.  HTML-escapes first."""
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Bold **text** or __text__
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
    safe = re.sub(r"__(.+?)__", r"<strong>\1</strong>", safe)
    # Italic *text* or _text_ (single star/underscore, not nested)
    safe = re.sub(r"\*([^*]+?)\*", r"<em>\1</em>", safe)
    safe = re.sub(r"_([^_]+?)_", r"<em>\1</em>", safe)
    # Inline code `code`
    safe = re.sub(r"`([^`]+?)`", r"<code>\1</code>", safe)
    return safe
