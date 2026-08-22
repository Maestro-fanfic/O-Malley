#!/usr/bin/env python3
"""Static site generator for Maestro's Fanfic Archive.

Reads chapter text directly from the original project folders and writes a
plain static HTML site. No dependencies beyond the standard library.
"""
import re
import html
import os

ROOT = "C:/Users/thela/Downloads/Fanfic"
OMWOM = f"{ROOT}/O'Make Way, O'Malley!"
CW = f"{ROOT}/Collected Works"
CW_COMPLETE = f"{CW}/01 Complete"
CW_IN_PROGRESS = f"{CW}/02 In Progress"
OUT = f"{ROOT}/Website/docs"

# Comments are powered by giscus (github.com/giscus/giscus), backed by GitHub
# Discussions on whatever repo ends up hosting this site. Fill these in once
# that repo exists, Discussions is enabled on it, the giscus app is installed,
# and https://giscus.app has generated the repo-id/category-id for you.
# Until GISCUS_REPO is set, comment sections render a "not wired up yet" note
# instead of the live widget, so the build never ships a broken embed.
GISCUS_REPO = "Maestro-fanfic/O-Malley"
GISCUS_REPO_ID = "R_kgDOUA13lA"
GISCUS_CATEGORY = "Announcements"
GISCUS_CATEGORY_ID = "DIC_kwDOUA13lM4DD9qY"

CHAPTER_RE = re.compile(r"^Chapter (\d+):[ \t]*(.*)$", re.MULTILINE)

# Some projects (e.g. Ship of the Line) spell chapter numbers out as words —
# "Chapter One:", "Chapter Twenty-Seven:" — instead of digits.
WORD_CHAPTER_RE = re.compile(r"^Chapter ([A-Za-z][A-Za-z-]*):[ \t]*(.*)$", re.MULTILINE)

_ONES = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}


def word_to_num(s):
    """Parse a spelled-out chapter number ('TwentySeven', 'Twenty-Seven') to an int."""
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", "-", s).lower()
    total = 0
    for part in s.split("-"):
        if part in _ONES:
            total += _ONES[part]
        elif part in _TENS:
            total += _TENS[part]
    return total


_NUMBER_WORD_PATTERN = (
    r"(?:" + "|".join(sorted(_TENS, key=len, reverse=True)).upper()
    + r")(?:-(?:" + "|".join(sorted(_ONES, key=len, reverse=True)).upper() + r"))?"
    + r"|(?:" + "|".join(sorted(_ONES, key=len, reverse=True)).upper() + r")"
)
# The Jumper-universe books (Momentum, Reach, Contact) head each chapter with
# a bare spelled-out number alone on its own line ("ONE", "TWENTY-ONE"), then
# an in-scene quote as the chapter's actual title on the very next line
# ("Cent: It worked once..."). Capture both lines together so the quote line
# becomes the chapter title rather than being left as ordinary body text.
JUMPER_CHAPTER_RE = re.compile(rf"^({_NUMBER_WORD_PATTERN})\n+(.+)$", re.MULTILINE)

# Same books also use that "Name: quote" (or "Name POV: quote" / "Name (POV): quote")
# shape mid-chapter, as an explicit POV-shift marker between speakers/scenes.
JUMPER_POV_RE = re.compile(r'^([A-Z][a-zA-Z\']+)(?:\s*\(?POV\)?)?:\s')

# The curated Collected Works copy of Ship of the Line reformatted its headers
# to "Chapter One" (no colon, title case, no same-line title) with the actual
# title on a later line, same shape as the Jumper books but with a literal
# "Chapter " prefix and case-insensitive number words.
SOTL_CHAPTER_RE = re.compile(rf"^Chapter ({_NUMBER_WORD_PATTERN})\n+(.+)$", re.MULTILINE | re.IGNORECASE)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def split_chapters(text, chapter_re=CHAPTER_RE, parse_num=int):
    """Return (preamble, [(num, title, body), ...]) split on chapter-heading lines."""
    matches = list(chapter_re.finditer(text))
    if not matches:
        return text.strip(), []
    preamble = text[: matches[0].start()].strip()
    chapters = []
    for i, m in enumerate(matches):
        num = parse_num(m.group(1))
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        chapters.append((num, title, body))
    return preamble, chapters


def strip_ai_disclosure(text):
    """Remove the embedded Creative Process & AI Disclosure block from a story's
    own front matter — the site already surfaces that, site-wide, on the
    'Please Read This First' page, so repeating it per-story is redundant."""
    marker = "Creative Process & AI Disclosure"
    idx = text.find(marker)
    if idx == -1:
        return text
    m = re.search(r"^-{3,}\s*$", text[idx:], re.MULTILINE)
    if not m:
        return text[:idx].strip()
    end = idx + m.end()
    return (text[:idx].rstrip() + "\n\n" + text[end:].lstrip()).strip()


DEFAULT_POV_RE = re.compile(r'^"([^"]+)"\s*\(POV\):')


def body_to_html(body, pov_re=DEFAULT_POV_RE):
    """Convert plain-text chapter body into HTML paragraphs."""
    body = body.strip()
    # strip a trailing lone '~~~' separator some combined drafts use before the next chapter
    body = re.sub(r"\n?~~~\s*$", "", body).strip()
    paras = re.split(r"\n\s*\n", body)
    out = []
    for para in paras:
        para = para.strip()
        if not para:
            continue
        if re.fullmatch(r"\*\s*\*\s*\*", para) or re.fullmatch(r"-{3,}", para) or re.fullmatch(r"⁂\s*⁂\s*⁂", para):
            out.append('<p class="scenebreak">&#10035;</p>')
            continue
        esc = html.escape(para, quote=False)
        esc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc)
        esc = re.sub(r"\*(.+?)\*", r"<em>\1</em>", esc)
        esc = esc.replace("\n", "<br>\n")
        pov = pov_re.match(para)
        if pov:
            out.append(f'<p class="pov-header">{esc}</p>')
        else:
            out.append(f"<p>{esc}</p>")
    return "\n".join(out)


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


SITE_JS = """
(function () {
  var KEY = 'fanficFontScale';
  var MIN = 0.8, MAX = 1.7, STEP = 0.1;
  var saved = parseFloat(localStorage.getItem(KEY));
  var scale = isNaN(saved) ? 1 : saved;

  function apply() {
    document.documentElement.style.setProperty('--text-scale', scale);
  }
  apply();

  document.addEventListener('DOMContentLoaded', function () {
    var dec = document.getElementById('font-dec');
    var inc = document.getElementById('font-inc');
    if (dec) {
      dec.addEventListener('click', function () {
        scale = Math.max(MIN, Math.round((scale - STEP) * 100) / 100);
        apply();
        localStorage.setItem(KEY, scale);
      });
    }
    if (inc) {
      inc.addEventListener('click', function () {
        scale = Math.min(MAX, Math.round((scale + STEP) * 100) / 100);
        apply();
        localStorage.setItem(KEY, scale);
      });
    }

    var tocToggle = document.getElementById('toc-toggle');
    var tocPanel = document.getElementById('toc-panel');
    var tocClose = document.getElementById('toc-close');
    var tocBackdrop = document.getElementById('toc-backdrop');
    function openToc() {
      if (tocPanel) tocPanel.classList.add('open');
      if (tocBackdrop) tocBackdrop.classList.add('open');
    }
    function closeToc() {
      if (tocPanel) tocPanel.classList.remove('open');
      if (tocBackdrop) tocBackdrop.classList.remove('open');
    }
    if (tocToggle) tocToggle.addEventListener('click', openToc);
    if (tocClose) tocClose.addEventListener('click', closeToc);
    if (tocBackdrop) tocBackdrop.addEventListener('click', closeToc);
  });
})();
"""

CSS = """
:root {
  --bg: #faf7f2; --fg: #241f1a; --muted: #6b6055; --accent: #8a3b2f;
  --card: #ffffff; --border: #e4dccf; --link: #8a3b2f;
  --text-scale: 1;
}
@media (prefers-color-scheme: dark) {
  :root { --bg:#181513; --fg:#eee7dc; --muted:#a89a8a; --accent:#e4a186;
    --card:#221d19; --border:#382f28; --link:#e4a186; }
}
* { box-sizing: border-box; }
html { background: var(--bg); }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font-family: Georgia, 'Iowan Old Style', 'Palatino Linotype', serif;
  line-height: 1.65;
}
.chrome {
  font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif;
}
a { color: var(--link); }
.wrap { max-width: 1200px; margin: 0 auto; padding: 1.5rem 1.25rem 4rem; }
header.site-header {
  border-bottom: 1px solid var(--border); padding: 1rem 1.25rem;
}
header.site-header .wrap { max-width: 1200px; padding: 0; display:flex; align-items:baseline; justify-content:space-between; flex-wrap: wrap; gap: .5rem;}
header.site-header a.brand { font-family: Georgia, serif; font-weight: bold; font-size: 1.2rem; text-decoration:none; color: var(--fg); }
.header-controls { display:flex; align-items:center; gap:16px; font-size:14px; flex-wrap:wrap; }
.textsize-controls { display:inline-flex; align-items:center; gap:4px; }
.textsize-controls button {
  cursor:pointer; display:flex; align-items:center; justify-content:center;
  background: var(--card); color: var(--fg); border:1px solid var(--border); border-radius:5px;
  width:30px; height:30px; padding:0;
}
.textsize-controls button:hover { border-color: var(--link); color: var(--link); }
.textsize-controls svg { width:16px; height:16px; flex-shrink:0; }
a.download-link { white-space: nowrap; }
.toc-toggle {
  position: fixed; top: 50%; right: 0; transform: translateY(-50%); z-index: 40;
  font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; font-size: .85rem;
  background: var(--card); color: var(--fg); border: 1px solid var(--border); border-right: none;
  border-radius: 8px 0 0 8px; padding: .6rem .5rem; cursor: pointer;
  writing-mode: vertical-rl; text-orientation: mixed; letter-spacing: .04em;
}
.toc-toggle:hover { color: var(--link); border-color: var(--link); }
.toc-backdrop {
  position: fixed; inset: 0; background: rgba(0,0,0,.35); z-index: 45;
  opacity: 0; pointer-events: none; transition: opacity .15s ease;
}
.toc-backdrop.open { opacity: 1; pointer-events: auto; }
.toc-panel {
  position: fixed; top: 0; right: 0; bottom: 0; width: min(320px, 85vw); z-index: 50;
  background: var(--card); border-left: 1px solid var(--border); box-shadow: -8px 0 24px rgba(0,0,0,.25);
  transform: translateX(100%); transition: transform .2s ease; overflow-y: auto;
  font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif;
  padding: 1rem 1.25rem 2rem;
}
.toc-panel.open { transform: translateX(0); }
.toc-panel h2 { font-size: 1rem; font-family: inherit; margin: 0; }
.toc-panel-head { display:flex; align-items:center; justify-content:space-between; margin-bottom: 1rem; }
.toc-close {
  background: none; border: 1px solid var(--border); border-radius: 6px; color: var(--fg);
  cursor: pointer; width: 1.8rem; height: 1.8rem; font-size: 1rem; line-height: 1;
}
.toc-close:hover { color: var(--link); border-color: var(--link); }
.toc-panel ul { list-style: none; margin: 0; padding: 0; font-size: .9rem; }
.toc-panel li { margin-bottom: .1rem; }
.toc-panel a {
  display: block; padding: .4rem .5rem; border-radius: 6px; text-decoration: none; color: var(--fg);
}
.toc-panel a:hover { background: var(--bg); color: var(--link); }
.toc-panel a.current { background: var(--bg); font-weight: bold; color: var(--link); }
.toc-panel .toc-section-label {
  font-size: .72rem; text-transform: uppercase; letter-spacing: .05em; color: var(--muted);
  margin: 1rem 0 .3rem; padding: 0 .5rem;
}
.toc-panel .toc-section-label:first-of-type { margin-top: 0; }
.breadcrumb { font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; font-size: .85rem; color: var(--muted); margin: 1.25rem 0; }
.breadcrumb a { color: var(--muted); }
.breadcrumb a:hover { color: var(--link); }
h1 { font-size: 1.9rem; margin: 0 0 .25rem; }
h1.chapter-title { font-size: 1.5rem; }
.subtitle { color: var(--muted); font-style: italic; margin: 0 0 1rem; }
.meta { color: var(--muted); font-size: .9rem; font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; }
.badge {
  display:inline-block; font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif;
  font-size: .72rem; letter-spacing:.03em; text-transform:uppercase; padding: .15rem .55rem;
  border-radius: 999px; border:1px solid var(--border); color: var(--muted); margin-right:.4rem;
}
.badge.complete { color: #2f6b3a; border-color:#2f6b3a44; }
.badge.progress { color: #a3730f; border-color:#a3730f44; }
.badge.dev { color: var(--muted); }
.card-list { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:1rem; }
.card {
  position: relative; border:1px solid var(--border); border-radius:10px; padding:1rem 1.1rem;
  background: var(--card); transition: border-color .15s ease, background .15s ease;
}
.card:hover { border-color: var(--link); }
.card h3 { margin: 0 0 .25rem; }
.card p { margin: .35rem 0; color: var(--fg); }
.card .fandom { color: var(--muted); font-size: .85rem; font-style: italic; }
.card a.title-link { text-decoration:none; color: var(--fg); }
.card a.title-link:hover { color: var(--link); }
.card a.title-link::after { content: ""; position: absolute; inset: 0; border-radius: inherit; }
.readme-callout {
  border: 2px solid var(--accent); border-radius: 10px; padding: 1rem 1.25rem; margin: 1.5rem 0;
  background: var(--card);
}
.readme-callout a { font-weight:bold; }
.prose { margin-top: 1.5rem; font-size: calc(1rem * var(--text-scale)); }
.prose p { margin: 0 0 1.05em; }
section + section { margin-top: 3rem; padding-top: 2rem; border-top: 1px solid var(--border); }
section h2 { font-family: Georgia, serif; font-size: 1.3rem; margin: 0 0 1rem; }
.pov-header {
  font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif;
  font-weight: bold; letter-spacing:.02em; color: var(--muted); text-transform: uppercase;
  font-size: calc(.8rem * var(--text-scale));
  border-top: 1px solid var(--border); padding-top: 1rem; margin-top: 1.5rem !important;
}
.scenebreak { text-align:center; color: var(--muted); margin: 1.5em 0 !important; }
nav.chapter-nav {
  display:flex; justify-content:space-between; align-items:center; gap:1rem; margin-top: 2.5rem;
  padding-top: 1rem; border-top: 1px solid var(--border);
  font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; font-size: .95rem;
}
nav.chapter-nav .spacer { flex:1; text-align:center; }
.stub-note { border-left: 3px solid var(--border); padding-left: 1rem; color: var(--muted); font-style: italic; }
footer.site-footer { text-align:center; color: var(--muted); font-size:.8rem; padding: 2rem 1rem;
  font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; }
.comments { margin-top: 3rem; padding-top: 2rem; border-top: 1px solid var(--border); }
.comments-heading { font-size: 1.1rem; margin: 0 0 1rem; }
"""


def page(title, breadcrumb, body, root_rel="../../..", download_href=None, download_label=None, toc_html=None, toc_title=None, download_filename=None, has_prose=False, has_comments=False):
    download_html = (
        f'<a class="download-link" href="{download_href}" download="{html.escape(download_filename or download_href)}">&#11015; {html.escape(download_label)}</a>'
        if download_href
        else ""
    )
    textsize_html = (
        '<span class="textsize-controls" role="group" aria-label="Text size">'
        '<button type="button" id="font-dec" aria-label="Decrease text size"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line><line x1="8" y1="11" x2="14" y2="11"></line></svg></button>'
        '<button type="button" id="font-inc" aria-label="Increase text size"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line><line x1="11" y1="8" x2="11" y2="14"></line><line x1="8" y1="11" x2="14" y2="11"></line></svg></button>'
        '</span>'
        if has_prose
        else ""
    )
    toc_block = ""
    if toc_html:
        toc_block = f"""
<button type="button" id="toc-toggle" class="toc-toggle chrome">Chapters</button>
<div id="toc-backdrop" class="toc-backdrop"></div>
<aside id="toc-panel" class="toc-panel">
  <div class="toc-panel-head">
    <h2>{html.escape(toc_title or 'Chapters')}</h2>
    <button type="button" id="toc-close" class="toc-close" aria-label="Close chapter list">&times;</button>
  </div>
  {toc_html}
</aside>"""
    comments_html = ""
    if has_comments:
        if GISCUS_REPO:
            comments_html = f"""
<section class="comments">
  <h2 class="chrome comments-heading">Comments</h2>
  <script src="https://giscus.app/client.js"
    data-repo="{GISCUS_REPO}"
    data-repo-id="{GISCUS_REPO_ID}"
    data-category="{GISCUS_CATEGORY}"
    data-category-id="{GISCUS_CATEGORY_ID}"
    data-mapping="pathname"
    data-strict="0"
    data-reactions-enabled="1"
    data-emit-metadata="0"
    data-input-position="bottom"
    data-theme="preferred_color_scheme"
    data-lang="en"
    crossorigin="anonymous"
    async>
  </script>
</section>"""
        else:
            comments_html = """
<section class="comments">
  <h2 class="chrome comments-heading">Comments</h2>
  <p class="stub-note">Comments aren't wired up yet &mdash; this section is waiting on a GitHub repo with Discussions enabled and a giscus config. See Website/scripts/build.py for the setup notes.</p>
</section>"""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{root_rel}/css/style.css">
<script src="{root_rel}/js/site.js"></script>
</head>
<body>
<header class="site-header chrome">
  <div class="wrap">
    <a class="brand" href="{root_rel}/index.html">Maestro's Fanfic Archive</a>
    <div class="header-controls">
      {textsize_html}
      {download_html}
      <a href="{root_rel}/about/index.html">About the Author</a>
      <a href="{root_rel}/disclaimers/index.html">Please Read This First</a>
    </div>
  </div>
</header>
<div class="wrap">
  <p class="breadcrumb">{breadcrumb}</p>
  {body}
  {comments_html}
</div>
<footer class="site-footer">Fan works, offered freely, for love of the source material. See <a href="{root_rel}/disclaimers/index.html">disclaimers</a> for details.</footer>
{toc_block}
</body>
</html>"""


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# Series data. Each series has a name/tagline/intro, an optional general
# disclaimer (omit when there's no punched-up source text to reuse rather
# than inventing new legal copy), a dict of story configs, and optionally a
# dict of "in development" stub entries.
# ---------------------------------------------------------------------------

SERIES = {
    "omwom": {
        "name": "O'Make Way, O'Malley!",
        "tagline": "an anthology series — a Rob O'Make O'Malley Production",
        "home_fandom": "an anthology of passenger-seat crossovers, various fandoms",
        "home_blurb": "ROB O'Make O'Malley drops a person or fictional character into someone else's mind as a permanent passenger. Every entry is its own standalone pairing, its own continuity, its own fandom crossover.",
        "intro_html": """
<p><em>An homage to Ack's <strong>I, Panacea</strong> and <strong>Security!</strong> and their passenger-seat premise.</em></p>
<p>ROB O'Make O'Malley permanently drops a person or fictional character into someone else's mental passenger seat. The target remains the driver of their own body; the newcomer becomes an internal companion, adviser, complication, witness, and, eventually, partner.</p>
<p>The series isn't fandom-specific on either side of the pairing. Each entry pairs its own passenger and driver, drawn from whatever film, show, book, or original setting fits, and each entry is its own continuity: characters who share a name or face across two entries are not assumed to share a timeline.</p>
<p>The driver always keeps final say. The passenger is never a downloadable skill package, never omniscient, and can never seize control without the driver's own consent, no matter how good their instincts are. Full mechanics live in the series bible; you don't need it to enjoy any individual entry.</p>
""",
        "disclaimer_html": """
<h2 class="chrome" style="font-size:1.1rem;">Legal Safe Harbor &amp; Disclaimer</h2>
<p>All rights to <em>Worm</em> belong to Wildbow, who built the sandbox and should not be held responsible for what's happened to it since. The passenger-seat premise this whole anthology borrows, abuses, and refuses to give back belongs to Ack, who did it first, did it better, and is owed the credit accordingly. Whatever additional property a given installment drags into this mess belongs to its own respective studio, publisher, or author, none of whom were consulted, all of whom will be properly credited at the top of that entry, because unlike Mr. O'Malley, I do read the fine print. Only the six doors, the waistcoat, the questionable recruitment process, and the crossover logic required to justify any of it belong to Mr. O'Malley, for whatever that turns out to be worth in a court of law.</p>
<ul>
<li><strong>THE PROPER NOMENCLATURE CLAUSE:</strong> <em>&ldquo;It's Mr. O'Malley,&rdquo;</em> a voice cut in, unprompted, the moment an earlier draft of this page tried to get away with the bare trope acronym. <em>&ldquo;Ack gave me the trope. I gave myself the surname. The least anyone can do is use it.&rdquo;</em> Amended accordingly, under mild duress and threat of a violent reaction.</li>
<li><strong>THE WAITING ROOM POLICY:</strong> The author accepts no liability for anyone who drinks something labeled PLOT-RELEVANT BEVERAGE without first asking what plot. There were six doors. You used none of them. That one's on you.</li>
<li><strong>THE PASSENGER-SEAT CLAUSE:</strong> It's permanent. Permanent means permanent. Right up until the end of the story, at which point all bets, warranties, and promises made by a man in a waistcoat become somebody else's problem.</li>
<li><strong>THE &ldquo;IT'S NOT POSSESSION&rdquo; ADDENDUM:</strong> The legal distinction between &ldquo;possession&rdquo; and &ldquo;an uninvited, permanent, occasionally mouth-borrowing roommate&rdquo; remains unresolved and will stay that way for the duration of your natural life, and possibly the driver's too.</li>
<li><strong>THE CONSENT FORM YOU DIDN'T SIGN:</strong> By existing within Mr. O'Malley's reach, you have already implicitly agreed to whatever this is. Ignorance of the terms does not constitute grounds for eviction from someone else's skull. See also: the sign in the waiting room, which you did not read.</li>
<li><strong>THE CROSSOVER LIABILITY CLAUSE:</strong> The properties mixed herein did not consent to meet each other, did not rehearse together, and in several documented cases would actively loathe one another on sight. The author accepts full and complete responsibility for none of the resulting chaos.</li>
<li><strong>THE O'MALLEY ULTIMATUM:</strong> Anyone who argues Mr. O'Malley is not, actually, doing these people a favor will be reminded, calmly, at length, and against their will if necessary, that he never once claimed to be doing them a favor. He said he was giving them something else. Read the transcript. He was very clear about that part.</li>
<li><strong>THE SECOND OPINION CLAUSE:</strong> Mr. O'Malley, despite considerable and largely unearned confidence in his own recruiting instincts, would welcome a critical eye on his work. Beta readers, canon nitpickers, and anyone willing to point out a door that doesn't lead where he claimed it would are warmly invited to reach out before a chapter posts, not after. He finds retroactive correction far less charming than most reviewers seem to assume he would.</li>
</ul>
<p>Each story drags at least one more property into this mess besides <em>Worm</em> and <em>I, Panacea</em>/<em>Security!</em>, and carries its own specific ownership notice for it, since the actual studios and authors involved differ entry to entry. You'll find that story-specific legal text on each story's own disclaimer page, linked from its story index and from the disclaimers hub.</p>
<h2 class="chrome" style="font-size:1.1rem;">Whose Sandbox This Is</h2>
<p>O'Make Way, O'Malley! belongs to me, not to Ack. Whatever this premise owes <em>I, Panacea</em> and <em>Security!</em> is a debt of inspiration, not shared continuity; nothing here is set inside Ack's own version of events, and none of his characters appear.</p>
<p>Rule 9a still applies. I, Maestro, creator and sole proprietor of this sandbox, give open, standing permission for anyone who wants to write more of it, the ROB O'Make O'Malley mechanic, its rules, the anthology structure, all of it, to go ahead. The only conditions are the ordinary ones: proper credit, the standard disclaimer, and whatever Mr. O'Malley himself might decide to add unilaterally, a man who has never once been reachable for comment and shows no sign of starting now.</p>
<p>All of it is fan work, offered freely, for love of the source material, and to Rob O'Make O'Malley, who does not, as far as anyone can prove, actually exist, and who would very much like it kept that way. Any use of this by the copyright owner(s) is freely offered, without expectation of compensation (although a small token of appreciation would be appreciated).</p>
""",
        "stories": {
            "dana": {
                "title": "You Got to Have Faith",
                "series_name": "O'Make Way for Dana",
                "fandom": "True Lies (1994) x Buffy the Vampire Slayer",
                "blurb": "Faith Lehane gets pulled voice-only into the passenger seat of Dana Tasker, an ordinary rebellious teenager, on an ordinary night, right up until Faith realizes Dana's parents are not remotely ordinary.",
                "status": "progress",
                "status_label": "In progress (16 chapters posted)",
                "mode": "dir",
                "dir": f"{CW_IN_PROGRESS}/O'Make Way, O'Malley!/You Got to Have Faith/Chapters",
                "honest_trailer_file": f"{CW_IN_PROGRESS}/O'Make Way, O'Malley!/You Got to Have Faith/Chapters/Honest Trailer.txt",
                "download_author": "O'Malley",
            },
            "taylor": {
                "title": "Med Hard?",
                "series_name": "O'Make Way for Taylor",
                "fandom": "Die Hard 2 (1990) x Worm",
                "blurb": "John McClane goes to the wrong building at the wrong time again. Taylor Hebert just wanted to get through a charity gala as her dad's plus-one. Mr. O'Malley decides they should share the evening, and possibly a body.",
                "status": "complete",
                "status_label": "Complete (29 chapters)",
                "mode": "combined",
                "file": f"{CW_COMPLETE}/O'Make Way, O'Malley!/Book 3 - Med Hard/Manuscript.txt",
                "download_author": "O'Malley",
            },
            "greg": {
                "title": "Staff Infection",
                "series_name": "O'Make Way for Greg",
                "fandom": "Stargate SG-1 x Worm",
                "blurb": "Greg Veder, of all people, gets Colonel Jack O'Neill for a passenger. What starts as one more thing for Greg to feel inadequate about turns into the first real backup he's ever had.",
                "status": "complete",
                "status_label": "Complete (40 chapters)",
                "mode": "combined",
                "file": f"{CW_COMPLETE}/O'Make Way, O'Malley!/Book 2 - Staff Infection/Manuscript.txt",
                "download_author": "O'Malley",
            },
            "xander": {
                "title": "The Eye of the One Who Sees",
                "series_name": "O'Make Way for Xander",
                "fandom": "Buffy the Vampire Slayer x Marvel Cinematic Universe",
                "blurb": "An hour or two before Caleb takes his eye, Xander Harris gets a passenger: Phil Coulson, dry and unbothered and years away from knowing what's coming for him either. Neither of them signed up for this. Both of them show up anyway.",
                "status": "complete",
                "status_label": "Complete (43 chapters)",
                "mode": "combined",
                "file": f"{CW_COMPLETE}/O'Make Way, O'Malley!/Book 1 - The Eye of the One Who Sees/Manuscript.txt",
                "download_author": "O'Malley",
            },
        },
        "story_order": ["dana", "taylor", "greg", "xander"],
        "stubs": {
            "bravestone": {
                "title": "O'Make Way for Bravestone",
                "subtitle": "subtitle undecided",
                "fandom": "The Condemned (2007) x Jumanji: Welcome to the Jungle (2017) x Buffy the Vampire Slayer",
                "blurb": "A double entry: two simultaneous insertions tied to the same mid-drop transformation moment, sharing one setting, one O'Malley, and one climax, but each with its own passenger, driver, and arc.",
            },
            "girl-in-black": {
                "title": "O'Make Way for Girl in Black",
                "subtitle": "subtitle undecided",
                "fandom": "Men in Black (1997) x Worm",
                "blurb": "A rare reversal: Taylor Hebert, pulled out of her locker before her trigger event completes, becomes the passenger riding shotgun in a young NYPD officer who hasn't been recruited into the Men in Black yet.",
            },
            "varga": {
                "title": "O'Make Way for Varga",
                "subtitle": "a very meta O'Make, adjacent to the numbered series",
                "fandom": "Taylor Varga (by mp3.1415player) x O'Make Way, O'Malley! itself",
                "blurb": "Not a driver/passenger insertion at all: characters from an existing, independently-authored fanfic get pulled into the Gallery itself, and Mr. O'Malley retroactively claims credit for an inciting event that may or may not have been his to begin with.",
            },
        },
        "stub_order": ["bravestone", "girl-in-black", "varga"],
    },
    "jumper": {
        "name": "The Jumper Universe",
        "tagline": "an unofficial continuation of Steven Gould's Jumper novels",
        "home_fandom": "Jumper (Steven Gould), 3-book continuation",
        "home_blurb": "The next generation of jumpers, picking up after Exo, following the same multi-POV first-person structure the source novels use.",
        "intro_html": """
<p>A continuation set directly in Steven Gould's own <em>Jumper</em> universe, following <em>Exo</em> (2014), matching the multi-POV first-person structure <em>Impulse</em> and <em>Exo</em> both use, and slotting into the series' one-word-physics-term naming pattern: <em>Jumper, Reflex, Impulse, Exo, Momentum, Reach, Contact</em>. Chapters are headed by whichever character's POV that chapter belongs to, quoting their own opening line as the chapter's title.</p>
<p>Follows Cent, Millie, and Davy, the next generation of jumpers, as the ability stops being anyone's private secret. A light crossover element runs through <em>Momentum</em>: Dan Truman, NASA's Director of Flight Crew Operations from the film <em>Armageddon</em> (1998), appears as an actual character on the mission-command side of the story, not just an homage.</p>
""",
        "disclaimer_html": None,
        "stories": {
            "momentum": {
                "title": "Momentum",
                "series_name": "Book One of the Jumper Universe",
                "fandom": "Jumper (Steven Gould) x Armageddon (1998)",
                "blurb": "Cent's post-Exo life on Kristen Station is steady, hard-won, almost boring, the good kind. Normal doesn't last. The next generation of jumpers has to find out what all that stability was actually for, with NASA's Dan Truman now in the room for the parts of it that go through official channels.",
                "status": "complete",
                "status_label": "Complete (49 chapters)",
                "mode": "combined",
                "file": f"{CW_COMPLETE}/Momentum/Book 1 - Momentum/Manuscript.txt",
                "honest_trailer_file": f"{CW_COMPLETE}/Momentum/Book 1 - Momentum/Honest Trailer.md",
                "chapter_re": JUMPER_CHAPTER_RE,
                "parse_num": word_to_num,
                "pov_re": JUMPER_POV_RE,
                "download_author": "Maestro",
            },
            "reach": {
                "title": "Reach",
                "series_name": "Book Two of the Jumper Universe",
                "fandom": "Jumper (Steven Gould)",
                "blurb": "The direct follow-up to Momentum: further out, harder jobs, and a crew that keeps growing past just Cent, Millie, and Davy as jumping stops being anyone's private secret.",
                "status": "complete",
                "status_label": "Complete (89 chapters)",
                "mode": "combined",
                "file": f"{CW_COMPLETE}/Momentum/Book 2 - Reach/Manuscript.txt",
                "honest_trailer_file": f"{CW_COMPLETE}/Momentum/Book 2 - Reach/Honest Trailer.md",
                "chapter_re": JUMPER_CHAPTER_RE,
                "parse_num": word_to_num,
                "pov_re": JUMPER_POV_RE,
                "download_author": "Maestro",
            },
            "contact": {
                "title": "Contact",
                "series_name": "Book Three of the Jumper Universe",
                "fandom": "Jumper (Steven Gould)",
                "blurb": "The trilogy's capstone. A routine orbital cleanup job turns into something that reaches a great deal further than anyone on the team signed up for.",
                "status": "complete",
                "status_label": "Complete (53 chapters)",
                "mode": "combined",
                "file": f"{CW_COMPLETE}/Momentum/Book 3 - Contact/Manuscript.txt",
                "honest_trailer_file": f"{CW_COMPLETE}/Momentum/Book 3 - Contact/Honest Trailer.md",
                "chapter_re": JUMPER_CHAPTER_RE,
                "parse_num": word_to_num,
                "pov_re": JUMPER_POV_RE,
                "download_author": "Maestro",
            },
        },
        "story_order": ["momentum", "reach", "contact"],
        "stubs": {},
        "stub_order": [],
    },
    "sotl": {
        "name": "Ship of the Line",
        "tagline": "an anthology built on Zaion's Halloween-costume challenge",
        "home_fandom": "an anthology of Halloween-costume crossovers, various fandoms",
        "home_blurb": "One Halloween challenge, answered more than once: a costume that becomes a permanent identity merger, not just a power. Each entry pulls in its own crossover and its own cast.",
        "intro_html": """
<p>Built on Zaion's original "Ship of the Line" challenge: a Halloween costume becomes a permanent identity merger, not just a power. Each entry answers that challenge differently, its own crossover pulled in alongside the costume-shop premise, its own cast, its own shape for what the costume actually becomes.</p>
""",
        "disclaimer_html": None,
        "stories": {
            "convergence": {
                "title": "Ship of the Line - Convergence",
                "series_name": "entry one",
                "fandom": "Buffy the Vampire Slayer x Stargate SG-1 x Stargate Universe x No Man's Sky x The West Wing",
                "blurb": "On Halloween, three costumes stop being costumes. Xander wakes up carrying Eli Wallace's memories and a future he hasn't lived yet; Buffy and Willow wake up not human anymore, at all, permanently. A dare from a costume shop turns into first contact with two governments, an Ancient warship, and whatever's left of who they used to be.",
                "status": "complete",
                "status_label": "Complete (27 chapters)",
                "mode": "combined",
                "file": f"{CW_COMPLETE}/Ship of the Line/Convergence/Manuscript.txt",
                "honest_trailer_file": f"{CW_COMPLETE}/Ship of the Line/Convergence/Honest Trailer.md",
                "chapter_re": SOTL_CHAPTER_RE,
                "parse_num": word_to_num,
                "download_author": "Maestro",
            },
        },
        "story_order": ["convergence"],
        "stubs": {
            "city-who-fought": {
                "title": "Ship of the Line: The City Who Fought (working title)",
                "subtitle": "entry two, subtitle undecided",
                "fandom": "Buffy the Vampire Slayer x The City Who Fought (Anne McCaffrey & S.M. Stirling)",
                "blurb": "A second answer to Zaion's “Ship of the Line” challenge. Not yet started; further details to come.",
            },
        },
        "stub_order": ["city-who-fought"],
    },
}

SERIES_ORDER = ["omwom", "jumper", "sotl"]

# ---------------------------------------------------------------------------
# Standalone works — single stories that don't belong to a numbered series,
# so they skip the series-index/series-disclaimer wrapper pages and live
# directly under standalone/{slug}/ instead of series/{series}/{slug}/.
# ---------------------------------------------------------------------------

STANDALONES = {
    "wood-it-work": {
        "title": "Wood It Work: Book 2 — Wardrobes and Would-Work",
        "series_name": "a continuation of Wood It Work by dogbertcarroll",
        "fandom": "Buffy the Vampire Slayer x Dungeons & Dragons",
        "blurb": "A continuation of dogbertcarroll's Wood It Work, picking up at Chapter 26. Xander, Willow, Jesse, and the household built around one very unusual workshop door keep finding new worlds on the other side of it, including a water-scarce desert culture mid-treaty negotiation and whatever King Then'tal's court actually wants from them.",
        "status": "complete",
        "status_label": "Complete (57 chapters, numbered 26–82)",
        "mode": "combined",
        "file": f"{CW_COMPLETE}/Wood It Work/Book 2 - Wardrobes and Would-Work/Manuscript.txt",
        "honest_trailer_file": f"{CW_COMPLETE}/Wood It Work/Book 2 - Wardrobes and Would-Work/Honest Trailer.md",
        "download_author": "Maestro",
    },
}

STANDALONE_ORDER = ["wood-it-work"]

AI_DISCLOSURE_HTML = """
<h2>Creative Process &amp; AI Disclosure</h2>
<p>Please read all of this first part of the disclosure before deciding to turn it down flat.</p>
<p>Every chapter, every paragraph, every word has passed my &ldquo;perception filter,&rdquo; trained by half a century of reading fiction to know what works &amp; what's the &ldquo;uncanny valley.&rdquo; However, despite decades of workshops, seminars, and trying my hardest, I cannot write believable prose myself; my raw writing always turns out wooden. And it hasn't improved one iota for the attempt in a half-century.</p>
<p>Because of this, my creative process is a partnership:</p>
<p><strong>What I Do:</strong> I handle 100% of the world-building, plot outlining, scene development, character arcs, and deep structural and copy-editing.<br>
<strong>What AI Does:</strong> I use generative AI as a tool to help bridge the gap between my outlines and the raw text, drafting the initial prose based on my exact conceptual directions.<br>
<strong>The Final Polish:</strong> I hand-edit and proofread every single word to ensure the final story matches my exact vision.</p>
<p>Why I do it this way: I write these so I can enjoy reading the result, just as I would a book by the original author, and because leaving them as un-fleshed-out ideas is unconscionable. The difference is, I finally have tools good enough to do something about it. Posting them here will always be secondary.</p>
<p>I believe in radical transparency. If you are looking for works written entirely by a human hand, I completely respect that, but this story may not be for you. If you are here for the world, the characters, and the care put into crafting the narrative, welcome aboard.</p>
"""


def build_toc(chapters, has_disclaimer, has_trailer, current_href):
    def link(href, label):
        cls = ' class="current"' if href == current_href else ""
        return f'<li><a href="{href}"{cls}>{label}</a></li>'

    parts = []
    if has_disclaimer:
        parts.append('<p class="toc-section-label">Front Matter</p><ul>')
        parts.append(link("disclaimer.html", "Disclaimer"))
        parts.append("</ul>")
    parts.append('<p class="toc-section-label">Chapters</p><ul>')
    for num, title, _ in chapters:
        parts.append(link(f"ch{num}.html", f"{num}. {html.escape(title)}"))
    parts.append("</ul>")
    extras = []
    if has_trailer:
        extras.append(link("honest-trailer.html", "Honest Trailer"))
    extras.append(link("full.html", "Full Text (one page)"))
    parts.append('<p class="toc-section-label">Extras</p><ul>' + "".join(extras) + "</ul>")
    return "\n".join(parts)


def crumb_prefix(root_rel, series_slug, series_display_name, story_title):
    """Breadcrumb prefix for a story's SUB-pages (disclaimer/chapter/full/etc),
    where the story name is itself a link back to its own index."""
    home = f'<a href="{root_rel}/index.html">Home</a> &raquo; '
    if series_slug:
        return (
            home
            + f'<a href="{root_rel}/series/{series_slug}/index.html">{html.escape(series_display_name)}</a> &raquo; '
            + f'<a href="index.html">{html.escape(story_title)}</a>'
        )
    return home + f'<a href="index.html">{html.escape(story_title)}</a>'


def crumb_prefix_plain(root_rel, series_slug, series_display_name, story_title):
    """Breadcrumb for the story's OWN index page, where the story name is the
    current (non-link) page and so renders as plain text."""
    home = f'<a href="{root_rel}/index.html">Home</a> &raquo; '
    if series_slug:
        return (
            home
            + f'<a href="{root_rel}/series/{series_slug}/index.html">{html.escape(series_display_name)}</a> &raquo; '
            + html.escape(story_title)
        )
    return home + html.escape(story_title)


def load_standalone_trailer(path):
    """Return (title, body) from a standalone Honest Trailer file, or None if
    the story has no such file. Handles a leading Markdown '# ' title line
    (the Collected Works convention) as well as a bare first-line title."""
    if not path or not os.path.exists(path):
        return None
    raw = read(path).strip()
    first_nl = raw.find("\n")
    title = raw[:first_nl].strip() if first_nl != -1 else raw
    body = raw[first_nl:].strip() if first_nl != -1 else ""
    title = re.sub(r"^#+\s*", "", title)
    return (title, body)


def build_story(slug, cfg, series_slug=None, series_display_name=None):
    """Build one story's pages. series_slug=None means a standalone (no wrapping
    series index/disclaimer page); otherwise nests under series/{series_slug}/{slug}."""
    if series_slug:
        base = f"{OUT}/series/{series_slug}/{slug}"
        root_rel = "../../.."
    else:
        base = f"{OUT}/standalone/{slug}"
        root_rel = "../.."
    download_href = f"{slug}.txt"
    download_label = "Download as text"
    download_filename = f"{cfg.get('download_author', 'Maestro')} - {cfg['title']}.txt"
    uses_honest_trailer = cfg.get("uses_honest_trailer", True)
    chapter_re = cfg.get("chapter_re", CHAPTER_RE)
    parse_num = cfg.get("parse_num", int)
    exts = cfg.get("chapter_file_exts", (".txt",))
    pov_re = cfg.get("pov_re", DEFAULT_POV_RE)

    if cfg["mode"] == "dir":
        files = sorted(
            f for f in os.listdir(cfg["dir"])
            if f.lower().endswith(exts) and "chapter" in f.lower()
        )
        chapters = []
        ch0_body = None
        preamble_for_ch1 = None
        for fname in files:
            text = read(f"{cfg['dir']}/{fname}")
            preamble, parsed = split_chapters(text, chapter_re, parse_num)
            for num, title, body in parsed:
                if num == 0:
                    ch0_body = body
                else:
                    chapters.append((num, title, body))
            if preamble and any(num == 1 for num, _, _ in parsed):
                preamble_for_ch1 = preamble
        if ch0_body is None:
            ch0_body = preamble_for_ch1
        chapters.sort(key=lambda c: c[0])
    else:
        text = read(cfg["file"])
        preamble, parsed = split_chapters(text, chapter_re, parse_num)
        ch0_body = None
        chapters = []
        for num, title, body in parsed:
            if num == 0:
                ch0_body = body
            else:
                chapters.append((num, title, body))
        if ch0_body is None and preamble:
            ch0_body = preamble

    honest_trailer_standalone = load_standalone_trailer(cfg.get("honest_trailer_file"))

    # some books' chapters carry no individual title, just a number — fall back
    # to "Chapter N" as the display title rather than leaving it blank
    chapters = [(num, title if title else f"Chapter {num}", body) for num, title, body in chapters]

    # find in-sequence honest trailer chapter (used by some series, e.g. O'Make Way, O'Malley!)
    ht_inline_num = None
    if uses_honest_trailer:
        for num, title, body in chapters:
            if "honest trailer" in title.lower():
                ht_inline_num = num
                break
    has_trailer = honest_trailer_standalone is not None or ht_inline_num is not None
    has_disclaimer = ch0_body is not None
    ch0_body_clean = strip_ai_disclosure(ch0_body) if ch0_body else None
    toc_title = cfg["title"]
    crumb_base = crumb_prefix(root_rel, series_slug, series_display_name, cfg["title"])

    # --- disclaimer page ---
    disclaimer_body_html = (
        body_to_html(ch0_body_clean, pov_re)
        if ch0_body_clean
        else "<p><em>No separate disclaimer chapter for this entry yet.</em></p>"
    )
    ai_pointer_html = (
        f'<p class="stub-note">How these stories actually get written lives site-wide on the '
        f'<a href="{root_rel}/disclaimers/index.html">Please Read This First</a> page, not repeated per story.</p>'
    )
    write(
        f"{base}/disclaimer.html",
        page(
            f"{cfg['title']} — Disclaimer",
            f"{crumb_base} &raquo; Disclaimer",
            f'<h1 class="chapter-title">Disclaimer &amp; Front Matter</h1>\n{ai_pointer_html}\n<div class="prose">{disclaimer_body_html}</div>'
            f'\n<nav class="chapter-nav"><a href="index.html">&larr; Back to story</a><span class="spacer"></span>'
            f'<a href="ch1.html">Start reading &rarr;</a></nav>',
            root_rel,
            download_href,
            download_label,
            build_toc(chapters, has_disclaimer, has_trailer, "disclaimer.html"),
            toc_title,
            download_filename,
            True,
        ),
    )

    # --- chapter pages ---
    n = len(chapters)
    for i, (num, title, body) in enumerate(chapters):
        body_html = body_to_html(body, pov_re)
        prev_link = f'<a href="ch{chapters[i-1][0]}.html">&larr; Ch. {chapters[i-1][0]}</a>' if i > 0 else f'<a href="disclaimer.html">&larr; Front matter</a>'
        if i + 1 < n:
            next_link = f'<a href="ch{chapters[i+1][0]}.html">Ch. {chapters[i+1][0]} &rarr;</a>'
        elif honest_trailer_standalone:
            next_link = '<a href="honest-trailer.html">Honest Trailer &rarr;</a>'
        else:
            next_link = '<a href="index.html">Back to story index</a>'
        crumb = f"{crumb_base} &raquo; Ch. {num}"
        pos = i + 1
        meta_line = f"Chapter {num} of {n}" if pos == num else f"Chapter {num} ({pos} of {n} in this book)"
        content = (
            f'<p class="meta">{meta_line}</p>'
            f'<h1 class="chapter-title">{html.escape(title)}</h1>'
            f'<div class="prose">{body_html}</div>'
            f'<nav class="chapter-nav">{prev_link}<span class="spacer"><a href="index.html">Story index</a></span>{next_link}</nav>'
        )
        write(f"{base}/ch{num}.html", page(f"{cfg['title']} — Ch. {num}: {title}", crumb, content, root_rel, download_href, download_label, build_toc(chapters, has_disclaimer, has_trailer, f"ch{num}.html"), toc_title, download_filename, True, True))
        if num == ht_inline_num:
            # duplicate as the dedicated Honest Trailer page for the story->trailer->fic click path
            ht_crumb = f"{crumb_base} &raquo; Honest Trailer"
            ht_content = (
                f'<p class="meta">Honest Trailer</p>'
                f'<h1 class="chapter-title">{html.escape(title)}</h1>'
                f'<div class="prose">{body_html}</div>'
                f'<nav class="chapter-nav"><a href="index.html">&larr; Back to story</a><span class="spacer"></span>'
                f'<a href="ch1.html">Start from Chapter 1 &rarr;</a></nav>'
            )
            write(f"{base}/honest-trailer.html", page(f"{cfg['title']} — Honest Trailer", ht_crumb, ht_content, root_rel, download_href, download_label, build_toc(chapters, has_disclaimer, has_trailer, "honest-trailer.html"), toc_title, download_filename, True))

    if honest_trailer_standalone:
        ht_title, ht_body = honest_trailer_standalone
        ht_body_html = body_to_html(ht_body, pov_re)
        crumb = f"{crumb_base} &raquo; Honest Trailer"
        content = (
            f'<p class="meta">Honest Trailer</p>'
            f'<h1 class="chapter-title">{html.escape(ht_title)}</h1>'
            f'<div class="prose">{ht_body_html}</div>'
            f'<nav class="chapter-nav"><a href="index.html">&larr; Back to story</a><span class="spacer"></span>'
            f'<a href="ch1.html">Start from Chapter 1 &rarr;</a></nav>'
        )
        write(f"{base}/honest-trailer.html", page(f"{cfg['title']} — Honest Trailer", crumb, content, root_rel, download_href, download_label, build_toc(chapters, has_disclaimer, has_trailer, "honest-trailer.html"), toc_title, download_filename, True))

    # --- plain-text download ---
    txt_parts = [cfg["title"], cfg.get("series_name") or "", ""]
    if ch0_body_clean:
        txt_parts.append(ch0_body_clean.strip())
        txt_parts.append("")
    for num, title, body in chapters:
        txt_parts.append(f"Chapter {num}: {title}")
        txt_parts.append("")
        txt_parts.append(body.strip())
        txt_parts.append("")
    if honest_trailer_standalone:
        ht_title, ht_body = honest_trailer_standalone
        txt_parts.append(ht_title)
        txt_parts.append("")
        txt_parts.append(ht_body.strip())
        txt_parts.append("")
    write(f"{base}/{download_href}", "\n\n".join(txt_parts).strip() + "\n")

    # --- combined "read the whole story" page ---
    full_sections = []
    if ch0_body_clean:
        full_sections.append(
            f'<section><h2>Disclaimer &amp; Front Matter</h2><div class="prose">{body_to_html(ch0_body_clean, pov_re)}</div></section>'
        )
    for num, title, body in chapters:
        full_sections.append(
            f'<section><h2>Chapter {num}: {html.escape(title)}</h2><div class="prose">{body_to_html(body, pov_re)}</div></section>'
        )
    if honest_trailer_standalone:
        ht_title, ht_body = honest_trailer_standalone
        full_sections.append(
            f'<section><h2>{html.escape(ht_title)}</h2><div class="prose">{body_to_html(ht_body, pov_re)}</div></section>'
        )
    full_content = (
        f'<h1>{html.escape(cfg["title"])}</h1>'
        f'<p class="subtitle">the whole thing, one page, no clicking</p>'
        f'<p class="meta"><a href="index.html">&larr; Back to story index</a></p>'
        + "".join(full_sections)
        + '<nav class="chapter-nav"><a href="index.html">&larr; Back to story index</a><span class="spacer"></span><a href="#">&uarr; Top</a></nav>'
    )
    full_crumb = f"{crumb_base} &raquo; Full text"
    write(
        f"{base}/full.html",
        page(f"{cfg['title']} — Full Text", full_crumb, full_content, root_rel, download_href, download_label, build_toc(chapters, has_disclaimer, has_trailer, "full.html"), toc_title, download_filename, True),
    )

    # --- story index page ---
    if has_trailer:
        trailer_html = '<p><a href="honest-trailer.html"><strong>&#9658; Read the Honest Trailer</strong></a> (a spoiler-heavy, trailer-voice bonus bit &mdash; read it before or after, your call)</p>'
    elif uses_honest_trailer:
        trailer_html = '<p class="stub-note">No Honest Trailer written for this entry yet.</p>'
    else:
        trailer_html = ""
    badge_class = "complete" if cfg["status"] == "complete" else "progress"
    subtitle_html = f'<p class="subtitle">{html.escape(cfg["series_name"])}</p>' if cfg.get("series_name") else ""
    content = f"""
<h1>{html.escape(cfg['title'])}</h1>
{subtitle_html}
<p class="meta"><span class="badge {badge_class}">{html.escape(cfg['status_label'])}</span></p>
<p class="fandom">{html.escape(cfg['fandom'])}</p>
<p>{html.escape(cfg['blurb'])}</p>
{trailer_html}
<p><a href="disclaimer.html">Disclaimer &amp; front matter for this story</a></p>
<p><a href="ch{chapters[0][0]}.html"><strong>Start reading &rarr;</strong></a></p>
<p><a href="full.html">Read the whole story in one page &rarr;</a></p>
<p><a href="{download_href}" download="{html.escape(download_filename)}">&#11015; Download as text</a></p>
<p class="stub-note">Full chapter list is in the &ldquo;Chapters&rdquo; panel, right edge of the screen.</p>
"""
    crumb = crumb_prefix_plain(root_rel, series_slug, series_display_name, cfg["title"])
    write(f"{base}/index.html", page(cfg["title"], crumb, content, root_rel, download_href, download_label, build_toc(chapters, has_disclaimer, has_trailer, "index.html"), toc_title, download_filename, False, True))
    return {"has_trailer": has_trailer, "base_href": (f"series/{series_slug}/{slug}" if series_slug else f"standalone/{slug}")}


def build_stub(series_slug, series_name, slug, cfg):
    root_rel = "../../.."
    crumb = (
        f'<a href="{root_rel}/index.html">Home</a> &raquo; '
        f'<a href="{root_rel}/series/{series_slug}/index.html">{html.escape(series_name)}</a> &raquo; {html.escape(cfg["title"])}'
    )
    content = f"""
<h1>{html.escape(cfg['title'])}</h1>
<p class="subtitle">{html.escape(cfg['subtitle'])}</p>
<p class="meta"><span class="badge dev">In development &mdash; not yet drafted</span></p>
<p class="fandom">{html.escape(cfg['fandom'])}</p>
<p>{html.escape(cfg['blurb'])}</p>
<p class="stub-note">This entry hasn't been written yet. Check back later.</p>
"""
    write(f"{OUT}/series/{series_slug}/{slug}/index.html", page(cfg["title"], crumb, content, root_rel))


def build_series_index(series_slug, info):
    root_rel = "../.."
    cards = []
    for slug in info["story_order"]:
        cfg = info["stories"][slug]
        badge_class = "complete" if cfg["status"] == "complete" else "progress"
        cards.append(f"""
<li class="card">
  <h3><a class="title-link" href="{slug}/index.html">{html.escape(cfg['title'])}</a></h3>
  <p class="fandom">{html.escape(cfg['fandom'])}</p>
  <p><span class="badge {badge_class}">{html.escape(cfg['status_label'])}</span></p>
  <p>{html.escape(cfg['blurb'])}</p>
</li>""")
    for slug in info.get("stub_order", []):
        cfg = info["stubs"][slug]
        cards.append(f"""
<li class="card">
  <h3><a class="title-link" href="{slug}/index.html">{html.escape(cfg['title'])}</a></h3>
  <p class="fandom">{html.escape(cfg['fandom'])}</p>
  <p><span class="badge dev">In development</span></p>
  <p>{html.escape(cfg['blurb'])}</p>
</li>""")
    disclaimer_link = (
        '<p><a href="disclaimer.html">Read the general series disclaimer</a></p>'
        if info.get("disclaimer_html")
        else ""
    )
    content = f"""
<h1>{html.escape(info['name'])}</h1>
<p class="subtitle">{html.escape(info['tagline'])}</p>
{info['intro_html']}
{disclaimer_link}
<h2 class="chrome" style="font-size:1.2rem; margin-top:2rem;">Entries</h2>
<ul class="card-list">
{''.join(cards)}
</ul>
"""
    write(f"{OUT}/series/{series_slug}/index.html", page(info["name"], f'<a href="{root_rel}/index.html">Home</a> &raquo; {html.escape(info["name"])}', content, root_rel))


def build_series_disclaimer(series_slug, info):
    if not info.get("disclaimer_html"):
        return
    root_rel = "../.."
    content = f"""
<h1>{html.escape(info['name'])} &mdash; General Disclaimer</h1>
{info['disclaimer_html']}
<p><a href="index.html">&larr; Back to {html.escape(info['name'])}</a></p>
"""
    write(
        f"{OUT}/series/{series_slug}/disclaimer.html",
        page(
            f"{info['name']} — General Disclaimer",
            f'<a href="{root_rel}/index.html">Home</a> &raquo; <a href="index.html">{html.escape(info["name"])}</a> &raquo; Disclaimer',
            content,
            root_rel,
        ),
    )


def build_disclaimers_hub():
    root_rel = ".."
    series_disclaimer_links = "\n".join(
        f'<li><a href="{root_rel}/series/{series_slug}/disclaimer.html"><strong>{html.escape(info["name"])} general disclaimer</strong></a></li>'
        for series_slug in SERIES_ORDER
        for info in [SERIES[series_slug]]
        if info.get("disclaimer_html")
    )
    other_disclaimers_block = (
        f'<h2 class="chrome" style="font-size:1.1rem;">Other disclaimers</h2>\n<ul>\n{series_disclaimer_links}\n</ul>'
        if series_disclaimer_links
        else ""
    )
    story_links = "\n".join(
        f'<li><a href="{root_rel}/series/{series_slug}/{slug}/disclaimer.html">{html.escape(cfg["title"])}</a> &mdash; {html.escape(cfg["fandom"])}</li>'
        for series_slug in SERIES_ORDER
        for slug, cfg in SERIES[series_slug]["stories"].items()
    )
    standalone_links = "\n".join(
        f'<li><a href="{root_rel}/standalone/{slug}/disclaimer.html">{html.escape(STANDALONES[slug]["title"])}</a> &mdash; {html.escape(STANDALONES[slug]["fandom"])}</li>'
        for slug in STANDALONE_ORDER
    )
    content = f"""
<h1>Please Read This First</h1>
{AI_DISCLOSURE_HTML}
<hr style="border:none; border-top:1px solid var(--border); margin:2rem 0;">
{other_disclaimers_block}
<h3 class="chrome" style="font-size:1rem;">Story-specific disclaimers</h3>
<p>Each story below crosses its own specific properties and carries its own ownership notice on its own disclaimer page:</p>
<ul>
{story_links}
{standalone_links}
</ul>
<p><a href="{root_rel}/index.html">&larr; Back to the front page</a></p>
"""
    write(f"{OUT}/disclaimers/index.html", page("Please Read This First", '<a href="../index.html">Home</a> &raquo; Please Read This First', content, root_rel))


ABOUT_SECTIONS_HTML = """
<h2 class="chrome" style="font-size:1.2rem;">Watch as he...</h2>
<p>Tries obsessively, for the better part of a century, to write believable prose of any kind</p>
<p>Fails miserably, time after time</p>
<p>Attends workshops, seminars, even one-on-ones with published authors</p>
<p>Keeps failing miserably</p>
<p>And finally, after decades, concludes he&#x27;s just incapable of doing it. <em>&ldquo;I mean, I had to get there eventually.&rdquo;</em></p>

<h2 class="chrome" style="font-size:1.2rem; margin-top:2rem;">Marvel as he...</h2>
<p>Breaks every rule made by man, nature, physics, and common decency, just to make his obsession bear fruit he&#x27;ll actually enjoy reading</p>
<p>Uses a personal mantra as his mission statement. <em>&ldquo;Well, yeah. &lsquo;Find the funny&rsquo; is kind of catchy when you think about it.&rdquo;</em></p>
<p>Mocks everything in the universe: things that are real, things that are made up, characters from any fandom that catches his interest, the actors who play them, and&hellip; himself</p>

<h2 class="chrome" style="font-size:1.2rem; margin-top:2rem;">Featuring him...</h2>
<p>Picking up a tool that draws nothing but pitchforks from half the writing community</p>
<p>Not giving a single fuck about any of it</p>
<p>Defending that choice loudly, repeatedly, at a length nobody asked for</p>
<p>Refusing, categorically, to back down</p>

<h2 class="chrome" style="font-size:1.2rem; margin-top:2rem;">Starring...</h2>
<p>One (1) revolving door</p>
<p>One entire cast encompassing every character that ever existed, passing through it&hellip; and a few that only existed in a fever-dream</p>
<p>One (?) Omnipotent Being</p>
<p>One (1) all-time favorite author, Steven Gould, without whom none of this would exist</p>
<p>and</p>
<p>One intent to mock anyone who disagrees with that opinion</p>

<h2 class="chrome" style="font-size:1.2rem; margin-top:2rem;">Be astounded by...</h2>
<p>A writing style that imitates someone who imitates something else already</p>
<p><em>(Seriously, those guys over at <a href="https://www.youtube.com/@ScreenJunkies" target="_blank" rel="noopener">Screen Junkies</a> are fucking incredible. Major props to them.)</em></p>
"""


def build_about():
    root_rel = ".."
    content = f"""
<h1>The Author Who Wouldn&#x27;t Shut Up About It</h1>
<p class="subtitle">an origin story, honest-trailer style</p>
<div class="prose">
{ABOUT_SECTIONS_HTML}
</div>
"""
    write(
        f"{OUT}/about/index.html",
        page(
            "About the Author — Maestro's Fanfic Archive",
            '<a href="../index.html">Home</a> &raquo; About the Author',
            content,
            root_rel,
        ),
    )


def build_home():
    series_cards = []
    for series_slug in SERIES_ORDER:
        info = SERIES[series_slug]
        series_cards.append(f"""
<li class="card">
  <h3><a class="title-link" href="series/{series_slug}/index.html">{html.escape(info['name'])}</a></h3>
  <p class="fandom">{html.escape(info['home_fandom'])}</p>
  <p>{html.escape(info['home_blurb'])}</p>
</li>""")
    standalone_cards = []
    for slug in STANDALONE_ORDER:
        cfg = STANDALONES[slug]
        badge_class = "complete" if cfg["status"] == "complete" else "progress"
        standalone_cards.append(f"""
<li class="card">
  <h3><a class="title-link" href="standalone/{slug}/index.html">{html.escape(cfg['title'])}</a></h3>
  <p class="fandom">{html.escape(cfg['fandom'])}</p>
  <p><span class="badge {badge_class}">{html.escape(cfg['status_label'])}</span></p>
  <p>{html.escape(cfg['blurb'])}</p>
</li>""")
    content = f"""
<h1>Maestro's Fanfic Archive</h1>
<p class="subtitle">a home for the stories, series by series</p>
<div class="prose">
{ABOUT_SECTIONS_HTML}
</div>
<div class="readme-callout chrome" style="margin-top:2rem;">
  <p>New here? <a href="disclaimers/index.html">Please read this first</a> &mdash; how these stories get written, what they are and aren't, and the specific disclaimers for each series and story.</p>
</div>
<h2 class="chrome" style="font-size:1.2rem;">Series</h2>
<ul class="card-list">
{''.join(series_cards)}
</ul>
<h2 class="chrome" style="font-size:1.2rem; margin-top:2rem;">Standalones</h2>
<ul class="card-list">
{''.join(standalone_cards)}
</ul>
"""
    write(f"{OUT}/index.html", page("Maestro's Fanfic Archive", 'Home', content, "."))


def main():
    write(f"{OUT}/css/style.css", CSS)
    write(f"{OUT}/js/site.js", SITE_JS)
    for series_slug in SERIES_ORDER:
        info = SERIES[series_slug]
        for slug in info["story_order"]:
            build_story(slug, info["stories"][slug], series_slug=series_slug, series_display_name=info["name"])
        for slug in info.get("stub_order", []):
            build_stub(series_slug, info["name"], slug, info["stubs"][slug])
        build_series_index(series_slug, info)
        build_series_disclaimer(series_slug, info)
    for slug in STANDALONE_ORDER:
        build_story(slug, STANDALONES[slug])
    build_disclaimers_hub()
    build_about()
    build_home()
    print("Build complete ->", OUT)


if __name__ == "__main__":
    main()
