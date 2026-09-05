import os
from django.conf import settings
from django.http import FileResponse, HttpResponse, Http404
from sys import platform
import requests


def download(request, path, content_type="application/pdf", param_download=True):
    # -
    if ".." in path:
        raise Http404("Invalid file path")

    file_path = os.path.join(settings.MEDIA_ROOT, path)
    if os.path.exists(file_path):
        # FileResponse envoie le fichier par blocs (streaming) plutôt que de le charger
        # intégralement en mémoire avec fh.read() : évite un pic mémoire sur les gros
        # exports et laisse le serveur commencer à répondre sans attendre d'avoir tout lu.
        content = 'inline; filename=' + os.path.basename(file_path)
        if param_download:
            content = "attachment; filename=" + os.path.basename(file_path)
        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
        response['Content-Disposition'] = content
        return response
    raise Http404


def download_file_view(request, path, content_type):
    if path:
        if platform == "win32":
            # windows
            path = path.replace("___", "\\")
        else:
            path = path.replace('___', '/')
            
    if content_type in (None, 'None'):
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    return download(
        request, 
        path,
        content_type
    )


def download_from_url(request, param_download=True):
    url = request.GET.get('url')
    if url:
        r = requests.get(url, stream=True)
        if r.status_code == 200:
            filename = url.split("/")[-1]
            response = HttpResponse(r.content, content_type=r.headers.get('Content-Type', 'application/octet-stream'))
            if param_download:
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
            else:
                response['Content-Disposition'] = f'inline; filename="{filename}"'
            return response
        else:
            raise Http404("File non found")
    else:
        raise Http404("Specify the url")