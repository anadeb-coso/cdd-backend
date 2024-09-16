from rest_framework.views import APIView
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from django.utils import timezone
from django.utils.translation import gettext_lazy
from datetime import datetime
import locale

from dashboard.facilitators.repository.db_facilitator_repository import FacilitatorRepository
from dashboard.facilitators.repository.facilitator_criteria import FacilitatorCriteria
from news.serializers import *
from news.models import *
from .custom import CustomPagination
from authentication.api.auth.login import CheckUserSerializer
from cdd.my_librairies.mail.send_mail import send_email



# =================================== Save =================================================================
class RestSaveNews(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = SaveNewsSerializer
    
    def post(self, request, *args, **kwargs):
        try:
            id = request.data.get('id')
            files_saving = request.data.get('files')
            publication_date = None
            publication_date_existed = False


            if id:
                news = News.objects.get(id=id)
                serializer = self.serializer_class(news, data=request.data, context={'request': request})
                if not news.publish and request.data.get('publish'):
                    publication_date = timezone.now()
                if news.publication_date:
                    publication_date_existed = True
            else:
                serializer = self.serializer_class(data=request.data, context={'request': request})
                
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data
            
            s = CheckUserSerializer(request.data).data

            news = serializer.save()
            
            if request.data.get('username'):
                user = User.objects.filter(username=request.data.get('username')).first()
                user = FacilitatorRepository(FacilitatorCriteria(
                    username=request.data.get('username'),
                    projects__id=[self.request.session.get('project_id')]
                )).first() if not user else user
            elif request.data.get('email'):
                user = User.objects.filter(email=request.data.get('email')).first()
                user = FacilitatorRepository(FacilitatorCriteria(
                        email=request.data.get('email'),
                        projects__id=[self.request.session.get('project_id')]
                    )
                ).first() if not user else user
            
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

            if not id and news.publish:
                news.publication_date = timezone.now()
            if publication_date:
                news.publication_date = publication_date

            news = news.save_and_return_object()
            
            if (not id and news.publish) or (not publication_date_existed and publication_date):
                try:
                    
                    locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
                    msg = send_email(
                        f"Nouvelle - COSO : {news.title}",
                        "mail/send/news",
                        {
                            "datas": {
                            },
                            "user": {
                            },
                            "url": f"",
                            "news": news,
                            "event_date": news.event_date.strftime('%A %d %B %Y à %H:%M') if news.event_date else None,
                            "publication_date": news.publication_date.strftime('%A %d %B %Y à %H:%M') if news.publication_date else None,
                            "files": news.get_files() if news.get_files().count() <= 3 else news.get_files()[:3],
                            "files_count": news.get_files().count() if news.get_files().count() <= 3 else 3,
                            "villages_exist": (len([ad for ad in news.administrative_levels if ad.get('type') == "Village"]) != 0) if news.administrative_levels else False
                        },
                        [
                            (subscrib.user.email if subscrib.user else subscrib.facilitator.email) for subscrib in  Subscription.objects.filter(category_id=news.category_id)
                        ],
                        [
                            "cosotogosig@gmail.com"
                        ]
                    )
                    
                    mail_message = gettext_lazy("Mail sent successfully")
                except Exception as exc:
                    print(exc)
                    mail_message = gettext_lazy("An error occurred while sending the email")

        
            return Response(
                NewsSerializer(
                    news,
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
        try:
            id = request.data.get('id')
            urls = request.data.get('urls')
            serializer = self.serializer_class(data=request.data, context={'request': request})

            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data
            file = serializer.save()

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
        try:
            serializer = self.serializer_class(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data

        
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
        try:
            serializer = self.serializer_class(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data

        
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
        


class SubscriptionAPIView(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data

            if request.data.get('save') == 'all':
                Subscription.objects.bulk_create([
                    (Subscription(facilitator=user,category_id = cat.id) if user and hasattr(user, 'no_sql_user') else Subscription(user=user,category_id = cat.id)) for cat in Category.objects.all()
                ])

                return Response(
                    {'success': 'ok'}, 
                    status=status.HTTP_200_OK
                )
            else:
                subscription = Subscription()
                if user and hasattr(user, 'no_sql_user'):
                    subscription.facilitator = user
                else:
                    subscription.user = user
                subscription.category_id = request.data['category']
                subscription = subscription.save_and_return_object()
                return Response(
                    SubscriptionSerializer(
                        Subscription.objects.get(id=subscription.pk),
                        many=False).data, 
                    status=status.HTTP_200_OK
                )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )
        

class RestGetSubscriptionsByUser(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data

            if user and hasattr(user, 'no_sql_user'):
                return Response(
                    SubscriptionSerializer(
                        Subscription.objects.filter(facilitator__id=user.id),
                        many=True).data, 
                    status=status.HTTP_200_OK
                )
            
            return Response(
                    SubscriptionSerializer(
                        Subscription.objects.filter(user__id=user.id),
                        many=True).data, 
                    status=status.HTTP_200_OK
                )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
class DeleteSubscriptionAPIView(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data

            if request.data.get('delete') == 'all':
                Subscription.objects.filter(id__in=request.data['ids']).delete()
            else:
                _ = Subscription.objects.get(id=request.data['id']).delete()
            return Response(
                {'success': 'deleted'}, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )