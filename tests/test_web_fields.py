"""Two iOS Safari behaviours the stylesheet has to hold the line against.

Focusing any control under 16px zooms the page, and the zoom does not undo on blur. Once
magnified, the 390px layout is wider than the visual viewport: the input row's buttons sit
off-screen and the page drags sideways, both of which read as layout bugs and are not. So 16px
is a floor on every focusable field, and the document is pinned against sideways movement on
<html>, which is the viewport scroller -- overflow-x on <body> alone does not hold.

Source-text checks, on purpose: what breaks here is a number someone lowers to make a row
tidier, and a regex catches that without a browser.
"""
import re
import unittest

from web_source import web_source


def rule_body(page, selector):
    match = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", page)
    if not match:
        raise AssertionError(f"no `{selector} {{ ... }}` rule")
    return match.group(1)


class FieldTests(unittest.TestCase):
    def setUp(self):
        self.page = web_source()

    def test_focusable_fields_never_drop_below_16px(self):
        field_rule = re.compile(r"(?m)^[^\n{}]*\b(?:input|select|textarea)\b[^\n{}]*\{([^}]*)\}")
        checked = 0
        for body in field_rule.findall(self.page):
            declared = re.search(r"font-size:\s*([\d.]+)(px|rem)", body)
            if not declared:
                continue
            checked += 1
            size = float(declared.group(1)) * (16 if declared.group(2) == "rem" else 1)
            self.assertGreaterEqual(size, 16, f"field under 16px: {body.strip()[:70]}")
        self.assertGreater(checked, 0, "no field font-size rules matched; selector drifted")

        # The command palette's search box is styled inline, out of reach of any rule above.
        inline = re.search(r'id="cmdSearch"[^>]*font-size:\s*([\d.]+)px', self.page)
        self.assertIsNotNone(inline, "#cmdSearch lost its inline font-size")
        self.assertGreaterEqual(float(inline.group(1)), 16)

    def test_page_itself_never_pans_sideways(self):
        html = rule_body(self.page, "html")
        self.assertIn("overflow-x: hidden", html)
        self.assertIn("overscroll-behavior: none", html)
        self.assertIn("overscroll-behavior: none", rule_body(self.page, "body"))


if __name__ == "__main__":
    unittest.main()
