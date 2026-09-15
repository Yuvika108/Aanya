"""
AANYA — Personal AI Voice Desktop Assistant
Tailwind Sky-Blue Theme · Heroicon Vector Icons
"""

import subprocess
import threading
import datetime
import math
import os
from PIL import Image, ImageDraw

# pyrefly: ignore [missing-import]
import customtkinter as ctk
from main import AanyaEngine, SITES

# ─────────────────────────────────────────────
#  Design System  (Tailwind Slate / Sky palette)
# ─────────────────────────────────────────────
BG_DARK       = "#090d16"
BG_PANEL      = "#0f172a"
BG_CARD       = "#1e293b"
BG_INPUT      = "#1e293b"
BORDER_SUBTLE = "#334155"

ACCENT_SKY       = "#38bdf8"   # Sky 400 — primary
ACCENT_SKY_HOVER = "#0284c7"   # Sky 600
ACCENT_SKY_DARK  = "#0c4a6e"   # Sky 900
ACCENT_EMERALD   = "#10b981"   # Emerald 500 — listening
ACCENT_CYAN      = "#06b6d4"   # Cyan 500 — speaking
ACCENT_CRIMSON   = "#f43f5e"   # Rose 500 — destructive
ACCENT_AMBER     = "#f59e0b"   # Amber 500 — executing

TEXT_PRIMARY   = "#f8fafc"
TEXT_SECONDARY = "#94a3b8"
TEXT_DIM       = "#64748b"

FONT = "SF Pro Display"

STATE_CONFIG = {
    "standby":   {"colour": TEXT_DIM,      "label": "●  Standby",      "dot": TEXT_DIM},
    "listening": {"colour": ACCENT_EMERALD, "label": "●  Listening...", "dot": ACCENT_EMERALD},
    "thinking":  {"colour": ACCENT_SKY,    "label": "●  Thinking...",  "dot": ACCENT_SKY},
    "speaking":  {"colour": ACCENT_CYAN,   "label": "●  Speaking...",  "dot": ACCENT_CYAN},
    "executing": {"colour": ACCENT_AMBER,  "label": "●  Processing...", "dot": ACCENT_AMBER},
}


# ─────────────────────────────────────────────
#  Icon Engine  (Heroicon / Lucide vector style)
# ─────────────────────────────────────────────
def _hex_to_rgba(hex_str: str) -> tuple:
    h = hex_str.lstrip("#")
    if len(h) == 6:
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) + (255,)
    return (248, 250, 252, 255)


def _draw_icon(draw: ImageDraw.ImageDraw, name: str, c, cx: float, cy: float, s: int):
    """Draw a single Heroicon-style vector shape.  s = scale factor."""
    lw = max(2, s * 2)

    ops = {
        "mic": lambda: [
            draw.rounded_rectangle([cx-4*s, cy-8*s, cx+4*s, cy+2*s], radius=3*s, outline=c, width=lw),
            draw.arc([cx-7*s, cy-4*s, cx+7*s, cy+5*s], 0, 180, fill=c, width=lw),
            draw.line([cx, cy+5*s, cx, cy+9*s], fill=c, width=lw),
            draw.line([cx-4*s, cy+9*s, cx+4*s, cy+9*s], fill=c, width=lw),
        ],
        "send": lambda: [
            draw.line([cx-6*s, cy, cx+6*s, cy], fill=c, width=lw),
            draw.line([cx+2*s, cy-5*s, cx+6*s, cy], fill=c, width=lw),
            draw.line([cx+2*s, cy+5*s, cx+6*s, cy], fill=c, width=lw),
        ],
        "search": lambda: [
            draw.ellipse([cx-7*s, cy-7*s, cx+2*s, cy+2*s], outline=c, width=lw),
            draw.line([cx+1*s, cy+1*s, cx+7*s, cy+7*s], fill=c, width=lw),
        ],
        "globe": lambda: [
            draw.ellipse([cx-7*s, cy-7*s, cx+7*s, cy+7*s], outline=c, width=lw),
            draw.line([cx-7*s, cy, cx+7*s, cy], fill=c, width=lw),
            draw.ellipse([cx-3.5*s, cy-7*s, cx+3.5*s, cy+7*s], outline=c, width=lw),
        ],
        "play": lambda: [draw.polygon([(cx-4*s, cy-6*s), (cx+6*s, cy), (cx-4*s, cy+6*s)], fill=c)],
        "code": lambda: [
            draw.line([cx-2*s, cy-6*s, cx-7*s, cy], fill=c, width=lw),
            draw.line([cx-7*s, cy, cx-2*s, cy+6*s], fill=c, width=lw),
            draw.line([cx+2*s, cy-6*s, cx+7*s, cy], fill=c, width=lw),
            draw.line([cx+7*s, cy, cx+2*s, cy+6*s], fill=c, width=lw),
        ],
        "music": lambda: [
            draw.ellipse([cx-7*s, cy+2*s, cx-2*s, cy+6*s], fill=c),
            draw.line([cx-2*s, cy+4*s, cx-2*s, cy-6*s], fill=c, width=lw),
            draw.line([cx-2*s, cy-6*s, cx+5*s, cy-3*s], fill=c, width=lw),
        ],
        "book": lambda: [
            draw.rectangle([cx-7*s, cy-6*s, cx-1*s, cy+5*s], outline=c, width=lw),
            draw.rectangle([cx+1*s, cy-6*s, cx+7*s, cy+5*s], outline=c, width=lw),
        ],
        "folder": lambda: [
            draw.rounded_rectangle([cx-7*s, cy-5*s, cx+7*s, cy+6*s], radius=2*s, outline=c, width=lw),
            draw.line([cx-7*s, cy-2*s, cx-2*s, cy-2*s], fill=c, width=lw),
        ],
        "chrome": lambda: [
            draw.ellipse([cx-7*s, cy-7*s, cx+7*s, cy+7*s], outline=c, width=lw),
            draw.ellipse([cx-3*s, cy-3*s, cx+3*s, cy+3*s], fill=c),
        ],
        "close": lambda: [
            draw.line([cx-5*s, cy-5*s, cx+5*s, cy+5*s], fill=c, width=lw),
            draw.line([cx+5*s, cy-5*s, cx-5*s, cy+5*s], fill=c, width=lw),
        ],
        "refresh": lambda: [
            draw.arc([cx-6*s, cy-6*s, cx+6*s, cy+6*s], 30, 330, fill=c, width=lw),
            draw.polygon([(cx+3*s, cy-7*s), (cx+7*s, cy-4*s), (cx+3*s, cy-2*s)], fill=c),
        ],
    }
    ops.get(name, lambda: [draw.ellipse([cx-4*s, cy-4*s, cx+4*s, cy+4*s], fill=c)])()


def make_icon(name: str, color: str = TEXT_SECONDARY, size=(20, 20)) -> ctk.CTkImage:
    """Return a CTkImage rendered at 2× for sharpness, cached on the token key."""
    key = (name, color, size)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]

    scale = 2
    w, h = size[0] * scale, size[1] * scale
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    c_rgba = _hex_to_rgba(color) if isinstance(color, str) else color
    _draw_icon(draw, name, c_rgba, w / 2, h / 2, scale)
    img = img.resize(size, Image.Resampling.LANCZOS)
    result = ctk.CTkImage(light_image=img, dark_image=img, size=size)
    _ICON_CACHE[key] = result
    return result

_ICON_CACHE: dict = {}


# ─────────────────────────────────────────────
#  Chat Bubble
# ─────────────────────────────────────────────
class ChatBubble(ctk.CTkFrame):
    def __init__(self, master, text: str, sender: str = "aanya", **kw):
        super().__init__(master, fg_color="transparent", **kw)
        is_user      = sender == "user"
        bubble_bg    = ACCENT_SKY_DARK if is_user else BG_PANEL
        border_color = ACCENT_SKY      if is_user else BORDER_SUBTLE
        avatar_color = ACCENT_SKY      if is_user else ACCENT_CYAN
        avatar_text  = "YOU"           if is_user else "AANYA"
        side         = "right"         if is_user else "left"
        padx         = (80, 0)         if is_user else (0, 80)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=6)

        bubble = ctk.CTkFrame(row, fg_color=bubble_bg, corner_radius=14,
                              border_width=1, border_color=border_color)
        bubble.pack(side=side, padx=padx)

        # Name + timestamp row
        meta = ctk.CTkFrame(bubble, fg_color="transparent")
        meta.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(meta, text=avatar_text,
                     font=(FONT, 10, "bold"), text_color=avatar_color).pack(side="left")
        ctk.CTkLabel(meta, text=datetime.datetime.now().strftime("%H:%M"),
                     font=(FONT, 10), text_color=TEXT_DIM).pack(side="right")

        # Body
        ctk.CTkLabel(bubble, text=text, font=(FONT, 13), text_color=TEXT_PRIMARY,
                     wraplength=440, justify="left", anchor="w"
                     ).pack(padx=16, pady=(0, 14), anchor="w")


# ─────────────────────────────────────────────
#  Sidebar quick-launch button
# ─────────────────────────────────────────────
class QuickLaunchButton(ctk.CTkButton):
    def __init__(self, master, label: str, icon_name: str, command, **kw):
        super().__init__(
            master,
            text=f"  {label}",
            image=make_icon(icon_name, TEXT_SECONDARY, (16, 16)),
            compound="left",
            font=(FONT, 12),
            fg_color="transparent", hover_color=BG_CARD,
            text_color=TEXT_SECONDARY,
            anchor="w", height=34, corner_radius=8,
            command=command, **kw
        )


# ─────────────────────────────────────────────
#  Main App
# ─────────────────────────────────────────────
class AanyaApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Aanya Desktop")
        self.geometry("980x700")
        self.minsize(840, 580)
        self.configure(fg_color=BG_DARK)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Pre-cache frequently reused icons
        self._icon_mic_active   = make_icon("mic",  "#0f172a", (16, 16))
        self._icon_mic_inactive = make_icon("mic",  "#ffffff", (16, 16))
        self._icon_close        = make_icon("close", ACCENT_CRIMSON, (12, 12))
        self._icon_send         = make_icon("send",  TEXT_PRIMARY,   (16, 16))
        self._icon_refresh      = make_icon("refresh", ACCENT_CRIMSON, (14, 14))

        # Engine
        self.engine = AanyaEngine()
        self.engine.on_status = lambda i, l, m: self.after(0, lambda: self.status_label.configure(text=f"{l} · {m}"))
        self.engine.on_speak  = lambda t: self.after(0, lambda: self._add_bubble(t, "aanya"))
        self.engine.on_heard  = lambda t: self.after(0, lambda: self._add_bubble(t, "user"))
        self.engine.on_wake   = lambda: self.after(0, lambda: self.status_label.configure(text="Wake word detected!"))
        self.engine.on_state  = self._on_engine_state

        self._current_state    = "standby"
        self._orb_angle        = 0.0
        self._sidebar_visible  = True

        self._build_header()
        self._build_body()
        self._build_status_bar()
        self._animate_orb()
        self.engine.start_voice_loop()
        self.protocol("WM_DELETE_WINDOW", lambda: (self.engine.stop_voice_loop(), self.destroy()))

    # ── UI build ──────────────────────────────

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=BG_PANEL, height=64, corner_radius=0,
                           border_width=1, border_color=BORDER_SUBTLE)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        # Left brand
        brand = ctk.CTkFrame(hdr, fg_color="transparent")
        brand.pack(side="left", padx=20)
        self.orb_canvas = ctk.CTkCanvas(brand, width=28, height=28,
                                        bg=BG_PANEL, highlightthickness=0)
        self.orb_canvas.pack(side="left", padx=(0, 12))
        self._draw_orb()

        title_box = ctk.CTkFrame(brand, fg_color="transparent")
        title_box.pack(side="left")
        ctk.CTkLabel(title_box, text="Aanya", font=(FONT, 16, "bold"), text_color=TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(title_box, text="Voice Assistant · Gemini 3.6 Flash",
                     font=(FONT, 11), text_color=TEXT_DIM).pack(anchor="w")

        # Right controls
        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.pack(side="right", padx=20)
        ctk.CTkButton(right, text="Sidebar", width=68, height=32,
                      font=(FONT, 11, "bold"), fg_color=BG_CARD, hover_color=BORDER_SUBTLE,
                      text_color=TEXT_SECONDARY, border_width=1, border_color=BORDER_SUBTLE,
                      corner_radius=6, command=self._toggle_sidebar).pack(side="right")
        self.header_state_label = ctk.CTkLabel(right, text="●  Standby",
                                               font=(FONT, 12, "bold"), text_color=TEXT_DIM)
        self.header_state_label.pack(side="right", padx=(0, 12))

    def _build_body(self):
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)

        self.chat_column = ctk.CTkFrame(self.body, fg_color="transparent")
        self.chat_column.pack(side="left", fill="both", expand=True)
        self._build_chat_display()
        self._build_controls()

        self.sidebar = ctk.CTkFrame(self.body, fg_color=BG_PANEL, width=240,
                                    corner_radius=0, border_width=1, border_color=BORDER_SUBTLE)
        self.sidebar.pack(side="right", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_sidebar_content()

    def _build_chat_display(self):
        self.chat_frame = ctk.CTkScrollableFrame(
            self.chat_column, fg_color=BG_DARK, corner_radius=0,
            scrollbar_button_color=BORDER_SUBTLE,
            scrollbar_button_hover_color=TEXT_DIM
        )
        self.chat_frame.pack(fill="both", expand=True)
        self._add_bubble(
            "Hello Yuvi! I'm Aanya. Say 'Aanya' to wake me up, "
            "click Mic, or type a command below.",
            "aanya"
        )

        # Quick-prompt chips
        chips = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        chips.pack(fill="x", padx=24, pady=12)
        for label, cmd in [("What time is it?", "What time is it?"),
                            ("Show my tasks",    "Show my tasks"),
                            ("Open YouTube",     "Open youtube"),
                            ("Reset Chat",       "reset chat")]:
            ctk.CTkButton(chips, text=label, font=(FONT, 11),
                          fg_color=BG_CARD, hover_color=BORDER_SUBTLE,
                          text_color=TEXT_SECONDARY, border_width=1,
                          border_color=BORDER_SUBTLE, corner_radius=16, height=30,
                          command=lambda t=cmd: self._run_bg(self.engine.process_text_command, t)
                          ).pack(side="left", padx=(0, 8))

    def _build_controls(self):
        wrapper = ctk.CTkFrame(self.chat_column, fg_color=BG_DARK, height=76)
        wrapper.pack(fill="x", side="bottom")
        wrapper.pack_propagate(False)

        bar = ctk.CTkFrame(wrapper, fg_color=BG_INPUT, corner_radius=16,
                           border_width=1, border_color=BORDER_SUBTLE)
        bar.pack(fill="both", expand=True, padx=24, pady=12)

        self.mic_btn = ctk.CTkButton(
            bar, text=" Mic", image=self._icon_mic_inactive, compound="left",
            width=72, height=36, font=(FONT, 12, "bold"),
            fg_color=ACCENT_SKY, hover_color=ACCENT_SKY_HOVER,
            text_color="#0f172a", corner_radius=10,
            command=self._on_mic_click
        )
        self.mic_btn.pack(side="left", padx=(8, 8))

        self.text_input = ctk.CTkEntry(
            bar, placeholder_text="Type a message or command...",
            font=(FONT, 13), fg_color="transparent", border_width=0,
            text_color=TEXT_PRIMARY, placeholder_text_color=TEXT_DIM, height=36
        )
        self.text_input.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.text_input.bind("<Return>", self._on_send)

        ctk.CTkButton(
            bar, text=" Send", image=self._icon_send, compound="left",
            width=72, height=36, font=(FONT, 12, "bold"),
            fg_color=BG_CARD, hover_color=BORDER_SUBTLE,
            text_color=TEXT_PRIMARY, border_width=1,
            border_color=BORDER_SUBTLE, corner_radius=10,
            command=lambda: self._on_send(None)
        ).pack(side="right", padx=(0, 8))

    def _build_sidebar_content(self):
        def section(title, pady_top=18):
            ctk.CTkLabel(self.sidebar, text=title, font=(FONT, 10, "bold"),
                         text_color=TEXT_DIM).pack(padx=16, pady=(pady_top, 6), anchor="w")

        section("QUICK ACCESS")
        site_icons = {"youtube": "play", "google": "search", "github": "code",
                      "whatsapp": "globe", "spotify": "music", "wikipedia": "book", "leetcode": "code"}
        for site, url in SITES.items():
            QuickLaunchButton(
                self.sidebar, label=site.capitalize(),
                icon_name=site_icons.get(site, "globe"),
                command=lambda u=url, s=site: self._quick_launch(s, u)
            ).pack(fill="x", padx=8, pady=1)

        section("APPLICATIONS", 16)
        for label, icon, path in [
            ("Google Chrome", "chrome", "/Applications/Google Chrome.app"),
            ("Brave Browser",  "chrome", "/Applications/Brave Browser.app"),
            ("Finder Files",   "folder", os.path.expanduser("~")),
        ]:
            QuickLaunchButton(
                self.sidebar, label=label, icon_name=icon,
                command=lambda p=path, n=label: self._open_app(n, p)
            ).pack(fill="x", padx=8, pady=1)

        section("TASKS", 16)
        self.tasks_frame = ctk.CTkScrollableFrame(
            self.sidebar, fg_color="transparent", scrollbar_button_color=BORDER_SUBTLE
        )
        self.tasks_frame.pack(fill="both", expand=True, padx=4, pady=(0, 8))
        self._refresh_tasks()

        ctk.CTkButton(
            self.sidebar, text=" Reset Session",
            image=self._icon_refresh, compound="left",
            font=(FONT, 11, "bold"), fg_color="transparent",
            hover_color="#2b171c", text_color=ACCENT_CRIMSON,
            border_width=1, border_color="#451e25",
            corner_radius=8, height=32, command=self._on_reset_chat
        ).pack(fill="x", padx=12, pady=(4, 16))

    def _build_status_bar(self):
        bar = ctk.CTkFrame(self, fg_color=BG_PANEL, height=26, corner_radius=0,
                           border_width=1, border_color=BORDER_SUBTLE)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self.status_label = ctk.CTkLabel(bar, text="Ready · Say 'Aanya' to activate",
                                         font=(FONT, 11), text_color=TEXT_DIM, anchor="w")
        self.status_label.pack(side="left", padx=16, fill="x")
        self.time_label = ctk.CTkLabel(bar, text="", font=(FONT, 11),
                                       text_color=TEXT_DIM, anchor="e")
        self.time_label.pack(side="right", padx=16)
        self._update_clock()

    # ── Animation & clock ─────────────────────

    def _draw_orb(self):
        c = self.orb_canvas
        c.delete("all")
        cx = cy = 14
        r = 6
        colour = STATE_CONFIG.get(self._current_state, STATE_CONFIG["standby"])["dot"]
        pr = r + 2 + 1.5 * math.sin(self._orb_angle)
        c.create_oval(cx-pr, cy-pr, cx+pr, cy+pr, fill="", outline=colour, width=1)
        c.create_oval(cx-r, cy-r, cx+r, cy+r, fill=colour, outline="")

    def _animate_orb(self):
        self._orb_angle += 0.1
        self._draw_orb()
        self.after(50, self._animate_orb)

    def _update_clock(self):
        self.time_label.configure(text=datetime.datetime.now().strftime("%I:%M:%S %p"))
        self.after(1000, self._update_clock)

    # ── Engine state callback ─────────────────

    def _on_engine_state(self, state: str):
        self._current_state = state
        cfg = STATE_CONFIG.get(state, STATE_CONFIG["standby"])
        self.after(0, lambda: self.header_state_label.configure(
            text=cfg["label"], text_color=cfg["colour"]
        ))

    # ── Chat stream ───────────────────────────

    def _add_bubble(self, text: str, sender: str = "aanya"):
        ChatBubble(self.chat_frame, text=text, sender=sender).pack(fill="x", pady=2)
        self.chat_frame.after(100, lambda: self.chat_frame._parent_canvas.yview_moveto(1.0))

    # ── Generic background runner ─────────────

    def _run_bg(self, fn, *args, on_done=None):
        """Run fn(*args) on a daemon thread; call on_done() on the main thread after."""
        def _wrapper():
            fn(*args)
            if on_done:
                self.after(0, on_done)
        threading.Thread(target=_wrapper, daemon=True).start()

    # ── Controls ──────────────────────────────

    def _on_mic_click(self):
        self.mic_btn.configure(fg_color=ACCENT_CRIMSON, text="Listening",
                               image=self._icon_mic_inactive)
        self._run_bg(
            self.engine.push_to_talk,
            on_done=lambda: (
                self.mic_btn.configure(fg_color=ACCENT_SKY, text=" Mic",
                                       image=self._icon_mic_active),
                self._refresh_tasks()
            )
        )

    def _on_send(self, _event):
        text = self.text_input.get().strip()
        if not text:
            return
        self.text_input.delete(0, "end")
        self._run_bg(self.engine.process_text_command, text, on_done=self._refresh_tasks)

    # ── Quick launch / open ───────────────────

    def _quick_launch(self, site: str, url: str):
        self._add_bubble(f"Open {site}", "user")
        subprocess.run(["open", url])
        self._add_bubble(f"Opening {site.capitalize()}.", "aanya")

    def _open_app(self, name: str, path: str):
        self._add_bubble(f"Open {name}", "user")
        subprocess.run(["open", path])
        self._add_bubble(f"Launched {name}.", "aanya")

    # ── Chat reset ────────────────────────────

    def _on_reset_chat(self):
        self._run_bg(self.engine.reset_chat)
        for w in self.chat_frame.winfo_children():
            w.destroy()
        self._add_bubble("Chat reset. How can I help you?", "aanya")

    # ── Sidebar ───────────────────────────────

    def _toggle_sidebar(self):
        if self._sidebar_visible:
            self.sidebar.pack_forget()
        else:
            self.sidebar.pack(side="right", fill="y", in_=self.body)
        self._sidebar_visible = not self._sidebar_visible

    def _refresh_tasks(self):
        for w in self.tasks_frame.winfo_children():
            w.destroy()
        tasks = self.engine.load_tasks()
        if not tasks:
            ctk.CTkLabel(self.tasks_frame, text="No tasks saved",
                         font=(FONT, 11), text_color=TEXT_DIM).pack(pady=12)
            return
        for i, task in enumerate(tasks, 1):
            row = ctk.CTkFrame(self.tasks_frame, fg_color=BG_CARD,
                               corner_radius=6, border_width=1, border_color=BORDER_SUBTLE)
            row.pack(fill="x", pady=2, padx=4)
            ctk.CTkLabel(row, text=f"{i}.", font=(FONT, 11, "bold"),
                         text_color=ACCENT_SKY, width=16).pack(side="left", padx=(6, 2))
            ctk.CTkLabel(row, text=task, font=(FONT, 11),
                         text_color=TEXT_PRIMARY, anchor="w").pack(side="left", fill="x", expand=True)
            ctk.CTkButton(row, text="", image=self._icon_close, width=20, height=20,
                          fg_color="transparent", hover_color="#2b171c", corner_radius=4,
                          command=lambda idx=str(i): self._run_bg(
                              self.engine.delete_task, idx, on_done=self._refresh_tasks
                          )).pack(side="right", padx=4)


# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("[Aanya] Starting desktop voice assistant GUI...", flush=True)
    app = AanyaApp()
    print("[Aanya] Application window is active. Press Ctrl+C in terminal or close window to exit.", flush=True)
    app.mainloop()
