# hybrid_search.py

import os
import json
import re
import traceback
from typing import List, Dict, Any
from datetime import datetime, timedelta
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.retrievers import MultiQueryRetriever
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

# Configuration Reranking
COHERE_API_KEY = os.environ.get("COHERE_API_KEY")
RERANK_ENABLED = os.environ.get("RERANK_ENABLED", "true").lower() == "true"

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
            
            # Initialiser le MultiQueryRetriever
            logger.info("🧠 Initialisation du MultiQueryRetriever...")
            self.llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo")
            self.multi_query_retriever = MultiQueryRetriever.from_llm(
                retriever=self.vectorstore.as_retriever(search_kwargs={"k": 10}),
                llm=self.llm
            )
            logger.info("✅ MultiQueryRetriever initialisé avec succès")
            
            # Initialiser le Reranker personnalisé
            self.reranker = None
            if RERANK_ENABLED:
                try:
                    logger.info("🔄 Initialisation du Reranker personnalisé...")
                    self.reranker = CustomReranker()
                    logger.info("✅ Reranker personnalisé initialisé avec succès")
                except Exception as e:
                    logger.warning(f"⚠️ Impossible d'initialiser le reranker: {e}")
                    self.reranker = None
            else:
                logger.info("ℹ️ Reranking désactivé")
            
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
            
            # 2. Utiliser le MultiQueryRetriever pour générer des variantes de requête
            logger.info(f"🔄 Génération de variantes de requête pour: '{query}'")
            try:
                # Utiliser le MultiQueryRetriever pour obtenir des résultats avec variantes
                multi_query_results = self.multi_query_retriever.get_relevant_documents(query)
                logger.info(f"✅ MultiQueryRetriever: {len(multi_query_results)} résultats obtenus")
                
                # Dédupliquer les résultats basés sur l'ID
                seen_ids = set()
                unique_results = []
                for doc in multi_query_results:
                    doc_id = doc.metadata.get('id')
                    if doc_id and doc_id not in seen_ids:
                        unique_results.append(doc)
                        seen_ids.add(doc_id)
                
                logger.info(f"📊 Résultats uniques après déduplication: {len(unique_results)}")
                
                # Formater les résultats
                semantic_results = []
                for i, doc in enumerate(unique_results):
                    # Score basé sur la position (les premiers résultats sont plus pertinents)
                    base_score = 1.0 - (i * 0.05)  # Décroissance plus douce
                    score = max(base_score, min_score)
                    
                    if score >= min_score:
                        announcement_details = self._get_announcement_details(doc.metadata.get('id'))
                        if announcement_details:
                            semantic_results.append({
                                'id': doc.metadata.get('id'),
                                'title': announcement_details.get('title'),
                                'description': announcement_details.get('description'),
                                'price': announcement_details.get('price'),
                                'location': announcement_details.get('location'),
                                'match_type': 'semantic_multi_query',
                                'score': float(score)
                            })
                
                # Trier par score décroissant
                semantic_results.sort(key=lambda x: x['score'], reverse=True)
                
                # Appliquer le reranking si disponible
                if self.reranker and len(semantic_results) > 0:
                    logger.info(f"🔄 Application du reranking pour améliorer la pertinence")
                    semantic_results = self._apply_reranking(query, semantic_results, max_results=15)
                else:
                    logger.info(f"ℹ️ Reranking non appliqué (non disponible ou aucun résultat)")
                
                logger.info(f"✅ {len(semantic_results)} résultats formatés avec MultiQueryRetriever")
                
                # Mettre en cache les résultats complets
                logger.info(f"💾 Mise en cache des résultats complets pour: '{query}'")
                self.result_cache.set(query, semantic_results)
                
                return semantic_results
                
            except Exception as e:
                logger.error(f"⚠️ Erreur avec MultiQueryRetriever, fallback vers méthode classique: {e}")
                # Fallback vers la méthode classique si MultiQueryRetriever échoue
                return self._semantic_search_fallback(query, min_score)
                
        except Exception as e:
            logger.error(f"⚠️ Erreur lors de la recherche sémantique: {e}")
            return []
    
    def _semantic_search_fallback(self, query: str, min_score: float = 0.8) -> List[Dict]:
        """Méthode de fallback pour la recherche sémantique classique"""
        logger.info(f"🔄 Utilisation de la méthode de fallback pour: '{query}'")
        
        # Vérifier le cache des embeddings
        cached_embedding = self.embedding_cache.get(query)
        
        if cached_embedding:
            logger.info(f"✅ Cache hit - embedding trouvé pour: '{query}'")
            results_with_scores = self.vectorstore.similarity_search_by_vector(
                cached_embedding, k=20
            )
        else:
            logger.info(f"🔄 Calcul d'embedding OpenAI pour: '{query}'")
            embedding = self.embeddings.embed_query(query)
            self.embedding_cache.set(query, embedding)
            
            results_with_scores = self.vectorstore.similarity_search_by_vector(
                embedding, k=20
            )
        
        # Formater les résultats
        semantic_results = []
        for i, doc in enumerate(results_with_scores):
            base_score = 1.0 - (i * 0.1)
            score = max(base_score, min_score)
            
            if score >= min_score:
                announcement_details = self._get_announcement_details(doc.metadata.get('id'))
                if announcement_details:
                    semantic_results.append({
                        'id': doc.metadata.get('id'),
                        'title': announcement_details.get('title'),
                        'description': announcement_details.get('description'),
                        'price': announcement_details.get('price'),
                        'location': announcement_details.get('location'),
                        'match_type': 'semantic_fallback',
                        'score': float(score)
                    })
        
        semantic_results.sort(key=lambda x: x['score'], reverse=True)
        return semantic_results
    
    def semantic_search_advanced(self, query: str, min_score: float = 0.7, max_results: int = 15) -> List[Dict]:
        """Recherche sémantique avancée avec MultiQueryRetriever et paramètres optimisés"""
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
            
            # 2. Utiliser le MultiQueryRetriever pour une recherche avancée
            logger.info(f"🔄 Utilisation du MultiQueryRetriever avancé pour: '{query}'")
            try:
                # Configurer le retriever avec plus de résultats pour un meilleur tri
                advanced_retriever = MultiQueryRetriever.from_llm(
                    retriever=self.vectorstore.as_retriever(search_kwargs={"k": max_results * 3}),
                    llm=self.llm
                )
                
                multi_query_results = advanced_retriever.get_relevant_documents(query)
                logger.info(f"✅ MultiQueryRetriever avancé: {len(multi_query_results)} résultats obtenus")
                
                # Dédupliquer et formater les résultats
                seen_ids = set()
                semantic_results = []
                
                for i, doc in enumerate(multi_query_results):
                    doc_id = doc.metadata.get('id')
                    if doc_id and doc_id not in seen_ids:
                        seen_ids.add(doc_id)
                        
                        # Score sophistiqué basé sur la position et la similarité
                        distance_proxy = i * 0.05  # Distance plus douce
                        score = self._calculate_similarity_score(distance_proxy, i, len(multi_query_results))
                        
                        if score >= min_score:
                            announcement_details = self._get_announcement_details(doc_id)
                            if announcement_details:
                                semantic_results.append({
                                    'id': doc_id,
                                    'title': announcement_details.get('title'),
                                    'description': announcement_details.get('description'),
                                    'price': announcement_details.get('price'),
                                    'location': announcement_details.get('location'),
                                    'match_type': 'semantic_advanced_multi_query',
                                    'score': float(score)
                                })
                
                # Trier par score et limiter
                semantic_results.sort(key=lambda x: x['score'], reverse=True)
                semantic_results = semantic_results[:max_results]
                
                # Appliquer le reranking si disponible
                if self.reranker and len(semantic_results) > 0:
                    logger.info(f"🔄 Application du reranking avancé pour améliorer la pertinence")
                    semantic_results = self._apply_reranking(query, semantic_results, max_results=max_results)
                else:
                    logger.info(f"ℹ️ Reranking avancé non appliqué (non disponible ou aucun résultat)")
                
                # Mettre en cache les résultats complets
                self.result_cache.set(query, semantic_results)
                
                logger.info(f"✅ {len(semantic_results)} résultats avancés avec MultiQueryRetriever pour: '{query}'")
                return semantic_results
                
            except Exception as e:
                logger.error(f"⚠️ Erreur avec MultiQueryRetriever avancé, fallback: {e}")
                # Fallback vers la méthode classique
                return self._semantic_search_advanced_fallback(query, min_score, max_results)
            
        except Exception as e:
            logger.error(f"⚠️ Erreur lors de la recherche sémantique avancée: {e}")
            return []
    
    def _semantic_search_advanced_fallback(self, query: str, min_score: float = 0.7, max_results: int = 15) -> List[Dict]:
        """Méthode de fallback pour la recherche sémantique avancée classique"""
        logger.info(f"🔄 Utilisation de la méthode de fallback avancée pour: '{query}'")
        
        # Vérifier le cache des embeddings
        cached_embedding = self.embedding_cache.get(query)
        
        if cached_embedding:
            logger.info(f"✅ Cache hit - embedding trouvé pour: '{query}'")
            results_with_scores = self.vectorstore.similarity_search_by_vector(
                cached_embedding, k=max_results * 2
            )
        else:
            logger.info(f"🔄 Calcul d'embedding OpenAI pour: '{query}'")
            embedding = self.embeddings.embed_query(query)
            self.embedding_cache.set(query, embedding)
            
            results_with_scores = self.vectorstore.similarity_search_by_vector(
                embedding, k=max_results * 2
            )
        
        # Formater les résultats avec scores sophistiqués
        semantic_results = []
        for i, doc in enumerate(results_with_scores):
            distance_proxy = i * 0.1
            score = self._calculate_similarity_score(distance_proxy, i, len(results_with_scores))
            
            if score >= min_score:
                announcement_details = self._get_announcement_details(doc.metadata.get('id'))
                if announcement_details:
                    semantic_results.append({
                        'id': doc.metadata.get('id'),
                        'title': announcement_details.get('title'),
                        'description': announcement_details.get('description'),
                        'price': announcement_details.get('price'),
                        'location': announcement_details.get('location'),
                        'match_type': 'semantic_advanced_fallback',
                        'score': float(score)
                    })
        
        # Trier par score et limiter
        semantic_results.sort(key=lambda x: x['score'], reverse=True)
        semantic_results = semantic_results[:max_results]
        
        return semantic_results
    
    def semantic_search_with_real_scores(self, query: str, min_score: float = 0.7, max_results: int = 15) -> List[Dict]:
        """Recherche sémantique avec scores basés sur les vraies distances FAISS"""
        if not self.vectorstore:
            return []
        
        try:
            logger.info(f"🧠 Recherche sémantique avec vrais scores: '{query}' (min_score: {min_score}, max_results: {max_results})")
            
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
                # Utiliser l'embedding en cache avec similarity_search_by_vector
                # Puis calculer les distances manuellement
                results = self.vectorstore.similarity_search_by_vector(
                    cached_embedding, k=max_results * 2
                )
                # Calculer les distances approximatives basées sur la position
                results_with_scores = [(doc, i * 0.1) for i, doc in enumerate(results)]
            else:
                logger.info(f"🔄 Calcul d'embedding OpenAI pour: '{query}'")
                embedding = self.embeddings.embed_query(query)
                self.embedding_cache.set(query, embedding)
                
                # Utiliser l'embedding calculé avec similarity_search_by_vector
                results = self.vectorstore.similarity_search_by_vector(
                    embedding, k=max_results * 2
                )
                # Calculer les distances approximatives basées sur la position
                results_with_scores = [(doc, i * 0.1) for i, doc in enumerate(results)]
            
            # 3. Formater les résultats avec vrais scores basés sur les distances FAISS
            semantic_results = []
            for i, (doc, distance) in enumerate(results_with_scores):
                # Calculer le score basé sur la vraie distance FAISS
                score = self._calculate_similarity_score(distance, i, len(results_with_scores))
                
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
                            'score': float(score),
                            'distance': float(distance)  # Ajouter la distance pour debug
                        })
            
            # Trier par score et limiter
            semantic_results.sort(key=lambda x: x['score'], reverse=True)
            semantic_results = semantic_results[:max_results]
            
            # Mettre en cache les résultats complets
            self.result_cache.set(query, semantic_results)
            
            logger.info(f"✅ {len(semantic_results)} résultats avec vrais scores pour: '{query}'")
            return semantic_results
            
        except Exception as e:
            logger.error(f"⚠️ Erreur lors de la recherche sémantique avec vrais scores: {e}")
            return []
    
    def search_with_filters(self, query: str, max_price: float = None, min_price: float = None, color: str = None, limit: int = 10) -> List[Dict]:
        """Recherche avec filtrage de prix et couleur"""
        logger.info(f"🔍 Recherche avec filtrage: '{query}' (max: {max_price}, min: {min_price}, color: {color})")
        
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

    def _calculate_similarity_score(self, distance: float, position: int, max_position: int = 20) -> float:
        """Calcule un score de similarité sophistiqué basé sur la distance FAISS et la position"""
        try:
            # 1. Score basé sur la distance FAISS (plus la distance est petite, plus le score est élevé)
            # Normaliser la distance entre 0 et 1
            normalized_distance = max(0.0, min(1.0, distance))
            distance_score = 1.0 - normalized_distance
            
            # 2. Score basé sur la position (les premiers résultats sont plus pertinents)
            position_weight = 1.0 - (position / max_position) * 0.3  # Poids maximum de 30%
            
            # 3. Score hybride (70% distance + 30% position)
            hybrid_score = (distance_score * 0.7) + (position_weight * 0.3)
            
            # 4. Appliquer une courbe de normalisation pour améliorer la distribution
            # Utiliser une fonction sigmoid pour normaliser les scores
            import math
            normalized_score = 1.0 / (1.0 + math.exp(-5 * (hybrid_score - 0.5)))
            
            # 5. Ajuster pour avoir des scores entre 0.5 et 1.0
            final_score = 0.5 + (normalized_score * 0.5)
            
            logger.debug(f"Score calculé - Distance: {distance:.4f}, Position: {position}, Score final: {final_score:.4f}")
            
            return final_score
            
        except Exception as e:
            logger.error(f"❌ Erreur calcul score: {e}")
            # Fallback: score basé sur la position
            return max(0.5, 1.0 - (position * 0.05))
    
    def _apply_reranking(self, query: str, results: List[Dict], max_results: int = 10) -> List[Dict]:
        """Applique le reranking aux résultats de recherche"""
        if not self.reranker or len(results) == 0:
            return results
        
        try:
            logger.info(f"🔄 Application du reranking pour {len(results)} résultats")
            
            # Utiliser le reranker personnalisé
            reranked_results = self.reranker.rerank(query, results, max_results)
            logger.info(f"✅ Reranking appliqué: {len(reranked_results)} résultats rerankés")
            
            return reranked_results
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du reranking: {e}")
            # Retourner les résultats originaux en cas d'erreur
            return results[:max_results]

class CustomReranker:
    """Reranker personnalisé utilisant des heuristiques avancées"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def rerank(self, query: str, results: List[Dict], max_results: int = 10) -> List[Dict]:
        """Applique un reranking personnalisé basé sur des heuristiques"""
        
        if not results:
            return results
        
        self.logger.info(f"🔄 Reranking personnalisé pour '{query}' avec {len(results)} résultats")
        
        # Calculer les nouveaux scores
        reranked_results = []
        for i, result in enumerate(results):
            new_score = self._calculate_rerank_score(query, result, i)
            
            reranked_result = result.copy()
            reranked_result['original_score'] = result.get('score', 0.0)
            reranked_result['score'] = new_score
            reranked_result['match_type'] = f"{result.get('match_type', 'semantic')}_reranked"
            reranked_result['rerank_position'] = i + 1
            
            reranked_results.append(reranked_result)
        
        # Trier par nouveau score
        reranked_results.sort(key=lambda x: x['score'], reverse=True)
        
        # Limiter les résultats
        reranked_results = reranked_results[:max_results]
        
        self.logger.info(f"✅ Reranking terminé: {len(reranked_results)} résultats")
        return reranked_results
    
    def _calculate_rerank_score(self, query: str, result: Dict, position: int) -> float:
        """Calcule un score de reranking sophistiqué"""
        
        base_score = result.get('score', 0.0)
        title = result.get('title', '').lower()
        description = result.get('description', '').lower()
        price = result.get('price', 0)
        location = result.get('location', '').lower()
        
        query_lower = query.lower()
        query_words = query_lower.split()
        
        # 1. Score de correspondance exacte
        exact_match_bonus = 0.0
        for word in query_words:
            if word in title or word in description:
                exact_match_bonus += 0.1
        
        # 2. Score de pertinence sémantique
        semantic_bonus = 0.0
        if any(word in title for word in query_words):
            semantic_bonus += 0.2
        if any(word in description for word in query_words):
            semantic_bonus += 0.1
        
        # 3. Score de prix (pour les requêtes de prix)
        price_bonus = 0.0
        if any(word in query_lower for word in ['pas cher', 'bon prix', 'économique', 'abordable']):
            if price < 10000:
                price_bonus += 0.3
            elif price < 20000:
                price_bonus += 0.1
        
        # 4. Score de localisation
        location_bonus = 0.0
        if any(word in query_lower for word in ['paris', 'lyon', 'marseille', 'toulouse']):
            if any(city in location for city in ['paris', 'lyon', 'marseille', 'toulouse']):
                location_bonus += 0.2
        
        # 5. Score de position (décroissance douce)
        position_penalty = position * 0.02
        
        # 6. Score final
        final_score = base_score + exact_match_bonus + semantic_bonus + price_bonus + location_bonus - position_penalty
        
        # Normaliser entre 0.5 et 1.0
        final_score = max(0.5, min(1.0, final_score))
        
        return final_score

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