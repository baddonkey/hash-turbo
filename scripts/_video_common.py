"""Shared bootstrap, cursor/subtitle/audio helpers for recording scripts.

Import this module *before* any PySide6 imports in each recording script so
that the Windows DLL search path is configured in time.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap — must run before any PySide6 import
# ---------------------------------------------------------------------------

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "src"))

os.environ["QT_QUICK_CONTROLS_STYLE"] = "Material"

if sys.platform == "win32":
    try:
        import PySide6 as _ps6
        os.add_dll_directory(os.fspath(Path(_ps6.__file__).parent.resolve()))
    except (ImportError, OSError):
        pass

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = _project_root
OUTPUT_DIR = _project_root / "docs" / "screenshots"
RECORD_FPS = 30

# ---------------------------------------------------------------------------
# PySide6 imports (after DLL path is set)
# ---------------------------------------------------------------------------

from PySide6.QtCore import QPointF, QUrl  # noqa: E402
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen, QPolygonF  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

# ---------------------------------------------------------------------------
# Cursor animation
# ---------------------------------------------------------------------------


class CursorAnimator:
    """Interpolate a simulated mouse cursor through timed waypoints."""

    def __init__(self, start_pos: tuple[float, float] = (0.50, 0.55)) -> None:
        self._waypoints: list[tuple[float, float, float]] = [(0.0, *start_pos)]

    def move_to(self, arrive_at_ms: float, pos: tuple[float, float]) -> None:
        """Schedule the cursor to arrive at *pos* (fractions) at *arrive_at_ms*."""
        self._waypoints.append((arrive_at_ms, pos[0], pos[1]))

    def pos_at(self, elapsed_ms: float, win_w: int, win_h: int) -> tuple[int, int]:
        """Return pixel (x, y) at *elapsed_ms* using cubic ease-in-out."""
        wpts = self._waypoints
        if elapsed_ms <= wpts[0][0]:
            _, xf, yf = wpts[0]
            return int(xf * win_w), int(yf * win_h)
        if elapsed_ms >= wpts[-1][0]:
            _, xf, yf = wpts[-1]
            return int(xf * win_w), int(yf * win_h)
        for i in range(len(wpts) - 1):
            t0, x0, y0 = wpts[i]
            t1, x1, y1 = wpts[i + 1]
            if t0 <= elapsed_ms <= t1:
                raw = (elapsed_ms - t0) / (t1 - t0) if t1 > t0 else 1.0
                ease = raw * raw * (3.0 - 2.0 * raw)
                return (
                    int((x0 + (x1 - x0) * ease) * win_w),
                    int((y0 + (y1 - y0) * ease) * win_h),
                )
        _, xf, yf = wpts[-1]
        return int(xf * win_w), int(yf * win_h)


def draw_cursor(image: QImage, cx: int, cy: int) -> None:
    """Paint a standard arrow cursor onto *image* at pixel position (cx, cy)."""
    s = 22.0
    pts = [
        QPointF(cx,             cy            ),
        QPointF(cx,             cy + s * 0.85 ),
        QPointF(cx + s * 0.27, cy + s * 0.58 ),
        QPointF(cx + s * 0.48, cy + s * 0.84 ),
        QPointF(cx + s * 0.63, cy + s * 0.76 ),
        QPointF(cx + s * 0.42, cy + s * 0.51 ),
        QPointF(cx + s * 0.73, cy + s * 0.48 ),
    ]
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(255, 255, 255, 230))
    p.setPen(QPen(QColor(0, 0, 0, 200), 1.5))
    p.drawPolygon(QPolygonF(pts))
    p.end()


# ---------------------------------------------------------------------------
# QML item position query
# ---------------------------------------------------------------------------


def get_item_frac(root_window: object, object_name: str) -> tuple[float, float] | None:
    """Return the fractional window-center (x, y) of a QML item by objectName.

    Uses QQuickItem.mapToScene() so coordinates are correct regardless of
    whether the item's tab is currently active.
    Returns *None* if the item is not found or the window has no size yet.
    """
    from PySide6.QtQuick import QQuickItem  # noqa: PLC0415

    items = root_window.findChildren(QQuickItem, object_name)  # type: ignore[attr-defined]
    if not items:
        return None
    item = items[0]
    center = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    w: int = root_window.width()   # type: ignore[attr-defined]
    h: int = root_window.height()  # type: ignore[attr-defined]
    if w <= 0 or h <= 0:
        return None
    return center.x() / w, center.y() / h


# ---------------------------------------------------------------------------
# Subtitle / narration track
# ---------------------------------------------------------------------------


@dataclass
class _NarrationLine:
    start_ms: float
    end_ms: float
    text: str


class NarrationTrack:
    """Collects timed subtitle lines during recording; generates TTS audio after."""

    def __init__(self) -> None:
        self._lines: list[_NarrationLine] = []
        # Pre-generated clips cached by lang for build_lang_audio().
        self._pre_clips: dict[str, list[tuple[float, Path]]] = {}

    def add(self, start_ms: float, text: str, duration_ms: float = 4_500) -> None:
        """Register a subtitle line starting at *start_ms* for *duration_ms* ms."""
        self._lines.append(_NarrationLine(start_ms, start_ms + duration_ms, text))

    def get_text(self, elapsed_ms: float) -> str | None:
        """Return the subtitle text active at *elapsed_ms*, or *None*."""
        for line in self._lines:
            if line.start_ms <= elapsed_ms < line.end_ms:
                return line.text
        return None

    def get_translated_text(self, elapsed_ms: float, texts: list[str]) -> str | None:
        """Return the translated subtitle text active at *elapsed_ms*, or *None*."""
        for i, line in enumerate(self._lines):
            if line.start_ms <= elapsed_ms < line.end_ms:
                return texts[i] if i < len(texts) else line.text
        return None

    def write_srt(self, output_path: Path, texts: list[str] | None = None) -> None:
        """Write an SRT subtitle file using this track's (adjusted) timing.

        If *texts* is given it must have the same length as the track and is
        used instead of the English source strings — for translated SRT files
        that share the same timing as the original.
        """
        def _fmt(ms: float) -> str:
            h = int(ms // 3_600_000)
            m = int((ms % 3_600_000) // 60_000)
            s = int((ms % 60_000) // 1_000)
            c = int(ms % 1_000)
            return f"{h:02d}:{m:02d}:{s:02d},{c:03d}"

        labels = texts if texts is not None else [ln.text for ln in self._lines]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fh:
            for idx, (line, text) in enumerate(zip(self._lines, labels), 1):
                fh.write(f"{idx}\n")
                fh.write(f"{_fmt(line.start_ms)} --> {_fmt(line.end_ms)}\n")
                fh.write(f"{text}\n\n")

    def write_ass(self, output_path: Path, texts: list[str] | None = None) -> None:
        """Write an ASS subtitle file with explicit styling for good readability.

        ASS carries font size, outline, shadow and background through to
        ``mov_text`` when ffmpeg re-encodes it into an MP4 container.
        """
        def _fmt(ms: float) -> str:
            h = int(ms // 3_600_000)
            m = int((ms % 3_600_000) // 60_000)
            s = int((ms % 60_000) // 1_000)
            cs = int((ms % 1_000) / 10)  # centiseconds
            return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

        # ASS colours: &HAABBGGRR (alpha, blue, green, red)
        # White text, black outline, semi-transparent dark box background
        _STYLE = (
            "Style: Default,"
            "Segoe UI,28,"          # font, size
            "&H00FFFFFF,"           # primary (white text)
            "&H000000FF,"           # secondary (unused)
            "&H00000000,"           # outline (black)
            "&H99000000,"           # background (semi-transparent black)
            "-1,0,0,0,"             # bold, italic, underline, strikeout
            "100,100,0,0,"          # scaleX, scaleY, spacing, angle
            "1,2,1,"                # border style 1=outline+shadow, outline=2, shadow=1
            "2,20,20,20,1"          # alignment=2 (bottom-center), marginL/R/V, encoding
        )
        header = (
            "[Script Info]\r\n"
            "ScriptType: v4.00+\r\n"
            "WrapStyle: 0\r\n"
            "ScaledBorderAndShadow: yes\r\n"
            "\r\n"
            "[V4+ Styles]\r\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour,"
            " OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut,"
            " ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow,"
            " Alignment, MarginL, MarginR, MarginV, Encoding\r\n"
            f"{_STYLE}\r\n"
            "\r\n"
            "[Events]\r\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\r\n"
        )

        labels = texts if texts is not None else [ln.text for ln in self._lines]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fh:
            fh.write(header)
            for line, text in zip(self._lines, labels):
                start = _fmt(line.start_ms)
                end = _fmt(line.end_ms)
                fh.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\r\n")

    def pre_generate_clips(
        self, clip_dir: Path, lang: str, texts: list[str]
    ) -> list[float]:
        """Generate TTS clips for *lang* and return actual durations (ms) per clip.

        Clips are cached in ``self._pre_clips[lang]`` for later mixing via
        :meth:`build_lang_audio`.  Falls back to the estimated durations from
        the registered narration lines when TTS is unavailable (no voice for
        the language, missing ffmpeg, or network error).
        """
        voice = _LANG_VOICES.get(lang)
        if not voice or not shutil.which("ffmpeg"):
            return [ln.end_ms - ln.start_ms for ln in self._lines]

        lang_lines = [
            _NarrationLine(ln.start_ms, ln.end_ms, text)
            for ln, text in zip(self._lines, texts)
        ]
        clip_subdir = clip_dir / f"{lang}_pre"
        clip_subdir.mkdir(parents=True, exist_ok=True)

        clips = _generate_clips_edge_tts(lang_lines, clip_subdir, voice)
        if clips is None:
            return [ln.end_ms - ln.start_ms for ln in self._lines]

        self._pre_clips[lang] = clips
        return [_probe_duration_ms(p) for _, p in clips]

    def build_lang_audio(
        self,
        clip_dir: Path,
        lang: str,
        delays_ms: list[int],
        durations_ms: list[float],
    ) -> Path | None:
        """Mix pre-generated clips at *delays_ms* offsets; update timing for SRT.

        Returns the mixed WAV path, or *None* if no pre-generated clips exist
        for *lang* (e.g. Rumantsch has no TTS voice).  Updates ``self._lines``
        so that :meth:`write_srt` emits timestamps aligned with the audio.
        """
        clips = self._pre_clips.get(lang)
        if not clips:
            return None

        wav_path = clip_dir / f"narration_{lang}.wav"
        if not _mix_clips_to_wav(clips, delays_ms, wav_path):
            return None

        for i, (delay, dur) in enumerate(zip(delays_ms, durations_ms)):
            if i < len(self._lines):
                self._lines[i].start_ms = float(delay)
                self._lines[i].end_ms   = float(delay + dur + 100)

        return wav_path

    def generate_all_audio(
        self,
        clip_dir: Path,
        lang_texts: dict[str, list[str]],
    ) -> dict[str, Path]:
        """Generate one mixed WAV per language using edge-tts neural voices.

        Each language gets independent overlap-avoidance: clip durations are
        probed and any start time that would cause a clip to run into the next
        is pushed forward.  The primary language (en) determines the subtitle
        timestamps; all other languages use those times as a floor and may be
        pushed further back when their clips are longer than the English ones.

        Languages without a known TTS voice (e.g. 'rm') are silently skipped.
        Returns {lang: wav_path} for every language that was successfully built.
        """
        if not shutil.which("ffmpeg"):
            print("WARNING: ffmpeg not found — skipping audio.", file=sys.stderr)
            return {}

        clip_dir.mkdir(parents=True, exist_ok=True)

        available = {lang: _LANG_VOICES[lang] for lang in lang_texts if lang in _LANG_VOICES}
        if not available:
            print("WARNING: no TTS voices available — skipping audio.", file=sys.stderr)
            return {}

        # --- Primary language (en): generate clips and determine timing ---
        primary_lang = "en" if "en" in available else next(iter(available))
        primary_lines = [
            _NarrationLine(ln.start_ms, ln.end_ms, text)
            for ln, text in zip(self._lines, lang_texts[primary_lang])
        ]
        primary_clip_dir = clip_dir / primary_lang
        primary_clip_dir.mkdir(parents=True, exist_ok=True)
        primary_clips = _generate_clips_edge_tts(
            primary_lines, primary_clip_dir, available[primary_lang]
        )
        if primary_clips is None:
            primary_clips = _generate_clips_pyttsx3(primary_lines, primary_clip_dir)
        if primary_clips is None:
            print("WARNING: TTS generation failed — skipping audio.", file=sys.stderr)
            return {}

        # Probe clip durations; push back start times to prevent overlap.
        # These adjusted times become the subtitle timestamps and the floor
        # for all other language tracks.
        primary_floors = [float(s) for s, _ in primary_clips]
        adjusted_en = _compute_overlap_free_delays(primary_clips, primary_floors)

        for i, d in enumerate(adjusted_en):
            dur = _probe_duration_ms(primary_clips[i][1])
            orig_dur = self._lines[i].end_ms - self._lines[i].start_ms
            self._lines[i].start_ms = float(d)
            self._lines[i].end_ms = float(d) + max(orig_dur, dur + 200)

        result: dict[str, Path] = {}

        primary_wav = clip_dir / f"narration_{primary_lang}.wav"
        if _mix_clips_to_wav(primary_clips, adjusted_en, primary_wav):
            result[primary_lang] = primary_wav

        # --- Remaining languages: independent overlap avoidance ---
        en_floors = [float(d) for d in adjusted_en]
        for lang, voice in available.items():
            if lang == primary_lang:
                continue
            lang_lines = [
                _NarrationLine(self._lines[i].start_ms, self._lines[i].end_ms, text)
                for i, text in enumerate(lang_texts[lang])
            ]
            lang_clip_dir = clip_dir / lang
            lang_clip_dir.mkdir(parents=True, exist_ok=True)
            clips = _generate_clips_edge_tts(lang_lines, lang_clip_dir, voice)
            if clips is None:
                print(f"WARNING: TTS generation failed for '{lang}' — skipping.", file=sys.stderr)
                continue
            # Use EN-adjusted starts as floors so this track never begins
            # before EN; then push further if this language's clips are longer.
            lang_delays = _compute_overlap_free_delays(clips, en_floors)
            lang_wav = clip_dir / f"narration_{lang}.wav"
            if _mix_clips_to_wav(clips, lang_delays, lang_wav):
                result[lang] = lang_wav

        return result


# ---------------------------------------------------------------------------
# TTS helpers
# ---------------------------------------------------------------------------


def _probe_duration_ms(path: Path) -> float:
    """Return the duration of an audio file in milliseconds via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(result.stdout.strip()) * 1000
    except (ValueError, AttributeError):
        return 5_000.0


def _generate_clips_edge_tts(
    lines: list[_NarrationLine], clip_dir: Path, voice: str = "en-US-JennyNeural"
) -> list[tuple[float, Path]] | None:
    """Generate MP3 clips using Microsoft edge-tts.

    Returns the (start_ms, path) list, or *None* if edge-tts is unavailable
    or fails (network error, etc.).
    """
    try:
        import asyncio  # noqa: PLC0415

        import edge_tts  # noqa: PLC0415
    except ImportError:
        return None

    clips: list[tuple[float, Path]] = []

    async def _gen_all() -> None:
        for i, line in enumerate(lines):
            path = clip_dir / f"clip_{i:03d}.mp3"
            comm = edge_tts.Communicate(line.text, voice, rate="-5%")
            await comm.save(str(path))
            clips.append((line.start_ms, path))

    try:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_gen_all())
        finally:
            loop.close()
        return clips
    except Exception as exc:  # network, rate-limit, etc.
        print(f"edge-tts failed ({exc}), falling back to pyttsx3…", file=sys.stderr)
        return None


def _generate_clips_pyttsx3(
    lines: list[_NarrationLine], clip_dir: Path
) -> list[tuple[float, Path]] | None:
    """Generate WAV clips using pyttsx3 (Zira SAPI5 fallback)."""
    try:
        import pyttsx3  # noqa: PLC0415
    except ImportError:
        return None

    engine = pyttsx3.init()
    for v in engine.getProperty("voices"):
        if "Zira" in v.name:
            engine.setProperty("voice", v.id)
            break
    engine.setProperty("rate", 130)

    clips: list[tuple[float, Path]] = []
    for i, line in enumerate(lines):
        path = clip_dir / f"clip_{i:03d}.wav"
        engine.save_to_file(line.text, str(path))
        clips.append((line.start_ms, path))
    engine.runAndWait()
    return clips


# ---------------------------------------------------------------------------
# Subtitle rendering
# ---------------------------------------------------------------------------


def draw_subtitle(image: QImage, text: str) -> None:
    """Render a subtitle bar at the bottom of *image*."""
    from PySide6.QtCore import Qt  # noqa: PLC0415

    bar_h = 72
    y = image.height() - bar_h
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.fillRect(0, y, image.width(), bar_h, QColor(0, 0, 0, 210))
    p.setPen(QColor(255, 255, 255))
    p.setFont(QFont("Segoe UI", 18))
    p.drawText(
        30, y, image.width() - 60, bar_h,
        int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter),
        text,
    )
    p.end()


# ---------------------------------------------------------------------------
# ffmpeg assembly
# ---------------------------------------------------------------------------


def _encode_frames(frame_dir: Path, output: Path, fps: float) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-framerate", f"{fps:.3f}",
        "-i", str(frame_dir / "frame_%06d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-movflags", "+faststart",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("ffmpeg encode stderr:\n", result.stderr, file=sys.stderr)
        sys.exit(result.returncode)


# ISO 639-2 codes, display labels, and TTS voice names per language.
_LANG_ISO: dict[str, str] = {
    "en": "eng",
    "de": "deu",
    "fr": "fra",
    "it": "ita",
    "rm": "roh",
}
_LANG_LABEL: dict[str, str] = {
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "it": "Italiano",
    "rm": "Rumantsch",
}
# edge-tts voice per language.  Rumantsch has no TTS voice in edge-tts.
_LANG_VOICES: dict[str, str] = {
    "en": "en-US-JennyNeural",
    "de": "de-DE-KatjaNeural",    # German (Germany)
    "fr": "fr-CH-ArianeNeural",  # Swiss French
    "it": "it-IT-ElsaNeural",    # Italian
}


def _compute_overlap_free_delays(
    clips: list[tuple[float, Path]],
    floor_starts_ms: list[float],
) -> list[int]:
    """Return overlap-free integer delay (ms) for each clip.

    Each clip starts at *floor_starts_ms[i]* at the earliest; if the previous
    clip has not yet finished (plus a 250 ms gap) the start is pushed forward.
    """
    adjusted: list[int] = []
    current_end = 0.0
    for i, (_, clip_path) in enumerate(clips):
        actual_start = max(floor_starts_ms[i], current_end + 250.0)
        adjusted.append(int(actual_start))
        dur = _probe_duration_ms(clip_path)
        current_end = actual_start + dur
    return adjusted


def _mix_clips_to_wav(
    clips: list[tuple[float, Path]],
    delays_ms: list[int],
    output: Path,
) -> bool:
    """Mix TTS clip files into a single WAV at the given millisecond offsets."""
    inputs: list[str] = []
    filter_parts: list[str] = []
    for i, ((_orig, clip_path), d) in enumerate(zip(clips, delays_ms)):
        inputs += ["-i", str(clip_path)]
        filter_parts.append(f"[{i}]adelay={d}|{d}[a{i}]")
    labels = "".join(f"[a{i}]" for i in range(len(clips)))
    mix = (
        f"{labels}amix=inputs={len(clips)}"
        ":normalize=0:duration=longest:dropout_transition=0[aout]"
    )
    filter_complex = ";".join(filter_parts) + ";" + mix
    cmd = (
        ["ffmpeg", "-y"]
        + inputs
        + ["-filter_complex", filter_complex, "-map", "[aout]", str(output)]
    )
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Audio mix failed:\n{result.stderr}", file=sys.stderr)
        return False
    return True


def _mux_streams(
    video: Path,
    audio_tracks: dict[str, Path],
    subtitle_files: dict[str, Path],
    output: Path,
) -> None:
    """Embed audio tracks + subtitle tracks into *video* in a single ffmpeg pass."""
    a_langs = list(audio_tracks.keys())
    s_langs = list(subtitle_files.keys())

    cmd = ["ffmpeg", "-y", "-i", str(video)]
    for lang in a_langs:
        cmd += ["-i", str(audio_tracks[lang])]
    for lang in s_langs:
        cmd += ["-i", str(subtitle_files[lang])]

    cmd += ["-map", "0:v"]
    for i in range(len(a_langs)):
        cmd += ["-map", str(i + 1)]
    for i in range(len(s_langs)):
        cmd += ["-map", str(len(a_langs) + 1 + i)]

    cmd += ["-c:v", "copy"]
    if a_langs:
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    if s_langs:
        cmd += ["-c:s", "mov_text"]

    for i, lang in enumerate(a_langs):
        iso   = _LANG_ISO.get(lang, lang)
        label = _LANG_LABEL.get(lang, lang)
        cmd += [f"-metadata:s:a:{i}", f"language={iso}"]
        cmd += [f"-metadata:s:a:{i}", f"title={label}"]
    for i, lang in enumerate(s_langs):
        iso   = _LANG_ISO.get(lang, lang)
        label = _LANG_LABEL.get(lang, lang)
        cmd += [f"-metadata:s:s:{i}", f"language={iso}"]
        cmd += [f"-metadata:s:s:{i}", f"title={label}"]

    cmd.append(str(output))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("ffmpeg mux stderr:\n", result.stderr, file=sys.stderr)
        sys.exit(result.returncode)


def assemble_video(
    frame_dir: Path,
    output: Path,
    fps: float = RECORD_FPS,
    audio_tracks: dict[str, Path] | None = None,
    subtitle_files: dict[str, Path] | None = None,
) -> None:
    """Stitch PNG frames into an MP4; optionally mux language audio + subtitle tracks."""
    if not shutil.which("ffmpeg"):
        print(
            f"WARNING: ffmpeg not found — frames saved to {frame_dir} "
            "but no video produced.",
            file=sys.stderr,
        )
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    n_frames = len(list(frame_dir.glob("*.png")))
    print(f"\nAssembling video with ffmpeg ({n_frames} frames)…")

    if audio_tracks:
        print(f"Embedding {len(audio_tracks)} audio track(s): {', '.join(audio_tracks)}")
    if subtitle_files:
        print(f"Embedding {len(subtitle_files)} subtitle track(s): {', '.join(subtitle_files)}")

    needs_mux = bool(audio_tracks) or bool(subtitle_files)
    step1_out = frame_dir / "_step1.mp4" if needs_mux else output
    _encode_frames(frame_dir, step1_out, fps)

    if needs_mux:
        _mux_streams(step1_out, audio_tracks or {}, subtitle_files or {}, output)
        step1_out.unlink(missing_ok=True)

    print(f"Video saved → {output}")


# ---------------------------------------------------------------------------
# QML application / engine factory
# ---------------------------------------------------------------------------


def make_app_and_engine(lang: str = "en") -> tuple[
    QGuiApplication,
    QQmlApplicationEngine,
    object,  # settingsModel
    object,  # hashModel
    object,  # verifyModel
    object,  # sanitizeModel
]:
    """Create the QGuiApplication, load Main.qml, and return all view models."""
    from hash_turbo.i18n import apply_language  # noqa: PLC0415
    apply_language(lang)

    from hash_turbo import __version__  # noqa: PLC0415
    from hash_turbo.gui.gettext_translator import GettextTranslator  # noqa: PLC0415
    from hash_turbo.gui.hash_view_model import HashViewModel  # noqa: PLC0415
    from hash_turbo.gui.sanitize_view_model import SanitizeViewModel  # noqa: PLC0415
    from hash_turbo.gui.settings_model import SettingsModel  # noqa: PLC0415
    from hash_turbo.gui.verify_view_model import VerifyViewModel  # noqa: PLC0415

    app = QGuiApplication(sys.argv)
    app.setApplicationName("hash-turbo")
    app.setOrganizationName("hash-turbo")
    QQuickStyle.setStyle("Material")

    translator = GettextTranslator(app)
    app.installTranslator(translator)

    engine = QQmlApplicationEngine()
    settings_model = SettingsModel()
    hash_model     = HashViewModel()
    verify_model   = VerifyViewModel()
    sanitize_model = SanitizeViewModel()

    ctx = engine.rootContext()
    ctx.setContextProperty("appVersion", __version__)
    ctx.setContextProperty("settingsModel", settings_model)
    ctx.setContextProperty("hashModel",     hash_model)
    ctx.setContextProperty("verifyModel",   verify_model)
    ctx.setContextProperty("sanitizeModel", sanitize_model)
    ctx.setContextProperty("userManualUrl", "")

    qml_path = PROJECT_ROOT / "src" / "hash_turbo" / "gui" / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))

    if not engine.rootObjects():
        print("ERROR: Failed to load QML", file=sys.stderr)
        sys.exit(1)

    return app, engine, settings_model, hash_model, verify_model, sanitize_model
