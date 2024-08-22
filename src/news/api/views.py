from rest_framework.views import APIView
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from news.serializers import *
from news.models import *
from .custom import CustomPagination
from authentication.api.auth.login import CheckUserSerializer



# =================================== Save =================================================================
class RestSaveNews(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = SaveNewsSerializer
    
    def post(self, request, *args, **kwargs):
        id = request.data.get('id')
        files_saving = request.data.get('files')


        if id:
            serializer = self.serializer_class(News.objects.get(id=id), data=request.data, context={'request': request})
        else:
            serializer = self.serializer_class(data=request.data, context={'request': request})
            
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        
        s = CheckUserSerializer(request.data).data

        news = serializer.save()
        
        if request.data.get('username'):
            user = User.objects.filter(username=request.data.get('username')).first()
            user = Facilitator.objects.filter(username=request.data.get('username')).first() if not user else user
        elif request.data.get('email'):
            user = User.objects.filter(email=request.data.get('email')).first()
            user = Facilitator.objects.filter(email=request.data.get('email')).first() if not user else user
        
        if user and not hasattr(user, 'no_sql_user'):
            news.user = user
        else:
            news.facilitator = user
        
        files = news.get_files()
        for file_saving in files_saving:
            file = NewsFile.objects.get(url=file_saving.get('url'))
            file.news = news

            principal = False
            if len(files) == 0:
                principal = True

            file.principal = principal
            file.save()

        news = news.save_and_return_object()

        try:
            return Response(
                NewsSerializer(
                    News.objects.get(id=news.pk),
                    many=False).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )


class RestSaveNewsFile(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = NewsFileSerializer
    
    def post(self, request, *args, **kwargs):
        id = request.data.get('id')
        urls = request.data.get('urls')
        serializer = self.serializer_class(data=request.data, context={'request': request})

        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        file = serializer.save()

        try:
            return Response(
                NewsFileSerializer(
                    NewsFile.objects.get(id=file.pk),
                    many=False).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )



# =================================== Get =================================================================
class RestGetCategories(APIView):
    throttle_classes = ()
    permission_classes = ()
    
    def post(self, request, *args, **kwargs):
        try:
            return Response(
                CategorySerializer(
                    Category.objects.all().order_by('name'),
                    many=True).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )
class RestGetCategoryById(APIView):
    throttle_classes = ()
    permission_classes = ()
    
    def post(self, request, pk, *args, **kwargs):
        try:
            return Response(
                CategorySerializer(
                    Category.objects.get(id=pk),
                    many=False).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )
        

class RestGetNews(APIView):
    throttle_classes = ()
    permission_classes = ()
    
    def post(self, request, *args, **kwargs):
        try:
            paginator = CustomPagination()
            paginated_data = paginator.paginate_queryset(News.objects.all().order_by('-created_date'), request)
            serializer = NewsSerializer(paginated_data, many=True)
            
            return paginator.get_paginated_response(serializer.data)
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )

class RestGetNewById(APIView):
    throttle_classes = ()
    permission_classes = ()
    
    def post(self, request, pk, *args, **kwargs):
        try:
            return Response(
                NewsSerializer(
                    News.objects.get(id=pk),
                    many=False).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )
        

class RestGetNewsByAttributes(APIView):
    throttle_classes = ()
    permission_classes = ()
    
    def post(self, request, *args, **kwargs):
        try:
            return Response(
                NewsSerializer(
                    News.objects.filter(**request.data).order_by('-created_date'),
                    many=True
                    ).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
class RestGetTags(APIView):
    throttle_classes = ()
    permission_classes = ()
    
    def post(self, request, *args, **kwargs):
        # try:
            return Response(
                TagSerializer(
                    Tag.objects.all().order_by('name'),
                    many=True
                    ).data, 
                status=status.HTTP_200_OK
            )
        # except Exception as exc:
        #     return Response(
        #         {'error': exc.__str__()}, 
        #         status=status.HTTP_404_NOT_FOUND
        #     )
        
class RestGetNewsFiles(APIView):
    throttle_classes = ()
    permission_classes = ()
    
    def post(self, request, *args, **kwargs):
        try:
            return Response(
                NewsFileSerializer(
                    NewsFile.objects.all().order_by('-created_date'),
                    many=True
                    ).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
class RestGetNewsFilesByAttributes(APIView):
    throttle_classes = ()
    permission_classes = ()
    
    def post(self, request, *args, **kwargs):
        try:
            return Response(
                NewsFileSerializer(
                    NewsFile.objects.filter(**request.data).order_by('-created_date'),
                    many=True
                    ).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )

class DeleteNewsAPIView(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data

        try:
            if user and hasattr(user, 'is_superuser') and user.is_superuser:
                _ = News.objects.get(id=request.data['id']).delete()
                return Response(
                    {'success': 'deleted'}, 
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {'error': exc.__str__()}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
class DeleteNewsFileAPIView(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data

        try:
            _ = NewsFile.objects.get(url=request.data['url']).delete()
            return Response(
                {'success': 'deleted'}, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )