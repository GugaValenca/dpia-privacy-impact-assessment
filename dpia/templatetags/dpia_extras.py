"""Template tags shared across the DPIA wizard templates."""

from django import template

register = template.Library()

# Single source of truth for the wizard's step labels, so the step
# indicator shown on every wizard template can't drift out of sync with
# itself across steps.
WIZARD_STEP_LABELS = [
    "Processing description",
    "Necessity & proportionality",
    "Risk factors",
    "Mitigation measures",
    "Review & risk score",
]


@register.inclusion_tag("dpia/_wizard_steps.html")
def wizard_steps(step: int):
    return {"step": step, "labels": WIZARD_STEP_LABELS}
