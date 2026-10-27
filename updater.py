"""GitHub Releases üzerinden güncelleme denetimi ve (.exe için) otomatik kurulum."""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request


def valid_repo(repo):
    return bool(re.fullmatch(r"[\w.\-]+/[\w.\-]+", repo or ""))


def parse_version(v):
    nums = re.findall(r"\d+", str(v).split("-")[0])
    return tuple(int(x) for x in nums[:4]) or (0,)


def is_newer(latest, current):
    return parse_version(latest) > parse_version(current)


def _get(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": "IsletmePaneli",
                                               "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_latest(repo, timeout=8):
    if not valid_repo(repo):
        raise ValueError("Depo adı 'kullanici/depo' biçiminde olmalı.")
    with _get(f"https://api.github.com/repos/{repo}/releases/latest", timeout) as r:
        d = json.load(r)
    assets = d.get("assets", [])
    exe = next((a for a in assets if a["name"].lower().endswith(".exe")), None)
    sha = next((a for a in assets if a["name"].lower().endswith(".sha256")), None)
    return {"version": str(d["tag_name"]).lstrip("vV"), "notes": d.get("body") or "",
            "page": d["html_url"],
            "exe_url": exe["browser_download_url"] if exe else None,
            "sha_url": sha["browser_download_url"] if sha else None}


def _download(url, dest, timeout=60):
    if not url.startswith("https://github.com/"):
        raise ValueError("Güvenilmeyen indirme adresi.")
    with _get(url, timeout) as r, open(dest, "wb") as fh:
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            fh.write(chunk)


def make_bat(new_path, exe_path):
    """Program kapanınca yeni .exe'yi eskisinin yerine koyup yeniden başlatır."""
    return ("@echo off\r\nchcp 65001 >nul\r\n"
            "for /l %%i in (1,1,30) do (\r\n"
            f'  move /y "{new_path}" "{exe_path}" >nul 2>&1 && goto ok\r\n'
            "  timeout /t 1 /nobreak >nul\r\n"
            ")\r\nexit /b 1\r\n:ok\r\n"
            f'start "" "{exe_path}"\r\n'
            '(goto) 2>nul & del "%~f0"\r\n')


def install_update(info):
    """Yalnızca paketlenmiş .exe için. İndirir, SHA256 doğrular, güncelleyiciyi başlatır.
    Çağıran, bu işlev döndükten sonra programı hemen kapatmalıdır."""
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Otomatik kurulum yalnızca .exe sürümünde çalışır.")
    exe = sys.executable
    new = exe + ".new"
    _download(info["exe_url"], new)
    if info.get("sha_url"):
        with _get(info["sha_url"], 15) as r:
            expected = r.read().decode("utf-8", "ignore").split()[0].strip().lower()
        h = hashlib.sha256()
        with open(new, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest().lower() != expected:
            os.remove(new)
            raise ValueError("İndirilen dosyanın doğrulaması (SHA256) başarısız. Güncelleme iptal edildi.")
    bat = os.path.join(tempfile.gettempdir(), "isletme_paneli_guncelle.bat")
    with open(bat, "w", encoding="utf-8", newline="") as fh:
        fh.write(make_bat(new, exe))
    subprocess.Popen(["cmd", "/c", bat], creationflags=0x00000008 | 0x08000000, close_fds=True)
