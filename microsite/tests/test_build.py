"""Tests for the microsite builder (microsite/build.py)."""

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


class TestRealContentBuilds(unittest.TestCase):
    """The committed content must actually build -- catches a broken site.json."""

    def test_build_check_runs_clean(self):
        self.assertEqual(build.build(check_only=True), 0)


if __name__ == "__main__":
    unittest.main()
