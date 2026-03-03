#!/bin/bash
# Script para preparar entorno en Render

# Actualizamos pip (opcional pero recomendable)
python -m pip install --upgrade pip

# Instalamos dependencias de Python
pip install -r requirements.txt

echo "Entorno listo ✅"