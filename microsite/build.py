"""Static site builder for the NBC Trust succession microsite.

Stdlib only, matching the data-engine's constraint (D-005): no pip, no build
toolchain, runs anywhere, and a solo maintainer can read the whole thing.

Design (D-019):
- **Copy lives in ``content/*.md``, markup lives in ``src/template.html``.**
  Sam owns the former and never has to touch HTML; I own the latter. This is
  the whole reason the builder exists -- integrating real copy later is an
  edit to a markdown file, not a rebuild of the page.
- Every page's copy is a versioned file in git, which is also PLAN.md Stage
  F1's public-asset-versioning requirement satisfied for free.
- Output goes to ``dist/`` and is NOT committed; it is generated.
- The markdown subset is deliberately small (see ``_render_blocks``). A
  hand-rolled parser is only defensible if it stays small, so anything it
  does not recognise is emitted as a paragraph rather than silently dropped.

Run:  python3 microsite/build.py            # builds to microsite/dist/
      python3 microsite/build.py --check    # report placeholders, build nothing
"""

import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

MICROSITE_ROOT = Path(__file__).resolve().parent
CONTENT_DIR = MICROSITE_ROOT / "content"
SRC_DIR = MICROSITE_ROOT / "src"
DIST_DIR = MICROSITE_ROOT / "dist"
SITE_CONFIG = MICROSITE_ROOT / "site.json"

# Copy still awaiting Sam is marked with this token so `--check` can find it
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


def _inline(text):
    """Escape, then apply the inline subset. Escaping first is deliberate:
    copy is authored by humans and must never be able to inject markup."""
    out = html.escape(text, quote=False)
    for pattern, repl in _INLINE:
        out = pattern.sub(repl, out)
    return out


def _render_blocks(body, videos):
    """Render the markdown subset. Unrecognised input becomes a paragraph."""
    parts = []
    for block in re.split(r"\n\s*\n", body.strip()):
        block = block.strip()
        if not block:
            continue

        # [video:slug] -- an embed slot, resolved against site.json
        m = re.fullmatch(r"\[video:([\w-]+)\]", block)
        if m:
            parts.append(_render_video(m.group(1), videos))
            continue

        # [cta:checklist] / [cta:contact]
        m = re.fullmatch(r"\[cta:([\w-]+)\]", block)
        if m:
            parts.append(_render_cta(m.group(1)))
            continue

        if block.startswith("### "):
            parts.append("<h3>%s</h3>" % _inline(block[4:].strip()))
        elif block.startswith("## "):
            parts.append("<h2>%s</h2>" % _inline(block[3:].strip()))
        elif block.startswith("# "):
            parts.append("<h1>%s</h1>" % _inline(block[2:].strip()))
        elif all(l.strip().startswith("- ") for l in block.splitlines()):
            items = "".join("<li>%s</li>" % _inline(l.strip()[2:])
                            for l in block.splitlines())
            parts.append("<ul>%s</ul>" % items)
        elif all(l.strip().startswith("> ") for l in block.splitlines()):
            quote = " ".join(l.strip()[2:] for l in block.splitlines())
            parts.append("<blockquote><p>%s</p></blockquote>" % _inline(quote))
        else:
            parts.append("<p>%s</p>" % _inline(block.replace("\n", " ")))
    return "\n".join(parts)


def _render_video(slug, videos):
    """A video slot. Renders a labelled placeholder until Drew delivers."""
    meta = videos.get(slug)
    if not meta or not meta.get("src"):
        label = (meta or {}).get("working_title", slug.replace("-", " "))
        return (
            '<figure class="video video--pending" role="group" '
            'aria-label="Video not yet available">\n'
            '  <div class="video__slot">\n'
            '    <span class="video__badge">Video slot</span>\n'
            '    <p class="video__title">%s</p>\n'
            '    <p class="video__note">PLACEHOLDER &mdash; awaiting final edit from Drew.</p>\n'
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


def _render_cta(kind):
    if kind == "checklist":
        return (
            '<aside class="cta cta--checklist">\n'
            '  <h2>The succession checklist</h2>\n'
            '  <p>A practical starting point &mdash; the questions worth answering '
            'before you talk to anyone.</p>\n'
            '  <a class="button" href="#checklist-form">Get the checklist</a>\n'
            '</aside>')
    if kind == "contact":
        return (
            '<aside class="cta cta--contact">\n'
            '  <h2>Start a conversation</h2>\n'
            '  <p>No pitch and no obligation &mdash; a conversation about what '
            'you want the end of your practice to look like.</p>\n'
            '  <a class="button button--quiet" href="#contact-form">Reach out directly</a>\n'
            '</aside>')
    return '<!-- unknown cta: %s -->' % html.escape(kind)


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
    return json.dumps(data, indent=2)


def render_page(page, site, template, nav_html):
    out = template
    replacements = {
        "{{title}}": html.escape(page["title"]),
        "{{description}}": html.escape(page["description"]),
        "{{canonical}}": html.escape(site["base_url"].rstrip("/") + page["url"]),
        "{{organization}}": html.escape(site["organization"]),
        "{{body}}": page["body_html"],
        "{{nav}}": nav_html,
        "{{structured_data}}": _structured_data(page, site),
        "{{stylesheet}}": html.escape((site.get("path_prefix", "").rstrip("/") or "") + "/styles.css"),
        "{{home}}": html.escape((site.get("path_prefix", "").rstrip("/") or "") + "/"),
        "{{build_date}}": date.today().isoformat(),
        "{{year}}": str(date.today().year),
    }
    for token, value in replacements.items():
        out = out.replace(token, value)
    return out


def _nav_html(pages, current_slug):
    items = []
    for p in pages:
        if not p.get("in_nav", True):
            continue
        aria = ' aria-current="page"' if p["slug"] == current_slug else ""
        items.append('<li><a href="%s"%s>%s</a></li>'
                     % (html.escape(p["url"]), aria, html.escape(p.get("nav_label", p["title"]))))
    return "<ul>%s</ul>" % "".join(items)


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


def build(check_only=False, local=False):
    site = load_site_config()
    local_build = local
    if local:
        # Preview at a server root: the mount prefix is what differs between
        # a /succession path and a subdomain, so it is the only thing to strip.
        site["path_prefix"] = ""
    pages = collect_pages(site)
    videos = site.get("videos", {})

    for p in pages:
        p["body_html"] = _render_blocks(p["body_md"], videos)

    placeholders = find_placeholders(pages)

    if check_only:
        print("Content files: %d" % len(pages))
        if placeholders:
            print("\nPlaceholders still awaiting real content (%d):" % len(placeholders))
            for name, line_no, text in placeholders:
                print("  %s:%d  %s" % (name, line_no, text[:90]))
        else:
            print("\nNo placeholders -- all copy is real.")
        pending = [s for s, v in videos.items() if not v.get("src")]
        if pending:
            print("\nVideo slots with no file yet (%d): %s" % (len(pending), ", ".join(pending)))
        return 0

    template = (SRC_DIR / "template.html").read_text(encoding="utf-8")
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    for p in pages:
        nav = _nav_html(pages, p["slug"])
        out_html = render_page(p, site, template, nav)
        if p["slug"] == "index":
            out_path = DIST_DIR / "index.html"
        else:
            out_path = DIST_DIR / p["slug"] / "index.html"
            out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out_html, encoding="utf-8")
        print("built %s -> %s" % (p["content_path"].name, out_path.relative_to(MICROSITE_ROOT)))

    (DIST_DIR / "styles.css").write_text(
        (SRC_DIR / "styles.css").read_text(encoding="utf-8"), encoding="utf-8")
    (DIST_DIR / "sitemap.xml").write_text(_sitemap(pages, site), encoding="utf-8")
    (DIST_DIR / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n"
        % site["base_url"].rstrip("/"), encoding="utf-8")

    if not site.get("path_prefix") and local_build:
        print("\nNOTE: --local build. Paths are rooted for preview and canonical URLs omit "
              "the mount prefix -- do NOT deploy this output.")

    print("\n%d pages, %d placeholder line(s) remaining." % (len(pages), len(placeholders)))
    if placeholders:
        print("Run --check to list them. Do NOT launch with placeholders present.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the NBC Trust succession microsite")
    ap.add_argument("--check", action="store_true",
                    help="report outstanding placeholders and video slots; build nothing")
    ap.add_argument("--local", action="store_true",
                    help="build with an empty path prefix, for previewing at a server root")
    args = ap.parse_args(argv)
    return build(check_only=args.check, local=args.local)


if __name__ == "__main__":
    sys.exit(main())
