"""Forms for the 5-step DPIA wizard.

Steps 1-3 are plain ModelForms/Forms. Step 4 (mitigations) is the one
exception: which fields it needs depends on which risk factors were
picked in step 3, so its fields are built dynamically in `__init__`
rather than declared statically on the class.
"""

from django import forms

from .models import RiskFactor

REDUCTION_CHOICES = [
    ("", "No mitigation for this risk factor"),
    ("1", "Low impact (-1)"),
    ("2", "Medium impact (-2)"),
    ("3", "High impact (-3)"),
]


class ProcessingDescriptionForm(forms.Form):
    """Step 1: identifies the assessment (Assessment.project_name/
    description) and describes the processing itself
    (ProcessingDescription's fields) in one screen — they're presented
    together because a reviewer thinks of "what is this assessment" and
    "what does the processing involve" as the same first question."""

    project_name = forms.CharField(
        max_length=200,
        label="Project / activity name",
        help_text='e.g. "AI-Powered Product Recommendation Engine"',
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Assessment summary",
        help_text="A short summary of what's being proposed and why this assessment exists.",
    )
    nature = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Nature of the processing",
        help_text="What data is collected and how it will be processed.",
    )
    scope = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Scope of the processing",
        help_text="How much data, how many data subjects, how often.",
    )
    context = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Context of the processing",
        help_text="The relationship with data subjects and what they'd reasonably expect.",
    )
    purpose = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Purpose of the processing",
        help_text="Why this processing is being introduced.",
    )


class NecessityProportionalityForm(forms.Form):
    """Step 2: whether the processing is necessary and proportionate to
    its stated purpose."""

    necessity_justification = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Necessity",
        help_text="Why this purpose can't reasonably be achieved without this processing.",
    )
    proportionality_justification = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Proportionality",
        help_text="Why the amount/type of data processed is proportionate to the purpose.",
    )
    alternatives_considered = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        label="Less intrusive alternatives considered",
        help_text="Optional. Alternatives considered and why they were rejected.",
    )
    data_minimization_measures = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        label="Data minimization measures",
        help_text="Optional. Steps taken to limit collection/processing to what's needed.",
    )


class RiskFactorSelectionForm(forms.Form):
    """Step 3: which catalog risk factors apply to this processing
    activity. An empty selection is valid — see dpia/scoring.py."""

    risk_factors = forms.ModelMultipleChoiceField(
        queryset=RiskFactor.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Applicable risk factors",
    )


class MitigationForm(forms.Form):
    """Step 4: one optional mitigation per risk factor selected in step
    3. Fields are named `mitigate_<id>`, `description_<id>`,
    `reduction_<id>` so the view can read them back per risk factor
    without a formset — there's exactly one row per selected factor, a
    fixed and known count by the time this form is built.
    """

    def __init__(self, risk_factors, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.risk_factors = list(risk_factors)
        for factor in self.risk_factors:
            self.fields[f"mitigate_{factor.id}"] = forms.BooleanField(
                required=False, label=f"Add a mitigation for {factor.name}"
            )
            self.fields[f"description_{factor.id}"] = forms.CharField(
                required=False,
                widget=forms.Textarea(attrs={"rows": 2}),
                label="Mitigation description",
            )
            self.fields[f"reduction_{factor.id}"] = forms.ChoiceField(
                required=False, choices=REDUCTION_CHOICES, label="Expected impact"
            )

    def clean(self):
        cleaned_data = super().clean()
        for factor in self.risk_factors:
            if not cleaned_data.get(f"mitigate_{factor.id}"):
                continue
            if not cleaned_data.get(f"description_{factor.id}", "").strip():
                self.add_error(
                    f"description_{factor.id}",
                    "Describe the mitigation, or uncheck the box above.",
                )
            if not cleaned_data.get(f"reduction_{factor.id}"):
                self.add_error(
                    f"reduction_{factor.id}",
                    "Choose the mitigation's expected impact, or uncheck the box above.",
                )
        return cleaned_data

    def rows(self):
        """Pairs each risk factor with its three bound fields, for easy
        iteration in the template."""
        for factor in self.risk_factors:
            yield {
                "factor": factor,
                "mitigate": self[f"mitigate_{factor.id}"],
                "description": self[f"description_{factor.id}"],
                "reduction": self[f"reduction_{factor.id}"],
            }

    def mitigations_data(self) -> dict[str, dict]:
        """Selected mitigations as {risk_factor_id: {description, reduction_weight}},
        ready to store in the session."""
        result = {}
        for factor in self.risk_factors:
            if not self.cleaned_data.get(f"mitigate_{factor.id}"):
                continue
            result[str(factor.id)] = {
                "description": self.cleaned_data[f"description_{factor.id}"].strip(),
                "reduction_weight": int(self.cleaned_data[f"reduction_{factor.id}"]),
            }
        return result
