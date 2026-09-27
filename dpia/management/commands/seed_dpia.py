"""Seed the risk factor catalog and one complete example DPIA for
NimbusCart, the same fictional mid-size e-commerce company used in
Data-Mapping-ROPA, so the dashboard, wizard, risk scoring,
and PDF export all have something meaningful to show right away.

# TODO: VERIFY exact legal citation against official source.
The risk factor catalog below loosely follows the shape of well-known
DPIA screening criteria (the kind referenced in GDPR Art. 35 guidance and
CPRA risk-assessment practice), but no specific article, section, or
agency publication is cited as authority here — see the disclaimer in
`dpia/models.py` and `dpia/scoring.py`. Severity weights are an internal
1-3 scale for this simplified model, not a citation to any regulatory
severity scale.

Run with: python manage.py seed_dpia
Safe to re-run: it clears existing DPIA data first (--keep to skip that).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from dpia.models import (
    Assessment,
    MitigationMeasure,
    NecessityProportionality,
    ProcessingDescription,
    RiskFactor,
)


class Command(BaseCommand):
    help = "Seed the risk factor catalog and one example DPIA for NimbusCart (fictional e-commerce company)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep",
            action="store_true",
            help="Don't clear existing data before seeding.",
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            if not options["keep"]:
                self.stdout.write("Clearing existing DPIA data…")
                Assessment.objects.all().delete()
                RiskFactor.objects.all().delete()

            risk_factors = self._seed_risk_factors()
            self._seed_example_assessment(risk_factors)

        self.stdout.write(self.style.SUCCESS("Seed data loaded."))

    # -- Risk factor catalog ---------------------------------------------

    def _seed_risk_factors(self) -> dict[str, RiskFactor]:
        data = [
            (
                "Evaluation or scoring",
                "Profiling or predicting aspects of a person's behavior, "
                "preferences, or performance.",
                2,
            ),
            (
                "Automated decision-making with legal or similarly significant effect",
                "A decision about a person is made largely or entirely by an "
                "automated process, with an outcome that meaningfully affects them "
                "(e.g. eligibility, pricing, access to a service).",
                3,
            ),
            (
                "Systematic monitoring",
                "Observing, tracking, or scoring individuals' behavior in an "
                "ongoing, systematic way rather than as a one-off interaction.",
                2,
            ),
            (
                "Sensitive data or data of a highly personal nature",
                "Processing involves a special category of data or data that is "
                "otherwise highly personal (health, precise location, government ID).",
                3,
            ),
            (
                "Large-scale processing",
                "The processing covers a large number of data subjects, a large "
                "volume of data, or runs continuously across a broad population.",
                2,
            ),
            (
                "Matching or combining datasets",
                "Data from multiple sources or collected for different purposes "
                "is combined in ways the data subject wouldn't necessarily expect.",
                2,
            ),
            (
                "Data concerning vulnerable data subjects",
                "The data subjects are in a position where they can't easily "
                "consent, object, or exercise their rights (e.g. children, employees).",
                3,
            ),
            (
                "Innovative use or new technology",
                "The processing applies a technology or technique new to the "
                "organization, where the privacy impact isn't yet well understood.",
                2,
            ),
            (
                "Processing that limits data subjects' rights or access to a service",
                "The outcome of the processing could deny someone a right, a "
                "benefit, or access to a service or contract.",
                2,
            ),
        ]
        objs = {}
        for name, description, severity_weight in data:
            objs[name] = RiskFactor.objects.create(
                name=name, description=description, severity_weight=severity_weight
            )
        return objs

    # -- Example assessment ------------------------------------------------

    def _seed_example_assessment(self, risk_factors: dict[str, RiskFactor]):
        assessment = Assessment.objects.create(
            project_name="AI-Powered Product Recommendation Engine",
            description=(
                "Proposal to replace NimbusCart's rule-based 'best sellers' "
                "recommendations with a machine learning model that scores products "
                "for relevance using each customer's browsing history and purchase data."
            ),
            status=Assessment.Status.IN_REVIEW,
        )
        ProcessingDescription.objects.create(
            assessment=assessment,
            nature=(
                "Customer browsing history and purchase data are fed into a machine "
                "learning model that scores products for relevance and generates "
                "ranked recommendations shown on the storefront and in marketing emails."
            ),
            scope=(
                "Applies to all registered and guest customers browsing the NimbusCart "
                "storefront. Uses up to 12 months of browsing and purchase history per "
                "customer; recommendations refresh nightly."
            ),
            context=(
                "Customers already expect basic personalization (e.g. 'recently "
                "viewed'), but may not expect a predictive model scoring their "
                "preferences behind the scenes to drive what they're shown."
            ),
            purpose=(
                "Increase conversion and average order value by surfacing more "
                "relevant products, and improve the browsing experience."
            ),
        )
        NecessityProportionality.objects.create(
            assessment=assessment,
            necessity_justification=(
                "Rule-based recommendations ('best sellers') significantly "
                "underperform in click-through and conversion A/B testing; a scoring "
                "model is judged necessary to meaningfully improve on that baseline."
            ),
            proportionality_justification=(
                "The model uses only browsing and purchase data already collected to "
                "operate the storefront — no new data category is introduced to build it."
            ),
            alternatives_considered=(
                "A simpler 'customers who bought X also bought Y' rule was evaluated "
                "but produced materially weaker relevance in internal testing."
            ),
            data_minimization_measures=(
                "Browsing history is capped at 12 months and aggregated into "
                "behavioral features before being used by the model; raw "
                "click-by-click event logs are deleted after 90 days."
            ),
        )

        selected = [
            risk_factors["Evaluation or scoring"],
            risk_factors["Large-scale processing"],
            risk_factors["Systematic monitoring"],
            risk_factors["Matching or combining datasets"],
            risk_factors["Innovative use or new technology"],
        ]
        assessment.risk_factors.set(selected)

        MitigationMeasure.objects.create(
            assessment=assessment,
            risk_factor=risk_factors["Evaluation or scoring"],
            description=(
                "Customers can view a plain-language summary of why a product was "
                "recommended and opt out of personalized scoring, falling back to "
                "non-personalized best-sellers."
            ),
            reduction_weight=2,
        )
        MitigationMeasure.objects.create(
            assessment=assessment,
            risk_factor=risk_factors["Systematic monitoring"],
            description=(
                "Behavioral events are pseudonymized before being loaded into the "
                "model's feature store, and raw event logs are deleted after 90 days."
            ),
            reduction_weight=1,
        )
        MitigationMeasure.objects.create(
            assessment=assessment,
            risk_factor=risk_factors["Large-scale processing"],
            description=(
                "Access to the underlying browsing/purchase dataset is restricted to "
                "the ML engineering team through role-based access control."
            ),
            reduction_weight=1,
        )

        self.stdout.write(
            "Created 1 example assessment (AI-Powered Product Recommendation Engine)."
        )
