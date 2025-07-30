#!/bin/bash

# Script de démarrage pour Render
echo "🚀 Démarrage de l'API Bazaria Search sur Render..."

# Vérification des variables d'environnement
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ ERREUR: OPENAI_API_KEY n'est pas définie"
    exit 1
fi

if [ -z "$APPWRITE_ENDPOINT" ]; then
    echo "❌ ERREUR: APPWRITE_ENDPOINT n'est pas définie"
    exit 1
fi

if [ -z "$APPWRITE_PROJECT_ID" ]; then
    echo "❌ ERREUR: APPWRITE_PROJECT_ID n'est pas définie"
    exit 1
fi

if [ -z "$APPWRITE_API_KEY" ]; then
    echo "❌ ERREUR: APPWRITE_API_KEY n'est pas définie"
    exit 1
fi

if [ -z "$APPWRITE_DATABASE_ID" ]; then
    echo "❌ ERREUR: APPWRITE_DATABASE_ID n'est pas définie"
    exit 1
fi

if [ -z "$APPWRITE_COLLECTION_ID" ]; then
    echo "❌ ERREUR: APPWRITE_COLLECTION_ID n'est pas définie"
    exit 1
fi

echo "✅ Toutes les variables d'environnement sont configurées"
echo "🌐 Démarrage de l'API sur le port $PORT"

# Démarrage de l'application
exec uvicorn api:app --host 0.0.0.0 --port $PORT 