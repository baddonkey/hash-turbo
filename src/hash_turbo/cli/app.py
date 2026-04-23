"""CLI entry point — click commands for hash-turbo."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from hash_turbo import __version__
from hash_turbo.cli.formatters import OutputFormatter
from hash_turbo.core.hash_file import HashFileFormatter, HashFileParser
from hash_turbo.core.hasher import Hasher
from hash_turbo.core.models import (
    Algorithm,
    AlgorithmLike,
    HashFileFormat,
    HashResult,
    VerifyStatus,
)
from hash_turbo.core.sanitizer import (
    HashCase,
    LineEnding,
    PathSeparator,
    SanitizeOptions,
    Sanitizer,
    SortKey,
)
from hash_turbo.core.verifier import Verifier
from hash_turbo.infra.atomic_write import atomic_write_bytes, atomic_write_text
from hash_turbo.infra.executor import HashExecutor
from hash_turbo.infra.file_scanner import FileScanner
from hash_turbo.infra.hash_io import hash_file
from hash_turbo.infra.logging import LoggingSetup


class AlgorithmType(click.ParamType):
    """Click parameter type for hash algorithms."""

    name = "algorithm"

    def convert(
        self,
        value: str,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> AlgorithmLike:
        try:
            return Algorithm.from_str(value)
        except ValueError:
            self.fail(
                f"Unknown algorithm '{value}'. "
                "Run 'hash-turbo algorithms' to list available.",
                param, ctx,
            )


ALGORITHM_TYPE = AlgorithmType()


def _resolve_log_level(verbose: int) -> int:
    """Map ``-v`` count to a logging level."""
    if verbose >= 2:
        return logging.DEBUG
    if verbose >= 1:
        return logging.INFO
    return logging.WARNING


def _hide_windows_console() -> None:
    """Hide the console window on Windows before launching the GUI.

    Built with console=True so CLI stdout/stderr always work; this hides
    the window before Qt opens its first frame -- imperceptible in practice.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()  # type: ignore[attr-defined]
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE = 0  # type: ignore[attr-defined]
    except Exception:
        pass


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="hash-turbo")
@click.option(
    "-v", "--verbose",
    count=True,
    help="Increase log verbosity (-v=INFO, -vv=DEBUG).",
)
@click.option(
    "--log-file",
    type=click.Path(dir_okay=False),
    default=None,
    help="Also write logs to FILE (rotating).",
)
@click.pass_context
def main(ctx: click.Context, verbose: int, log_file: str | None) -> None:
    """hash-turbo — Cross-platform file hash management tool."""
    LoggingSetup.configure(
        level=_resolve_log_level(verbose),
        file_logging=log_file is not None,
        log_path=Path(log_file) if log_file else None,
    )
    if ctx.invoked_subcommand is None:
        # Headless / SSH session — refuse to launch GUI rather than
        # failing inside Qt with a confusing platform error.
        if sys.platform not in ("win32", "darwin"):
            import os as _os

            if not _os.environ.get("DISPLAY") and not _os.environ.get("WAYLAND_DISPLAY"):
                click.echo(
                    "Error: no display detected. The GUI requires a graphical "
                    "session.\nRun 'hash-turbo --help' for CLI usage.",
                    err=True,
                )
                ctx.exit(1)
                return

        try:
            from hash_turbo.gui.app import GuiApp
        except ImportError:
            click.echo(
                "Error: PySide6 is required for the GUI. "
                "Install it with: pip install PySide6",
                err=True,
            )
            ctx.exit(1)
            return

        _hide_windows_console()
        GuiApp.run()


@main.command(name="hash")
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("-a", "--algorithm", "algo", type=ALGORITHM_TYPE, default="sha256",
              help="Hash algorithm (default: sha256)")
@click.option("-r", "--recursive", is_flag=True, help="Recurse into directories")
@click.option("-g", "--glob", "glob_pattern", type=str, default=None,
              help="Filter files by glob pattern")
@click.option("--exclude", type=str, default=None, help="Exclude files matching pattern")
@click.option("-o", "--output", "output_file", type=click.Path(), default=None,
              help="Write hashes to file")
@click.option("--format", "fmt", type=click.Choice(["gnu", "bsd", "json"]),
              default="gnu", help="Output format")
@click.option("--path-mode", type=click.Choice(["relative", "absolute"]),
              default="relative", help="Path style in output")
@click.option("--base-dir", type=click.Path(exists=True, file_okay=False),
              default=None, help="Base directory for relative paths")
@click.option("-j", "--jobs", type=int, default=None,
              help="Number of parallel workers")
@click.option("--quiet", is_flag=True, help="Quiet output")
def hash_cmd(
    paths: tuple[str, ...],
    algo: AlgorithmLike,
    recursive: bool,
    glob_pattern: str | None,
    exclude: str | None,
    output_file: str | None,
    fmt: str,
    path_mode: str,
    base_dir: str | None,
    jobs: int | None,
    quiet: bool,
) -> None:
    """Generate file hashes."""
    input_paths = [Path(p) for p in paths]
    files = FileScanner.scan_paths(
        input_paths, recursive=recursive,
        glob_pattern=glob_pattern, exclude=exclude,
    )

    if not files:
        if not quiet:
            click.echo("No files found.", err=True)
        sys.exit(2)

    executor = HashExecutor()
    report = executor.hash_files_with_report(files, algorithm=algo, jobs=jobs)
    results = report.results

    for _item, exc in report.errors:
        click.echo(f"Error: {exc}", err=True)

    if path_mode == "relative":
        base = Path(base_dir) if base_dir else (
            Path(output_file).parent if output_file else Path.cwd()
        )
        results = _relativize_results(results, base)

    hash_format = HashFileFormat(fmt)

    if output_file:
        if hash_format is HashFileFormat.JSON:
            text = HashFileFormatter.format_json(results)
        elif hash_format is HashFileFormat.BSD:
            text = "\n".join(HashFileFormatter.format_bsd(r) for r in results) + "\n"
        else:
            text = "\n".join(HashFileFormatter.format_gnu(r) for r in results) + "\n"
        atomic_write_text(Path(output_file), text)
        if not quiet:
            click.echo(f"Written {len(results)} hash(es) to {output_file}")
    else:
        if (
            len(results) == 1
            and len(input_paths) == 1
            and input_paths[0].is_file()
            and fmt == "gnu"
        ):
            click.echo(OutputFormatter.format_single(results[0]))
        elif hash_format is HashFileFormat.JSON:
            click.echo(HashFileFormatter.format_json(results))
        elif hash_format is HashFileFormat.BSD:
            lines = [HashFileFormatter.format_bsd(r) for r in results]
            click.echo("\n".join(lines))
        else:
            click.echo(OutputFormatter.format_table(results))

    if report.errors:
        sys.exit(1)


@main.command(name="verify")
@click.argument("hashfile", required=False, type=click.Path(exists=True))
@click.option("--expect", type=str, default=None,
              help="Expected hash for inline verification")
@click.option("--strict", is_flag=True, help="Fail on missing files")
@click.option("-q", "--quiet", is_flag=True, help="Only show failures")
@click.option("--verbose", "verbose_out", is_flag=True,
              help="Print expected/computed on failures")
@click.option("-a", "--algorithm", "algo", type=ALGORITHM_TYPE, default="sha256",
              help="Algorithm for --expect mode")
@click.option("--algorithm-hint", "algo_hint", type=ALGORITHM_TYPE, default=None,
              help="Default algorithm for entries with no explicit type "
                   "(e.g. raw '<hash>  <path>' lines).")
@click.option("--base-dir", type=click.Path(exists=True, file_okay=False),
              default=None,
              help="Base directory for resolving relative paths in the hash "
                   "file (default: directory containing the hash file).")
@click.option(
    "--flexible-whitespace/--no-flexible-whitespace",
    default=True,
    help="Accept tabs and multiple spaces in GNU format (default: enabled)",
)
@click.option(
    "--binary-only/--no-binary-only",
    default=True,
    help="Always hash in binary mode; when disabled, respect the binary/text "
         "mode indicator (default: enabled)",
)
def verify_cmd(
    hashfile: str | None,
    expect: str | None,
    strict: bool,
    quiet: bool,
    verbose_out: bool,
    algo: AlgorithmLike,
    algo_hint: AlgorithmLike | None,
    base_dir: str | None,
    flexible_whitespace: bool,
    binary_only: bool,
) -> None:
    """Verify files against a hash file or expected hash."""
    hasher = Hasher()
    if expect and hashfile:
        file_path = Path(hashfile)
        try:
            result = hash_file(hasher, file_path, algo)
        except OSError as exc:
            click.echo(f"{file_path}: I/O error — {exc}", err=True)
            sys.exit(1)
        if result.hex_digest.lower() == expect.lower():
            if not quiet:
                click.echo(f"{file_path}: OK")
            sys.exit(0)
        else:
            click.echo(f"{file_path}: FAILED")
            if verbose_out:
                click.echo(f"  expected: {expect}", err=True)
                click.echo(f"  computed: {result.hex_digest}", err=True)
            sys.exit(1)

    if not hashfile:
        click.echo(
            "Error: provide a hash file or use --expect with a file path.",
            err=True,
        )
        sys.exit(2)

    hashfile_path = Path(hashfile)
    content = hashfile_path.read_text(encoding="utf-8")
    entries = HashFileParser.parse(
        content,
        flexible_whitespace=flexible_whitespace,
        algorithm_hint=algo_hint,
    )

    if not entries:
        click.echo("No hash entries found in file.", err=True)
        sys.exit(2)

    # Resolve relative entries against --base-dir; default is the manifest
    # directory.  Absolute paths in the manifest are honoured verbatim.
    base = Path(base_dir) if base_dir else hashfile_path.parent
    computed: dict[str, HashResult] = {}
    has_errors = False

    for entry in entries:
        entry_path = Path(entry.path)
        file_path = entry_path if entry_path.is_absolute() else base / entry_path

        try:
            exists = file_path.is_file()
        except OSError as exc:
            click.echo(f"{entry.path}: I/O error — {exc}", err=True)
            has_errors = True
            continue

        if not exists:
            if strict:
                has_errors = True
            continue

        bm = True if binary_only else entry.binary_mode
        try:
            result = hash_file(hasher, file_path, entry.algorithm, binary_mode=bm)
        except OSError as exc:
            click.echo(f"{entry.path}: I/O error — {exc}", err=True)
            has_errors = True
            continue

        computed[entry.path] = HashResult(
            path=entry.path,
            algorithm=result.algorithm,
            hex_digest=result.hex_digest,
        )

    verify_out = Verifier.verify_results(entries, computed)

    for vr in verify_out:
        if vr.status is VerifyStatus.OK:
            if not quiet:
                click.echo(f"{vr.entry.path}: OK")
        elif vr.status is VerifyStatus.FAILED:
            click.echo(f"{vr.entry.path}: FAILED")
            has_errors = True
        elif vr.status is VerifyStatus.MISSING:
            if strict:
                click.echo(f"{vr.entry.path}: MISSING")
                has_errors = True
            elif not quiet:
                click.echo(f"{vr.entry.path}: MISSING (warning)", err=True)

    if has_errors:
        sys.exit(1)


@main.command(name="sanitize")
@click.argument("hashfile", type=click.Path(exists=True))
@click.option(
    "--format", "fmt", type=click.Choice(["gnu", "bsd"]), default=None,
    help="Output format (default: keep original)",
)
@click.option(
    "--separator", type=click.Choice(["keep", "posix", "windows"]),
    default="keep", help="Path separator style",
)
@click.option(
    "--strip-prefix", type=str, default="",
    help="Remove this leading path prefix from all entries",
)
@click.option(
    "--hash-case", type=click.Choice(["keep", "lower", "upper"]),
    default="keep", help="Normalize hex digest casing",
)
@click.option(
    "--sort", "sort_key",
    type=click.Choice(["none", "path", "hash", "filesystem"]),
    default="none", help="Sort entries",
)
@click.option("--deduplicate", is_flag=True, help="Remove duplicate entries by path")
@click.option(
    "--line-ending", type=click.Choice(["system", "lf", "crlf", "cr"]),
    default="system", help="Line ending style (default: system)",
)
@click.option(
    "--normalize-whitespace/--no-normalize-whitespace",
    default=True,
    help="Accept and fix irregular whitespace in GNU format (default: enabled)",
)
@click.option(
    "-o", "--output", "output_file", type=click.Path(), default=None,
    help="Write result to file (default: stdout)",
)
def sanitize_cmd(
    hashfile: str,
    fmt: str | None,
    separator: str,
    strip_prefix: str,
    hash_case: str,
    sort_key: str,
    deduplicate: bool,
    line_ending: str,
    normalize_whitespace: bool,
    output_file: str | None,
) -> None:
    """Sanitize a hash manifest file — convert format, normalize paths, deduplicate."""
    hashfile_path = Path(hashfile)
    content = hashfile_path.read_text(encoding="utf-8")

    try:
        entries = HashFileParser.parse(
            content, flexible_whitespace=normalize_whitespace,
        )
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(2)

    if not entries:
        click.echo("No hash entries found in file.", err=True)
        sys.exit(2)

    if fmt is None:
        first_line = next(
            (ln.strip() for ln in content.splitlines()
             if ln.strip() and not ln.startswith("#")),
            "",
        )
        try:
            detected = HashFileFormatter.detect_format(
                first_line, flexible_whitespace=normalize_whitespace,
            )
        except ValueError:
            detected = HashFileFormat.GNU
        output_format = detected
    else:
        output_format = HashFileFormat(fmt)

    options = SanitizeOptions(
        output_format=output_format,
        path_separator=PathSeparator(separator),
        strip_prefix=strip_prefix,
        hash_case=HashCase(hash_case),
        sort_key=SortKey(sort_key),
        deduplicate=deduplicate,
        line_ending=LineEnding(line_ending),
    )

    sanitizer = Sanitizer(options)
    transformed = sanitizer.transform(entries)
    result_text = sanitizer.format(transformed)

    if output_file:
        # Bytes preserve the chosen line-ending sequences exactly and the
        # atomic write avoids leaving a half-written manifest behind.
        atomic_write_bytes(Path(output_file), result_text.encode("utf-8"))
        click.echo(f"Written {len(transformed)} entry/entries to {output_file}")
    else:
        click.echo(result_text, nl=False)


@main.command(name="algorithms")
def algorithms_cmd() -> None:
    """List available hash algorithms."""
    for algo in Algorithm.available():
        click.echo(f"  {algo.value}")


@main.command(name="gui")
def gui_cmd() -> None:
    """Launch the PySide6 GUI."""
    try:
        from hash_turbo.gui.app import GuiApp
    except ImportError:
        click.echo(
            "Error: PySide6 is required for the GUI. "
            "Install it with: pip install hash-turbo[gui]",
            err=True,
        )
        raise SystemExit(1)

    _hide_windows_console()
    GuiApp.run()


def _relativize_results(results: list[HashResult], base: Path) -> list[HashResult]:
    """Convert absolute paths in results to relative paths."""
    output: list[HashResult] = []
    base_resolved = base.resolve()
    for r in results:
        try:
            rel = Path(r.path).relative_to(base_resolved)
            output.append(HashResult(
                path=str(rel), algorithm=r.algorithm, hex_digest=r.hex_digest,
            ))
        except ValueError:
            output.append(r)
    return output


__all__ = ["main"]


if __name__ == "__main__":
    main()
