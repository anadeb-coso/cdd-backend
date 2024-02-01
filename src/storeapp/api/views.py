from rest_framework.views import APIView
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from storeapp.serializers import StoreProjectSerializer
from storeapp.models import StoreProject
from .custom import CustomPagination


class RestGetStoreProjects(APIView):
    throttle_classes = ()
    permission_classes = ()
    
    def post(self, request, *args, **kwargs):
        try:
            return Response(
                StoreProjectSerializer(
                    StoreProject.objects.all().order_by('name'),
                    many=True).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )


class RestGetStoreProjectByPackage(APIView):
    throttle_classes = ()
    permission_classes = ()
    
    def post(self, request, package, *args, **kwargs):
        try:
            return Response(
                StoreProjectSerializer(
                    StoreProject.objects.get(package=package)
                    ).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )
