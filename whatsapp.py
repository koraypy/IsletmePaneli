"""WhatsApp yardımcıları: numara düzeltme, mesaj şablonu, sohbet açma.

Mesajlar wa.me / whatsapp:// bağlantısıyla WhatsApp'ta HAZIR olarak açılır;
"Gönder"e kişi kendisi basar. (Otomatik gönderim için resmî WhatsApp Business
API gerekir; resmî olmayan otomasyonlar hesap engeline yol açabilir.)
"""
import os
import re
import urllib.parse
import webbrowser

from core import norm

PHONE_WORDS = {"tel", "gsm", "cep", "whatsapp", "mobil"}

DEFAULT_TEMPLATES = {
    "Merhaba": "Merhaba {ad}, nasılsınız?",
    "Toplantı hatırlatma": "Merhaba {ad}, yarınki toplantıyı hatırlatmak istedim. Katılımınızı teyit eder misiniz?",
    "Duyuru": "Sayın {tam_ad}, önemli bir duyurumuz var: ",
    "Bilgi formu": "Merhaba {ad}, bilgilerini şu formdan doldurur musun? {form_linki}  Davet kodu: {davet_kodu}",
}


def wa_number(raw):
    """WhatsApp için uluslararası biçim (+ ve boşluksuz). Geçersiz/sabit hat -> ''."""
    s = str(raw or "").strip()
    d = re.sub(r"\D", "", s)
    if not d:
        return ""
    if s.startswith("+"):
        return d if 8 <= len(d) <= 15 else ""
    if d.startswith("00"):
        d = d[2:]
        return d if 8 <= len(d) <= 15 else ""
    if len(d) == 11 and d.startswith("05"):      # 0555 444 55 44
        return "9" + d
    if len(d) == 10 and d.startswith("5"):       # 555 444 55 44 / Excel'in 0'ı attığı biçim
        return "90" + d
    if len(d) == 12 and d.startswith("90"):      # 90 555 ...
        return d
    if d.startswith("0"):                        # sabit hat veya tanınmayan ulusal biçim
        return ""
    return d if 11 <= len(d) <= 15 else ""


def _is_phone_field(name):
    for w in re.findall(r"\w+", norm(name)):
        if w in PHONE_WORDS or w.startswith("telefon"):
            return True
    return False


def phone_options(store, rec):
    """[(etiket, wa_numarası), ...] — kaydın WhatsApp'a uygun numaraları."""
    out, seen = [], set()
    for f in store.fields(rec["category_id"]):
        if not _is_phone_field(f["name"]):
            continue
        value = str(rec["data"].get(str(f["id"]), ""))
        for part in re.split(r"[/,;|\n]|\bve\b", value):
            n = wa_number(part)
            if n and n not in seen:
                seen.add(n)
                out.append((f"{f['name']}: {part.strip()}", n))
    return out


def fill_template(text, store, rec):
    """{ad}, {tam_ad} ve alan adlarını ({görev} gibi) kayıttan doldurur.
    Gizli alanlar (TC, IBAN…) mesaja ASLA konmaz; yazılırsa olduğu gibi kalır."""
    flds = store.fields(rec["category_id"])
    title = store.title(rec, flds)
    parts = title.split()
    tokens = {"tam_ad": title, "ad": parts[0] if parts else title}
    for key, setting in (("form_linki", "web_url"), ("davet_kodu", "web_code")):
        val = (store.get_setting(setting, "") or "").strip()
        if val:
            tokens[key] = val
    for f in flds:
        if f["sensitive"]:
            continue
        v = str(rec["data"].get(str(f["id"]), "")).strip()
        tokens.setdefault(norm(f["name"]).strip().replace(" ", "_"), v)

    def sub(m):
        key = norm(m.group(1)).strip().replace(" ", "_")
        return tokens.get(key, m.group(0))

    return re.sub(r"\{([^{}]+)\}", sub, text)


def urls(number, text):
    q = urllib.parse.quote(text or "", safe="")
    web = f"https://wa.me/{number}" + (f"?text={q}" if text else "")
    app = f"whatsapp://send?phone={number}" + (f"&text={q}" if text else "")
    return web, app


def open_chat(number, text, mode="web"):
    web, app = urls(number, text)
    if mode == "app":
        try:
            os.startfile(app)  # Windows: WhatsApp Masaüstü
            return
        except Exception:
            pass
    webbrowser.open(web)
