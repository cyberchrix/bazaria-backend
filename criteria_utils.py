# criteria_utils.py

import json
from appwrite.client import Client
from appwrite.services.databases import Databases

import os

# Configuration Appwrite
APPWRITE_ENDPOINT = os.environ.get("APPWRITE_ENDPOINT", "https://cloud.appwrite.io/v1")
APPWRITE_PROJECT = os.environ.get("APPWRITE_PROJECT_ID")
APPWRITE_API_KEY = os.environ.get("APPWRITE_API_KEY")
DATABASE_ID = os.environ.get("APPWRITE_DATABASE_ID")
CRITERIA_COLLECTION_ID = "68850b060013a170d573"  # Cette collection reste fixe

# Cache pour les libellés des critères
_criteria_labels_cache = None

def get_criteria_labels():
    """Récupère les libellés des critères avec cache"""
    global _criteria_labels_cache
    
    if _criteria_labels_cache is not None:
        return _criteria_labels_cache
    
    # Connexion Appwrite
    client = Client()
    client.set_endpoint(APPWRITE_ENDPOINT)
    client.set_project(APPWRITE_PROJECT)
    client.set_key(APPWRITE_API_KEY)
    db = Databases(client)
    
    try:
        # Récupérer tous les critères
        response = db.list_documents(
            database_id=DATABASE_ID, 
            collection_id=CRITERIA_COLLECTION_ID, 
            queries=[]
        )
        
        # Créer un dictionnaire id_criteria -> libellé
        criteria_dict = {}
        for crit in response['documents']:
            crit_id = crit.get('$id')
            label = crit.get('label', 'Sans libellé')
            criteria_dict[crit_id] = label
        
        _criteria_labels_cache = criteria_dict
        return criteria_dict
        
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des critères: {e}")
        return {}

def format_criteria_with_labels(criterias_str):
    """Formate les critères avec leurs libellés"""
    try:
        criterias = json.loads(criterias_str)
        criteria_labels = get_criteria_labels()
        
        formatted_criteria = []
        for crit in criterias:
            crit_id = crit.get('id_criteria')
            value = crit.get('value', '')
            label = criteria_labels.get(crit_id, 'Critère inconnu')
            formatted_criteria.append(f"{label}: {value}")
        
        return formatted_criteria
    except:
        return [] 