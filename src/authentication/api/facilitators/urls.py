from django.urls import path

from .update_adl import RestUpdateFacilitatorAdl
from .eadl_by_email import RestFacilitatorEadlByEmail

app_name = 'facilitators'

urlpatterns = [
    path('update-user-adls/', RestUpdateFacilitatorAdl.as_view(), name='update_user_adls'),
    path('eadl-by-email/', RestFacilitatorEadlByEmail.as_view(), name='eadl_by_email'),
]
