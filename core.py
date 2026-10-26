"""İşletme Paneli - çekirdek modül (arayüzden bağımsız).

Veritabanı (SQLite), Türkçe uyumlu arama, akıllı yanıt, hızlı ekleme,
içe/dışa aktarma ve isteğe bağlı Ollama (yerel yapay zekâ) bağlantısı.
Yalnızca Python standart kütüphanesini kullanır.
"""
import csv
import datetime
import difflib
import json
import os
import re
import sqlite3
import sys
import unicodedata
import urllib.request

APP_NAME = "IsletmePaneli"


# --------------------------------------------------------------------------- #
# Klasörler
# --------------------------------------------------------------------------- #
def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def data_dir():
    """Veri klasörü. Programın yanında 'veri' klasörü varsa taşınabilir mod,
    yoksa %APPDATA%\\IsletmePaneli kullanılır."""
    portable = os.path.join(app_dir(), "veri")
    if os.path.isdir(portable):
        return portable
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


# --------------------------------------------------------------------------- #
# Metin normalleştirme (Türkçe harfler, büyük/küçük harf, aksanlar)
# --------------------------------------------------------------------------- #
_TR = str.maketrans({
    "İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c",
})


def norm(s):
    s = str(s or "").translate(_TR).lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


STOP = {
    "numara", "numarasi", "numarasini", "nedir", "kimdir", "nerede", "kac",
    "bana", "goster", "getir", "bul", "ver", "ve", "ile", "bir", "icin",
    "mi", "mu", "hangi", "ne", "nin", "nun", "in", "un",
}


def _prepare_query(q):
    # Ahmet'in -> Ahmet  (kesme işaretinden sonraki ek atılır)
    q = re.sub(r"['’`´]\w*", " ", q)

    # "0555 444 55 44" gibi boşluklu telefonları tek rakam dizisine çevir
    def phone(m):
        digits = re.sub(r"\D", "", m.group(0))
        return " " + digits + " " if len(digits) >= 7 else m.group(0)

    return re.sub(r"(?<!\d)\d{2,4}(?:[\s\-]\d{2,4}){2,5}(?!\d)", phone, q)


def _tokenize(q):
    toks = re.findall(r"[\w@.+\-]+", norm(_prepare_query(q)))
    toks = [t.strip(".-") for t in toks]
    return [t for t in toks if t and t not in STOP]


def _tok_hit(tok, text, digits, words):
    if tok in text:
        return 1.0
    if tok.isdigit() and len(tok) >= 3 and tok in digits:
        return 1.0
    for k in range(1, 4):  # basit ek soyma: "telefonu" -> "telefon"
        s = tok[:-k]
        if len(s) >= 4 and s in text:
            return 0.9
    if len(tok) >= 4 and difflib.get_close_matches(tok, words, n=1, cutoff=0.8):
        return 0.7  # yazım hatası toleransı
    return 0.0


def _is_hint(tok, fieldwords):
    if tok in fieldwords:
        return True
    return any(len(w) >= 4 and tok.startswith(w) and len(tok) <= len(w) + 4
               for w in fieldwords)


def _field_matches(field_name, hints):
    words = re.findall(r"\w+", norm(field_name))
    for h in hints:
        for w in words:
            if w == h or (len(w) >= 4 and h.startswith(w)) or (len(h) >= 3 and w.startswith(h)):
                return True
    return False


# --------------------------------------------------------------------------- #
# Veritabanı
# --------------------------------------------------------------------------- #
SCHEMA = """
CREATE TABLE IF NOT EXISTS categories(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    position INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS fields(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    ftype TEXT DEFAULT 'text',
    sensitive INTEGER DEFAULT 0,
    position INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS records(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    created TEXT,
    updated TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
"""

DEFAULT_CATEGORIES = {
    "Personel": [("Ad Soyad", "text", 0), ("Telefon", "text", 0),
                 ("TC Kimlik No", "text", 1), ("Görev", "text", 0),
                 ("E-posta", "text", 0), ("Notlar", "long", 0)],
    "Müşteri": [("Firma / Ad", "text", 0), ("Yetkili", "text", 0),
                ("Telefon", "text", 0), ("E-posta", "text", 0),
                ("Adres", "long", 0), ("Vergi No", "text", 0),
                ("Notlar", "long", 0)],
    "Tedarikçi": [("Firma", "text", 0), ("Yetkili", "text", 0),
                  ("Telefon", "text", 0), ("E-posta", "text", 0),
                  ("IBAN", "text", 1), ("Notlar", "long", 0)],
}

# Örnek kayıt (istediğiniz zaman silebilirsiniz)
EXAMPLE_PERSON = {"Ad Soyad": "Ahmet Yalın", "Telefon": "0555 444 55 44",
                  "TC Kimlik No": "12345678901"}


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


class Store:
    def __init__(self, path=None):
        self.path = path or os.path.join(data_dir(), "isletme.db")
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)
        self._fc = {}
        if self.get_setting("seeded") != "1":
            self._seed()

    def close(self):
        self.db.commit()
        self.db.close()

    # -- ayarlar ----------------------------------------------------------- #
    def get_setting(self, key, default=None):
        r = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default

    def set_setting(self, key, value):
        self.db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
                        (key, str(value)))
        self.db.commit()

    def _seed(self):
        for name, flds in DEFAULT_CATEGORIES.items():
            cid = self.add_category(name, flds)
            if name == "Personel":
                by_name = {f["name"]: f["id"] for f in self.fields(cid)}
                self.add_record(cid, {str(by_name[k]): v for k, v in EXAMPLE_PERSON.items()})
        self.set_setting("seeded", "1")

    # -- kategoriler ------------------------------------------------------- #
    def categories(self):
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM categories ORDER BY position, id")]

    def add_category(self, name, fields=None):
        name = (name or "").strip()
        if not name:
            raise ValueError("Kategori adı boş olamaz.")
        if any(norm(c["name"]) == norm(name) for c in self.categories()):
            raise ValueError("Bu isimde bir kategori zaten var.")
        pos = self.db.execute("SELECT COALESCE(MAX(position),0)+1 FROM categories").fetchone()[0]
        cur = self.db.execute("INSERT INTO categories(name,position) VALUES(?,?)", (name, pos))
        cid = cur.lastrowid
        for f in fields or []:
            if isinstance(f, str):
                f = (f, "text", 0)
            self.add_field(cid, f[0], f[1], f[2], commit=False)
        self.db.commit()
        self._fc.clear()
        return cid

    def rename_category(self, cid, name):
        name = (name or "").strip()
        if not name:
            raise ValueError("Kategori adı boş olamaz.")
        if any(norm(c["name"]) == norm(name) and c["id"] != cid for c in self.categories()):
            raise ValueError("Bu isimde bir kategori zaten var.")
        self.db.execute("UPDATE categories SET name=? WHERE id=?", (name, cid))
        self.db.commit()

    def delete_category(self, cid):
        self.db.execute("DELETE FROM categories WHERE id=?", (cid,))
        self.db.commit()
        self._fc.clear()

    def count_by_category(self):
        return {r["category_id"]: r["n"] for r in self.db.execute(
            "SELECT category_id, COUNT(*) n FROM records GROUP BY category_id")}

    # -- alanlar ----------------------------------------------------------- #
    def fields(self, cid):
        if cid not in self._fc:
            self._fc[cid] = [dict(r) for r in self.db.execute(
                "SELECT * FROM fields WHERE category_id=? ORDER BY position, id", (cid,))]
        return self._fc[cid]

    def add_field(self, cid, name, ftype="text", sensitive=0, commit=True):
        name = (name or "").strip()
        if not name:
            raise ValueError("Alan adı boş olamaz.")
        if any(norm(f["name"]) == norm(name) for f in self.fields(cid)):
            raise ValueError("Bu kategoride aynı isimde bir alan var.")
        pos = self.db.execute("SELECT COALESCE(MAX(position),0)+1 FROM fields WHERE category_id=?",
                              (cid,)).fetchone()[0]
        cur = self.db.execute(
            "INSERT INTO fields(category_id,name,ftype,sensitive,position) VALUES(?,?,?,?,?)",
            (cid, name, ftype, int(bool(sensitive)), pos))
        if commit:
            self.db.commit()
        self._fc.pop(cid, None)
        return cur.lastrowid

    def update_field(self, fid, **kw):
        row = self.db.execute("SELECT * FROM fields WHERE id=?", (fid,)).fetchone()
        if not row:
            return
        if "name" in kw:
            name = kw["name"].strip()
            if not name:
                raise ValueError("Alan adı boş olamaz.")
            if any(norm(f["name"]) == norm(name) and f["id"] != fid
                   for f in self.fields(row["category_id"])):
                raise ValueError("Bu kategoride aynı isimde bir alan var.")
            kw["name"] = name
        for k in kw:
            if k not in ("name", "ftype", "sensitive"):
                raise ValueError("Geçersiz alan özelliği.")
        sets = ", ".join(f"{k}=?" for k in kw)
        self.db.execute(f"UPDATE fields SET {sets} WHERE id=?", (*kw.values(), fid))
        self.db.commit()
        self._fc.pop(row["category_id"], None)

    def move_field(self, fid, direction):
        row = self.db.execute("SELECT * FROM fields WHERE id=?", (fid,)).fetchone()
        if not row:
            return
        flds = self.fields(row["category_id"])
        ids = [f["id"] for f in flds]
        i = ids.index(fid)
        j = i + direction
        if not 0 <= j < len(ids):
            return
        ids[i], ids[j] = ids[j], ids[i]
        for pos, f_id in enumerate(ids):
            self.db.execute("UPDATE fields SET position=? WHERE id=?", (pos, f_id))
        self.db.commit()
        self._fc.pop(row["category_id"], None)

    def delete_field(self, fid):
        row = self.db.execute("SELECT * FROM fields WHERE id=?", (fid,)).fetchone()
        if not row:
            return
        cid = row["category_id"]
        for r in self.db.execute("SELECT id,data FROM records WHERE category_id=?", (cid,)).fetchall():
            d = json.loads(r["data"])
            if str(fid) in d:
                d.pop(str(fid))
                self.db.execute("UPDATE records SET data=? WHERE id=?",
                                (json.dumps(d, ensure_ascii=False), r["id"]))
        self.db.execute("DELETE FROM fields WHERE id=?", (fid,))
        self.db.commit()
        self._fc.pop(cid, None)

    # -- kayıtlar ---------------------------------------------------------- #
    @staticmethod
    def _rec(row):
        return {"id": row["id"], "category_id": row["category_id"],
                "category": row["cname"], "data": json.loads(row["data"]),
                "created": row["created"], "updated": row["updated"]}

    def all_records(self, cid=None):
        sql = ("SELECT r.*, c.name cname FROM records r "
               "JOIN categories c ON c.id=r.category_id")
        args = ()
        if cid:
            sql += " WHERE r.category_id=?"
            args = (cid,)
        sql += " ORDER BY c.position, r.id"
        return [self._rec(r) for r in self.db.execute(sql, args)]

    def get_record(self, rid):
        r = self.db.execute("SELECT r.*, c.name cname FROM records r "
                            "JOIN categories c ON c.id=r.category_id WHERE r.id=?", (rid,)).fetchone()
        return self._rec(r) if r else None

    def add_record(self, cid, data):
        now = _now()
        cur = self.db.execute(
            "INSERT INTO records(category_id,data,created,updated) VALUES(?,?,?,?)",
            (cid, json.dumps(data, ensure_ascii=False), now, now))
        self.db.commit()
        return cur.lastrowid

    def update_record(self, rid, data):
        self.db.execute("UPDATE records SET data=?, updated=? WHERE id=?",
                        (json.dumps(data, ensure_ascii=False), _now(), rid))
        self.db.commit()

    def delete_record(self, rid):
        self.db.execute("DELETE FROM records WHERE id=?", (rid,))
        self.db.commit()

    def title(self, rec, flds=None):
        flds = flds if flds is not None else self.fields(rec["category_id"])
        for f in flds:
            v = str(rec["data"].get(str(f["id"]), "")).strip()
            if v:
                return v.splitlines()[0]
        return "(boş kayıt)"

    # -- arama ------------------------------------------------------------- #
    def search(self, query, cid=None):
        """(sonuçlar, ipuçları) döner. Sonuçlar: [(kayıt, puan), ...]"""
        recs = self.all_records(cid)
        fields_by_cat = {c["id"]: self.fields(c["id"]) for c in self.categories()}
        fieldwords = set()
        for fl in fields_by_cat.values():
            for f in fl:
                fieldwords.update(w for w in re.findall(r"\w+", norm(f["name"])) if len(w) >= 2)

        toks = _tokenize(query)
        if not toks:
            return [(r, 0.0) for r in recs], []
        hints = [t for t in toks if _is_hint(t, fieldwords)]
        core_toks = [t for t in toks if t not in hints]
        use = core_toks or toks

        prepared = []
        for rec in recs:
            ids = {str(f["id"]) for f in fields_by_cat.get(rec["category_id"], [])}
            vals = [str(v) for k, v in rec["data"].items() if k in ids and str(v).strip()]
            text = norm(rec["category"] + " " + " ".join(vals))
            digits = " ".join(re.sub(r"\D", "", v) for v in vals)
            words = set(re.findall(r"\w+", text))
            prepared.append((rec, text, digits, words))

        def run(tokens):
            out = []
            for rec, text, digits, words in prepared:
                hits = [_tok_hit(t, text, digits, words) for t in tokens]
                n = sum(1 for h in hits if h)
                score = sum(hits)
                if norm(self.title(rec)).startswith(tokens[0]):
                    score += 0.5
                out.append((rec, score, n))
            return out

        scored = run(use)
        res = [(r, s) for r, s, n in scored if n == len(use)]
        if not res and len(use) >= 3:
            res = [(r, s) for r, s, n in scored if n >= len(use) - 1 and n > 0]
        if not res and not core_toks:
            res = [(r, 0.0) for r in recs]  # sadece alan adı yazıldı: hepsini listele
        res.sort(key=lambda x: (-x[1], norm(self.title(x[0]))))
        return res, hints

    # -- akıllı yanıt (çevrimdışı, kural tabanlı) -------------------------- #
    def offline_answer(self, results, hints, limit=5):
        if not results:
            return "Kayıt bulunamadı."
        lines = []
        for rec, _ in results[:limit]:
            flds = self.fields(rec["category_id"])
            title = self.title(rec, flds)
            picked = [f for f in flds if hints and _field_matches(f["name"], hints)]
            parts = []
            if picked:
                for f in picked:
                    v = str(rec["data"].get(str(f["id"]), "")).strip()
                    if not v:
                        parts.append(f"{f['name']}: (boş)")
                    elif f["sensitive"]:
                        parts.append(f"{f['name']}: 🔒 gizli alan – kayıt detayında “Göster”e basın")
                    else:
                        parts.append(f"{f['name']}: {v}")
            else:
                for f in flds:
                    v = str(rec["data"].get(str(f["id"]), "")).strip()
                    if v and not f["sensitive"] and f["name"] and v != title:
                        parts.append(f"{f['name']}: {v.splitlines()[0]}")
                parts = parts[:4]
            lines.append(f"{title} ({rec['category']})" + (" → " + "; ".join(parts) if parts else ""))
        if len(results) > limit:
            lines.append(f"… ve {len(results) - limit} kayıt daha")
        return "\n".join(lines)

    def context_lines(self, recs):
        """Yapay zekâya gönderilecek metin. Gizli alanlar ASLA dahil edilmez."""
        out = []
        for rec in recs:
            flds = self.fields(rec["category_id"])
            parts = []
            for f in flds:
                v = str(rec["data"].get(str(f["id"]), "")).strip()
                if v and not f["sensitive"]:
                    parts.append(f"{f['name']}={v.replace(chr(10), ' ')}")
            out.append(f"[{rec['category']}] " + "; ".join(parts))
        return out

    # -- hızlı ekleme ------------------------------------------------------ #
    def parse_quick_add(self, text):
        """'+ Personel | Ad Soyad=Ali Veli | 0555...' -> (kategori_id, veri)"""
        body = text.lstrip("+").strip()
        parts = [p.strip() for p in re.split(r"[|;]", body) if p.strip()]
        if len(parts) < 2:
            raise ValueError("Biçim:  + Kategori | Değer | Alan=Değer | ...")
        cat = None
        cats = self.categories()
        for c in cats:
            if norm(c["name"]) == norm(parts[0]):
                cat = c
        if cat is None:
            for c in cats:
                if norm(c["name"]).startswith(norm(parts[0])):
                    cat = c
                    break
        if cat is None:
            raise ValueError(f"“{parts[0]}” adında bir kategori yok.")
        flds = self.fields(cat["id"])
        data = {}
        for p in parts[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                f = next((f for f in flds if norm(f["name"]) == norm(k)), None) or \
                    next((f for f in flds if norm(f["name"]).startswith(norm(k.strip()))), None)
                if not f:
                    raise ValueError(f"“{k.strip()}” adında bir alan yok.")
                data[str(f["id"])] = v.strip()
            else:
                for f in flds:
                    if str(f["id"]) not in data:
                        data[str(f["id"])] = p
                        break
        return cat["id"], data

    # -- yedek / içe-dışa aktarma ------------------------------------------ #
    def backup(self, dest):
        d = sqlite3.connect(dest)
        try:
            self.db.backup(d)
        finally:
            d.close()

    def auto_backup(self, keep=14):
        d = os.path.join(os.path.dirname(self.path), "yedekler")
        os.makedirs(d, exist_ok=True)
        f = os.path.join(d, f"isletme-{datetime.date.today():%Y%m%d}.db")
        if not os.path.exists(f):
            self.backup(f)
        files = sorted(x for x in os.listdir(d) if x.startswith("isletme-") and x.endswith(".db"))
        for old in files[:-keep]:
            try:
                os.remove(os.path.join(d, old))
            except OSError:
                pass

    def export_json(self, path, with_records=True):
        out = {"version": 1, "categories": []}
        for c in self.categories():
            flds = self.fields(c["id"])
            item = {"name": c["name"],
                    "fields": [{"name": f["name"], "type": f["ftype"],
                                "sensitive": bool(f["sensitive"])} for f in flds],
                    "records": []}
            if with_records:
                for r in self.all_records(c["id"]):
                    item["records"].append({f["name"]: r["data"].get(str(f["id"]), "") for f in flds})
            out["categories"].append(item)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)

    def import_json(self, path):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        n = 0
        for c in data.get("categories", []):
            cats = {norm(x["name"]): x["id"] for x in self.categories()}
            cid = cats.get(norm(c["name"]))
            if cid is None:
                cid = self.add_category(c["name"])
            existing = {norm(f["name"]): f for f in self.fields(cid)}
            for f in c.get("fields", []):
                if norm(f["name"]) not in existing:
                    self.add_field(cid, f["name"], f.get("type", "text"), f.get("sensitive", 0))
            by_name = {norm(f["name"]): f["id"] for f in self.fields(cid)}
            for rec in c.get("records", []):
                d = {str(by_name[norm(k)]): str(v) for k, v in rec.items() if norm(k) in by_name}
                if any(v.strip() for v in d.values()):
                    self.add_record(cid, d)
                    n += 1
        return n

    def export_csv(self, path, cid=None):
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            if cid:
                flds = self.fields(cid)
                w.writerow([f["name"] for f in flds])
                for r in self.all_records(cid):
                    w.writerow([r["data"].get(str(f["id"]), "") for f in flds])
            else:
                w.writerow(["Kategori", "Kayıt No", "Alan", "Değer"])
                for r in self.all_records():
                    for f in self.fields(r["category_id"]):
                        v = r["data"].get(str(f["id"]), "")
                        if str(v).strip():
                            w.writerow([r["category"], r["id"], f["name"], v])


# --------------------------------------------------------------------------- #
# İsteğe bağlı: Ollama (ücretsiz, açık kaynak, yerel yapay zekâ)
# --------------------------------------------------------------------------- #
def ollama_models(host, timeout=2):
    with urllib.request.urlopen(host.rstrip("/") + "/api/tags", timeout=timeout) as r:
        return [m["name"] for m in json.load(r).get("models", [])]


def ollama_answer(host, model, question, context_lines, timeout=90):
    prompt = ("Sen bir işletmenin kayıt asistanısın. Yalnızca aşağıdaki kayıtlara dayanarak "
              "kısa ve Türkçe cevap ver. Cevap kayıtlarda yoksa 'Kayıtlarda bulamadım' de. "
              "Bilgi uydurma.\n\nKAYITLAR:\n" + "\n".join(context_lines) +
              f"\n\nSORU: {question}\nCEVAP:")
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(host.rstrip("/") + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r).get("response", "").strip()
