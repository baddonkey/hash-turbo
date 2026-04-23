"""Tests for ``Algorithm.from_str`` + ``DynamicAlgorithm``."""

from __future__ import annotations

import pytest

from hash_turbo.core.models import Algorithm, AlgorithmLike, DynamicAlgorithm


class TestAlgorithmFromStr:
    def test_well_known_returns_enum(self) -> None:
        result = Algorithm.from_str("sha256")
        assert result is Algorithm.SHA256

    def test_dash_underscore_normalisation(self) -> None:
        # 'sha3_256' (underscore) should resolve to the SHA3-256 enum.
        assert Algorithm.from_str("sha3_256") is Algorithm.SHA3_256

    def test_dynamic_algorithm_for_shake(self) -> None:
        result = Algorithm.from_str("shake_128")
        assert isinstance(result, DynamicAlgorithm)
        # The dash-normalisation accepts shake_128 via its dashed form;
        # any value that hashlib.new() accepts is fine.
        assert result.value in ("shake-128", "shake_128")

    def test_unknown_algorithm_raises(self) -> None:
        with pytest.raises(ValueError):
            Algorithm.from_str("definitely-not-a-real-algo-xyz")

    def test_protocol_satisfied_by_both(self) -> None:
        enum_algo: AlgorithmLike = Algorithm.SHA256
        dyn_algo: AlgorithmLike = Algorithm.from_str("shake_128")
        assert enum_algo.value
        assert enum_algo.display_name
        assert dyn_algo.value
        assert dyn_algo.display_name


class TestDynamicAlgorithm:
    def test_display_name_falls_back_to_uppercase(self) -> None:
        d = DynamicAlgorithm(value="shake_128")
        assert d.display_name == "SHAKE_128"

    def test_is_frozen(self) -> None:
        d = DynamicAlgorithm(value="md5")
        with pytest.raises((AttributeError, Exception)):
            d.value = "sha1"  # type: ignore[misc]
