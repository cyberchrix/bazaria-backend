# api.py

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

# Configuration du logging
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
    title="Bazaria Search API",
    description="API de recherche hybride pour les annonces Bazaria",
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
    logger.info("🚀 Démarrage de l'API Bazaria Search...")
    
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
        raise

@app.get("/", response_model=HealthResponse)
async def root():
    """Point d'entrée principal"""
    return HealthResponse(
        status="ok",
        message="Bazaria Search API - Utilisez /docs pour la documentation"
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
            return HealthResponse(
                status="healthy",
                message="API opérationnelle - Index FAISS et Appwrite connectés"
            )
        else:
            logger.warning("⚠️ API partiellement opérationnelle")
            return HealthResponse(
                status="warning",
                message="API partiellement opérationnelle - Vérifiez les connexions"
            )
    except Exception as e:
        logger.error(f"❌ Erreur lors du health check: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erreur de santé: {str(e)}")

@app.post("/search", response_model=SearchResponse)
async def search_announcements(request: SearchRequest, api: HybridSearchAPI = Depends(get_search_api)):
    """
    Recherche d'annonces avec système hybride (complet mais plus lent)
    
    - **query**: Terme de recherche (ex: "villa", "Samsung", "Vélo électrique")
    - **limit**: Nombre maximum de résultats (défaut: 10)
    """
    logger.info(f"🔍 Recherche hybride demandée: '{request.query}' (limit: {request.limit})")
    
    try:
        if not request.query.strip():
            logger.warning("❌ Requête vide rejetée")
            raise HTTPException(status_code=400, detail="La requête ne peut pas être vide")
        
        # Effectuer la recherche
        logger.info("🔍 Exécution de la recherche hybride...")
        results = api.hybrid_search(request.query, limit=request.limit)
        
        if "error" in results:
            logger.error(f"❌ Erreur lors de la recherche: {results['error']}")
            raise HTTPException(status_code=500, detail=results["error"])
        
        # Convertir les résultats en format Pydantic
        search_results = []
        for result in results["results"]:
            search_results.append(SearchResult(
                id=result["id"],
                title=result["title"],
                description=result["description"],
                price=result["price"],
                location=result["location"],
                match_type=result["match_type"],
                score=result["score"]
            ))
        
        logger.info(f"✅ Recherche hybride terminée: {results['total_results']} résultats trouvés")
        logger.info(f"   - Correspondances textuelles: {results['text_results']}")
        logger.info(f"   - Correspondances sémantiques: {results['semantic_results']}")
        
        return SearchResponse(
            query=results["query"],
            total_results=results["total_results"],
            text_results=results["text_results"],
            semantic_results=results["semantic_results"],
            results=search_results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur inattendue lors de la recherche: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la recherche: {str(e)}")

@app.post("/search/fast", response_model=SearchResponse)
async def search_announcements_fast(request: SearchRequest, api: HybridSearchAPI = Depends(get_search_api)):
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
        if not api.vectorstore:
            raise HTTPException(status_code=500, detail="Index FAISS non disponible")
        
        # Recherche sémantique dans FAISS
        results_with_scores = api.vectorstore.similarity_search_with_score(request.query, k=request.limit * 2)
        
        # Filtrer et formater les résultats
        filtered_results = []
        for doc, score in results_with_scores:
            if score >= 0.30:  # Seuil ajusté pour inclure les villas (score ~0.33)
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
        
        logger.info(f"✅ Recherche rapide terminée: {len(final_results)} résultats trouvés")
        
        return SearchResponse(
            query=request.query,
            total_results=len(final_results),
            text_results=0,
            semantic_results=len(final_results),
            results=search_results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur inattendue lors de la recherche rapide: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la recherche rapide: {str(e)}")

@app.get("/search/{query}", response_model=SearchResponse)
async def search_announcements_get(
    query: str, 
    limit: Optional[int] = 10,
    api: HybridSearchAPI = Depends(get_search_api)
):
    """
    Recherche d'annonces via GET (pour tests rapides)
    
    - **query**: Terme de recherche dans l'URL
    - **limit**: Nombre maximum de résultats (paramètre query)
    """
    try:
        if not query.strip():
            raise HTTPException(status_code=400, detail="La requête ne peut pas être vide")
        
        # Effectuer la recherche
        results = api.hybrid_search(query, limit=limit)
        
        if "error" in results:
            raise HTTPException(status_code=500, detail=results["error"])
        
        # Convertir les résultats en format Pydantic
        search_results = []
        for result in results["results"]:
            search_results.append(SearchResult(
                id=result["id"],
                title=result["title"],
                description=result["description"],
                price=result["price"],
                location=result["location"],
                match_type=result["match_type"],
                score=result["score"]
            ))
        
        return SearchResponse(
            query=results["query"],
            total_results=results["total_results"],
            text_results=results["text_results"],
            semantic_results=results["semantic_results"],
            results=search_results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la recherche: {str(e)}")

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

@app.post("/admin/rebuild-index")
async def rebuild_index_endpoint():
    """Force la reconstruction complète de l'index (admin only)"""
    try:
        logger.info("🔄 Reconstruction forcée de l'index demandée...")
        
        from update_index import rebuild_index
        rebuild_index()
        
        logger.info("✅ Index reconstruit avec succès")
        return {"message": "Index reconstruit avec succès", "status": "success"}
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la reconstruction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la reconstruction: {str(e)}")

@app.post("/admin/update-index")
async def update_index_endpoint():
    """Met à jour l'index avec les nouvelles annonces (admin only)"""
    try:
        logger.info("🔄 Mise à jour de l'index demandée...")
        
        from update_index import update_index
        result = update_index()
        
        if result.get("success"):
            logger.info(f"✅ Index mis à jour: {result.get('new_announcements', 0)} nouvelles annonces")
            return {
                "message": f"Index mis à jour avec {result.get('new_announcements', 0)} nouvelles annonces",
                "status": "success",
                "new_announcements": result.get('new_announcements', 0)
            }
        else:
            logger.warning(f"⚠️ Mise à jour partielle: {result.get('message', 'Erreur inconnue')}")
            return {
                "message": result.get('message', 'Erreur inconnue'),
                "status": "partial",
                "new_announcements": result.get('new_announcements', 0)
            }
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la mise à jour: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la mise à jour: {str(e)}")

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

@app.get("/admin/force-new-format")
async def force_new_format():
    """Force l'utilisation du nouveau format (admin only)"""
    try:
        logger.info("🔄 Forçage du nouveau format...")
        
        # Forcer la mise à jour avec le nouveau format
        from update_index import update_index
        result = update_index()
        
        if result.get("success"):
            logger.info(f"✅ Nouveau format appliqué: {result.get('new_announcements', 0)} annonces")
            return {
                "message": f"Nouveau format appliqué avec {result.get('new_announcements', 0)} annonces",
                "status": "success",
                "new_announcements": result.get('new_announcements', 0)
            }
        else:
            logger.warning(f"⚠️ Échec de l'application du nouveau format: {result.get('message', 'Erreur inconnue')}")
            return {
                "message": result.get('message', 'Erreur inconnue'),
                "status": "error",
                "new_announcements": 0
            }
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du forçage du nouveau format: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du forçage du nouveau format: {str(e)}")

if __name__ == "__main__":
    # Configuration pour le développement
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 