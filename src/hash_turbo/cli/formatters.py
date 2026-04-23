"""CLI output formatting."""

from __future__ import annotations

from typing import Sequence

from hash_turbo.core.models import HashResult


class OutputFormatter:
    """Formats hash results for CLI display."""

    @staticmethod
    def format_single(result: HashResult) -> str:
        """Format a single hash result for display: '<Algorithm>: <hash>'."""
        return f"{result.algorithm.display_name}: {result.hex_digest}"

    @staticmethod
    def format_table(results: Sequence[HashResult]) -> str:
        """Format multiple hash results as '<hash>  <path>' lines."""
        lines = [f"{r.hex_digest}  {r.path}" for r in results]
        return "\n".join(lines)


__all__ = ["OutputFormatter"]
