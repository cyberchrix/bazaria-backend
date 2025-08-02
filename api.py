# api.py - API unifiée pour local et production

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import uvicorn
import logging
import traceback
from datetime import datetime

# Import de notre système de recherche
from hybrid_search import HybridSearchAPI
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.query import Query

# Détection de l'environnement
IS_LOCAL = os.environ.get("ENVIRONMENT", "production") == "local"

# Configuration du logging
if IS_LOCAL:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
else:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('api.log')
        ]
    )
logger = logging.getLogger(__name__)

# Configuration
# OPENAI_API_KEY doit être définie comme variable d'environnement

# Modèles Pydantic
class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 10

class AdvancedSearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 15
    min_score: Optional[float] = 0.7

class FilteredSearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 10
    max_price: Optional[float] = None
    min_price: Optional[float] = None

class SearchResult(BaseModel):
    id: str
    title: str
    description: str
    price: float
    location: str
    match_type: str
    score: float

class SearchResponse(BaseModel):
    query: str
    total_results: int
    text_results: int
    semantic_results: int
    
    results: List[SearchResult]

class HealthResponse(BaseModel):
    status: str
    message: str

# Initialisation de l'API
app = FastAPI(
    title="Bazaria Search API" + (" - Local" if IS_LOCAL else ""),
    description="API de recherche hybride pour les annonces Bazaria" + (" (Mode local)" if IS_LOCAL else ""),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS pour Flutter
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production, spécifiez vos domaines
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variable globale pour l'API de recherche
search_api = None

def get_search_api():
    """Dependency pour obtenir l'API de recherche"""
    global search_api
    if search_api is None:
        search_api = HybridSearchAPI(os.environ["OPENAI_API_KEY"])
    return search_api

@app.on_event("startup")
async def startup_event():
    """Initialisation au démarrage"""
    import os
    
    global search_api
    env_type = "LOCAL" if IS_LOCAL else "PRODUCTION"
    logger.info(f"🚀 Démarrage de l'API Bazaria Search ({env_type})...")
    
    # Vérifier les variables d'environnement
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
            logger.error(f"❌ Variable d'environnement manquante: {var}")
    
    if missing_vars:
        logger.error(f"❌ Variables manquantes: {missing_vars}")
        if IS_LOCAL:
            logger.warning("⚠️ Mode local avec variables manquantes - certaines fonctionnalités peuvent être limitées")
    else:
        logger.info("✅ Toutes les variables d'environnement sont configurées")
    
    try:
        # Vérifier et générer l'index si nécessaire
        from generate_index_paginated import generate_index
        
        # Vérifier si l'index existe
        if not os.path.exists("index_bazaria"):
            logger.info("🔍 Index FAISS non trouvé, génération...")
            generate_index()
            logger.info("✅ Index FAISS généré avec succès")
        else:
            logger.info("✅ Index FAISS trouvé")
        
        index_ok = True
        
        search_api = HybridSearchAPI(os.environ["OPENAI_API_KEY"])
        logger.info("✅ API de recherche initialisée avec succès")
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'initialisation de l'API: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        if IS_LOCAL:
            logger.warning("⚠️ Mode local - l'API continuera avec des fonctionnalités limitées")
        else:
            raise

@app.get("/", response_model=HealthResponse)
async def root():
    """Point d'entrée principal"""
    env_type = "LOCAL" if IS_LOCAL else "PRODUCTION"
    return HealthResponse(
        status="ok",
        message=f"Bazaria Search API ({env_type}) - Utilisez /docs pour la documentation"
    )

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Vérification de l'état de l'API"""
    logger.info("🔍 Health check demandé")
    try:
        api = get_search_api()
        
        # Vérifications détaillées
        vectorstore_status = "✅" if api.vectorstore else "❌"
        db_status = "✅" if api.db else "❌"
        
        logger.info(f"Index FAISS: {vectorstore_status}")
        logger.info(f"Connexion Appwrite: {db_status}")
        
        if api.vectorstore and api.db:
            logger.info("✅ API entièrement opérationnelle")
            env_type = "LOCAL" if IS_LOCAL else "PRODUCTION"
            return HealthResponse(
                status="healthy",
                message=f"API {env_type} opérationnelle - Index FAISS et Appwrite connectés"
            )
        else:
            logger.warning("⚠️ API partiellement opérationnelle")
            env_type = "LOCAL" if IS_LOCAL else "PRODUCTION"
            return HealthResponse(
                status="warning",
                message=f"API {env_type} partiellement opérationnelle - Vérifiez les connexions"
            )
    except Exception as e:
        logger.error(f"❌ Erreur lors du health check: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erreur de santé: {str(e)}")

@app.post("/search/keyword", response_model=SearchResponse)
async def search_announcements_keyword(request: SearchRequest, api: HybridSearchAPI = Depends(get_search_api)):
    """
    Recherche par mots-clés exacts (pour termes précis)
    
    - **query**: Mot-clé précis (ex: "villa", "Samsung", "Vélo électrique")
    - **limit**: Nombre maximum de résultats (défaut: 10)
    """
    logger.info(f"🔍 Recherche par mots-clés demandée: '{request.query}' (limit: {request.limit})")
    
    try:
        if not request.query.strip():
            logger.warning("❌ Requête vide rejetée")
            raise HTTPException(status_code=400, detail="La requête ne peut pas être vide")
        
        # Récupérer toutes les annonces pour la recherche textuelle directe
        logger.info("📥 Récupération des annonces depuis Appwrite...")
        
        # Récupérer toutes les annonces avec pagination
        all_announcements = []
        offset = 0
        limit_per_page = 25
        
        while True:
            try:
                response = api.db.list_documents(
                    database_id=os.environ.get("APPWRITE_DATABASE_ID"),
                    collection_id=os.environ.get("APPWRITE_COLLECTION_ID"),
                    queries=[Query.offset(offset), Query.limit(limit_per_page)]
                )
                
                documents = response.get('documents', [])
                if not documents:
                    break
                
                all_announcements.extend(documents)
                offset += limit_per_page
                
                if len(documents) < limit_per_page:
                    break
                    
            except Exception as e:
                logger.error(f"❌ Erreur lors de la récupération des annonces: {e}")
                break
        
        logger.info(f"📊 Total d'annonces récupérées: {len(all_announcements)}")
        
        # Recherche textuelle directe (sans FAISS, sans OpenAI)
        logger.info("🔍 Exécution de la recherche textuelle directe...")
        query_lower = request.query.lower()
        text_results = []
        
        for announcement in all_announcements:
            # Chercher dans le titre et la description
            title = announcement.get('title', '').lower()
            description = announcement.get('description', '').lower()
            
            # Vérifier si la requête apparaît dans le titre ou la description
            if query_lower in title or query_lower in description:
                text_results.append({
                    'id': announcement.get('$id'),
                    'title': announcement.get('title'),
                    'description': announcement.get('description'),
                    'price': announcement.get('price', 0.0),
                    'location': announcement.get('location', ''),
                    'match_type': 'text',
                    'score': 1.0  # Score parfait pour correspondance textuelle
                })
        
        # Limiter les résultats
        final_results = text_results[:request.limit]
        
        # Convertir les résultats en format Pydantic
        search_results = []
        for result in final_results:
            search_results.append(SearchResult(
                id=result["id"],
                title=result["title"],
                description=result["description"],
                price=result["price"],
                location=result["location"],
                match_type=result["match_type"],
                score=result["score"]
            ))
        
        logger.info(f"✅ Recherche par mots-clés terminée: {len(final_results)} résultats trouvés")
        logger.info(f"   - Correspondances textuelles: {len(final_results)}")
        logger.info(f"   - Correspondances sémantiques: 0")
        
        return SearchResponse(
            query=request.query,
            total_results=len(final_results),
            text_results=len(final_results),
            semantic_results=0,
            results=search_results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur inattendue lors de la recherche par mots-clés: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la recherche par mots-clés: {str(e)}")

@app.post("/search/semantic", response_model=SearchResponse)
async def search_announcements_semantic(request: SearchRequest, api: HybridSearchAPI = Depends(get_search_api)):
    """
    Recherche sémantique pure (pour concepts, intentions, synonymes)
    
    - **query**: Concept ou intention (ex: "pour me déplacer", "moderne et élégant")
    - **limit**: Nombre maximum de résultats (défaut: 10)
    """
    logger.info(f"🧠 Recherche sémantique demandée: '{request.query}' (limit: {request.limit})")
    
    try:
        if not request.query.strip():
            logger.warning("❌ Requête vide rejetée")
            raise HTTPException(status_code=400, detail="La requête ne peut pas être vide")
        
        # Utiliser notre fonction semantic_search avec cache optimisé
        semantic_results = api.semantic_search(request.query, min_score=0.8)
        
        # Limiter le nombre de résultats
        filtered_results = semantic_results[:request.limit]
        
        # Convertir les résultats en format Pydantic
        search_results = []
        for result in filtered_results:
            search_results.append(SearchResult(
                id=result["id"],
                title=result["title"],
                description=result["description"],
                price=result["price"],
                location=result["location"],
                match_type=result["match_type"],
                score=result["score"]
            ))
        
        logger.info(f"✅ Recherche sémantique terminée: {len(filtered_results)} résultats trouvés")
        
        return SearchResponse(
            query=request.query,
            total_results=len(filtered_results),
            text_results=0,  # Pas de résultats textuels en recherche sémantique pure
            semantic_results=len(filtered_results),
            results=search_results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur inattendue lors de la recherche sémantique: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la recherche sémantique: {str(e)}")


@app.post("/search/semantic/advanced", response_model=SearchResponse)
async def search_announcements_semantic_advanced(request: AdvancedSearchRequest, api: HybridSearchAPI = Depends(get_search_api)):
    """
    Recherche sémantique avancée avec paramètres optimisés
    
    - **query**: Concept ou intention (ex: "pour me déplacer", "moderne et élégant")
    - **limit**: Nombre maximum de résultats (défaut: 15)
    - **min_score**: Score minimum de pertinence (défaut: 0.7)
    """
    logger.info(f"🧠 Recherche sémantique avancée demandée: '{request.query}' (limit: {request.limit}, min_score: {request.min_score})")
    
    try:
        if not request.query.strip():
            logger.warning("❌ Requête vide rejetée")
            raise HTTPException(status_code=400, detail="La requête ne peut pas être vide")
        
        # Utiliser notre fonction semantic_search_advanced avec cache optimisé
        semantic_results = api.semantic_search_advanced(
            request.query, 
            min_score=request.min_score, 
            max_results=request.limit
        )
        
        # Convertir les résultats en format Pydantic
        search_results = []
        for result in semantic_results:
            search_results.append(SearchResult(
                id=result["id"],
                title=result["title"],
                description=result["description"],
                price=result["price"],
                location=result["location"],
                match_type=result["match_type"],
                score=result["score"]
            ))
        
        logger.info(f"✅ Recherche sémantique avancée terminée: {len(semantic_results)} résultats trouvés")
        
        return SearchResponse(
            query=request.query,
            total_results=len(semantic_results),
            text_results=0,  # Pas de résultats textuels en recherche sémantique pure
            semantic_results=len(semantic_results),
            results=search_results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur inattendue lors de la recherche sémantique avancée: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la recherche sémantique avancée: {str(e)}")


@app.post("/search/filtered", response_model=SearchResponse)
async def search_announcements_filtered(request: FilteredSearchRequest, api: HybridSearchAPI = Depends(get_search_api)):
    """
    Recherche avec filtrage de prix (idéal pour "téléphone à moins de 100 euros")
    
    - **query**: Requête de recherche (ex: "téléphone", "vélo électrique")
    - **limit**: Nombre maximum de résultats (défaut: 10)
    - **max_price**: Prix maximum (ex: 100 pour "moins de 100 euros")
    - **min_price**: Prix minimum (ex: 50 pour "entre 50 et 100 euros")
    """
    logger.info(f"🔍 Recherche avec filtrage demandée: '{request.query}' (max_price: {request.max_price}, min_price: {request.min_price})")
    
    try:
        if not request.query.strip():
            logger.warning("❌ Requête vide rejetée")
            raise HTTPException(status_code=400, detail="La requête ne peut pas être vide")
        
        # Utiliser notre fonction de recherche avec filtrage
        filtered_results = api.search_with_price_filter(
            request.query,
            max_price=request.max_price,
            min_price=request.min_price,
            limit=request.limit
        )
        
        # Convertir les résultats en format Pydantic
        search_results = []
        for result in filtered_results:
            search_results.append(SearchResult(
                id=result["id"],
                title=result["title"],
                description=result["description"],
                price=result["price"],
                location=result["location"],
                match_type=result["match_type"],
                score=result["score"]
            ))
        
        logger.info(f"✅ Recherche avec filtrage terminée: {len(filtered_results)} résultats trouvés")
        
        return SearchResponse(
            query=request.query,
            total_results=len(filtered_results),
            text_results=len([r for r in filtered_results if r["match_type"] == "text"]),
            semantic_results=len([r for r in filtered_results if r["match_type"] == "semantic"]),
            results=search_results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur inattendue lors de la recherche avec filtrage: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la recherche avec filtrage: {str(e)}")


@app.post("/search/semantic/real-scores", response_model=SearchResponse)
async def search_announcements_semantic_real_scores(request: AdvancedSearchRequest, api: HybridSearchAPI = Depends(get_search_api)):
    """
    Recherche sémantique avec vrais scores basés sur les distances FAISS
    
    - **query**: Requête de recherche
    - **limit**: Nombre maximum de résultats (défaut: 15)
    - **min_score**: Score minimum basé sur la vraie similarité (défaut: 0.7)
    """
    logger.info(f"🧠 Recherche sémantique avec vrais scores demandée: '{request.query}' (limit: {request.limit}, min_score: {request.min_score})")
    
    try:
        if not request.query.strip():
            logger.warning("❌ Requête vide rejetée")
            raise HTTPException(status_code=400, detail="La requête ne peut pas être vide")
        
        # Utiliser notre fonction de recherche avec vrais scores
        semantic_results = api.semantic_search_with_real_scores(
            request.query, 
            min_score=request.min_score, 
            max_results=request.limit
        )
        
        # Convertir les résultats en format Pydantic
        search_results = []
        for result in semantic_results:
            search_results.append(SearchResult(
                id=result["id"],
                title=result["title"],
                description=result["description"],
                price=result["price"],
                location=result["location"],
                match_type=result["match_type"],
                score=result["score"]
            ))
        
        logger.info(f"✅ Recherche sémantique avec vrais scores terminée: {len(semantic_results)} résultats trouvés")
        
        return SearchResponse(
            query=request.query,
            total_results=len(semantic_results),
            text_results=0,  # Pas de résultats textuels en recherche sémantique pure
            semantic_results=len(semantic_results),
            results=search_results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur inattendue lors de la recherche sémantique avec vrais scores: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la recherche sémantique avec vrais scores: {str(e)}")


@app.post("/search/category", response_model=SearchResponse)
async def search_announcements_by_category(request: SearchRequest, api: HybridSearchAPI = Depends(get_search_api)):
    """
    Recherche par catégorie (Véhicules, Immobilier, Électronique, Mobilier, etc.)
    
    - **query**: Catégorie ou sous-catégorie (ex: "Véhicules", "Immobilier", "Électronique")
    - **limit**: Nombre maximum de résultats (défaut: 10)
    """
    logger.info(f"🏷️  Recherche par catégorie demandée: '{request.query}' (limit: {request.limit})")
    
    try:
        if not request.query.strip():
            logger.warning("❌ Requête vide rejetée")
            raise HTTPException(status_code=400, detail="La requête ne peut pas être vide")
        
        # Utiliser l'index FAISS pour la recherche par catégorie
        if not api.vectorstore:
            raise HTTPException(status_code=500, detail="Index FAISS non disponible")
        
        # Recherche sémantique dans FAISS avec focus sur la catégorie
        results_with_scores = api.vectorstore.similarity_search_with_score(request.query, k=request.limit * 3)
        
        # Filtrer par catégorie et formater les résultats
        filtered_results = []
        category_lower = request.query.lower()
        
        for doc, score in results_with_scores:
            # Vérifier si la catégorie correspond
            metadata = doc.metadata
            doc_category = metadata.get('category', '').lower()
            
            # Correspondance exacte ou partielle de catégorie
            if (category_lower in doc_category or 
                doc_category in category_lower or
                any(word in doc_category for word in category_lower.split())):
                
                if score >= 0.25:  # Seuil plus bas pour la recherche par catégorie
                    # Récupérer les détails depuis Appwrite
                    announcement_details = api._get_announcement_details(metadata.get('id'))
                    if announcement_details:
                        filtered_results.append({
                            'id': metadata.get('id'),
                            'title': announcement_details.get('title'),
                            'description': announcement_details.get('description'),
                            'price': announcement_details.get('price'),
                            'location': announcement_details.get('location'),
                            'category': metadata.get('category', 'Non classé'),
                            'match_type': 'category',
                            'score': score
                        })
        
        # Limiter le nombre de résultats
        filtered_results = filtered_results[:request.limit]
        
        # Convertir les résultats en format Pydantic
        search_results = []
        for result in filtered_results:
            search_results.append(SearchResult(
                id=result["id"],
                title=result["title"],
                description=result["description"],
                price=result["price"],
                location=result["location"],
                match_type=result["match_type"],
                score=result["score"]
            ))
        
        logger.info(f"✅ Recherche par catégorie terminée: {len(filtered_results)} résultats trouvés")
        logger.info(f"   - Catégorie recherchée: {request.query}")
        
        return SearchResponse(
            query=request.query,
            total_results=len(filtered_results),
            text_results=0,
            semantic_results=len(filtered_results),
            results=search_results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur inattendue lors de la recherche par catégorie: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la recherche par catégorie: {str(e)}")


@app.get("/categories")
async def get_categories(api: HybridSearchAPI = Depends(get_search_api)):
    """
    Liste toutes les catégories disponibles dans l'index
    """
    logger.info("📋 Demande de liste des catégories...")
    
    try:
        if not api.vectorstore:
            raise HTTPException(status_code=500, detail="Index FAISS non disponible")
        
        # Récupérer toutes les catégories depuis l'index
        categories_count = {}
        total_docs = len(api.vectorstore.index_to_docstore_id)
        
        # Parcourir tous les documents pour compter les catégories
        for doc_id in api.vectorstore.index_to_docstore_id.values():
            doc = api.vectorstore.docstore._dict.get(doc_id)
            if doc and doc.metadata:
                category = doc.metadata.get('category', 'Non classé')
                categories_count[category] = categories_count.get(category, 0) + 1
        
        # Trier par nombre d'annonces décroissant
        sorted_categories = sorted(categories_count.items(), key=lambda x: x[1], reverse=True)
        
        logger.info(f"✅ Catégories récupérées: {len(categories_count)} catégories trouvées")
        
        return {
            "total_announcements": total_docs,
            "categories": [
                {
                    "name": category,
                    "count": count,
                    "percentage": round((count / total_docs) * 100, 1)
                }
                for category, count in sorted_categories
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération des catégories: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des catégories: {str(e)}")


@app.get("/stats")
async def get_stats(api: HybridSearchAPI = Depends(get_search_api)):
    """Statistiques de l'API"""
    try:
        if api.vectorstore:
            total_docs = len(api.vectorstore.index_to_docstore_id)
            return {
                "total_announcements": total_docs,
                "index_status": "loaded",
                "search_api_status": "operational"
            }
        else:
            return {
                "total_announcements": 0,
                "index_status": "not_loaded",
                "search_api_status": "error"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des stats: {str(e)}")

# Endpoints supprimés car redondants avec /admin/force-new-format
# Utilisez /admin/force-new-format pour reconstruire l'index avec le nouveau format

@app.get("/admin/index-content")
async def get_index_content(api: HybridSearchAPI = Depends(get_search_api)):
    """Liste le contenu de l'index FAISS (admin only)"""
    try:
        logger.info("📋 Demande de contenu de l'index...")
        
        if not api.vectorstore:
            raise HTTPException(status_code=500, detail="Index FAISS non disponible")
        
        # Récupérer le contenu de l'index
        index_content = []
        
        # Parcourir tous les documents de l'index
        for doc_id, doc in api.vectorstore.index_to_docstore_id.items():
            try:
                # Récupérer le document
                document = api.vectorstore.docstore.search(doc)
                
                if document:
                    # Extraire les métadonnées
                    metadata = document.metadata
                    content = document.page_content[:200] + "..." if len(document.page_content) > 200 else document.page_content
                    
                    index_content.append({
                        "id": metadata.get('id', 'N/A'),
                        "title": metadata.get('title', 'Titre non disponible'),
                        "description": metadata.get('description', 'Description non disponible'),
                        "price": metadata.get('price', 0.0),
                        "location": metadata.get('location', 'Localisation non disponible'),
                        "content_preview": content,
                        "doc_id": doc_id
                    })
            except Exception as e:
                logger.warning(f"⚠️ Erreur lors de la récupération du document {doc_id}: {e}")
                continue
        
        # Trier par titre pour une meilleure lisibilité
        index_content.sort(key=lambda x: x['title'])
        
        logger.info(f"✅ Contenu de l'index récupéré: {len(index_content)} documents")
        
        return {
            "total_documents": len(index_content),
            "index_status": "loaded",
            "documents": index_content
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération du contenu: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération du contenu: {str(e)}")

@app.get("/admin/test-scores/{query}")
async def test_scores(query: str, api: HybridSearchAPI = Depends(get_search_api)):
    """Teste tous les scores pour une requête sans filtre (admin only)"""
    try:
        logger.info(f"🔍 Test des scores pour '{query}'...")
        
        if not api.vectorstore:
            raise HTTPException(status_code=500, detail="Index FAISS non disponible")
        
        # Recherche sémantique dans FAISS sans filtre
        results_with_scores = api.vectorstore.similarity_search_with_score(query, k=50)
        
        # Formater tous les résultats avec leurs scores
        all_results = []
        for doc, score in results_with_scores:
            try:
                metadata = doc.metadata
                all_results.append({
                    'id': metadata.get('id', 'N/A'),
                    'title': metadata.get('title', 'Titre non disponible'),
                    'description': metadata.get('description', 'Description non disponible'),
                    'price': metadata.get('price', 0.0),
                    'location': metadata.get('location', 'Localisation non disponible'),
                    'score': float(score) if score is not None else 0.0
                })
            except Exception as e:
                logger.warning(f"⚠️ Erreur lors du traitement du document: {e}")
                continue
        
        # Trier par score décroissant
        all_results.sort(key=lambda x: x['score'], reverse=True)
        
        logger.info(f"✅ Test des scores terminé: {len(all_results)} résultats")
        
        return {
            "query": query,
            "total_results": len(all_results),
            "results": all_results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur lors du test des scores: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du test des scores: {str(e)}")

@app.get("/admin/rebuild-index")
async def rebuild_index():
    """Force la reconstruction complète de l'index (admin only)"""
    try:
        logger.info("🔄 Reconstruction forcée de l'index demandée...")
        
        # Forcer la mise à jour avec le nouveau format
        from update_index import update_index
        result = update_index()
        
        if result.get("success"):
            logger.info(f"✅ Index reconstruit avec succès: {result.get('new_announcements', 0)} annonces")
            return {
                "message": f"Index reconstruit avec succès: {result.get('new_announcements', 0)} annonces",
                "status": "success",
                "new_announcements": result.get('new_announcements', 0)
            }
        else:
            logger.warning(f"⚠️ Échec de la reconstruction: {result.get('message', 'Erreur inconnue')}")
            return {
                "message": result.get('message', 'Erreur inconnue'),
                "status": "error",
                "new_announcements": 0
            }
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la reconstruction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la reconstruction: {str(e)}")

@app.post("/admin/reload-index")
async def reload_index():
    """Recharge l'index FAISS depuis le fichier (admin only)"""
    try:
        logger.info("🔄 Rechargement de l'index FAISS...")
        
        # Vider l'index en mémoire
        from hybrid_search import HybridSearchAPI
        import os
        
        # Vérifier si l'index existe
        INDEX_DIR = "index_bazaria"
        if not os.path.exists(INDEX_DIR):
            logger.error("❌ Index FAISS non trouvé")
            raise HTTPException(status_code=404, detail="Index FAISS non trouvé")
        
        # Forcer le rechargement de l'API
        logger.info("📦 Rechargement de l'index en mémoire...")
        
        # Créer une nouvelle instance de l'API pour recharger l'index
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            logger.error("❌ OPENAI_API_KEY non définie")
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY non définie")
        
        # Recharger l'index
        new_api = HybridSearchAPI(openai_api_key)
        
        # Vérifier que l'index est chargé
        if new_api.vectorstore is None:
            logger.error("❌ Échec du rechargement de l'index")
            raise HTTPException(status_code=500, detail="Échec du rechargement de l'index")
        
        # Remplacer l'instance globale et forcer le rechargement
        global search_api
        search_api = None  # Vider le cache
        search_api = new_api  # Assigner la nouvelle instance
        
        logger.info("✅ Index FAISS rechargé avec succès")
        return {
            "message": "Index FAISS rechargé avec succès",
            "status": "success",
            "index_loaded": True
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du rechargement de l'index: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du rechargement de l'index: {str(e)}")

@app.get("/admin/cache-stats")
async def get_cache_stats(api: HybridSearchAPI = Depends(get_search_api)):
    """Récupère les statistiques des caches (admin only)"""
    try:
        logger.info("📊 Récupération des statistiques des caches...")
        
        embedding_stats = api.embedding_cache.get_stats()
        result_stats = api.result_cache.get_stats()
        
        logger.info(f"✅ Statistiques des caches récupérées")
        
        return {
            "embedding_cache": {
                "total_entries": embedding_stats['total_entries'],
                "cache_file": embedding_stats['cache_file'],
                "duration_hours": embedding_stats['duration_hours']
            },
            "result_cache": {
                "total_entries": result_stats['total_entries'],
                "cache_file": result_stats['cache_file'],
                "duration_hours": result_stats['duration_hours']
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur récupération stats cache: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/admin/clear-cache")
async def clear_cache(api: HybridSearchAPI = Depends(get_search_api)):
    """Vide tous les caches (admin only)"""
    try:
        logger.info("🗑️ Vidage de tous les caches...")
        
        # Vider le cache des embeddings
        api.embedding_cache.cache = {}
        api.embedding_cache._save_cache()
        
        # Vider le cache des résultats
        api.result_cache.cache = {}
        api.result_cache._save_cache()
        
        logger.info("✅ Tous les caches vidés avec succès")
        return {"message": "Tous les caches vidés avec succès", "status": "success"}
        
    except Exception as e:
        logger.error(f"❌ Erreur vidage cache: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.get("/admin/cache-logs")
async def get_cache_logs(api: HybridSearchAPI = Depends(get_search_api)):
    """Retourne les vrais logs de cache depuis le système de logging (admin only)"""
    try:
        logger.info("📊 Récupération des vrais logs de cache...")
        
        # Récupérer les logs depuis le système de logging
        import logging
        import io
        
        # Capturer les logs
        log_capture = io.StringIO()
        log_handler = logging.StreamHandler(log_capture)
        log_handler.setLevel(logging.INFO)
        
        # Ajouter temporairement le handler
        root_logger = logging.getLogger()
        root_logger.addHandler(log_handler)
        
        # Effectuer une vraie recherche pour générer des logs
        test_query = "test logs cache réel"
        logger.info(f"🧪 Test de recherche pour générer des logs: '{test_query}'")
        
        # Faire une vraie recherche sémantique
        results = api.semantic_search(test_query)
        logger.info(f"✅ Recherche terminée: {len(results)} résultats")
        
        # Récupérer les logs capturés
        logs = log_capture.getvalue().split('\n')
        logs = [log.strip() for log in logs if log.strip() and 'cache' in log.lower()]
        
        # Nettoyer
        root_logger.removeHandler(log_handler)
        
        return {
            "status": "success",
            "message": "Vrais logs de cache récupérés",
            "logs": logs,
            "cache_stats": {
                "embedding_cache": api.embedding_cache.get_stats(),
                "result_cache": api.result_cache.get_stats()
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération des logs: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des logs: {e}")

@app.post("/admin/test-cache-logs")
async def test_cache_logs(api: HybridSearchAPI = Depends(get_search_api)):
    """Test de recherche avec logs de cache en temps réel (admin only)"""
    try:
        logger.info("🧪 Test de recherche avec logs de cache...")
        
        # Effectuer une vraie recherche sémantique
        test_query = "test cache logs temps réel"
        logger.info(f"🔍 Début de recherche: '{test_query}'")
        
        # Faire une vraie recherche sémantique
        results = api.semantic_search(test_query)
        logger.info(f"✅ Recherche terminée: {len(results)} résultats")
        
        # Deuxième recherche pour tester le cache
        logger.info(f"🔍 Deuxième recherche: '{test_query}' (avec cache)")
        results2 = api.semantic_search(test_query)
        logger.info(f"✅ Deuxième recherche terminée: {len(results2)} résultats")
        
        return {
            "status": "success",
            "message": "Test de cache avec logs terminé",
            "first_search_results": len(results),
            "second_search_results": len(results2),
            "cache_stats": {
                "embedding_cache": api.embedding_cache.get_stats(),
                "result_cache": api.result_cache.get_stats()
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Erreur lors du test de cache: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du test de cache: {e}")

if __name__ == "__main__":
    # Configuration pour le développement local
    print("🚀 Démarrage de l'API en mode LOCAL")
    print("📍 URL: http://localhost:8000")
    print("📚 Documentation: http://localhost:8000/docs")
    print("⏹️  Pour arrêter: Ctrl+C")
    print()
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 