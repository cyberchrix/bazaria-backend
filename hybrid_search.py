# hybrid_search.py

import os
import json
import re
from typing import List, Dict, Any
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.query import Query
from criteria_utils import format_criteria_with_labels

# Configuration
# OPENAI_API_KEY doit être définie comme variable d'environnement

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
        print("🔧 Initialisation de l'API de recherche hybride...")
        
        # Configuration OpenAI
        os.environ["OPENAI_API_KEY"] = self.openai_api_key
        
        # Charger l'index FAISS
        try:
            INDEX_DIR = "index_bazaria"
            if not os.path.exists(INDEX_DIR):
                raise FileNotFoundError(f"Index non trouvé dans '{INDEX_DIR}'")
            
            embeddings = OpenAIEmbeddings()
            self.vectorstore = FAISS.load_local(INDEX_DIR, embeddings, allow_dangerous_deserialization=True)
            print("✅ Index FAISS chargé")
        except Exception as e:
            print(f"❌ Erreur lors du chargement de l'index: {e}")
            return
        
        # Connexion Appwrite
        try:
            client = Client()
            client.set_endpoint(APPWRITE_ENDPOINT)
            client.set_project(APPWRITE_PROJECT)
            client.set_key(APPWRITE_API_KEY)
            self.db = Databases(client)
            print("✅ Connexion Appwrite établie")
        except Exception as e:
            print(f"❌ Erreur lors de la connexion Appwrite: {e}")
    
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
        
        # Récupérer toutes les annonces pour la recherche textuelle
        try:
            # Récupérer toutes les annonces avec pagination
            all_announcements = []
            offset = 0
            limit = 25
            
            while True:
                response = self.db.list_documents(
                    database_id=DATABASE_ID, 
                    collection_id=COLLECTION_ID, 
                    queries=[
                        Query.limit(limit),
                        Query.offset(offset)
                    ]
                )
                announcements = response['documents']
                
                if len(announcements) == 0:
                    break
                
                all_announcements.extend(announcements)
                offset += limit
                
                # Si on a moins d'annonces que la limite, c'est la dernière page
                if len(announcements) < limit:
                    break
                
        except Exception as e:
            print(f"❌ Erreur lors de la récupération des annonces: {e}")
            return {"error": "Impossible de récupérer les annonces"}
        
        # Recherche textuelle
        text_results = self.text_search(query, all_announcements)
        
        # Recherche sémantique avec seuil strict
        semantic_results = self.semantic_search(query, min_score=0.7)
        
        # Combiner et dédupliquer les résultats
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