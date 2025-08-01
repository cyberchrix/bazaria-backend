#!/bin/bash

echo "🔧 CONFIGURATION DES VARIABLES D'ENVIRONNEMENT LOCALES"
echo "====================================================="

# Vérifier si le fichier .env existe
if [ ! -f ".env" ]; then
    echo "📝 Création du fichier .env..."
    cp env.example .env
    echo "✅ Fichier .env créé à partir de env.example"
else
    echo "✅ Fichier .env existe déjà"
fi

echo ""
echo "🔑 CONFIGURATION REQUISE:"
echo "=========================="
echo ""
echo "1. Ouvrez le fichier .env dans votre éditeur:"
echo "   code .env"
echo "   # ou"
echo "   nano .env"
echo ""
echo "2. Remplacez les valeurs par vos vraies clés API:"
echo "   - OPENAI_API_KEY: Votre clé OpenAI"
echo "   - APPWRITE_*: Vos identifiants Appwrite"
echo ""
echo "3. Sauvegardez le fichier"
echo ""
echo "4. Redémarrez l'API locale:"
echo "   ./start_local_real.sh"
echo ""
echo "⚠️  IMPORTANT: Ne committez jamais le fichier .env dans Git !"
echo "✅ Le fichier .env est déjà dans .gitignore" 