
#!/usr/bin/env python3
# Diego's Chess Wizard
# Tracks Elo ratings, games and skill mastery for my chess class.
#
# pip install customtkinter
# python3 chess_wizard.py

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from functools import partial
from tkinter import font as tkfont

import customtkinter as ctk


APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(APP_DIR, "chess_wizard_data.json")
# old version of the app saved here, load it if the new file doesn't exist yet
OLD_DATA_FILE = os.path.join(APP_DIR, "chess_class_data.json")

START_ELO = 500.0
K = 32.0  # bigger K = ratings move faster. 32 works for beginners

PROFICIENT = 3

MASTERY_NAMES = {
    0: "Not introduced",
    1: "Learning",
    2: "Developing",
    3: "Proficient",
    4: "Mastered",
}

DEFAULT_SKILLS = [
    "Piece movement",
    "Check and checkmate",
    "Castling",
    "En passant",
    "Pawn promotion",
    "Reading notation",
    "Opening principles",
    "Forks",
    "Pins",
    "Skewers",
    "Discovered attacks",
    "Back-rank mate",
    "Queen and king mate",
    "Rook and king mate",
    "Pawn endgames",
]

# colors
PAPER = "#F5EFDF"
BUFF = "#E7DCC0"
SAND = "#DCCFAE"
SAND_HI = "#D0C199"
LINE = "#C9BB96"
INK = "#1F3529"
MOSS = "#5E7360"
BRASS = "#9A7415"
BRASS_FILL = "#DFBA5B"
BRASS_DIM = "#7D5D10"
BRICK = "#9C4530"


# ---- elo ----

def expected_score(ra, rb):
    # chance that A beats B
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


def elo_update(ra, rb, score_a, k=K):
    # score_a is 1 for a win, 0.5 draw, 0 loss
    change = k * (score_a - expected_score(ra, rb))
    return ra + change, rb - change


# ---- data ----

@dataclass
class Student:
    name: str
    elo: float = START_ELO
    peak_elo: float = START_ELO
    wins: int = 0
    losses: int = 0
    draws: int = 0
    skills: dict = field(default_factory=dict)

    @property
    def games_played(self):
        return self.wins + self.losses + self.draws

    @property
    def record(self):
        return f"{self.wins}–{self.losses}–{self.draws}"

    def note_result(self, score):
        if score == 1.0:
            self.wins += 1
        elif score == 0.5:
            self.draws += 1
        else:
            self.losses += 1

    def sync_skills(self, skills):
        for skill in skills:
            self.skills.setdefault(skill, 0)

    def mastered_count(self, skills):
        return sum(1 for s in skills if self.skills.get(s, 0) >= PROFICIENT)


@dataclass
class GameRecord:
    date: str
    white: str
    black: str
    result: str  # white, black or draw
    white_before: float
    black_before: float
    white_after: float
    black_after: float


class ClassData:
    def __init__(self):
        self.students = {}  # keyed by lowercase name
        self.skills = list(DEFAULT_SKILLS)
        self.history = []
        self.load_error = ""

    def save(self, path=DATA_FILE):
        payload = {
            "skills": self.skills,
            "students": [asdict(s) for s in self.students.values()],
            "history": [asdict(g) for g in self.history],
        }
        # write to a temp file and swap so a crash can't wreck the real one
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, path)

    @classmethod
    def load(cls, path=DATA_FILE):
        data = cls()
        if not os.path.exists(path) and os.path.exists(OLD_DATA_FILE):
            path = OLD_DATA_FILE
        if not os.path.exists(path):
            return data

        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            # keep the bad file around instead of starting empty and
            # overwriting it on the next save
            bad = path + ".unreadable"
            try:
                os.replace(path, bad)
                data.load_error = ("Could not read your data file. "
                                   f"Kept as {os.path.basename(bad)}")
            except OSError:
                data.load_error = f"Could not read your data file: {e}"
            return data

        data.skills = payload.get("skills", list(DEFAULT_SKILLS))
        for raw in payload.get("students", []):
            s = Student(**raw)
            s.sync_skills(data.skills)
            data.students[s.name.lower()] = s
        for raw in payload.get("history", []):
            data.history.append(GameRecord(**raw))
        return data

    def add_student(self, name):
        key = name.lower()
        if not name or key in self.students:
            return None
        s = Student(name=name)
        s.sync_skills(self.skills)
        self.students[key] = s
        return s

    def remove_student(self, name):
        self.students.pop(name.lower(), None)

    def get(self, name):
        return self.students.get(name.lower())

    def standings(self):
        return sorted(self.students.values(), key=lambda s: s.elo, reverse=True)

    def names(self):
        return [s.name for s in self.standings()]

    def play_game(self, white, black, result):
        score_white = {"white": 1.0, "draw": 0.5, "black": 0.0}[result]
        w_before, b_before = white.elo, black.elo

        white.elo, black.elo = elo_update(w_before, b_before, score_white)
        white.peak_elo = max(white.peak_elo, white.elo)
        black.peak_elo = max(black.peak_elo, black.elo)
        white.note_result(score_white)
        black.note_result(1.0 - score_white)

        rec = GameRecord(
            date=datetime.now().strftime("%b %d, %Y  %I:%M %p"),
            white=white.name, black=black.name, result=result,
            white_before=w_before, black_before=b_before,
            white_after=white.elo, black_after=black.elo,
        )
        self.history.append(rec)
        return rec

    def skill_gaps(self):
        # (skill, class average, number below proficient), weakest first
        rows = []
        n = len(self.students)
        for skill in self.skills:
            if n == 0:
                rows.append((skill, 0.0, 0))
                continue
            levels = [s.skills.get(skill, 0) for s in self.students.values()]
            below = sum(1 for lv in levels if lv < PROFICIENT)
            rows.append((skill, sum(levels) / n, below))
        rows.sort(key=lambda r: r[1])
        return rows


def pick_font(candidates, fallback):
    installed = set(tkfont.families())
    for name in candidates:
        if name in installed:
            return name
    return fallback


class Checkerboard(ctk.CTkCanvas):
    # little 2 row board in the sidebar
    def __init__(self, master, cols=8, size=15, **kw):
        super().__init__(master, height=size * 2, width=cols * size,
                         highlightthickness=0, bd=0, bg=SAND, **kw)
        for row in range(2):
            for col in range(cols):
                color = PAPER if (row + col) % 2 == 0 else INK
                self.create_rectangle(col * size, row * size,
                                      col * size + size, row * size + size,
                                      fill=color, outline="")


# ---- app ----

class ChessWizardApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.data = ClassData.load()

        self.title("Diego's Chess Wizard")
        self.geometry("1040x680")
        self.minsize(960, 620)
        self.configure(fg_color=BUFF)

        serif = pick_font(["Georgia", "Palatino", "Palatino Linotype",
                           "Book Antiqua", "Times New Roman", "DejaVu Serif"],
                          "Times")
        sans = pick_font(["Segoe UI", "Helvetica Neue", "Helvetica",
                          "Inter", "DejaVu Sans", "Arial"], "Helvetica")

        self.f_eyebrow = ctk.CTkFont(serif, 15, slant="italic")
        self.f_wordmark = ctk.CTkFont(serif, 23, "bold")
        self.f_title = ctk.CTkFont(serif, 27)
        self.f_rating = ctk.CTkFont(serif, 21)
        self.f_rating_big = ctk.CTkFont(serif, 42)
        self.f_nav = ctk.CTkFont(sans, 14)
        self.f_body = ctk.CTkFont(sans, 13)
        self.f_small = ctk.CTkFont(sans, 12)
        self.f_label = ctk.CTkFont(sans, 12, "bold")
        self.f_name = ctk.CTkFont(sans, 15)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.build_sidebar()
        self.build_stage()

        # easy to lose track of where the json went
        print("data file:", DATA_FILE)
        if self.data.load_error:
            self.save_status.configure(text=self.data.load_error,
                                       text_color=BRICK)
        elif self.data.students:
            self.save_status.configure(
                text=f"Loaded {len(self.data.history)} games")

        self.current = ""
        self.show("standings")

    def commit(self):
        # called after every change so nothing gets lost
        try:
            self.data.save()
        except OSError as e:
            self.save_status.configure(
                text="Not saved. Check folder permissions.", text_color=BRICK)
            print("save failed:", e)
        else:
            now = datetime.now().strftime("%I:%M %p").lstrip("0")
            self.save_status.configure(text=f"Saved {now}", text_color=MOSS)

    # layout

    def build_sidebar(self):
        bar = ctk.CTkFrame(self, fg_color=SAND, corner_radius=0, width=232)
        bar.grid(row=0, column=0, sticky="nsew")
        bar.grid_propagate(False)
        bar.grid_rowconfigure(7, weight=1)

        ctk.CTkLabel(bar, text="Diego's", font=self.f_eyebrow,
                     text_color=MOSS).grid(row=0, column=0, sticky="w",
                                           padx=24, pady=(26, 0))
        ctk.CTkLabel(bar, text="Chess Wizard", font=self.f_wordmark,
                     text_color=INK).grid(row=1, column=0, sticky="w",
                                          padx=24, pady=(0, 26))

        self.nav_buttons = {}
        items = [
            ("standings", "Standings"),
            ("record", "Record a game"),
            ("players", "Players"),
            ("skills", "Skills"),
            ("log", "Game log"),
        ]
        for i, (key, label) in enumerate(items):
            btn = ctk.CTkButton(
                bar, text=label, font=self.f_nav, anchor="w",
                height=38, corner_radius=6,
                fg_color="transparent", hover_color=SAND_HI,
                text_color=MOSS, command=partial(self.show, key))
            btn.grid(row=2 + i, column=0, sticky="ew", padx=14, pady=1)
            self.nav_buttons[key] = btn

        foot = ctk.CTkFrame(bar, fg_color="transparent")
        foot.grid(row=8, column=0, sticky="sw", padx=24, pady=(0, 24))
        Checkerboard(foot).pack(anchor="w", pady=(0, 10))
        self.roster_count = ctk.CTkLabel(foot, text="", font=self.f_small,
                                         text_color=MOSS)
        self.roster_count.pack(anchor="w")
        self.save_status = ctk.CTkLabel(foot, text="", font=self.f_small,
                                        text_color=MOSS)
        self.save_status.pack(anchor="w", pady=(2, 0))

    def build_stage(self):
        self.stage = ctk.CTkFrame(self, fg_color=BUFF, corner_radius=0)
        self.stage.grid(row=0, column=1, sticky="nsew")
        self.stage.grid_columnconfigure(0, weight=1)
        self.stage.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(self.stage, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=40, pady=(30, 0))
        head.grid_columnconfigure(0, weight=1)

        self.view_title = ctk.CTkLabel(head, text="", font=self.f_title,
                                       text_color=INK, anchor="w")
        self.view_title.grid(row=0, column=0, sticky="w")

        ctk.CTkFrame(head, height=1, fg_color=LINE).grid(
            row=1, column=0, sticky="ew", pady=(14, 0))

        self.body = ctk.CTkFrame(self.stage, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=40, pady=(18, 30))
        self.body.grid_columnconfigure(0, weight=1)
        self.body.grid_rowconfigure(0, weight=1)

    def show(self, key):
        self.current = key
        for name, btn in self.nav_buttons.items():
            active = name == key
            btn.configure(fg_color=PAPER if active else "transparent",
                          text_color=BRASS if active else MOSS)

        for child in self.body.winfo_children():
            child.destroy()

        # reset row weights or the last view's layout sticks around
        for r in range(4):
            self.body.grid_rowconfigure(r, weight=1 if r == 0 else 0)

        views = {
            "standings": self.view_standings,
            "record": self.view_record,
            "players": self.view_players,
            "skills": self.view_skills,
            "log": self.view_log,
        }
        views[key]()

        n = len(self.data.students)
        self.roster_count.configure(
            text=f"{n} player{'' if n == 1 else 's'} on the roster")

    def set_head(self, title):
        self.view_title.configure(text=title)

    def empty_state(self, message, button_text, goto):
        box = ctk.CTkFrame(self.body, fg_color="transparent")
        box.grid(row=0, column=0)
        ctk.CTkLabel(box, text=message, font=self.f_body,
                     text_color=MOSS).pack(pady=(70, 14))
        ctk.CTkButton(box, text=button_text, font=self.f_nav,
                      fg_color=BRASS, hover_color=BRASS_DIM,
                      text_color=PAPER, height=38, width=180,
                      corner_radius=6,
                      command=partial(self.show, goto)).pack()

    def scroll_list(self, parent):
        # scrollable frame with the colors used everywhere
        return ctk.CTkScrollableFrame(
            parent, fg_color="transparent",
            scrollbar_button_color=LINE, scrollbar_button_hover_color=SAND_HI)

    # standings

    def view_standings(self):
        self.set_head("Standings")

        if not self.data.students:
            self.empty_state("No players yet.", "Add your first player",
                             "players")
            return

        # header columns need to match the row widths below
        header = ctk.CTkFrame(self.body, fg_color="transparent", height=24)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="", width=22).grid(
            row=0, column=0, padx=(14, 0))
        ctk.CTkLabel(header, text="Player", font=self.f_label,
                     text_color=MOSS, anchor="w").grid(
            row=0, column=1, sticky="w", padx=(10, 0))
        cols = [("Rating", 70), ("From start", 80),
                ("W–L–D", 70), ("Skills", 60)]
        for col, (text, width) in enumerate(cols, start=2):
            ctk.CTkLabel(header, text=text, font=self.f_label,
                         text_color=MOSS, anchor="e", width=width).grid(
                row=0, column=col, padx=(0, 18))

        self.body.grid_rowconfigure(0, weight=0)
        self.body.grid_rowconfigure(1, weight=1)

        rows = self.scroll_list(self.body)
        rows.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        rows.grid_columnconfigure(0, weight=1)

        total_skills = len(self.data.skills)
        for i, s in enumerate(self.data.standings(), 1):
            row = ctk.CTkFrame(rows, fg_color=PAPER, corner_radius=6,
                               height=46)
            row.grid(row=i, column=0, sticky="ew", pady=2)
            row.grid_columnconfigure(1, weight=1)
            row.grid_propagate(False)

            ctk.CTkLabel(row, text=str(i), font=self.f_small,
                         text_color=MOSS, width=22, anchor="w").grid(
                row=0, column=0, padx=(14, 0), pady=11)
            ctk.CTkLabel(row, text=s.name, font=self.f_name,
                         text_color=INK, anchor="w").grid(
                row=0, column=1, sticky="w", padx=(10, 0))
            ctk.CTkLabel(row, text=f"{s.elo:.0f}", font=self.f_rating,
                         text_color=BRASS, anchor="e", width=70).grid(
                row=0, column=2, padx=(0, 18))

            delta = s.elo - START_ELO
            if abs(delta) < 0.5:
                color, text = MOSS, "even"
            elif delta > 0:
                color, text = INK, f"+{delta:.0f}"
            else:
                color, text = BRICK, f"{delta:.0f}"
            ctk.CTkLabel(row, text=text, font=self.f_body,
                         text_color=color, anchor="e", width=80).grid(
                row=0, column=3, padx=(0, 18))

            ctk.CTkLabel(row, text=s.record, font=self.f_body,
                         text_color=MOSS, anchor="e", width=70).grid(
                row=0, column=4, padx=(0, 18))
            mastered = s.mastered_count(self.data.skills)
            ctk.CTkLabel(row, text=f"{mastered}/{total_skills}",
                         font=self.f_body, text_color=MOSS, anchor="e",
                         width=60).grid(row=0, column=5, padx=(0, 18))

    # record a game

    def view_record(self):
        self.set_head("Record a game")

        if len(self.data.students) < 2:
            self.empty_state("You need at least two players to record a game.",
                             "Add players", "players")
            return

        wrap = ctk.CTkFrame(self.body, fg_color="transparent")
        wrap.grid(row=0, column=0, sticky="n", pady=(20, 0))

        names = self.data.names()
        self.white_var = ctk.StringVar(value=names[0])
        self.black_var = ctk.StringVar(value=names[1])

        picker = ctk.CTkFrame(wrap, fg_color="transparent")
        picker.pack()

        def side(label, var, col):
            box = ctk.CTkFrame(picker, fg_color=PAPER, corner_radius=8)
            box.grid(row=0, column=col, padx=10)
            ctk.CTkLabel(box, text=label, font=self.f_label,
                         text_color=MOSS).pack(padx=26, pady=(16, 8))
            ctk.CTkOptionMenu(
                box, values=names, variable=var, width=210, height=36,
                font=self.f_body, corner_radius=6,
                fg_color=BUFF, button_color=BUFF,
                button_hover_color=SAND_HI, text_color=INK,
                dropdown_fg_color=PAPER, dropdown_text_color=INK,
                dropdown_hover_color=SAND_HI, dropdown_font=self.f_body,
            ).pack(padx=26, pady=(0, 20))

        side("White", self.white_var, 0)
        ctk.CTkLabel(picker, text="versus", font=self.f_small,
                     text_color=MOSS).grid(row=0, column=1, padx=6)
        side("Black", self.black_var, 2)

        buttons = ctk.CTkFrame(wrap, fg_color="transparent")
        buttons.pack(pady=(28, 0))
        # label, result, bg, text color, border width
        specs = [
            ("White wins", "white", PAPER, INK, 1),
            ("Draw", "draw", SAND, INK, 0),
            ("Black wins", "black", INK, PAPER, 0),
        ]
        for col, (label, result, bg, fg, border) in enumerate(specs):
            ctk.CTkButton(
                buttons, text=label, font=self.f_nav, width=150, height=44,
                corner_radius=6, fg_color=bg, text_color=fg,
                border_width=border, border_color=LINE,
                hover_color=SAND_HI,
                command=partial(self.submit_game, result),
            ).grid(row=0, column=col, padx=6)

        self.result_panel = ctk.CTkFrame(wrap, fg_color="transparent")
        self.result_panel.pack(pady=(30, 0))

    def submit_game(self, result):
        white = self.data.get(self.white_var.get())
        black = self.data.get(self.black_var.get())

        for child in self.result_panel.winfo_children():
            child.destroy()

        if white is None or black is None:
            return
        if white is black:
            ctk.CTkLabel(self.result_panel, text="Pick two different players.",
                         font=self.f_body, text_color=BRICK).pack()
            return

        rec = self.data.play_game(white, black, result)
        self.commit()

        card = ctk.CTkFrame(self.result_panel, fg_color=PAPER,
                            corner_radius=8)
        card.pack()
        card.grid_columnconfigure((0, 1), weight=1)

        pairs = [(rec.white, rec.white_before, rec.white_after),
                 (rec.black, rec.black_before, rec.black_after)]
        for col, (name, before, after) in enumerate(pairs):
            cell = ctk.CTkFrame(card, fg_color="transparent")
            cell.grid(row=0, column=col, padx=34, pady=22)
            delta = after - before
            color = INK if delta > 0 else BRICK if delta < 0 else MOSS
            ctk.CTkLabel(cell, text=name, font=self.f_body,
                         text_color=MOSS).pack()
            ctk.CTkLabel(cell, text=f"{after:.0f}", font=self.f_rating_big,
                         text_color=BRASS).pack(pady=(2, 0))
            ctk.CTkLabel(cell, text=f"{delta:+.1f}", font=self.f_body,
                         text_color=color).pack()

    # players

    def view_players(self):
        self.set_head("Players")

        add = ctk.CTkFrame(self.body, fg_color="transparent")
        add.grid(row=0, column=0, sticky="ew")
        self.body.grid_rowconfigure(0, weight=0)
        self.body.grid_rowconfigure(1, weight=1)

        self.new_name = ctk.CTkEntry(
            add, placeholder_text="Player name", width=280, height=40,
            font=self.f_body, corner_radius=6, fg_color=PAPER,
            border_color=LINE, border_width=1, text_color=INK,
            placeholder_text_color=MOSS)
        self.new_name.grid(row=0, column=0)
        self.new_name.bind("<Return>", lambda e: self.add_player())

        ctk.CTkButton(add, text="Add player", font=self.f_nav, width=130,
                      height=40, corner_radius=6, fg_color=BRASS,
                      hover_color=BRASS_DIM, text_color=PAPER,
                      command=self.add_player).grid(row=0, column=1, padx=10)

        self.player_msg = ctk.CTkLabel(add, text="", font=self.f_small,
                                       text_color=BRICK)
        self.player_msg.grid(row=0, column=2, padx=6)

        rows = self.scroll_list(self.body)
        rows.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        rows.grid_columnconfigure(0, weight=1)

        if not self.data.students:
            ctk.CTkLabel(rows, text="The roster is empty. Add a name above "
                                    "to get started.",
                         font=self.f_body, text_color=MOSS).grid(
                row=0, column=0, pady=50)
            return

        for i, s in enumerate(self.data.standings()):
            row = ctk.CTkFrame(rows, fg_color=PAPER, corner_radius=6,
                               height=46)
            row.grid(row=i, column=0, sticky="ew", pady=2)
            row.grid_columnconfigure(1, weight=1)
            row.grid_propagate(False)

            ctk.CTkLabel(row, text=s.name, font=self.f_name,
                         text_color=INK, anchor="w").grid(
                row=0, column=1, sticky="w", padx=(18, 0), pady=11)
            ctk.CTkLabel(row, text=f"{s.elo:.0f}", font=self.f_rating,
                         text_color=BRASS, width=70, anchor="e").grid(
                row=0, column=2, padx=(0, 16))
            ctk.CTkLabel(row, text=f"{s.games_played} games",
                         font=self.f_body, text_color=MOSS, width=80,
                         anchor="e").grid(row=0, column=3, padx=(0, 16))
            ctk.CTkButton(row, text="Remove", font=self.f_small, width=76,
                          height=28, corner_radius=5, fg_color="transparent",
                          border_width=1, border_color=LINE, text_color=BRICK,
                          hover_color=SAND_HI,
                          command=partial(self.drop_player, s.name)).grid(
                row=0, column=4, padx=(0, 14))

    def add_player(self):
        name = self.new_name.get().strip()
        if not name:
            return
        if self.data.add_student(name) is None:
            self.player_msg.configure(text=f"{name} is already on the roster.")
            return
        self.commit()
        self.show("players")

    def drop_player(self, name):
        self.data.remove_student(name)
        self.commit()
        self.show("players")

    # skills

    def view_skills(self):
        self.set_head("Skills")

        if not self.data.students:
            self.empty_state("No players to assess yet.", "Add players",
                             "players")
            return

        tabs = ctk.CTkTabview(
            self.body, fg_color="transparent", corner_radius=8,
            segmented_button_fg_color=SAND,
            segmented_button_selected_color=BRASS_FILL,
            segmented_button_selected_hover_color=BRASS_FILL,
            segmented_button_unselected_color=SAND,
            segmented_button_unselected_hover_color=SAND_HI,
            text_color=INK, anchor="w")
        tabs.grid(row=0, column=0, sticky="nsew")
        one = tabs.add("One player")
        whole = tabs.add("Whole class")

        self.skills_single(one)
        self.skills_class(whole)

    def skills_single(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(6, 10))

        names = self.data.names()
        self.skill_student = ctk.StringVar(value=names[0])
        ctk.CTkOptionMenu(
            top, values=names, variable=self.skill_student, width=200,
            height=34, font=self.f_body, corner_radius=6,
            fg_color=PAPER, button_color=PAPER,
            button_hover_color=SAND_HI, text_color=INK,
            dropdown_fg_color=PAPER, dropdown_text_color=INK,
            dropdown_hover_color=SAND_HI, dropdown_font=self.f_body,
            command=lambda v: self.render_skill_rows(),
        ).grid(row=0, column=0)

        legend = "  ".join(f"{k} {v.lower()}" for k, v in MASTERY_NAMES.items())
        ctk.CTkLabel(top, text=legend, font=self.f_small,
                     text_color=MOSS).grid(row=0, column=1, padx=20)

        self.skill_rows = self.scroll_list(parent)
        self.skill_rows.grid(row=1, column=0, sticky="nsew")
        self.skill_rows.grid_columnconfigure(0, weight=1)
        self.render_skill_rows()

    def render_skill_rows(self):
        for child in self.skill_rows.winfo_children():
            child.destroy()

        student = self.data.get(self.skill_student.get())
        if student is None:
            return
        student.sync_skills(self.data.skills)

        for i, skill in enumerate(self.data.skills):
            row = ctk.CTkFrame(self.skill_rows, fg_color=PAPER,
                               corner_radius=6)
            row.grid(row=i, column=0, sticky="ew", pady=2)
            row.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(row, text=skill, font=self.f_body, text_color=INK,
                         anchor="w").grid(row=0, column=0, sticky="w",
                                          padx=18, pady=10)

            level = ctk.StringVar(value=str(student.skills.get(skill, 0)))
            ctk.CTkSegmentedButton(
                row, values=["0", "1", "2", "3", "4"], variable=level,
                width=210, height=30, font=self.f_small, corner_radius=5,
                fg_color=BUFF, selected_color=BRASS_FILL,
                selected_hover_color=BRASS_FILL, unselected_color=BUFF,
                unselected_hover_color=SAND_HI, text_color=INK,
                command=partial(self.set_skill, student.name, skill),
            ).grid(row=0, column=1, padx=(0, 14))

    def set_skill(self, student_name, skill, value):
        student = self.data.get(student_name)
        if student is None:
            return
        student.skills[skill] = int(value)
        self.commit()

    def skills_class(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        total = len(self.data.students)
        ctk.CTkLabel(
            parent,
            text="Weakest skills first. These are the gaps worth a lesson.",
            font=self.f_body, text_color=MOSS, anchor="w").grid(
            row=0, column=0, sticky="w", pady=(6, 10))

        rows = self.scroll_list(parent)
        rows.grid(row=1, column=0, sticky="nsew")
        rows.grid_columnconfigure(0, weight=1)

        for i, (skill, avg, below) in enumerate(self.data.skill_gaps()):
            row = ctk.CTkFrame(rows, fg_color=PAPER, corner_radius=6)
            row.grid(row=i, column=0, sticky="ew", pady=2)
            row.grid_columnconfigure(1, weight=1)

            # red when more than half the class is below proficient
            urgent = below > total / 2
            ctk.CTkLabel(row, text=skill, font=self.f_body,
                         text_color=INK, anchor="w", width=200).grid(
                row=0, column=0, sticky="w", padx=18, pady=10)

            bar = ctk.CTkProgressBar(
                row, width=220, height=8, corner_radius=4, fg_color=BUFF,
                progress_color=BRICK if urgent else BRASS)
            bar.set(avg / 4.0)
            bar.grid(row=0, column=1, sticky="w")

            ctk.CTkLabel(row, text=f"avg {avg:.1f}", font=self.f_small,
                         text_color=MOSS, width=60, anchor="e").grid(
                row=0, column=2, padx=(14, 0))
            ctk.CTkLabel(row, text=f"{below} of {total} below proficient",
                         font=self.f_small,
                         text_color=BRICK if urgent else MOSS,
                         width=170, anchor="e").grid(
                row=0, column=3, padx=(10, 16))

    # game log

    def view_log(self):
        self.set_head("Game log")

        if not self.data.history:
            self.empty_state("No games recorded yet.", "Record a game",
                             "record")
            return

        rows = self.scroll_list(self.body)
        rows.grid(row=0, column=0, sticky="nsew")
        rows.grid_columnconfigure(0, weight=1)

        for i, g in enumerate(reversed(self.data.history)):
            row = ctk.CTkFrame(rows, fg_color=PAPER, corner_radius=6)
            row.grid(row=i, column=0, sticky="ew", pady=2)
            row.grid_columnconfigure(1, weight=1)

            if g.result == "draw":
                headline = f"{g.white} and {g.black} drew"
            elif g.result == "white":
                headline = f"{g.white} beat {g.black}"
            else:
                headline = f"{g.black} beat {g.white}"

            ctk.CTkLabel(row, text=headline, font=self.f_body,
                         text_color=INK, anchor="w").grid(
                row=0, column=1, sticky="w", padx=18, pady=11)

            swing = abs(g.white_after - g.white_before)
            ctk.CTkLabel(row, text=f"±{swing:.1f}", font=self.f_small,
                         text_color=MOSS, width=60, anchor="e").grid(
                row=0, column=2, padx=(0, 16))
            ctk.CTkLabel(row, text=g.date, font=self.f_small,
                         text_color=MOSS, width=170, anchor="e").grid(
                row=0, column=3, padx=(0, 16))


def main():
    ctk.set_appearance_mode("light")
    app = ChessWizardApp()
    app.mainloop()


if __name__ == "__main__":
    main()
