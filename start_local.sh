#!/bin/bash

# Script simple pour démarrer l'API en mode local

echo "🚀 DÉMARRAGE DE L'API EN MODE LOCAL"
echo "===================================="

# Activer l'environnement virtuel
echo "🔧 Activation de l'environnement virtuel..."
source venv/bin/activate

# Installer les dépendances si nécessaire
echo "📥 Vérification des dépendances..."
pip install -r requirements.txt

# Charger les variables d'environnement si .env existe
if [ -f ".env" ]; then
    echo "🔑 Chargement des variables d'environnement..."
    export $(cat .env | xargs)
fi

# Vérifier si le port 8000 est libre
echo "🔍 Vérification du port 8000..."
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  Le port 8000 est déjà utilisé"
    echo "🔄 Arrêt des processus sur le port 8000..."
    pkill -f "uvicorn.*8000" || true
    sleep 2
fi

echo "🚀 Démarrage de l'API en mode LOCAL..."
echo "📍 URL: http://localhost:8000"
echo "📚 Documentation: http://localhost:8000/docs"
echo "⏹️  Pour arrêter: Ctrl+C"
echo ""

# Démarrer l'API en mode local
export ENVIRONMENT=local
python api.py 