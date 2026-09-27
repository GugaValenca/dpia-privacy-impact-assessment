"""
Risk-scoring logic for the DPIA tool.

Deliberately isolated from views and models: this module takes plain data
in and returns plain data out, so it can be unit-tested directly (see
`dpia/tests.py`) and reused in two different contexts that otherwise
share nothing — the wizard's live preview (built from session data,
before anything is saved) and a saved Assessment's detail/PDF view (built
from the database).

DISCLAIMER: this is a simplified internal risk model inspired by common
DPIA practice, not an official regulatory scoring system, and its output
is not legal advice. See the module docstring in `dpia/models.py` for the
full disclaimer this mirrors.
"""

from dataclasses import dataclass
from enum import Enum


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def label(self) -> str:
        return {"low": "Low", "medium": "Medium", "high": "High"}[self.value]


# Thresholds against the *mitigated* score (see RiskFactorContribution
# below). Chosen so that a single high-severity, unmitigated risk factor
# (weight 3) stays Low on its own, two or three unmitigated factors move
# into Medium, and a genuinely risky combination (multiple high-severity
# factors, weakly mitigated) reaches High — a deliberately simple
# threshold model, not a calibrated statistical one.
LOW_MAX = 4
MEDIUM_MAX = 9

RECOMMENDATIONS: dict[RiskLevel, str] = {
    RiskLevel.LOW: (
        "Low risk under this simplified model. Standard privacy safeguards and "
        "periodic review are recommended before launch."
    ),
    RiskLevel.MEDIUM: (
        "Medium risk under this simplified model. Consider additional mitigations "
        "and a documented sign-off from a privacy lead before launch."
    ),
    RiskLevel.HIGH: (
        "High risk under this simplified model. A full DPIA review and consultation "
        "with legal/DPO is recommended before launch."
    ),
}

LEGAL_DISCLAIMER = (
    "This assessment is a simulation for demonstration purposes and "
    "does not constitute legal advice."
)


@dataclass(frozen=True)
class RiskFactorContribution:
    """One selected risk factor's contribution to the overall score,
    after its own mitigations are applied.

    `mitigation_reduction` is the sum of `reduction_weight` across every
    mitigation tied to this risk factor on this assessment. A risk
    factor's net contribution can't go below zero — a mitigation can
    fully neutralize a risk factor's weight but can't turn it into a
    negative offset against other, unrelated risk factors.
    """

    name: str
    severity_weight: int
    mitigation_reduction: int = 0

    @property
    def net_contribution(self) -> int:
        return max(0, self.severity_weight - self.mitigation_reduction)


@dataclass(frozen=True)
class RiskScoreResult:
    raw_score: int
    mitigated_score: int
    risk_level: RiskLevel
    recommendation: str
    contributions: tuple[RiskFactorContribution, ...]


def classify_risk_level(mitigated_score: int) -> RiskLevel:
    if mitigated_score <= LOW_MAX:
        return RiskLevel.LOW
    if mitigated_score <= MEDIUM_MAX:
        return RiskLevel.MEDIUM
    return RiskLevel.HIGH


def calculate_risk_score(
    contributions: list[RiskFactorContribution],
) -> RiskScoreResult:
    """Combine a set of risk-factor contributions into an overall score,
    risk level, and recommendation.

    An assessment with no selected risk factors scores 0 and is Low —
    the model has nothing to flag, which is a legitimate (if unusual)
    outcome rather than a special case to guard against.
    """
    raw_score = sum(c.severity_weight for c in contributions)
    mitigated_score = sum(c.net_contribution for c in contributions)
    risk_level = classify_risk_level(mitigated_score)
    return RiskScoreResult(
        raw_score=raw_score,
        mitigated_score=mitigated_score,
        risk_level=risk_level,
        recommendation=RECOMMENDATIONS[risk_level],
        contributions=tuple(contributions),
    )


def calculate_assessment_risk(assessment) -> RiskScoreResult:
    """Build a RiskScoreResult straight from a saved Assessment.

    Callers (the detail view, the PDF export) are expected to have
    already prefetched `risk_factors` and `mitigation_measures` on the
    queryset — this function makes no further queries of its own.
    """
    mitigations_by_factor: dict[int, int] = {}
    for mitigation in assessment.mitigation_measures.all():
        mitigations_by_factor[mitigation.risk_factor_id] = (
            mitigations_by_factor.get(mitigation.risk_factor_id, 0)
            + mitigation.reduction_weight
        )

    contributions = [
        RiskFactorContribution(
            name=factor.name,
            severity_weight=factor.severity_weight,
            mitigation_reduction=mitigations_by_factor.get(factor.id, 0),
        )
        for factor in assessment.risk_factors.all()
    ]
    return calculate_risk_score(contributions)
