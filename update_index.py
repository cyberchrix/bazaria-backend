# update_index.py

from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.query import Query
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
import os
import json
from criteria_utils import format_criteria_with_labels

# ==== Configuration ====
APPWRITE_ENDPOINT = os.environ.get("APPWRITE_ENDPOINT", "https://cloud.appwrite.io/v1")
APPWRITE_PROJECT = os.environ.get("APPWRITE_PROJECT_ID")
APPWRITE_API_KEY = os.environ.get("APPWRITE_API_KEY")
DATABASE_ID = os.environ.get("APPWRITE_DATABASE_ID")
COLLECTION_ID = os.environ.get("APPWRITE_COLLECTION_ID")

# Configuration OpenAI
# OPENAI_API_KEY doit être définie comme variable d'environnement

INDEX_DIR = "index_bazaria"
INDEXED_IDS_FILE = "indexed_ids.json"

def load_indexed_ids():
    """Charge la liste des IDs déjà indexés"""
    if os.path.exists(INDEXED_IDS_FILE):
        with open(INDEXED_IDS_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_indexed_ids(indexed_ids):
    """Sauvegarde la liste des IDs indexés"""
    with open(INDEXED_IDS_FILE, 'w') as f:
        json.dump(list(indexed_ids), f)

def format_annonce(a):
    """Formate une annonce pour l'index"""
    lignes = [
        f"Titre : {a.get('title', '')}",
        f"Localisation : {a.get('location', '')}",
        f"Prix : {a.get('price', '')} €",
        "Caractéristiques :"
    ]
    # Utiliser les libellés des critères
    formatted_criteria = format_criteria_with_labels(a.get('criterias', '[]'))
    for crit_line in formatted_criteria:
        lignes.append(f"- {crit_line}")
    lignes.append("")
    lignes.append("Description :")
    lignes.append(a.get('description', ''))
    return "\n".join(lignes)

def update_index():
    """Met à jour l'index avec les nouvelles annonces"""
    
    print("🔄 Mise à jour de l'index FAISS...")
    
    # Connexion Appwrite
    client = Client()
    client.set_endpoint(APPWRITE_ENDPOINT)
    client.set_project(APPWRITE_PROJECT)
    client.set_key(APPWRITE_API_KEY)
    db = Databases(client)
    
    # Charger les IDs déjà indexés
    indexed_ids = load_indexed_ids()
    print(f"📊 Annonces déjà indexées: {len(indexed_ids)}")
    
    # Récupérer toutes les annonces
    print("🔍 Récupération de toutes les annonces...")
    all_annonces = []
    offset = 0
    limit = 25
    
    while True:
        try:
            response = db.list_documents(
                database_id=DATABASE_ID, 
                collection_id=COLLECTION_ID, 
                queries=[
                    Query.limit(limit),
                    Query.offset(offset)
                ]
            )
            annonces = response['documents']
            
            if len(annonces) == 0:
                break
            
            all_annonces.extend(annonces)
            offset += limit
            
            if len(annonces) < limit:
                break
                
        except Exception as e:
            print(f"❌ Erreur lors de la récupération: {e}")
            return {"success": False, "new_announcements": 0, "message": f"Erreur lors de la récupération: {e}"}
    
    print(f"📊 Total d'annonces récupérées: {len(all_annonces)}")
    
    # Identifier les nouvelles annonces
    new_annonces = []
    for annonce in all_annonces:
        if annonce['$id'] not in indexed_ids:
            new_annonces.append(annonce)
    
    print(f"🆕 Nouvelles annonces à indexer: {len(new_annonces)}")
    
    if len(new_annonces) == 0:
        print("✅ Aucune nouvelle annonce à indexer")
        return {"success": True, "new_announcements": 0, "message": "Aucune nouvelle annonce à indexer"}
    
    # Charger l'index existant ou en créer un nouveau
    embeddings = OpenAIEmbeddings()
    
    if os.path.exists(INDEX_DIR):
        print("📂 Chargement de l'index existant...")
        vectorstore = FAISS.load_local(INDEX_DIR, embeddings, allow_dangerous_deserialization=True)
        print(f"✅ Index chargé avec succès")
    else:
        print("📂 Création d'un nouvel index...")
        vectorstore = FAISS.from_documents([], embeddings)
        print(f"✅ Nouvel index créé")
    
    # Ajouter les nouvelles annonces
    print(f"📦 Ajout de {len(new_annonces)} nouvelles annonces...")
    
    new_docs = [
        Document(page_content=format_annonce(a), metadata={"id": a["$id"]})
        for a in new_annonces
    ]
    
    vectorstore.add_documents(new_docs)
    
    # Sauvegarder l'index mis à jour
    vectorstore.save_local(INDEX_DIR)
    print(f"✅ Index mis à jour et sauvegardé dans '{INDEX_DIR}/'")
    
    # Mettre à jour la liste des IDs indexés
    for annonce in new_annonces:
        indexed_ids.add(annonce['$id'])
    
    save_indexed_ids(indexed_ids)
    print(f"✅ Liste des IDs indexés mise à jour")
    
    # Afficher les nouvelles annonces ajoutées
    print("\n🆕 Nouvelles annonces ajoutées:")
    for i, annonce in enumerate(new_annonces, 1):
        print(f"{i:2d}. {annonce.get('title')} (ID: {annonce['$id']})")
    
    print(f"\n📊 Statistiques finales:")
    print(f"  - Total d'annonces indexées: {len(indexed_ids)}")
    print(f"  - Nouvelles annonces ajoutées: {len(new_annonces)}")
    
    return {"success": True, "new_announcements": len(new_annonces), "message": f"{len(new_annonces)} nouvelles annonces indexées"}

def rebuild_index():
    """Reconstruit complètement l'index (option de secours)"""
    
    print("🔄 Reconstruction complète de l'index...")
    
    # Supprimer les fichiers d'index existants
    if os.path.exists(INDEX_DIR):
        import shutil
        shutil.rmtree(INDEX_DIR)
        print("🗑️ Ancien index supprimé")
    
    if os.path.exists(INDEXED_IDS_FILE):
        os.remove(INDEXED_IDS_FILE)
        print("🗑️ Ancienne liste d'IDs supprimée")
    
    # Relancer l'indexation complète en appelant directement la fonction
    from generate_index_paginated import main as generate_index
    generate_index()
    
    print("✅ Index reconstruit avec succès")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--rebuild":
        rebuild_index()
    else:
        update_index() 