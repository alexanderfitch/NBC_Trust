"""Tests for the microsite builder (microsite/build.py)."""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build


class TestFrontMatter(unittest.TestCase):
    def test_parses_keys(self):
        meta, body = build.parse_front_matter(
            "---\ntitle: Hello\ndescription: A page\n---\n\nBody text\n")
        self.assertEqual(meta["title"], "Hello")
        self.assertEqual(meta["description"], "A page")
        self.assertEqual(body.strip(), "Body text")

    def test_no_front_matter_returns_whole_body(self):
        meta, body = build.parse_front_matter("Just a body\n")
        self.assertEqual(meta, {})
        self.assertEqual(body, "Just a body\n")

    def test_values_containing_colons_survive(self):
        meta, _ = build.parse_front_matter("---\ntitle: A: B\n---\nx")
        self.assertEqual(meta["title"], "A: B")


class TestMarkdownSubset(unittest.TestCase):
    def r(self, md, videos=None):
        return build._render_blocks(md, videos or {})

    def test_headings(self):
        self.assertIn("<h1>Title</h1>", self.r("# Title"))
        self.assertIn("<h2>Section</h2>", self.r("## Section"))
        self.assertIn("<h3>Sub</h3>", self.r("### Sub"))

    def test_paragraph_and_soft_wrap_joined(self):
        out = self.r("One line\nand its continuation")
        self.assertIn("<p>One line and its continuation</p>", out)

    def test_list(self):
        out = self.r("- one\n- two")
        self.assertIn("<ul><li>one</li><li>two</li></ul>", out)

    def test_blockquote_joins_lines(self):
        out = self.r("> a quote\n> continued")
        self.assertIn("<blockquote><p>a quote continued</p></blockquote>", out)

    def test_inline_formatting(self):
        out = self.r("**bold** and *italic* and [a link](https://example.com)")
        self.assertIn("<strong>bold</strong>", out)
        self.assertIn("<em>italic</em>", out)
        self.assertIn('<a href="https://example.com">a link</a>', out)

    def test_unrecognised_input_becomes_a_paragraph_not_dropped(self):
        out = self.r("|| weird || syntax ||")
        self.assertIn("<p>", out)
        self.assertIn("weird", out)


class TestEscaping(unittest.TestCase):
    """Copy is human-authored; it must never be able to inject markup."""

    def test_raw_html_in_copy_is_escaped(self):
        out = build._render_blocks("<script>alert(1)</script>", {})
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)

    def test_escaping_happens_before_inline_so_formatting_still_works(self):
        out = build._render_blocks("**bold** <b>raw</b>", {})
        self.assertIn("<strong>bold</strong>", out)
        self.assertIn("&lt;b&gt;", out)


class TestVideoSlots(unittest.TestCase):
    def test_missing_video_renders_a_marked_placeholder(self):
        out = build._render_blocks("[video:dans-decision]",
                                   {"dans-decision": {"working_title": "Dan's decision"}})
        self.assertIn("video--pending", out)
        self.assertIn("Dan&#x27;s decision", out)
        self.assertIn(build.PLACEHOLDER_TOKEN, out)

    def test_unknown_slug_still_renders_a_placeholder(self):
        out = build._render_blocks("[video:not-in-config]", {})
        self.assertIn("video--pending", out)
        self.assertIn("not in config", out)

    def test_present_video_renders_a_real_player(self):
        out = build._render_blocks("[video:x]", {
            "x": {"src": "/a/v.mp4", "poster": "/a/p.jpg", "caption": "A caption"}})
        self.assertIn('<source src="/a/v.mp4"', out)
        self.assertIn('poster="/a/p.jpg"', out)
        self.assertIn("A caption", out)
        self.assertNotIn("video--pending", out)


class TestCTAs(unittest.TestCase):
    def test_checklist_and_contact(self):
        self.assertIn("cta--checklist", build._render_blocks("[cta:checklist]", {}))
        self.assertIn("cta--contact", build._render_blocks("[cta:contact]", {}))

    def test_unknown_cta_is_a_comment_not_a_crash(self):
        out = build._render_blocks("[cta:nope]", {})
        self.assertIn("<!-- unknown cta", out)


class TestPathPrefix(unittest.TestCase):
    """PLAN.md decision #6 -- mount point must be a config change, not a rewrite."""

    def _pages(self, prefix):
        site = {"path_prefix": prefix, "pages": [
            {"slug": "index", "content": "hub.md"},
            {"slug": "story", "content": "case-study.md"},
        ]}
        prefix = site.get("path_prefix", "").rstrip("/")
        return [(p["slug"], (prefix + "/") if p["slug"] == "index"
                 else "%s/%s/" % (prefix, p["slug"])) for p in site["pages"]]

    def test_mounted_under_a_path(self):
        self.assertEqual(self._pages("/succession"),
                         [("index", "/succession/"), ("story", "/succession/story/")])

    def test_mounted_at_a_root(self):
        self.assertEqual(self._pages(""), [("index", "/"), ("story", "/story/")])


class TestPlaceholderDetection(unittest.TestCase):
    def test_finds_every_placeholder_line(self):
        pages = [{"raw": "clean\nPLACEHOLDER one\nclean\nPLACEHOLDER two\n",
                  "content_path": Path("x.md")}]
        found = build.find_placeholders(pages)
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0][1], 2)
        self.assertEqual(found[1][1], 4)

    def test_clean_content_reports_none(self):
        pages = [{"raw": "all real copy\n", "content_path": Path("x.md")}]
        self.assertEqual(build.find_placeholders(pages), [])


class TestLocalToolsNeverShip(unittest.TestCase):
    """The dashboard holds named firms, phone numbers and readiness scores.
    A production build must not emit it, link it, or list it in the sitemap."""

    def _site(self):
        return build.load_site_config()

    def test_production_build_collects_no_tools(self):
        self.assertEqual(build.collect_local_tools(self._site(), local=False), [])

    def test_local_build_does_collect_them(self):
        tools = build.collect_local_tools(self._site(), local=True)
        self.assertTrue(tools, "expected the dashboard tool in a local build")
        self.assertEqual(tools[0]["slug"], "dashboard")

    def test_tools_are_absent_from_production_nav(self):
        pages = [{"slug": "index", "url": "/", "title": "Home", "in_nav": True}]
        nav = build._nav_html(pages, "index", build.collect_local_tools(self._site(), local=False))
        self.assertNotIn("nav__tool", nav)
        self.assertNotIn("dashboard", nav)

    def test_tools_appear_in_local_nav(self):
        pages = [{"slug": "index", "url": "/", "title": "Home", "in_nav": True}]
        nav = build._nav_html(pages, "index", build.collect_local_tools(self._site(), local=True))
        self.assertIn("nav__tool", nav)
        self.assertIn("dashboard", nav)

    def test_sitemap_never_includes_tools(self):
        site = self._site()
        pages = [{"slug": "index", "url": "/succession/"}]
        xml = build._sitemap(pages, site)
        self.assertNotIn("dashboard", xml)

    def test_missing_source_is_skipped_not_fatal(self):
        site = dict(self._site())
        site["local_tools"] = [{"slug": "ghost", "label": "Ghost",
                                "source": "docs/does-not-exist.html"}]
        self.assertEqual(build.collect_local_tools(site, local=True), [])


class TestBrandAssets(unittest.TestCase):
    """Icons and the asset pipeline."""

    def test_icons_exist_at_every_declared_size(self):
        for name in ("icon-32.png", "icon-180.png", "icon-512.png"):
            self.assertTrue((build.ASSETS_DIR / name).exists(), "missing %s" % name)

    def test_icons_are_real_pngs(self):
        for name in ("icon-32.png", "icon-180.png", "icon-512.png"):
            head = (build.ASSETS_DIR / name).read_bytes()[:8]
            self.assertEqual(head, b"\x89PNG\r\n\x1a\n", "%s is not a PNG" % name)

    def test_generator_script_is_not_shipped_as_an_asset(self):
        """make_icons.py needs PIL and is a build tool, not site content."""
        self.assertTrue((build.ASSETS_DIR / "make_icons.py").exists())
        shipped = build.DIST_DIR / "assets" / "make_icons.py"
        self.assertFalse(shipped.exists(), "the generator must not be published")


class TestMotion(unittest.TestCase):
    """Motion must be gated, and must never be able to strand content.

    History worth keeping: this was an IntersectionObserver plus a rescue
    timer, and it stranded content at opacity 0 twice -- once because an
    observer can exist and never fire in a page that is never rendered, and
    again because setTimeout is throttled in exactly those pages, so the rescue
    never ran either. It is now a scroll-driven CSS animation with no script at
    all. These tests exist to stop that regressing.
    """

    def _css(self):
        return (build.SRC_DIR / "styles.css").read_text(encoding="utf-8")

    def _template(self):
        return (build.SRC_DIR / "template.html").read_text(encoding="utf-8")

    def test_reduced_motion_block_exists(self):
        self.assertIn("prefers-reduced-motion: reduce", self._css())

    def test_reduced_motion_disables_view_transitions(self):
        css = self._css()
        block = css[css.index("prefers-reduced-motion: reduce"):]
        self.assertIn("navigation: none", block)

    def test_reveal_is_hidden_only_inside_a_support_query(self):
        """The whole safety argument: the hidden state may only exist where the
        engine that reveals it is known to run."""
        css = self._css()
        i = css.index("@keyframes reveal-in")
        self.assertIn("opacity: 0", css[i:i + 200])

        supports = css.index("@supports (animation-timeline: view())")
        applied = css.index("animation-timeline: view();", supports)
        self.assertGreater(applied, supports)
        self.assertIn("prefers-reduced-motion: no-preference",
                      css[supports:applied])

    def test_reveal_uses_a_cover_range_not_entry(self):
        """An element taller than the viewport never fully 'enters', so an
        entry-based range can strand a long quote or video part-way."""
        css = self._css()
        i = css.index("animation-range:")
        line = css[i:css.index(";", i)]
        self.assertIn("cover", line)
        self.assertNotIn("entry", line)

    def test_no_executable_javascript_on_the_page(self):
        """No script means no observer to miss and no timer to throttle."""
        t = self._template()
        scripts = re.findall(r'<script[^>]*>', t)
        for tag in scripts:
            self.assertIn("application/ld+json", tag,
                          "unexpected executable script: %s" % tag)

    def test_no_leftover_js_reveal_hooks(self):
        """Comments are stripped first -- the design history is written down in
        them on purpose, and mentioning the old approach is not a stale hook."""
        css = re.sub(r"/\*.*?\*/", "", self._css(), flags=re.S)
        tpl = re.sub(r"<!--.*?-->", "", self._template(), flags=re.S)
        for needle in ("js-reveal", "IntersectionObserver", "is-in"):
            self.assertNotIn(needle, css, "stale hook in CSS: %s" % needle)
            self.assertNotIn(needle, tpl, "stale hook in template: %s" % needle)


class TestRealContentBuilds(unittest.TestCase):
    """The committed content must actually build -- catches a broken site.json."""

    def test_build_check_runs_clean(self):
        self.assertEqual(build.build(check_only=True), 0)


if __name__ == "__main__":
    unittest.main()
