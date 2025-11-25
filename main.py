"""Tkinter language translator with ttkbootstrap styling, googletrans, pyttsx3,
and pyperclip support. Designed for the PyRunners prelims brief."""

from __future__ import annotations

import random
import threading
import tkinter as tk
from collections import deque
from tkinter import filedialog, messagebox

import pyperclip
import pyttsx3
import ttkbootstrap as tb
from googletrans import LANGUAGES, Translator
from ttkbootstrap.constants import BOTH, END, LEFT, RIGHT, TOP, X
from ttkbootstrap.tooltip import ToolTip

# Build language helper structures once so dropdowns remain sorted and readable.
LANGUAGE_MAP = {name.title(): code for code, name in LANGUAGES.items()}
LANGUAGE_NAMES = sorted(LANGUAGE_MAP.keys())
POPULAR_LANGUAGES = ["English", "Hindi", "Spanish", "French", "German"]
CODE_TO_NAME = {code: name for name, code in LANGUAGE_MAP.items()}
NEON_COLORS = ("#00f5ff", "#ff00e6", "#4dff6e", "#ff9a00", "#7a5cff")
THEME_CYCLE = ("darkly", "flatly")


class ParticleCanvas(tk.Canvas):
    """Animated neon particles for a faux 3D cyber aesthetic."""

    def __init__(self, master: tk.Misc, particle_count: int = 40, **kwargs) -> None:
        super().__init__(master, highlightthickness=0, **kwargs)
        self.desired_count = particle_count
        self.particles = [self._create_particle() for _ in range(particle_count)]
        self.bind("<Configure>", self._handle_resize)
        self.after(35, self._animate)

    def _create_particle(self) -> dict:
        size = random.randint(6, 50)
        particle = {
            "x": 0,
            "y": 0,
            "dx": random.uniform(-1.5, 1.5),
            "dy": random.uniform(0.3, 1.6),
            "size": size,
            "color": random.choice(NEON_COLORS),
            "id": self.create_oval(0, 0, size, size, fill="", outline=""),
        }
        return particle

    def _handle_resize(self, event: tk.Event) -> None:
        self._scatter_particles(event.width, event.height)

    def reseed(self) -> None:
        """Public helper so parent widgets can randomize positions."""
        self._scatter_particles(self.winfo_width() or 1, self.winfo_height() or 1)
        self.set_particle_count(self.desired_count)

    def _scatter_particles(self, width: int, height: int) -> None:
        if width <= 1 or height <= 1:
            return
        for particle in self.particles:
            particle["x"] = random.randint(0, width)
            particle["y"] = random.randint(0, height)
            self._draw_particle(particle)

    def _draw_particle(self, particle: dict) -> None:
        self.coords(
            particle["id"],
            particle["x"],
            particle["y"],
            particle["x"] + particle["size"],
            particle["y"] + particle["size"],
        )
        self.itemconfig(particle["id"], fill=particle["color"], outline="")

    def _animate(self) -> None:
        width = self.winfo_width() or 1
        height = self.winfo_height() or 1
        for particle in self.particles:
            particle["x"] += particle["dx"]
            particle["y"] += particle["dy"]

            if particle["x"] <= 0 or particle["x"] >= width:
                particle["dx"] *= -1

            if particle["y"] >= height:
                particle["y"] = -particle["size"]
                particle["x"] = random.randint(0, width)

            self._draw_particle(particle)
        self.after(35, self._animate)

    def set_particle_count(self, count: int) -> None:
        """Increase or decrease particle instances to match desired count."""
        count = max(5, min(count, 150))
        self.desired_count = count
        current = len(self.particles)
        while current < count:
            new_particle = self._create_particle()
            width = self.winfo_width() or 1
            height = self.winfo_height() or 1
            new_particle["x"] = random.randint(0, width)
            new_particle["y"] = random.randint(0, height)
            self._draw_particle(new_particle)
            self.particles.append(new_particle)
            current += 1
        while current > count and self.particles:
            particle = self.particles.pop()
            self.delete(particle["id"])
            current -= 1


class TranslatorApp:
    def __init__(self) -> None:
        self.root = tb.Window(themename=THEME_CYCLE[0])
        self.root.title("Language Translator by L0stxRising")
        self.root.geometry("1080x680")
        self.root.resizable(True, True)
        self.root.configure(bg="#000000")
        self.style = tb.Style()
        self.style.configure("Glass.TFrame", background="#050505", borderwidth=0)
        self.style.configure("Inner.TFrame", background="#050505")
        self.style.configure("Section.TFrame", background="#050505")

        self.translator = Translator()
        self.tts_engine = pyttsx3.init()
        self.tts_voices = self.tts_engine.getProperty("voices")
        self.status_var = tk.StringVar(
            value="Ready. Press Translate ✨ or Ctrl+Enter."
        )
        self.last_translation = ""
        self.last_detected = ""
        self.history = deque(maxlen=10)
        self.char_count_var = tk.StringVar(value="Words: 0 | Characters: 0")
        self.voice_choice_var = tk.StringVar(value="Default")
        self.speed_var = tk.IntVar(value=170)
        self.volume_var = tk.DoubleVar(value=80)
        self.auto_translate_delay = 650
        self.typing_job: str | None = None
        self.theme_index = 0
        self.dropdown_headers = {"— Popular —", "— All Languages —"}
        self.source_last_selection = "Auto Detect"
        self.target_last_selection = "English"
        self.language_options = self._build_language_values()
        self.source_lang_var = tk.StringVar(value="Auto Detect")
        self.target_lang_var = tk.StringVar(value="English")

        self.particle_layer = ParticleCanvas(self.root, bg="#000000")
        self.particle_layer.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.root.after(150, self.particle_layer.reseed)

        self._build_ui()
        self.root.bind_all("<Control-Return>", lambda event: self.translate())
        self.root.bind_all("<Control-KP_Enter>", lambda event: self.translate())
        self.root.bind_all("<Control-l>", lambda event: self.clear_text())
        self.root.bind_all("<Control-L>", lambda event: self.clear_text())
        self.root.bind_all("<Control-Shift-C>", lambda event: self.copy_translation())
        self.root.bind_all("<Control-Shift-S>", lambda event: self.swap_languages())
        self.root.bind_all("<Escape>", lambda event: self.set_status("Status cleared."))

    def _build_ui(self) -> None:
        padding = dict(padx=16, pady=10)

        container = tb.Frame(
            self.root,
            bootstyle="dark",
            padding=24,
            style="Glass.TFrame",
        )
        container.pack(fill=BOTH, expand=True, padx=18, pady=18)
        self.container = container

        inner = tb.Frame(container, style="Inner.TFrame")
        inner.pack(fill=BOTH, expand=True)
        self.inner_frame = inner

        header = tb.Label(
            inner,
            text="🌍  Language Translator by L0stxRising",
            font=("Segoe UI", 18, "bold"),
        )
        header.pack(fill=X, **padding)

        selector_frame = tb.Frame(inner, style="Section.TFrame")
        selector_frame.pack(fill=X, **padding)

        tb.Label(selector_frame, text="From").pack(side=LEFT, padx=(0, 6))
        self.source_combo = tb.Combobox(
            selector_frame,
            values=["Auto Detect", *self.language_options],
            textvariable=self.source_lang_var,
            width=18,
            state="readonly",
        )
        self.source_combo.pack(side=LEFT, padx=(0, 12))
        self.source_combo.bind(
            "<<ComboboxSelected>>",
            lambda event: self._handle_combo_selection(
                self.source_combo, self.source_lang_var, allow_auto=True
            ),
        )

        swap_btn = tb.Button(
            selector_frame,
            text="⇆ Swap",
            command=self.swap_languages,
            bootstyle="warning-outline",
        )
        swap_btn.pack(side=LEFT, padx=4)

        tb.Label(selector_frame, text="To").pack(side=LEFT, padx=(12, 6))
        self.target_combo = tb.Combobox(
            selector_frame,
            values=self.language_options,
            textvariable=self.target_lang_var,
            width=18,
            state="readonly",
        )
        self.target_combo.pack(side=LEFT, padx=(0, 12))
        self.target_combo.bind(
            "<<ComboboxSelected>>",
            lambda event: self._handle_combo_selection(
                self.target_combo, self.target_lang_var, allow_auto=False
            ),
        )

        text_frame = tb.Frame(inner, style="Section.TFrame")
        text_frame.pack(fill=BOTH, expand=True, **padding)
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        text_frame.rowconfigure(1, weight=1)

        input_frame = tk.Frame(text_frame, borderwidth=0, bg="#050505", highlightthickness=0)
        input_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 8))

        self.source_text = tk.Text(
            input_frame,
            height=10,
            font=("Segoe UI", 12),
            wrap="word",
            bd=0,
            bg="#0a0a0a",
            fg="#f2f2f2",
            insertbackground="#f2f2f2",
        )
        self.source_text.pack(fill=BOTH, expand=True)
        self.source_text.bind("<KeyRelease>", lambda event: self._on_input_change())
        self.source_text.bind(
            "<<Paste>>", lambda event: self.root.after(10, self._on_input_change)
        )
        self.input_frame = input_frame

        input_footer = tk.Frame(input_frame, bg="#050505", highlightthickness=0)
        input_footer.pack(fill=X, pady=(6, 0))

        self.clear_input_btn = tb.Button(
            input_footer,
            text="Clear Input",
            bootstyle="danger-outline",
            command=self.clear_input_only,
            width=12,
        )
        self.clear_input_btn.pack(side=LEFT)

        self.word_char_label = tb.Label(
            input_footer,
            textvariable=self.char_count_var,
            bootstyle="secondary",
        )
        self.word_char_label.pack(side=LEFT, padx=10)

        self.translate_btn = tb.Button(
            input_footer,
            text="Translate ✨",
            bootstyle="success",
            command=self.translate,
            width=16,
        )
        self.translate_btn.pack(side=RIGHT)

        output_frame = tk.Frame(text_frame, borderwidth=0, bg="#050505", highlightthickness=0)
        output_frame.grid(row=1, column=0, sticky="nsew")

        self.output_text = tk.Text(
            output_frame,
            height=10,
            font=("Segoe UI", 12),
            wrap="word",
            state="disabled",
            bd=0,
            bg="#0a0a0a",
            fg="#f2f2f2",
        )
        self.output_text.pack(fill=BOTH, expand=True)
        self.output_frame = output_frame

        button_frame = tb.Frame(inner)
        button_frame.pack(fill=X, **padding)

        self.translate_toolbar_btn = tb.Button(
            button_frame,
            text="Translate",
            bootstyle="success",
            command=self.translate,
        )
        self.translate_toolbar_btn.pack(side=LEFT, padx=4)

        tb.Button(
            button_frame,
            text="Speak",
            bootstyle="info-outline",
            command=self.speak_translation,
        ).pack(side=LEFT, padx=4)

        tb.Button(
            button_frame,
            text="Copy",
            bootstyle="secondary-outline",
            command=self.copy_translation,
        ).pack(side=LEFT, padx=4)

        tb.Button(
            button_frame,
            text="Paste",
            bootstyle="secondary",
            command=self.paste_from_clipboard,
        ).pack(side=LEFT, padx=4)

        tb.Button(
            button_frame,
            text="Clear",
            bootstyle="danger-outline",
            command=self.clear_text,
        ).pack(side=LEFT, padx=4)

        tb.Button(
            button_frame,
            text="History",
            bootstyle="dark-outline",
            command=self.show_history,
        ).pack(side=LEFT, padx=4)

        tb.Button(
            button_frame,
            text="Import .txt",
            bootstyle="warning-outline",
            command=self.import_text_file,
        ).pack(side=LEFT, padx=4)

        tb.Button(
            button_frame,
            text="Export .txt",
            bootstyle="warning",
            command=self.export_translation_file,
        ).pack(side=LEFT, padx=4)

        tb.Button(
            button_frame,
            text="Theme",
            bootstyle="info-outline",
            command=self.toggle_theme,
        ).pack(side=RIGHT, padx=4)

        tts_frame = tb.Frame(inner)
        tts_frame.pack(fill=X, **padding)

        tb.Label(tts_frame, text="Speed").pack(side=LEFT, padx=(0, 4))
        speed_scale = tb.Scale(
            tts_frame,
            from_=120,
            to=220,
            orient="horizontal",
            variable=self.speed_var,
            command=lambda _: self._apply_tts_preferences(),
            length=120,
        )
        speed_scale.pack(side=LEFT, padx=(0, 12))

        tb.Label(tts_frame, text="Volume").pack(side=LEFT, padx=(0, 4))
        volume_scale = tb.Scale(
            tts_frame,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self.volume_var,
            command=lambda _: self._apply_tts_preferences(),
            length=120,
        )
        volume_scale.pack(side=LEFT, padx=(0, 12))

        tb.Button(
            tts_frame,
            text="Stop Speaking",
            bootstyle="warning-outline",
            command=self.stop_speaking,
        ).pack(side=LEFT, padx=4)

        self.status_label = tb.Label(
            inner,
            textvariable=self.status_var,
            anchor="w",
            bootstyle="inverse-dark",
        )
        self.status_label.pack(fill=X, padx=12, pady=(0, 12))
        self.status_tooltip = ToolTip(self.status_label, text=self.status_var.get())
        self._update_char_count()
        self._apply_palette("dark")

    def swap_languages(self) -> None:
        if self.source_lang_var.get() == "Auto Detect":
            self.set_status("Cannot swap while source is Auto Detect.")
            return
        src, tgt = self.source_lang_var.get(), self.target_lang_var.get()
        self.source_lang_var.set(tgt)
        self.target_lang_var.set(src)

    def translate(self) -> None:
        text = self.source_text.get("1.0", END).strip()
        if not text:
            self.set_status("Type something to translate.")
            return

        src_name = self.source_lang_var.get()
        tgt_name = self.target_lang_var.get()
        src_code = "auto" if src_name == "Auto Detect" else LANGUAGE_MAP[src_name]
        tgt_code = LANGUAGE_MAP[tgt_name]

        self.set_status("Translating…")
        threading.Thread(
            target=self._translate_worker, args=(text, src_code, tgt_code), daemon=True
        ).start()
        self.typing_job = None

    def _translate_worker(self, text: str, src: str, dest: str) -> None:
        try:
            result = self.translator.translate(text, src=src, dest=dest)
        except Exception as exc:
            self.root.after(0, lambda: self._handle_error(exc))
            return
        self.root.after(0, lambda: self._apply_translation(result))

    def _apply_translation(self, result) -> None:
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", END)
        translation = result.text.strip()
        self.last_translation = translation

        detected = CODE_TO_NAME.get(result.src, result.src)
        self.last_detected = detected

        self.output_text.insert(END, translation)
        if detected:
            self.output_text.insert(END, f"\n\n[Detected language: {detected}]")
        self.output_text.config(state="disabled")

        target = CODE_TO_NAME.get(result.dest, result.dest)
        self.set_status(f"Translated {detected} → {target}.")
        self._record_history(self.source_text.get("1.0", END).strip(), translation, detected, target)

    def speak_translation(self) -> None:
        text = self.last_translation.strip()
        if not text:
            self.set_status("Nothing to speak. Translate first.")
            return
        self._apply_tts_preferences()
        self.set_status("Speaking…")
        threading.Thread(target=self._speak_worker, args=(text,), daemon=True).start()

    def _speak_worker(self, text: str) -> None:
        try:
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except Exception as exc:
            self.root.after(0, lambda: self.set_status(f"TTS failed: {exc}"))
            return
        self.root.after(0, lambda: self.set_status("Done speaking."))

    def copy_translation(self) -> None:
        text = self.last_translation.strip()
        if not text:
            self.set_status("Nothing to copy yet.")
            return
        pyperclip.copy(text)
        self.set_status("Copied translation to clipboard.")

    def clear_text(self) -> None:   
        self.source_text.delete("1.0", END)
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", END)
        self.output_text.config(state="disabled")
        self.last_translation = ""
        self.last_detected = ""
        self._update_char_count()
        self.set_status("Cleared input and output.")

    def set_status(self, message: str) -> None:
        self.status_var.set(message)
        tooltip = getattr(self, "status_tooltip", None)
        if tooltip is None:
            self.status_tooltip = ToolTip(self.status_label, text=message)
        else:
            tooltip.text = message

    def _handle_error(self, exc: Exception) -> None:
        self.set_status("Translation failed. Check network/API limits.")
        messagebox.showerror("Translation Error", str(exc))

    def _handle_combo_selection(
        self, combo: tb.Combobox, var: tk.StringVar, allow_auto: bool
    ) -> None:
        value = var.get()
        if value in self.dropdown_headers:
            previous = (
                self.source_last_selection if allow_auto else self.target_last_selection
            )
            var.set(previous)
            return
        if not allow_auto and value == "Auto Detect":
            var.set(self.target_last_selection)
            return
        if allow_auto:
            self.source_last_selection = value
        else:
            self.target_last_selection = value

    def _on_input_change(self) -> None:
        self._update_char_count()
        if self.typing_job:
            self.root.after_cancel(self.typing_job)
        self.typing_job = self.root.after(self.auto_translate_delay, self.translate)

    def _update_char_count(self) -> None:
        text = self.source_text.get("1.0", END).strip("\n")
        words = len(text.split()) if text else 0
        chars = len(text)
        self.char_count_var.set(f"Words: {words} | Characters: {chars}")

    def clear_input_only(self) -> None:
        self.source_text.delete("1.0", END)
        self._update_char_count()
        self.set_status("Cleared input.")

    def paste_from_clipboard(self) -> None:
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            self.set_status("Clipboard empty.")
            return
        self.source_text.insert(tk.INSERT, text)
        self._on_input_change()
        self.set_status("Pasted from clipboard.")

    def show_history(self) -> None:
        if not self.history:
            messagebox.showinfo("History", "No translations yet.")
            return
        history_win = tb.Toplevel(self.root)
        history_win.title("Recent Translations")
        history_win.geometry("520x320")
        text_widget = tk.Text(history_win, wrap="word", state="normal")
        text_widget.pack(fill=BOTH, expand=True, padx=12, pady=12)
        for idx, entry in enumerate(reversed(self.history), start=1):
            src, dest, detected, target = entry
            text_widget.insert(
                END,
                f"{idx}. {detected} → {target}\nSource: {src}\nTranslation: {dest}\n\n",
            )
        text_widget.config(state="disabled")

    def import_text_file(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError as exc:
            self.set_status(f"Failed to open file: {exc}")
            return
        self.source_text.delete("1.0", END)
        self.source_text.insert("1.0", content)
        self._on_input_change()
        self.set_status(f"Loaded text from {path}")

    def export_translation_file(self) -> None:
        if not self.last_translation.strip():
            self.set_status("Translate something before exporting.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile="translation.txt",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.last_translation)
        except OSError as exc:
            self.set_status(f"Failed to save file: {exc}")
            return
        self.set_status(f"Saved translation to {path}")

    def toggle_theme(self) -> None:
        self.theme_index = (self.theme_index + 1) % len(THEME_CYCLE)
        theme_name = THEME_CYCLE[self.theme_index]
        self.root.style.theme_use(theme_name)
        self._apply_palette("dark" if self.theme_index == 0 else "light")
        self.set_status(f"Theme set to {theme_name}")

    def _apply_palette(self, mode: str) -> None:
        palette = {
            "dark": {"root": "#000000", "panel": "#050505", "text": "#0a0a0a", "fg": "#f2f2f2"},
            "light": {"root": "#f5f7fb", "panel": "#ffffff", "text": "#ffffff", "fg": "#111111"},
        }[mode]
        self.root.configure(bg=palette["root"])
        for frame in (self.container, self.inner_frame, self.input_frame, self.output_frame):
            try:
                frame.configure(bg=palette["panel"])
            except tk.TclError:
                pass
        self.source_text.configure(
            bg=palette["text"], fg=palette["fg"], insertbackground=palette["fg"]
        )
        self.output_text.configure(bg=palette["text"], fg=palette["fg"])

    def _record_history(self, source: str, translation: str, detected: str, target: str) -> None:
        preview_src = (source[:120] + "…") if len(source) > 120 else source
        preview_dest = (translation[:120] + "…") if len(translation) > 120 else translation
        self.history.append((preview_src, preview_dest, detected, target))

    def _apply_tts_preferences(self) -> None:
        self.tts_engine.setProperty("rate", self.speed_var.get())
        self.tts_engine.setProperty("volume", self.volume_var.get() / 100.0)

    def stop_speaking(self) -> None:
        try:
            self.tts_engine.stop()
        except Exception:
            pass
        self.set_status("Stopped speaking.")

    def run(self) -> None:
        self.root.mainloop()

    def _build_language_values(self) -> list[str]:
        popular = [name.title() for name in POPULAR_LANGUAGES if name.title() in LANGUAGE_MAP]
        others = [name for name in LANGUAGE_NAMES if name not in popular]
        return ["— Popular —", *popular, "— All Languages —", *others]


def main() -> None:
    app = TranslatorApp()
    app.run()


if __name__ == "__main__":
    main()
