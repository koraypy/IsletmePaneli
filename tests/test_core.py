import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import core  # noqa: E402


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = core.Store(os.path.join(self.tmp.name, "t.db"))

    def tearDown(self):
        self.s.close()
        self.tmp.cleanup()

    def names(self, q, cid=None):
        res, _ = self.s.search(q, cid)
        return [self.s.title(r) for r, _ in res]

    def test_seed_and_example(self):
        self.assertEqual([c["name"] for c in self.s.categories()][0], "Personel")
        self.assertEqual(self.names("ahmet"), ["Ahmet Yalın"])

    def test_turkish_case_and_accents(self):
        for q in ("AHMET YALIN", "ahmet yalın", "YALIN", "ahmet'in", "AHMET'İN"):
            self.assertEqual(self.names(q), ["Ahmet Yalın"], q)

    def test_phone_and_tc(self):
        for q in ("0555 444 55 44", "05554445544", "555 444", "12345678901", "444 55"):
            self.assertEqual(self.names(q), ["Ahmet Yalın"], q)

    def test_typo(self):
        self.assertEqual(self.names("ahmt"), ["Ahmet Yalın"])

    def test_no_false_positive(self):
        self.assertEqual(self.names("zeynep"), [])

    def test_natural_language_answer(self):
        res, hints = self.s.search("Ahmet'in telefon numarası")
        ans = self.s.offline_answer(res, hints)
        self.assertIn("0555 444 55 44", ans)

    def test_sensitive_not_revealed_in_answer(self):
        res, hints = self.s.search("ahmet tc")
        ans = self.s.offline_answer(res, hints)
        self.assertNotIn("12345678901", ans)
        self.assertIn("gizli", ans)

    def test_sensitive_not_sent_to_ai(self):
        res, _ = self.s.search("ahmet")
        ctx = "\n".join(self.s.context_lines([r for r, _ in res]))
        self.assertNotIn("12345678901", ctx)
        self.assertIn("0555", ctx)

    def test_field_name_alone_lists_all(self):
        self.assertEqual(self.names("telefon"), ["Ahmet Yalın"])

    def test_category_and_field_management(self):
        cid = self.s.add_category("Araç", ["Plaka", ("Ruhsat No", "text", 0)])
        fid = self.s.add_field(cid, "Sigorta Bitiş", "text", 0)
        by = {f["name"]: str(f["id"]) for f in self.s.fields(cid)}
        self.s.add_record(cid, {by["Plaka"]: "34 ABC 123", by["Sigorta Bitiş"]: "01.01.2027"})
        self.assertEqual(self.names("34 abc"), ["34 ABC 123"])
        self.s.update_field(fid, name="Sigorta Tarihi")
        self.assertIn("Sigorta Tarihi", [f["name"] for f in self.s.fields(cid)])
        self.s.delete_field(fid)
        self.assertEqual(self.names("2027"), [])
        with self.assertRaises(ValueError):
            self.s.add_category("araç")
        self.s.delete_category(cid)
        self.assertEqual(self.names("34 abc"), [])

    def test_quick_add(self):
        cid, data = self.s.parse_quick_add("+ Personel | Mehmet Kaya | 0532 111 22 33")
        self.s.add_record(cid, data)
        self.assertEqual(self.names("kaya"), ["Mehmet Kaya"])
        self.assertEqual(self.names("0532 111 22 33"), ["Mehmet Kaya"])
        cid, data = self.s.parse_quick_add("+ pers | Telefon=0500 000 00 00 | Ad Soyad=Ayşe Demir")
        self.s.add_record(cid, data)
        self.assertEqual(self.names("ayse"), ["Ayşe Demir"])
        with self.assertRaises(ValueError):
            self.s.parse_quick_add("+ Yokkategori | x")

    def test_export_import_roundtrip(self):
        p = os.path.join(self.tmp.name, "e.json")
        self.s.export_json(p)
        s2 = core.Store(os.path.join(self.tmp.name, "t2.db"))
        try:
            # ikinci veritabanını boşalt
            for c in s2.categories():
                s2.delete_category(c["id"])
            n = s2.import_json(p)
            self.assertEqual(n, 1)
            res, _ = s2.search("ahmet")
            self.assertEqual(len(res), 1)
        finally:
            s2.close()

    def test_csv_and_backup(self):
        cid = self.s.categories()[0]["id"]
        p = os.path.join(self.tmp.name, "x.csv")
        self.s.export_csv(p, cid)
        with open(p, encoding="utf-8-sig") as fh:
            self.assertIn("Ahmet Yalın", fh.read())
        b = os.path.join(self.tmp.name, "b.db")
        self.s.backup(b)
        self.assertTrue(os.path.getsize(b) > 0)

    def test_move_field(self):
        cid = self.s.categories()[0]["id"]
        first = self.s.fields(cid)[0]["id"]
        self.s.move_field(first, +1)
        self.assertEqual(self.s.fields(cid)[1]["id"], first)


if __name__ == "__main__":
    unittest.main()
