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
    
    # Récupérer toutes les annonces
    print("🔍 Récupération de toutes les annonces...")
    all_annonces = []
    offset = 0
    limit = 25
    
    while True:
        print(f"📄 Récupération page {offset//limit + 1} (offset={offset}, limit={limit})")
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
            print(f"  ✅ Récupéré {len(annonces)} annonces")
            
            if len(annonces) == 0:
                print("  🏁 Fin de pagination (aucune annonce)")
                break
            
            all_annonces.extend(annonces)
            offset += limit
            
            if len(annonces) < limit:
                print("  🏁 Dernière page atteinte")
                break
                
        except Exception as e:
            print(f"❌ Erreur lors de la récupération: {e}")
            return {"success": False, "new_announcements": 0, "message": f"Erreur lors de la récupération: {e}"}
    
    print(f"📊 Total d'annonces récupérées: {len(all_annonces)}")
    
    # Afficher les titres des annonces récupérées
    print("📋 Annonces récupérées:")
    for i, annonce in enumerate(all_annonces, 1):
        print(f"  {i}. {annonce.get('title', 'N/A')} (ID: {annonce.get('$id', 'N/A')})")
    
    # Forcer la régénération complète avec le nouveau format
    print("🔄 Régénération complète avec le nouveau format...")
    
    # Supprimer l'index existant pour forcer la régénération
    if os.path.exists(INDEX_DIR):
        import shutil
        shutil.rmtree(INDEX_DIR)
        print("🗑️ Ancien index supprimé")
    
    if os.path.exists(INDEXED_IDS_FILE):
        os.remove(INDEXED_IDS_FILE)
        print("🗑️ Ancienne liste d'IDs supprimée")
    
    # Créer un nouvel index avec toutes les annonces
    # Utiliser un modèle d'embedding plus avancé pour une meilleure compréhension sémantique
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-large",  # Modèle plus avancé
        dimensions=3072  # Plus de dimensions pour une meilleure représentation
    )
    
    # Formater tous les documents avec les métadonnées complètes
    print(f"\n🔧 Formatage de {len(all_annonces)} annonces...")
    docs = []
    
    for i, a in enumerate(all_annonces, 1):
        try:
            print(f"  📝 Traitement annonce {i}/{len(all_annonces)}: '{a.get('title', 'N/A')}' (ID: {a.get('$id', 'N/A')})")
            
            # Formater le contenu
            try:
                formatted_content = format_annonce(a)
                print(f"    ✅ Contenu formaté ({len(formatted_content)} caractères)")
            except Exception as e:
                print(f"    ❌ Erreur formatage: {e}")
                continue
            
            # Créer le document
            doc = Document(
                page_content=formatted_content, 
                metadata={
                    "id": a["$id"],
                    "title": a.get('title', ''),
                    "description": a.get('description', ''),
                    "price": a.get('price', 0.0),
                    "location": a.get('location', '')
                }
            )
            
            docs.append(doc)
            print(f"    ✅ Document créé et ajouté")
            
        except Exception as e:
            print(f"    ❌ Erreur traitement annonce {i}: {e}")
            continue
    
    # Générer l'index FAISS
    print(f"\n📦 Génération des embeddings pour {len(docs)} annonces...")
    
    try:
        print("  🔧 Création de l'index FAISS...")
        vectorstore = FAISS.from_documents(docs, embeddings)
        print("  ✅ Index FAISS créé avec succès")
        
    except Exception as e:
        print(f"  ❌ Erreur création index FAISS: {e}")
        return {"success": False, "new_announcements": 0, "message": f"Erreur création index FAISS: {e}"}
    
    # Sauvegarder l'index
    vectorstore.save_local(INDEX_DIR)
    print(f"✅ Index sauvegardé dans '{INDEX_DIR}/' avec {len(docs)} annonces")
    
    # Mettre à jour la liste des IDs indexés
    indexed_ids = set()
    for annonce in all_annonces:
        indexed_ids.add(annonce['$id'])
    
    save_indexed_ids(indexed_ids)
    print(f"✅ Liste des IDs indexés mise à jour")
    
    # Afficher les titres des annonces incluses
    print("\n📋 Titres des annonces incluses:")
    for i, doc in enumerate(docs, 1):
        title = doc.metadata.get('title', 'Titre non disponible')
        print(f"{i:2d}. {title}")
    
    print(f"\n📊 Statistiques finales:")
    print(f"  - Total d'annonces indexées: {len(indexed_ids)}")
    print(f"  - Nouvelles annonces ajoutées: {len(all_annonces)}")
    
    return {"success": True, "new_announcements": len(all_annonces), "message": f"{len(all_annonces)} annonces indexées avec le nouveau format"}

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
    
    # Forcer la régénération complète avec toutes les annonces
    print("📦 Régénération complète avec toutes les annonces...")
    
    # Connexion Appwrite
    client = Client()
    client.set_endpoint(APPWRITE_ENDPOINT)
    client.set_project(APPWRITE_PROJECT)
    client.set_key(APPWRITE_API_KEY)
    db = Databases(client)
    
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
            break
    
    print(f"📊 Total d'annonces récupérées: {len(all_annonces)}")
    
    # Formater les documents avec les métadonnées complètes
    docs = [
        Document(
            page_content=format_annonce(a), 
            metadata={
                "id": a["$id"],
                "title": a.get('title', ''),
                "description": a.get('description', ''),
                "price": a.get('price', 0.0),
                "location": a.get('location', '')
            }
        )
        for a in all_annonces
    ]
    
    # Générer l'index FAISS
    print(f"📦 Génération des embeddings pour {len(docs)} annonces...")
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_documents(docs, embeddings)
    
    # Sauvegarder l'index
    vectorstore.save_local(INDEX_DIR)
    print(f"✅ Index sauvegardé dans '{INDEX_DIR}/' avec {len(docs)} annonces")
    
    # Afficher les titres des annonces incluses
    print("\n📋 Titres des annonces incluses:")
    for i, doc in enumerate(docs, 1):
        title = doc.metadata.get('title', 'Titre non disponible')
        print(f"{i:2d}. {title}")
    
    print("✅ Index reconstruit avec succès")

def add_new_announcements():
    """Ajoute seulement les nouvelles annonces à l'index existant"""
    
    print("🔄 Ajout des nouvelles annonces à l'index FAISS...")
    
    # Connexion Appwrite
    client = Client()
    client.set_endpoint(APPWRITE_ENDPOINT)
    client.set_project(APPWRITE_PROJECT)
    client.set_key(APPWRITE_API_KEY)
    db = Databases(client)
    
    # Charger les IDs déjà indexés
    indexed_ids = load_indexed_ids()
    print(f"📊 IDs déjà indexés: {len(indexed_ids)}")
    
    # Récupérer toutes les annonces
    print("🔍 Récupération de toutes les annonces...")
    all_annonces = []
    offset = 0
    limit = 25
    
    while True:
        print(f"📄 Récupération page {offset//limit + 1} (offset={offset}, limit={limit})")
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
            print(f"  ✅ Récupéré {len(annonces)} annonces")
            
            if len(annonces) == 0:
                print("  🏁 Fin de pagination (aucune annonce)")
                break
            
            all_annonces.extend(annonces)
            offset += limit
            
            if len(annonces) < limit:
                print("  🏁 Dernière page atteinte")
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
    
    print(f"🆕 Nouvelles annonces trouvées: {len(new_annonces)}")
    
    if len(new_annonces) == 0:
        print("✅ Aucune nouvelle annonce à ajouter")
        return {"success": True, "new_announcements": 0, "message": "Aucune nouvelle annonce à ajouter"}
    
    # Afficher les nouvelles annonces
    print("📋 Nouvelles annonces:")
    for i, annonce in enumerate(new_annonces, 1):
        print(f"  {i}. {annonce.get('title', 'N/A')} (ID: {annonce.get('$id', 'N/A')})")
    
    # Charger l'index existant
    if not os.path.exists(INDEX_DIR):
        print("❌ Index FAISS non trouvé, création d'un nouvel index...")
        return update_index()
    
    print("📦 Chargement de l'index FAISS existant...")
    try:
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large",
            dimensions=3072
        )
        vectorstore = FAISS.load_local(INDEX_DIR, embeddings, allow_dangerous_deserialization=True)
        print("✅ Index FAISS chargé avec succès")
    except Exception as e:
        print(f"❌ Erreur chargement index: {e}")
        return {"success": False, "new_announcements": 0, "message": f"Erreur chargement index: {e}"}
    
    # Formater les nouvelles annonces
    print(f"\n🔧 Formatage de {len(new_annonces)} nouvelles annonces...")
    new_docs = []
    
    for i, a in enumerate(new_annonces, 1):
        try:
            print(f"  📝 Traitement nouvelle annonce {i}/{len(new_annonces)}: '{a.get('title', 'N/A')}' (ID: {a.get('$id', 'N/A')})")
            
            try:
                formatted_content = format_annonce(a)
                print(f"    ✅ Contenu formaté ({len(formatted_content)} caractères)")
            except Exception as e:
                print(f"    ❌ Erreur formatage: {e}")
                continue
            
            doc = Document(
                page_content=formatted_content, 
                metadata={
                    "id": a["$id"],
                    "title": a.get('title', ''),
                    "description": a.get('description', ''),
                    "price": a.get('price', 0.0),
                    "location": a.get('location', '')
                }
            )
            
            new_docs.append(doc)
            print(f"    ✅ Document créé et ajouté")
            
        except Exception as e:
            print(f"    ❌ Erreur traitement annonce {i}: {e}")
            continue
    
    if len(new_docs) == 0:
        print("❌ Aucun document valide à ajouter")
        return {"success": False, "new_announcements": 0, "message": "Aucun document valide à ajouter"}
    
    # Ajouter les nouveaux documents à l'index
    print(f"\n📦 Ajout de {len(new_docs)} nouveaux documents à l'index...")
    try:
        vectorstore.add_documents(new_docs)
        print("✅ Nouveaux documents ajoutés à l'index")
    except Exception as e:
        print(f"❌ Erreur ajout documents: {e}")
        return {"success": False, "new_announcements": 0, "message": f"Erreur ajout documents: {e}"}
    
    # Sauvegarder l'index mis à jour
    vectorstore.save_local(INDEX_DIR)
    print(f"✅ Index mis à jour sauvegardé dans '{INDEX_DIR}/'")
    
    # Mettre à jour la liste des IDs indexés
    for annonce in new_annonces:
        indexed_ids.add(annonce['$id'])
    
    save_indexed_ids(indexed_ids)
    print(f"✅ Liste des IDs indexés mise à jour")
    
    print(f"\n📊 Statistiques finales:")
    print(f"  - Nouvelles annonces ajoutées: {len(new_annonces)}")
    print(f"  - Total d'annonces indexées: {len(indexed_ids)}")
    
    return {"success": True, "new_announcements": len(new_annonces), "message": f"{len(new_annonces)} nouvelles annonces ajoutées à l'index"}

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--rebuild":
        rebuild_index()
    else:
        update_index() 