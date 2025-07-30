# api.py

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import uvicorn

# Import de notre système de recherche
from hybrid_search import HybridSearchAPI

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
    global search_api
    print("🚀 Démarrage de l'API Bazaria Search...")
    search_api = HybridSearchAPI(os.environ["OPENAI_API_KEY"])
    print("✅ API initialisée avec succès")

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
    try:
        api = get_search_api()
        if api.vectorstore and api.db:
            return HealthResponse(
                status="healthy",
                message="API opérationnelle - Index FAISS et Appwrite connectés"
            )
        else:
            return HealthResponse(
                status="warning",
                message="API partiellement opérationnelle - Vérifiez les connexions"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de santé: {str(e)}")

@app.post("/search", response_model=SearchResponse)
async def search_announcements(request: SearchRequest, api: HybridSearchAPI = Depends(get_search_api)):
    """
    Recherche d'annonces avec système hybride
    
    - **query**: Terme de recherche (ex: "villa", "Samsung", "Vélo électrique")
    - **limit**: Nombre maximum de résultats (défaut: 10)
    """
    try:
        if not request.query.strip():
            raise HTTPException(status_code=400, detail="La requête ne peut pas être vide")
        
        # Effectuer la recherche
        results = api.hybrid_search(request.query, limit=request.limit)
        
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

if __name__ == "__main__":
    # Configuration pour le développement
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 