"""Synthetic confirmed sessions/flow fixtures; never physical associations."""
import test_ups_frontend as browser_fixture
import test_device_sessions as fixture
from dashboard import device_sessions, device_aliases


def send(case, items=None, registry=None):
    if items is None:
        items, registry=fixture.three_devices()
    rows, summary=device_sessions.consolidate(items,device_aliases.load_registry(),registry or device_sessions.SessionRegistry(),now=fixture.NOW)
    payload={"devices":rows,"device_summary":summary,"queue":{"state":"OK","rows":[],"summary":{"pending":0,"sent":1150}},"services":[{"name":"ttn-gateway.service","ActiveState":"active","state":"OK"}],"internet":{"state":"ONLINE"},"gateway":{"rak5146":{"state":"UNKNOWN"},"ttn":{"state":"ONLINE","ack_age_seconds":1}}}
    case.page.evaluate("payload=>testSocket.onmessage({data:JSON.stringify(payload)})",payload)
    return payload


class SessionFrontendTests(browser_fixture.DashboardBrowserCase):
    def test_kpi_three_devices_not_five_sessions_and_history_visible(self):
        send(self)
        card=self.page.locator("#cards .kpi").filter(has=self.page.locator(".kpi-top",has_text="Equipos consolidados"))
        self.assertEqual(card.locator(".kpi-value").inner_text(),"3")
        self.assertIn("8 identidades",card.inner_text())
        self.assertEqual(self.page.locator("#devices-table tbody tr").count(),3)
        self.assertIn("DevAddr anteriores",self.page.locator("#devices-table").inner_text())

    def test_flow_active_devices_forwarder_without_rf_claim(self):
        send(self)
        steps=self.page.locator("#operational-flow .flow-step")
        self.assertIn("3 ACTIVOS",steps.nth(0).inner_text())
        self.assertIn("Último uplink:",steps.nth(0).inner_text())
        self.assertIn("FORWARDER ACTIVE",steps.nth(1).inner_text())
        self.assertIn("RF: NO VERIFICADO",steps.nth(1).inner_text())
        self.assertNotIn("RF OK",steps.nth(1).inner_text())
        self.assertIn("0 Pending",steps.nth(2).inner_text())
        self.assertIn("1.150 Sent",steps.nth(2).inner_text())
        self.assertIn("ONLINE",steps.nth(3).inner_text())

    def test_unknown_addresses_stay_visible_and_are_not_physical_count(self):
        send(self,[fixture.observation("DevAddr:260CB888"),fixture.observation("DevAddr:260CA3CA")])
        first=self.page.locator("#operational-flow .flow-step").first
        self.assertIn("2 IDENTIDADES RECIENTES",first.inner_text())
        self.assertIn("DevAddr",first.inner_text())
        self.assertEqual(self.page.locator("#devices-table tbody tr").count(),2)
        self.assertIn("DISPOSITIVO NO REGISTRADO",self.page.locator("#devices-table").inner_text())

    def test_old_data_observed_not_active_and_join_not_last_uplink(self):
        send(self,[fixture.observation("DevAddr:ABCDEF12",ago=500),fixture.observation("DevEUI:"+fixture.LILY,join=True,ago=1)])
        first=self.page.locator("#operational-flow .flow-step").first
        self.assertIn("IDENTIDADES OBSERVADAS",first.inner_text())
        self.assertNotIn("ACTIVOS",first.inner_text())
        self.assertIn("DevAddr ABCDEF12",first.inner_text())

    def test_stale_does_not_claim_active_forwarder(self):
        send(self)
        self.page.evaluate("testSocket.onclose()")
        text=self.page.locator("#operational-flow").inner_text()
        self.assertNotIn("3 ACTIVOS",text)
        self.assertNotIn("FORWARDER ACTIVE",text)
        self.assertIn("NO VERIFICADO",text)

    def test_responsive_flow_and_devices(self):
        send(self)
        for width,height in ((1366,768),(900,1000),(390,844),(320,740)):
            self.page.set_viewport_size({"width":width,"height":height})
            for section in ("overview","devices"):
                self.page.evaluate("section=>goTo(section)",section)
                self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth<=innerWidth"),(width,section))
