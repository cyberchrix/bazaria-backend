#!/usr/bin/env python3
"""
Version optimisée de la recherche hybride
Utilise uniquement l'index FAISS pour de meilleures performances
"""

import os
import logging
import traceback
from typing import List, Dict, Any
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.query import Query
from criteria_utils import format_criteria_with_labels

logger = logging.getLogger(__name__)

# Configuration Appwrite
APPWRITE_ENDPOINT = os.environ.get("APPWRITE_ENDPOINT", "https://cloud.appwrite.io/v1")
APPWRITE_PROJECT = os.environ.get("APPWRITE_PROJECT_ID")
APPWRITE_API_KEY = os.environ.get("APPWRITE_API_KEY")
DATABASE_ID = os.environ.get("APPWRITE_DATABASE_ID")
COLLECTION_ID = os.environ.get("APPWRITE_COLLECTION_ID")

class OptimizedHybridSearchAPI:
    """API de recherche hybride optimisée (utilise uniquement FAISS)"""
    
    def __init__(self, openai_api_key: str):
        self.vectorstore = None
        self.db = None
        self.openai_api_key = openai_api_key
        self._load_components()
    
    def _load_components(self):
        """Charge l'index FAISS et la connexion Appwrite"""
        logger.info("🔧 Initialisation de l'API de recherche optimisée...")
        
        # Configuration OpenAI
        os.environ["OPENAI_API_KEY"] = self.openai_api_key
        logger.info("✅ Configuration OpenAI OK")
        
        # Charger l'index FAISS
        try:
            INDEX_DIR = "index_bazaria"
            logger.info(f"🔍 Vérification de l'index dans '{INDEX_DIR}'...")
            
            if not os.path.exists(INDEX_DIR):
                logger.error(f"❌ Index non trouvé dans '{INDEX_DIR}'")
                raise FileNotFoundError(f"Index non trouvé dans '{INDEX_DIR}'")
            
            logger.info("📦 Chargement de l'index FAISS...")
            embeddings = OpenAIEmbeddings()
            self.vectorstore = FAISS.load_local(INDEX_DIR, embeddings, allow_dangerous_deserialization=True)
            logger.info("✅ Index FAISS chargé avec succès")
        except Exception as e:
            logger.error(f"❌ Erreur lors du chargement de l'index: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return
        
        # Connexion Appwrite (seulement pour récupérer les détails)
        try:
            logger.info("🔌 Connexion à Appwrite...")
            client = Client()
            client.set_endpoint(APPWRITE_ENDPOINT)
            client.set_project(APPWRITE_PROJECT)
            client.set_key(APPWRITE_API_KEY)
            self.db = Databases(client)
            logger.info("✅ Connexion Appwrite établie")
        except Exception as e:
            logger.error(f"❌ Erreur lors de la connexion Appwrite: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.db = None
    
    def fast_search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Recherche rapide utilisant uniquement l'index FAISS"""
        logger.info(f"🚀 Recherche rapide pour: '{query}' (limit: {limit})")
        
        if not self.vectorstore:
            logger.error("❌ Index FAISS non disponible")
            return {"error": "Index FAISS non disponible"}
        
        try:
            # Recherche sémantique dans FAISS
            logger.info("🧠 Recherche sémantique dans FAISS...")
            results_with_scores = self.vectorstore.similarity_search_with_score(query, k=limit * 2)
            
            # Filtrer et formater les résultats
            filtered_results = []
            for doc, score in results_with_scores:
                if score >= 0.5:  # Seuil de confiance
                    announcement_details = self._get_announcement_details(doc.metadata.get('id'))
                    if announcement_details:
                        filtered_results.append({
                            'id': doc.metadata.get('id'),
                            'title': announcement_details.get('title'),
                            'description': announcement_details.get('description'),
                            'price': announcement_details.get('price'),
                            'location': announcement_details.get('location'),
                            'match_type': 'semantic',
                            'score': score
                        })
            
            # Trier par score et limiter
            filtered_results.sort(key=lambda x: x['score'], reverse=True)
            final_results = filtered_results[:limit]
            
            logger.info(f"✅ Recherche rapide terminée: {len(final_results)} résultats")
            
            return {
                "query": query,
                "total_results": len(final_results),
                "text_results": 0,
                "semantic_results": len(final_results),
                "results": final_results
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la recherche rapide: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"error": f"Erreur lors de la recherche: {str(e)}"}
    
    def _get_announcement_details(self, announcement_id: str) -> Dict[str, Any]:
        """Récupère les détails d'une annonce depuis Appwrite"""
        if not self.db:
            return None
        
        try:
            response = self.db.get_document(
                database_id=DATABASE_ID,
                collection_id=COLLECTION_ID,
                document_id=announcement_id
            )
            return response
        except Exception as e:
            logger.warning(f"⚠️ Impossible de récupérer les détails pour {announcement_id}: {e}")
            return None

# Fonction de test
def test_fast_search():
    """Test de la recherche rapide"""
    import os
    api = OptimizedHybridSearchAPI(os.environ.get("OPENAI_API_KEY"))
    
    if not api.vectorstore:
        print("❌ Impossible d'initialiser l'API")
        return
    
    # Test de recherche
    results = api.fast_search("villa", limit=3)
    print(f"Résultats: {results}")

if __name__ == "__main__":
    test_fast_search() 