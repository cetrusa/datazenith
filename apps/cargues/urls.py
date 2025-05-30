#
from django.urls import path

from . import views
from .views import CargueInfoVentasPage
from .views_checktaskstatus import CheckCargueTaskStatusView

app_name = "cargues_app"

urlpatterns = [
    path(
        "cargue/",
        views.UploadZipView.as_view(),
        name="cargue",
    ),
    path(
        "cargue_planos_tsol/",
        views.UploadPlanoFilesView.as_view(),
        name="cargue_planos_tsol",
    ),
    path(
        "cargue-infoventas/", CargueInfoVentasPage.as_view(), name="cargue_infoventas"
    ),
    path(
        "check_task_status/",
        CheckCargueTaskStatusView.as_view(),
        name="check_task_status",
    ),
]
