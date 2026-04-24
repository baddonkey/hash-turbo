#!/usr/bin/env python3
"""Record a user-manual video demonstrating the Sanitize tab.

Uses a real hash file from the project (generated on-the-fly from
src/hash_turbo/core/*.py) to show a genuine transformation workflow.

Workflow:
  1. Sanitize tab shown empty
  2. Load the real GNU-format hash file
  3. Transform: GNU → BSD, POSIX separators, lowercase, sorted by path, LF line-endings
  4. Output shown with the transformed entries

Run from the project root with the venv activated:
    python scripts/record_sanitize_video.py

Output:
    docs/screenshots/user-manual-sanitize.mp4

Requirements:
    ffmpeg on PATH.
    pyttsx3 installed (pip install pyttsx3).
    PySide6 installed (pip install -e ".[gui]").
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _video_common as _vc  # noqa: E402

from PySide6.QtCore import QTimer, QUrl  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_VIDEO  = _vc.OUTPUT_DIR / "user-manual-sanitize.mp4"
_SOURCE_DIR   = _vc.PROJECT_ROOT / "src" / "hash_turbo" / "core"

# Timeline (ms)
_T_INTRO_MS         = 3_500
_T_AFTER_LOAD_MS    = 2_000   # brief look at loaded input
_T_SET_OPTIONS_MS   = 4_000   # cursor visits fmtCombo, sepCombo, sortCombo
_T_BEFORE_RUN_MS    = 1_500   # pause near Transform before clicking
_T_AFTER_DONE_MS    = 5_500

# Narration
_NARRATION = [
    (   0, "The Sanitize tab lets you reformat and transform existing hash files.", 4_200),
    (4_200, "Load a GNU-format hash file generated from the project source files.", 3_500),
    (8_200, "The file is loaded. You can see the GNU-format checksums on the left.", 3_000),
    (11_500, "Set the options: convert to BSD format, POSIX separators, sorted by path.", 4_000),
    (16_000, "Click Transform to apply the selected options to the input.", 3_000),
    (20_000, "The transformation is complete. BSD-format checksums appear on the right.", 5_000),
]

# Translated subtitle text — same order as _NARRATION, same timing.
_TRANSLATIONS: dict[str, list[str]] = {
    "en": [
        "The Sanitize tab lets you reformat and transform existing hash files.",
        "Load a GNU-format hash file generated from the project source files.",
        "The file is loaded. You can see the GNU-format checksums on the left.",
        "Set the options: convert to BSD format, POSIX separators, sorted by path.",
        "Click Transform to apply the selected options to the input.",
        "The transformation is complete. BSD-format checksums appear on the right.",
    ],
    "de": [
        "Der Tab Sanitize ermöglicht das Umformatieren und Transformieren von Hash-Dateien.",
        "Eine GNU-formatierte Hash-Datei aus den Projektquellen laden.",
        "Die Datei ist geladen. Die GNU-Prüfsummen sind auf der linken Seite sichtbar.",
        "Optionen wählen: BSD-Format, POSIX-Trennzeichen, nach Pfad sortiert.",
        "Auf Transformieren klicken, um die gewählten Optionen auf die Eingabe anzuwenden.",
        "Die Transformation ist abgeschlossen. BSD-Prüfsummen erscheinen auf der rechten Seite.",
    ],
    "fr": [
        "L'onglet Sanitize permet de reformater et transformer des fichiers de hachage.",
        "Charger un fichier de hachage au format GNU généré depuis les sources du projet.",
        "Le fichier est chargé. Les sommes de contrôle GNU sont visibles à gauche.",
        "Définir les options : format BSD, séparateurs POSIX, trié par chemin.",
        "Cliquer sur Transformer pour appliquer les options sélectionnées à l'entrée.",
        "La transformation est terminée. Les sommes de contrôle BSD apparaissent à droite.",
    ],
    "it": [
        "La scheda Sanitize consente di riformattare e trasformare i file hash esistenti.",
        "Caricare un file hash in formato GNU generato dai file sorgente del progetto.",
        "Il file è caricato. I checksum in formato GNU sono visibili a sinistra.",
        "Impostare le opzioni: formato BSD, separatori POSIX, ordinato per percorso.",
        "Cliccare Trasforma per applicare le opzioni selezionate all'input.",
        "La trasformazione è completata. I checksum in formato BSD appaiono a destra.",
    ],
    "rm": [
        "Il tab Sanitize permetta da reformatar e transformar datotecas da hash existentas.",
        "Chargiar in fichier da hash en format GNU generà dals datotecs da funtauna dal project.",
        "Il fichier è chargià. Las sumaziuns da control GNU èn visiblas a sanester.",
        "Fixar las opziuns: format BSD, separaturs POSIX, ordinà tenor il camin.",
        "Clichar Transform per applitgar las opziuns selecziunadas a l'entrada.",
        "La transformaziun è cumplida. Las sumaziuns da control BSD apparian a dretg.",
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_gnu_hash_file(source_dir: Path, output: Path) -> None:
    """Hash every .py file under source_dir into a GNU-format file."""
    lines: list[str] = []
    for py_file in sorted(source_dir.glob("*.py")):
        digest = hashlib.sha256(py_file.read_bytes()).hexdigest()
        lines.append(f"{digest} *{py_file.name}")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


# Languages to produce — one video per entry.
_LANGS = ["en", "de", "fr", "it", "rm"]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Per-language timing
# ---------------------------------------------------------------------------

def _compute_lang_timing(
    clip_durations: list[float],
) -> tuple[dict[str, int], list[int]]:
    """Return (timing_dict, audio_delays_ms) sized to fit *clip_durations*.

    Clip mapping:
      0 \u2014 intro (sanitize tab overview)
      1 \u2014 loading the file (plays while file is loaded + displayed)
      2 \u2014 file shown (plays while showing loaded result)
      3 \u2014 set options
      4 \u2014 click Transform
      5 \u2014 transformation complete
    """
    PAD = 400
    dur = clip_durations

    t_intro       = max(3_500, int(dur[0]) + PAD)
    # Clips 1 and 2 both play while the loaded file is on screen.
    t_after_load  = max(2_000, int(dur[1]) + int(dur[2]) + PAD)
    t_set_options = max(4_000, int(dur[3]) + PAD)
    t_before_run  = max(1_500, int(dur[4]) + PAD)
    t_after_done  = max(5_500, int(dur[5]) + 1_000)

    timing = {
        "t_intro":       t_intro,
        "t_after_load":  t_after_load,
        "t_set_options": t_set_options,
        "t_before_run":  t_before_run,
        "t_after_done":  t_after_done,
    }

    # Audio placement aligned to GUI events.
    d0 = 0
    d1 = t_intro                                    # file starts loading
    d2 = d1 + int(dur[1]) + 300                    # clip 2 starts after clip 1
    d3 = t_intro + t_after_load                     # set options phase starts
    d4 = d3 + t_set_options                         # before-run phase starts
    d5 = d4 + t_before_run + 200                   # transform complete

    return timing, [d0, d1, d2, d3, d4, d5]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _record_one_lang(lang: str) -> None:
    """Record the sanitize video for a single language (must run in its own process)."""
    _vc.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not _SOURCE_DIR.is_dir():
        print(f"ERROR: source directory not found: {_SOURCE_DIR}", file=sys.stderr)
        sys.exit(1)

    print(f"\n=== Recording language: {lang} ===")
    tmp_dir   = Path(tempfile.mkdtemp(prefix=f"hash-turbo-san-{lang}-"))
    frame_dir = tmp_dir / "frames"
    audio_dir = tmp_dir / "audio"
    frame_dir.mkdir()
    audio_dir.mkdir()

    input_hash_file = tmp_dir / "core-checksums.sha256"
    _generate_gnu_hash_file(_SOURCE_DIR, input_hash_file)

    narration = _vc.NarrationTrack()
    for start_ms, text, dur_ms in _NARRATION:
        narration.add(start_ms, text, dur_ms)

    output_video = _vc.OUTPUT_DIR / f"user-manual-sanitize.{lang}.mp4"
    try:
        # 1. Pre-generate TTS to get actual clip durations before recording.
        clip_durations = narration.pre_generate_clips(
            audio_dir, lang, _TRANSLATIONS.get(lang, _TRANSLATIONS["en"])
        )
        # 2. Compute per-language hold times and audio placement.
        timing, audio_delays = _compute_lang_timing(clip_durations)

        # 3. Record GUI with per-language hold times.
        actual_fps = _run_gui(tmp_dir, frame_dir, input_hash_file, narration, lang, timing)

        # 4. Mix audio at the GUI-aligned timestamps.
        wav = narration.build_lang_audio(audio_dir, lang, audio_delays, clip_durations)
        audio_tracks: dict[str, Path] = {lang: wav} if wav else {}

        # For RM (no TTS) update _lines so SRT timestamps reflect the timing.
        if not wav:
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
        _record_one_lang(args.lang)
    else:
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
    tmp_dir: Path,
    frame_dir: Path,
    input_hash_file: Path,
    narration: _vc.NarrationTrack,
    lang: str = "en",
    timing: dict[str, int] | None = None,
) -> float:
    """Drive the GUI through the sanitize workflow; return actual capture fps."""
    T_INTRO       = (timing or {}).get("t_intro",       _T_INTRO_MS)
    T_AFTER_LOAD  = (timing or {}).get("t_after_load",  _T_AFTER_LOAD_MS)
    T_SET_OPTIONS = (timing or {}).get("t_set_options", _T_SET_OPTIONS_MS)
    T_BEFORE_RUN  = (timing or {}).get("t_before_run",  _T_BEFORE_RUN_MS)
    T_AFTER_DONE  = (timing or {}).get("t_after_done",  _T_AFTER_DONE_MS)

    app, engine, settings_model, _hm, _vm, sanitize_model = _vc.make_app_and_engine(lang)
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
            "tabSanitize":    (0.62,  0.056),
            "sanitizeLoadBtn":(0.097, 0.275),
            "fmtCombo":       (0.218, 0.466),
            "sepCombo":       (0.482, 0.466),
            "sortCombo":      (0.267, 0.524),
            "transformBtn":   (0.895, 0.58),
        }
        for name, fb in defaults.items():
            pos[name] = _vc.get_item_frac(root_window, name) or fb

    def _set_combo_index(object_name: str, index: int) -> None:
        from PySide6.QtQuick import QQuickItem  # noqa: PLC0415
        items = root_window.findChildren(QQuickItem, object_name)
        if items:
            items[0].setProperty("currentIndex", index)
            log(f"  {object_name} -> index {index}")

    # The GNU content of the input file (used in transform call)
    gnu_content = input_hash_file.read_text(encoding="utf-8")

    def step_init() -> None:
        _wall_start[0] = time.perf_counter()
        settings_model._theme = "light"
        settings_model.theme_changed.emit()
        switch_tab(2)
        _resolve()
        frame_timer.start()
        log("Recording started -- Sanitize tab (empty)")

        def _re_resolve() -> None:
            _resolve()
            log(f"Re-resolved: sanitizeLoadBtn={pos['sanitizeLoadBtn']}  transformBtn={pos['transformBtn']}")
            cursor.move_to(_ms() + (T_INTRO - 150) * 0.55, pos["sanitizeLoadBtn"])

        QTimer.singleShot(150, _re_resolve)
        QTimer.singleShot(T_INTRO, step_load_file)

    def step_load_file() -> None:
        url = QUrl.fromLocalFile(str(input_hash_file)).toString()
        sanitize_model.loadFile(url)
        log("Loading hash file...")
        QTimer.singleShot(100, step_wait_load)

    def step_wait_load() -> None:
        if sanitize_model.isLoading:
            QTimer.singleShot(50, step_wait_load)
            return
        log("File loaded -- showing input")
        t0 = _ms()
        cursor.move_to(t0 + 400,                (0.28, 0.43))
        cursor.move_to(t0 + 1200,               (0.50, 0.55))
        cursor.move_to(t0 + T_AFTER_LOAD * 0.9, pos["fmtCombo"])
        QTimer.singleShot(T_AFTER_LOAD, step_set_options)

    def step_set_options() -> None:
        log("Setting options...")
        t0 = _ms()
        slot = T_SET_OPTIONS / 3.5  # ~1140ms per combo

        # fmtCombo -> BSD (index 1)
        cursor.move_to(t0 + slot * 0.1, pos["fmtCombo"])
        QTimer.singleShot(int(slot * 0.3), lambda: _set_combo_index("fmtCombo", 1))

        # sepCombo -> POSIX (index 1)
        cursor.move_to(t0 + slot * 1.1, pos["sepCombo"])
        QTimer.singleShot(int(slot * 1.3), lambda: _set_combo_index("sepCombo", 1))

        # sortCombo -> By path (index 1)
        cursor.move_to(t0 + slot * 2.1, pos["sortCombo"])
        QTimer.singleShot(int(slot * 2.3), lambda: _set_combo_index("sortCombo", 1))

        # glide toward Transform button
        cursor.move_to(t0 + T_SET_OPTIONS * 0.85, pos["transformBtn"])
        QTimer.singleShot(T_SET_OPTIONS, step_before_run)

    def step_before_run() -> None:
        log("Pausing before transform...")
        t0 = _ms()
        cursor.move_to(t0 + T_BEFORE_RUN * 0.6, pos["transformBtn"])
        QTimer.singleShot(T_BEFORE_RUN, step_run)

    def step_run() -> None:
        # combos are set to BSD / POSIX / By-path; call transform with the
        # same values so the output matches what the UI shows.
        sanitize_model.transform(
            gnu_content, "bsd", "posix", "", "lower", "path", False, True, "lf",
        )
        log("Transform started...")
        QTimer.singleShot(100, step_wait_run)

    def step_wait_run() -> None:
        if sanitize_model.isSanitizing:
            QTimer.singleShot(50, step_wait_run)
            return
        log("Transform complete — holding on output")
        cursor.move_to(_ms() + 700, (0.72, 0.43))
        QTimer.singleShot(T_AFTER_DONE, step_done)

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

