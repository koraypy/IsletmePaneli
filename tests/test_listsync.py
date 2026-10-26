import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import core  # noqa: E402
import listsync  # noqa: E402


def make_xlsx(path, rows):
    """Excel'in yaptığı gibi: metinler sharedStrings'te, sayılar düz sayı."""
    shared, sheet_rows = [], []
    for ri, row in enumerate(rows, 1):
        cells = []
        for ci, v in enumerate(row):
            ref = "ABCDEFGH"[ci] + str(ri)
            if isinstance(v, (int, float)):
                cells.append(f'<c r="{ref}"><v>{v}</v></c>')
            else:
                if v not in shared:
                    shared.append(v)
                cells.append(f'<c r="{ref}" t="s"><v>{shared.index(v)}</v></c>')
        sheet_rows.append(f'<row r="{ri}">{"".join(cells)}</row>')
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/workbook.xml",
                   f'<workbook {ns} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                   '<sheets><sheet name="S1" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/sharedStrings.xml",
                   f'<sst {ns}>' + "".join(f"<si><t>{s}</t></si>" for s in shared) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml",
                   f'<worksheet {ns}><sheetData>{"".join(sheet_rows)}</sheetData></worksheet>')


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = core.Store(os.path.join(self.tmp.name, "t.db"))
        self.cid = self.s.categories()[0]["id"]
        self.f = {f["name"]: f["id"] for f in self.s.fields(self.cid)}
        # ikinci mevcut kişi (listede olmayacak)
        self.s.add_record(self.cid, {str(self.f["Ad Soyad"]): "Zeynep Acar",
                                     str(self.f["Telefon"]): "0532 000 11 22"})
        self.mapping = {self.f["Ad Soyad"]: "Ad", self.f["Telefon"]: "Tel", self.f["Görev"]: "Görev"}

    def tearDown(self):
        self.s.close()
        self.tmp.cleanup()

    def run_xlsx(self, rows):
        p = os.path.join(self.tmp.name, "l.xlsx")
        make_xlsx(p, [["Ad", "Tel", "Görev"]] + rows)
        headers, data = listsync.read_table(p)
        self.assertEqual(headers, ["Ad", "Tel", "Görev"])
        return listsync.compare(self.s, self.cid, data, self.mapping, self.f["Telefon"])

    def test_phone_formats_match(self):
        # Excel başındaki 0'ı atmış sayı, +90'lı ve boşluklu biçim: hepsi Ahmet
        for tel in (5554445544, "+90 555 444 55 44", "0555-444-5544"):
            res = self.run_xlsx([["Ahmet Yalın", tel, ""]])
            self.assertEqual(len(res["new"]), 0, tel)
            self.assertEqual(len(res["same"]), 1, tel)

    def test_new_changed_missing(self):
        res = self.run_xlsx([
            ["Ahmet Yalın", "0555 444 55 44", "Muhasebe"],   # aynı kişi, yeni görev bilgisi
            ["Mehmet Kaya", "0533 111 22 33", "Şoför"],       # yeni
            ["Telefonsuz Kişi", "", "x"],                      # anahtar yok
            ["Mehmet Kaya (2)", "0533 111 22 33", "x"],       # listede tekrar
        ])
        self.assertEqual([i["title"] for i in res["new"]], ["Mehmet Kaya"])
        self.assertEqual(len(res["changed"]), 1)
        self.assertEqual(res["changed"][0]["diffs"][0][1], "Görev")
        self.assertEqual([i["title"] for i in res["missing"]], ["Zeynep Acar"])
        self.assertEqual(len(res["nokey"]), 1)
        self.assertEqual(len(res["dup"]), 1)

    def test_apply(self):
        res = self.run_xlsx([["Ahmet Yalın", "0555 444 55 44", "Muhasebe"],
                             ["Mehmet Kaya", "0533 111 22 33", "Şoför"]])
        self.assertEqual(listsync.add_new(self.s, self.cid, res["new"]), 1)
        self.assertEqual(listsync.apply_changes(self.s, res["changed"]), 1)
        again = self.run_xlsx([["Ahmet Yalın", "0555 444 55 44", "Muhasebe"],
                               ["Mehmet Kaya", "0533 111 22 33", "Şoför"]])
        self.assertEqual((len(again["new"]), len(again["changed"]), len(again["same"])), (0, 0, 2))
        # TC dokunulmadı
        rec = [r for r in self.s.all_records(self.cid) if "Ahmet" in self.s.title(r)][0]
        self.assertEqual(rec["data"][str(self.f["TC Kimlik No"])], "12345678901")

    def test_blank_in_file_does_not_erase(self):
        res = self.run_xlsx([["Ahmet Yalın", "0555 444 55 44", ""]])
        self.assertEqual(len(res["changed"]), 0)

    def test_csv_semicolon_turkish(self):
        p = os.path.join(self.tmp.name, "l.csv")
        with open(p, "w", encoding="cp1254", newline="") as fh:
            fh.write("Ad;Tel;Görev\nİbrahim Şen;0544 999 88 77;Güvenlik\n")
        headers, rows = listsync.read_table(p)
        res = listsync.compare(self.s, self.cid, rows, self.mapping, self.f["Telefon"])
        self.assertEqual(res["new"][0]["title"], "İbrahim Şen")

    def test_xls_rejected(self):
        with self.assertRaises(ValueError):
            listsync.read_table(os.path.join(self.tmp.name, "a.xls"))


if __name__ == "__main__":
    unittest.main()
