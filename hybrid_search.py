# hybrid_search.py

import os
import json
import re
import traceback
from typing import List, Dict, Any
from datetime import datetime, timedelta
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

class EmbeddingCache:
    """Cache pour les embeddings OpenAI"""
    
    def __init__(self, cache_file="embedding_cache.json", duration_hours=24):
        # Utiliser le répertoire persistant sur Render
        if os.path.exists("/opt/render/project/src/data"):
            self.cache_file = os.path.join("/opt/render/project/src/data", cache_file)
        elif os.path.exists("/var/data"):
            self.cache_file = os.path.join("/var/data", cache_file)
        else:
            self.cache_file = cache_file
        self.duration_hours = duration_hours
        self.cache = self._load_cache()
    
    def _load_cache(self):
        """Charge le cache depuis le fichier"""
        logger.info(f"📂 Tentative de chargement du cache depuis: {self.cache_file}")
        
        if os.path.exists(self.cache_file):
            try:
                logger.info(f"✅ Fichier cache trouvé: {self.cache_file}")
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                logger.info(f"📖 Données lues: {len(cache_data)} entrées totales")
                
                # Nettoyer le cache expiré
                current_time = datetime.now()
                cleaned_cache = {}
                
                for query, data in cache_data.items():
                    cache_time = datetime.fromisoformat(data['timestamp'])
                    if current_time - cache_time < timedelta(hours=self.duration_hours):
                        cleaned_cache[query] = data
                
                logger.info(f"📦 Cache chargé: {len(cleaned_cache)} entrées valides")
                return cleaned_cache
                
            except Exception as e:
                logger.error(f"❌ Erreur chargement cache: {e}")
                logger.error(f"📂 Fichier problématique: {self.cache_file}")
                return {}
        else:
            logger.info(f"📂 Fichier cache non trouvé: {self.cache_file}")
        return {}
    
    def _save_cache(self):
        """Sauvegarde le cache dans le fichier"""
        try:
            logger.info(f"💾 Tentative de sauvegarde du cache vers: {self.cache_file}")
            
            # Vérifier si le répertoire existe
            import os
            cache_dir = os.path.dirname(self.cache_file)
            if cache_dir and not os.path.exists(cache_dir):
                logger.info(f"📁 Création du répertoire: {cache_dir}")
                os.makedirs(cache_dir, exist_ok=True)
            
            # Vérifier les permissions
            logger.info(f"🔐 Vérification des permissions pour: {self.cache_file}")
            
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
            
            # Vérifier que le fichier a été créé
            if os.path.exists(self.cache_file):
                file_size = os.path.getsize(self.cache_file)
                logger.info(f"✅ Cache sauvegardé: {len(self.cache)} entrées dans {self.cache_file} ({file_size} bytes)")
            else:
                logger.error(f"❌ Fichier non créé: {self.cache_file}")
                
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde cache: {e}")
            logger.error(f"📂 Fichier problématique: {self.cache_file}")
            logger.error(f"🔍 Détails de l'erreur: {str(e)}")
    
    def get(self, query):
        """Récupère un embedding du cache"""
        query_lower = query.lower().strip()
        logger.info(f"🔍 Recherche dans le cache embedding: '{query}' (normalisé: '{query_lower}')")
        
        if query_lower in self.cache:
            data = self.cache[query_lower]
            cache_time = datetime.fromisoformat(data['timestamp'])
            
            if datetime.now() - cache_time < timedelta(hours=self.duration_hours):
                logger.info(f"✅ Cache hit pour: '{query}' (valide)")
                return data['embedding']
            else:
                logger.info(f"⏰ Cache expiré pour: '{query}' (supprimé)")
                del self.cache[query_lower]
        else:
            logger.info(f"❌ Cache miss pour: '{query}' (non trouvé)")
        
        return None
    
    def set(self, query, embedding):
        """Stocke un embedding dans le cache"""
        query_lower = query.lower().strip()
        logger.info(f"💾 Stockage dans le cache embedding: '{query}' (normalisé: '{query_lower}')")
        
        self.cache[query_lower] = {
            'embedding': embedding,
            'timestamp': datetime.now().isoformat()
        }
        logger.info(f"✅ Embedding mis en cache pour: '{query}'")
        self._save_cache()
    
    def get_stats(self):
        """Retourne les statistiques du cache"""
        return {
            'total_entries': len(self.cache),
            'cache_file': self.cache_file,
            'duration_hours': self.duration_hours
        }

class ResultCache:
    """Cache pour les résultats de recherche complets avec TTL dynamique"""
    
    def __init__(self, cache_file="result_cache.json", duration_hours=2):  # Augmenté à 2h
        # Utiliser le répertoire persistant sur Render
        if os.path.exists("/opt/render/project/src/data"):
            self.cache_file = os.path.join("/opt/render/project/src/data", cache_file)
        elif os.path.exists("/var/data"):
            self.cache_file = os.path.join("/var/data", cache_file)
        else:
            self.cache_file = cache_file
        self.duration_hours = duration_hours
        self.cache = self._load_cache()
    
    def _load_cache(self):
        """Charge le cache depuis le fichier"""
        logger.info(f"📂 Tentative de chargement du cache résultats depuis: {self.cache_file}")
        
        if os.path.exists(self.cache_file):
            try:
                logger.info(f"✅ Fichier cache résultats trouvé: {self.cache_file}")
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                logger.info(f"📖 Données résultats lues: {len(cache_data)} entrées totales")
                
                # Nettoyer le cache expiré
                current_time = datetime.now()
                cleaned_cache = {}
                
                for query, data in cache_data.items():
                    cache_time = datetime.fromisoformat(data['timestamp'])
                    if current_time - cache_time < timedelta(hours=self.duration_hours):
                        cleaned_cache[query] = data
                
                logger.info(f"📦 Cache résultats chargé: {len(cleaned_cache)} entrées valides")
                return cleaned_cache
                
            except Exception as e:
                logger.error(f"❌ Erreur chargement cache résultats: {e}")
                logger.error(f"📂 Fichier problématique: {self.cache_file}")
                return {}
        else:
            logger.info(f"📂 Fichier cache résultats non trouvé: {self.cache_file}")
        return {}
    
    def _save_cache(self):
        """Sauvegarde le cache dans le fichier"""
        try:
            logger.info(f"💾 Tentative de sauvegarde du cache résultats vers: {self.cache_file}")
            
            # Vérifier si le répertoire existe
            import os
            cache_dir = os.path.dirname(self.cache_file)
            if cache_dir and not os.path.exists(cache_dir):
                logger.info(f"📁 Création du répertoire: {cache_dir}")
                os.makedirs(cache_dir, exist_ok=True)
            
            # Vérifier les permissions
            logger.info(f"🔐 Vérification des permissions pour: {self.cache_file}")
            
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
            
            # Vérifier que le fichier a été créé
            if os.path.exists(self.cache_file):
                file_size = os.path.getsize(self.cache_file)
                logger.info(f"✅ Cache résultats sauvegardé: {len(self.cache)} entrées dans {self.cache_file} ({file_size} bytes)")
            else:
                logger.error(f"❌ Fichier non créé: {self.cache_file}")
                
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde cache résultats: {e}")
            logger.error(f"📂 Fichier problématique: {self.cache_file}")
            logger.error(f"🔍 Détails de l'erreur: {str(e)}")
    
    def get(self, query):
        """Récupère un résultat du cache"""
        query_lower = query.lower().strip()
        logger.info(f"🔍 Recherche dans le cache résultats: '{query}' (normalisé: '{query_lower}')")
        
        if query_lower in self.cache:
            data = self.cache[query_lower]
            cache_time = datetime.fromisoformat(data['timestamp'])
            
            if datetime.now() - cache_time < timedelta(hours=self.duration_hours):
                logger.info(f"✅ Cache hit résultats pour: '{query}' (valide)")
                return data['results']
            else:
                logger.info(f"⏰ Cache résultats expiré pour: '{query}' (supprimé)")
                del self.cache[query_lower]
        else:
            logger.info(f"❌ Cache miss résultats pour: '{query}' (non trouvé)")
        
        return None
    
    def set(self, query, results):
        """Stocke un résultat dans le cache"""
        query_lower = query.lower().strip()
        logger.info(f"💾 Stockage dans le cache résultats: '{query}' (normalisé: '{query_lower}')")
        
        self.cache[query_lower] = {
            'results': results,
            'timestamp': datetime.now().isoformat()
        }
        logger.info(f"✅ Résultats mis en cache pour: '{query}' ({len(results)} résultats)")
        self._save_cache()
    
    def get_stats(self):
        """Retourne les statistiques du cache"""
        return {
            'total_entries': len(self.cache),
            'cache_file': self.cache_file,
            'duration_hours': self.duration_hours
        }

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
        self.embedding_cache = EmbeddingCache()  # Cache des embeddings
        self.result_cache = ResultCache()  # Cache des résultats
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
            self.embeddings = OpenAIEmbeddings(
                model="text-embedding-3-large",  # Modèle plus avancé
                dimensions=3072  # Plus de dimensions pour une meilleure représentation
            )
            self.vectorstore = FAISS.load_local(INDEX_DIR, self.embeddings, allow_dangerous_deserialization=True)
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
        """Recherche sémantique avec cache optimisé (embeddings + résultats)"""
        if not self.vectorstore:
            return []
        
        try:
            logger.info(f"🧠 Recherche sémantique: '{query}'")
            
            # 1. Vérifier le cache des résultats complets (le plus rapide)
            logger.info(f"🔍 Vérification du cache des résultats pour: '{query}'")
            cached_results = self.result_cache.get(query)
            if cached_results:
                logger.info(f"✅ Cache hit - résultats complets trouvés pour: '{query}'")
                return cached_results
            else:
                logger.info(f"❌ Cache miss - résultats complets non trouvés pour: '{query}'")
            
            # 2. Vérifier le cache des embeddings
            logger.info(f"🔍 Vérification du cache des embeddings pour: '{query}'")
            cached_embedding = self.embedding_cache.get(query)
            
            if cached_embedding:
                logger.info(f"✅ Cache hit - embedding trouvé pour: '{query}'")
                # Utiliser l'embedding en cache pour la recherche FAISS
                results_with_scores = self.vectorstore.similarity_search_by_vector(
                    cached_embedding, k=20  # Plus de résultats pour un meilleur tri
                )
                logger.info(f"🔍 Recherche FAISS avec embedding en cache: {len(results_with_scores)} résultats")
            else:
                logger.info(f"❌ Cache miss - embedding non trouvé pour: '{query}'")
                logger.info(f"🔄 Calcul d'embedding OpenAI pour: '{query}'")
                # Calculer l'embedding réel et le mettre en cache
                embedding = self.embeddings.embed_query(query)
                logger.info(f"✅ Embedding calculé et mis en cache pour: '{query}'")
                self.embedding_cache.set(query, embedding)
                
                # Recherche avec l'embedding calculé
                results_with_scores = self.vectorstore.similarity_search_by_vector(
                    embedding, k=20  # Plus de résultats pour un meilleur tri
                )
                logger.info(f"🔍 Recherche FAISS avec nouvel embedding: {len(results_with_scores)} résultats")
            
            # 3. Formater les résultats
            logger.info(f"📝 Formatage des résultats pour: '{query}'")
            semantic_results = []
            
            # Calculer les scores de similarité réels
            for i, doc in enumerate(results_with_scores):
                # Score basé sur la position dans les résultats (plus proche = meilleur score)
                # Les premiers résultats sont les plus pertinents
                base_score = 1.0 - (i * 0.1)  # Décroissance linéaire
                score = max(base_score, min_score)  # Minimum défini par min_score
                
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
            
            # Trier par score décroissant pour une meilleure pertinence
            semantic_results.sort(key=lambda x: x['score'], reverse=True)
            
            logger.info(f"✅ {len(semantic_results)} résultats formatés pour: '{query}'")
            
            # 4. Mettre en cache les résultats complets
            logger.info(f"💾 Mise en cache des résultats complets pour: '{query}'")
            self.result_cache.set(query, semantic_results)
            
            return semantic_results
        except Exception as e:
            logger.error(f"⚠️ Erreur lors de la recherche sémantique: {e}")
            return []
    
    def semantic_search_advanced(self, query: str, min_score: float = 0.7, max_results: int = 15) -> List[Dict]:
        """Recherche sémantique avancée avec paramètres optimisés"""
        if not self.vectorstore:
            return []
        
        try:
            logger.info(f"🧠 Recherche sémantique avancée: '{query}' (min_score: {min_score}, max_results: {max_results})")
            
            # 1. Vérifier le cache des résultats complets
            cached_results = self.result_cache.get(query)
            if cached_results:
                logger.info(f"✅ Cache hit - résultats complets trouvés pour: '{query}'")
                # Filtrer et limiter les résultats en cache
                filtered_results = [r for r in cached_results if r['score'] >= min_score][:max_results]
                return filtered_results
            
            # 2. Vérifier le cache des embeddings
            cached_embedding = self.embedding_cache.get(query)
            
            if cached_embedding:
                logger.info(f"✅ Cache hit - embedding trouvé pour: '{query}'")
                results_with_scores = self.vectorstore.similarity_search_by_vector(
                    cached_embedding, k=max_results * 2  # Plus de résultats pour un meilleur tri
                )
            else:
                logger.info(f"🔄 Calcul d'embedding OpenAI pour: '{query}'")
                embedding = self.embeddings.embed_query(query)
                self.embedding_cache.set(query, embedding)
                
                results_with_scores = self.vectorstore.similarity_search_by_vector(
                    embedding, k=max_results * 2
                )
            
            # 3. Formater les résultats avec scores améliorés
            semantic_results = []
            for i, doc in enumerate(results_with_scores):
                # Score basé sur la position et la similarité
                position_score = 1.0 - (i * 0.05)  # Décroissance plus douce
                score = max(position_score, min_score)
                
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
            
            # Trier par score et limiter
            semantic_results.sort(key=lambda x: x['score'], reverse=True)
            semantic_results = semantic_results[:max_results]
            
            # Mettre en cache les résultats complets
            self.result_cache.set(query, semantic_results)
            
            logger.info(f"✅ {len(semantic_results)} résultats avancés pour: '{query}'")
            return semantic_results
            
        except Exception as e:
            logger.error(f"⚠️ Erreur lors de la recherche sémantique avancée: {e}")
            return []
    
    def search_with_price_filter(self, query: str, max_price: float = None, min_price: float = None, limit: int = 10) -> List[Dict]:
        """Recherche avec filtrage de prix"""
        logger.info(f"🔍 Recherche avec filtrage de prix: '{query}' (max: {max_price}, min: {min_price})")
        
        # 1. Recherche sémantique pour comprendre l'intention
        semantic_results = self.semantic_search(query, min_score=0.6)
        logger.info(f"🧠 Résultats sémantiques: {len(semantic_results)}")
        
        # 2. Recherche textuelle pour les correspondances exactes
        try:
            all_announcements = []
            offset = 0
            page_limit = 25
            
            while True:
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
                    break
                
                all_announcements.extend(announcements)
                offset += page_limit
                
                if len(announcements) < page_limit:
                    break
                    
        except Exception as e:
            logger.error(f"❌ Erreur récupération annonces: {e}")
            return []
        
        # Recherche textuelle
        text_results = self.text_search(query, all_announcements)
        logger.info(f"📝 Résultats textuels: {len(text_results)}")
        
        # 3. Combiner et filtrer par prix
        combined_results = []
        seen_ids = set()
        
        # Ajouter résultats textuels
        for result in text_results:
            if result['id'] not in seen_ids:
                combined_results.append(result)
                seen_ids.add(result['id'])
        
        # Ajouter résultats sémantiques
        for result in semantic_results:
            if result['id'] not in seen_ids:
                combined_results.append(result)
                seen_ids.add(result['id'])
        
        # 4. Filtrer par prix
        filtered_results = []
        for result in combined_results:
            price = result.get('price', 0)
            
            # Vérifier les contraintes de prix
            if max_price is not None and price > max_price:
                continue
            if min_price is not None and price < min_price:
                continue
                
            filtered_results.append(result)
        
        # 5. Trier par score et limiter
        filtered_results.sort(key=lambda x: x['score'], reverse=True)
        filtered_results = filtered_results[:limit]
        
        logger.info(f"✅ Recherche avec filtrage: {len(filtered_results)} résultats (sur {len(combined_results)} total)")
        
        return filtered_results
    
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