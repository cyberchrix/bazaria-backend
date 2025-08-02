# generate_index_paginated.py

from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.query import Query
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
import os
from criteria_utils import format_criteria_with_labels
import json

# ==== Configuration ====
APPWRITE_ENDPOINT = os.environ.get("APPWRITE_ENDPOINT", "https://cloud.appwrite.io/v1")
APPWRITE_PROJECT = os.environ.get("APPWRITE_PROJECT_ID")
APPWRITE_API_KEY = os.environ.get("APPWRITE_API_KEY")
DATABASE_ID = os.environ.get("APPWRITE_DATABASE_ID")
COLLECTION_ID = os.environ.get("APPWRITE_COLLECTION_ID")

# Configuration OpenAI
# OPENAI_API_KEY doit être définie comme variable d'environnement

def get_criteria_labels():
    """Retourne les libellés des critères pour la détermination de la catégorie."""
    from criteria_utils import get_criteria_labels as get_criteria_labels_from_utils
    return get_criteria_labels_from_utils()

def determine_category(criterias_str, title, description):
    """Détermine la catégorie principale de l'annonce basée sur les critères et le contenu"""
    try:
        criterias = json.loads(criterias_str)
        criteria_labels = get_criteria_labels()
        
        # Mots-clés pour identifier les catégories
        category_keywords = {
            "Véhicules": ["vélo", "voiture", "moto", "scooter", "véhicule", "automobile", "peugeot", "renault", "citroën", "bmw", "audi", "mercedes"],
            "Immobilier": ["maison", "appartement", "villa", "studio", "duplex", "location", "bien immobilier", "logement"],
            "Électronique": ["téléphone", "smartphone", "ordinateur", "laptop", "tablette", "tv", "télévision", "playstation", "xbox", "console"],
            "Mobilier": ["canapé", "lit", "table", "chaise", "armoire", "bureau", "meuble", "mobilier"],
            "Sport & Loisirs": ["vélo", "vtt", "bmx", "sport", "loisir", "équipement sportif"],
            "Décoration": ["tableau", "vase", "miroir", "lampe", "coussin", "déco", "décoration"]
        }
        
        # Analyser le titre et la description
        content_lower = f"{title} {description}".lower()
        
        # Chercher des correspondances de catégories
        for category, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in content_lower:
                    return category
        
        # Si aucune correspondance, analyser les critères
        for crit in criterias:
            crit_id = crit.get('id_criteria')
            value = crit.get('value', '').lower()
            label = criteria_labels.get(crit_id, '').lower()
            
            # Chercher des mots-clés dans les critères
            for category, keywords in category_keywords.items():
                for keyword in keywords:
                    if keyword in value or keyword in label:
                        return category
        
        return "Autres"
        
    except:
        return "Autres"

def format_annonce_improved(a):
    """Formate l'annonce avec catégories structurées et concepts sémantiques"""
    # Déterminer la catégorie
    category = determine_category(a.get('criterias', '[]'), a.get('title', ''), a.get('description', ''))
    
    # Ajouter des concepts sémantiques selon la catégorie
    semantic_concepts = get_semantic_concepts(category, a.get('title', ''), a.get('description', ''))
    
    lignes = [
        f"Titre : {a.get('title', '')}",
        f"Catégorie : {category}",
        f"Localisation : {a.get('location', '')}",
        f"Prix : {a.get('price', '')} €",
        "Caractéristiques :"
    ]
    
    # Utiliser les libellés des critères
    formatted_criteria = format_criteria_with_labels(a.get('criterias', '[]'))
    for crit_line in formatted_criteria:
        lignes.append(f"- {crit_line}")
    
    # Ajouter les concepts sémantiques
    if semantic_concepts:
        lignes.append("")
        lignes.append("Concepts sémantiques :")
        for concept in semantic_concepts:
            lignes.append(f"- {concept}")
    
    lignes.append("")
    lignes.append("Description :")
    lignes.append(a.get('description', ''))
    
    return "\n".join(lignes)

def get_semantic_concepts(category, title, description):
    """Génère des concepts sémantiques pour améliorer la recherche"""
    concepts = []
    
    # Concepts pour les véhicules
    if category == "Véhicules":
        concepts.extend([
            "pour se déplacer",
            "pour me déplacer", 
            "moyen de transport",
            "véhicule de transport",
            "mobilité personnelle",
            "déplacement quotidien",
            "transport individuel"
        ])
        
        # Concepts spécifiques selon le type de véhicule
        title_lower = title.lower()
        if "voiture" in title_lower or "auto" in title_lower:
            concepts.extend([
                "voiture personnelle",
                "automobile",
                "véhicule particulier"
            ])
        elif "moto" in title_lower or "scooter" in title_lower:
            concepts.extend([
                "deux-roues",
                "moto",
                "transport urbain"
            ])
        elif "vélo" in title_lower:
            concepts.extend([
                "vélo",
                "cyclisme",
                "transport écologique",
                "mobilité douce"
            ])
    
    # Concepts pour l'immobilier
    elif category == "Immobilier":
        concepts.extend([
            "lieu de vie",
            "habitation",
            "logement",
            "résidence"
        ])
    
    # Concepts pour le mobilier
    elif category == "Mobilier":
        concepts.extend([
            "aménagement intérieur",
            "décoration",
            "confort domestique",
            "équipement maison"
        ])
    
    # Concepts pour l'électronique
    elif category == "Électronique":
        concepts.extend([
            "technologie",
            "appareil électronique",
            "équipement numérique"
        ])
    
    return concepts

def generate_index():
    """Fonction pour générer l'index FAISS - utilisée par l'API de production"""
    main()

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

    # ==== Formater les documents avec catégories ====
    docs = []
    categories_count = {}
    
    print(f"\n🔧 Formatage de {len(all_annonces)} annonces...")
    
    for i, a in enumerate(all_annonces, 1):
        try:
            print(f"  📝 Traitement annonce {i}/{len(all_annonces)}: '{a.get('title', 'N/A')}' (ID: {a.get('$id', 'N/A')})")
            
            # Déterminer la catégorie
            category = determine_category(a.get('criterias', '[]'), a.get('title', ''), a.get('description', ''))
            print(f"    🏷️ Catégorie déterminée: {category}")
            
            # Formater le contenu
            try:
                formatted_content = format_annonce_improved(a)
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
                    "location": a.get('location', ''),
                    "category": category
                }
            )
            
            docs.append(doc)
            categories_count[category] = categories_count.get(category, 0) + 1
            print(f"    ✅ Document créé et ajouté")
            
        except Exception as e:
            print(f"    ❌ Erreur traitement annonce {i}: {e}")
            continue

    # ==== Générer l'index FAISS ====
    print(f"\n📦 Génération des embeddings pour {len(docs)} annonces...")
    
    try:
        # Utiliser un modèle d'embedding plus avancé pour une meilleure compréhension sémantique
        print("  🔧 Initialisation OpenAI Embeddings...")
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large",  # Modèle plus avancé
            dimensions=3072  # Plus de dimensions pour une meilleure représentation
        )
        print("  ✅ OpenAI Embeddings initialisé")
        
        print("  🔧 Création de l'index FAISS...")
        vectorstore = FAISS.from_documents(docs, embeddings)
        print("  ✅ Index FAISS créé avec succès")
        
    except Exception as e:
        print(f"  ❌ Erreur création index FAISS: {e}")
        raise

    # ==== Sauvegarder l'index ====
    INDEX_DIR = "index_bazaria"
    print(f"\n💾 Sauvegarde de l'index dans '{INDEX_DIR}/'...")
    
    try:
        if not os.path.exists(INDEX_DIR):
            os.makedirs(INDEX_DIR)
            print("  📁 Répertoire créé")
        
        vectorstore.save_local(INDEX_DIR)
        print(f"  ✅ Index sauvegardé avec {len(docs)} annonces")
        
    except Exception as e:
        print(f"  ❌ Erreur sauvegarde: {e}")
        raise

    # ==== Vérification avec catégories ====
    print("\n🔍 Vérification de l'index généré:")
    print(f"📊 Nombre d'annonces dans l'index: {len(docs)}")
    print("📋 Répartition par catégories:")
    for category, count in sorted(categories_count.items()):
        print(f"  - {category}: {count} annonces")
    
    print("\n📋 Titres des annonces incluses:")
    for i, doc in enumerate(docs, 1):
        content = doc.page_content
        title_line = content.split('\n')[0]
        title = title_line.replace('Titre : ', '')
        category = doc.metadata.get('category', 'Non classé')
        print(f"{i:2d}. [{category}] {title}")

    # Chercher spécifiquement une villa
    print("\n🏠 Recherche d'annonces contenant 'villa':")
    villa_count = 0
    for doc in docs:
        content = doc.page_content.lower()
        if 'villa' in content:
            villa_count += 1
            title_line = doc.page_content.split('\n')[0]
            title = title_line.replace('Titre : ', '')
            category = doc.metadata.get('category', 'Non classé')
            print(f"  🏠 Trouvé: [{category}] {title}")

    print(f"🏠 Total d'annonces contenant 'villa': {villa_count}")

    if villa_count == 0:
        print("\n💡 Aucune villa trouvée. Vérifiez que votre annonce 'Villa' existe bien dans la base de données.")
    else:
        print(f"\n🎉 Trouvé {villa_count} annonce(s) contenant 'villa' !")

if __name__ == "__main__":
    main() 