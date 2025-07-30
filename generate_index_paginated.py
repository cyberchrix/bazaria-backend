# generate_index_paginated.py

from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.query import Query
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
import os
from criteria_utils import format_criteria_with_labels

# ==== Configuration ====
APPWRITE_ENDPOINT = os.environ.get("APPWRITE_ENDPOINT", "https://cloud.appwrite.io/v1")
APPWRITE_PROJECT = os.environ.get("APPWRITE_PROJECT_ID")
APPWRITE_API_KEY = os.environ.get("APPWRITE_API_KEY")
DATABASE_ID = os.environ.get("APPWRITE_DATABASE_ID")
COLLECTION_ID = os.environ.get("APPWRITE_COLLECTION_ID")

# Configuration OpenAI
# OPENAI_API_KEY doit être définie comme variable d'environnement

def main():
    """Fonction principale pour générer l'index"""
    
    # ==== Connexion Appwrite ====
    client = Client()
    client.set_endpoint(APPWRITE_ENDPOINT)
    client.set_project(APPWRITE_PROJECT)
    client.set_key(APPWRITE_API_KEY)
    db = Databases(client)

    # ==== Récupération de toutes les annonces avec pagination ====
    print("🔍 Récupération de toutes les annonces avec pagination...")

    all_annonces = []
    offset = 0
    limit = 25  # Limite par page

    while True:
        print(f"📄 Récupération page {offset//limit + 1} (offset={offset}, limit={limit})")
        
        try:
            # Utiliser Query.limit() et Query.offset() pour la pagination
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
            
            # Si on a moins d'annonces que la limite, c'est la dernière page
            if len(annonces) < limit:
                print("  🏁 Dernière page atteinte")
                break
                
        except Exception as e:
            print(f"❌ Erreur lors de la récupération: {e}")
            break

    print(f"\n📊 Total d'annonces récupérées: {len(all_annonces)}")

    # ==== Formater les documents ====
    def format_annonce(a):
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

    docs = [
        Document(page_content=format_annonce(a), metadata={"id": a["$id"]})
        for a in all_annonces
    ]

    # ==== Générer l'index FAISS ====
    print(f"\n📦 Génération des embeddings pour {len(docs)} annonces...")
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_documents(docs, embeddings)

    # ==== Sauvegarder l'index ====
    INDEX_DIR = "index_bazaria"
    if not os.path.exists(INDEX_DIR):
        os.makedirs(INDEX_DIR)

    vectorstore.save_local(INDEX_DIR)
    print(f"✅ Index sauvegardé dans '{INDEX_DIR}/' avec {len(docs)} annonces")

    # ==== Vérification ====
    print("\n🔍 Vérification de l'index généré:")
    print(f"📊 Nombre d'annonces dans l'index: {len(docs)}")
    print("📋 Titres des annonces incluses:")
    for i, doc in enumerate(docs, 1):
        content = doc.page_content
        title_line = content.split('\n')[0]
        title = title_line.replace('Titre : ', '')
        print(f"{i:2d}. {title}")

    # Chercher spécifiquement une villa
    print("\n🏠 Recherche d'annonces contenant 'villa':")
    villa_count = 0
    for doc in docs:
        content = doc.page_content.lower()
        if 'villa' in content:
            villa_count += 1
            title_line = doc.page_content.split('\n')[0]
            title = title_line.replace('Titre : ', '')
            print(f"  🏠 Trouvé: {title}")

    print(f"🏠 Total d'annonces contenant 'villa': {villa_count}")

    if villa_count == 0:
        print("\n💡 Aucune villa trouvée. Vérifiez que votre annonce 'Villa' existe bien dans la base de données.")
    else:
        print(f"\n🎉 Trouvé {villa_count} annonce(s) contenant 'villa' !")

if __name__ == "__main__":
    main() 