"""Internship Tracker - modern edition (CustomTkinter).

Run from source:  python internship_tracker.py
Or run build.bat once to get a real app you can pin to the taskbar.

Data lives in %APPDATA%\\InternshipTracker\\internships.json (Windows)
or ~/.internship_tracker/internships.json (elsewhere).
"""

import json
import os
import shutil
import sys
import uuid
import webbrowser
from datetime import datetime
from math import ceil
from pathlib import Path

import customtkinter as ctk

APP_NAME = "InternshipTracker"
STATUSES = ["Wishlist", "Applied", "Interviewing", "Offer", "Rejected"]
STATUS_COLORS = {
    "Wishlist": "#6B7280",
    "Applied": "#3B82F6",
    "Interviewing": "#F59E0B",
    "Offer": "#10B981",
    "Rejected": "#EF4444",
}
DATE_FMT = "%Y-%m-%d"

# (light, dark) palette
BG = ("#F3F4F8", "#0F1115")
SIDEBAR = ("#FFFFFF", "#14171D")
PANEL = ("#FFFFFF", "#1A1D25")
ITEM = ("#F5F6FA", "#1D212A")
ITEM_HOVER = ("#ECEEF6", "#252A35")
ITEM_SELECTED = ("#E0E7FF", "#2A3052")
INPUT_BG = ("#FFFFFF", "#12151B")
BORDER = ("#E5E7EB", "#2F3542")
TEXT = ("#111827", "#F3F4F6")
MUTED = ("#6B7280", "#9CA3AF")
ACCENT = "#6366F1"
ACCENT_HOVER = "#4F46E5"
DANGER = "#EF4444"
STAR_ON = "#F59E0B"
STAR_OFF = ("#D1D5DB", "#3A4050")

UI_FONT = "Segoe UI" if os.name == "nt" else None


# ---------- paths & data ----------
def resource(name):
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root / name


def app_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def data_dir():
    if os.name == "nt":
        d = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
    else:
        d = Path.home() / ".internship_tracker"
    d.mkdir(parents=True, exist_ok=True)
    return d


DATA_FILE = data_dir() / "internships.json"


def migrate_legacy():
    """Pick up an internships.json from the old version if it sits next to the app."""
    legacy = app_dir() / "internships.json"
    if not DATA_FILE.exists() and legacy.exists():
        try:
            shutil.copy2(legacy, DATA_FILE)
        except OSError:
            pass


def load_data():
    migrate_legacy()
    if not DATA_FILE.exists():
        return [], ""
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("unexpected format")
        for it in data:
            it.setdefault("id", uuid.uuid4().hex)
        return data, ""
    except (json.JSONDecodeError, OSError, ValueError):
        backup = DATA_FILE.with_name("internships.corrupt.json")
        try:
            os.replace(DATA_FILE, backup)
        except OSError:
            pass
        return [], f"Couldn't read your data file. It was kept as {backup.name}."


def save_data(items):
    tmp = DATA_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    os.replace(tmp, DATA_FILE)


# ---------- helpers ----------
def valid_date(s):
    if not s:
        return True
    try:
        datetime.strptime(s, DATE_FMT)
        return True
    except ValueError:
        return False


def nice_date(s):
    try:
        d = datetime.strptime(s, DATE_FMT)
        return f"{d:%b} {d.day}, {d.year}"
    except (TypeError, ValueError):
        return s or ""


def clip(s, n):
    return s if len(s) <= n else s[: n - 1].rstrip() + "\u2026"


class StarRating(ctk.CTkFrame):
    def __init__(self, master, value=3, interactive=True, size=22):
        super().__init__(master, fg_color="transparent")
        self.value = int(value or 0)
        self.labels = []
        for i in range(1, 6):
            lbl = ctk.CTkLabel(self, text="\u2605", width=size + 6,
                               font=ctk.CTkFont(size=size))
            lbl.pack(side="left")
            if interactive:
                lbl.bind("<Button-1>", lambda e=None, n=i: self.set(n))
            self.labels.append(lbl)
        self._paint()

    def set(self, n):
        self.value = n
        self._paint()

    def _paint(self):
        for i, lbl in enumerate(self.labels, 1):
            lbl.configure(text_color=STAR_ON if i <= self.value else STAR_OFF)


# ---------- app ----------
class App(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")
        super().__init__(fg_color=BG)
        self.title("Internship Tracker")
        self.geometry("1080x700")
        self.minsize(940, 580)
        self.after(200, self._set_icon)
        self.after(250, self.focus_set)  # don't start with the search box focused

        self.f_h1 = ctk.CTkFont(family=UI_FONT, size=26, weight="bold")
        self.f_h2 = ctk.CTkFont(family=UI_FONT, size=16)
        self.f_title = ctk.CTkFont(family=UI_FONT, size=14, weight="bold")
        self.f_body = ctk.CTkFont(family=UI_FONT, size=13)
        self.f_small = ctk.CTkFont(family=UI_FONT, size=12)
        self.f_section = ctk.CTkFont(family=UI_FONT, size=14, weight="bold")

        self.items, warning = load_data()
        self.selected_id = None
        self.cards = {}
        self._save_cb = None
        self._cancel_cb = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar(warning)
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.grid(row=0, column=1, sticky="nsew")

        self.bind("<Control-n>", lambda e: self.show_form())
        self.bind("<Control-f>", lambda e: self.search_entry.focus())
        self.bind("<Control-s>", lambda e: self._save_cb and self._save_cb())
        self.bind("<Escape>", lambda e: self._cancel_cb and self._cancel_cb())

        self.refresh_list()
        self.show_empty()

    def _set_icon(self):
        try:
            self.iconbitmap(str(resource("icon.ico")))
        except Exception:
            pass

    # ----- sidebar -----
    def _build_sidebar(self, warning):
        side = ctk.CTkFrame(self, width=340, corner_radius=0, fg_color=SIDEBAR)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)
        side.grid_columnconfigure(0, weight=1)
        side.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(side, text="Internships", font=self.f_h1, text_color=TEXT,
                     anchor="w").grid(row=0, column=0, sticky="w", padx=22, pady=(24, 0))
        self.count_label = ctk.CTkLabel(side, text="", font=self.f_small,
                                        text_color=MUTED, anchor="w")
        self.count_label.grid(row=1, column=0, sticky="w", padx=22, pady=(0, 14))

        ctk.CTkButton(side, text="+  New internship", height=40, corner_radius=10,
                      font=self.f_title, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=lambda: self.show_form()
                      ).grid(row=2, column=0, sticky="ew", padx=20)

        self.search_entry = ctk.CTkEntry(
            side, placeholder_text="Search title or company",
            height=38, corner_radius=10, fg_color=INPUT_BG, border_color=BORDER,
            font=self.f_body)
        self.search_entry.bind("<KeyRelease>", lambda e: self.refresh_list())
        self.search_entry.grid(row=3, column=0, sticky="ew", padx=20, pady=(12, 10))

        self.list_frame = ctk.CTkScrollableFrame(side, fg_color="transparent")
        self.list_frame.grid(row=4, column=0, sticky="nsew", padx=(10, 6), pady=(0, 10))
        self.list_frame.grid_columnconfigure(0, weight=1)

        if warning:
            ctk.CTkLabel(side, text=warning, font=self.f_small, text_color=DANGER,
                         wraplength=290, justify="left").grid(row=5, column=0, padx=20, pady=(0, 12))

    def refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.cards = {}
        q = self.search_entry.get().strip().lower()
        shown = 0
        for it in sorted(self.items, key=lambda i: (i["company"].lower(), i["title"].lower())):
            if q and q not in f"{it['title']} {it['company']}".lower():
                continue
            self._make_card(it, shown)
            shown += 1
        total = len(self.items)
        self.count_label.configure(
            text=f"{total} total" if shown == total else f"{shown} of {total}")
        if shown == 0:
            msg = "No matches." if self.items else "Nothing here yet.\nAdd your first internship."
            ctk.CTkLabel(self.list_frame, text=msg, font=self.f_body, text_color=MUTED,
                         justify="center").grid(row=0, column=0, pady=40)

    def _make_card(self, item, row):
        iid = item["id"]
        card = ctk.CTkFrame(self.list_frame, corner_radius=12, fg_color=self._card_color(iid))
        card.grid(row=row, column=0, sticky="ew", padx=6, pady=3)
        card.grid_columnconfigure(0, weight=1)
        title = ctk.CTkLabel(card, text=clip(item["title"], 32), font=self.f_title,
                             text_color=TEXT, anchor="w")
        title.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 0))
        company = ctk.CTkLabel(card, text=clip(item["company"], 38), font=self.f_small,
                               text_color=MUTED, anchor="w")
        company.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))

        for w in (card, title, company):
            w.bind("<Button-1>", lambda e=None, i=iid: self.select(i))
            w.bind("<Enter>", lambda e=None, i=iid: self._hover(i, True))
            w.bind("<Leave>", lambda e=None, i=iid: self._hover(i, False))
        self.cards[iid] = card

    def _card_color(self, iid):
        return ITEM_SELECTED if iid == self.selected_id else ITEM

    def _inside(self, card):
        try:
            w = self.winfo_containing(*self.winfo_pointerxy())
        except Exception:
            return False
        while w is not None:
            if w is card:
                return True
            w = getattr(w, "master", None)
        return False

    def _hover(self, iid, entering):
        card = self.cards.get(iid)
        if card is None or iid == self.selected_id:
            return
        if entering:
            card.configure(fg_color=ITEM_HOVER)
        elif not self._inside(card):
            card.configure(fg_color=ITEM)

    def select(self, iid):
        item = next((i for i in self.items if i["id"] == iid), None)
        if not item:
            return
        self.selected_id = iid
        for cid, card in self.cards.items():
            card.configure(fg_color=self._card_color(cid))
        self.show_detail(item)

    # ----- main pane plumbing -----
    def clear_main(self):
        self._save_cb = None
        self._cancel_cb = None
        for w in self.main.winfo_children():
            w.destroy()

    def _panel(self):
        panel = ctk.CTkScrollableFrame(self.main, fg_color="transparent")
        panel.pack(fill="both", expand=True, padx=(10, 24), pady=(20, 16))
        panel.grid_columnconfigure(0, weight=1)
        return panel

    def _card(self, parent):
        return ctk.CTkFrame(parent, corner_radius=14, fg_color=PANEL)

    def show_empty(self):
        self.clear_main()
        box = ctk.CTkFrame(self.main, fg_color="transparent")
        box.place(relx=0.5, rely=0.45, anchor="center")
        has_items = bool(self.items)
        ctk.CTkLabel(box, text="Select an internship" if has_items else "Track your first internship",
                     font=self.f_h1, text_color=TEXT).pack()
        ctk.CTkLabel(box, text="Click one on the left to see the details." if has_items
                     else "Hit \u201cNew internship\u201d to get started.",
                     font=self.f_h2, text_color=MUTED).pack(pady=(6, 0))
        ctk.CTkLabel(box, text="Tip: Ctrl+N adds a new one, Ctrl+F searches.",
                     font=self.f_small, text_color=MUTED).pack(pady=(18, 0))

    # ----- detail view -----
    def show_detail(self, item):
        self.clear_main()
        panel = self._panel()

        head = ctk.CTkFrame(panel, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text=item["title"], font=self.f_h1, text_color=TEXT,
                     anchor="w", justify="left", wraplength=520
                     ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(head, text=item["company"], font=self.f_h2, text_color=MUTED,
                     anchor="w").grid(row=1, column=0, sticky="w", pady=(2, 0))

        actions = ctk.CTkFrame(head, fg_color="transparent")
        actions.grid(row=0, column=1, rowspan=2, sticky="ne", padx=(12, 0))
        ctk.CTkButton(actions, text="Edit", width=72, height=34, corner_radius=8,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER, font=self.f_body,
                      command=lambda: self.show_form(item)).pack(side="left", padx=(0, 8))
        self._delete_btn = ctk.CTkButton(
            actions, text="Delete", width=72, height=34, corner_radius=8, font=self.f_body,
            fg_color="transparent", border_width=1, border_color=BORDER,
            text_color=DANGER, hover_color=("#FEE2E2", "#3A1D1F"),
            command=lambda: self._confirm_delete(item))
        self._delete_btn.pack(side="left")

        status = item.get("status", "Wishlist")
        meta = ctk.CTkFrame(panel, fg_color="transparent")
        meta.grid(row=1, column=0, sticky="w", pady=(0, 16))
        ctk.CTkLabel(meta, text=status, font=self.f_title, text_color="white",
                     fg_color=STATUS_COLORS.get(status, "#6B7280"), corner_radius=14,
                     height=28, width=100).pack(side="left")
        ctk.CTkLabel(meta, text="How much I want it", font=self.f_small, text_color=MUTED
                     ).pack(side="left", padx=(24, 8))
        StarRating(meta, item.get("rating", 0), interactive=False, size=20).pack(side="left")

        facts = self._card(panel)
        facts.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        facts.grid_columnconfigure((0, 1), weight=1, uniform="f")
        dates = ""
        if item.get("start_date") or item.get("end_date"):
            dates = f"{nice_date(item.get('start_date')) or '?'}  \u2192  {nice_date(item.get('end_date')) or '?'}"
        cells = [
            ("Date applied", nice_date(item.get("date_applied"))),
            ("Internship dates", dates),
            ("Location", item.get("location", "")),
            ("Contact", item.get("contact", "")),
        ]
        for idx, (label, value) in enumerate(cells):
            self._fact(facts, label, value, idx // 2, idx % 2)

        link = item.get("link", "")
        cell = ctk.CTkFrame(facts, fg_color="transparent")
        cell.grid(row=2, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 14))
        ctk.CTkLabel(cell, text="Link", font=self.f_small, text_color=MUTED, anchor="w").pack(anchor="w")
        if link:
            url = link if link.lower().startswith(("http://", "https://")) else "https://" + link
            ctk.CTkButton(cell, text=clip(link, 70) + "  \u2197", anchor="w", height=24,
                          fg_color="transparent", hover_color=ITEM_HOVER, text_color=ACCENT,
                          font=self.f_body, command=lambda: webbrowser.open(url)
                          ).pack(anchor="w", pady=(2, 0))
        else:
            ctk.CTkLabel(cell, text="\u2014", font=self.f_body, text_color=TEXT).pack(anchor="w")

        row = 3
        for heading, key, empty in (("Job description", "description", "No description added."),
                                    ("Notes", "notes", None)):
            text = item.get(key, "")
            if not text and empty is None:
                continue
            sec = self._card(panel)
            sec.grid(row=row, column=0, sticky="ew", pady=(0, 14))
            sec.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(sec, text=heading, font=self.f_section, text_color=TEXT, anchor="w"
                         ).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 6))
            lines = sum(max(1, ceil(len(l) / 80)) for l in (text or empty).split("\n"))
            box = ctk.CTkTextbox(sec, height=min(320, max(44, lines * 21 + 14)), wrap="word",
                                 fg_color="transparent", font=self.f_body,
                                 text_color=TEXT if text else MUTED, border_width=0)
            box.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))
            box.insert("1.0", text or empty)
            box.configure(state="disabled")
            row += 1

    def _fact(self, parent, label, value, r, c):
        cell = ctk.CTkFrame(parent, fg_color="transparent")
        cell.grid(row=r, column=c, sticky="nw", padx=20, pady=(14, 14 if r else 0))
        ctk.CTkLabel(cell, text=label, font=self.f_small, text_color=MUTED, anchor="w").pack(anchor="w")
        ctk.CTkLabel(cell, text=value or "\u2014", font=self.f_body, text_color=TEXT,
                     anchor="w", justify="left", wraplength=260).pack(anchor="w", pady=(2, 0))

    def _confirm_delete(self, item):
        btn = self._delete_btn
        if btn.cget("text") == "Delete":
            btn.configure(text="Sure?", fg_color=DANGER, text_color="white", hover_color="#DC2626")
            self.after(3000, lambda: btn.winfo_exists() and btn.configure(
                text="Delete", fg_color="transparent", text_color=DANGER,
                hover_color=("#FEE2E2", "#3A1D1F")))
            return
        self.items.remove(item)
        save_data(self.items)
        self.selected_id = None
        self.refresh_list()
        self.show_empty()

    # ----- add / edit form -----
    def show_form(self, item=None):
        self.clear_main()
        editing = item is not None
        orig = item
        item = item or {}
        panel = self._panel()

        ctk.CTkLabel(panel, text="Edit internship" if editing else "New internship",
                     font=self.f_h1, text_color=TEXT, anchor="w"
                     ).grid(row=0, column=0, sticky="w", pady=(0, 14))
        card = self._card(panel)
        card.grid(row=1, column=0, sticky="ew")
        card.grid_columnconfigure((0, 1), weight=1, uniform="c")

        entries = {}

        def add(parent, key, label, row, col, span=1, placeholder="", padx=(18, 18)):
            wrap = ctk.CTkFrame(parent, fg_color="transparent")
            wrap.grid(row=row, column=col, columnspan=span, sticky="ew", padx=padx, pady=(14, 0))
            ctk.CTkLabel(wrap, text=label, font=self.f_small, text_color=MUTED, anchor="w").pack(fill="x")
            ent = ctk.CTkEntry(wrap, placeholder_text=placeholder, height=38, corner_radius=8,
                               fg_color=INPUT_BG, border_color=BORDER, font=self.f_body)
            ent.pack(fill="x", pady=(4, 0))
            if item.get(key):
                ent.insert(0, item[key])
            entries[key] = ent

        add(card, "title", "Internship title *", 0, 0, placeholder="e.g. Software Engineering Intern")
        add(card, "company", "Company *", 0, 1)
        add(card, "location", "Location", 1, 0)
        add(card, "contact", "Contact person", 1, 1)

        dates = ctk.CTkFrame(card, fg_color="transparent")
        dates.grid(row=2, column=0, columnspan=2, sticky="ew")
        dates.grid_columnconfigure((0, 1, 2), weight=1, uniform="d")
        add(dates, "date_applied", "Date applied", 0, 0, placeholder="YYYY-MM-DD", padx=(18, 8))
        add(dates, "start_date", "Internship start", 0, 1, placeholder="YYYY-MM-DD", padx=(8, 8))
        add(dates, "end_date", "Internship end", 0, 2, placeholder="YYYY-MM-DD", padx=(8, 18))

        add(card, "link", "Link to posting", 3, 0, span=2, placeholder="https://")

        sr = ctk.CTkFrame(card, fg_color="transparent")
        sr.grid(row=4, column=0, columnspan=2, sticky="ew", padx=18, pady=(16, 0))
        sr.grid_columnconfigure(0, weight=1)
        left = ctk.CTkFrame(sr, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(left, text="Status", font=self.f_small, text_color=MUTED, anchor="w").pack(anchor="w")
        status = ctk.CTkSegmentedButton(left, values=STATUSES, height=34, font=self.f_body,
                                        selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
                                        fg_color=("#E5E7EB", "#2A2F3A"),
                                        unselected_color=("#E5E7EB", "#2A2F3A"),
                                        unselected_hover_color=("#D8DBE3", "#353B48"),
                                        text_color=TEXT)
        status.pack(anchor="w", pady=(4, 0))
        cur = item.get("status", "Wishlist")
        status.set(cur if cur in STATUSES else "Wishlist")
        right = ctk.CTkFrame(sr, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e", padx=(16, 0))
        ctk.CTkLabel(right, text="How much I want it", font=self.f_small, text_color=MUTED,
                     anchor="w").pack(anchor="w")
        stars = StarRating(right, item.get("rating", 3), interactive=True, size=24)
        stars.pack(anchor="w", pady=(2, 0))

        boxes = {}
        for r, (key, label, h) in enumerate((("description", "Job description", 150),
                                             ("notes", "Notes", 100)), start=5):
            wrap = ctk.CTkFrame(card, fg_color="transparent")
            wrap.grid(row=r, column=0, columnspan=2, sticky="ew", padx=18, pady=(14, 0))
            ctk.CTkLabel(wrap, text=label, font=self.f_small, text_color=MUTED, anchor="w").pack(fill="x")
            tb = ctk.CTkTextbox(wrap, height=h, corner_radius=8, wrap="word", border_width=1,
                                fg_color=INPUT_BG, border_color=BORDER, font=self.f_body,
                                text_color=TEXT)
            tb.pack(fill="x", pady=(4, 0))
            tb.insert("1.0", item.get(key, ""))
            boxes[key] = tb
        ctk.CTkFrame(card, height=18, fg_color="transparent").grid(row=7, column=0)

        bar = ctk.CTkFrame(panel, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        error = ctk.CTkLabel(bar, text="", font=self.f_small, text_color=DANGER)

        def cancel():
            if editing:
                self.show_detail(orig)
            else:
                self.show_empty()

        def save():
            data = {k: w.get().strip() for k, w in entries.items()}
            data["description"] = boxes["description"].get("1.0", "end").strip()
            data["notes"] = boxes["notes"].get("1.0", "end").strip()
            data["status"] = status.get()
            data["rating"] = stars.value
            if not data["title"] or not data["company"]:
                error.configure(text="Title and company are required.")
                return
            for key, label in (("date_applied", "Date applied"), ("start_date", "Internship start"),
                               ("end_date", "Internship end")):
                if not valid_date(data[key]):
                    error.configure(text=f"{label} should look like 2026-06-01.")
                    return
            if editing:
                orig.update(data)
                record = orig
            else:
                record = {"id": uuid.uuid4().hex, **data}
                self.items.append(record)
            save_data(self.items)
            self.search_entry.delete(0, "end")
            self.refresh_list()
            self.select(record["id"])

        self._save_cb, self._cancel_cb = save, cancel
        ctk.CTkButton(bar, text="Save", width=110, height=38, corner_radius=8, font=self.f_title,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER, command=save).pack(side="left")
        ctk.CTkButton(bar, text="Cancel", width=90, height=38, corner_radius=8, font=self.f_body,
                      fg_color="transparent", border_width=1, border_color=BORDER,
                      text_color=TEXT, hover_color=ITEM_HOVER, command=cancel
                      ).pack(side="left", padx=10)
        error.pack(side="left", padx=10)
        entries["title"].focus()


def main():
    if os.name == "nt":
        try:  # lets Windows show our own icon on the taskbar instead of Python's
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Pete.InternshipTracker")
        except Exception:
            pass
    App().mainloop()


if __name__ == "__main__":
    main()
