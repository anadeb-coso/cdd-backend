from rest_framework.views import APIView
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from supportmaterial.serializers import SubjectSerializer
from supportmaterial.models import Subject
from .custom import CustomPagination


class RestGetSubjects(APIView):
    throttle_classes = ()
    permission_classes = ()
    
    def post(self, request, *args, **kwargs):
        print(777777777777)
        # try:
        return Response(
            SubjectSerializer(
                Subject.objects.filter(parent=None).order_by('rank', 'name'),
                many=True).data, 
            status=status.HTTP_200_OK
        )
        # except Exception as exc:
        #     return Response(
        #         {'error': exc.__str__()}, 
        #         status=status.HTTP_404_NOT_FOUND
        #     )

