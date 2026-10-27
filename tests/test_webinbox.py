import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import core  # noqa: E402
import listsync  # noqa: E402
import webinbox  # noqa: E402
import whatsapp  # noqa: E402

KEY = "k" * 32
A = "a" * 32
B = "b" * 32


class Mock(BaseHTTPRequestHandler):
    """web/api.php sözleşmesinin Python taklidi."""
    items = {}

    def log_message(self, *a):
        pass

    def _send(self, code, data, raw=None):
        body = raw if raw is not None else json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.startswith("/botwall/"):
            return self._send(200, None, raw=b"<html>checking your browser</html>")
        n = int(self.headers.get("Content-Length", 0))
        d = json.loads(self.rfile.read(n))
        if d.get("key") != KEY:
            return self._send(401, {"ok": False, "error": "Anahtar hatalı."})
        a = d.get("action")
        if a == "ping":
            return self._send(200, {"ok": True, "pending": len(self.items), "fields": ["Ad Soyad"]})
        if a == "list":
            return self._send(200, {"ok": True, "items": list(self.items.values())})
        if a == "ack":
            k = 0
            for i in d.get("ids", []):
                if self.items.pop(i, None):
                    k += 1
            return self._send(200, {"ok": True, "deleted": k})
        self._send(400, {"ok": False, "error": "Bilinmeyen işlem."})


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), Mock)
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}/"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        Mock.items = {
            A: {"id": A, "received": "2026-10-27T08:00:00+00:00",
                "fields": {"Ad Soyad": "Ahmet Yalın", "Telefon": "0555 444 55 44", "Görev": "Muhasebe"}},
            B: {"id": B, "received": "2026-10-27T09:00:00+00:00",
                "fields": {"Ad Soyad": "Selin Aksoy", "Telefon": "+90 532 777 66 55", "E-posta": "s@x.com"}},
        }
        self.tmp = tempfile.TemporaryDirectory()
        self.s = core.Store(os.path.join(self.tmp.name, "t.db"))

    def tearDown(self):
        self.s.close()
        self.tmp.cleanup()

    def test_url_helpers(self):
        self.assertEqual(webinbox.base_url("https://a.b/x/api.php"), "https://a.b/x/")
        self.assertEqual(webinbox.base_url("https://a.b"), "https://a.b/")
        self.assertEqual(webinbox.api_url("https://a.b/x"), "https://a.b/x/api.php")
        self.assertTrue(webinbox.valid_url("https://a.b/"))
        self.assertFalse(webinbox.valid_url("http://a.b/"))
        code, key = webinbox.new_keys()
        self.assertRegex(code, r"^[A-Z2-9]{4}-[A-Z2-9]{4}$")
        self.assertGreaterEqual(len(key), 40)

    def test_wrong_key_and_botwall(self):
        with self.assertRaisesRegex(RuntimeError, "Anahtar"):
            webinbox.ping(self.base, "yanlis")
        with self.assertRaisesRegex(RuntimeError, "JSON"):
            webinbox.ping(self.base + "botwall/", KEY)

    def test_full_flow_new_changed_same(self):
        cid = self.s.categories()[0]["id"]  # Personel (Ahmet Yalın, 0555 444 55 44 mevcut)
        self.assertEqual(webinbox.ping(self.base, KEY)["pending"], 2)
        headers, rows = webinbox.to_rows(webinbox.list_items(self.base, KEY))
        f = {x["name"]: x["id"] for x in self.s.fields(cid)}
        mapping = {f[h]: h for h in headers if h in f}
        res = listsync.compare(self.s, cid, rows, mapping, f["Telefon"])
        self.assertEqual([i["title"] for i in res["new"]], ["Selin Aksoy"])
        self.assertEqual(len(res["changed"]), 1)          # Ahmet'in Görev'i yeni
        self.assertEqual(res["changed"][0]["row"]["_id"], A)
        # işle: ekle + güncelle, sonra sunucudan sil
        listsync.add_new(self.s, cid, res["new"])
        listsync.apply_changes(self.s, res["changed"])
        ids = [i["row"]["_id"] for i in res["new"] + res["changed"]]
        self.assertEqual(webinbox.ack(self.base, KEY, ids), 2)
        self.assertEqual(webinbox.ping(self.base, KEY)["pending"], 0)
        self.assertEqual(webinbox.ack(self.base, KEY, ["../etc/passwd", "x"]), 0)  # geçersiz kimlikler atılır

    def test_whatsapp_form_tokens(self):
        rec = self.s.all_records()[0]
        self.s.set_setting("web_url", "https://form.example/")
        self.s.set_setting("web_code", "ABCD-2345")
        out = whatsapp.fill_template(whatsapp.DEFAULT_TEMPLATES["Bilgi formu"], self.s, rec)
        self.assertEqual(out, "Merhaba Ahmet, bilgilerini şu formdan doldurur musun? "
                              "https://form.example/  Davet kodu: ABCD-2345")

    def test_csv_formula_injection(self):
        self.assertEqual(core.csv_safe("=1+1"), "'=1+1")
        self.assertEqual(core.csv_safe("@SUM(A1)"), "'@SUM(A1)")
        self.assertEqual(core.csv_safe("+cmd|' /C calc'!A0"), "'+cmd|' /C calc'!A0")
        self.assertEqual(core.csv_safe("+90 555 444 55 44"), "+90 555 444 55 44")
        self.assertEqual(listsync.csv_safe("Ahmet"), "Ahmet")


if __name__ == "__main__":
    unittest.main()
