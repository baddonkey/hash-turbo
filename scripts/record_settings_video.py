#!/usr/bin/env python3
"""Record a user-manual video demonstrating Settings: dark/light theme toggle.

Workflow:
  1. Settings tab in light mode — cursor browses the controls
  2. Click Theme ComboBox → select Dark
  3. UI re-renders in dark mode — hold for viewer
  4. Click Theme ComboBox → select Light
  5. UI returns to light mode — hold before ending

Run from the project root with the venv activated:
    python scripts/record_settings_video.py

Output:
    docs/screenshots/user-manual-settings.mp4

Requirements:
    ffmpeg on PATH.
    pyttsx3 installed (pip install pyttsx3).
    PySide6 installed (pip install -e ".[gui]").
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _video_common as _vc  # noqa: E402

from PySide6.QtCore import QTimer  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_VIDEO = _vc.OUTPUT_DIR / "user-manual-settings.mp4"

# Timeline (ms)
_T_INTRO_MS         = 3_000
_T_BROWSE_MS        = 3_000
_T_DARK_HOLD_MS     = 5_000
_T_BACK_TO_THEME_MS = 2_000
_T_LIGHT_HOLD_MS    = 10_000

# Narration
_NARRATION = [
    (   0, "The Settings tab lets you configure hash-turbo to your preferences.", 4_000),
    (4_000, "Here you can set the default algorithm, path mode, and output format.", 3_500),
    (7_500, "The Theme setting controls the application colour scheme.", 3_000),
    (11_000, "Selecting Dark switches the entire interface to a dark colour scheme.", 4_500),
    (16_000, "Dark mode is active. All views adapt to the selected theme.", 4_500),
    (21_000, "Switching back to Light mode restores the original bright interface.", 7_000),
]

# Translated subtitle text — same order as _NARRATION, same timing.
_TRANSLATIONS: dict[str, list[str]] = {
    "en": [
        "The Settings tab lets you configure hash-turbo to your preferences.",
        "Here you can set the default algorithm, path mode, and output format.",
        "The Theme setting controls the application colour scheme.",
        "Selecting Dark switches the entire interface to a dark colour scheme.",
        "Dark mode is active. All views adapt to the selected theme.",
        "Switching back to Light mode restores the original bright interface.",
    ],
    "de": [
        "Der Tab Einstellungen erlaubt die Konfiguration von hash-turbo nach Ihren Wünschen.",
        "Hier können Sie den Standard-Algorithmus, den Pfadmodus und das Ausgabeformat festlegen.",
        "Die Theme-Einstellung steuert das Farbschema der Anwendung.",
        "Die Auswahl von \"dark\" schaltet die gesamte Oberfläche auf ein dunkles Farbschema.",
        "Der Dunkelmodus ist aktiv. Alle Ansichten passen sich dem gewählten Theme an.",
        "Das Zurückschalten auf \"light\" stellt die ursprüngliche helle Benutzeroberfläche wieder her.",
    ],
    "fr": [
        "L'onglet Paramètres permet de configurer hash-turbo selon vos préférences.",
        "Ici, vous pouvez définir l'algorithme par défaut, le mode de chemin et le format de sortie.",
        "Le paramètre Thème contrôle le schéma de couleurs de l'application.",
        "Sélectionner \"dark\" bascule toute l'interface vers un schéma de couleurs sombre.",
        "Le mode sombre est actif. Toutes les vues s'adaptent au thème sélectionné.",
        "Revenir au mode \"light\" restaure l'interface lumineuse d'origine.",
    ],
    "it": [
        "La scheda Impostazioni consente di configurare hash-turbo secondo le proprie preferenze.",
        "Qui è possibile impostare l'algoritmo predefinito, la modalità percorso e il formato di output.",
        "L'impostazione Tema controlla la combinazione di colori dell'applicazione.",
        "La selezione di \"dark\" passa tutta l'interfaccia a una combinazione di colori scura.",
        "La modalità scura è attiva. Tutte le viste si adattano al tema selezionato.",
        "Tornare alla modalità \"light\" ripristina l'interfaccia originale luminosa.",
    ],
    "rm": [
        "Il tab Parameters permetta da configurar hash-turbo tenor vossas preferenzas.",
        "Qua pudais vus fixar l'algoritmus standard, il modus da via e il format d'output.",
        "L'agiustament Tema steuera il schema da colurs da l'applicaziun.",
        "La selecziun da \"dark\" bascola tut l'interfatscha en in schema da colurs stgir.",
        "Il modus stgir è activ. Tut las vistas s'adatteschan al tema selecziunà.",
        "Returnar al modus \"light\" restabilescha l'interfatscha originala brillanta.",
    ],
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

# Languages to produce — one video per entry.
_LANGS = ["en", "de", "fr", "it", "rm"]


def _compute_lang_timing(clip_durations: list[float]) -> tuple[dict[str, int], list[int]]:
    """Derive per-language hold times from actual TTS clip durations."""
    PAD = 400
    dur = clip_durations
    t_intro     = max(3_000, int(dur[0]) + PAD)
    t_browse    = max(3_000, int(dur[1]) + int(dur[2]) + PAD)  # clips 1+2 overlap browse
    t_dark_hold = max(5_000, int(dur[3]) + int(dur[4]) + PAD)  # clips 3+4 overlap dark
    t_back      = 2_000
    t_light     = max(10_000, int(dur[5]) + 1_000)
    timing = {
        "t_intro": t_intro, "t_browse": t_browse,
        "t_dark_hold": t_dark_hold, "t_back": t_back, "t_light": t_light,
    }
    d0, d1 = 0, t_intro
    d2 = d1 + int(dur[1]) + 300
    d3 = t_intro + t_browse           # dark mode switches
    d4 = d3 + int(dur[3]) + 300
    d5 = d3 + t_dark_hold + t_back    # light mode switches
    return timing, [d0, d1, d2, d3, d4, d5]


def _record_one_lang(lang: str) -> None:
    """Record the settings video for a single language (must run in its own process)."""
    _vc.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n=== Recording language: {lang} ===")
    tmp_dir   = Path(tempfile.mkdtemp(prefix=f"hash-turbo-set-{lang}-"))
    frame_dir = tmp_dir / "frames"
    audio_dir = tmp_dir / "audio"
    frame_dir.mkdir()
    audio_dir.mkdir()

    narration = _vc.NarrationTrack()
    for start_ms, text, dur_ms in _NARRATION:
        narration.add(start_ms, text, dur_ms)

    lang_texts = _TRANSLATIONS.get(lang, _TRANSLATIONS["en"])
    clip_durations = narration.pre_generate_clips(audio_dir, lang, lang_texts)
    timing, audio_delays = _compute_lang_timing(clip_durations)

    output_video = _vc.OUTPUT_DIR / f"user-manual-settings.{lang}.mp4"
    try:
        actual_fps = _run_gui(frame_dir, narration, lang, timing)
        wav = narration.build_lang_audio(audio_dir, lang, audio_delays, clip_durations)
        audio_tracks = {lang: wav} if wav else {}
        if not wav:
            # RM (no voice): update _lines timing for correct SRT timestamps
            for i, (delay, dur) in enumerate(zip(audio_delays, clip_durations)):
                narration._lines[i].start_ms = float(delay)
                narration._lines[i].end_ms   = float(delay + dur + 100)
        srt_files: dict[str, Path] = {}
        for srt_lang, texts in _TRANSLATIONS.items():
            srt_path = tmp_dir / f"subs-{srt_lang}.ass"
            narration.write_ass(srt_path, texts)
            srt_files[srt_lang] = srt_path
        _vc.assemble_video(
            frame_dir, output_video, fps=actual_fps,
            audio_tracks=audio_tracks, subtitle_files=srt_files,
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", default=None, help="Record only this language (internal use).")
    args = parser.parse_args()

    if args.lang:
        # Single-language mode — called from subprocess.
        _record_one_lang(args.lang)
    else:
        # Orchestrator mode — spawn a fresh process per language.
        script = Path(__file__).resolve()
        for lang in _LANGS:
            cmd = [sys.executable, str(script), "--lang", lang]
            result = subprocess.run(cmd, check=False)
            if result.returncode != 0:
                print(f"ERROR: language '{lang}' failed with exit code {result.returncode}", file=sys.stderr)


# ---------------------------------------------------------------------------
# GUI session
# ---------------------------------------------------------------------------

def _run_gui(
    frame_dir: Path,
    narration: _vc.NarrationTrack,
    lang: str = "en",
    timing: dict[str, int] | None = None,
) -> float:
    """Drive the GUI through the settings workflow; return actual capture fps."""
    T_INTRO     = (timing or {}).get("t_intro",     _T_INTRO_MS)
    T_BROWSE    = (timing or {}).get("t_browse",    _T_BROWSE_MS)
    T_DARK_HOLD = (timing or {}).get("t_dark_hold", _T_DARK_HOLD_MS)
    T_BACK      = (timing or {}).get("t_back",      _T_BACK_TO_THEME_MS)
    T_LIGHT     = (timing or {}).get("t_light",     _T_LIGHT_HOLD_MS)

    app, engine, settings_model, _hm, _vm, _sm = _vc.make_app_and_engine(lang)
    root_window = engine.rootObjects()[0]

    frame_counter: list[int]   = [0]
    recording:     list[bool]  = [True]
    _wall_start:   list[float] = [0.0]
    _actual_fps:   list[float] = [float(_vc.RECORD_FPS)]
    cursor = _vc.CursorAnimator(start_pos=(0.50, 0.55))

    def _ms() -> float:
        if _wall_start[0] == 0.0:
            return 0.0
        return (time.perf_counter() - _wall_start[0]) * 1000.0

    def capture_frame() -> None:
        if not recording[0]:
            return
        img = root_window.grabWindow()
        cx, cy = cursor.pos_at(_ms(), img.width(), img.height())
        _vc.draw_cursor(img, cx, cy)
        (frame_dir / f"frame_{frame_counter[0]:06d}.png").write_bytes(
            _img_bytes(img)
        )
        frame_counter[0] += 1

    def _img_bytes(img: object) -> bytes:
        from PySide6.QtCore import QBuffer, QIODevice  # noqa: PLC0415
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.ReadWrite)
        img.save(buf, "PNG")  # type: ignore[attr-defined]
        return buf.data().data()

    frame_timer = QTimer()
    frame_timer.setInterval(1000 // _vc.RECORD_FPS)
    frame_timer.timeout.connect(capture_frame)

    def switch_tab(index: int) -> None:
        header = root_window.property("header")
        if header:
            header.setProperty("currentIndex", index)

    def log(msg: str) -> None:
        print(f"  [{_ms() / 1000:6.1f}s] {msg}")

    pos: dict[str, tuple[float, float]] = {}

    def _resolve() -> None:
        defaults = {
            "tabSettings": (0.87, 0.056),
            "themeCombo":  (0.60, 0.385),
        }
        for name, fb in defaults.items():
            pos[name] = _vc.get_item_frac(root_window, name) or fb

    # Approximate positions of settings groups (for cursor browsing)
    _POS_DEFAULTS_GROUP = (0.50, 0.20)
    _POS_EXCLUDE_GROUP  = (0.50, 0.65)

    def step_init() -> None:
        _wall_start[0] = time.perf_counter()
        settings_model._theme = "light"
        settings_model.theme_changed.emit()
        switch_tab(3)
        _resolve()
        frame_timer.start()
        log("Recording started — Settings tab (light mode)")
        t0 = _ms()
        cursor.move_to(t0 + 600,             _POS_DEFAULTS_GROUP)
        cursor.move_to(t0 + T_INTRO * 0.55,  pos["themeCombo"])
        QTimer.singleShot(T_INTRO, step_browse)

    def step_browse() -> None:
        log("Browsing settings…")
        t0 = _ms()
        cursor.move_to(t0 + 500,               _POS_DEFAULTS_GROUP)
        cursor.move_to(t0 + T_BROWSE * 0.4,   _POS_EXCLUDE_GROUP)
        cursor.move_to(t0 + T_BROWSE * 0.75,  pos["themeCombo"])
        QTimer.singleShot(T_BROWSE, step_switch_dark)

    def step_switch_dark() -> None:
        log("Switching to dark mode…")
        settings_model._theme = "dark"
        settings_model.theme_changed.emit()
        t0 = _ms()
        cursor.move_to(t0 + 700,                pos["themeCombo"])
        cursor.move_to(t0 + T_DARK_HOLD * 0.4, _POS_DEFAULTS_GROUP)
        cursor.move_to(t0 + T_DARK_HOLD * 0.7, _POS_EXCLUDE_GROUP)
        cursor.move_to(t0 + T_DARK_HOLD * 0.9, pos["themeCombo"])
        QTimer.singleShot(T_DARK_HOLD, step_back_to_theme)

    def step_back_to_theme() -> None:
        log("Moving back to Theme combo…")
        t0 = _ms()
        cursor.move_to(t0 + T_BACK * 0.65, pos["themeCombo"])
        QTimer.singleShot(T_BACK, step_switch_light)

    def step_switch_light() -> None:
        log("Switching back to light mode…")
        settings_model._theme = "light"
        settings_model.theme_changed.emit()
        t0 = _ms()
        cursor.move_to(t0 + 700,            pos["themeCombo"])
        cursor.move_to(t0 + T_LIGHT * 0.5, _POS_DEFAULTS_GROUP)
        QTimer.singleShot(T_LIGHT, step_done)

    def step_done() -> None:
        recording[0] = False
        frame_timer.stop()
        elapsed_s = time.perf_counter() - _wall_start[0]
        fps = frame_counter[0] / elapsed_s if elapsed_s > 0 else float(_vc.RECORD_FPS)
        _actual_fps[0] = fps
        log(
            f"Recording stopped — {frame_counter[0]} frames "
            f"({elapsed_s:.1f}s real, {fps:.1f} fps effective)"
        )
        app.quit()

    QTimer.singleShot(800, step_init)
    app.exec()
    return _actual_fps[0]


if __name__ == "__main__":
    main()

