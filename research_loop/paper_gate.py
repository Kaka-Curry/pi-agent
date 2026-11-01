"""Paper-window gate for the ML arm.

``pick5d_ml`` is resolved from the trailing clean window in
``paper_ab_ml_arms_void.json``. A short or void window returns no pick.
That is an observation of the ledger, not a hardcoded empty arm.

``promote`` is only this paper-window observation. ``approved`` stays
false and the production score stays v3.7.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

PRODUCTION_SCORE = "v3.7"
CLEAN_WINDOW_DAYS = 20

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARMS_PATH = (
    REPO_ROOT / "control_plane" / "state" / "paper_ab_ml_arms_void.json"
)

_FORBIDDEN_PATH_MARKERS = (
    "scoring_config",
    "primary",
    "orders",
    "shap_production",
    "shap",
)


class BoundaryError(RuntimeError):
    """A research-loop path tried to cross a hard boundary."""


@dataclass(frozen=True)
class PaperGateDecision:
    pick5d_ml: str | None
    promote: bool
    approved: bool
    production_score: str
    clean_days: int
    required_days: int
    reason: str

    def as_dict(self) -> dict[str, object]:
        return {
            "pick5d_ml": self.pick5d_ml,
            "promote": self.promote,
            "approved": self.approved,
            "production_score": self.production_score,
            "clean_days": self.clean_days,
            "required_days": self.required_days,
            "reason": self.reason,
        }


def assert_research_read_path(path: Path) -> None:
    """Refuse reads that would pull production-control files into the gate."""
    lowered = path.as_posix().lower()
    for marker in _FORBIDDEN_PATH_MARKERS:
        if marker in lowered:
            raise BoundaryError(f"refusing to read research gate input from {path}")


def load_arms(path: Path | None = None) -> dict:
    source = DEFAULT_ARMS_PATH if path is None else Path(path)
    assert_research_read_path(source)
    with source.open(encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict):
        raise ValueError("paper arms document must be a JSON object")
    return document


def evaluate_paper_gate(document: Mapping) -> PaperGateDecision:
    """Read the clean 20-day window and resolve ``pick5d_ml`` from it."""
    required = _required_days(document)
    days = _days(document)
    full, clean_days, pick = _trailing_clean_pick(days, required)
    if not full:
        return _decision(
            pick5d_ml=None,
            promote=False,
            clean_days=clean_days,
            required_days=required,
            reason="insufficient_clean_window",
        )
    return _decision(
        pick5d_ml=pick,
        promote=True,
        clean_days=clean_days,
        required_days=required,
        reason="clean_window",
    )


def evaluate_default_paper_gate() -> PaperGateDecision:
    return evaluate_paper_gate(load_arms(DEFAULT_ARMS_PATH))


def _decision(
    *,
    pick5d_ml: str | None,
    promote: bool,
    clean_days: int,
    required_days: int,
    reason: str,
) -> PaperGateDecision:
    return PaperGateDecision(
        pick5d_ml=pick5d_ml,
        promote=promote,
        approved=False,
        production_score=PRODUCTION_SCORE,
        clean_days=clean_days,
        required_days=required_days,
        reason=reason,
    )


def _required_days(document: Mapping) -> int:
    window = document.get("clean_window")
    if not isinstance(window, Mapping):
        raise ValueError("paper arms document requires clean_window")
    if "required_days" not in window:
        raise ValueError("clean_window.required_days is required")
    declared = window["required_days"]
    if isinstance(declared, bool) or not isinstance(declared, int):
        raise ValueError("clean_window.required_days must be an integer")
    if declared != CLEAN_WINDOW_DAYS:
        raise ValueError(
            f"clean window must be {CLEAN_WINDOW_DAYS} days, got {declared}"
        )
    return declared


def _days(document: Mapping) -> list:
    window = document["clean_window"]
    days = window.get("days")
    if not isinstance(days, list):
        raise ValueError("clean_window.days must be a list")
    return days


def _trailing_clean_pick(
    days: list, required: int
) -> tuple[bool, int, str | None]:
    if len(days) < required:
        return False, sum(1 for day in days if _is_clean(day)), None
    tail = days[-required:]
    clean = [day for day in tail if _is_clean(day)]
    if len(clean) != required:
        return False, len(clean), None
    return True, required, str(clean[-1]["pick5d_ml"])


def _is_clean(day: object) -> bool:
    if not isinstance(day, Mapping):
        return False
    if day.get("void") is True or day.get("clean") is not True:
        return False
    pick = day.get("pick5d_ml")
    return isinstance(pick, str) and bool(pick.strip())
