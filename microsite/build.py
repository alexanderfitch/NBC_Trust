"""Static site builder for The Owner's Table, NBC Trust's advisor microsite.

Stdlib only, matching the data-engine's constraint (D-005): no pip, no build
toolchain, runs anywhere, and a solo maintainer can read the whole thing.

Design (D-019, extended by D-025):
- **Copy lives in ``content/*.md``, markup lives in ``src/``.** Whoever writes
  copy never has to touch HTML. Integrating new copy is an edit to a markdown
  file, not a rebuild of the page.
- Every page's copy is a versioned file in git, which is also PLAN.md Stage
  F1's public-asset-versioning requirement satisfied for free.
- Output goes to ``dist/`` and is NOT committed; it is generated.
- The markdown subset is deliberately small (see ``_render_block``). A
  hand-rolled parser is only defensible if it stays small, so anything it
  does not recognise is emitted as a paragraph rather than silently dropped.

The subset, beyond headings / lists / quotes / bold / italic / links:

    ::: name [modifier ...]     a full-width section ("band"). Text before the
    ...                         first ### is the band's intro; each ### starts
    :::                         an item (a card, a step, an FAQ entry...).
    ^ Eyebrow                   a small label line above a heading
    -> [Label](/url)            a button; consecutive lines form a button row
    [video:slug]                a video slot, resolved against site.json
    [cta:kind]                  a closing call to action (join, hand, checklist)
    [partial:name]              src/partials/name.html, verbatim (tools, forms)
    [library:featured|all|related]   article cards from content/library/

Links in copy are written root-relative (``/library/``) as if the site lived
at ``/``; the mount prefix is applied at build time (PLAN.md decision #6).

Run:  python3 microsite/build.py            # builds to microsite/dist/
      python3 microsite/build.py --local    # preview build, server root
      python3 microsite/build.py --check    # report placeholders, build nothing
"""

import argparse
import html
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

MICROSITE_ROOT = Path(__file__).resolve().parent
CONTENT_DIR = MICROSITE_ROOT / "content"
LIBRARY_DIR = CONTENT_DIR / "library"
SRC_DIR = MICROSITE_ROOT / "src"
PARTIALS_DIR = SRC_DIR / "partials"
ASSETS_DIR = MICROSITE_ROOT / "assets"
DIST_DIR = MICROSITE_ROOT / "dist"
SITE_CONFIG = MICROSITE_ROOT / "site.json"

# Copy or wiring still owed is marked with this token so `--check` can find it
# and so nothing placeholder-y can reach production unnoticed.
PLACEHOLDER_TOKEN = "PLACEHOLDER"


# --------------------------------------------------------------------------
# front matter + markdown subset
# --------------------------------------------------------------------------

def parse_front_matter(text):
    """Split leading ``---`` delimited ``key: value`` block from the body."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    meta = {}
    for line in text[3:end].strip().splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        meta[key.strip()] = val.strip()
    return meta, text[end + 4:].lstrip("\n")


_INLINE = [
    (re.compile(r"\*\*(.+?)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<!\*)\*([^*]+?)\*(?!\*)"), r"<em>\1</em>"),
    (re.compile(r"\[([^\]]+)\]\(([^)]+)\)"), r'<a href="\2">\1</a>'),
]


_SMART_QUOTES = [
    (re.compile(r"(?<=\w)'"), "\u2019"),            # don't, owner's
    (re.compile(r"'(?=\w)"), "\u2018"),
    (re.compile(r"'"), "\u2019"),
    (re.compile(r'(^|(?<=[\s(\[*]))"'), "\u201c"),
    (re.compile(r'"'), "\u201d"),
]


def smart_quotes(text):
    """Typographer's quotes for plain copy. Runs before any markup exists, so
    it can never touch an attribute value."""
    for pattern, repl in _SMART_QUOTES:
        text = pattern.sub(repl, text)
    return text


def _inline(text):
    """Escape, then apply the inline subset. Escaping first is deliberate:
    copy is authored by humans and must never be able to inject markup."""
    out = html.escape(smart_quotes(text), quote=False)
    for pattern, repl in _INLINE:
        out = pattern.sub(repl, out)
    return out


def prefix_links(markup, prefix):
    """Mount root-relative ``href``/``src`` values under the path prefix.

    Applied to rendered copy and partials only -- never to the assembled page,
    whose template tokens are already prefixed and would be doubled.
    """
    prefix = (prefix or "").rstrip("/")
    if not prefix:
        return markup
    return re.sub(r'\b(href|src|action)="/(?!/)', r'\1="%s/' % prefix, markup)


_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _render_actions(block):
    """``-> [Label](/url)`` lines become a button row; the first is primary."""
    buttons = []
    for i, line in enumerate(block.splitlines()):
        m = _LINK.search(line)
        if not m:
            continue
        cls = "button" if i == 0 else "button button--ghost"
        buttons.append('<a class="%s" href="%s">%s</a>'
                       % (cls, html.escape(m.group(2)), _inline(m.group(1))))
    return '<p class="actions">%s</p>' % "".join(buttons)


def _is_actions(block):
    return all(l.strip().startswith("-> ") for l in block.splitlines())


def _render_block(block, ctx):
    """One blank-line-separated block of the subset."""
    videos = ctx.get("videos", {})

    m = re.fullmatch(r"\[video:([\w-]+)\]", block)
    if m:
        return _render_video(m.group(1), videos)
    m = re.fullmatch(r"\[cta:([\w-]+)\]", block)
    if m:
        return _render_cta(m.group(1))
    m = re.fullmatch(r"\[partial:([\w-]+)\]", block)
    if m:
        return _render_partial(m.group(1))
    m = re.fullmatch(r"\[library:([\w-]+)\]", block)
    if m:
        return _render_library(m.group(1), ctx)

    if block.startswith("### "):
        return "<h3>%s</h3>" % _inline(block[4:].strip())
    if block.startswith("## "):
        return "<h2>%s</h2>" % _inline(block[3:].strip())
    if block.startswith("# "):
        return "<h1>%s</h1>" % _inline(block[2:].strip())
    if block.startswith("^ "):
        return '<p class="eyebrow">%s</p>' % _inline(block[2:].strip())
    if _is_actions(block):
        return _render_actions(block)
    lines = block.splitlines()
    if all(l.strip().startswith("- ") for l in lines):
        return "<ul>%s</ul>" % "".join("<li>%s</li>" % _inline(l.strip()[2:]) for l in lines)
    if all(re.match(r"\d+\. ", l.strip()) for l in lines):
        return "<ol>%s</ol>" % "".join(
            "<li>%s</li>" % _inline(l.strip().split(" ", 1)[1]) for l in lines)
    if all(l.strip().startswith("> ") for l in lines):
        quote = " ".join(l.strip()[2:] for l in lines)
        return "<blockquote><p>%s</p></blockquote>" % _inline(quote)
    return "<p>%s</p>" % _inline(block.replace("\n", " "))


def _blocks(text):
    return [b.strip() for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]


# Directives that render their own full-width section, so a run of prose
# around them must be closed off first rather than wrapping them.
_FULL_BLEED = re.compile(r"\[(cta|partial|library):[\w-]+\]")

_CONTAINER_OPEN = re.compile(r"^:::\s*([\w-]+(?:\s+[\w-]+)*)\s*$")


def _segments(body):
    """Split the body into prose runs and ``:::`` containers.

    An unclosed container runs to the end of the file rather than raising --
    the same forgiveness as the rest of the subset.
    """
    segs, buf, names = [], [], None
    for line in body.splitlines():
        s = line.strip()
        if names is None:
            m = _CONTAINER_OPEN.match(s)
            if m:
                segs.append(("md", None, "\n".join(buf)))
                buf, names = [], m.group(1).split()
                continue
        elif s == ":::":
            segs.append(("band", names, "\n".join(buf)))
            buf, names = [], None
            continue
        buf.append(line)
    segs.append(("band", names, "\n".join(buf)) if names else ("md", None, "\n".join(buf)))
    return [s for s in segs if s[2].strip()]


def _render_band(names, text, ctx):
    """A ``:::`` container: intro blocks, then one item per ``###``."""
    kind, mods = names[0], names[1:]
    chunks = re.split(r"(?m)^(?=### )", text.strip())
    intro = chunks[0] if not chunks[0].startswith("### ") else ""
    items = [c for c in chunks if c.startswith("### ")]

    rendered = []
    for item in items:
        head, _, rest = item.partition("\n")
        title = _inline(head[4:].strip())
        inner = "\n".join(_render_block(b, ctx) for b in _blocks(rest))
        if kind == "faq":
            rendered.append('<details class="item"><summary>%s</summary>'
                            '<div class="item__body">%s</div></details>' % (title, inner))
        else:
            rendered.append('<div class="item"><h3>%s</h3>%s</div>' % (title, inner))

    classes = " ".join(["band", "band--" + kind] + ["band--" + m for m in mods])
    out = ['<section class="%s">' % classes, '<div class="wrap">']
    if intro.strip():
        out.append('<div class="band__intro">%s</div>'
                   % "\n".join(_render_block(b, ctx) for b in _blocks(intro)))
    if rendered:
        out.append('<div class="band__items">%s</div>' % "\n".join(rendered))
    out += ["</div>", "</section>"]
    return "\n".join(out)


def _render_blocks(body, videos, ctx=None):
    """Render a page body. Unrecognised input becomes a paragraph.

    Runs of ordinary prose are wrapped in a readable measure; containers and
    full-bleed directives break out of it to span the page.
    """
    ctx = dict(ctx or {}, videos=videos)
    parts, prose = [], []

    def flush():
        if prose:
            parts.append('<div class="wrap prose">\n%s\n</div>' % "\n".join(prose))
            prose.clear()

    for kind, names, text in _segments(body):
        if kind == "band":
            flush()
            parts.append(_render_band(names, text, ctx))
            continue
        for block in _blocks(text):
            if _FULL_BLEED.fullmatch(block):
                flush()
                parts.append(_render_block(block, ctx))
            else:
                prose.append(_render_block(block, ctx))
    flush()
    return "\n".join(parts)


def _render_video(slug, videos):
    """A video slot. Renders a labelled placeholder until the film exists."""
    meta = videos.get(slug)
    if not meta or not meta.get("src"):
        label = (meta or {}).get("working_title", slug.replace("-", " "))
        return (
            '<figure class="video video--pending" role="group" '
            'aria-label="Video not yet available">\n'
            '  <div class="video__slot">\n'
            '    <span class="video__play" aria-hidden="true"></span>\n'
            '    <p class="video__title">%s</p>\n'
            '    <p class="video__note">PLACEHOLDER &mdash; film in production.</p>\n'
            '  </div>\n'
            '</figure>' % html.escape(label))

    poster = ' poster="%s"' % html.escape(meta["poster"]) if meta.get("poster") else ""
    caption = ("<figcaption>%s</figcaption>" % _inline(meta["caption"])
               if meta.get("caption") else "")
    return (
        '<figure class="video">\n'
        '  <video controls preload="metadata"%s>\n'
        '    <source src="%s" type="video/mp4">\n'
        '    Your browser does not support embedded video.\n'
        '  </video>\n'
        '  %s\n'
        '</figure>' % (poster, html.escape(meta["src"]), caption))


def split_hero(body):
    """Peel the leading ``# heading`` and what follows it off the body.

    The hero is a distinct typographic region, not just the first heading in a
    wall of prose -- that separation is most of what makes the page read as
    designed rather than as a document. The lede may end in a ``->`` button
    row. Everything from the first ``##``, directive or container onward stays
    in the body.
    """
    blocks = re.split(r"\n\s*\n", body.strip())
    heading, lede = "", []
    i = 0
    if i < len(blocks) and blocks[i].strip().startswith("# "):
        heading = blocks[i].strip()[2:].strip()
        i += 1
        while i < len(blocks):
            b = blocks[i].strip()
            if b.startswith("#") or b.startswith("[") or b.startswith(":::"):
                break
            lede.append(b)
            i += 1
    return heading, lede, "\n\n".join(blocks[i:])


# The round-table mark (assets/mark.svg), with the reader's seat in copper.
_MARK_SVG = (
    '<svg class="cta__mark" viewBox="0 0 40 40" aria-hidden="true">'
    '<circle cx="20" cy="20" r="9" fill="currentColor"/>'
    '<g fill="currentColor" opacity=".45">'
    '<circle cx="20" cy="4.5" r="2.6"/><circle cx="31" cy="9" r="2.6"/>'
    '<circle cx="35.5" cy="20" r="2.6"/><circle cx="31" cy="31" r="2.6"/>'
    '<circle cx="9" cy="31" r="2.6"/><circle cx="4.5" cy="20" r="2.6"/>'
    '<circle cx="9" cy="9" r="2.6"/></g>'
    '<circle cx="20" cy="35.5" r="3" fill="#e0814e"/></svg>')

_CTAS = {
    "join": (
        "cta--join",
        "Your seat is already saved",
        "Membership is free. You get the library, the tools, a short monthly "
        "briefing, and a standing invitation to the roundtables. Nobody will "
        "call you because you joined.",
        ("/join/", "Claim your seat"), ("/library/", "Keep reading first")),
    "hand": (
        "cta--contact",
        "Ready when you are. Not before.",
        "When you want to talk about what comes next for your practice, raise "
        "your hand. You will hear back from a person in Lincoln, not a sales "
        "queue, and the first conversation commits you to nothing.",
        ("/raise-your-hand/", "Raise your hand"), ("/story/", "Read Dan's story")),
    "checklist": (
        "cta--checklist",
        "How ready is your practice, really?",
        "Twelve plain questions, about four minutes, and an honest picture of "
        "what would need doing before anyone else could run your firm.",
        ("/tools/readiness/", "Take the readiness check"), None),
}
_CTAS["contact"] = _CTAS["hand"]


def _render_cta(kind):
    spec = _CTAS.get(kind)
    if not spec:
        return '<!-- unknown cta: %s -->' % html.escape(kind)
    cls, title, body, primary, secondary = spec
    buttons = '<a class="button" href="%s">%s</a>' % primary
    if secondary:
        buttons += '<a class="button button--ghost" href="%s">%s</a>' % secondary
    return (
        '<aside class="cta %s">\n'
        '  <div class="wrap cta__inner">\n'
        '    %s\n'
        '    <h2>%s</h2>\n'
        '    <p>%s</p>\n'
        '    <p class="actions">%s</p>\n'
        '  </div>\n'
        '</aside>' % (cls, _MARK_SVG, html.escape(title), html.escape(body), buttons))


def _render_partial(name):
    """Interactive markup (tools, forms) that does not belong in copy."""
    path = PARTIALS_DIR / ("%s.html" % name)
    if not path.exists():
        return '<!-- unknown partial: %s -->' % html.escape(name)
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# the library
# --------------------------------------------------------------------------

def collect_library(site):
    """Every article in content/library/, newest-first within declared order."""
    prefix = site.get("path_prefix", "").rstrip("/")
    cats = site.get("library_categories", {})
    articles = []
    if not LIBRARY_DIR.exists():
        return articles
    for path in sorted(LIBRARY_DIR.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        meta, body = parse_front_matter(raw)
        slug = "library/" + path.stem
        cat = meta.get("category", "")
        articles.append({
            "slug": slug,
            "url": "%s/%s/" % (prefix, slug),
            "root_url": "/%s/" % slug,
            "content_path": path,
            "raw": raw,
            "title": meta.get("title") or path.stem,
            "description": meta.get("description", ""),
            "category": cat,
            "category_label": cats.get(cat, {}).get("label", cat.title()),
            "read_time": meta.get("read_time", ""),
            "featured": meta.get("featured", "").lower() in ("yes", "true"),
            "order": int(meta.get("order", "100")),
            "layout": "article",
            "schema_type": meta.get("schema_type", "Article"),
            "eyebrow": cats.get(cat, {}).get("label", "From the library"),
            "status": meta.get("status", "final"),
            "in_nav": False,
            "body_md": body,
        })
    articles.sort(key=lambda a: (a["order"], a["title"]))
    return articles


def _card(a):
    meta = html.escape(a["read_time"]) if a["read_time"] else "Read"
    return (
        '<a class="card card--%s" href="%s" data-cat="%s">'
        '<span class="card__cat">%s</span>'
        '<span class="card__title">%s</span>'
        '<span class="card__desc">%s</span>'
        '<span class="card__meta">%s <span class="card__arrow" aria-hidden="true">&rarr;</span></span>'
        '</a>' % (html.escape(a["category"]), html.escape(a["root_url"]),
                  html.escape(a["category"]), html.escape(a["category_label"]),
                  html.escape(a["title"]), html.escape(a["description"]), meta))


def _render_library(kind, ctx):
    articles = ctx.get("library", [])
    current = ctx.get("current")
    if kind == "featured":
        chosen = [a for a in articles if a["featured"]][:3] or articles[:3]
        return '<div class="cards">%s</div>' % "".join(_card(a) for a in chosen)
    if kind == "related":
        others = [a for a in articles if a["slug"] != (current or {}).get("slug")]
        same = [a for a in others if a["category"] == (current or {}).get("category")]
        chosen = (same + [a for a in others if a not in same])[:3]
        return '<div class="cards">%s</div>' % "".join(_card(a) for a in chosen)
    if kind == "all":
        # Filtering is CSS-only (radio inputs + :has()), so the page still
        # ships no executable script (D-024). Without :has() every card shows.
        cats = ctx.get("categories", {})
        chips = ['<input type="radio" name="topic" id="topic-all" checked>'
                 '<label for="topic-all">Everything</label>']
        for key, c in cats.items():
            chips.append('<input type="radio" name="topic" id="topic-%s">'
                         '<label for="topic-%s">%s</label>'
                         % (html.escape(key), html.escape(key), html.escape(c["label"])))
        return (
            '<section class="band band--library"><div class="wrap">'
            '<div class="library" data-count="%d">'
            '<fieldset class="filters"><legend>Show</legend>%s</fieldset>'
            '<div class="cards cards--all">%s</div>'
            '</div></div></section>'
            % (len(articles), "".join(chips), "".join(_card(a) for a in articles)))
    return '<!-- unknown library view: %s -->' % html.escape(kind)


# --------------------------------------------------------------------------
# page assembly
# --------------------------------------------------------------------------

def load_site_config(path=SITE_CONFIG):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _structured_data(page, site):
    """JSON-LD. Search engines use it; it costs nothing to emit correctly."""
    data = {
        "@context": "https://schema.org",
        "@type": page.get("schema_type", "WebPage"),
        "name": page["title"],
        "description": page["description"],
        "url": site["base_url"].rstrip("/") + page["url"],
        "publisher": {
            "@type": "Organization",
            "name": site["organization"],
            "url": site["base_url"],
        },
    }
    if page.get("schema_type") == "Article":
        data["headline"] = page["title"]
    return json.dumps(data, indent=2)


def render_page(page, site, template, nav_html):
    prefix = (site.get("path_prefix", "").rstrip("/") or "")
    out = template
    replacements = {
        "{{eyebrow}}": html.escape(page.get("eyebrow", "")),
        "{{heading}}": page.get("heading_html") or html.escape(page["title"]),
        "{{lede}}": page.get("lede_html", ""),
        "{{hero_visual}}": page.get("hero_visual_html", ""),
        "{{hero_meta}}": page.get("hero_meta_html", ""),
        "{{layout}}": html.escape(page.get("layout", "page")),
        "{{page_class}}": html.escape(page["slug"].replace("/", "-")),
        "{{footer_nav}}": page.get("footer_nav", ""),
        "{{draft_notice}}": page.get("draft_notice", ""),
        "{{title}}": html.escape(page["title"]),
        "{{description}}": html.escape(page["description"]),
        "{{canonical}}": html.escape(site["base_url"].rstrip("/") + page["url"]),
        "{{organization}}": html.escape(site["organization"]),
        "{{program}}": html.escape(site.get("program_name", site["organization"])),
        "{{body}}": page["body_html"],
        "{{nav}}": nav_html,
        "{{structured_data}}": _structured_data(page, site),
        "{{stylesheet}}": html.escape(prefix + "/styles.css"),
        "{{assets}}": html.escape(prefix + "/assets"),
        "{{root}}": html.escape(prefix),
        "{{canonical_origin}}": html.escape(site["base_url"].rstrip("/")),
        "{{home}}": html.escape(prefix + "/"),
        "{{build_date}}": date.today().isoformat(),
        "{{year}}": str(date.today().year),
    }
    for token, value in replacements.items():
        out = out.replace(token, value)
    return out


def _is_current(nav_slug, current_slug):
    return current_slug == nav_slug or current_slug.startswith(nav_slug + "/")


def _nav_html(pages, current_slug, tools=()):
    items = []
    for p in pages:
        if not p.get("in_nav", True):
            continue
        aria = ' aria-current="page"' if _is_current(p["slug"], current_slug) else ""
        items.append('<li><a href="%s"%s>%s</a></li>'
                     % (html.escape(p["url"]), aria, html.escape(p.get("nav_label") or p["title"])))
    for t in tools:
        aria = ' aria-current="page"' if t["slug"] == current_slug else ""
        items.append('<li class="nav__tool"><a href="%s"%s>%s</a></li>'
                     % (html.escape(t["url"]), aria, html.escape(t["label"])))
    return "<ul>%s</ul>" % "".join(items)


def collect_local_tools(site, local):
    """Internal convenience links, included ONLY in --local preview builds.

    These point at working tools that hold confidential data -- the prospect
    dashboard lists named firms with phone numbers and readiness scores. A
    production build must never emit them, never link them, and never put them
    in the sitemap. Returning [] unless ``local`` is the whole guard, and
    tests/test_build.py asserts it.
    """
    if not local:
        return []
    prefix = site.get("path_prefix", "").rstrip("/")
    tools = []
    for entry in site.get("local_tools", []):
        src = MICROSITE_ROOT.parent / entry["source"]
        if not src.exists():
            print("  skipping local tool %r -- source not found: %s" % (entry["slug"], src))
            continue
        tools.append({
            "slug": entry["slug"],
            "label": entry["label"],
            "url": "%s/%s/" % (prefix, entry["slug"]),
            "source_path": src,
        })
    return tools


def collect_pages(site):
    """Read every content file named in site.json, in declared order."""
    pages = []
    for entry in site["pages"]:
        path = CONTENT_DIR / entry["content"]
        if not path.exists():
            raise SystemExit("Missing content file: %s (declared in site.json)" % path)
        raw = path.read_text(encoding="utf-8")
        meta, body = parse_front_matter(raw)

        slug = entry["slug"]
        prefix = site.get("path_prefix", "").rstrip("/")
        page = {
            "slug": slug,
            "url": (prefix + "/") if slug == "index" else "%s/%s/" % (prefix, slug),
            "content_path": path,
            "raw": raw,
            "title": meta.get("title") or entry.get("title") or slug,
            "description": meta.get("description", ""),
            "nav_label": meta.get("nav_label") or entry.get("nav_label"),
            "in_nav": entry.get("in_nav", True),
            "schema_type": meta.get("schema_type", entry.get("schema_type", "WebPage")),
            "eyebrow": meta.get("eyebrow", ""),
            "layout": meta.get("layout", "page"),
            "hero_visual": meta.get("hero_visual", ""),
            "status": meta.get("status", "final"),
            "body_md": body,
        }
        pages.append(page)
    return pages


def _sitemap(pages, site):
    urls = "".join(
        "  <url><loc>%s</loc></url>\n"
        % html.escape(site["base_url"].rstrip("/") + p["url"]) for p in pages)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            '%s</urlset>\n' % urls)


def find_placeholders(pages):
    """Every place real content is still owed. Drives --check and the build report."""
    found = []
    for p in pages:
        for i, line in enumerate(p["raw"].splitlines(), 1):
            if PLACEHOLDER_TOKEN in line:
                found.append((p["content_path"].name, i, line.strip()))
    return found


def partial_sources():
    """Partials as placeholder-scannable records: forms are wired here."""
    if not PARTIALS_DIR.exists():
        return []
    return [{"raw": p.read_text(encoding="utf-8"), "content_path": p}
            for p in sorted(PARTIALS_DIR.glob("*.html"))]


def _render_hero(p, prefix):
    """Fill the hero tokens: heading, lede (which may end in buttons), visual."""
    heading, lede, rest = split_hero(p["body_md"])
    p["heading_html"] = _inline(heading) if heading else html.escape(p["title"])
    lede_parts = []
    for block in lede:
        if _is_actions(block):
            lede_parts.append(_render_actions(block))
        else:
            lede_parts.append('<p class="hero__lede">%s</p>' % _inline(block.replace("\n", " ")))
    if not lede and p.get("layout") == "article" and p["description"]:
        lede_parts.append('<p class="hero__lede">%s</p>' % html.escape(p["description"]))
    p["lede_html"] = prefix_links("\n".join(lede_parts), prefix)

    p["hero_visual_html"] = ""
    if p.get("hero_visual"):
        p["hero_visual_html"] = prefix_links(
            '<div class="hero__visual">%s</div>' % _render_partial("hero-" + p["hero_visual"]),
            prefix)

    p["hero_meta_html"] = ""
    if p.get("layout") == "article":
        bits = [b for b in (p.get("read_time"), "From the library") if b]
        p["hero_meta_html"] = '<p class="hero__meta">%s</p>' % " &middot; ".join(
            html.escape(b) for b in bits)
    return rest


def build(check_only=False, local=False):
    site = load_site_config()
    local_build = local
    if local:
        # Preview at a server root: the mount prefix is what differs between
        # a /succession path and a subdomain, so it is the only thing to strip.
        site["path_prefix"] = ""
    prefix = site.get("path_prefix", "").rstrip("/")
    pages = collect_pages(site)
    library = collect_library(site)
    everything = pages + library
    videos = site.get("videos", {})
    categories = site.get("library_categories", {})

    for p in everything:
        rest = _render_hero(p, prefix)
        ctx = {"library": library, "current": p, "categories": categories}
        if p.get("layout") == "article":
            rest += ("\n\n::: related\n^ Keep reading\n\n## More from the library\n\n"
                     "[library:related]\n:::\n\n[cta:join]")
        p["body_html"] = prefix_links(_render_blocks(rest, videos, ctx), prefix)

    placeholders = find_placeholders(everything + partial_sources())

    if check_only:
        print("Content files: %d pages, %d library articles" % (len(pages), len(library)))
        if placeholders:
            print("\nPlaceholders still awaiting real content (%d):" % len(placeholders))
            for name, line_no, text in placeholders:
                print("  %s:%d  %s" % (name, line_no, text[:90]))
        else:
            print("\nNo placeholders -- all copy is real.")
        drafts = [p["content_path"].name for p in everything if p["status"] == "draft"]
        if drafts:
            print("\nPages still marked status: draft (%d): %s"
                  % (len(drafts), ", ".join(drafts)))

        pending = [s for s, v in videos.items() if not v.get("src")]
        if pending:
            print("\nVideo slots with no file yet (%d): %s" % (len(pending), ", ".join(pending)))
        return 0

    template = (SRC_DIR / "template.html").read_text(encoding="utf-8")
    if DIST_DIR.exists():
        # Pages get renamed; a stale page left in dist/ would otherwise deploy.
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)

    tools = collect_local_tools(site, local_build)

    footer_nav = "".join('<li><a href="%s">%s</a></li>'
                         % (html.escape(q["url"]),
                            html.escape(q.get("nav_label") or q["title"]))
                         for q in pages if q.get("in_nav", True))

    show_draft = site.get("show_draft_notice", True)

    for p in everything:
        nav = _nav_html(pages, p["slug"], tools)
        p["footer_nav"] = footer_nav
        p["draft_notice"] = ""
        if show_draft and p["status"] == "draft":
            p["draft_notice"] = (
                '<div class="draft"><strong>Draft</strong>'
                'Working copy for review. Wording, forms and videos are not final '
                'and nothing here has had compliance review.</div>')
        out_html = render_page(p, site, template, nav)
        if p["slug"] == "index":
            out_path = DIST_DIR / "index.html"
        else:
            out_path = DIST_DIR / p["slug"] / "index.html"
            out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out_html, encoding="utf-8")
        print("built %s -> %s" % (p["content_path"].name, out_path.relative_to(MICROSITE_ROOT)))

    for t in tools:
        # Copied verbatim: these are standalone tools with their own styling,
        # not microsite pages. A banner is injected so it is unmistakable that
        # the page is internal and which build produced it.
        raw = t["source_path"].read_text(encoding="utf-8")
        banner = (
            '<div style="position:sticky;top:0;z-index:99;background:#7a2318;color:#fff;'
            'font:600 13px/1.4 -apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;'
            'padding:10px 16px;text-align:center">'
            'INTERNAL &mdash; confidential prospect data. Local preview build only; '
            'never published. <a href="%s" style="color:#fff">&larr; back to the site</a>'
            '</div>' % html.escape(prefix + "/"))
        marker = "<body>"
        raw = (raw.replace(marker, marker + "\n" + banner, 1) if marker in raw
               else banner + raw)
        tool_path = DIST_DIR / t["slug"] / "index.html"
        tool_path.parent.mkdir(parents=True, exist_ok=True)
        tool_path.write_text(raw, encoding="utf-8")
        print("built %s (INTERNAL, local only) -> %s"
              % (t["source_path"].name, tool_path.relative_to(MICROSITE_ROOT)))

    # Ship assets/ (icons, fonts, social image). Generator scripts are build
    # tools, not site content -- keep them out of the output.
    if ASSETS_DIR.exists():
        for src in sorted(ASSETS_DIR.rglob("*")):
            if src.is_file() and src.suffix.lower() != ".py" and not src.name.startswith("."):
                dest = DIST_DIR / "assets" / src.relative_to(ASSETS_DIR)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(src.read_bytes())
        print("assets copied")

    (DIST_DIR / "styles.css").write_text(
        (SRC_DIR / "styles.css").read_text(encoding="utf-8"), encoding="utf-8")
    (DIST_DIR / "sitemap.xml").write_text(_sitemap(everything, site), encoding="utf-8")
    (DIST_DIR / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n"
        % site["base_url"].rstrip("/"), encoding="utf-8")

    if not site.get("path_prefix") and local_build:
        print("\nNOTE: --local build. Paths are rooted for preview and canonical URLs omit "
              "the mount prefix -- do NOT deploy this output.")

    print("\n%d pages + %d articles, %d placeholder line(s) remaining."
          % (len(pages), len(library), len(placeholders)))
    if placeholders:
        print("Run --check to list them. Do NOT launch with placeholders present.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build The Owner's Table microsite")
    ap.add_argument("--check", action="store_true",
                    help="report outstanding placeholders and video slots; build nothing")
    ap.add_argument("--local", action="store_true",
                    help="build with an empty path prefix, for previewing at a server root")
    args = ap.parse_args(argv)
    return build(check_only=args.check, local=args.local)


if __name__ == "__main__":
    sys.exit(main())
