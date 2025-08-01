#!/bin/bash

# Script de démarrage pour l'API locale avec vrai index FAISS

echo "🚀 DÉMARRAGE DE L'API LOCALE AVEC VRAI INDEX FAISS"
echo "=================================================="

# Vérifier si l'environnement virtuel existe
if [ ! -d "venv" ]; then
    echo "📦 Création de l'environnement virtuel..."
    python3 -m venv venv
fi

# Activer l'environnement virtuel
echo "🔧 Activation de l'environnement virtuel..."
source venv/bin/activate

# Installer les dépendances
echo "📥 Installation des dépendances..."
pip install -r requirements.txt

# Charger les variables d'environnement si .env existe
if [ -f ".env" ]; then
    echo "🔑 Chargement des variables d'environnement..."
    export $(cat .env | xargs)
else
    echo "⚠️  Fichier .env non trouvé"
    echo "📝 Exécutez ./setup_local_env.sh pour configurer les variables"
fi

# Vérifier si le port 8000 est libre
echo "🔍 Vérification du port 8000..."
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  Le port 8000 est déjà utilisé"
    echo "🔄 Arrêt des processus sur le port 8000..."
    pkill -f "uvicorn.*8000" || true
    sleep 2
fi

# Vérifier les variables d'environnement requises
echo "🔍 Vérification des variables d'environnement..."
required_vars=("OPENAI_API_KEY" "APPWRITE_ENDPOINT" "APPWRITE_PROJECT_ID" "APPWRITE_API_KEY" "APPWRITE_DATABASE_ID" "APPWRITE_COLLECTION_ID")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo "⚠️  Variables d'environnement manquantes: ${missing_vars[*]}"
    echo "📝 Exécutez ./setup_local_env.sh pour configurer les variables"
    echo ""
    echo "🔄 Démarrage en mode simulation..."
    export ENVIRONMENT=local
    python api.py
else
    echo "✅ Toutes les variables d'environnement sont configurées"
    echo ""
    echo "🚀 Démarrage de l'API locale avec vrai index FAISS..."
    echo "📍 URL: http://localhost:8000"
    echo "📚 Documentation: http://localhost:8000/docs"
    echo "🔍 Tests: python tests/local/test_local_api.py"
    echo ""
    echo "⏹️  Pour arrêter: Ctrl+C"
    echo ""
    
    # Démarrer l'API en mode local
    export ENVIRONMENT=local
    python api.py
fi 