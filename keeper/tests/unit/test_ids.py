from __future__ import annotations

from hermit_keeper.ids import new_id, seed_from_id


def test_prefixed_ulid_shape() -> None:
    value = new_id("pc")
    prefix, body = value.split("_", 1)
    assert prefix == "pc"
    assert len(body) == 26


def test_seed_is_deterministic_and_positive() -> None:
    value = new_id("pc")
    assert seed_from_id(value) == seed_from_id(value)
    assert 0 <= seed_from_id(value) < 2**31
