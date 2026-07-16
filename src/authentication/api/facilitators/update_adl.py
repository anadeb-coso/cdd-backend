from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from django.utils.translation import gettext_lazy as _
from datetime import datetime

from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
# from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from authentication.models import Facilitator
from planning.serializers import *
from planning.models import *
from authentication.api.facilitators.serializers import FacilitatorUpdateAdlSerializer
from cdd.my_librairies.mail.send_mail import send_email
from cdd.functions import get_dates_between
from cdd.call_objects_from_other_db import mis_objects_call
from subprojects.models import Project as MisProject
from administrativelevels import models as administrativelevels_models
from cdd.functions import list_with_and
from dashboard.utils import search_facilitators_db_with_villages_stabilized



class RestUpdateFacilitatorAdl(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = FacilitatorUpdateAdlSerializer
    
    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data
            
            facilitator = validated_data["user"]

            facilitator.stabilization_administrative_ids = validated_data["stabilization_administrative_ids"]
            facilitator.additional_administrative_ids = validated_data["additional_administrative_ids"]

            facilitator.simple_save()

            stabilization_administrative = list(mis_objects_call.filter_objects(
                administrativelevels_models.AdministrativeLevel,
                id__in=facilitator.stabilization_administrative_ids
            ).values_list('name', flat=True))

            administrative_levels = list(mis_objects_call.filter_objects(
                administrativelevels_models.AdministrativeLevel,
                id__in=facilitator.administrative_levels_ids
            ).values_list('name', flat=True))

            additional_administrative = list(mis_objects_call.filter_objects(
                administrativelevels_models.AdministrativeLevel,
                id__in=[x for x in facilitator.additional_administrative_ids if x not in [(facilitator.administrative_levels_ids or list()) + (facilitator.stabilization_administrative_ids or list())]]
            ).values_list('name', flat=True))

            # Update facilitator no_sql_dbs_names
            if hasattr(facilitator, 'projects') and hasattr(facilitator, 'no_sql_db_name') and facilitator.no_sql_db_name:
                project = facilitator.projects.first()
                if project:
                    search_facilitators_db_with_villages_stabilized(project.name, no_sql_db=facilitator.no_sql_db_name)

            datas = {}
            
            if stabilization_administrative:
                datas[_("Areas of ​​intervention")] = list_with_and(stabilization_administrative)

            if administrative_levels:
                datas[_("Default zones")] = list_with_and(administrative_levels)
            
            if additional_administrative:
                datas[_("Additional locations")] = list_with_and(additional_administrative)


            _status = send_email(
                f'[COSO Apps : {datetime.now().strftime("%Y-%m-%d")}] {_("Update your service areas")}',
                "mail/send/notification",
                {
                    'title': _("Update your service areas"),
                    "datas": datas,
                    "user": {
                        _("Name"): facilitator.name,
                        _("Phone"): facilitator.phone,
                        _("Email"): facilitator.email
                    },
                    "user_full_name": facilitator.name,
                    "comment":  _("Below you will find information relating to your areas of intervention."), 
                    "greeting":  _("Hello"),
                    "all_sex":  _("Mr./Mrs."),
                    'current_year': datetime.now().year,
                    "details_btn": False
                },
                [facilitator.email]
            )    

        except Exception as exc:
            return Response(
                {'error': exc.__str__(), 'status': 'error'}, 
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
                {'success': 'ok', 'status': 'success'}, 
                status=status.HTTP_200_OK
            )