from django.contrib import admin
from django_ratelimit.decorators import ratelimit

from .models import (
    Assessment,
    MitigationMeasure,
    NecessityProportionality,
    ProcessingDescription,
    RiskFactor,
)

admin.site.site_header = "DPIA-Privacy-Impact-Assessment Administration"
admin.site.site_title = "DPIA Admin"
admin.site.index_title = "Manage assessments & the risk factor catalog"

# The login form is the one publicly reachable, unauthenticated endpoint
# in this app, so it's the one worth rate limiting against brute force.
# mypy sees this as reassigning a method on an instance, which its type
# model doesn't allow even though Python (and Django's own AdminSite,
# built to have its attributes overridden this way) allows it fine.
admin.site.login = ratelimit(  # type: ignore[method-assign]
    key="ip", rate="5/m", method="POST", block=True
)(admin.site.login)


class ProcessingDescriptionInline(admin.StackedInline):
    model = ProcessingDescription
    can_delete = False


class NecessityProportionalityInline(admin.StackedInline):
    model = NecessityProportionality
    can_delete = False


class MitigationMeasureInline(admin.TabularInline):
    model = MitigationMeasure
    extra = 0


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("project_name", "status", "risk_level_display", "created_at")
    list_filter = ("status", "risk_factors")
    search_fields = ("project_name", "description")
    filter_horizontal = ("risk_factors",)
    inlines = (
        ProcessingDescriptionInline,
        NecessityProportionalityInline,
        MitigationMeasureInline,
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related("risk_factors", "mitigation_measures")
        )

    @admin.display(description="Risk level")
    def risk_level_display(self, obj: Assessment) -> str:
        from .scoring import calculate_assessment_risk

        return calculate_assessment_risk(obj).risk_level.label


@admin.register(RiskFactor)
class RiskFactorAdmin(admin.ModelAdmin):
    list_display = ("name", "severity_weight")
    list_filter = ("severity_weight",)
    search_fields = ("name", "description")


@admin.register(MitigationMeasure)
class MitigationMeasureAdmin(admin.ModelAdmin):
    list_display = ("assessment", "risk_factor", "reduction_weight")
    list_filter = ("risk_factor",)
    search_fields = ("description",)
