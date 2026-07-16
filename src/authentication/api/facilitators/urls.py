from django.urls import path

from .update_adl import RestUpdateFacilitatorAdl

app_name = 'facilitators'

urlpatterns = [
    path('update-user-adls/', RestUpdateFacilitatorAdl.as_view(), name='update_user_adls'),
]
