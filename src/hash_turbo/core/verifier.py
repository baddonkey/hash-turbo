"""Verification logic — compare computed hashes against expected entries."""

from __future__ import annotations

from typing import Callable, Mapping, Sequence

from hash_turbo.core.models import HashEntry, HashResult, VerifyResult, VerifyStatus
from hash_turbo.core.path_key import normalize_path_key


class Verifier:
    """Compares computed hashes against expected entries."""

    @staticmethod
    def verify_entry(entry: HashEntry, computed: HashResult) -> VerifyResult:
        """Compare a single expected entry against its computed hash."""
        if entry.expected_hash.lower() == computed.hex_digest.lower():
            return VerifyResult(entry=entry, status=VerifyStatus.OK)
        return VerifyResult(entry=entry, status=VerifyStatus.FAILED)

    @staticmethod
    def verify_results(
        entries: Sequence[HashEntry],
        computed: Mapping[str, HashResult],
    ) -> list[VerifyResult]:
        """Batch-verify entries against a mapping of path → computed hash.

        The mapping may be keyed by the entry's raw ``path`` string or
        by the normalised lookup key (see
        :func:`hash_turbo.core.path_key.normalize_path_key`); both are
        tried, in that order.  Any entry that matches neither is
        reported as :class:`VerifyStatus.MISSING`.
        """
        normalised: dict[str, HashResult] = {
            normalize_path_key(k): v for k, v in computed.items()
        }
        results: list[VerifyResult] = []
        for entry in entries:
            hit = computed.get(entry.path)
            if hit is None:
                hit = normalised.get(normalize_path_key(entry.path))
            if hit is None:
                results.append(VerifyResult(entry=entry, status=VerifyStatus.MISSING))
            else:
                results.append(Verifier.verify_entry(entry, hit))
        return results

    @staticmethod
    def verify_with_lookup(
        entries: Sequence[HashEntry],
        compute: Callable[[HashEntry], HashResult | None],
    ) -> list[VerifyResult]:
        """Verify *entries* using a per-entry compute callback.

        The callback returns the computed :class:`HashResult` or
        ``None`` if the file is missing/unavailable.  Preferred over
        :meth:`verify_results` when the adapter already knows how to
        resolve a file path from an entry — keeps the lookup convention
        inside the verifier.
        """
        results: list[VerifyResult] = []
        for entry in entries:
            computed = compute(entry)
            if computed is None:
                results.append(VerifyResult(entry=entry, status=VerifyStatus.MISSING))
            else:
                results.append(Verifier.verify_entry(entry, computed))
        return results


__all__ = ["Verifier"]
