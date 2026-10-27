import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import core  # noqa: E402
import updater  # noqa: E402
import whatsapp  # noqa: E402


class WhatsAppTests(unittest.TestCase):
    def test_numbers(self):
        w = whatsapp.wa_number
        for raw in ("0555 444 55 44", "05554445544", "555 444 55 44", "5554445544",
                    "+90 555 444 55 44", "90 555 444 55 44", "0090 555 444 55 44", "(0555) 444-5544"):
            self.assertEqual(w(raw), "905554445544", raw)
        self.assertEqual(w("+49 151 1234 5678"), "4915112345678")
        self.assertEqual(w("0212 555 11 22"), "")   # sabit hat
        self.assertEqual(w("123"), "")
        self.assertEqual(w(""), "")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = core.Store(os.path.join(self.tmp.name, "t.db"))
        self.rec = self.s.all_records()[0]

    def tearDown(self):
        self.s.close()
        self.tmp.cleanup()

    def test_options_and_template(self):
        opts = whatsapp.phone_options(self.s, self.rec)
        self.assertEqual([n for _l, n in opts], ["905554445544"])
        self.assertEqual(whatsapp.fill_template("Merhaba {ad}! {Ad Soyad} / {tam_ad}", self.s, self.rec),
                         "Merhaba Ahmet! Ahmet Yalın / Ahmet Yalın")

    def test_sensitive_never_in_message(self):
        out = whatsapp.fill_template("TC: {tc_kimlik_no}", self.s, self.rec)
        self.assertNotIn("12345678901", out)
        self.assertEqual(out, "TC: {tc_kimlik_no}")

    def test_urls(self):
        web, app = whatsapp.urls("905554445544", "Merhaba Ahmet, görüşelim & konuşalım")
        self.assertTrue(web.startswith("https://wa.me/905554445544?text=Merhaba%20Ahmet"))
        self.assertIn("%26", web)
        self.assertTrue(app.startswith("whatsapp://send?phone=905554445544&text="))
        self.assertEqual(whatsapp.urls("905554445544", "")[0], "https://wa.me/905554445544")

    def test_multiple_numbers_in_cell(self):
        cid = self.rec["category_id"]
        f = {x["name"]: str(x["id"]) for x in self.s.fields(cid)}
        rid = self.s.add_record(cid, {f["Ad Soyad"]: "Çift Hatlı",
                                      f["Telefon"]: "0532 111 22 33 / 0212 555 11 22 / 0544 999 88 77"})
        opts = whatsapp.phone_options(self.s, self.s.get_record(rid))
        self.assertEqual([n for _l, n in opts], ["905321112233", "905449998877"])


class UpdaterTests(unittest.TestCase):
    def test_versions(self):
        self.assertTrue(updater.is_newer("1.10.0", "1.9.3"))
        self.assertTrue(updater.is_newer("v1.2.1", "1.2.0"))
        self.assertFalse(updater.is_newer("1.2.0", "1.2.0"))
        self.assertFalse(updater.is_newer("1.1.9", "1.2.0"))

    def test_repo(self):
        self.assertTrue(updater.valid_repo("ali/isletme-paneli"))
        for bad in ("", "ali", "ali/x/y", "https://github.com/a/b", "a b/c"):
            self.assertFalse(updater.valid_repo(bad), bad)

    def test_bat_and_host_check(self):
        bat = updater.make_bat(r"C:\x y\a.exe.new", r"C:\x y\a.exe")
        self.assertIn('move /y "C:\\x y\\a.exe.new" "C:\\x y\\a.exe"', bat)
        self.assertIn('start "" "C:\\x y\\a.exe"', bat)
        with self.assertRaises(ValueError):
            updater._download("http://evil.example/a.exe", "x")
        with self.assertRaises(RuntimeError):
            updater.install_update({})


if __name__ == "__main__":
    unittest.main()
