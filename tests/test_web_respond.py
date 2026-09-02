"""Answering a blocked agent pane from the web app: the two paths and what each has to carry.

The relay refuses a `respond` whose prompt_id is not the one the pane is showing, and a missing
one never matches -- question_prompt_id hashes the screen even when it detects no question. So a
button that sends no prompt_id is a button that does nothing, silently: the relay's error reply
is deliberately not rendered. Typed free text has the further problem that `respond` only carries
it where the relay can drive a question; anywhere else it is refused, and the text has to go in
through send_text instead.

Skipped, not failed, when playwright or a chromium build is missing.
"""
import unittest

from test_web_shell import PAGE, PHONE, _agent, _chrome, sync_playwright

# One browser for the file, for the reason spelled out in test_web_keys.py.
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


REFUSED = "free-text response requires a detected question"

SNAPSHOT = {
    "type": "agents",
    "agents": [_agent(
        "wE:pB", "wE", "wE:t1", status="blocked", prompt_id="p-1", interaction="prompt",
        multi=False, multi_options=[], selected_options=[],
        options=["yes, single permission", "trust, always allow", "no (tab to edit)"],
    )],
    "spaces": {
        "workspaces": [{"workspace_id": "wE", "label": "api", "number": 1, "focused": True,
                        "tab_count": 1, "pane_count": 1, "host": "local"}],
        "tabs": [{"tab_id": "wE:t1", "workspace_id": "wE", "label": "1", "number": 1,
                  "focused": True, "pane_count": 1, "host": "local"}],
    },
    "panes": [],
}


@unittest.skipIf(sync_playwright is None, "playwright is not installed")
@unittest.skipIf(_chrome() is None, "no chromium build available")
class WebRespondTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = _shared["browser"].new_page(viewport=PHONE)
        cls.page.goto(PAGE)

    @classmethod
    def tearDownClass(cls):
        cls.page.close()

    def setUp(self):
        self.page.evaluate("""s => {
          activeWorkspace = null; activeTab = null;
          handleMessage(s);
          openTerminal('wE:pB');
          window.__sent = [];
          ws = {readyState: 1, send: p => window.__sent.push(JSON.parse(p))};
        }""", SNAPSHOT)

    def sent(self):
        """Everything but the mirror's own reads, which are not the point here."""
        return [m for m in self.page.evaluate("window.__sent")
                if m["type"] not in ("read_pane", "get_history")]

    def type_and_send(self, text):
        self.page.evaluate("""t => {
          document.getElementById('termInput').value = t;
          sendText();
        }""", text)

    def test_a_quick_action_carries_the_prompt_id(self):
        self.page.eval_on_selector("#quickActions button", "b => b.click()")
        self.assertEqual(self.sent(), [
            {"type": "respond", "pane_id": "wE:pB", "prompt_id": "p-1", "text": "yes, single permission"}])

    def test_typed_text_the_relay_refuses_is_typed_into_the_pane_instead(self):
        self.type_and_send("explain first")
        self.assertEqual(self.sent(), [
            {"type": "respond", "pane_id": "wE:pB", "prompt_id": "p-1", "text": "explain first"}])
        self.page.evaluate("m => handleMessage(m)", {"type": "error", "message": REFUSED})
        # send_text and nothing after it: Enter on a multi-select toggles a row, not submits.
        self.assertEqual(self.sent()[1:], [
            {"type": "send_text", "pane_id": "wE:pB", "text": "explain first"}])

    def test_a_refusal_with_nothing_pending_types_nothing(self):
        """A button press after typed text, or any other error, must not replay stale text."""
        self.type_and_send("explain first")
        self.page.eval_on_selector("#quickActions button", "b => b.click()")
        self.page.evaluate("m => handleMessage(m)", {"type": "error", "message": REFUSED})
        self.assertEqual([m["type"] for m in self.sent()], ["respond", "respond"])


if __name__ == "__main__":
    unittest.main()
