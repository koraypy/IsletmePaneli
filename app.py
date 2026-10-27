"""İşletme Paneli - Windows masaüstü arayüzü (Tkinter, ek kurulum gerektirmez)."""
import datetime
import json
import os
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

import core
import listsync
import updater
import webinbox
import whatsapp
from version import UPDATE_REPO, VERSION

APP_TITLE = "İşletme Paneli"
FAMILY = "Segoe UI"

THEMES = {
    "acik": dict(bg="#f3f4f6", fg="#1f2933", card="#ffffff", muted="#6b7280",
                 entry="#ffffff", border="#d1d5db", hover="#e5e7eb"),
    "koyu": dict(bg="#1b1f24", fg="#e6e8eb", card="#262c33", muted="#9aa4af",
                 entry="#2b323a", border="#3a434d", hover="#323b45"),
}
MASK = "•••••••••••"


def shade(hexcolor, f):
    h = hexcolor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c * f))) for c in (r, g, b))


class ScrollFrame(ttk.Frame):
    """Kaydırılabilir alan."""

    def __init__(self, master, card=False):
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, style="Card.TFrame" if card else "TFrame")
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.win, width=e.width))
        self.canvas.configure(yscrollcommand=vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, e):
        self.canvas.yview_scroll(int(-e.delta / 120), "units")


# =========================================================================== #
# Kayıt ekle / düzenle penceresi
# =========================================================================== #
class RecordDialog(tk.Toplevel):
    def __init__(self, app, record=None, cat_id=None):
        super().__init__(app)
        self.app, self.store, self.record = app, app.store, record
        self.cats = self.store.categories()
        if not self.cats:
            messagebox.showinfo(APP_TITLE, "Önce bir kategori oluşturun (Düzen ▸ Kategorileri yönet).",
                                parent=app)
            self.destroy()
            return
        self.configure(bg=app.t["bg"])
        self.title("Kaydı düzenle" if record else "Yeni kayıt")
        self.geometry("560x580")
        self.transient(app)

        top = ttk.Frame(self, padding=(14, 12))
        top.pack(fill="x")
        ttk.Label(top, text="Kategori").pack(side="left")
        self.cat_var = tk.StringVar()
        self.cb = ttk.Combobox(top, textvariable=self.cat_var, state="readonly",
                               values=[c["name"] for c in self.cats])
        self.cb.pack(side="left", padx=10, fill="x", expand=True)
        start = record["category_id"] if record else (cat_id or self.cats[0]["id"])
        self.cat_var.set(next(c["name"] for c in self.cats if c["id"] == start))
        if record:
            self.cb.state(["disabled"])
        self.cb.bind("<<ComboboxSelected>>", lambda e: self.build_fields())

        self.sf = ScrollFrame(self)
        self.sf.pack(fill="both", expand=True, padx=14)
        self.sf.canvas.configure(bg=app.t["bg"])

        bar = ttk.Frame(self, padding=14)
        bar.pack(fill="x")
        ttk.Button(bar, text="İptal", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="Kaydet  (Ctrl+Enter)", style="Accent.TButton",
                   command=self.save).pack(side="right", padx=8)

        self.build_fields()
        self.bind("<Control-Return>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.destroy())
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    def cid(self):
        return next(c["id"] for c in self.cats if c["name"] == self.cat_var.get())

    def build_fields(self):
        t = self.app.t
        for w in self.sf.inner.winfo_children():
            w.destroy()
        cid = self.cid()
        self.widgets = {}
        inner = self.sf.inner
        inner.columnconfigure(0, weight=1)
        first = None
        r = 0
        for f in self.store.fields(cid):
            label = ("🔒 " if f["sensitive"] else "") + f["name"]
            ttk.Label(inner, text=label, style="Muted.TLabel").grid(row=r, column=0, sticky="w", pady=(8, 2))
            if f["ftype"] == "long":
                w = tk.Text(inner, height=4, wrap="word", bg=t["entry"], fg=t["fg"],
                            insertbackground=t["fg"], relief="flat", highlightthickness=1,
                            highlightbackground=t["border"], highlightcolor=self.app.accent,
                            font=(FAMILY, self.app.font_size))
                w.bind("<Tab>", lambda e: (e.widget.tk_focusNext().focus(), "break")[1])
            else:
                w = ttk.Entry(inner)
            w.grid(row=r + 1, column=0, sticky="ew")
            r += 2
            if self.record and self.record["category_id"] == cid:
                v = str(self.record["data"].get(str(f["id"]), ""))
                if isinstance(w, tk.Text):
                    w.insert("1.0", v)
                else:
                    w.insert(0, v)
            self.widgets[f["id"]] = w
            if first is None:
                first = w
        if first:
            first.focus_set()

    def save(self):
        data = {}
        for fid, w in self.widgets.items():
            v = w.get("1.0", "end-1c") if isinstance(w, tk.Text) else w.get()
            data[str(fid)] = v.strip()
        if not any(data.values()):
            messagebox.showwarning(APP_TITLE, "En az bir alanı doldurun.", parent=self)
            return
        if self.record:
            self.store.update_record(self.record["id"], data)
            self.app.select_after = self.record["id"]
        else:
            self.app.select_after = self.store.add_record(self.cid(), data)
        self.app.refresh_categories()
        self.app.refresh()
        self.destroy()


# =========================================================================== #
# Kategori ve alan yönetimi
# =========================================================================== #
class CategoryDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app, self.store = app, app.store
        self.title("Kategorileri ve alanları yönet")
        self.geometry("820x500")
        self.configure(bg=app.t["bg"])
        self.transient(app)

        left = ttk.Frame(self, padding=12)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="Kategoriler", style="Title.TLabel").pack(anchor="w", pady=(0, 6))
        self.lb_c = self._listbox(left)
        self.lb_c.bind("<<ListboxSelect>>", lambda e: self.load_fields())
        for txt, cmd in (("Kategori ekle", self.add_cat), ("Yeniden adlandır", self.ren_cat),
                         ("Sil", self.del_cat)):
            ttk.Button(left, text=txt, command=cmd).pack(fill="x", pady=2)

        right = ttk.Frame(self, padding=12)
        right.pack(side="left", fill="both", expand=True)
        ttk.Label(right, text="Seçili kategorinin alanları", style="Title.TLabel").pack(anchor="w", pady=(0, 6))
        mid = ttk.Frame(right)
        mid.pack(fill="both", expand=True)
        self.lb_f = self._listbox(mid, side="left")
        col = ttk.Frame(mid, padding=(10, 0))
        col.pack(side="left", fill="y")
        for txt, cmd in (("Alan ekle", self.add_field), ("Yeniden adlandır", self.ren_field),
                         ("Gizli ⇄ Normal", self.toggle_sens), ("Kısa ⇄ Uzun metin", self.toggle_long),
                         ("▲ Yukarı", lambda: self.move(-1)), ("▼ Aşağı", lambda: self.move(1)),
                         ("Alanı sil", self.del_field)):
            ttk.Button(col, text=txt, command=cmd).pack(fill="x", pady=2)
        ttk.Label(right, text="🔒 Gizli alan: ekranda ••• olarak görünür, “Göster” ile açılır; "
                              "yapay zekâya hiç gönderilmez.", style="Muted.TLabel",
                  wraplength=480).pack(anchor="w", pady=(8, 0))
        ttk.Button(right, text="Kapat", command=self.destroy).pack(anchor="e", pady=(8, 0))
        self.load_cats()

    def _listbox(self, master, side=None):
        t, app = self.app.t, self.app
        lb = tk.Listbox(master, exportselection=False, activestyle="none", bd=0,
                        highlightthickness=1, highlightbackground=t["border"],
                        bg=t["card"], fg=t["fg"], selectbackground=app.accent,
                        selectforeground="#ffffff", font=(FAMILY, app.font_size), width=26)
        if side:
            lb.pack(side=side, fill="both", expand=True)
        else:
            lb.pack(fill="both", expand=True, pady=(0, 6))
        return lb

    def changed(self):
        self.app.refresh_categories()
        self.app.refresh()

    def cur_cat(self):
        s = self.lb_c.curselection()
        return self.cats[s[0]] if s else None

    def cur_field(self):
        s = self.lb_f.curselection()
        return self.flds[s[0]] if s else None

    def load_cats(self, select_id=None):
        self.cats = self.store.categories()
        self.lb_c.delete(0, "end")
        for c in self.cats:
            self.lb_c.insert("end", c["name"])
        idx = 0
        if select_id:
            idx = next((i for i, c in enumerate(self.cats) if c["id"] == select_id), 0)
        if self.cats:
            self.lb_c.selection_set(idx)
        self.load_fields()

    def load_fields(self, select_id=None):
        self.lb_f.delete(0, "end")
        c = self.cur_cat()
        self.flds = self.store.fields(c["id"]) if c else []
        for f in self.flds:
            tags = (" 🔒" if f["sensitive"] else "") + (" (uzun metin)" if f["ftype"] == "long" else "")
            self.lb_f.insert("end", f["name"] + tags)
        if self.flds:
            idx = next((i for i, f in enumerate(self.flds) if f["id"] == select_id), 0)
            self.lb_f.selection_set(idx)

    def _warn(self, e):
        messagebox.showwarning(APP_TITLE, str(e), parent=self)

    def add_cat(self):
        name = simpledialog.askstring("Yeni kategori", "Kategori adı:", parent=self)
        if not name:
            return
        try:
            cid = self.store.add_category(name, [("Ad / Başlık", "text", 0), ("Notlar", "long", 0)])
        except ValueError as e:
            return self._warn(e)
        self.load_cats(cid)
        self.changed()

    def ren_cat(self):
        c = self.cur_cat()
        if not c:
            return
        name = simpledialog.askstring("Yeniden adlandır", "Yeni ad:", initialvalue=c["name"], parent=self)
        if not name:
            return
        try:
            self.store.rename_category(c["id"], name)
        except ValueError as e:
            return self._warn(e)
        self.load_cats(c["id"])
        self.changed()

    def del_cat(self):
        c = self.cur_cat()
        if not c:
            return
        n = self.store.count_by_category().get(c["id"], 0)
        if messagebox.askyesno(APP_TITLE, f"“{c['name']}” kategorisi ve içindeki {n} kayıt kalıcı olarak "
                                          "silinecek. Emin misiniz?", icon="warning", parent=self):
            self.store.delete_category(c["id"])
            self.app.current_cat = None
            self.load_cats()
            self.changed()

    def add_field(self):
        c = self.cur_cat()
        if not c:
            return
        name = simpledialog.askstring("Yeni alan", "Alan adı (ör. Doğum Tarihi):", parent=self)
        if not name:
            return
        long_ = messagebox.askyesno("Alan türü", "Çok satırlı (uzun) metin alanı mı?\n"
                                                 "(Adres, not gibi)", parent=self)
        sens = messagebox.askyesno("Gizli alan", "Gizli alan mı?\n(TC no, IBAN, şifre gibi — "
                                                 "ekranda gizlenir)", parent=self)
        try:
            fid = self.store.add_field(c["id"], name, "long" if long_ else "text", sens)
        except ValueError as e:
            return self._warn(e)
        self.load_fields(fid)
        self.changed()

    def ren_field(self):
        f = self.cur_field()
        if not f:
            return
        name = simpledialog.askstring("Yeniden adlandır", "Yeni ad:", initialvalue=f["name"], parent=self)
        if not name:
            return
        try:
            self.store.update_field(f["id"], name=name)
        except ValueError as e:
            return self._warn(e)
        self.load_fields(f["id"])
        self.changed()

    def toggle_sens(self):
        f = self.cur_field()
        if f:
            self.store.update_field(f["id"], sensitive=0 if f["sensitive"] else 1)
            self.load_fields(f["id"])
            self.changed()

    def toggle_long(self):
        f = self.cur_field()
        if f:
            self.store.update_field(f["id"], ftype="text" if f["ftype"] == "long" else "long")
            self.load_fields(f["id"])
            self.changed()

    def move(self, d):
        f = self.cur_field()
        if f:
            self.store.move_field(f["id"], d)
            self.load_fields(f["id"])
            self.changed()

    def del_field(self):
        f = self.cur_field()
        if f and messagebox.askyesno(APP_TITLE, f"“{f['name']}” alanı ve tüm kayıtlardaki bu alanın "
                                                "bilgileri silinecek. Emin misiniz?",
                                     icon="warning", parent=self):
            self.store.delete_field(f["id"])
            self.load_fields()
            self.changed()


# =========================================================================== #
# Dosyadan karşılaştır (Excel / CSV)  +  izleme
# =========================================================================== #
class SyncDialog(tk.Toplevel):
    TABS = [("new", "Yeni"), ("changed", "Değişmiş"), ("missing", "Listede yok"),
            ("same", "Aynı"), ("issue", "Sorunlu")]
    NONE = "— yok —"

    def __init__(self, app, preset=False):
        super().__init__(app)
        self.app, self.store = app, app.store
        self.cats = self.store.categories()
        if not self.cats:
            messagebox.showinfo(APP_TITLE, "Önce bir kategori oluşturun.", parent=app)
            self.destroy()
            return
        self.title("Dosyadan karşılaştır / içe aktar")
        self.geometry("960x720")
        self.configure(bg=app.t["bg"])
        self.transient(app)
        self.headers, self.rows, self.res = [], [], None
        self.items = {}
        self.map_vars = {}

        top = ttk.Frame(self, padding=(14, 12, 14, 4))
        top.pack(fill="x")
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="Kategori").grid(row=0, column=0, sticky="w", pady=2)
        self.cat_var = tk.StringVar(value=self._cat_name(app.current_cat))
        cb = ttk.Combobox(top, textvariable=self.cat_var, state="readonly",
                          values=[c["name"] for c in self.cats])
        cb.grid(row=0, column=1, sticky="ew", padx=8, pady=2)
        cb.bind("<<ComboboxSelected>>", lambda e: self.build_mapping())
        ttk.Label(top, text="Dosya").grid(row=1, column=0, sticky="w", pady=2)
        self.path_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.path_var).grid(row=1, column=1, sticky="ew", padx=8, pady=2)
        ttk.Button(top, text="Seç…", command=self.choose).grid(row=1, column=2, pady=2)
        ttk.Label(top, text="Eşleştirme alanı").grid(row=2, column=0, sticky="w", pady=2)
        self.key_var = tk.StringVar()
        self.key_cb = ttk.Combobox(top, textvariable=self.key_var, state="readonly")
        self.key_cb.grid(row=2, column=1, sticky="ew", padx=8, pady=2)
        ttk.Label(top, text="(kişiler bu alanla tanınır — Telefon)", style="Muted.TLabel").grid(
            row=2, column=2, sticky="w")

        ttk.Label(self, text="Dosyadaki sütunları alanlarla eşleştirin", style="Title.TLabel",
                  padding=(14, 8, 14, 2)).pack(anchor="w")
        self.map_sf = ScrollFrame(self)
        self.map_sf.canvas.configure(height=140, bg=app.t["bg"])
        self.map_sf.pack(fill="x", padx=14)

        opt = ttk.Frame(self, padding=(14, 8))
        opt.pack(fill="x")
        self.watch_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt, text="Bu dosyayı izle, değişince haber ver — her", variable=self.watch_var).pack(side="left")
        self.min_var = tk.IntVar(value=int(app.cfg("watch_minutes", "30") or 30))
        ttk.Spinbox(opt, from_=1, to=1440, width=5, textvariable=self.min_var).pack(side="left", padx=6)
        ttk.Label(opt, text="dakikada").pack(side="left")
        ttk.Button(opt, text="Karşılaştır", style="Accent.TButton", command=self.run_compare).pack(side="right")

        self.summary = ttk.Label(self, style="Muted.TLabel", padding=(14, 0))
        self.summary.pack(anchor="w")
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=14, pady=(4, 14))
        self.trees = {}
        for kind, label in self.TABS:
            fr = ttk.Frame(self.nb, padding=6)
            self.nb.add(fr, text=label)
            tree = ttk.Treeview(fr, columns=("a", "b", "c"), show="headings", selectmode="extended")
            for col, txt, w in (("a", "Kişi", 200), ("b", "Telefon", 140), ("c", "Ayrıntı", 480)):
                tree.heading(col, text=txt)
                tree.column(col, width=w, anchor="w")
            vsb = ttk.Scrollbar(fr, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)
            bar = ttk.Frame(fr)
            bar.pack(side="bottom", fill="x", pady=(6, 0))
            tree.pack(side="left", fill="both", expand=True)
            vsb.pack(side="right", fill="y")
            tree.bind("<Control-a>", lambda e, t=tree: (t.selection_set(t.get_children()), "break")[1])
            self.trees[kind] = tree
            self._buttons(kind, bar)

        self.key_cb.bind("<<ComboboxSelected>>", lambda e: self.build_mapping(keep=True))
        if preset:
            self._load_preset()
        else:
            self.build_mapping()

    # -- yardımcılar ------------------------------------------------------- #
    def _cat_name(self, cid):
        return next((c["name"] for c in self.cats if c["id"] == cid), self.cats[0]["name"])

    def cid(self):
        return next(c["id"] for c in self.cats if c["name"] == self.cat_var.get())

    def _buttons(self, kind, bar):
        def add(txt, cmd, accent=False):
            ttk.Button(bar, text=txt, command=cmd,
                       style="Accent.TButton" if accent else "TButton").pack(side="left", padx=(0, 6))
        if kind == "new":
            add("Seçilileri ekle", lambda: self.do_add(False), True)
            add("Hepsini ekle", lambda: self.do_add(True))
        elif kind == "changed":
            add("Seçilileri güncelle", lambda: self.do_update(False), True)
            add("Hepsini güncelle", lambda: self.do_update(True))
        elif kind == "missing":
            add("Listeyi CSV olarak kaydet", self.export_missing, True)
            ttk.Label(bar, text="Panelde olup dosyada bulunmayan kişiler (silinmez).",
                      style="Muted.TLabel").pack(side="left", padx=6)
        elif kind == "issue":
            add("Telefonsuzları yine de ekle (seçili)", self.do_add_nokey)
            ttk.Label(bar, text="Telefonu olmayan/geçersiz satırlar ve dosyada tekrar edenler.",
                      style="Muted.TLabel").pack(side="left", padx=6)

    def choose(self):
        p = filedialog.askopenfilename(parent=self, filetypes=[
            ("Excel / CSV", "*.xlsx *.csv *.txt"), ("Tümü", "*.*")])
        if p:
            self.path_var.set(p)
            self.load_file()

    def load_file(self):
        try:
            self.headers, self.rows = listsync.read_table(self.path_var.get())
        except Exception as e:
            self.headers, self.rows = [], []
            messagebox.showerror(APP_TITLE, f"Dosya okunamadı:\n{e}", parent=self)
        self.build_mapping()

    def build_mapping(self, keep=False, preset_map=None):
        flds = self.store.fields(self.cid())
        names = [f["name"] for f in flds]
        if not keep or self.key_var.get() not in names:
            key = next((f["name"] for f in flds if "telefon" in core.norm(f["name"])), names[0] if names else "")
            self.key_var.set(key)
        self.key_cb.configure(values=names)
        old = {n: v.get() for n, v in self.map_vars.items()} if keep else {}
        inner = self.map_sf.inner
        for w in inner.winfo_children():
            w.destroy()
        self.map_vars = {}
        inner.columnconfigure(1, weight=1)
        if not self.headers:
            ttk.Label(inner, text="Önce bir Excel/CSV dosyası seçin.", style="Muted.TLabel").grid(
                row=0, column=0, pady=8)
            return
        for r, f in enumerate(flds):
            mark = "🔑 " if f["name"] == self.key_var.get() else ""
            ttk.Label(inner, text=mark + f["name"]).grid(row=r, column=0, sticky="w", padx=(0, 12), pady=2)
            if preset_map and str(f["id"]) in preset_map and preset_map[str(f["id"])] in self.headers:
                guess = preset_map[str(f["id"])]
            elif f["name"] in old:
                guess = old[f["name"]]
            else:
                guess = self._guess(f["name"])
            var = tk.StringVar(value=guess)
            ttk.Combobox(inner, textvariable=var, state="readonly",
                         values=[self.NONE] + self.headers).grid(row=r, column=1, sticky="ew", pady=2)
            self.map_vars[f["name"]] = var

    def _guess(self, fname):
        n = core.norm(fname)
        for h in self.headers:
            if core.norm(h) == n:
                return h
        for h in self.headers:
            hn = core.norm(h)
            if hn and (hn in n or n in hn):
                return h
        return self.NONE

    def _mapping(self):
        flds = {f["name"]: f["id"] for f in self.store.fields(self.cid())}
        return {flds[n]: v.get() for n, v in self.map_vars.items() if v.get() != self.NONE}, flds

    # -- karşılaştırma ----------------------------------------------------- #
    def run_compare(self):
        if not self.rows and self.path_var.get():
            self.load_file()
        if not self.rows:
            messagebox.showinfo(APP_TITLE, "Önce dosya seçin.", parent=self)
            return
        mapping, flds = self._mapping()
        key_fid = flds.get(self.key_var.get())
        if key_fid not in mapping:
            messagebox.showwarning(APP_TITLE, f"“{self.key_var.get()}” alanı için dosyadan bir sütun seçin.",
                                   parent=self)
            return
        self.res = res = listsync.compare(self.store, self.cid(), self.rows, mapping, key_fid)
        self.mapping, self.key_fid = mapping, key_fid
        self._fill(res)
        self._save_watch()
        n = lambda k: len(res[k])  # noqa: E731
        self.summary.config(text=f"Dosyada {len(self.rows)} satır  ·  yeni {n('new')}  ·  değişmiş {n('changed')}"
                                 f"  ·  aynı {n('same')}  ·  listede yok {n('missing')}")
        self.nb.select(0 if n("new") else (1 if n("changed") else 0))

    def _fill(self, res):
        fnames = {f["id"]: f["name"] for f in self.store.fields(self.cid())}
        self.items = {"new": res["new"], "changed": res["changed"], "missing": res["missing"],
                      "same": res["same"],
                      "issue": [dict(i, why="Telefon yok/geçersiz") for i in res["nokey"]] +
                               [dict(i, why="Dosyada tekrar") for i in res["dup"]]}
        for kind, label in self.TABS:
            tree = self.trees[kind]
            tree.delete(*tree.get_children())
            for idx, it in enumerate(self.items[kind]):
                if kind == "new":
                    detail = "; ".join(f"{fnames[int(k)]}: {v}" for k, v in it["data"].items()
                                       if int(k) != self.key_fid and fnames.get(int(k)))
                elif kind == "changed":
                    detail = "; ".join(f"{n}: {o or '(boş)'} → {nw}" for _f, n, o, nw in it["diffs"])
                elif kind == "missing":
                    detail = it["rec"]["category"]
                elif kind == "issue":
                    detail = it["why"] + " — " + "; ".join(str(v) for v in it["data"].values())
                else:
                    detail = ""
                tree.insert("", "end", iid=str(idx), values=(it["title"], it["phone"], detail))
            self.nb.tab(list(self.trees).index(kind), text=f"{label} ({len(self.items[kind])})")

    def _selected(self, kind, everything):
        tree = self.trees[kind]
        ids = tree.get_children() if everything else tree.selection()
        return [self.items[kind][int(i)] for i in ids]

    def _after_change(self, msg):
        self.app.refresh_categories()
        self.app.refresh()
        self.run_compare()
        self.summary.config(text=msg + "   |   " + self.summary.cget("text"))

    def do_add(self, everything):
        its = self._selected("new", everything)
        if its and messagebox.askyesno(APP_TITLE, f"{len(its)} yeni kişi panele eklensin mi?", parent=self):
            n = listsync.add_new(self.store, self.cid(), its)
            self._after_change(f"{n} kişi eklendi.")

    def do_add_nokey(self):
        its = [i for i in self._selected("issue", False) if i.get("why") == "Telefon yok/geçersiz"]
        if its and messagebox.askyesno(APP_TITLE, f"{len(its)} telefonsuz kişi yine de eklensin mi?\n"
                                                  "(Sonraki karşılaştırmada tanınmayacaklar.)", parent=self):
            n = listsync.add_new(self.store, self.cid(), its)
            self._after_change(f"{n} kişi eklendi.")

    def do_update(self, everything):
        its = self._selected("changed", everything)
        if its and messagebox.askyesno(APP_TITLE, f"{len(its)} kişinin bilgileri dosyadaki değerlerle "
                                                  "güncellensin mi?", parent=self):
            n = listsync.apply_changes(self.store, its)
            self._after_change(f"{n} kişi güncellendi.")

    def export_missing(self):
        its = self.items.get("missing", [])
        if not its:
            messagebox.showinfo(APP_TITLE, "Listede olmayan kişi yok.", parent=self)
            return
        p = filedialog.asksaveasfilename(parent=self, defaultextension=".csv", initialfile="listede-yok.csv",
                                         filetypes=[("CSV (Excel)", "*.csv")])
        if p:
            listsync.write_csv(p, ["Kişi", "Telefon", "Kategori"],
                               [[i["title"], i["phone"], i["rec"]["category"]] for i in its])
            messagebox.showinfo(APP_TITLE, "Kaydedildi.", parent=self)

    # -- izleme ayarları ---------------------------------------------------- #
    def _save_watch(self):
        s = self.store
        if self.watch_var.get():
            try:
                mins = max(1, int(self.min_var.get()))
            except (tk.TclError, ValueError):
                mins = 30
            path = self.path_var.get()
            s.set_setting("watch_path", path)
            s.set_setting("watch_cat", self.cid())
            s.set_setting("watch_map", json.dumps({str(k): v for k, v in self.mapping.items()}))
            s.set_setting("watch_key", self.key_fid)
            s.set_setting("watch_minutes", mins)
            s.set_setting("watch_sig", listsync.file_sig(path))
            self.app.status.config(text=f"Dosya izleniyor: her {mins} dakikada kontrol edilecek.")
        elif s.get_setting("watch_path"):
            s.set_setting("watch_path", "")

    def _load_preset(self):
        s = self.store
        self.cat_var.set(self._cat_name(int(s.get_setting("watch_cat", "0") or 0)))
        self.path_var.set(s.get_setting("watch_path", ""))
        self.watch_var.set(True)
        try:
            self.headers, self.rows = listsync.read_table(self.path_var.get())
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Dosya okunamadı:\n{e}", parent=self)
            self.headers, self.rows = [], []
        key_fid = int(s.get_setting("watch_key", "0") or 0)
        self.key_var.set(next((f["name"] for f in self.store.fields(self.cid()) if f["id"] == key_fid), ""))
        self.build_mapping(keep=True, preset_map=json.loads(s.get_setting("watch_map", "{}")))
        self.run_compare()


# =========================================================================== #
# WhatsApp mesajı (tek kişi veya listelenen herkes)
# =========================================================================== #
class WhatsAppDialog(tk.Toplevel):
    def __init__(self, app, recs):
        super().__init__(app)
        self.app, self.store = app, app.store
        self.targets = []
        for rec in recs:
            opts = whatsapp.phone_options(self.store, rec)
            if opts:
                self.targets.append({"rec": rec, "title": self.store.title(rec), "opts": opts,
                                     "sel": 0, "status": "bekliyor"})
        skipped = len(recs) - len(self.targets)
        if not self.targets:
            messagebox.showinfo(APP_TITLE, "WhatsApp'a uygun cep numarası bulunamadı.\n"
                                           "(Alan adı “Telefon”, “GSM”, “Cep” gibi olmalı; sabit hatlar atlanır.)",
                                parent=app)
            self.destroy()
            return
        t = app.t
        self.title("WhatsApp mesajı")
        self.geometry("820x700")
        self.configure(bg=t["bg"])
        self.transient(app)

        head = f"{len(self.targets)} kişiye mesaj hazırlanacak"
        if skipped:
            head += f"   ({skipped} kayıt atlandı: uygun numara yok)"
        ttk.Label(self, text=head, style="Title.TLabel", padding=(14, 12, 14, 4)).pack(anchor="w")

        tf = ttk.Frame(self, padding=(14, 0))
        tf.pack(fill="x")
        self.tree = ttk.Treeview(tf, columns=("k", "n", "d"), show="headings", selectmode="browse",
                                 height=min(8, max(2, len(self.targets))))
        for col, txt, w in (("k", "Kişi", 260), ("n", "Numara", 200), ("d", "Durum", 120)):
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor="w")
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="x", expand=True)
        vsb.pack(side="right", fill="y")
        for i, tg in enumerate(self.targets):
            self.tree.insert("", "end", iid=str(i), values=(tg["title"], tg["opts"][0][0], tg["status"]))
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.on_select())

        row = ttk.Frame(self, padding=(14, 8, 14, 0))
        row.pack(fill="x")
        row.columnconfigure(1, weight=1)
        ttk.Label(row, text="Numara").grid(row=0, column=0, sticky="w")
        self.num_var = tk.StringVar()
        self.num_cb = ttk.Combobox(row, textvariable=self.num_var, state="readonly")
        self.num_cb.grid(row=0, column=1, sticky="ew", padx=8, pady=2)
        self.num_cb.bind("<<ComboboxSelected>>", lambda e: self.on_number())
        ttk.Label(row, text="Şablon").grid(row=1, column=0, sticky="w")
        self.tpl_var = tk.StringVar()
        self.tpl_cb = ttk.Combobox(row, textvariable=self.tpl_var, state="readonly")
        self.tpl_cb.grid(row=1, column=1, sticky="ew", padx=8, pady=2)
        self.tpl_cb.bind("<<ComboboxSelected>>", lambda e: self.pick_template())
        bb = ttk.Frame(row)
        bb.grid(row=1, column=2)
        ttk.Button(bb, text="Kaydet", command=self.save_template).pack(side="left", padx=2)
        ttk.Button(bb, text="Sil", command=self.del_template).pack(side="left")

        ttk.Label(self, text="Mesaj", style="Muted.TLabel", padding=(14, 8, 14, 2)).pack(anchor="w")
        self.msg = tk.Text(self, height=6, wrap="word", bg=t["entry"], fg=t["fg"], insertbackground=t["fg"],
                           relief="flat", highlightthickness=1, highlightbackground=t["border"],
                           highlightcolor=app.accent, font=(FAMILY, app.font_size))
        self.msg.pack(fill="x", padx=14)
        self.msg.bind("<KeyRelease>", lambda e: self.update_preview())
        ttk.Label(self, style="Muted.TLabel", padding=(14, 2, 14, 6), wraplength=780, justify="left",
                  text="Kullanılabilir alanlar: {ad}  {tam_ad}  ve kategorinizdeki alan adları, ör. {görev}. "
                       "Gizli alanlar (TC, IBAN) mesaja konmaz.").pack(anchor="w")

        ttk.Label(self, text="Önizleme (seçili kişi için)", style="Muted.TLabel",
                  padding=(14, 0, 14, 2)).pack(anchor="w")
        pf = ttk.Frame(self, style="Card.TFrame", padding=10)
        pf.pack(fill="x", padx=14)
        self.preview = ttk.Label(pf, style="Card.TLabel", wraplength=760, justify="left")
        self.preview.pack(anchor="w")

        ttk.Label(self, style="Muted.TLabel", padding=(14, 8, 14, 0), wraplength=780, justify="left",
                  text="WhatsApp, mesaj hazır şekilde açılır; “Gönder”e siz basarsınız. Çok kişiye yazarken "
                       "yalnızca sizinle iletişim kurmayı kabul etmiş kişilere (ör. personel) gönderin; "
                       "istenmeyen toplu mesajlar numaranızın engellenmesine yol açabilir.").pack(anchor="w")
        bar = ttk.Frame(self, padding=14)
        bar.pack(side="bottom", fill="x")
        ttk.Button(bar, text="Kapat", command=self.destroy).pack(side="right")
        if len(self.targets) > 1:
            ttk.Button(bar, text="Sıradakini aç  →", style="Accent.TButton",
                       command=self.open_next).pack(side="right", padx=8)
        ttk.Button(bar, text="Seçiliyi WhatsApp'ta aç", style="Accent.TButton" if len(self.targets) == 1
                   else "TButton", command=self.open_selected).pack(side="right", padx=(0, 8))

        self.templates = self._load_templates()
        self.refresh_templates()
        self.tree.selection_set("0")
        self.on_select()

    # -- şablonlar --------------------------------------------------------- #
    def _load_templates(self):
        try:
            d = json.loads(self.app.cfg("wa_templates", "null"))
            if isinstance(d, dict) and d:
                return d
        except ValueError:
            pass
        return dict(whatsapp.DEFAULT_TEMPLATES)

    def refresh_templates(self, pick=None):
        self.tpl_cb.configure(values=list(self.templates))
        if pick:
            self.tpl_var.set(pick)
            self.msg.delete("1.0", "end")
            self.msg.insert("1.0", self.templates[pick])
            self.update_preview()

    def pick_template(self):
        name = self.tpl_var.get()
        if name in self.templates:
            self.refresh_templates(name)

    def save_template(self):
        text = self.msg.get("1.0", "end-1c").strip()
        if not text:
            return
        name = simpledialog.askstring("Şablonu kaydet", "Şablon adı:", initialvalue=self.tpl_var.get(),
                                      parent=self)
        if name and name.strip():
            self.templates[name.strip()] = text
            self.app.store.set_setting("wa_templates", json.dumps(self.templates, ensure_ascii=False))
            self.refresh_templates(name.strip())

    def del_template(self):
        name = self.tpl_var.get()
        if name in self.templates and messagebox.askyesno(APP_TITLE, f"“{name}” şablonu silinsin mi?",
                                                          parent=self):
            del self.templates[name]
            self.app.store.set_setting("wa_templates", json.dumps(self.templates, ensure_ascii=False))
            self.tpl_var.set("")
            self.refresh_templates()

    # -- seçim / önizleme -------------------------------------------------- #
    def cur(self):
        sel = self.tree.selection()
        return (int(sel[0]), self.targets[int(sel[0])]) if sel else (None, None)

    def on_select(self):
        i, tg = self.cur()
        if tg is None:
            return
        labels = [o[0] for o in tg["opts"]]
        self.num_cb.configure(values=labels)
        self.num_var.set(labels[tg["sel"]])
        self.update_preview()

    def on_number(self):
        i, tg = self.cur()
        if tg is None:
            return
        labels = [o[0] for o in tg["opts"]]
        if self.num_var.get() in labels:
            tg["sel"] = labels.index(self.num_var.get())
            self.tree.set(str(i), "n", labels[tg["sel"]])

    def text_for(self, tg):
        return whatsapp.fill_template(self.msg.get("1.0", "end-1c").strip(), self.store, tg["rec"])

    def update_preview(self):
        i, tg = self.cur()
        if tg is None:
            return
        text = self.text_for(tg)
        warn = "\n\n⚠ Tanınmayan {alan} var, olduğu gibi gönderilir." if "{" in text and "}" in text else ""
        self.preview.config(text=(text or "(mesaj boş)") + warn)

    # -- açma -------------------------------------------------------------- #
    def open_selected(self):
        i, tg = self.cur()
        if tg is None:
            return
        text = self.text_for(tg)
        if not text:
            messagebox.showwarning(APP_TITLE, "Önce bir mesaj yazın.", parent=self)
            return
        number = tg["opts"][tg["sel"]][1]
        whatsapp.open_chat(number, text, self.app.cfg("wa_mode", "web"))
        tg["status"] = "açıldı ✓"
        self.tree.set(str(i), "d", tg["status"])

    def open_next(self):
        i, _tg = self.cur()
        order = list(range(i + 1, len(self.targets))) + list(range(0, (i or 0) + 1))
        nxt = next((j for j in order if self.targets[j]["status"] == "bekliyor"), None)
        if nxt is None:
            messagebox.showinfo(APP_TITLE, "Bekleyen kişi kalmadı.", parent=self)
            return
        self.tree.selection_set(str(nxt))
        self.tree.see(str(nxt))
        self.update_idletasks()
        self.open_selected()


# =========================================================================== #
# Web başvuruları (personelin web formundan gönderdiği bilgiler)
# =========================================================================== #
class WebInboxDialog(tk.Toplevel):
    STATUS = {"new": "Yeni", "changed": "Bilgisi farklı", "same": "Zaten kayıtlı",
              "nokey": "Telefon geçersiz", "dup": "Tekrar başvuru"}
    ACTION = {"new": "eklenecek", "changed": "güncellenecek", "same": "sunucudan silinecek"}

    def __init__(self, app):
        super().__init__(app)
        self.app, self.store = app, app.store
        self.base, self.key = app.cfg("web_url", ""), app.cfg("web_key", "")
        if not self.base or not self.key:
            messagebox.showinfo(APP_TITLE, "Önce Düzen ▸ Ayarlar ▸ Web formu bölümüne site adresini ve "
                                           "API anahtarını girin.", parent=app)
            self.destroy()
            return
        self.cats = self.store.categories()
        if not self.cats:
            self.destroy()
            return
        self.title("Web başvuruları")
        self.geometry("900x640")
        self.configure(bg=app.t["bg"])
        self.transient(app)
        self.items = []

        top = ttk.Frame(self, padding=(14, 12, 14, 4))
        top.pack(fill="x")
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="Kategori").grid(row=0, column=0, sticky="w")
        pref = app.cfg("web_cat", "")
        names = [c["name"] for c in self.cats]
        self.cat_var = tk.StringVar(value=next((n for n in names if n == pref), None) or
                                    next((n for n in names if core.norm(n) == "personel"), names[0]))
        cb = ttk.Combobox(top, textvariable=self.cat_var, state="readonly", values=names)
        cb.grid(row=0, column=1, sticky="ew", padx=8)
        cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Button(top, text="Yenile", style="Accent.TButton", command=self.refresh).grid(row=0, column=2)
        self.info = ttk.Label(self, style="Muted.TLabel", padding=(14, 0), wraplength=860, justify="left")
        self.info.pack(anchor="w")

        tf = ttk.Frame(self, padding=(14, 6))
        tf.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tf, columns=("s", "k", "t", "d"), show="headings", selectmode="extended")
        for col, txt, w in (("s", "Durum", 130), ("k", "Kişi", 200), ("t", "Telefon", 140), ("d", "Gelen bilgiler", 380)):
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=w, anchor="w")
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Control-a>", lambda e: (self.tree.selection_set(self.tree.get_children()), "break")[1])
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.show_detail())

        cardf = ttk.Frame(self, style="Card.TFrame", padding=10)
        cardf.pack(fill="x", padx=14)
        self.detail = ttk.Label(cardf, style="Card.TLabel", wraplength=840, justify="left",
                                text="Ayrıntı için bir başvuru seçin.")
        self.detail.pack(anchor="w")

        bar = ttk.Frame(self, padding=14)
        bar.pack(fill="x")
        ttk.Button(bar, text="Kapat", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="Seçilileri sil (reddet)", command=self.reject).pack(side="right", padx=8)
        ttk.Button(bar, text="Tümünü işle", command=lambda: self.process(True)).pack(side="right")
        ttk.Button(bar, text="Seçilileri işle", style="Accent.TButton",
                   command=lambda: self.process(False)).pack(side="right", padx=8)
        self.after(100, self.refresh)

    def cid(self):
        return next(c["id"] for c in self.cats if c["name"] == self.cat_var.get())

    def refresh(self):
        self.store.set_setting("web_cat", self.cat_var.get())
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            raw = webinbox.list_items(self.base, self.key)
        except Exception as e:
            self.config(cursor="")
            self.info.config(text=f"Başvurular alınamadı: {e}")
            return
        self.config(cursor="")
        headers, rows = webinbox.to_rows(raw)
        cid = self.cid()
        flds = self.store.fields(cid)
        mapping, unmapped = {}, []
        for h in headers:
            f = next((f for f in flds if core.norm(f["name"]) == core.norm(h) and f["id"] not in mapping), None)
            if f:
                mapping[f["id"]] = h
            else:
                unmapped.append(h)
        key_f = next((f for f in flds if "telefon" in core.norm(f["name"])), None)
        self.items = []
        self.tree.delete(*self.tree.get_children())
        msg = f"{len(rows)} başvuru bekliyor."
        if unmapped:
            msg += f"  ⚠ Kategoride karşılığı olmayan form alanları (aktarılmaz): {', '.join(unmapped)}"
        if rows and (key_f is None or key_f["id"] not in mapping):
            self.info.config(text="Bu kategoride “Telefon” alanı ya da formda telefon alanı yok; eşleştirme yapılamıyor.")
            return
        if rows:
            res = listsync.compare(self.store, cid, rows, mapping, key_f["id"])
            order = {r["_id"]: n for n, r in enumerate(rows)}
            for kind in ("new", "changed", "same", "nokey", "dup"):
                for it in res[kind]:
                    it["kind"] = kind
                    self.items.append(it)
            self.items.sort(key=lambda it: order[it["row"]["_id"]])
        fn = {f["id"]: f["name"] for f in flds}
        for idx, it in enumerate(self.items):
            detail = "; ".join(f"{fn[int(k)]}: {v}" for k, v in it["data"].items()
                               if int(k) != (key_f["id"] if key_f else -1) and int(k) in fn)
            self.tree.insert("", "end", iid=str(idx),
                             values=(self.STATUS[it["kind"]], it["title"], it["phone"], detail))
        self.info.config(text=msg)
        self.detail.config(text="Ayrıntı için bir başvuru seçin.")

    def show_detail(self):
        sel = self.tree.selection()
        if len(sel) != 1:
            return
        it = self.items[int(sel[0])]
        lines = [f"{k}: {v}" for k, v in it["row"].items() if not k.startswith("_")]
        lines.append(f"Geldiği zaman (UTC): {it['row'].get('_received', '')}")
        if it["kind"] == "changed":
            lines.append("Panelde farklı olanlar: " + "; ".join(
                f"{n}: {o or '(boş)'} → {nw}" for _f, n, o, nw in it["diffs"]))
        self.detail.config(text="\n".join(lines))

    def _chosen(self, everything):
        ids = self.tree.get_children() if everything else self.tree.selection()
        return [self.items[int(i)] for i in ids]

    def _ack(self, its):
        try:
            webinbox.ack(self.base, self.key, [it["row"]["_id"] for it in its])
            return True
        except Exception as e:
            messagebox.showerror(APP_TITLE, "Kayıtlar işlendi ama sunucudan silinemedi (tekrar yenileyin):\n"
                                            f"{e}", parent=self)
            return False

    def process(self, everything):
        its = [i for i in self._chosen(everything) if i["kind"] in ("new", "changed", "same")]
        if not its:
            messagebox.showinfo(APP_TITLE, "İşlenecek başvuru seçilmedi.\n(Telefonu geçersiz ya da tekrar eden "
                                           "başvurular otomatik işlenmez; bakıp silebilirsiniz.)", parent=self)
            return
        n = {k: sum(1 for i in its if i["kind"] == k) for k in ("new", "changed", "same")}
        if not messagebox.askyesno(APP_TITLE, f"{n['new']} kişi eklenecek, {n['changed']} kişinin bilgisi "
                                              f"güncellenecek, {n['same']} başvuru zaten kayıtlı olduğundan "
                                              "sunucudan silinecek.\n\nDevam edilsin mi?", parent=self):
            return
        cid = self.cid()
        listsync.add_new(self.store, cid, [i for i in its if i["kind"] == "new"])
        listsync.apply_changes(self.store, [i for i in its if i["kind"] == "changed"])
        self._ack(its)
        self.app.refresh_categories()
        self.app.refresh()
        self.refresh()

    def reject(self):
        its = self._chosen(False)
        if its and messagebox.askyesno(APP_TITLE, f"{len(its)} başvuru panele EKLENMEDEN sunucudan "
                                                  "kalıcı olarak silinsin mi?", icon="warning", parent=self):
            self._ack(its)
            self.refresh()


# =========================================================================== #
# Ayarlar
# =========================================================================== #
class SettingsDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app, self.store = app, app.store
        self.title("Ayarlar")
        self.geometry("580x720")
        self.configure(bg=app.t["bg"])
        self.transient(app)
        bar = ttk.Frame(self, padding=(16, 8))
        bar.pack(side="bottom", fill="x")
        sf = ScrollFrame(self)
        sf.pack(fill="both", expand=True)
        sf.canvas.configure(bg=app.t["bg"])
        pad = ttk.Frame(sf.inner, padding=16)
        pad.pack(fill="both", expand=True)

        ttk.Label(pad, text="Görünüm", style="Title.TLabel").pack(anchor="w")
        self.theme = tk.StringVar(value=app.cfg("theme", "acik"))
        row = ttk.Frame(pad)
        row.pack(anchor="w", pady=6)
        ttk.Radiobutton(row, text="Açık tema", value="acik", variable=self.theme).pack(side="left")
        ttk.Radiobutton(row, text="Koyu tema", value="koyu", variable=self.theme).pack(side="left", padx=12)

        self.accent = app.accent
        row = ttk.Frame(pad)
        row.pack(anchor="w", pady=6, fill="x")
        ttk.Label(row, text="Vurgu rengi:").pack(side="left")
        self.acc_btn = tk.Button(row, width=8, bg=self.accent, activebackground=self.accent,
                                 relief="flat", command=self.pick)
        self.acc_btn.pack(side="left", padx=8)

        row = ttk.Frame(pad)
        row.pack(anchor="w", pady=6)
        ttk.Label(row, text="Yazı boyutu:").pack(side="left")
        self.size = tk.IntVar(value=app.font_size)
        ttk.Spinbox(row, from_=8, to=20, width=5, textvariable=self.size).pack(side="left", padx=8)

        ttk.Separator(pad).pack(fill="x", pady=12)
        ttk.Label(pad, text="Yapay zekâ (isteğe bağlı, ücretsiz)", style="Title.TLabel").pack(anchor="w")
        ttk.Label(pad, text="Dahili akıllı arama her zaman çalışır. İsterseniz bilgisayarınızda çalışan "
                            "açık kaynaklı Ollama ile serbest soru sorabilirsiniz. Veriler internete "
                            "çıkmaz; gizli alanlar hiç gönderilmez.", style="Muted.TLabel",
                  wraplength=470, justify="left").pack(anchor="w", pady=4)
        self.ai_on = tk.BooleanVar(value=app.cfg("ollama_enabled", "0") == "1")
        ttk.Checkbutton(pad, text="Ollama'yı kullan", variable=self.ai_on).pack(anchor="w")
        g = ttk.Frame(pad)
        g.pack(fill="x", pady=6)
        g.columnconfigure(1, weight=1)
        self.host = tk.StringVar(value=app.cfg("ollama_host", "http://localhost:11434"))
        self.model = tk.StringVar(value=app.cfg("ollama_model", "llama3.2"))
        ttk.Label(g, text="Adres").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(g, textvariable=self.host).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Label(g, text="Model").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(g, textvariable=self.model).grid(row=1, column=1, sticky="ew", padx=8)
        ttk.Button(g, text="Bağlantıyı dene", command=self.test).grid(row=1, column=2)

        ttk.Separator(pad).pack(fill="x", pady=12)
        ttk.Label(pad, text="WhatsApp", style="Title.TLabel").pack(anchor="w")
        self.wa_mode = tk.StringVar(value=app.cfg("wa_mode", "web"))
        ttk.Radiobutton(pad, text="Tarayıcı üzerinden aç (wa.me) — her zaman çalışır", value="web",
                        variable=self.wa_mode).pack(anchor="w", pady=(4, 0))
        ttk.Radiobutton(pad, text="WhatsApp Masaüstü uygulamasını doğrudan aç (kuruluysa)", value="app",
                        variable=self.wa_mode).pack(anchor="w")

        ttk.Separator(pad).pack(fill="x", pady=12)
        ttk.Label(pad, text="Web formu (personel kendi bilgisini girsin)", style="Title.TLabel").pack(anchor="w")
        g3 = ttk.Frame(pad)
        g3.pack(fill="x", pady=4)
        g3.columnconfigure(1, weight=1)
        self.web_url = tk.StringVar(value=app.cfg("web_url", ""))
        self.web_key = tk.StringVar(value=app.cfg("web_key", ""))
        self.web_code = tk.StringVar(value=app.cfg("web_code", ""))
        ttk.Label(g3, text="Site adresi").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(g3, textvariable=self.web_url).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Label(g3, text="API anahtarı").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(g3, textvariable=self.web_key, show="•").grid(row=1, column=1, sticky="ew", padx=8)
        ttk.Label(g3, text="Davet kodu").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Entry(g3, textvariable=self.web_code).grid(row=2, column=1, sticky="ew", padx=8)
        wb = ttk.Frame(pad)
        wb.pack(anchor="w", pady=4)
        ttk.Button(wb, text="Anahtar üret", command=self.gen_keys).pack(side="left")
        ttk.Button(wb, text="Bağlantıyı dene", command=self.test_web).pack(side="left", padx=6)
        self.web_auto = tk.BooleanVar(value=app.cfg("web_auto", "1") == "1")
        ttk.Checkbutton(pad, text="Yeni başvuru var mı diye her 15 dakikada bir bak",
                        variable=self.web_auto).pack(anchor="w")
        ttk.Label(pad, text="Kurulum: web klasörünü hosta yükleyin, “Anahtar üret”in verdiği iki satırı "
                            "web/config.php'ye yapıştırın. Ayrıntı: web/KURULUM.md", style="Muted.TLabel",
                  wraplength=520, justify="left").pack(anchor="w", pady=(4, 0))

        ttk.Separator(pad).pack(fill="x", pady=12)
        ttk.Label(pad, text="Güncelleme", style="Title.TLabel").pack(anchor="w")
        g2 = ttk.Frame(pad)
        g2.pack(fill="x", pady=4)
        g2.columnconfigure(1, weight=1)
        self.repo = tk.StringVar(value=app.cfg("update_repo", UPDATE_REPO))
        ttk.Label(g2, text="GitHub deposu").grid(row=0, column=0, sticky="w")
        ttk.Entry(g2, textvariable=self.repo).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Label(g2, text="kullaniciadi/depoadi", style="Muted.TLabel").grid(row=0, column=2)
        self.upd_auto = tk.BooleanVar(value=app.cfg("update_auto", "1") == "1")
        ttk.Checkbutton(pad, text="Açılışta günde bir kez yeni sürümü denetle",
                        variable=self.upd_auto).pack(anchor="w")

        ttk.Label(pad, text=f"Veri klasörü: {os.path.dirname(app.store.path)}", style="Muted.TLabel",
                  wraplength=470).pack(anchor="w", pady=(12, 0))
        ttk.Button(bar, text="İptal", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="Kaydet", style="Accent.TButton", command=self.save).pack(side="right", padx=8)

    def gen_keys(self):
        code, key = webinbox.new_keys()
        self.web_code.set(code)
        self.web_key.set(key)
        self.clipboard_clear()
        self.clipboard_append(webinbox.config_lines(code, key))
        messagebox.showinfo(APP_TITLE, "Yeni davet kodu ve anahtar üretildi; şu iki satır panoya kopyalandı:\n\n"
                                       + webinbox.config_lines(code, key) + "\nweb/config.php içinde aynı satırların "
                                       "yerine yapıştırın, sonra Kaydet'e basın.", parent=self)

    def test_web(self):
        try:
            r = webinbox.ping(self.web_url.get(), self.web_key.get().strip())
        except Exception as e:
            messagebox.showwarning("Web formu", f"Bağlanılamadı:\n{e}", parent=self)
            return
        messagebox.showinfo("Web formu", f"Bağlandı. Bekleyen başvuru: {r.get('pending', 0)}\n"
                                         f"Form alanları: {', '.join(r.get('fields', []))}", parent=self)

    def pick(self):
        c = colorchooser.askcolor(color=self.accent, parent=self)[1]
        if c:
            self.accent = c
            self.acc_btn.configure(bg=c, activebackground=c)

    def test(self):
        try:
            models = core.ollama_models(self.host.get())
            messagebox.showinfo("Ollama", "Bağlandı. Yüklü modeller:\n" + ("\n".join(models) or "(yok)"),
                                parent=self)
        except Exception:
            messagebox.showwarning("Ollama bulunamadı",
                                   "Ollama çalışmıyor gibi görünüyor.\n\n1) https://ollama.com adresinden "
                                   "kurun\n2) Komut satırında:  ollama pull llama3.2\n3) Buradan tekrar deneyin.",
                                   parent=self)

    def save(self):
        s = self.store
        s.set_setting("theme", self.theme.get())
        s.set_setting("accent", self.accent)
        try:
            s.set_setting("font_size", max(8, min(20, int(self.size.get()))))
        except (tk.TclError, ValueError):
            pass
        s.set_setting("ollama_enabled", "1" if self.ai_on.get() else "0")
        s.set_setting("ollama_host", self.host.get().strip())
        s.set_setting("ollama_model", self.model.get().strip())
        s.set_setting("wa_mode", self.wa_mode.get())
        s.set_setting("web_url", webinbox.base_url(self.web_url.get()))
        s.set_setting("web_key", self.web_key.get().strip())
        s.set_setting("web_code", self.web_code.get().strip())
        s.set_setting("web_auto", "1" if self.web_auto.get() else "0")
        s.set_setting("update_repo", self.repo.get().strip())
        s.set_setting("update_auto", "1" if self.upd_auto.get() else "0")
        self.app.apply_theme()
        self.app.refresh_categories()
        self.app.refresh()
        self.destroy()


# =========================================================================== #
# Ana pencere
# =========================================================================== #
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.store = core.Store()
        try:
            self.store.auto_backup()
        except Exception:
            pass
        self.title(APP_TITLE)
        self.geometry(self.store.get_setting("geometry", "1150x700"))
        self.minsize(820, 540)
        self.style = ttk.Style(self)
        self.current_cat = None
        self.cat_ids = [None]
        self.rec_by_iid = {}
        self.selected = None
        self.revealed = set()
        self.select_after = None
        self.hints = []
        self._after = None
        self._ai_token = 0
        self._ai_result = None
        self._sort_rev = {}
        self.t = THEMES["acik"]
        self.accent = "#2563eb"
        self.font_size = 10
        self._build()
        self.apply_theme()
        self.refresh_categories()
        self.refresh()
        self.search.focus_set()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._last_watch = 0.0
        self._last_web = 0.0
        self._web_pending = None
        self._web_notified = 0
        self.after(3000, self.watch_tick)
        self.after(8000, self._auto_update)
        self._upd_result = None
        self._inst_result = None

    # -- ayar yardımcıları -------------------------------------------------- #
    def cfg(self, key, default=None):
        return self.store.get_setting(key, default)

    # -- arayüz ------------------------------------------------------------- #
    def _build(self):
        m = tk.Menu(self)
        self.config(menu=m)
        f = tk.Menu(m, tearoff=0)
        m.add_cascade(label="Dosya", menu=f)
        f.add_command(label="Yeni kayıt\tCtrl+N", command=self.new_record)
        f.add_command(label="Dosyadan karşılaştır (Excel, CSV)…", command=lambda: SyncDialog(self))
        f.add_command(label="Web başvuruları…", command=lambda: WebInboxDialog(self))
        f.add_separator()
        f.add_command(label="Yedek al…", command=self.do_backup)
        f.add_command(label="Dışa aktar (JSON)…", command=self.export_json)
        f.add_command(label="Dışa aktar (CSV / Excel)…", command=self.export_csv)
        f.add_command(label="Dışa aktar (yalnızca yapı, kayıtsız şablon)…",
                      command=lambda: self.export_json(False))
        f.add_command(label="İçe aktar (JSON)…", command=self.import_json)
        f.add_separator()
        f.add_command(label="Veri klasörünü aç", command=self.open_data_dir)
        f.add_command(label="Çıkış", command=self.on_close)
        d = tk.Menu(m, tearoff=0)
        m.add_cascade(label="Düzen", menu=d)
        d.add_command(label="Kategorileri ve alanları yönet…", command=lambda: CategoryDialog(self))
        d.add_command(label="Dosyadan karşılaştır / içe aktar (Excel, CSV)…", command=lambda: SyncDialog(self))
        d.add_command(label="Ayarlar…", command=lambda: SettingsDialog(self))
        h = tk.Menu(m, tearoff=0)
        m.add_cascade(label="Yardım", menu=h)
        h.add_command(label="Güncellemeleri denetle…", command=lambda: self.check_updates(True))
        h.add_command(label="Hakkında", command=self.about)

        self.top = ttk.Frame(self, padding=(14, 12, 14, 2))
        self.top.pack(fill="x")
        self.search_var = tk.StringVar()
        self.search = ttk.Entry(self.top, textvariable=self.search_var, style="Search.TEntry")
        self.search.pack(side="left", fill="x", expand=True)
        ttk.Button(self.top, text="✨ Sor", command=self.ask_current).pack(side="left", padx=(8, 0))
        ttk.Button(self.top, text="💬 Toplu mesaj", command=self.bulk_whatsapp).pack(side="left", padx=(8, 0))
        ttk.Button(self.top, text="＋ Yeni kayıt", style="Accent.TButton",
                   command=self.new_record).pack(side="left", padx=(8, 0))
        ttk.Label(self, style="Muted.TLabel", padding=(16, 0, 14, 6),
                  text="Ad, telefon, TC… yazın  ·  Akıllı: “Ahmet'in telefonu” + Enter  ·  "
                       "Hızlı ekle: + Personel | Ad Soyad | 0555…").pack(fill="x")

        self.answer_frame = ttk.Frame(self, style="Card.TFrame", padding=10)
        self.answer_label = ttk.Label(self.answer_frame, style="Card.TLabel", justify="left")
        self.answer_label.pack(side="left", fill="x", expand=True)
        ttk.Button(self.answer_frame, text="✕", width=3, command=self.hide_answer).pack(side="right")
        self.answer_frame.bind("<Configure>",
                               lambda e: self.answer_label.configure(wraplength=max(200, e.width - 70)))

        self.status = ttk.Label(self, style="Muted.TLabel", padding=(14, 4))
        self.status.pack(side="bottom", fill="x")

        self.body = ttk.Frame(self, padding=(14, 0, 14, 0))
        self.body.pack(fill="both", expand=True)

        left = ttk.Frame(self.body)
        left.pack(side="left", fill="y", padx=(0, 12))
        ttk.Label(left, text="Kategoriler", style="Title.TLabel").pack(anchor="w", pady=(0, 6))
        self.cat_list = tk.Listbox(left, exportselection=False, activestyle="none", bd=0,
                                   highlightthickness=1, width=22)
        self.cat_list.pack(fill="both", expand=True)
        self.cat_list.bind("<<ListboxSelect>>", self.on_cat_select)
        ttk.Button(left, text="Kategorileri yönet", command=lambda: CategoryDialog(self)).pack(
            fill="x", pady=(8, 0))

        pw = ttk.PanedWindow(self.body, orient="vertical")
        pw.pack(side="left", fill="both", expand=True)
        tf = ttk.Frame(pw)
        self.tree = ttk.Treeview(tf, show="headings", selectmode="browse")
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        pw.add(tf, weight=3)
        self.detail = ScrollFrame(pw, card=True)
        pw.add(self.detail, weight=2)

        self.search_var.trace_add("write", lambda *a: self.schedule_refresh())
        self.search.bind("<Return>", self.on_enter)
        self.search.bind("<Escape>", lambda e: self.search_var.set(""))
        self.bind("<Control-f>", lambda e: (self.search.focus_set(), self.search.select_range(0, "end")))
        self.bind("<Control-n>", lambda e: self.new_record())
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())
        self.tree.bind("<Delete>", lambda e: self.delete_selected())

    def apply_theme(self):
        t = self.t = THEMES.get(self.cfg("theme", "acik"), THEMES["acik"])
        self.accent = acc = self.cfg("accent", "#2563eb")
        try:
            self.font_size = size = int(self.cfg("font_size", "10"))
        except ValueError:
            self.font_size = size = 10
        for n in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tkfont.nametofont(n).configure(family=FAMILY, size=size)
            except tk.TclError:
                pass
        self.configure(bg=t["bg"])
        s = self.style
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        base = (FAMILY, size)
        s.configure(".", background=t["bg"], foreground=t["fg"], fieldbackground=t["entry"],
                    bordercolor=t["border"], lightcolor=t["bg"], darkcolor=t["bg"],
                    troughcolor=t["bg"], font=base, focuscolor=t["bg"])
        s.configure("TFrame", background=t["bg"])
        s.configure("Card.TFrame", background=t["card"])
        s.configure("TLabel", background=t["bg"], foreground=t["fg"])
        s.configure("Muted.TLabel", background=t["bg"], foreground=t["muted"])
        s.configure("Title.TLabel", background=t["bg"], foreground=t["fg"], font=(FAMILY, size + 1, "bold"))
        s.configure("Card.TLabel", background=t["card"], foreground=t["fg"])
        s.configure("CardMuted.TLabel", background=t["card"], foreground=t["muted"])
        s.configure("CardTitle.TLabel", background=t["card"], foreground=t["fg"],
                    font=(FAMILY, size + 3, "bold"))
        s.configure("TButton", background=t["card"], foreground=t["fg"], padding=(10, 6),
                    bordercolor=t["border"], relief="flat")
        s.map("TButton", background=[("active", t["hover"])])
        s.configure("Accent.TButton", background=acc, foreground="#ffffff", bordercolor=acc, padding=(12, 6))
        s.map("Accent.TButton", background=[("active", shade(acc, 0.85))])
        s.configure("TEntry", padding=6, fieldbackground=t["entry"], foreground=t["fg"],
                    insertcolor=t["fg"], bordercolor=t["border"])
        s.configure("Search.TEntry", padding=9, font=(FAMILY, size + 3))
        s.map("TEntry", bordercolor=[("focus", acc)])
        s.configure("TCombobox", padding=5, fieldbackground=t["entry"], foreground=t["fg"],
                    arrowcolor=t["fg"], background=t["card"])
        s.configure("TSpinbox", padding=4, fieldbackground=t["entry"], foreground=t["fg"],
                    arrowcolor=t["fg"], background=t["card"])
        s.configure("TCheckbutton", background=t["bg"], foreground=t["fg"])
        s.configure("TRadiobutton", background=t["bg"], foreground=t["fg"])
        s.configure("TSeparator", background=t["border"])
        s.configure("Treeview", background=t["card"], fieldbackground=t["card"], foreground=t["fg"],
                    rowheight=int(size * 2.5), borderwidth=0)
        s.map("Treeview", background=[("selected", acc)], foreground=[("selected", "#ffffff")])
        s.configure("Treeview.Heading", background=t["bg"], foreground=t["muted"], relief="flat",
                    font=(FAMILY, size, "bold"), padding=6)
        s.map("Treeview.Heading", background=[("active", t["hover"])])
        s.configure("Vertical.TScrollbar", background=t["border"], troughcolor=t["bg"],
                    bordercolor=t["bg"], arrowcolor=t["fg"])
        s.configure("TPanedwindow", background=t["bg"])
        self.option_add("*TCombobox*Listbox.background", t["entry"])
        self.option_add("*TCombobox*Listbox.foreground", t["fg"])
        self.option_add("*TCombobox*Listbox.selectBackground", acc)
        self.cat_list.configure(bg=t["card"], fg=t["fg"], selectbackground=acc,
                                selectforeground="#ffffff", highlightbackground=t["border"], font=base)
        self.detail.canvas.configure(bg=t["card"])
        if self.selected:
            self.show_detail(self.selected)

    # -- kategoriler -------------------------------------------------------- #
    def refresh_categories(self):
        cats = self.store.categories()
        counts = self.store.count_by_category()
        self.cat_ids = [None] + [c["id"] for c in cats]
        if self.current_cat not in self.cat_ids:
            self.current_cat = None
        self.cat_list.delete(0, "end")
        self.cat_list.insert("end", f"Tümü ({sum(counts.values())})")
        for c in cats:
            self.cat_list.insert("end", f"{c['name']} ({counts.get(c['id'], 0)})")
        self.cat_list.selection_set(self.cat_ids.index(self.current_cat))

    def on_cat_select(self, _e=None):
        s = self.cat_list.curselection()
        if s:
            self.current_cat = self.cat_ids[s[0]]
            self.refresh()

    # -- listeleme / arama -------------------------------------------------- #
    def schedule_refresh(self):
        if self._after:
            self.after_cancel(self._after)
        self._after = self.after(150, self.refresh)

    def refresh(self):
        q = self.search_var.get().strip()
        cid = self.current_cat
        self.hints = []
        note = ""
        if q.startswith("+"):
            results = []
            note = "Hızlı ekleme modu — kaydetmek için Enter'a basın."
        elif q:
            results, self.hints = self.store.search(q, cid)
        else:
            results = [(r, 0) for r in self.store.all_records(cid)]
            results.sort(key=lambda x: core.norm(self.store.title(x[0])))

        flds = self.store.fields(cid) if cid else []
        if cid and flds:
            cols = [f["name"] for f in flds]
        else:
            cols, flds = ["Kategori", "Başlık", "Özet"], None
        ids = [f"c{i}" for i in range(len(cols))]
        self.tree["columns"] = ids
        for i, c in zip(ids, cols):
            self.tree.heading(i, text=c, command=lambda i=i: self.sort_by(i))
            self.tree.column(i, width=130 if flds else (150 if i != "c2" else 380), anchor="w", stretch=True)

        self.tree.delete(*self.tree.get_children())
        self.rec_by_iid = {}
        for rec, _ in results:
            if flds:
                vals = []
                for f in flds:
                    v = str(rec["data"].get(str(f["id"]), "")).replace("\n", " ")
                    vals.append(MASK if (f["sensitive"] and v) else v)
            else:
                rf = self.store.fields(rec["category_id"])
                title = self.store.title(rec, rf)
                summ = " · ".join(str(rec["data"].get(str(f["id"]), "")).replace("\n", " ")
                                  for f in rf if not f["sensitive"]
                                  and str(rec["data"].get(str(f["id"]), "")).strip()
                                  and str(rec["data"].get(str(f["id"]), "")).splitlines()[0] != title)
                vals = [rec["category"], title, summ]
            iid = str(rec["id"])
            self.rec_by_iid[iid] = rec
            self.tree.insert("", "end", iid=iid, values=vals)

        self.status.config(text=note or f"{len(results)} kayıt")
        target = self.select_after
        self.select_after = None
        if target is None and self.selected:
            target = self.selected["id"]
        if target is not None and str(target) in self.rec_by_iid:
            self.tree.selection_set(str(target))
            self.tree.see(str(target))
        else:
            self.show_detail(None)

    def sort_by(self, col):
        rev = self._sort_rev[col] = not self._sort_rev.get(col, True)
        items = sorted(self.tree.get_children(), key=lambda i: core.norm(self.tree.set(i, col)), reverse=rev)
        for idx, iid in enumerate(items):
            self.tree.move(iid, "", idx)

    # -- detay -------------------------------------------------------------- #
    def on_select(self, _e=None):
        sel = self.tree.selection()
        if sel:
            rec = self.rec_by_iid.get(sel[0])
            if not self.selected or self.selected["id"] != rec["id"]:
                self.revealed.clear()
            self.show_detail(rec)

    def show_detail(self, rec):
        self.selected = rec
        inner = self.detail.inner
        for w in inner.winfo_children():
            w.destroy()
        inner.columnconfigure(1, weight=1)
        if not rec:
            ttk.Label(inner, text="Ayrıntıları görmek için bir kayıt seçin.",
                      style="CardMuted.TLabel").grid(row=0, column=0, padx=12, pady=12)
            return
        flds = self.store.fields(rec["category_id"])
        head = ttk.Frame(inner, style="Card.TFrame")
        head.grid(row=0, column=0, columnspan=4, sticky="ew", padx=12, pady=(10, 6))
        ttk.Label(head, text=self.store.title(rec, flds), style="CardTitle.TLabel").pack(side="left")
        ttk.Label(head, text=f"   {rec['category']}", style="CardMuted.TLabel").pack(side="left")
        ttk.Button(head, text="Sil", command=self.delete_selected).pack(side="right")
        ttk.Button(head, text="Düzenle", command=self.edit_selected).pack(side="right", padx=6)
        if whatsapp.phone_options(self.store, rec):
            ttk.Button(head, text="💬 WhatsApp", style="Accent.TButton",
                       command=self.whatsapp_selected).pack(side="right")
        r = 1
        for f in flds:
            v = str(rec["data"].get(str(f["id"]), ""))
            if not v.strip():
                continue
            shown = (not f["sensitive"]) or (rec["id"], f["id"]) in self.revealed
            ttk.Label(inner, text=f["name"], style="CardMuted.TLabel").grid(
                row=r, column=0, sticky="nw", padx=(12, 14), pady=3)
            ttk.Label(inner, text=v if shown else MASK, style="Card.TLabel", wraplength=560,
                      justify="left").grid(row=r, column=1, sticky="nw", pady=3)
            if f["sensitive"]:
                ttk.Button(inner, text="Gizle" if shown else "Göster", width=7,
                           command=lambda f=f: self.toggle_reveal(f)).grid(row=r, column=2, padx=6)
            ttk.Button(inner, text="Kopyala", width=8,
                       command=lambda v=v: self.copy(v)).grid(row=r, column=3, padx=(0, 12))
            r += 1
        ttk.Label(inner, text=f"Oluşturma: {rec['created']}   ·   Güncelleme: {rec['updated']}",
                  style="CardMuted.TLabel").grid(row=r, column=0, columnspan=4, sticky="w", padx=12, pady=(10, 8))

    def toggle_reveal(self, f):
        key = (self.selected["id"], f["id"])
        if key in self.revealed:
            self.revealed.discard(key)
        else:
            self.revealed.add(key)
        self.show_detail(self.selected)

    def copy(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status.config(text="Panoya kopyalandı.")

    # -- kayıt işlemleri ---------------------------------------------------- #
    def new_record(self):
        RecordDialog(self, cat_id=self.current_cat)

    def edit_selected(self):
        if self.selected:
            RecordDialog(self, record=self.selected)

    def delete_selected(self):
        rec = self.selected
        if rec and messagebox.askyesno(APP_TITLE, f"“{self.store.title(rec)}” kaydı silinsin mi?",
                                       icon="warning", parent=self):
            self.store.delete_record(rec["id"])
            self.selected = None
            self.refresh_categories()
            self.refresh()

    # -- akıllı arama / yapay zekâ ------------------------------------------ #
    def on_enter(self, _e=None):
        q = self.search_var.get().strip()
        if q.startswith("+"):
            self.quick_add(q)
        else:
            self.ask(q)

    def ask_current(self):
        self.ask(self.search_var.get().strip())

    def quick_add(self, q):
        try:
            cid, data = self.store.parse_quick_add(q)
            rid = self.store.add_record(cid, data)
        except ValueError as e:
            messagebox.showwarning(APP_TITLE, str(e), parent=self)
            return
        self.search_var.set("")
        self.select_after = rid
        self.refresh_categories()
        self.refresh()
        self.status.config(text="Kayıt eklendi.")

    def show_answer(self, text):
        self.answer_label.config(text=text)
        self.answer_frame.pack(fill="x", padx=14, pady=(0, 6), before=self.body)

    def hide_answer(self):
        self.answer_frame.pack_forget()

    def ask(self, q):
        if not q:
            return
        results, hints = self.store.search(q, self.current_cat)
        base = self.store.offline_answer(results, hints)
        if self.cfg("ollama_enabled", "0") != "1":
            self.show_answer(base)
            return
        self.show_answer(base + "\n\n🤖 Yapay zekâ yanıtı hazırlanıyor…")
        self._ai_token += 1
        token = self._ai_token
        host, model = self.cfg("ollama_host", "http://localhost:11434"), self.cfg("ollama_model", "llama3.2")
        recs = [r for r, _ in results[:10]] or self.store.all_records(None)[:30]
        ctx = self.store.context_lines(recs)

        def worker():
            try:
                ans = "🤖 " + core.ollama_answer(host, model, q, ctx)
            except Exception as e:
                ans = f"(Yapay zekâ kullanılamadı: Ollama çalışıyor mu? — {e.__class__.__name__})"
            if token == self._ai_token:
                self._ai_result = (base, ans)

        threading.Thread(target=worker, daemon=True).start()
        self.after(300, self._poll_ai)

    def _poll_ai(self):
        if self._ai_result:
            base, ans = self._ai_result
            self._ai_result = None
            self.show_answer(base + "\n\n" + ans)
        else:
            self.after(300, self._poll_ai)

    # -- WhatsApp ----------------------------------------------------------- #
    def whatsapp_selected(self):
        if self.selected:
            WhatsAppDialog(self, [self.selected])

    def bulk_whatsapp(self):
        recs = [self.rec_by_iid[i] for i in self.tree.get_children() if i in self.rec_by_iid]
        if not recs:
            messagebox.showinfo(APP_TITLE, "Listede kayıt yok. Önce arama yapın veya bir kategori seçin.",
                                parent=self)
            return
        WhatsAppDialog(self, recs)

    # -- güncelleme --------------------------------------------------------- #
    def _auto_update(self):
        today = datetime.date.today().isoformat()
        repo = (self.cfg("update_repo", UPDATE_REPO) or "").strip()
        if self.cfg("update_auto", "1") == "1" and updater.valid_repo(repo) \
                and self.cfg("update_last") != today:
            self.store.set_setting("update_last", today)
            self.check_updates(False)

    def check_updates(self, manual=True):
        repo = (self.cfg("update_repo", UPDATE_REPO) or "").strip()
        if not updater.valid_repo(repo):
            if manual:
                messagebox.showinfo(APP_TITLE, "Güncelleme için GitHub deposu girilmemiş.\n"
                                               "Düzen ▸ Ayarlar ▸ Güncelleme bölümüne “kullaniciadi/depoadi” yazın.",
                                    parent=self)
            return
        if manual:
            self.status.config(text="Güncellemeler denetleniyor…")
        self._upd_result = None

        def worker():
            try:
                self._upd_result = ("ok", updater.fetch_latest(repo))
            except Exception as e:
                self._upd_result = ("err", e)

        threading.Thread(target=worker, daemon=True).start()
        self.after(400, lambda: self._poll_update(manual))

    def _poll_update(self, manual):
        r = self._upd_result
        if r is None:
            self.after(400, lambda: self._poll_update(manual))
            return
        self._upd_result = None
        kind, data = r
        if kind == "err":
            if manual:
                messagebox.showwarning(APP_TITLE, "Güncelleme denetlenemedi (internet var mı, depo herkese açık mı?)"
                                                  f"\n\n{data}", parent=self)
            return
        if not updater.is_newer(data["version"], VERSION):
            if manual:
                self.status.config(text="Uygulama güncel.")
                messagebox.showinfo(APP_TITLE, f"Güncelsiniz (sürüm {VERSION}).", parent=self)
            return
        notes = (data["notes"] or "").strip()[:700]
        head = f"Yeni sürüm var: {data['version']}   (sizde {VERSION})\n\n{notes}\n\n"
        if getattr(sys, "frozen", False) and data.get("exe_url"):
            if messagebox.askyesno(APP_TITLE, head + "Şimdi indirilip kurulsun mu?\n"
                                                     "Program kapanıp yeniden açılır. Verileriniz korunur.",
                                   parent=self):
                self.do_install(data)
        elif messagebox.askyesno(APP_TITLE, head + "Sürüm sayfası açılsın mı?", parent=self):
            webbrowser.open(data["page"])

    def do_install(self, info):
        self.status.config(text="Güncelleme indiriliyor, lütfen bekleyin…")
        self._inst_result = None

        def worker():
            try:
                updater.install_update(info)
                self._inst_result = ("ok", None)
            except Exception as e:
                self._inst_result = ("err", e)

        threading.Thread(target=worker, daemon=True).start()
        self.after(500, self._poll_install)

    def _poll_install(self):
        r = self._inst_result
        if r is None:
            self.after(500, self._poll_install)
            return
        if r[0] == "ok":
            self.on_close()
        else:
            self.status.config(text="Güncelleme başarısız.")
            messagebox.showerror(APP_TITLE, f"Güncelleme kurulamadı:\n{r[1]}", parent=self)

    # -- liste izleme ("bot") ----------------------------------------------- #
    def web_check_start(self):
        base, key = self.cfg("web_url"), self.cfg("web_key")

        def worker():
            try:
                self._web_pending = webinbox.ping(base, key).get("pending", 0)
            except Exception:
                self._web_pending = None

        threading.Thread(target=worker, daemon=True).start()

    def watch_tick(self):
        try:
            n = self._web_pending
            self._web_pending = None
            if n is not None and n > 0 and n != self._web_notified:
                self._web_notified = n
                self.show_answer(f"🔔 {n} yeni web başvurusu bekliyor — Dosya ▸ Web başvuruları'ndan işleyin.")
            elif n == 0:
                self._web_notified = 0
            if (self.cfg("web_url") and self.cfg("web_key") and self.cfg("web_auto", "1") == "1"
                    and time.time() - self._last_web >= 15 * 60):
                self._last_web = time.time()
                self.web_check_start()
        except Exception:
            pass
        try:
            mins = max(1, int(self.cfg("watch_minutes", "30") or 30))
            if self.cfg("watch_path") and time.time() - self._last_watch >= mins * 60:
                self._last_watch = time.time()
                self.watch_check()
        except Exception:
            pass  # dosya Excel'de açık/kilitli olabilir; sonraki turda tekrar denenir
        self.after(60000, self.watch_tick)

    def watch_check(self):
        path = self.cfg("watch_path")
        if not path or not os.path.exists(path):
            return
        sig = listsync.file_sig(path)
        if sig == self.cfg("watch_sig"):
            return
        _h, rows = listsync.read_table(path)
        mapping = {int(k): v for k, v in json.loads(self.cfg("watch_map", "{}")).items()}
        res = listsync.compare(self.store, int(self.cfg("watch_cat")), rows, mapping,
                               int(self.cfg("watch_key")))
        self.store.set_setting("watch_sig", sig)
        n_new, n_ch = len(res["new"]), len(res["changed"])
        if n_new or n_ch:
            if messagebox.askyesno(APP_TITLE, f"“{os.path.basename(path)}” değişmiş:\n"
                                              f"{n_new} yeni kişi, {n_ch} bilgisi değişmiş kişi var.\n\n"
                                              "Karşılaştırma ekranı açılsın mı?", parent=self):
                SyncDialog(self, preset=True)

    # -- dosya menüsü ------------------------------------------------------- #
    def do_backup(self):
        p = filedialog.asksaveasfilename(parent=self, defaultextension=".db",
                                         initialfile=f"isletme-yedek-{datetime.date.today():%Y%m%d}.db",
                                         filetypes=[("Veritabanı yedeği", "*.db")])
        if p:
            self.store.backup(p)
            messagebox.showinfo(APP_TITLE, "Yedek alındı.", parent=self)

    def export_json(self, with_records=True):
        p = filedialog.asksaveasfilename(parent=self, defaultextension=".json",
                                         initialfile="isletme-" + ("veri" if with_records else "sablon") + ".json",
                                         filetypes=[("JSON", "*.json")])
        if p:
            self.store.export_json(p, with_records)
            messagebox.showinfo(APP_TITLE, "Dışa aktarıldı.", parent=self)

    def export_csv(self):
        p = filedialog.asksaveasfilename(parent=self, defaultextension=".csv", initialfile="isletme.csv",
                                         filetypes=[("CSV (Excel)", "*.csv")])
        if p:
            self.store.export_csv(p, self.current_cat)
            messagebox.showinfo(APP_TITLE, "Dışa aktarıldı. (Excel'de ; ayracıyla açılır)", parent=self)

    def import_json(self):
        p = filedialog.askopenfilename(parent=self, filetypes=[("JSON", "*.json")])
        if not p:
            return
        try:
            n = self.store.import_json(p)
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"İçe aktarılamadı: {e}", parent=self)
            return
        self.refresh_categories()
        self.refresh()
        messagebox.showinfo(APP_TITLE, f"{n} kayıt içe aktarıldı.", parent=self)

    def open_data_dir(self):
        d = os.path.dirname(self.store.path)
        try:
            os.startfile(d)  # Windows
        except AttributeError:
            webbrowser.open("file://" + d)

    def about(self):
        messagebox.showinfo("Hakkında", f"{APP_TITLE} {VERSION}\nAçık kaynak (MIT Lisansı)\n\n"
                                        f"Veri: {self.store.path}", parent=self)

    def on_close(self):
        try:
            self.store.set_setting("geometry", f"{self.winfo_width()}x{self.winfo_height()}")
            self.store.close()
        finally:
            self.destroy()


def main():
    try:  # Windows'ta bulanık yazıyı önle
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App().mainloop()


if __name__ == "__main__":
    main()
