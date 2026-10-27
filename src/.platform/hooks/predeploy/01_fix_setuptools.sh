#!/bin/bash
source /var/app/venv/*/bin/activate

pip uninstall setuptools -y
pip install --no-cache-dir --force-reinstall setuptools==65.5.0
pip install --no-cache-dir --force-reinstall wheel