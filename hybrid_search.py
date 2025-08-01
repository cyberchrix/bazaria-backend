# hybrid_search.py

import os
import json
import re
import traceback
from typing import List, Dict, Any
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.query import Query
from criteria_utils import format_criteria_with_labels

import logging

# Configuration
# OPENAI_API_KEY doit être définie comme variable d'environnement

# Logger pour ce module
logger = logging.getLogger(__name__)

# Configuration Appwrite
APPWRITE_ENDPOINT = os.environ.get("APPWRITE_ENDPOINT", "https://cloud.appwrite.io/v1")
APPWRITE_PROJECT = os.environ.get("APPWRITE_PROJECT_ID")
APPWRITE_API_KEY = os.environ.get("APPWRITE_API_KEY")
DATABASE_ID = os.environ.get("APPWRITE_DATABASE_ID")
COLLECTION_ID = os.environ.get("APPWRITE_COLLECTION_ID")

class HybridSearchAPI:
    """API de recherche hybride (sémantique + textuelle)"""
    
    def __init__(self, openai_api_key: str):
        self.vectorstore = None
        self.db = None
        self.openai_api_key = openai_api_key
        self._load_components()
    
    def _load_components(self):
        """Charge l'index FAISS et la connexion Appwrite"""
        logger.info("🔧 Initialisation de l'API de recherche hybride...")
        
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
            # Utiliser un modèle d'embedding plus avancé pour une meilleure compréhension sémantique
            embeddings = OpenAIEmbeddings(
                model="text-embedding-3-large",  # Modèle plus avancé
                dimensions=3072  # Plus de dimensions pour une meilleure représentation
            )
            self.vectorstore = FAISS.load_local(INDEX_DIR, embeddings, allow_dangerous_deserialization=True)
            logger.info("✅ Index FAISS chargé avec succès")
        except Exception as e:
            logger.error(f"❌ Erreur lors du chargement de l'index: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return
        
        # Connexion Appwrite
        try:
            logger.info("🔌 Connexion à Appwrite...")
            logger.info(f"   Endpoint: {APPWRITE_ENDPOINT}")
            logger.info(f"   Project ID: {APPWRITE_PROJECT}")
            logger.info(f"   Database ID: {DATABASE_ID}")
            logger.info(f"   Collection ID: {COLLECTION_ID}")
            
            client = Client()
            client.set_endpoint(APPWRITE_ENDPOINT)
            client.set_project(APPWRITE_PROJECT)
            client.set_key(APPWRITE_API_KEY)
            self.db = Databases(client)
            
            # Test de connexion
            logger.info("🧪 Test de connexion Appwrite...")
            test_response = self.db.list_documents(
                database_id=DATABASE_ID,
                collection_id=COLLECTION_ID,
                queries=[Query.limit(1)]
            )
            logger.info(f"✅ Connexion Appwrite établie - {len(test_response['documents'])} document(s) de test récupéré(s)")
        except Exception as e:
            logger.error(f"❌ Erreur lors de la connexion Appwrite: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.db = None
    
    def text_search(self, query: str, announcements: List[Dict]) -> List[Dict]:
        """Recherche textuelle dans l'index FAISS (inclut les caractéristiques)"""
        if not self.vectorstore:
            return []
        
        query_lower = query.lower()
        results = []
        
        # Utiliser l'index FAISS pour la recherche textuelle
        try:
            # Récupérer plus de documents pour la recherche textuelle
            docs = self.vectorstore.similarity_search(query, k=20)
            
            for doc in docs:
                content_lower = doc.page_content.lower()
                
                # Vérifier si la requête apparaît dans le contenu complet (inclut caractéristiques)
                if query_lower in content_lower:
                    announcement_details = self._get_announcement_details(doc.metadata.get('id'))
                    if announcement_details:
                        results.append({
                            'id': doc.metadata.get('id'),
                            'title': announcement_details.get('title'),
                            'description': announcement_details.get('description'),
                            'price': announcement_details.get('price'),
                            'location': announcement_details.get('location'),
                            'match_type': 'text',
                            'score': 1.0  # Score parfait pour correspondance textuelle
                        })
        except Exception as e:
            print(f"⚠️ Erreur lors de la recherche textuelle: {e}")
        
        return results
    
    def semantic_search(self, query: str, min_score: float = 0.8) -> List[Dict]:
        """Recherche sémantique avec seuil strict"""
        if not self.vectorstore:
            return []
        
        try:
            results_with_scores = self.vectorstore.similarity_search_with_score(query, k=10)
            
            semantic_results = []
            for doc, score in results_with_scores:
                if score >= min_score:
                    announcement_details = self._get_announcement_details(doc.metadata.get('id'))
                    if announcement_details:
                        semantic_results.append({
                            'id': doc.metadata.get('id'),
                            'title': announcement_details.get('title'),
                            'description': announcement_details.get('description'),
                            'price': announcement_details.get('price'),
                            'location': announcement_details.get('location'),
                            'match_type': 'semantic',
                            'score': float(score)
                        })
            
            return semantic_results
        except Exception as e:
            print(f"⚠️ Erreur lors de la recherche sémantique: {e}")
            return []
    
    def _get_announcement_details(self, announcement_id: str) -> Dict[str, Any]:
        """Récupère les détails complets d'une annonce depuis Appwrite"""
        if not self.db or not announcement_id:
            return None
        
        try:
            response = self.db.get_document(
                database_id=DATABASE_ID,
                collection_id=COLLECTION_ID,
                document_id=announcement_id
            )
            return response
        except Exception as e:
            print(f"⚠️ Erreur lors de la récupération des détails pour {announcement_id}: {e}")
            return None
    
    def hybrid_search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Recherche hybride combinant textuelle et sémantique"""
        logger.info(f"🔍 Début de la recherche hybride pour: '{query}' (limit: {limit})")
        
        # Récupérer toutes les annonces pour la recherche textuelle
        try:
            logger.info("📥 Récupération des annonces depuis Appwrite...")
            # Récupérer toutes les annonces avec pagination
            all_announcements = []
            offset = 0
            page_limit = 25
            page_count = 0
            
            while True:
                page_count += 1
                logger.info(f"📄 Récupération page {page_count} (offset: {offset})")
                
                response = self.db.list_documents(
                    database_id=DATABASE_ID, 
                    collection_id=COLLECTION_ID, 
                    queries=[
                        Query.limit(page_limit),
                        Query.offset(offset)
                    ]
                )
                announcements = response['documents']
                
                if len(announcements) == 0:
                    logger.info("🏁 Fin de pagination (aucune annonce)")
                    break
                
                all_announcements.extend(announcements)
                offset += page_limit
                
                # Si on a moins d'annonces que la limite, c'est la dernière page
                if len(announcements) < page_limit:
                    logger.info("🏁 Dernière page atteinte")
                    break
                
            logger.info(f"📊 Total d'annonces récupérées: {len(all_announcements)}")
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération des annonces: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"error": "Impossible de récupérer les annonces"}
        
        # Recherche textuelle
        logger.info("🔍 Exécution de la recherche textuelle...")
        text_results = self.text_search(query, all_announcements)
        logger.info(f"📝 Résultats textuels trouvés: {len(text_results)}")
        
        # Recherche sémantique avec seuil strict
        logger.info("🧠 Exécution de la recherche sémantique...")
        semantic_results = self.semantic_search(query, min_score=0.7)
        logger.info(f"🧠 Résultats sémantiques trouvés: {len(semantic_results)}")
        
        # Combiner et dédupliquer les résultats
        logger.info("🔗 Combinaison des résultats...")
        combined_results = []
        seen_ids = set()
        
        # Priorité aux résultats textuels (correspondance exacte)
        for result in text_results:
            if result['id'] not in seen_ids:
                combined_results.append(result)
                seen_ids.add(result['id'])
        
        # Ajouter les résultats sémantiques
        for result in semantic_results:
            if result['id'] not in seen_ids:
                combined_results.append(result)
                seen_ids.add(result['id'])
        
        # Trier par score et limiter
        combined_results.sort(key=lambda x: x['score'], reverse=True)
        combined_results = combined_results[:limit]
        
        logger.info(f"✅ Recherche terminée: {len(combined_results)} résultats finaux")
        
        return {
            "query": query,
            "total_results": len(combined_results),
            "text_results": len(text_results),
            "semantic_results": len(semantic_results),
            "results": combined_results
        }

def interactive_search():
    """Recherche interactive"""
    
    print("🔍 Recherche hybride interactive")
    print("=" * 40)
    
    # Demander la clé API OpenAI
    print("🔑 Veuillez entrer votre clé API OpenAI:")
    print("   (ou appuyez sur Entrée pour utiliser la clé par défaut)")
    
    api_key = input("Clé API OpenAI: ").strip()
    if not api_key:
        print("❌ Veuillez fournir une clé API OpenAI valide")
        return
    
    # Initialiser l'API
    api = HybridSearchAPI(api_key)
    
    if not api.vectorstore:
        print("❌ Impossible d'initialiser l'API")
        return
    
    print("\n🎯 Recherche interactive")
    print("-" * 30)
    
    while True:
        query = input("\n🔎 Entrez votre requête de recherche (ou 'quit' pour quitter): ").strip()
        if query.lower() == 'quit':
            break
        
        if query:
            results = api.hybrid_search(query, limit=5)
            
            if "error" in results:
                print(f"  ❌ Erreur: {results['error']}")
            else:
                print(f"  📈 Résultats trouvés: {results['total_results']}")
                print(f"    - Correspondances textuelles: {results['text_results']}")
                print(f"    - Correspondances sémantiques: {results['semantic_results']}")
                
                if results['total_results'] == 0:
                    print("  ⚠️ Aucun résultat trouvé.")
                else:
                    for i, result in enumerate(results['results'], 1):
                        print(f"    Résultat {i}:")
                        print(f"      Titre: {result['title']}")
                        print(f"      Type: {result['match_type']}")
                        print(f"      Score: {result['score']:.4f}")
                        print(f"      Prix: {result['price']} €")
                        print(f"      Localisation: {result['location']}")
                        print()
    
    print("\n✅ Recherche terminée!")

if __name__ == "__main__":
    interactive_search() 