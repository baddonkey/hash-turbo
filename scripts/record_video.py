#!/usr/bin/env python3
"""Record a user-manual video: hashing real project files + verification.

Workflow:
  1. Hash tab — add the actual src/hash_turbo/core/ source directory
  2. Run SHA-256 hashing on those real Python files
  3. Switch to Verify tab, load the generated hash file
  4. Run verification — all files should pass

Run from the project root with the venv activated:
    python scripts/record_video.py

Output:
    docs/screenshots/user-manual-hash-verify.mp4

Requirements:
    ffmpeg on PATH.
    edge-tts installed (pip install edge-tts) — neural narration voice.
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

from PySide6.QtCore import QTimer, QUrl  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_VIDEO = _vc.OUTPUT_DIR / "user-manual-hash-verify.mp4"
_SOURCE_DIR  = _vc.PROJECT_ROOT / "src" / "hash_turbo" / "core"

# Workflow hold durations (wall-clock ms).
# The frame timer may run slower than 30 fps on Windows; using wall-clock
# time for _ms() keeps audio/subtitle timestamps in sync with QTimer delays.
_T_INTRO_MS             = 3_500
_T_AFTER_ADD_FOLDER_MS  = 2_500
_T_BEFORE_HASH_MS       = 2_500
_T_AFTER_HASH_DONE_MS   = 4_000
_T_AFTER_SWITCH_TAB_MS  = 2_500
_T_AFTER_LOAD_MS        = 1_500
# Long final hold so the last narration clip fully plays before recording ends.
_T_AFTER_VERIFY_DONE_MS = 10_000

# ---------------------------------------------------------------------------
# Narration (start_ms = wall-clock ms from recording start)
#
# Approximate workflow wall-clock events:
#   0s   recording starts (empty Hash tab)
#   3.5s folder added, files listed
#   9s   hashing starts (and completes near-instantly)
#   13s  switch to Verify tab
#   15.5s hash file loaded
#   17s  verification starts
#   21s  verification complete
#   31s  recording stops (21 + 10s hold)
# ---------------------------------------------------------------------------

_NARRATION = [
    (   0, "hash-turbo is a cross-platform file hash management tool.", 4_500),
    (4_500, "Add a folder to list its files, then click Hash to compute checksums.", 5_000),
    (9_500, "Hashing complete. Now switching to the Verify tab.", 3_500),
    (13_000, "Load the hash file and click Verify to check file integrity.", 5_000),
    (18_000, "Verification is running — comparing each file against its stored checksum.", 5_000),
    (23_000, "All files passed. Every checksum matched — your data is intact.", 8_000),
]

# Translated subtitle text — same order as _NARRATION, same timing.
_TRANSLATIONS: dict[str, list[str]] = {
    "en": [
        "hash-turbo is a cross-platform file hash management tool.",
        "Add a folder to list its files, then click Hash to compute checksums.",
        "Hashing complete. Now switching to the Verify tab.",
        "Load the hash file and click Verify to check file integrity.",
        "Verification is running — comparing each file against its stored checksum.",
        "All files passed. Every checksum matched — your data is intact.",
    ],
    "de": [
        "hash-turbo ist ein plattformübergreifendes Tool zur Verwaltung von Datei-Prüfsummen.",
        "Ordner hinzufügen, Dateien auflisten, dann Hash klicken, um Prüfsummen zu berechnen.",
        "Hashing abgeschlossen. Wechsel zum Verifizieren-Tab.",
        "Hash-Datei laden und Verifizieren klicken, um die Datei-Integrität zu prüfen.",
        "Verifikation läuft — jede Datei wird mit der gespeicherten Prüfsumme verglichen.",
        "Alle Dateien bestanden. Jede Prüfsumme stimmte überein — Ihre Daten sind intakt.",
    ],
    "fr": [
        "hash-turbo est un outil multiplateforme de gestion des sommes de contrôle de fichiers.",
        "Ajoutez un dossier pour lister ses fichiers, puis cliquez sur Hash pour calculer.",
        "Hachage terminé. Passage à l'onglet Verify.",
        "Chargez le fichier de hachage et cliquez sur Verify pour contrôler l'intégrité.",
        "Vérification en cours — chaque fichier est comparé à sa somme de contrôle enregistrée.",
        "Tous les fichiers ont réussi. Chaque somme correspond — vos données sont intactes.",
    ],
    "it": [
        "hash-turbo è uno strumento multipiattaforma per la gestione degli hash dei file.",
        "Aggiungere una cartella per elencare i file, poi cliccare Hash per calcolare i checksum.",
        "Hashing completato. Passaggio alla scheda Verify.",
        "Caricare il file hash e cliccare Verify per verificare l'integrità dei file.",
        "Verifica in corso — ogni file viene confrontato con il suo checksum memorizzato.",
        "Tutti i file hanno superato il controllo. Ogni checksum corrisponde — i dati sono intatti.",
    ],
    "rm": [
        "hash-turbo è in instrument per la gestiun da hashes da datotecas sin tut las platformas.",
        "Agiuntar in cartulari, vair las datotecas, lura clichar Hash per calcular las sumaziuns.",
        "Hashing cumplì. Migraziun al tab Verify.",
        "Chargiar il fichier da hash e clichar Verify per controllar l'integritad da las datotecas.",
        "Verificaziun è en marcha — mintga datoteca vegn cumpareglada cun sia sumaziun stovida.",
        "Tut las datotecas han passà. Mintga sumaziun correspunda — vossas datas èn intactas.",
    ],
}


# Languages to produce — one video per entry.
_LANGS = ["en", "de", "fr", "it", "rm"]


# ---------------------------------------------------------------------------
# Per-language timing
# ---------------------------------------------------------------------------

def _compute_lang_timing(
    clip_durations: list[float],
) -> tuple[dict[str, int], list[int]]:
    """Return (timing_dict, audio_delays_ms) sized to fit *clip_durations*.

    timing_dict  — hold times for each GUI phase (passed to _run_gui).
    audio_delays — ms offset from recording start at which each clip should
                   begin in the mixed WAV (aligned to the GUI events).
    """
    PAD = 400   # silence buffer after each clip before next visual event (ms)
    dur = clip_durations

    # Phase holds — always at least the original defaults.
    t_intro        = max(3_500,  int(dur[0]) + PAD)
    t_after_add    = 2_500                                # short cursor move, unchanged
    t_before_hash  = max(2_500,  int(dur[1]) + PAD - t_after_add)
    t_after_hash   = max(4_000,  int(dur[2]) + PAD)
    t_after_switch = max(2_500,  int(dur[3]) + PAD - 1_500)
    t_after_load   = 1_500                                # short, verify starts right after
    t_final        = max(10_000, int(dur[5]) + 1_000)

    timing = {
        "t_intro":        t_intro,
        "t_after_add":    t_after_add,
        "t_before_hash":  t_before_hash,
        "t_after_hash":   t_after_hash,
        "t_after_switch": t_after_switch,
        "t_after_load":   t_after_load,
        "t_final":        t_final,
    }

    # Audio placement: each clip starts when its corresponding visual event fires.
    d0 = 0
    d1 = t_intro                                               # folder added
    d2 = d1 + t_after_add + t_before_hash                     # hash completes
    d3 = d2 + t_after_hash                                     # switch to verify
    d4 = d3 + t_after_switch + t_after_load + 400             # verify starts
    d5 = d4 + 7_500                                            # verify completes (~7.5 s)

    return timing, [d0, d1, d2, d3, d4, d5]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _record_one_lang(lang: str) -> None:
    """Record the hash-verify video for a single language (must run in its own process)."""
    _vc.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not _SOURCE_DIR.is_dir():
        print(f"ERROR: source directory not found: {_SOURCE_DIR}", file=sys.stderr)
        sys.exit(1)

    print(f"\n=== Recording language: {lang} ===")
    tmp_dir   = Path(tempfile.mkdtemp(prefix=f"hash-turbo-hv-{lang}-"))
    frame_dir = tmp_dir / "frames"
    audio_dir = tmp_dir / "audio"
    frame_dir.mkdir()
    audio_dir.mkdir()

    narration = _vc.NarrationTrack()
    for start_ms, text, dur_ms in _NARRATION:
        narration.add(start_ms, text, dur_ms)

    output_video = _vc.OUTPUT_DIR / f"user-manual-hash-verify.{lang}.mp4"
    try:
        # 1. Pre-generate TTS to get actual clip durations before recording.
        clip_durations = narration.pre_generate_clips(
            audio_dir, lang, _TRANSLATIONS.get(lang, _TRANSLATIONS["en"])
        )
        # 2. Compute per-language hold times and audio placement.
        timing, audio_delays = _compute_lang_timing(clip_durations)

        # 3. Record GUI with per-language hold times.
        actual_fps = _run_gui(tmp_dir, frame_dir, narration, lang, timing)

        # 4. Mix audio at the GUI-aligned timestamps (updates narration._lines for SRT).
        wav = narration.build_lang_audio(audio_dir, lang, audio_delays, clip_durations)
        audio_tracks: dict[str, Path] = {lang: wav} if wav else {}

        # For RM (no TTS) update _lines so SRT timestamps reflect the timing.
        if not wav:
            for i, (delay, dur) in enumerate(zip(audio_delays, clip_durations)):
                narration._lines[i].start_ms = float(delay)
                narration._lines[i].end_ms   = float(delay + dur + 100)

        # 5. Write ASS subtitle files into tmp_dir (embedded in MP4; cleaned up after).
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
    narration: _vc.NarrationTrack,
    lang: str = "en",
    timing: dict[str, int] | None = None,
) -> float:
    """Drive the GUI through the workflow and return the actual capture fps."""
    # Resolve per-language hold times (fall back to module defaults for EN).
    T_INTRO        = (timing or {}).get("t_intro",        _T_INTRO_MS)
    T_AFTER_ADD    = (timing or {}).get("t_after_add",    _T_AFTER_ADD_FOLDER_MS)
    T_BEFORE_HASH  = (timing or {}).get("t_before_hash",  _T_BEFORE_HASH_MS)
    T_AFTER_HASH   = (timing or {}).get("t_after_hash",   _T_AFTER_HASH_DONE_MS)
    T_AFTER_SWITCH = (timing or {}).get("t_after_switch", _T_AFTER_SWITCH_TAB_MS)
    T_AFTER_LOAD   = (timing or {}).get("t_after_load",   _T_AFTER_LOAD_MS)
    T_FINAL        = (timing or {}).get("t_final",        _T_AFTER_VERIFY_DONE_MS)

    app, engine, settings_model, hash_model, verify_model, _ = _vc.make_app_and_engine(lang)
    root_window = engine.rootObjects()[0]

    frame_counter: list[int]   = [0]
    recording:     list[bool]  = [True]
    _wall_start:   list[float] = [0.0]
    _actual_fps:   list[float] = [float(_vc.RECORD_FPS)]
    cursor = _vc.CursorAnimator(start_pos=(0.50, 0.55))

    def _ms() -> float:
        """Wall-clock ms elapsed since recording started."""
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

    def _resolve_positions() -> None:
        fallbacks = {
            "tabHash":         (0.13, 0.056),
            "tabVerify":       (0.37, 0.056),
            "addFolderBtn":    (0.08, 0.24),
            "hashBtn":         (0.50, 0.68),
            "loadHashFileBtn": (0.13, 0.24),
            "verifyBtn":       (0.50, 0.66),
        }
        for name, fallback in fallbacks.items():
            pos[name] = _vc.get_item_frac(root_window, name) or fallback

    output_hash_file = tmp_dir / "output" / "checksums.sha256"
    output_hash_file.parent.mkdir(parents=True, exist_ok=True)

    def step_init() -> None:
        _wall_start[0] = time.perf_counter()
        settings_model._theme = "light"
        settings_model.theme_changed.emit()
        switch_tab(0)
        _resolve_positions()
        frame_timer.start()
        log("Recording started — Hash tab (empty)")
        t0 = _ms()
        cursor.move_to(t0 + T_INTRO * 0.55, pos["addFolderBtn"])
        QTimer.singleShot(T_INTRO, step_add_folder)

    def step_add_folder() -> None:
        folder_url = QUrl.fromLocalFile(str(_SOURCE_DIR)).toString()
        hash_model.addFolder(folder_url)
        log(f"Added folder: {_SOURCE_DIR.name}")
        t0 = _ms()
        cursor.move_to(t0 + 500,                        pos["addFolderBtn"])
        cursor.move_to(t0 + T_AFTER_ADD * 0.7, pos["hashBtn"])
        QTimer.singleShot(T_AFTER_ADD, step_before_hash)

    def step_before_hash() -> None:
        log("Pausing before hash…")
        t0 = _ms()
        cursor.move_to(t0 + T_BEFORE_HASH * 0.5, pos["hashBtn"])
        QTimer.singleShot(T_BEFORE_HASH, step_start_hash)

    def step_start_hash() -> None:
        hash_model.startHash(
            "sha256", "gnu", True, True,
            str(_SOURCE_DIR), str(output_hash_file),
        )
        log("Hashing started…")
        QTimer.singleShot(100, step_wait_hash)

    def step_wait_hash() -> None:
        if hash_model.isHashing:
            QTimer.singleShot(50, step_wait_hash)
            return
        log("Hash complete — holding on results")
        t0 = _ms()
        cursor.move_to(t0 + 600,                  (0.50, 0.82))
        cursor.move_to(t0 + T_AFTER_HASH * 0.7,  pos["tabVerify"])
        QTimer.singleShot(T_AFTER_HASH, step_switch_verify)

    def step_switch_verify() -> None:
        switch_tab(1)
        log("Switched to Verify tab")
        # Re-query verify-tab button positions now that the tab is active and laid out.
        def _re_resolve() -> None:
            pos["loadHashFileBtn"] = _vc.get_item_frac(root_window, "loadHashFileBtn") or pos["loadHashFileBtn"]
            pos["verifyBtn"]       = _vc.get_item_frac(root_window, "verifyBtn")       or pos["verifyBtn"]
            log(f"  verifyBtn resolved to {pos['verifyBtn']}")
        QTimer.singleShot(150, _re_resolve)
        t0 = _ms()
        cursor.move_to(t0 + T_AFTER_SWITCH * 0.6, pos["loadHashFileBtn"])
        QTimer.singleShot(T_AFTER_SWITCH, step_load_hash_file)

    def step_load_hash_file() -> None:
        url = QUrl.fromLocalFile(str(output_hash_file)).toString()
        verify_model.loadFile(url)
        log("Loading hash file…")
        QTimer.singleShot(100, step_wait_load)

    def step_wait_load() -> None:
        if verify_model.isLoading:
            QTimer.singleShot(50, step_wait_load)
            return
        log("Hash file loaded")
        t0 = _ms()
        cursor.move_to(t0 + T_AFTER_LOAD * 0.7, pos["verifyBtn"])
        QTimer.singleShot(T_AFTER_LOAD, step_start_verify)

    def step_start_verify() -> None:
        content = output_hash_file.read_text(encoding="utf-8")
        verify_model.verify(
            content, str(output_hash_file), str(_SOURCE_DIR),
            True, str(_SOURCE_DIR), True, True, True,
        )
        log("Verification started…")
        QTimer.singleShot(100, step_wait_verify)

    def step_wait_verify() -> None:
        if verify_model.isVerifying:
            QTimer.singleShot(50, step_wait_verify)
            return
        log("Verification complete — holding on results")
        cursor.move_to(_ms() + 800, (0.50, 0.82))
        QTimer.singleShot(T_FINAL, step_done)

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
