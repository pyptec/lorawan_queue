"""Browser regressions with synthetic transport only; no I2C or production data."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
HAS_BROWSER = importlib.util.find_spec("playwright") is not None and CHROME.is_file()


@unittest.skipUnless(HAS_BROWSER, "Requires existing Playwright and local Chrome; no hardware")
class UPSFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(executable_path=str(CHROME), headless=True)
        except Exception:
            cls.playwright.stop()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width":1366,"height":768})
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.add_init_script("window.WebSocket=class {constructor(){window.testSocket=this;} close(){if(this.onclose)this.onclose();}};")
        def route(request):
            path = request.request.url.removeprefix("http://dashboard.test")
            files = {"/": ROOT / "dashboard/templates/index.html"}
            if path.startswith("/static/"):
                candidate = (ROOT / "dashboard" / path.lstrip("/")).resolve()
                if candidate.is_relative_to(ROOT / "dashboard/static"):
                    files[path] = candidate
            file = files.get(path)
            if file and file.is_file():
                request.fulfill(path=str(file))
            else:
                request.abort()
        self.page.route("**/*", route)
        self.page.goto("http://dashboard.test/")
        self.page.wait_for_function("window.testSocket && typeof window.testSocket.onmessage === 'function'")
        self.page.evaluate("testSocket.onopen()")

    def tearDown(self):
        try:
            self.assertEqual(self.errors, [])
        finally:
            self.page.close()

    def send(self, ups):
        self.page.evaluate("ups=>testSocket.onmessage({data:JSON.stringify({ups,queue:{state:'UNKNOWN',rows:[]},devices:[],services:[]})})", ups)

    def card(self):
        return self.page.locator("#cards .kpi").filter(has=self.page.locator(".kpi-top", has_text="UPS"))

    def test_ok_without_sample_timestamp_renders_percent(self):
        self.send({"state":"OK","battery_percent":72,"battery_state":"OK","charge_state":"IDLE"})
        self.assertIn("72 %", self.card().inner_text())
        self.assertNotIn("UNKNOWN", self.card().inner_text())
        self.assertIn("72 %", self.page.locator("#ups-overview").inner_text())
        self.assertNotIn("UPS no disponible", self.page.locator("#ups-detail").inner_text())

    def test_unknown_and_missing_remain_unknown(self):
        for sample in ({"state":"UNKNOWN","battery_percent":72}, None, {}):
            with self.subTest(sample=sample):
                self.send(sample)
                self.assertIn("UNKNOWN", self.card().inner_text())
                self.assertNotIn("72 %", self.card().inner_text())
                self.assertIn("UPS no disponible", self.page.locator("#ups-detail").inner_text())

    def test_websocket_close_degrades_last_ok_sample(self):
        self.send({"state":"OK","battery_percent":72,"battery_state":"OK","charge_state":"IDLE"})
        self.page.evaluate("testSocket.onclose()")
        self.assertIn("UNKNOWN", self.card().inner_text())
        self.assertNotIn("72 %", self.card().inner_text())
        self.assertEqual(self.page.locator("#connection").get_attribute("data-state"), "STALE")
        self.assertIn("UPS no disponible", self.page.locator("#ups-detail").inner_text())

    def test_clock_skew_past_and_future_does_not_hide_ok_ups(self):
        for timestamp in (946684800, 4102444800):
            with self.subTest(sampled_at=timestamp):
                self.send({"state":"OK","battery_percent":72,"battery_state":"OK","charge_state":"IDLE","sampled_at":timestamp})
                self.assertIn("72 %", self.card().inner_text())
                self.assertEqual(self.card().get_attribute("data-state"), "OK")
                self.assertNotIn("UPS no disponible", self.page.locator("#ups-detail").inner_text())
