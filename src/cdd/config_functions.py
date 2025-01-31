from django.middleware.common import CommonMiddleware
from django.utils.deprecation import MiddlewareMixin


class CORSMiddleware(CommonMiddleware):
    def process_response(self, request, response):
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, DELETE, PUT, PATCH"
        response["Access-Control-Allow-Headers"] = "content-type, authorization, x-csrftoken, x-requested-with"
        return response
    

class CustomCORSMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if request.path.startswith("/static/"):  # Appliquer uniquement aux fichiers statiques
            response["Access-Control-Allow-Origin"] = "*"
        return response