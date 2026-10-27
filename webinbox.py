"""Web formundan (web/ klasöründeki PHP sitesi) gelen başvuruları panele çeker."""
import json
import re
import secrets
import urllib.error
import urllib.request


def base_url(u):
    """Kullanıcının yazdığı adresi 'https://site/yol/' biçimine getirir."""
    u = (u or "").strip()
    u = re.sub(r"[^/]+\.php$", "", u)
    return u.rstrip("/") + "/" if u else ""


def valid_url(u):
    u = (u or "").strip().lower()
    return u.startswith("https://") or u.startswith("http://localhost") or u.startswith("http://127.0.0.1")


def api_url(base):
    return base_url(base) + "api.php"


def new_keys():
    """(davet kodu, API anahtarı) üretir; karışabilecek harfler (0/O, 1/I) kullanılmaz."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    code = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"{code[:4]}-{code[4:]}", secrets.token_urlsafe(32)


def config_lines(code, key):
    return f"    'access_code' => '{code}',\n    'api_key'     => '{key}',\n"


def _post(base, key, payload, timeout=12):
    if not valid_url(base):
        raise RuntimeError("Adres https:// ile başlamalı (ör. https://siteniz.example/).")
    body = json.dumps(dict(payload, key=key)).encode("utf-8")
    req = urllib.request.Request(api_url(base), data=body, headers={
        "Content-Type": "application/json", "User-Agent": "IsletmePaneli"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            msg = json.loads(raw.decode("utf-8")).get("error")
        except Exception:
            msg = None
        raise RuntimeError(msg or f"Sunucu hatası (HTTP {e.code}).")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Sunucuya ulaşılamadı: {e.reason}")
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise RuntimeError("Sunucu beklenen JSON yerine başka bir yanıt verdi. Ücretsiz host, "
                           "tarayıcı dışı isteklere bot doğrulaması koyuyor olabilir; adresi ve "
                           "hosting ayarlarını kontrol edin.")
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "Bilinmeyen hata."))
    return data


def ping(base, key):
    return _post(base, key, {"action": "ping"})


def list_items(base, key):
    return _post(base, key, {"action": "list"}).get("items", [])


def ack(base, key, ids):
    ids = [i for i in ids if re.fullmatch(r"[a-f0-9]{32}", str(i))]
    if not ids:
        return 0
    return _post(base, key, {"action": "ack", "ids": ids}).get("deleted", 0)


def to_rows(items):
    """Başvurular -> (başlıklar, satırlar). Satırlar listsync.compare ile uyumludur."""
    headers, rows = [], []
    for it in sorted(items, key=lambda i: i.get("received", "")):
        row = {str(k): str(v) for k, v in it.get("fields", {}).items()}
        for k in row:
            if k not in headers:
                headers.append(k)
        row["_id"] = it["id"]
        row["_received"] = it.get("received", "")
        rows.append(row)
    return headers, rows
