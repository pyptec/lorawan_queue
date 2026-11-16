"""Synthetic alias UI fixtures; no external service or production telemetry."""
import test_ups_frontend as browser_fixture
from dashboard.device_aliases import load_registry


def send_devices(case):
    registry = load_registry()
    devices = [registry.resolve({"identity":identity,"fport":100,"fcnt16":84,"rssi":-87,"lsnr":8.5,"status":"pending","received_at":"2026-11-16T00:00:00+00:00"}) for identity in ("DevEUI:70B3D57ED0079EC3","DevEUI:A84041D1B186E98A","DevAddr:009356D5","DevAddr:ABCDEF12")]
    case.page.evaluate("devices=>testSocket.onmessage({data:JSON.stringify({devices,queue:{state:'OK',rows:[]},services:[]})})",devices)
    return devices



class DeviceAliasFrontendTests(browser_fixture.DashboardBrowserCase):
    def test_names_first_and_technical_fields(self):
        send_devices(self)
        self.page.evaluate("goTo('devices')")
        self.assertEqual(self.page.locator("#devices-table th").first.inner_text().upper(),"NOMBRE")
        for i,name in enumerate(("LILYGO T3S3","Dragino LHT65N","QALCOSONIC W1","DISPOSITIVO NO REGISTRADO")):
            row = self.page.locator("#devices-table tbody tr").nth(i)
            self.assertEqual(row.locator("strong").first.inner_text(),name)
            for technical in ("100","84","-87","8,5"):
                self.assertIn(technical,row.inner_text())
            self.assertIn(name,self.page.locator("#recent-devices").inner_text())
        water = self.page.locator("#devices-table tbody tr").nth(2)
        self.assertIn("009356D5",water.inner_text())
        self.assertIn("DevEUI (config.)",water.inner_text())
        self.assertIn("DevAddr de sesión",water.inner_text())
        self.assertIn("ABCDEF12",self.page.locator("#devices-table tbody tr").nth(3).inner_text())


    def test_responsive_name_stays_visible_in_scroll(self):
        send_devices(self)
        self.page.evaluate("goTo('devices')")
        for width,height in ((1366,768),(900,1000),(390,844),(320,740)):
            self.page.set_viewport_size({"width":width,"height":height})
            self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth<=innerWidth"))
            self.page.locator("#devices-table .scroll").evaluate("e=>e.scrollLeft=300")
            first = self.page.locator("#devices-table tbody tr").first.locator("td").first
            self.assertEqual(first.evaluate("e=>getComputedStyle(e).position"),"sticky")
            box = first.bounding_box()
            self.assertGreater(box["x"]+box["width"],0)
            self.assertLess(box["x"],width)


    def test_alias_text_does_not_inject_html(self):
        malicious = '<img src=x onerror=alert(1)>'
        item = {"registered":True,"name":malicious,"description":malicious,"alias_device_id":malicious,"identity":"DevAddr:ABCDEF12","dev_addr":"ABCDEF12"}
        self.page.evaluate("item=>testSocket.onmessage({data:JSON.stringify({devices:[item],queue:{state:'OK',rows:[]}})})",item)
        self.assertIn(malicious,self.page.locator("#devices-table").inner_text())
        self.assertEqual(self.page.locator("#devices-table img").count(),0)
