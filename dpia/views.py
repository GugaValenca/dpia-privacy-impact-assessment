"""Views for the DPIA dashboard, assessment detail, PDF export, and the
5-step guided wizard.

The wizard stores its in-progress data in the session under SESSION_KEY,
one dict key per step, rather than writing to the database as it goes —
an Assessment (and its related rows) is only ever created once,
atomically, when the final step is confirmed (see `_save_assessment`).
That keeps an abandoned wizard, or a reload partway through, from ever
leaving a half-saved Assessment behind.
"""

from typing import TypedDict

from django.contrib import messages
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from . import exports
from .forms import (
    MitigationForm,
    NecessityProportionalityForm,
    ProcessingDescriptionForm,
    RiskFactorSelectionForm,
)
from .models import (
    Assessment,
    MitigationMeasure,
    NecessityProportionality,
    ProcessingDescription,
    RiskFactor,
)
from .scoring import (
    RiskFactorContribution,
    RiskScoreResult,
    calculate_assessment_risk,
    calculate_risk_score,
)

SESSION_KEY = "dpia_wizard"


class AssessmentRiskRow(TypedDict):
    """One dashboard row: an Assessment paired with its computed risk."""

    assessment: Assessment
    risk: RiskScoreResult


# Each step's session key names the piece of data that only exists once
# the *previous* step has been submitted — e.g. reaching step 3 requires
# "necessity" (written by step 2). `_require_step` walks this to find the
# earliest step a request hasn't actually finished yet, so the wizard
# can't be skipped ahead by guessing URLs.
STEP_REQUIREMENTS = {
    2: "processing",
    3: "necessity",
    4: "risk_factor_ids",
    5: "mitigations",
}
STEP_URL_NAMES = {
    1: "dpia:wizard_step1",
    2: "dpia:wizard_step2",
    3: "dpia:wizard_step3",
    4: "dpia:wizard_step4",
    5: "dpia:wizard_step5",
}


def _wizard_data(request: HttpRequest) -> dict:
    return request.session.setdefault(SESSION_KEY, {})


def _require_step(request: HttpRequest, step: int):
    """Returns a redirect to the earliest incomplete step if `step` can't
    be reached yet, else None."""
    data = _wizard_data(request)
    for candidate in range(2, step + 1):
        if STEP_REQUIREMENTS[candidate] not in data:
            previous = candidate - 1
            messages.info(request, f"Let's finish step {previous} first.")
            return redirect(STEP_URL_NAMES[previous])
    return None


def dashboard(request: HttpRequest) -> HttpResponse:
    assessments = Assessment.objects.all().prefetch_related(
        "risk_factors", "mitigation_measures"
    )
    assessments_with_risk: list[AssessmentRiskRow] = [
        {"assessment": assessment, "risk": calculate_assessment_risk(assessment)}
        for assessment in assessments
    ]
    high_risk_count = sum(
        1 for item in assessments_with_risk if item["risk"].risk_level.value == "high"
    )
    return render(
        request,
        "dpia/dashboard.html",
        {
            "assessments_with_risk": assessments_with_risk,
            "total_count": len(assessments_with_risk),
            "high_risk_count": high_risk_count,
        },
    )


def about(request: HttpRequest) -> HttpResponse:
    return render(request, "dpia/about.html")


def assessment_detail(request: HttpRequest, pk: int) -> HttpResponse:
    assessment = get_object_or_404(
        Assessment.objects.select_related(
            "processing_description", "necessity_proportionality"
        ).prefetch_related("risk_factors", "mitigation_measures__risk_factor"),
        pk=pk,
    )
    risk = calculate_assessment_risk(assessment)
    return render(
        request, "dpia/assessment_detail.html", {"assessment": assessment, "risk": risk}
    )


def export_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    assessment = get_object_or_404(
        Assessment.objects.select_related(
            "processing_description", "necessity_proportionality"
        ).prefetch_related("risk_factors", "mitigation_measures__risk_factor"),
        pk=pk,
    )
    return exports.export_pdf(assessment)


def wizard_step1(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ProcessingDescriptionForm(request.POST)
        if form.is_valid():
            data = _wizard_data(request)
            data["processing"] = form.cleaned_data
            request.session.modified = True
            return redirect("dpia:wizard_step2")
    else:
        form = ProcessingDescriptionForm(initial=_wizard_data(request).get("processing"))
    return render(request, "dpia/wizard_step1.html", {"form": form, "step": 1})


def wizard_step2(request: HttpRequest) -> HttpResponse:
    guard = _require_step(request, 2)
    if guard:
        return guard

    if request.method == "POST":
        form = NecessityProportionalityForm(request.POST)
        if form.is_valid():
            data = _wizard_data(request)
            data["necessity"] = form.cleaned_data
            request.session.modified = True
            return redirect("dpia:wizard_step3")
    else:
        form = NecessityProportionalityForm(initial=_wizard_data(request).get("necessity"))
    return render(request, "dpia/wizard_step2.html", {"form": form, "step": 2})


def wizard_step3(request: HttpRequest) -> HttpResponse:
    guard = _require_step(request, 3)
    if guard:
        return guard

    if request.method == "POST":
        form = RiskFactorSelectionForm(request.POST)
        if form.is_valid():
            data = _wizard_data(request)
            data["risk_factor_ids"] = [rf.id for rf in form.cleaned_data["risk_factors"]]
            # Selecting a different set of risk factors invalidates any
            # mitigations already recorded for factors no longer chosen,
            # and step 4 needs to be revisited either way.
            data.pop("mitigations", None)
            request.session.modified = True
            return redirect("dpia:wizard_step4")
    else:
        selected_ids = _wizard_data(request).get("risk_factor_ids", [])
        form = RiskFactorSelectionForm(initial={"risk_factors": selected_ids})
    return render(request, "dpia/wizard_step3.html", {"form": form, "step": 3})


def wizard_step4(request: HttpRequest) -> HttpResponse:
    guard = _require_step(request, 4)
    if guard:
        return guard

    data = _wizard_data(request)
    risk_factors = list(RiskFactor.objects.filter(id__in=data["risk_factor_ids"]))

    if request.method == "POST":
        form = MitigationForm(risk_factors, request.POST)
        if form.is_valid():
            data["mitigations"] = form.mitigations_data()
            request.session.modified = True
            return redirect("dpia:wizard_step5")
    else:
        initial: dict[str, bool | str] = {}
        for factor_id, mitigation in data.get("mitigations", {}).items():
            initial[f"mitigate_{factor_id}"] = True
            initial[f"description_{factor_id}"] = mitigation["description"]
            initial[f"reduction_{factor_id}"] = str(mitigation["reduction_weight"])
        form = MitigationForm(risk_factors, initial=initial)

    return render(
        request,
        "dpia/wizard_step4.html",
        {"form": form, "step": 4, "risk_factors": risk_factors},
    )


def wizard_step5(request: HttpRequest) -> HttpResponse:
    guard = _require_step(request, 5)
    if guard:
        return guard

    data = _wizard_data(request)
    risk_factors = list(RiskFactor.objects.filter(id__in=data["risk_factor_ids"]))
    review_rows = [
        {"factor": factor, "mitigation": data["mitigations"].get(str(factor.id))}
        for factor in risk_factors
    ]
    contributions = [
        RiskFactorContribution(
            name=factor.name,
            severity_weight=factor.severity_weight,
            mitigation_reduction=data["mitigations"]
            .get(str(factor.id), {})
            .get("reduction_weight", 0),
        )
        for factor in risk_factors
    ]
    risk = calculate_risk_score(contributions)

    if request.method == "POST":
        assessment = _save_assessment(data, risk_factors)
        request.session.pop(SESSION_KEY, None)
        messages.success(request, f'Assessment "{assessment.project_name}" saved.')
        return redirect("dpia:assessment_detail", pk=assessment.pk)

    return render(
        request,
        "dpia/wizard_step5.html",
        {"step": 5, "data": data, "review_rows": review_rows, "risk": risk},
    )


def wizard_cancel(request: HttpRequest) -> HttpResponse:
    request.session.pop(SESSION_KEY, None)
    return redirect("dpia:dashboard")


@transaction.atomic
def _save_assessment(data: dict, risk_factors: list[RiskFactor]) -> Assessment:
    """Writes the wizard's session data as a complete Assessment in one
    transaction. Only called from `wizard_step5` once every prior step's
    key is confirmed present by `_require_step`."""
    processing = data["processing"]
    necessity = data["necessity"]

    assessment = Assessment.objects.create(
        project_name=processing["project_name"],
        description=processing["description"],
    )
    ProcessingDescription.objects.create(
        assessment=assessment,
        nature=processing["nature"],
        scope=processing["scope"],
        context=processing["context"],
        purpose=processing["purpose"],
    )
    NecessityProportionality.objects.create(
        assessment=assessment,
        necessity_justification=necessity["necessity_justification"],
        proportionality_justification=necessity["proportionality_justification"],
        alternatives_considered=necessity.get("alternatives_considered", ""),
        data_minimization_measures=necessity.get("data_minimization_measures", ""),
    )
    assessment.risk_factors.set(risk_factors)
    for factor_id, mitigation in data["mitigations"].items():
        MitigationMeasure.objects.create(
            assessment=assessment,
            risk_factor_id=int(factor_id),
            description=mitigation["description"],
            reduction_weight=mitigation["reduction_weight"],
        )
    return assessment
