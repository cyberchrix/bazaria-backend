#!/usr/bin/env python3
"""
Script pour vérifier et mettre à jour l'index FAISS au démarrage
"""

import os
import json
import logging
from datetime import datetime, timedelta
from update_index import update_index, rebuild_index

logger = logging.getLogger(__name__)

def check_and_update_index():
    """Vérifie si l'index doit être mis à jour et le fait si nécessaire"""
    
    INDEX_DIR = "index_bazaria"
    INDEXED_IDS_FILE = "indexed_ids.json"
    
    logger.info(f"🔍 Vérification de l'index dans '{INDEX_DIR}'...")
    
    # Si l'index n'existe pas, le générer
    if not os.path.exists(INDEX_DIR):
        logger.warning("❌ Index FAISS non trouvé, génération complète...")
        try:
            rebuild_index()
            logger.info("✅ Index FAISS généré avec succès")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération: {e}")
            return False
    
    # Si l'index existe, vérifier s'il faut le mettre à jour
    logger.info("✅ Index FAISS trouvé, vérification des mises à jour...")
    
    try:
        # Vérifier si le fichier de suivi existe
        if os.path.exists(INDEXED_IDS_FILE):
            logger.info("📊 Vérification des nouvelles annonces...")
            update_result = update_index()
            
            if update_result.get("success"):
                logger.info(f"✅ Index mis à jour: {update_result.get('new_announcements', 0)} nouvelles annonces")
                return True
            else:
                logger.warning(f"⚠️ Mise à jour partielle: {update_result.get('message', 'Erreur inconnue')}")
                return True
        else:
            logger.info("🔄 Fichier de suivi non trouvé, reconstruction complète...")
            rebuild_index()
            logger.info("✅ Index FAISS reconstruit avec succès")
            return True
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la mise à jour: {e}")
        logger.error("🔄 Tentative de reconstruction complète...")
        try:
            rebuild_index()
            logger.info("✅ Index FAISS reconstruit avec succès")
            return True
        except Exception as e2:
            logger.error(f"❌ Erreur lors de la reconstruction: {e2}")
            return False

if __name__ == "__main__":
    check_and_update_index() 