#!/usr/bin/env python3
"""
Script pour générer l'index FAISS au démarrage si il n'existe pas
"""

import os
import logging
from generate_index_paginated import main as generate_index

logger = logging.getLogger(__name__)

def check_and_generate_index():
    """Vérifie si l'index existe et le génère si nécessaire"""
    
    INDEX_DIR = "index_bazaria"
    
    logger.info(f"🔍 Vérification de l'index dans '{INDEX_DIR}'...")
    
    if os.path.exists(INDEX_DIR):
        logger.info("✅ Index FAISS trouvé")
        return True
    
    logger.warning("❌ Index FAISS non trouvé, génération en cours...")
    
    try:
        # Vérifier les variables d'environnement nécessaires
        required_vars = [
            "OPENAI_API_KEY",
            "APPWRITE_ENDPOINT",
            "APPWRITE_PROJECT_ID", 
            "APPWRITE_API_KEY",
            "APPWRITE_DATABASE_ID",
            "APPWRITE_COLLECTION_ID"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.environ.get(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.error(f"❌ Variables manquantes pour générer l'index: {missing_vars}")
            return False
        
        logger.info("🚀 Génération de l'index FAISS...")
        generate_index()
        logger.info("✅ Index FAISS généré avec succès")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la génération de l'index: {e}")
        return False

if __name__ == "__main__":
    check_and_generate_index() 