"""
app.py — WhatsApp AI Bot — CustomTkinter GUI
Run this file:  python app.py
"""

import os
import sys
import threading
import queue
import customtkinter as ctk
from datetime import datetime
from bot_logic import WhatsAppBot

# ── Theme ──────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

# ── Color palette ──────────────────────────────────────────────────────────────
C = {
    "bg":        "#0d1117",
    "surface":   "#161b22",
    "panel":     "#1c2230",
    "border":    "#30363d",
    "accent":    "#25d366",   # WhatsApp green
    "accent2":   "#128c7e",
    "danger":    "#e74c3c",
    "text":      "#e6edf3",
    "muted":     "#8b949e",
    "log_bg":    "#0a0e15",
    "recv":      "#1e3a2f",
    "sent":      "#1a2a3a",
    "sys":       "#2a1f0a",
}


def now_str() -> str:
    return datetime.now().strftime("%H:%M:%S")


class LogView(ctk.CTkTextbox):
    """Thread-safe, auto-scrolling log window with colour-coded lines."""

    TAG_COLORS = {
        "📨": C["recv"],
        "🤖": C["sent"],
        "✅": "#1a3a1a",
        "❌": "#3a1a1a",
        "⚠️": C["sys"],
        "💔": "#3a1a2a",
        "🚀": "#1a1a3a",
    }

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            font=("Consolas", 12),
            fg_color=C["log_bg"],
            text_color=C["text"],
            border_color=C["border"],
            border_width=1,
            wrap="word",
            **kwargs,
        )
        self.configure(state="disabled")
        self._queue: queue.Queue[str] = queue.Queue()
        self._schedule_drain()

    def append(self, line: str):
        """Thread-safe append."""
        self._queue.put(line)

    def _drain(self):
        while not self._queue.empty():
            line = self._queue.get_nowait()
            self.configure(state="normal")
            ts = f"[{now_str()}]  "
            self.insert("end", ts, "muted")
            self.insert("end", line + "\n")
            self.configure(state="disabled")
            self.see("end")
        self._schedule_drain()

    def _schedule_drain(self):
        self.after(100, self._drain)


class StatusBar(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=C["surface"], corner_radius=0, **kwargs)
        self._dot = ctk.CTkLabel(self, text="●", font=("Arial", 14), text_color=C["muted"])
        self._dot.pack(side="left", padx=(12, 4))
        self._lbl = ctk.CTkLabel(self, text="Idle", font=("Consolas", 12), text_color=C["muted"])
        self._lbl.pack(side="left")

    def set(self, text: str):
        color = (
            C["accent"]  if "Running" in text or "✔" in text else
            C["danger"]  if any(w in text for w in ("Error", "lost", "offline")) else
            "#f0a500"    if any(w in text for w in ("Waiting", "QR", "Stopping")) else
            C["muted"]
        )
        self._dot.configure(text_color=color)
        self._lbl.configure(text=text, text_color=color)


class SettingsPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=C["panel"], corner_radius=12, **kwargs)

        ctk.CTkLabel(
            self, text="⚙  Configuration",
            font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
            text_color=C["accent"],
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 6))

        # Chrome Profile
        ctk.CTkLabel(self, text="Chrome Profile Path", text_color=C["muted"],
                     font=("Segoe UI", 12)).grid(row=1, column=0, sticky="w", padx=16, pady=4)
        self.profile_var = ctk.StringVar(
            value=os.path.join(os.path.expanduser("~"), "whatsapp_chrome_profile")
        )
        ctk.CTkEntry(self, textvariable=self.profile_var, width=340,
                     fg_color=C["surface"], border_color=C["border"],
                     text_color=C["text"]).grid(row=1, column=1, padx=(0, 16), pady=4, sticky="ew")

        # Ollama Model
        ctk.CTkLabel(self, text="Ollama Model", text_color=C["muted"],
                     font=("Segoe UI", 12)).grid(row=2, column=0, sticky="w", padx=16, pady=4)
        self.model_var = ctk.StringVar(value="llama3.2")
        ctk.CTkEntry(self, textvariable=self.model_var, width=340,
                     fg_color=C["surface"], border_color=C["border"],
                     text_color=C["text"]).grid(row=2, column=1, padx=(0, 16), pady=4, sticky="ew")

        # Headless toggle
        ctk.CTkLabel(self, text="Headless Mode", text_color=C["muted"],
                     font=("Segoe UI", 12)).grid(row=3, column=0, sticky="w", padx=16, pady=4)
        self.headless_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(self, variable=self.headless_var, text="",
                      progress_color=C["accent"]).grid(row=3, column=1, sticky="w", padx=2, pady=4)

        # System Prompt
        ctk.CTkLabel(self, text="System Prompt", text_color=C["muted"],
                     font=("Segoe UI", 12)).grid(row=4, column=0, sticky="nw", padx=16, pady=(4, 0))
        self.prompt_box = ctk.CTkTextbox(
            self, height=80, width=340,
            fg_color=C["surface"], border_color=C["border"],
            text_color=C["text"], font=("Consolas", 11),
        )
        self.prompt_box.grid(row=4, column=1, padx=(0, 16), pady=(4, 14), sticky="ew")
        self.prompt_box.insert("end",
            "You are a WhatsApp assistant. Reply in 1-2 sentences maximum. "
            "Never say 'How can I assist you today?' or any greeting. "
            "Never ask how to help. Directly answer whatever was said or asked. "
            "If someone says hi, say hi back briefly. If asked a question, answer it."
        )

        self.columnconfigure(1, weight=1)

    @property
    def profile(self) -> str:
        return self.profile_var.get().strip()

    @property
    def model(self) -> str:
        return self.model_var.get().strip() or "llama3.2"

    @property
    def headless(self) -> bool:
        return self.headless_var.get()

    @property
    def system_prompt(self) -> str:
        return self.prompt_box.get("1.0", "end").strip()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WhatsApp AI Bot — Powered by Ollama")
        self.geometry("920x720")
        self.minsize(760, 580)
        self.configure(fg_color=C["bg"])
        self._bot: WhatsAppBot | None = None
        self._build_ui()

    # ─────────────────────────────
    #  UI construction
    # ─────────────────────────────

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0, height=56)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="  🟢  WhatsApp AI Bot",
            font=ctk.CTkFont("Segoe UI", 18, weight="bold"),
            text_color=C["accent"],
        ).pack(side="left", padx=18)

        ctk.CTkLabel(
            header,
            text="Selenium  ·  Ollama  ·  Phi-3",
            font=("Segoe UI", 11),
            text_color=C["muted"],
        ).pack(side="left", padx=4)

        # ── Status bar ──────────────────────────────────────────────────────
        self._status_bar = StatusBar(self)
        self._status_bar.pack(fill="x", side="bottom")

        # ── Main container ──────────────────────────────────────────────────
        container = ctk.CTkFrame(self, fg_color=C["bg"])
        container.pack(fill="both", expand=True, padx=16, pady=12)

        # Left column — settings + controls
        left = ctk.CTkFrame(container, fg_color=C["bg"], width=420)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        self._settings = SettingsPanel(left)
        self._settings.pack(fill="x")

        # Control buttons
        ctrl = ctk.CTkFrame(left, fg_color=C["bg"])
        ctrl.pack(fill="x", pady=10)

        self._start_btn = ctk.CTkButton(
            ctrl,
            text="▶  Start Bot",
            font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
            fg_color=C["accent2"],
            hover_color=C["accent"],
            height=44,
            corner_radius=10,
            command=self._toggle_bot,
        )
        self._start_btn.pack(fill="x", pady=(0, 6))

        self._update_prompt_btn = ctk.CTkButton(
            ctrl,
            text="💾  Update System Prompt",
            font=("Segoe UI", 12),
            fg_color=C["panel"],
            hover_color=C["border"],
            border_color=C["border"],
            border_width=1,
            height=36,
            corner_radius=8,
            command=self._update_prompt,
        )
        self._update_prompt_btn.pack(fill="x", pady=(0, 6))

        self._clear_btn = ctk.CTkButton(
            ctrl,
            text="🗑  Clear Log",
            font=("Segoe UI", 12),
            fg_color=C["panel"],
            hover_color=C["border"],
            border_color=C["border"],
            border_width=1,
            height=36,
            corner_radius=8,
            command=self._clear_log,
        )
        self._clear_btn.pack(fill="x")

        # Stats strip
        self._stats_frame = ctk.CTkFrame(left, fg_color=C["panel"], corner_radius=10)
        self._stats_frame.pack(fill="x", pady=(10, 0))
        self._msgs_lbl = ctk.CTkLabel(
            self._stats_frame, text="Messages processed: 0",
            font=("Consolas", 11), text_color=C["muted"]
        )
        self._msgs_lbl.pack(padx=14, pady=8)

        # Right column — log
        right = ctk.CTkFrame(container, fg_color=C["bg"])
        right.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            right,
            text="📋  Activity Log",
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            text_color=C["muted"],
        ).pack(anchor="w", pady=(0, 6))

        self._log_view = LogView(right)
        self._log_view.pack(fill="both", expand=True)

        # Initial log message
        self._log("🤖  WhatsApp AI Bot ready. Configure settings and press Start.")
        self._log("💡  Tip: make sure `ollama serve` is running before starting.")

    # ─────────────────────────────
    #  Bot control
    # ─────────────────────────────

    def _toggle_bot(self):
        if self._bot and self._bot.is_running():
            self._bot.stop()
            self._start_btn.configure(
                text="▶  Start Bot", fg_color=C["accent2"], hover_color=C["accent"]
            )
        else:
            self._start_bot()

    def _start_bot(self):
        s = self._settings
        self._msg_count = 0
        self._bot = WhatsAppBot(
            log_callback=self._log,
            status_callback=self._set_status,
            profile_path=s.profile,
            headless=s.headless,
            system_prompt=s.system_prompt,
            ollama_model=s.model,
        )
        self._bot.start()
        self._start_btn.configure(
            text="⏹  Stop Bot", fg_color=C["danger"], hover_color="#c0392b"
        )
        self._log(f"🚀  Bot starting — Model: {s.model} | Headless: {s.headless}")

    def _update_prompt(self):
        if self._bot:
            self._bot.update_system_prompt(self._settings.system_prompt)
            self._log("💾  System prompt updated on running bot.")
        else:
            self._log("ℹ️  (Prompt will be applied when bot starts.)")

    def _clear_log(self):
        self._log_view.configure(state="normal")
        self._log_view.delete("1.0", "end")
        self._log_view.configure(state="disabled")

    # ─────────────────────────────
    #  Thread-safe callbacks
    # ─────────────────────────────

    def _log(self, text: str):
        self._log_view.append(text)
        # bump counter for sent messages
        if text.startswith("✅") and "Reply sent" in text:
            if not hasattr(self, "_msg_count"):
                self._msg_count = 0
            self._msg_count += 1
            self.after(0, lambda c=self._msg_count: self._msgs_lbl.configure(
                text=f"Messages processed: {c}"
            ))

    def _set_status(self, text: str):
        self.after(0, lambda t=text: self._status_bar.set(t))
        # If bot stopped, reset button appearance
        if text in ("Stopped", "Error", "Browser error"):
            self.after(0, lambda: self._start_btn.configure(
                text="▶  Start Bot", fg_color=C["accent2"], hover_color=C["accent"]
            ))

    # ─────────────────────────────
    #  Window close
    # ─────────────────────────────

    def on_close(self):
        if self._bot and self._bot.is_running():
            self._bot.stop()
        self.destroy()


# ── Entry-point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()