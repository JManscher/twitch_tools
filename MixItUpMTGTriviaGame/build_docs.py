"""Render README.md to a self-contained, channel-themed README.html.

Usage:
    pip install -r requirements-docs.txt
    py build_docs.py

Produces README.html next to this script: one standalone file with embedded
CSS (no external assets beyond the Google Fonts link), styled to match the
trivia overlay's cream / sage / coral theme. Open it in any browser.
"""

import os
import sys

try:
    import markdown
except ImportError:
    print(
        "The 'markdown' package is required. Install it with:\n"
        "    pip install -r requirements-docs.txt\n"
        "(or: pip install markdown)",
        file=sys.stderr,
    )
    sys.exit(1)

_HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(_HERE, "README.md")
OUTPUT = os.path.join(_HERE, "README.html")
TITLE = "Mix It Up MTG Trivia Game"

# Kawaii palette, matching static/style.css, tuned for long-form reading.
STYLE = """
:root {
  --cream: #FBF1DA;
  --cream-deep: #F5E6C4;
  --paper: #FFFCF3;
  --sage: #7DA85E;
  --sage-deep: #5F8848;
  --sage-soft: #C7DEB4;
  --coral: #E76F8B;
  --coral-soft: #FFC2CC;
  --ink: #4A3A2F;
  --ink-soft: #7A6856;
  --code-bg: #2E2A33;
  --code-ink: #F3ECD8;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  padding: 48px 20px 96px;
  background-color: var(--cream);
  background-image:
    radial-gradient(circle at 12% 6%, rgba(255, 194, 204, 0.30), transparent 30%),
    radial-gradient(circle at 88% 96%, rgba(199, 222, 180, 0.40), transparent 34%);
  background-attachment: fixed;
  font-family: "Quicksand", "Segoe UI", system-ui, sans-serif;
  color: var(--ink);
  line-height: 1.65;
  font-size: 17px;
}
.page {
  max-width: 880px;
  margin: 0 auto;
  background: var(--paper);
  border: 3px solid var(--sage-soft);
  border-radius: 26px;
  box-shadow: 0 12px 48px rgba(180, 140, 90, 0.20);
  padding: 48px 56px 56px;
}
h1, h2, h3, h4 {
  font-family: "Fredoka", "Quicksand", sans-serif;
  color: var(--sage-deep);
  line-height: 1.2;
  margin-top: 1.8em;
  margin-bottom: 0.5em;
}
h1 {
  font-size: 2.1rem;
  margin-top: 0;
  color: var(--ink);
  border-bottom: 3px solid var(--coral-soft);
  padding-bottom: 0.3em;
}
h2 {
  font-size: 1.5rem;
  border-bottom: 2px dashed var(--sage-soft);
  padding-bottom: 0.25em;
}
h3 { font-size: 1.2rem; color: var(--coral); }
h4 { font-size: 1.05rem; }
p { margin: 0.7em 0; }
a { color: var(--coral); text-decoration: none; font-weight: 600; }
a:hover { text-decoration: underline; }
strong { color: var(--ink); }
ul, ol { padding-left: 1.5em; }
li { margin: 0.3em 0; }
hr { border: none; border-top: 2px dashed var(--sage-soft); margin: 2em 0; }
blockquote {
  margin: 1.2em 0;
  padding: 0.6em 1.1em;
  background: rgba(199, 222, 180, 0.30);
  border-left: 5px solid var(--sage);
  border-radius: 10px;
  color: var(--ink);
}
blockquote p { margin: 0.4em 0; }
code {
  font-family: "Cascadia Code", "Consolas", "SFMono-Regular", monospace;
  font-size: 0.9em;
  background: var(--cream-deep);
  color: #9C4A5E;
  padding: 0.12em 0.4em;
  border-radius: 6px;
  overflow-wrap: anywhere;
}
pre {
  background: var(--code-bg);
  color: var(--code-ink);
  padding: 16px 20px;
  border-radius: 14px;
  overflow-x: auto;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
  line-height: 1.5;
}
pre code {
  background: none;
  color: inherit;
  padding: 0;
  font-size: 0.88em;
}
table {
  border-collapse: collapse;
  width: 100%;
  margin: 1.2em 0;
  font-size: 0.95em;
  background: var(--paper);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 3px 14px rgba(180, 140, 90, 0.14);
}
th, td {
  text-align: left;
  padding: 10px 14px;
  border-bottom: 1px solid var(--sage-soft);
  vertical-align: top;
  overflow-wrap: anywhere;
}
th {
  background: var(--sage);
  color: #fff;
  font-family: "Fredoka", "Quicksand", sans-serif;
  font-weight: 600;
  letter-spacing: 0.02em;
}
tr:nth-child(even) td { background: rgba(199, 222, 180, 0.16); }
tr:last-child td { border-bottom: none; }
.doc-footer {
  margin-top: 3em;
  padding-top: 1.2em;
  border-top: 2px dashed var(--sage-soft);
  font-size: 0.85em;
  color: var(--ink-soft);
  text-align: center;
}
"""

HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Quicksand:wght@500;600;700&family=Fredoka:wght@600;700&display=swap" rel="stylesheet">
  <style>{style}</style>
</head>
<body>
  <main class="page">
{body}
    <div class="doc-footer">Generated from README.md &middot; Mix It Up MTG Trivia Game</div>
  </main>
</body>
</html>
"""


def build() -> str:
    with open(SOURCE, "r", encoding="utf-8") as f:
        text = f.read()

    md = markdown.Markdown(
        extensions=["extra", "sane_lists", "toc"],
        output_format="html5",
    )
    body = md.convert(text)

    html = HTML_TEMPLATE.format(title=TITLE, style=STYLE, body=body)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    return OUTPUT


if __name__ == "__main__":
    out = build()
    print(f"Wrote {out}")
