"""Paper gate reads a 20-day clean window instead of a hardcoded empty pick."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from research_loop.paper_gate import (
    CLEAN_WINDOW_DAYS,
    DEFAULT_ARMS_PATH,
    PRODUCTION_SCORE,
    BoundaryError,
    evaluate_default_paper_gate,
    evaluate_paper_gate,
    load_arms,
)

ROOT = Path(__file__).resolve().parents[1]


def _day(offset: int, pick: str = "600519.SH", *, clean: bool = True, void: bool = False) -> dict:
    session = date(2026, 9, 1) + timedelta(days=offset)
    return {
        "session_date": session.isoformat(),
        "clean": clean,
        "void": void,
        "pick5d_ml": pick,
    }


def _document(days: list[dict], **overrides) -> dict:
    document = {
        "schema_version": 1,
        "artifact": "paper_ab_ml_arms_void",
        "production_score": "v9-should-be-ignored",
        "approved": True,
        "status": "void" if not days else "filled",
        "clean_window": {"required_days": CLEAN_WINDOW_DAYS, "days": days},
    }
    document.update(overrides)
    return document


def test_landed_void_file_is_insufficient_not_a_hardcoded_empty_arm():
    decision = evaluate_default_paper_gate()

    assert DEFAULT_ARMS_PATH == ROOT / "control_plane" / "state" / "paper_ab_ml_arms_void.json"
    assert decision.pick5d_ml is None
    assert decision.promote is False
    assert decision.reason == "insufficient_clean_window"
    assert decision.clean_days == 0
    assert decision.required_days == 20
    assert decision.approved is False
    assert decision.production_score == PRODUCTION_SCORE == "v3.7"


def test_pick_comes_from_the_clean_window():
    first = evaluate_paper_gate(_document([_day(i, "600519.SH") for i in range(20)]))
    second = evaluate_paper_gate(_document([_day(i, "000001.SZ") for i in range(20)]))

    assert first.promote is True
    assert first.reason == "clean_window"
    assert first.pick5d_ml == "600519.SH"
    assert second.pick5d_ml == "000001.SZ"
    assert first.approved is False
    assert second.approved is False
    assert first.production_score == "v3.7"
    assert second.production_score == "v3.7"


def test_nineteen_clean_days_do_not_promote():
    decision = evaluate_paper_gate(_document([_day(i) for i in range(19)]))

    assert decision.promote is False
    assert decision.pick5d_ml is None
    assert decision.clean_days == 19
    assert decision.reason == "insufficient_clean_window"


def test_trailing_window_ignores_older_days_and_rejects_a_dirty_tail():
    older_dirty = [_day(0, clean=False)]
    clean = [_day(i + 1, "300750.SZ") for i in range(20)]
    ready = evaluate_paper_gate(_document(older_dirty + clean))
    spoiled = evaluate_paper_gate(
        _document(clean + [_day(21, "300750.SZ", clean=False)])
    )

    assert ready.promote is True
    assert ready.pick5d_ml == "300750.SZ"
    assert spoiled.promote is False
    assert spoiled.pick5d_ml is None
    assert spoiled.clean_days == 19


def test_void_or_blank_pick_is_not_clean():
    days = [_day(i) for i in range(20)]
    days[4] = _day(4, "600519.SH", void=True)
    days[5] = _day(5, "  ")

    decision = evaluate_paper_gate(_document(days))

    assert decision.promote is False
    assert decision.pick5d_ml is None
    assert decision.clean_days == 18


def test_window_length_cannot_shrink_below_twenty():
    document = _document([_day(i) for i in range(5)])
    document["clean_window"]["required_days"] = 5

    with pytest.raises(ValueError, match="20"):
        evaluate_paper_gate(document)


def test_tampered_approval_and_score_are_not_adopted():
    decision = evaluate_paper_gate(
        _document(
            [_day(i) for i in range(20)],
            approved=True,
            production_score="v3.8",
        )
    )

    assert decision.promote is True
    assert decision.approved is False
    assert decision.production_score == "v3.7"


def test_gate_refuses_production_control_paths(tmp_path: Path):
    for name in (
        "scoring_config.json",
        "PRIMARY.json",
        "orders/today.json",
        "models/shap_production.json",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        with pytest.raises(BoundaryError):
            load_arms(path)


def test_landed_artifact_matches_the_reader_contract():
    document = load_arms()

    assert document["artifact"] == "paper_ab_ml_arms_void"
    assert document["approved"] is False
    assert document["production_score"] == "v3.7"
    assert document["clean_window"]["required_days"] == 20
    assert document["clean_window"]["days"] == []
    assert document["status"] == "void"
