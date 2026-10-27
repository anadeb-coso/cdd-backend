#!/bin/bash
# LibreOffice (conversion Word -> PDF : profil de village, bouton « Convertir en PDF ») sur l'instance EB.
# - Ne fait rien s'il est déjà installé (seule une NOUVELLE instance le télécharge, ~245 Mo).
# - Borné dans le temps et sans jamais faire échouer le déploiement : en cas d'échec, seul le PDF est
#   indisponible (message clair à l'utilisateur), le site fonctionne.
LO_VERSION="25.8.7"
LOG=/var/log/install_libreoffice.log
if ls /opt/libreoffice*/program/soffice >/dev/null 2>&1; then
  echo "$(date) LibreOffice déjà présent" >> "$LOG"
  exit 0
fi
(
  set -e
  WORK=$(mktemp -d)
  cd "$WORK"
  URL="https://download.documentfoundation.org/libreoffice/stable/${LO_VERSION}/rpm/x86_64/LibreOffice_${LO_VERSION}_Linux_x86-64_rpm.tar.gz"
  timeout 300 curl -fsSL -o lo.tar.gz "$URL"
  tar xzf lo.tar.gz
  # bibliothèques nécessaires au mode headless + polices de substitution (Calibri -> Carlito)
  timeout 240 dnf install -y --setopt=install_weak_deps=False cairo cups-libs libSM libXinerama libXrender nss dbus-libs fontconfig || true
  timeout 120 dnf install -y google-carlito-fonts liberation-sans-fonts liberation-serif-fonts dejavu-sans-fonts || true
  timeout 300 dnf install -y --setopt=install_weak_deps=False ./LibreOffice_*_rpm/RPMS/*.rpm
  cd / && rm -rf "$WORK"
) >> "$LOG" 2>&1
if ls /opt/libreoffice*/program/soffice >/dev/null 2>&1; then
  echo "$(date) LibreOffice installé" >> "$LOG"
else
  echo "$(date) ÉCHEC de l'installation de LibreOffice (le PDF sera indisponible)" >> "$LOG"
fi
exit 0
