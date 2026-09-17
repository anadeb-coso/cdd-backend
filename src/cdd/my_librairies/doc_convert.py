"""
Conversion PDF <-> Word à la demande (bouton "Convertir" du dashboard,
`/fr/administrative-levels/documents/` et ailleurs).

- **PDF -> Word (.docx)** : `pdf2docx` (pur Python, s'appuie sur PyMuPDF en
  interne) — aucune dépendance système externe, fonctionne dès que le paquet
  Python est installé (voir requirements.txt).
- **Word (.docx/.doc) -> PDF** : nécessite LibreOffice en mode headless
  (binaire `soffice`) installé SUR LE SERVEUR — aucune bibliothèque Python
  pure ne produit une conversion Word -> PDF fidèle (mise en page, polices)
  sans un vrai moteur de rendu bureautique, et Microsoft Office/`docx2pdf`
  n'est pas une option côté serveur (Windows + licence Office requis).
  `_soffice_binary()` lève une erreur claire (plutôt qu'un plantage obscur)
  si LibreOffice n'est pas trouvé — **à installer sur le serveur de
  déploiement** (`apt install libreoffice` ou équivalent) pour activer cette
  direction de conversion.
"""
import os
import shutil
import subprocess
import tempfile

import requests


class DocConversionError(Exception):
    """Erreur de conversion — message déjà rédigé pour être affiché tel quel."""


def _download_to_temp(url, suffix):
    resp = requests.get(url, stream=True, timeout=60)
    if resp.status_code != 200:
        raise DocConversionError(f"Impossible de récupérer le fichier source (HTTP {resp.status_code}).")
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    fh.write(chunk)
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise
    return path


def convert_pdf_to_docx_bytes(source_url):
    """Télécharge le PDF ``source_url``, le convertit en ``.docx`` (pdf2docx),
    renvoie les octets du fichier Word résultant. Lève ``DocConversionError``
    en cas d'échec (fichier introuvable, PDF illisible, dépendance absente…)."""
    try:
        from pdf2docx import Converter
    except ImportError:
        raise DocConversionError(
            "La conversion PDF -> Word n'est pas disponible sur ce serveur "
            "(dépendance Python 'pdf2docx' manquante)."
        )

    pdf_path = _download_to_temp(source_url, ".pdf")
    docx_path = pdf_path[:-4] + ".docx"
    try:
        cv = Converter(pdf_path)
        try:
            cv.convert(docx_path)
        finally:
            cv.close()
        if not os.path.exists(docx_path):
            raise DocConversionError("La conversion PDF -> Word a échoué (aucun fichier produit).")
        with open(docx_path, "rb") as fh:
            return fh.read()
    except DocConversionError:
        raise
    except Exception as exc:
        raise DocConversionError(f"La conversion PDF -> Word a échoué : {exc}")
    finally:
        for p in (pdf_path, docx_path):
            try:
                os.remove(p)
            except OSError:
                pass


def _soffice_binary():
    """Chemin de l'exécutable LibreOffice headless, ou ``None`` si introuvable
    (PATH, puis emplacements d'installation standard Windows/Linux)."""
    for name in ("soffice", "soffice.exe"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/usr/bin/soffice",
        "/usr/bin/libreoffice",
        "/opt/libreoffice/program/soffice",
        "/opt/libreoffice7.6/program/soffice",
    ):
        if os.path.exists(candidate):
            return candidate
    return None


def convert_docx_to_pdf_bytes(source_url):
    """Télécharge le document Word ``source_url``, le convertit en PDF via
    LibreOffice headless (``soffice --headless --convert-to pdf``), renvoie
    les octets du PDF résultant. Lève ``DocConversionError`` (message déjà
    utilisateur) si LibreOffice est introuvable, échoue ou dépasse le délai."""
    soffice = _soffice_binary()
    if not soffice:
        raise DocConversionError(
            "La conversion Word -> PDF n'est pas disponible sur ce serveur "
            "(LibreOffice n'est pas installé)."
        )

    suffix = ".docx" if ".docx" in source_url.lower() else ".doc"
    src_path = _download_to_temp(source_url, suffix)
    out_dir = tempfile.mkdtemp()
    try:
        proc = subprocess.run(
            [soffice, "--headless", "--norestore", "--convert-to", "pdf", "--outdir", out_dir, src_path],
            capture_output=True, timeout=120,
        )
        base = os.path.splitext(os.path.basename(src_path))[0]
        pdf_path = os.path.join(out_dir, base + ".pdf")
        if proc.returncode != 0 or not os.path.exists(pdf_path):
            stderr = (proc.stderr or b"").decode("utf-8", "ignore").strip()
            raise DocConversionError("La conversion Word -> PDF a échoué" + (f" : {stderr}" if stderr else "."))
        with open(pdf_path, "rb") as fh:
            return fh.read()
    except DocConversionError:
        raise
    except subprocess.TimeoutExpired:
        raise DocConversionError("La conversion Word -> PDF a expiré (délai dépassé).")
    except Exception as exc:
        raise DocConversionError(f"La conversion Word -> PDF a échoué : {exc}")
    finally:
        try:
            os.remove(src_path)
        except OSError:
            pass
        shutil.rmtree(out_dir, ignore_errors=True)
