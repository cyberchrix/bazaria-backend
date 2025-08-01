#!/usr/bin/env python3
"""
API locale avec vrai index FAISS pour les tests
"""

import os
import logging
import traceback
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Création de l'application FastAPI
app = FastAPI(
    title="Bazaria Search API - Local",
    description="API de recherche locale avec vrai index FAISS",
    version="1.0.0"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variables globales
search_api = None

# Modèles Pydantic
class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 10

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

class IndexContentResponse(BaseModel):
    total_documents: int
    documents: List[dict]

def get_search_api():
    """Retourne l'instance de recherche"""
    global search_api
    
    if search_api is None:
        try:
            from hybrid_search import HybridSearchAPI
            openai_api_key = os.environ.get("OPENAI_API_KEY")
            if not openai_api_key:
                logger.error("❌ OPENAI_API_KEY non définie")
                return None
            search_api = HybridSearchAPI(openai_api_key)
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation de l'API de recherche: {str(e)}")
            return None
    
    return search_api

@app.on_event("startup")
async def startup_event():
    """Événement de démarrage de l'application"""
    logger.info("🚀 API locale avec vrai index FAISS démarrée")
    
    # Vérifier les variables d'environnement
    required_vars = ["OPENAI_API_KEY", "APPWRITE_ENDPOINT", "APPWRITE_PROJECT_ID", 
                    "APPWRITE_API_KEY", "APPWRITE_DATABASE_ID", "APPWRITE_COLLECTION_ID"]
    
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        logger.warning(f"⚠️ Variables manquantes: {missing_vars}")
        return
    
    logger.info("✅ Toutes les variables d'environnement sont configurées")
    
    # Vérifier l'index FAISS
    logger.info("🔍 Vérification de l'index FAISS...")
    if os.path.exists("index_bazaria"):
        logger.info("✅ Index FAISS trouvé")
        logger.info("✅ Index FAISS prêt")
    else:
        logger.warning("⚠️ Index FAISS non trouvé, génération...")
        try:
            from generate_index_paginated import generate_index
            generate_index()
            logger.info("✅ Index FAISS généré avec succès")
        except Exception as e:
            logger.error(f"❌ Erreur lors de la vérification de l'index: {str(e)}")
            logger.warning("⚠️ Index FAISS non disponible, mode simulation activé")
    
    logger.info("✅ Prêt pour les tests")

@app.get("/", response_model=HealthResponse)
async def root():
    """Point d'entrée principal"""
    return HealthResponse(
        status="ok",
        message="Bazaria Search API - Local avec vrai index FAISS"
    )

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Vérification de l'état de l'API"""
    logger.info("🔍 Health check demandé")
    try:
        api = get_search_api()
        
        if api and api.vectorstore and api.db:
            logger.info("✅ API entièrement opérationnelle")
            return HealthResponse(
                status="healthy",
                message="API locale opérationnelle - Index FAISS et Appwrite connectés"
            )
        else:
            logger.warning("⚠️ API partiellement opérationnelle")
            return HealthResponse(
                status="warning",
                message="API locale partiellement opérationnelle - Vérifiez les connexions"
            )
    except Exception as e:
        logger.error(f"❌ Erreur lors du health check: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur de santé: {str(e)}")

@app.post("/search", response_model=SearchResponse)
async def search_announcements(request: SearchRequest, api: Optional[object] = Depends(get_search_api)):
    """
    Recherche d'annonces avec système hybride (complet mais plus lent)
    
    - **query**: Terme de recherche (ex: "villa", "Samsung", "Vélo électrique")
    - **limit**: Nombre maximum de résultats (défaut: 10)
    """
    logger.info(f"🔍 Recherche demandée: '{request.query}' (limit: {request.limit})")
    
    try:
        if not request.query.strip():
            logger.warning("❌ Requête vide rejetée")
            raise HTTPException(status_code=400, detail="La requête ne peut pas être vide")
        
        if api:
            # Utiliser la vraie API de recherche
            results = api.hybrid_search(request.query, request.limit)
            logger.info(f"✅ Recherche terminée: {len(results.get('results', []))} résultats trouvés")
            return results
        else:
            # Mode simulation si l'API n'est pas disponible
            logger.warning("⚠️ Mode simulation activé")
            return SearchResponse(
                query=request.query,
                total_results=0,
                text_results=0,
                semantic_results=0,
                results=[]
            )
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la recherche: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la recherche: {str(e)}")

@app.post("/search/fast", response_model=SearchResponse)
async def search_announcements_fast(request: SearchRequest, api: Optional[object] = Depends(get_search_api)):
    """
    Recherche rapide d'annonces (utilise uniquement l'index FAISS)
    
    - **query**: Terme de recherche (ex: "villa", "Samsung", "Vélo électrique")
    - **limit**: Nombre maximum de résultats (défaut: 10)
    """
    logger.info(f"🚀 Recherche rapide demandée: '{request.query}' (limit: {request.limit})")
    
    try:
        if not request.query.strip():
            logger.warning("❌ Requête vide rejetée")
            raise HTTPException(status_code=400, detail="La requête ne peut pas être vide")
        
        # Effectuer la recherche rapide
        logger.info("🚀 Exécution de la recherche rapide...")
        
        # Utiliser directement l'index FAISS pour la recherche
        if not api or not api.vectorstore:
            raise HTTPException(status_code=500, detail="Index FAISS non disponible")
        
        # Recherche sémantique dans FAISS
        results_with_scores = api.vectorstore.similarity_search_with_score(request.query, k=request.limit * 2)
        
        # Filtrer et formater les résultats
        filtered_results = []
        for doc, score in results_with_scores:
            if score >= 0.05:  # Seuil extrêmement bas pour diagnostiquer
                # Utiliser les métadonnées directement de l'index FAISS
                metadata = doc.metadata
                if metadata and metadata.get('id'):
                    # Essayer de récupérer les détails depuis Appwrite
                    announcement_details = api._get_announcement_details(metadata.get('id'))
                    if announcement_details:
                        filtered_results.append({
                            'id': metadata.get('id'),
                            'title': announcement_details.get('title'),
                            'description': announcement_details.get('description'),
                            'price': announcement_details.get('price'),
                            'location': announcement_details.get('location'),
                            'match_type': 'semantic',
                            'score': score
                        })
                    else:
                        # Fallback : utiliser les métadonnées de l'index
                        logger.warning(f"⚠️ Impossible de récupérer les détails pour {metadata.get('id')}, utilisation des métadonnées de l'index")
                        filtered_results.append({
                            'id': metadata.get('id'),
                            'title': metadata.get('title', 'Titre non disponible'),
                            'description': metadata.get('description', 'Description non disponible'),
                            'price': metadata.get('price', 0.0),
                            'location': metadata.get('location', 'Localisation non disponible'),
                            'match_type': 'semantic',
                            'score': score
                        })
        
        # Trier par score et limiter
        filtered_results.sort(key=lambda x: x['score'], reverse=True)
        final_results = filtered_results[:request.limit]
        
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
        
        logger.info(f"✅ Recherche rapide terminée: {len(search_results)} résultats trouvés")
        
        return SearchResponse(
            query=request.query,
            total_results=len(search_results),
            text_results=0,
            semantic_results=len(search_results),
            results=search_results
        )
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la recherche rapide: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la recherche rapide: {str(e)}")

@app.get("/stats")
async def get_stats(api: Optional[object] = Depends(get_search_api)):
    """Statistiques de l'API"""
    try:
        stats = {
            "api_type": "local_real",
            "index_available": False,
            "appwrite_connected": False,
            "openai_configured": bool(os.environ.get("OPENAI_API_KEY"))
        }
        
        if api:
            stats["index_available"] = bool(api.vectorstore)
            stats["appwrite_connected"] = bool(api.db)
        
        return stats
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération des stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des stats: {str(e)}")

@app.get("/admin/index-content", response_model=IndexContentResponse)
async def get_index_content(api: Optional[object] = Depends(get_search_api)):
    """Contenu de l'index FAISS local"""
    logger.info("📋 Demande de contenu de l'index FAISS local...")
    
    try:
        if api and api.vectorstore:
            # Récupérer le contenu de l'index
            documents = []
            try:
                # Essayer de récupérer les métadonnées de l'index
                if hasattr(api.vectorstore, 'docstore') and api.vectorstore.docstore:
                    for doc_id in api.vectorstore.docstore._dict:
                        doc = api.vectorstore.docstore._dict[doc_id]
                        documents.append({
                            "id": doc_id,
                            "content": doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content,
                            "metadata": doc.metadata
                        })
            except Exception as e:
                logger.warning(f"⚠️ Impossible de récupérer le contenu détaillé: {str(e)}")
            
            logger.info(f"✅ Contenu de l'index récupéré: {len(documents)} documents")
            return IndexContentResponse(
                total_documents=len(documents),
                documents=documents
            )
        else:
            logger.warning("⚠️ Index FAISS non disponible")
            return IndexContentResponse(
                total_documents=0,
                documents=[]
            )
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération du contenu: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération du contenu: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True) 