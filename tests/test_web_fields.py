"""Where the session view is placed, and what a focused field costs.

Focusing any control under 16px zooms iOS Safari, and the zoom does not undo on blur. Once
magnified the 390px layout is wider than the visual viewport, which reads as a broken layout and
is not one. So 16px is a floor on every focusable field.

The placement half is about `top`. It is written for the phone, where the view is `position:
fixed`; the desktop branch turns it `relative` and there `top` no longer places the box, it
offsets it -- leaving an empty band the height of the header and pushing the same distance off
the bottom of the page. That one is measured in a browser, because the symptom is a scrollbar.
"""
import re
import unittest

from web_source import web_source
from test_web_shell import PAGE, _agent, _chrome, sync_playwright

DESKTOP = {"width": 1280, "height": 900}

_shared = {}


def setUpModule():  # noqa: N802 - unittest's own name
    if sync_playwright is None or _chrome() is None:
        return
    _shared["playwright"] = sync_playwright().start()
    _shared["browser"] = _shared["playwright"].chromium.launch(executable_path=_chrome())


def tearDownModule():  # noqa: N802 - unittest's own name
    if "browser" in _shared:
        _shared["browser"].close()
        _shared["playwright"].stop()
    _shared.clear()


def rule_body(page, selector):
    # `^\s*` rather than `^`: rules inside a media query are indented.
    match = re.search(r"(?m)^\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", page)
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
        self.assertIn("overflow-x: hidden", rule_body(self.page, "body"))
        self.assertIn("overscroll-behavior: none", rule_body(self.page, "body"))

    def test_the_root_element_is_never_made_a_scroll_container(self):
        """`overflow` on <html> stops the property propagating to the viewport and makes the root
        a scroller instead. On iOS that changes what a fixed box is laid out against, and the
        session view stops short of the bottom of the screen. Whatever the sideways-pan fix is,
        it is not this."""
        self.assertNotRegex(rule_body(self.page, "html"), r"overflow")


@unittest.skipIf(sync_playwright is None, "playwright is not installed")
@unittest.skipIf(_chrome() is None, "no chromium build available")
class DesktopPlacementTests(unittest.TestCase):
    """The desktop branch makes the view `position: relative`, where the `top` written for the
    phone's fixed box stops placing it and starts offsetting it. Both halves of that show up
    here: the band it leaves behind in the flow, and the page it outgrows."""

    @classmethod
    def setUpClass(cls):
        cls.page = _shared["browser"].new_page(viewport=DESKTOP)
        cls.page.goto(PAGE)

    @classmethod
    def tearDownClass(cls):
        cls.page.close()

    def setUp(self):
        self.page.evaluate("""s => {
          activeWorkspace = null; activeTab = null;
          handleMessage(s);
          openTerminal('wE:pH');
          handleMessage({type:'pane_content', pane_id:'wE:pH',
                         content: Array(120).fill('line of output').join('\\n')});
        }""", {
            "type": "agents",
            "agents": [_agent("wE:pH", "wE", "wE:t1", status="working")],
            "spaces": {
                "workspaces": [{"workspace_id": "wE", "label": "api", "number": 1, "focused": True,
                                "tab_count": 1, "pane_count": 1, "host": "local"}],
                "tabs": [{"tab_id": "wE:t1", "workspace_id": "wE", "label": "1", "number": 1,
                          "focused": True, "pane_count": 1, "host": "local"}],
            },
            "panes": [],
        })

    def test_the_session_view_starts_where_the_header_ends(self):
        gap = self.page.evaluate(
            """() => Math.round(document.querySelector('.terminal-view').getBoundingClientRect().top
                              - document.querySelector('.header').getBoundingClientRect().bottom)""")
        self.assertEqual(gap, 0, f"{gap}px of nothing between the header and the session view")

    def test_opening_a_session_does_not_give_the_page_a_scrollbar(self):
        overflow = self.page.evaluate(
            "() => Math.round(document.documentElement.scrollHeight - window.innerHeight)")
        self.assertLessEqual(overflow, 0, f"the page outgrows the viewport by {overflow}px")


if __name__ == "__main__":
    unittest.main()
