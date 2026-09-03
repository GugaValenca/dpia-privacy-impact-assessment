"""PDF export of a single DPIA Assessment.

Structured like an audit-ready assessment document: processing
description, necessity & proportionality, risk factors and their
mitigations, and the final risk score with its recommendation — the same
sections the wizard walks through, in the same order. Mirrors Project
2's `ropa/exports.py` export pattern for visual/UX consistency across the
portfolio.
"""

from xml.sax.saxutils import escape as xml_escape

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone

from .models import Assessment
from .scoring import LEGAL_DISCLAIMER, calculate_assessment_risk

EXPORT_BASENAME = "DPIA-Privacy-Impact-Assessment-Export"

RISK_LEVEL_COLORS = {
    "low": "#1E7A34",
    "medium": "#8A5A00",
    "high": "#B3261E",
}


def _p(text: str, style):
    # reportlab's Paragraph parses its text as a small XML-like markup
    # language, so any value that isn't hardcoded markup we wrote
    # ourselves has to be escaped first — otherwise a stray "<" or "&" in
    # a free-text field (all editable through the wizard) gets silently
    # swallowed or reinterpreted as a tag instead of showing up in the
    # exported document.
    from reportlab.platypus import Paragraph

    return Paragraph(xml_escape(str(text)), style)


def export_pdf(assessment: Assessment) -> HttpResponse:
    # Imported lazily so the app still runs (dashboard, wizard, admin) if
    # reportlab isn't installed in a given environment; only the PDF
    # export route pays the import cost / failure.
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    generated_at = timezone.now()
    response = HttpResponse(content_type="application/pdf")
    timestamp = generated_at.strftime("%Y%m%d")
    response["Content-Disposition"] = (
        f'attachment; filename="{EXPORT_BASENAME}-{timestamp}.pdf"'
    )

    doc = SimpleDocTemplate(
        response,  # type: ignore[arg-type]
        pagesize=letter,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.5 * inch,
        title=f"{settings.SITE_TITLE} — {assessment.project_name}",
    )

    styles = getSampleStyleSheet()
    body_style = styles["Normal"]
    section_style = ParagraphStyle(
        "section", parent=styles["Heading2"], spaceBefore=14, spaceAfter=4
    )
    field_label_style = ParagraphStyle(
        "fieldLabel", parent=body_style, fontName="Helvetica-Bold", spaceBefore=6
    )
    disclaimer_style = ParagraphStyle(
        "disclaimer",
        parent=body_style,
        fontSize=8.5,
        textColor=colors.grey,
        borderColor=colors.HexColor("#CCCCCC"),
        borderWidth=0.5,
        borderPadding=8,
    )

    processing = assessment.processing_description
    necessity = assessment.necessity_proportionality
    risk = calculate_assessment_risk(assessment)
    risk_color_hex = RISK_LEVEL_COLORS[risk.risk_level.value]

    elements = [
        Paragraph(settings.SITE_TITLE, styles["Title"]),
        Paragraph("Data Protection Impact Assessment", styles["Heading2"]),
        _p(
            f"{assessment.project_name} — generated {generated_at.strftime('%Y-%m-%d %H:%M')} "
            f"— status: {assessment.get_status_display()}",
            body_style,
        ),
        Spacer(1, 0.1 * inch),
        Paragraph(
            "This is a simplified internal risk model inspired by common DPIA practice, "
            "not an official regulatory scoring system.",
            disclaimer_style,
        ),
    ]

    elements.append(Paragraph("1. Processing Description", section_style))
    for label, value in [
        ("Nature", processing.nature),
        ("Scope", processing.scope),
        ("Context", processing.context),
        ("Purpose", processing.purpose),
    ]:
        elements.append(Paragraph(label, field_label_style))
        elements.append(_p(value, body_style))

    elements.append(Paragraph("2. Necessity &amp; Proportionality", section_style))
    for label, value in [
        ("Necessity", necessity.necessity_justification),
        ("Proportionality", necessity.proportionality_justification),
        ("Alternatives considered", necessity.alternatives_considered or "None documented."),
        (
            "Data minimization measures",
            necessity.data_minimization_measures or "None documented.",
        ),
    ]:
        elements.append(Paragraph(label, field_label_style))
        elements.append(_p(value, body_style))

    elements.append(Paragraph("3. Risk Factors", section_style))
    risk_factors = list(assessment.risk_factors.all())
    if risk_factors:
        header = [_p(h, field_label_style) for h in ["Risk factor", "Severity", "Description"]]
        rows = [header]
        for factor in risk_factors:
            rows.append(
                [
                    _p(factor.name, body_style),
                    _p(str(factor.severity_weight), body_style),
                    _p(factor.description, body_style),
                ]
            )
        table = Table(rows, colWidths=[1.8 * inch, 0.8 * inch, 3.8 * inch], repeatRows=1)
        table.setStyle(
            TableStyle(  # type: ignore[arg-type]
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2A44")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F5F6F8")],
                    ),
                ]
            )
        )
        elements.append(table)
    else:
        elements.append(
            _p("No risk factors were identified for this processing activity.", body_style)
        )

    elements.append(Paragraph("4. Mitigation Measures", section_style))
    mitigations = list(assessment.mitigation_measures.all())
    if mitigations:
        header = [_p(h, field_label_style) for h in ["Risk factor", "Mitigation", "Impact"]]
        rows = [header]
        for mitigation in mitigations:
            rows.append(
                [
                    _p(mitigation.risk_factor.name, body_style),
                    _p(mitigation.description, body_style),
                    _p(f"-{mitigation.reduction_weight}", body_style),
                ]
            )
        table = Table(rows, colWidths=[1.8 * inch, 3.8 * inch, 0.8 * inch], repeatRows=1)
        table.setStyle(
            TableStyle(  # type: ignore[arg-type]
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2A44")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F5F6F8")],
                    ),
                ]
            )
        )
        elements.append(table)
    else:
        elements.append(_p("No mitigation measures were documented.", body_style))

    elements.append(Paragraph("5. Risk Score &amp; Recommendation", section_style))
    elements.append(
        Paragraph(
            f'<font color="{risk_color_hex}"><b>{risk.risk_level.label} risk</b></font> '
            f"&mdash; mitigated score {risk.mitigated_score} (raw score {risk.raw_score})",
            body_style,
        )
    )
    elements.append(Spacer(1, 0.05 * inch))
    elements.append(_p(risk.recommendation, body_style))

    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(LEGAL_DISCLAIMER, disclaimer_style))

    doc.build(elements)
    return response
