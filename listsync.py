"""Excel/CSV listesini panelle karşılaştırma (yalnızca standart kütüphane).

- .xlsx dosyaları zipfile+XML ile okunur (openpyxl gerekmez).
- Kişiler TELEFON ile eşleştirilir: son 10 hane karşılaştırılır, böylece
  "0555 444 55 44", "+90 555 444 55 44" ve Excel'in başındaki 0'ı attığı
  "5554445544" aynı numara sayılır.
"""
import csv
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from decimal import Decimal, InvalidOperation

from core import norm

_M = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"m": _M}


# --------------------------------------------------------------------------- #
# Dosya okuma
# --------------------------------------------------------------------------- #
def _col_index(ref):
    letters = re.match(r"[A-Z]+", ref.upper()).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _num(s):
    """Excel sayılarını (5.55444E+9 gibi) düz metne çevir."""
    s = s.strip()
    if re.fullmatch(r"-?\d+(\.\d+)?([eE][+-]?\d+)?", s):
        try:
            d = Decimal(s)
            if d == d.to_integral_value():
                return str(int(d))
        except InvalidOperation:
            pass
    return s


def read_xlsx(path):
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{_M}}}t")))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        first = wb.find("m:sheets", NS).findall("m:sheet", NS)[0]
        rid = first.get(f"{{{_R}}}id")
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = next(r.get("Target") for r in rels if r.get("Id") == rid)
        target = target.lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        root = ET.fromstring(z.read(target))
        rows = []
        for row in root.iter(f"{{{_M}}}row"):
            cells = {}
            for c in row.findall("m:c", NS):
                t = c.get("t")
                v = c.find("m:v", NS)
                if t == "s" and v is not None:
                    val = shared[int(v.text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(f"{{{_M}}}t"))
                elif v is not None:
                    val = v.text or ""
                    if t in (None, "n"):
                        val = _num(val)
                else:
                    val = ""
                cells[_col_index(c.get("r"))] = val
            if cells:
                rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
        return rows


def read_csv(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8-sig", "cp1254"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    first = text.splitlines()[0] if text.strip() else ""
    delim = max((";", ",", "\t"), key=first.count)
    return [row for row in csv.reader(text.splitlines(), delimiter=delim)]


def read_table(path):
    """(başlıklar, satırlar[dict]) döner. İlk dolu satır başlık kabul edilir."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".xlsx":
        raw = read_xlsx(path)
    elif ext in (".csv", ".txt"):
        raw = read_csv(path)
    elif ext == ".xls":
        raise ValueError("Eski .xls biçimi desteklenmiyor. Excel'de 'Farklı kaydet ▸ .xlsx' yapın.")
    else:
        raise ValueError("Yalnızca .xlsx ve .csv dosyaları desteklenir.")
    raw = [r for r in raw if any(str(c).strip() for c in r)]
    if not raw:
        raise ValueError("Dosya boş görünüyor.")
    headers, seen = [], {}
    for i, h in enumerate(raw[0]):
        h = str(h).strip() or f"Sütun {i + 1}"
        if h in seen:
            seen[h] += 1
            h = f"{h} ({seen[h]})"
        else:
            seen[h] = 1
        headers.append(h)
    rows = []
    for r in raw[1:]:
        rows.append({h: (str(r[i]).strip() if i < len(r) else "") for i, h in enumerate(headers)})
    return headers, rows


def file_sig(path):
    return f"{os.path.getmtime(path)}:{os.path.getsize(path)}"


def csv_safe(v):
    """Excel'de formül olarak çalışabilecek hücreleri (=, @, +komut) etkisizleştirir."""
    v = "" if v is None else str(v)
    if v[:1] in ("=", "@") or (v[:1] in ("+", "-") and not re.fullmatch(r"[+\-]?[\d\s()./-]+", v)):
        return "'" + v
    return v


def write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow([csv_safe(h) for h in header])
        w.writerows([[csv_safe(c) for c in r] for r in rows])


# --------------------------------------------------------------------------- #
# Eşleştirme
# --------------------------------------------------------------------------- #
def phone_key(s):
    d = re.sub(r"\D", "", str(s or ""))
    return d[-10:] if len(d) >= 10 else ""


def phone_keys(value):
    """Bir hücrede birden fazla numara olabilir ('0555.. / 0532..')."""
    out = []
    for part in re.split(r"[/,;|]|\bve\b", str(value or "")):
        k = phone_key(part)
        if k and k not in out:
            out.append(k)
    return out


def _same(a, b):
    a, b = str(a).strip(), str(b).strip()
    numeric = re.compile(r"[\d\s+\-()./]+")
    if numeric.fullmatch(a) and numeric.fullmatch(b):
        da, db = re.sub(r"\D", "", a), re.sub(r"\D", "", b)
        if len(da) >= 7 and len(db) >= 7:
            return da[-10:] == db[-10:]
    return norm(" ".join(a.split())) == norm(" ".join(b.split()))


def title_of(store, cid, data):
    for f in store.fields(cid):
        v = str(data.get(str(f["id"]), "")).strip()
        if v:
            return v.splitlines()[0]
    return "(adsız)"


def compare(store, cid, rows, mapping, key_fid):
    """rows: read_table satırları. mapping: {alan_id: sütun_başlığı}.
    key_fid: eşleştirme anahtarı (telefon) alanının id'si.
    Dönüş: new / changed / same / missing / nokey / dup listeleri."""
    flds = {f["id"]: f for f in store.fields(cid)}
    existing = store.all_records(cid)
    index = {}
    for rec in existing:
        for k in phone_keys(rec["data"].get(str(key_fid), "")):
            index.setdefault(k, rec)

    res = {k: [] for k in ("new", "changed", "same", "missing", "nokey", "dup")}
    seen_file, matched_ids = set(), set()
    for row in rows:
        data = {}
        for fid, header in mapping.items():
            v = str(row.get(header, "")).strip()
            if v:
                data[str(fid)] = v
        if not data:
            continue
        keys = phone_keys(data.get(str(key_fid), ""))
        item = {"data": data, "row": row, "title": title_of(store, cid, data),
                "phone": data.get(str(key_fid), "")}
        if not keys:
            res["nokey"].append(item)
            continue
        if any(k in seen_file for k in keys):
            res["dup"].append(item)
            continue
        seen_file.update(keys)
        rec = next((index[k] for k in keys if k in index), None)
        if rec is None:
            res["new"].append(item)
            continue
        matched_ids.add(rec["id"])
        diffs = []
        for fid, header in mapping.items():
            new = data.get(str(fid), "")
            old = str(rec["data"].get(str(fid), "")).strip()
            if new and not _same(old, new):
                diffs.append((fid, flds[fid]["name"], old, new))
        item["rec"] = rec
        (res["changed"] if diffs else res["same"]).append(item)
        item["diffs"] = diffs
    for rec in existing:
        if rec["id"] not in matched_ids and phone_keys(rec["data"].get(str(key_fid), "")):
            res["missing"].append({"rec": rec, "title": store.title(rec),
                                   "phone": rec["data"].get(str(key_fid), "")})
    return res


def add_new(store, cid, items):
    for it in items:
        store.add_record(cid, dict(it["data"]))
    return len(items)


def apply_changes(store, items):
    for it in items:
        data = dict(it["rec"]["data"])
        for fid, _name, _old, new in it["diffs"]:
            data[str(fid)] = new
        store.update_record(it["rec"]["id"], data)
    return len(items)
