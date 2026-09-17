import mimetypes
import os
import re
from django.conf import settings
from django.http import FileResponse, HttpResponse, Http404
from sys import platform
import requests

from cdd.functions import normalize_text

# Content-Type génériques qui ne servent à rien au navigateur pour décider comment
# afficher un fichier "inline" (S3 les renvoie parfois faute de métadonnée fiable à
# l'upload) — dans ce cas on préfère deviner depuis l'extension du fichier.
_GENERIC_CONTENT_TYPES = (None, '', 'application/octet-stream', 'binary/octet-stream')

# Caractères interdits/à éviter dans un nom de fichier (Windows + POSIX confondus).
_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]+')


def sanitize_filename_part(text, max_length=150):
    """Nettoie un morceau de nom de fichier (titre de pièce jointe, nom de
    village/canton…) : caractères interdits remplacés par un espace, espaces
    multiples réduits, longueur plafonnée. Réutilisé par
    ``dashboard.administrative_levels.views_doc`` (téléchargement individuel
    ET groupé — même règle de nommage partout)."""
    text = text.replace(".", "_")
    text = (
        normalize_text(text)
        .replace("telecharger le", "").replace("telecharger", "")
        .replace("/", "_").replace("\\", "_").replace(":", "_")
        .replace("*", "_").replace("?", "_").replace('"', "_")
        .replace("<", "_").replace(">", "_").replace("|", "_")
        .replace("'", "_").replace("’", "_").replace("`", "_")
        .replace("(", "_").replace(")", "_").replace("[", "_").replace("]", "_")
        .replace("{", "_").replace("}", "_")
        .replace("-", "_")
        .strip()
        .replace(" ", "_")
    )
    
    text = _UNSAFE_FILENAME_CHARS.sub(' ', str(text or '')).strip()
    text = re.sub(r'\s+', ' ', text)
    return text[:max_length]


def display_filename_with_suffix(base_name, suffix, url):
    """``"<base_name> (<suffix>)<extension de url>"`` (ou juste
    ``"<base_name><extension>"`` si ``suffix`` est vide), extension prise sur
    le NOM DE FICHIER RÉEL de ``url`` (jamais celle, potentiellement absente
    ou trompeuse, d'un ``base_name`` fourni par l'utilisateur)."""
    base = sanitize_filename_part(base_name) or 'fichier'
    suffix = sanitize_filename_part(suffix)
    ext = os.path.splitext(url.split('/')[-1].split('?')[0])[1]
    if suffix:
        return f"{base} ({suffix}){ext}"
    return f"{base}{ext}"


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
    if not url:
        raise Http404("Specify the url")

    # `?disposition=inline|attachment` (query string) permet à un lien du dashboard de
    # choisir explicitement le comportement (ex. "Ouvrir dans un nouvel onglet" veut un
    # affichage en ligne même quand cette vue est par ailleurs appelée en mode
    # téléchargement par défaut ailleurs). Absence du paramètre -> comportement historique
    # inchangé (`param_download`, True par défaut = téléchargement forcé), pour ne rien
    # casser sur les autres pages qui utilisent déjà cette route sans ce paramètre.
    disposition_param = request.GET.get('disposition')
    if disposition_param == 'inline':
        force_download = False
    elif disposition_param == 'attachment':
        force_download = True
    else:
        force_download = param_download

    r = requests.get(url, stream=True)
    if r.status_code != 200:
        raise Http404("File non found")

    # `?filename=` (query string, optionnel) : nom de fichier à afficher au
    # téléchargement/ouverture, différent du nom brut de l'URL — ex. « Titre
    # de la pièce jointe (Village) » plutôt que le nom S3 opaque. Absent ->
    # comportement historique inchangé (nom pris sur l'URL).
    custom_filename = request.GET.get('filename')
    if custom_filename:
        ext = os.path.splitext(url.split('/')[-1].split('?')[0])[1]
        filename = sanitize_filename_part(custom_filename) + ext
    else:
        filename = url.split("/")[-1]
    content_type = r.headers.get('Content-Type', 'application/octet-stream')
    if not force_download and content_type in _GENERIC_CONTENT_TYPES:
        # La source (S3) ne renvoie pas un type exploitable pour un affichage "inline" ->
        # le navigateur téléchargerait le fichier au lieu de l'afficher, même sans
        # Content-Disposition: attachment. On devine alors le type depuis l'extension.
        guessed_type, _ = mimetypes.guess_type(filename)
        if guessed_type:
            content_type = guessed_type

    response = HttpResponse(r.content, content_type=content_type)
    disposition = "attachment" if force_download else "inline"
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    return response