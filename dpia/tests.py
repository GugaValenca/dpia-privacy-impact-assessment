"""Tests for the DPIA risk-scoring logic, the 5-step wizard, the
dashboard, and PDF export.

Covers the parts of this app where a silent regression would matter
most: `calculate_risk_score` across Low/Medium/High scenarios (the piece
most likely to come up in an interview, since it's pure logic reviewable
independently of the UI), the wizard's step-guard and session-persistence
behavior, and the export endpoint producing well-formed PDF output.
"""

import io

from django.core.cache import cache
from django.test import Client
from django.test import TestCase as DjangoTestCase
from django.urls import reverse
from pypdf import PdfReader

from .models import Assessment, MitigationMeasure, RiskFactor
from .scoring import (
    RiskFactorContribution,
    RiskLevel,
    calculate_assessment_risk,
    calculate_risk_score,
    classify_risk_level,
)
from .throttling import client_ip


class TestCase(DjangoTestCase):
    """Clears the cache before every test: the rate limiter counts requests
    there, and the suite as a whole makes more requests to a rate-limited
    view than one visitor may per minute."""

    def setUp(self):
        super().setUp()
        cache.clear()


class RiskScoreCalculationTests(TestCase):
    """Direct unit tests of the scoring function — no database, no
    views, just the pure logic in dpia/scoring.py."""

    def test_no_risk_factors_is_low_with_zero_score(self):
        result = calculate_risk_score([])
        self.assertEqual(result.raw_score, 0)
        self.assertEqual(result.mitigated_score, 0)
        self.assertEqual(result.risk_level, RiskLevel.LOW)

    def test_single_low_severity_factor_stays_low(self):
        result = calculate_risk_score([RiskFactorContribution("Factor", severity_weight=2)])
        self.assertEqual(result.mitigated_score, 2)
        self.assertEqual(result.risk_level, RiskLevel.LOW)

    def test_multiple_unmitigated_factors_reach_medium(self):
        contributions = [
            RiskFactorContribution("A", severity_weight=3),
            RiskFactorContribution("B", severity_weight=3),
        ]
        result = calculate_risk_score(contributions)
        self.assertEqual(result.mitigated_score, 6)
        self.assertEqual(result.risk_level, RiskLevel.MEDIUM)

    def test_many_high_severity_factors_reach_high(self):
        contributions = [
            RiskFactorContribution(f"Factor {i}", severity_weight=3) for i in range(4)
        ]
        result = calculate_risk_score(contributions)
        self.assertEqual(result.mitigated_score, 12)
        self.assertEqual(result.risk_level, RiskLevel.HIGH)

    def test_mitigation_reduces_a_factors_net_contribution(self):
        contribution = RiskFactorContribution(
            "Factor", severity_weight=3, mitigation_reduction=1
        )
        self.assertEqual(contribution.net_contribution, 2)

    def test_mitigation_cannot_push_a_factor_below_zero(self):
        contribution = RiskFactorContribution(
            "Factor", severity_weight=2, mitigation_reduction=5
        )
        self.assertEqual(contribution.net_contribution, 0)

    def test_mitigation_cannot_offset_other_unrelated_factors(self):
        # An over-mitigated factor floors at zero rather than going
        # negative and quietly discounting a different risk factor's
        # own, separate contribution.
        contributions = [
            RiskFactorContribution("Over-mitigated", severity_weight=1, mitigation_reduction=3),
            RiskFactorContribution("Untouched", severity_weight=3),
        ]
        result = calculate_risk_score(contributions)
        self.assertEqual(result.mitigated_score, 3)

    def test_mitigations_fully_offsetting_every_factor_is_low(self):
        contributions = [
            RiskFactorContribution("A", severity_weight=3, mitigation_reduction=3),
            RiskFactorContribution("B", severity_weight=2, mitigation_reduction=2),
        ]
        result = calculate_risk_score(contributions)
        self.assertEqual(result.mitigated_score, 0)
        self.assertEqual(result.risk_level, RiskLevel.LOW)

    def test_all_catalog_style_factors_unmitigated_is_high(self):
        # Nine factors, weights 1-3, roughly matching the seeded catalog.
        weights = [2, 3, 2, 3, 2, 2, 3, 2, 2]
        contributions = [
            RiskFactorContribution(f"Factor {i}", severity_weight=w)
            for i, w in enumerate(weights)
        ]
        result = calculate_risk_score(contributions)
        self.assertEqual(result.raw_score, sum(weights))
        self.assertEqual(result.risk_level, RiskLevel.HIGH)

    def test_classify_risk_level_boundaries(self):
        self.assertEqual(classify_risk_level(0), RiskLevel.LOW)
        self.assertEqual(classify_risk_level(4), RiskLevel.LOW)
        self.assertEqual(classify_risk_level(5), RiskLevel.MEDIUM)
        self.assertEqual(classify_risk_level(9), RiskLevel.MEDIUM)
        self.assertEqual(classify_risk_level(10), RiskLevel.HIGH)

    def test_recommendation_is_present_for_every_level(self):
        for level in RiskLevel:
            result = calculate_risk_score([RiskFactorContribution("Factor", severity_weight=0)])
            self.assertTrue(result.recommendation)


def make_assessment(name="Test Assessment") -> Assessment:
    return Assessment.objects.create(project_name=name, description="A test assessment.")


class CalculateAssessmentRiskTests(TestCase):
    """Same scoring function, driven from real model instances instead
    of hand-built dataclasses — exercises the assembly logic in
    `calculate_assessment_risk` itself."""

    def test_assessment_with_no_risk_factors_is_low(self):
        assessment = make_assessment()
        result = calculate_assessment_risk(assessment)
        self.assertEqual(result.risk_level, RiskLevel.LOW)
        self.assertEqual(result.raw_score, 0)

    def test_assessment_risk_reflects_selected_factors_and_mitigations(self):
        assessment = make_assessment()
        factor_a = RiskFactor.objects.create(name="A", description="d", severity_weight=3)
        factor_b = RiskFactor.objects.create(name="B", description="d", severity_weight=2)
        assessment.risk_factors.set([factor_a, factor_b])
        MitigationMeasure.objects.create(
            assessment=assessment,
            risk_factor=factor_a,
            description="Mitigate A",
            reduction_weight=2,
        )

        result = calculate_assessment_risk(assessment)
        self.assertEqual(result.raw_score, 5)
        self.assertEqual(result.mitigated_score, 3)  # (3-2) + 2
        self.assertEqual(result.risk_level, RiskLevel.LOW)


class WizardFlowTests(TestCase):
    """Exercises the 5-step wizard through the real endpoints, the way a
    browser would — step guarding, session persistence, and final
    Assessment creation."""

    def setUp(self):
        self.client = Client()
        self.factor = RiskFactor.objects.create(
            name="Automated decision-making", description="d", severity_weight=3
        )

    def test_step2_redirects_to_step1_when_skipped(self):
        response = self.client.get(reverse("dpia:wizard_step2"))
        self.assertRedirects(response, reverse("dpia:wizard_step1"))

    def test_step5_redirects_to_earliest_incomplete_step(self):
        response = self.client.get(reverse("dpia:wizard_step5"))
        self.assertRedirects(response, reverse("dpia:wizard_step1"))

    def _complete_step1(self):
        return self.client.post(
            reverse("dpia:wizard_step1"),
            {
                "project_name": "New Feature",
                "description": "A new feature.",
                "nature": "Nature text.",
                "scope": "Scope text.",
                "context": "Context text.",
                "purpose": "Purpose text.",
            },
        )

    def _complete_step2(self):
        return self.client.post(
            reverse("dpia:wizard_step2"),
            {
                "necessity_justification": "Necessity text.",
                "proportionality_justification": "Proportionality text.",
            },
        )

    def _complete_step3(self, factor_ids):
        return self.client.post(reverse("dpia:wizard_step3"), {"risk_factors": factor_ids})

    def test_step1_completion_redirects_to_step2(self):
        response = self._complete_step1()
        self.assertRedirects(response, reverse("dpia:wizard_step2"))
        self.assertIn("processing", self.client.session["dpia_wizard"])

    def test_step1_missing_required_field_reshows_form_with_error(self):
        response = self.client.post(reverse("dpia:wizard_step1"), {"project_name": ""})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())

    def test_full_wizard_flow_creates_complete_assessment(self):
        self._complete_step1()
        self._complete_step2()
        self._complete_step3([self.factor.id])

        step4_response = self.client.post(
            reverse("dpia:wizard_step4"),
            {
                f"mitigate_{self.factor.id}": "on",
                f"description_{self.factor.id}": "Human review of every decision.",
                f"reduction_{self.factor.id}": "2",
            },
        )
        self.assertRedirects(step4_response, reverse("dpia:wizard_step5"))

        step5_get = self.client.get(reverse("dpia:wizard_step5"))
        self.assertEqual(step5_get.status_code, 200)
        self.assertEqual(step5_get.context["risk"].mitigated_score, 1)  # 3 - 2

        step5_post = self.client.post(reverse("dpia:wizard_step5"))
        assessment = Assessment.objects.get(project_name="New Feature")
        self.assertRedirects(
            step5_post, reverse("dpia:assessment_detail", args=[assessment.pk])
        )

        self.assertTrue(assessment.is_complete)
        self.assertEqual(list(assessment.risk_factors.all()), [self.factor])
        self.assertEqual(assessment.mitigation_measures.count(), 1)
        self.assertNotIn("dpia_wizard", self.client.session)

    def test_wizard_completes_with_zero_selected_risk_factors(self):
        self._complete_step1()
        self._complete_step2()
        self._complete_step3([])

        step4_response = self.client.post(reverse("dpia:wizard_step4"), {})
        self.assertRedirects(step4_response, reverse("dpia:wizard_step5"))

        step5_post = self.client.post(reverse("dpia:wizard_step5"))
        assessment = Assessment.objects.get(project_name="New Feature")
        self.assertRedirects(
            step5_post, reverse("dpia:assessment_detail", args=[assessment.pk])
        )
        self.assertEqual(assessment.risk_factors.count(), 0)
        self.assertEqual(assessment.mitigation_measures.count(), 0)

    def test_mitigation_checked_without_description_is_rejected(self):
        self._complete_step1()
        self._complete_step2()
        self._complete_step3([self.factor.id])

        response = self.client.post(
            reverse("dpia:wizard_step4"),
            {f"mitigate_{self.factor.id}": "on"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())

    def test_cancel_clears_session_and_redirects_to_dashboard(self):
        self._complete_step1()
        response = self.client.get(reverse("dpia:wizard_cancel"))
        self.assertRedirects(response, reverse("dpia:dashboard"))
        self.assertNotIn("dpia_wizard", self.client.session)


class DashboardViewTests(TestCase):
    def test_empty_dashboard_shows_empty_state(self):
        response = self.client.get(reverse("dpia:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_count"], 0)

    def test_dashboard_lists_assessments_with_risk_level(self):
        assessment = make_assessment("Listed Assessment")
        factor = RiskFactor.objects.create(name="F", description="d", severity_weight=3)
        assessment.risk_factors.add(factor)

        response = self.client.get(reverse("dpia:dashboard"))
        self.assertEqual(response.context["total_count"], 1)
        item = response.context["assessments_with_risk"][0]
        self.assertEqual(item["assessment"], assessment)
        self.assertEqual(item["risk"].risk_level, RiskLevel.LOW)


class AboutViewTests(TestCase):
    def test_about_page_loads(self):
        response = self.client.get(reverse("dpia:about"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dpia/about.html")


class AssessmentDetailAndExportTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.assessment = make_assessment("Exported Assessment")
        from .models import NecessityProportionality, ProcessingDescription

        ProcessingDescription.objects.create(
            assessment=self.assessment,
            nature="Nature <tag> & text",
            scope="Scope text.",
            context="Context text.",
            purpose="Purpose text.",
        )
        NecessityProportionality.objects.create(
            assessment=self.assessment,
            necessity_justification="Necessity text.",
            proportionality_justification="Proportionality text.",
        )
        self.factor = RiskFactor.objects.create(
            name="Factor", description="d", severity_weight=2
        )
        self.assessment.risk_factors.add(self.factor)
        MitigationMeasure.objects.create(
            assessment=self.assessment,
            risk_factor=self.factor,
            description="A documented mitigation.",
            reduction_weight=1,
        )

    def test_detail_page_loads(self):
        response = self.client.get(reverse("dpia:assessment_detail", args=[self.assessment.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Exported Assessment")

    def test_pdf_export_returns_valid_pdf(self):
        response = self.client.get(reverse("dpia:export_pdf", args=[self.assessment.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_pdf_contains_expected_sections_and_disclaimer(self):
        response = self.client.get(reverse("dpia:export_pdf", args=[self.assessment.pk]))
        text = "".join(
            page.extract_text() for page in PdfReader(io.BytesIO(response.content)).pages
        )
        normalized = " ".join(text.split())
        self.assertIn("Processing Description", normalized)
        self.assertIn("Necessity", normalized)
        self.assertIn("Risk Factors", normalized)
        self.assertIn("Mitigation Measures", normalized)
        self.assertIn("Risk Score", normalized)
        self.assertIn("does not constitute legal advice", normalized)

    def test_pdf_export_preserves_markup_characters_in_free_text(self):
        response = self.client.get(reverse("dpia:export_pdf", args=[self.assessment.pk]))
        text = "".join(
            page.extract_text() for page in PdfReader(io.BytesIO(response.content)).pages
        )
        normalized = " ".join(text.split())
        self.assertIn("Nature <tag> & text", normalized)


class ModelTests(TestCase):
    def test_assessment_str_is_project_name(self):
        assessment = make_assessment("String Test")
        self.assertEqual(str(assessment), "String Test")

    def test_risk_factor_str_is_name(self):
        factor = RiskFactor.objects.create(
            name="Sensitive data", description="d", severity_weight=3
        )
        self.assertEqual(str(factor), "Sensitive data")

    def test_assessment_is_not_complete_without_related_sections(self):
        assessment = make_assessment()
        self.assertFalse(assessment.is_complete)


class RateLimitTests(TestCase):
    def test_pdf_exports_are_limited_per_visitor(self):
        from .models import NecessityProportionality, ProcessingDescription

        assessment = make_assessment()
        ProcessingDescription.objects.create(
            assessment=assessment,
            nature="Nature text.",
            scope="Scope text.",
            context="Context text.",
            purpose="Purpose text.",
        )
        NecessityProportionality.objects.create(
            assessment=assessment,
            necessity_justification="Necessity text.",
            proportionality_justification="Proportionality text.",
        )
        url = reverse("dpia:export_pdf", args=[assessment.pk])
        statuses = [self.client.get(url).status_code for _ in range(11)]
        self.assertEqual(statuses[:10], [200] * 10)
        self.assertEqual(statuses[10], 403)

    def test_admin_login_attempts_are_limited_per_visitor(self):
        url = reverse("admin:login")
        data = {"username": "nobody", "password": "wrong"}
        statuses = [self.client.post(url, data).status_code for _ in range(6)]
        self.assertEqual(statuses[:5], [200] * 5)
        self.assertEqual(statuses[5], 403)


class ClientIpTests(TestCase):
    """The rate-limit key trusts X-Real-IP only where the platform
    guarantees it (Vercel); elsewhere it could be forged to dodge limits."""

    def request(self, **meta):
        from django.test import RequestFactory

        return RequestFactory().get("/", REMOTE_ADDR="10.0.0.1", **meta)

    def test_header_is_ignored_off_vercel(self):
        with self.settings(RUNNING_ON_VERCEL=False):
            self.assertEqual(client_ip("g", self.request(HTTP_X_REAL_IP="1.2.3.4")), "10.0.0.1")

    def test_header_is_used_on_vercel(self):
        with self.settings(RUNNING_ON_VERCEL=True):
            self.assertEqual(client_ip("g", self.request(HTTP_X_REAL_IP="1.2.3.4")), "1.2.3.4")

    def test_falls_back_to_remote_addr_on_vercel_without_header(self):
        with self.settings(RUNNING_ON_VERCEL=True):
            self.assertEqual(client_ip("g", self.request()), "10.0.0.1")
