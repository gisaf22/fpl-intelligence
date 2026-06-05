"""Unit tests for the canonical ADR-003 finding-key codec."""

from __future__ import annotations

import pytest

from domain.registry.finding_key import (
    FindingKey,
    FindingKeyError,
    build_key,
    lens_token,
    parse_key,
)

pytestmark = pytest.mark.unit


def test_lens_token_normalises():
    assert lens_token("FORM") == "form"
    assert lens_token("AVAIL") == "avail"
    assert lens_token("Market-Behavior") == "market_behavior"


def test_build_key_without_position():
    assert build_key("xgi_roll3", "FORM", "total_points") == "xgi_roll3@form:total_points"


def test_build_key_with_position():
    assert build_key("purchase_price", "MARKET", "total_points", "FWD") == "purchase_price@market:total_points#FWD"


def test_parse_key_lens_finding():
    assert parse_key("xgi_roll3@form:total_points") == FindingKey("xgi_roll3", "form", "total_points", None)


def test_parse_key_position_scoped():
    assert parse_key("minutes_roll3@avail:played_next_gw#MID") == FindingKey(
        "minutes_roll3", "avail", "played_next_gw", "MID"
    )


@pytest.mark.parametrize(
    "key",
    [
        "no_at_sign:target",
        "signal@lens_no_colon",
        "@form:total_points",  # empty signal
        "signal@:total_points",  # empty lens
        "signal@form:",  # empty target
        "signal@form:total_points#",  # trailing hash, empty position
    ],
)
def test_parse_key_rejects_malformed(key):
    with pytest.raises(FindingKeyError):
        parse_key(key)


@pytest.mark.parametrize(
    ("signal", "lens", "target", "position"),
    [
        ("xgi_roll3", "FORM", "total_points", None),
        ("minutes_roll3", "AVAIL", "played_next_gw", "MID"),
        ("purchase_price", "MARKET", "total_points", "FWD"),
    ],
)
def test_build_then_parse_round_trips(signal, lens, target, position):
    parsed = parse_key(build_key(signal, lens, target, position))
    assert parsed == FindingKey(signal, lens_token(lens), target, position)
