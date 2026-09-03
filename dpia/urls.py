from django.urls import path

from . import views

app_name = "dpia"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("about/", views.about, name="about"),
    path("assessments/<int:pk>/", views.assessment_detail, name="assessment_detail"),
    path("assessments/<int:pk>/export/pdf/", views.export_pdf, name="export_pdf"),
    path("assessments/new/step-1/", views.wizard_step1, name="wizard_step1"),
    path("assessments/new/step-2/", views.wizard_step2, name="wizard_step2"),
    path("assessments/new/step-3/", views.wizard_step3, name="wizard_step3"),
    path("assessments/new/step-4/", views.wizard_step4, name="wizard_step4"),
    path("assessments/new/step-5/", views.wizard_step5, name="wizard_step5"),
    path("assessments/new/cancel/", views.wizard_cancel, name="wizard_cancel"),
]
