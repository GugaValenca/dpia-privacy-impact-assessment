"""
Data model for the DPIA-Privacy-Impact-Assessment tool.

A DPIA (Data Protection Impact Assessment) is a forward-looking review: a
company evaluates a *new* processing activity before it launches, instead
of documenting one already running (that's Data-Mapping-ROPA, the ROPA tool). This
model follows the same shape most DPIA templates use — describe the
processing, weigh its necessity and proportionality, identify which risk
factors apply, document mitigations, and arrive at an overall risk level
with a recommendation.

IMPORTANT — legal disclaimer for anyone reviewing this code:
This application is built around a fictional e-commerce company for
demonstration purposes. The risk-scoring model in `dpia/scoring.py` is a
simplified internal model inspired by common DPIA practice (it loosely
mirrors the shape of GDPR Art. 35 guidance and CPRA risk-assessment
practice, in structure only) — it is NOT an official regulatory scoring
system, and its output is NOT legal advice. Anywhere a real legal
citation, threshold, or deadline would need to be sourced from an actual
statute or regulator guidance, see the
`# TODO: VERIFY exact legal citation against official source` comments
below and in `dpia/management/commands/seed_dpia.py`.

VERIFIED 2026-10-02 (live web research this session, not from training
data): the "GDPR Art. 35 guidance" reference below is to the Article 29
Working Party's "Guidelines on Data Protection Impact Assessment"
(WP248 rev.01), endorsed by the EDPB, which really does list nine
criteria as indicators that processing is "likely to result in a high
risk" — language drawn directly from GDPR Art. 35(1) itself
(eur-lex.europa.eu/eli/reg/2016/679/oj). Cross-checked against the ICO's
published summary of WP248 (ico.org.uk, "When do we need to do a
DPIA?"). Separately, the CPPA's finalized CCPA/CPRA risk-assessment
regulations were approved by the CA Office of Administrative Law on
2025-09-23 and took effect 2026-01-01 (per contemporaneous legal-industry
reporting, e.g. Skadden and Freeman Mathis & Gary client alerts) — so
"CPRA risk-assessment practice" is a live, in-force regulatory regime as
of this verification, not a proposal. Neither check changes the
disclaimer above: this model still does not cite any specific article,
section, or agency publication as authority for its scoring — it only
confirms the *structural* resemblance claimed is genuine rather than
invented.
"""

from django.db import models


class RiskFactor(models.Model):
    """A catalog entry for a well-established DPIA risk trigger (e.g.
    "uses sensitive data", "large-scale processing"). Reusable across
    assessments, maintained through the Django admin.

    `severity_weight` feeds directly into `dpia.scoring.calculate_risk_score`
    — see that module for how it combines with mitigations into a final
    risk level. Weights are an internal 1-3 scale for this simplified
    model, not a citation to any specific regulatory severity scale.

    # This catalog's shape loosely follows well-known DPIA screening
    # criteria (e.g. WP29-style "likely high risk" indicators referenced
    # in GDPR Art. 35 guidance), but no specific article, section, or
    # agency publication is cited as authority here.
    #
    # VERIFIED 2026-10-02 via live web research against eur-lex.europa.eu
    # (GDPR Art. 35(1) text) and the ICO's published summary of the WP29
    # "WP248 rev.01" DPIA guidelines (endorsed by the EDPB): the real
    # WP248 nine-criteria list is "evaluation or scoring", "automated
    # decision-making with legal or similarly significant effect",
    # "systematic monitoring", "sensitive data or data of a highly
    # personal nature", "large-scale processing", "matching or combining
    # datasets", "data concerning vulnerable data subjects", "innovative
    # use or new technology", and "processing that prevents data subjects
    # from exercising a right or using a service or contract" — this is
    # genuinely a near-verbatim match to the nine entries seeded below, so
    # "loosely follows the shape of" is, if anything, an understatement of
    # the structural resemblance, not an overstatement. It remains true
    # that no specific article/section number is cited as legal authority
    # for any individual entry below — that framing is accurate and
    # intentionally left as-is; see `oag.ca.gov` / `planalto.gov.br` for
    # the CCPA/LGPD side of this catalog's inspiration, not yet
    # individually re-verified in this pass.
    """

    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(
        help_text="What this risk factor means and why it raises DPIA risk."
    )
    severity_weight = models.PositiveSmallIntegerField(
        help_text="Internal 1-3 severity scale used by the risk-scoring model (see dpia/scoring.py)."
    )

    class Meta:
        ordering = ("-severity_weight", "name")

    def __str__(self) -> str:
        return self.name


class Assessment(models.Model):
    """A single DPIA: one proposed processing activity under review.

    The four related sections (processing description, necessity &
    proportionality, risk factors, mitigations) are filled in over the
    5-step wizard (see `dpia/views.py`) and, together, are what the risk
    score and PDF export are built from.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_REVIEW = "in_review", "In review"
        APPROVED = "approved", "Approved"

    project_name = models.CharField(
        max_length=200,
        help_text="Name of the new processing activity or project being assessed.",
    )
    description = models.TextField(
        help_text="Short summary of what's being proposed and why this assessment exists."
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    risk_factors = models.ManyToManyField(
        RiskFactor,
        related_name="assessments",
        blank=True,
        help_text="Risk factors judged applicable to this processing activity.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.project_name

    @property
    def is_complete(self) -> bool:
        """True once every wizard section has been saved for this
        assessment. Assessments are only ever created at the end of the
        wizard (see `views.wizard_step5`), so in practice this is always
        True for a persisted Assessment — kept as an explicit check
        rather than an assumption, since a future edit flow could create
        a partial one."""
        return hasattr(self, "processing_description") and hasattr(
            self, "necessity_proportionality"
        )


class ProcessingDescription(models.Model):
    """Step 1 of the wizard: what the processing activity actually is."""

    assessment = models.OneToOneField(
        Assessment, on_delete=models.CASCADE, related_name="processing_description"
    )
    nature = models.TextField(help_text="What data is collected and how it will be processed.")
    scope = models.TextField(help_text="How much data, how many data subjects, how often.")
    context = models.TextField(
        help_text="The relationship with data subjects and what they'd reasonably expect."
    )
    purpose = models.TextField(help_text="Why this processing is being introduced.")

    def __str__(self) -> str:
        return f"Processing description for {self.assessment.project_name}"


class NecessityProportionality(models.Model):
    """Step 2 of the wizard: whether the processing is necessary and
    proportionate to its stated purpose — a documented judgment call, not
    a computed value."""

    assessment = models.OneToOneField(
        Assessment, on_delete=models.CASCADE, related_name="necessity_proportionality"
    )
    necessity_justification = models.TextField(
        help_text="Why this purpose can't reasonably be achieved without this processing."
    )
    proportionality_justification = models.TextField(
        help_text="Why the amount/type of data processed is proportionate to the purpose."
    )
    alternatives_considered = models.TextField(
        blank=True,
        help_text="Less intrusive alternatives that were considered and why they were rejected.",
    )
    data_minimization_measures = models.TextField(
        blank=True,
        help_text="Steps taken to limit collection/processing to what's actually needed.",
    )

    def __str__(self) -> str:
        return f"Necessity & proportionality for {self.assessment.project_name}"


class MitigationMeasure(models.Model):
    """A documented mitigation, tied to one specific risk factor on one
    specific assessment (e.g. "human review of automated recommendations"
    mitigating "automated decision-making with legal/significant
    effect"). `reduction_weight` is how many points it offsets on that
    risk factor's contribution to the final score."""

    assessment = models.ForeignKey(
        Assessment, on_delete=models.CASCADE, related_name="mitigation_measures"
    )
    risk_factor = models.ForeignKey(
        RiskFactor, on_delete=models.CASCADE, related_name="mitigation_measures"
    )
    description = models.TextField(
        help_text="What this mitigation is and how it reduces the associated risk."
    )
    reduction_weight = models.PositiveSmallIntegerField(
        default=1,
        help_text="How many points this mitigation offsets on its risk factor's severity (1-3).",
    )

    class Meta:
        ordering = ("assessment", "risk_factor")

    def __str__(self) -> str:
        return f"Mitigation for {self.risk_factor.name} on {self.assessment.project_name}"
