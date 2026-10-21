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

    def test_join_and_hand(self):
        self.assertIn('href="/join/"', build._render_blocks("[cta:join]", {}))
        self.assertIn('href="/raise-your-hand/"', build._render_blocks("[cta:hand]", {}))

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
        for name in ("icon-32.png", "icon-180.png", "icon-512.png", "og.png"):
            self.assertTrue((build.ASSETS_DIR / name).exists(), "missing %s" % name)

    def test_icons_are_real_pngs(self):
        for name in ("icon-32.png", "icon-180.png", "icon-512.png"):
            head = (build.ASSETS_DIR / name).read_bytes()[:8]
            self.assertEqual(head, b"\x89PNG\r\n\x1a\n", "%s is not a PNG" % name)

    def test_fonts_are_self_hosted_with_their_licences(self):
        """No third-party font request from a regulated public site (D-022)."""
        fonts = build.ASSETS_DIR / "fonts"
        self.assertTrue(list(fonts.glob("*.woff2")))
        self.assertTrue(list(fonts.glob("OFL-*.txt")))
        css = (build.SRC_DIR / "styles.css").read_text(encoding="utf-8")
        tpl = (build.SRC_DIR / "template.html").read_text(encoding="utf-8")
        for text in (css, tpl):
            self.assertNotIn("fonts.googleapis", text)
            self.assertNotIn("fonts.gstatic", text)

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


class TestBands(unittest.TestCase):
    """``:::`` containers break out of the prose measure into full-width bands."""

    def r(self, md):
        return build._render_blocks(md, {})

    def test_container_renders_a_band_with_intro_and_items(self):
        out = self.r("::: pillars dark\n## Heading\n\nIntro\n\n### One\n\nBody one\n\n### Two\n\nBody two\n:::")
        self.assertIn('class="band band--pillars band--dark"', out)
        self.assertIn('<div class="band__intro"><h2>Heading</h2>', out)
        self.assertEqual(out.count('<div class="item">'), 2)

    def test_faq_items_are_native_disclosures(self):
        out = self.r("::: faq\n### Question?\n\nAnswer.\n:::")
        self.assertIn("<details", out)
        self.assertIn("<summary>Question?</summary>", out)

    def test_prose_around_a_band_is_wrapped_separately(self):
        out = self.r("Before\n\n::: tiles\n### X\n:::\n\nAfter")
        self.assertEqual(out.count('class="wrap prose"'), 2)
        self.assertLess(out.index("Before"), out.index("band--tiles"))
        self.assertLess(out.index("band--tiles"), out.index("After"))

    def test_unclosed_container_runs_to_the_end_rather_than_raising(self):
        out = self.r("::: tiles\n### Item\n\ntext")
        self.assertIn("band--tiles", out)
        self.assertIn("text", out)

    def test_eyebrow_and_buttons(self):
        out = self.r("^ Label\n\n-> [Primary](/a/)\n-> [Second](/b/)")
        self.assertIn('<p class="eyebrow">Label</p>', out)
        self.assertIn('<a class="button" href="/a/">Primary</a>', out)
        self.assertIn('<a class="button button--ghost" href="/b/">Second</a>', out)

    def test_ordered_list(self):
        self.assertIn("<ol><li>one</li><li>two</li></ol>", self.r("1. one\n2. two"))


class TestLinksAndQuotes(unittest.TestCase):
    def test_root_relative_links_get_the_mount_prefix(self):
        out = build.prefix_links('<a href="/library/">x</a><img src="/assets/a.png">', "/succession")
        self.assertIn('href="/succession/library/"', out)
        self.assertIn('src="/succession/assets/a.png"', out)

    def test_external_and_protocol_relative_links_are_untouched(self):
        out = build.prefix_links('<a href="https://x.com/">x</a><a href="//cdn/">y</a>', "/succession")
        self.assertIn('href="https://x.com/"', out)
        self.assertIn('href="//cdn/"', out)

    def test_no_prefix_is_a_no_op(self):
        self.assertEqual(build.prefix_links('<a href="/x/">', ""), '<a href="/x/">')

    def test_smart_quotes_never_touch_link_targets(self):
        out = build._inline('"Owner\'s" [guide](/library/x/)')
        self.assertIn("\u201cOwner\u2019s\u201d", out)
        self.assertIn('href="/library/x/"', out)


class TestLibrary(unittest.TestCase):
    def setUp(self):
        self.site = build.load_site_config()
        self.articles = build.collect_library(self.site)

    def test_articles_are_collected_with_categories_the_site_knows(self):
        self.assertTrue(self.articles)
        cats = set(self.site["library_categories"])
        for a in self.articles:
            self.assertIn(a["category"], cats, a["content_path"].name)
            self.assertTrue(a["description"], a["content_path"].name)

    def test_every_category_has_a_css_filter_rule(self):
        """Filtering is CSS-only; a category without a rule could never be isolated."""
        css = (build.SRC_DIR / "styles.css").read_text(encoding="utf-8")
        for key in self.site["library_categories"]:
            self.assertIn("#topic-%s:checked" % key, css)

    def test_featured_view_shows_at_most_three(self):
        out = build._render_library("featured", {"library": self.articles})
        self.assertLessEqual(out.count('class="card '), 3)

    def test_related_view_excludes_the_current_article(self):
        cur = self.articles[0]
        out = build._render_library("related", {"library": self.articles, "current": cur})
        self.assertNotIn('href="%s"' % cur["root_url"], out)

    def test_internal_links_in_copy_resolve_to_real_pages(self):
        """A renamed page or article must not leave dead links behind."""
        pages = build.collect_pages(self.site)
        known = {"/"} | {"/%s/" % p["slug"] for p in pages} | {a["root_url"] for a in self.articles}
        sources = [p["raw"] for p in pages + self.articles]
        sources += [s["raw"] for s in build.partial_sources()]
        sources += [(build.SRC_DIR / "template.html").read_text(encoding="utf-8").replace("{{root}}", "")]
        sources += [str(v) for v in build._CTAS.values()]
        for text in sources:
            for target in re.findall(r'(?:\]\(|href="|\(")(/[\w/-]*)', text):
                if target.startswith("//"):
                    continue
                self.assertIn(target, known, "dead internal link: %s" % target)


class TestPartials(unittest.TestCase):
    def test_partials_carry_no_executable_script(self):
        """D-024 extends to partials: no <script> and no inline handlers."""
        for p in build.partial_sources():
            self.assertNotIn("<script", p["raw"], p["content_path"].name)
            self.assertIsNone(re.search(r"\son[a-z]+=", p["raw"]), p["content_path"].name)

    def test_unwired_forms_are_reported_as_placeholders(self):
        found = build.find_placeholders(build.partial_sources())
        names = {f[0] for f in found}
        self.assertIn("claim-form.html", names)
        self.assertIn("hand-form.html", names)

    def test_unknown_partial_is_a_comment_not_a_crash(self):
        self.assertIn("<!-- unknown partial", build._render_blocks("[partial:nope]", {}))


class TestButtonsKeepTheirColours(unittest.TestCase):
    """A contextual link rule like ``.prose a`` (0-1-1) outranks ``.button``
    (0-1-0), which once turned buttons in body copy copper-on-copper --
    invisible. Every link-colour rule must exclude buttons."""

    def test_link_colour_rules_exclude_buttons(self):
        css = re.sub(r"/\*.*?\*/", "", (build.SRC_DIR / "styles.css").read_text(encoding="utf-8"), flags=re.S)
        for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
            if not re.search(r"(^|;)\s*color\s*:", body):
                continue
            for sel in selectors.split(","):
                sel = sel.strip()
                if re.search(r"(^|\s)a(:hover)?$", sel) and ".nav" not in sel and "inherit" not in body:
                    self.fail("link colour rule may restyle buttons: %r" % sel)


class TestRealContentBuilds(unittest.TestCase):
    """The committed content must actually build -- catches a broken site.json."""

    def test_build_check_runs_clean(self):
        self.assertEqual(build.build(check_only=True), 0)


if __name__ == "__main__":
    unittest.main()
