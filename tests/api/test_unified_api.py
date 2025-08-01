#!/usr/bin/env python3
"""
Test de comparaison entre API locale et production
"""

import requests
import json
import time
from typing import Dict, Any

# URLs des APIs
LOCAL_URL = "http://localhost:8000"
PROD_URL = "https://bazaria-backend.onrender.com"

def test_endpoint(url: str, endpoint: str, method: str = "GET", data: Dict = None) -> Dict[str, Any]:
    """Teste un endpoint et retourne le résultat"""
    try:
        full_url = f"{url}{endpoint}"
        headers = {"Content-Type": "application/json"} if data else {}
        
        if method == "GET":
            response = requests.get(full_url, timeout=10)
        elif method == "POST":
            response = requests.post(full_url, json=data, headers=headers, timeout=10)
        else:
            return {"error": f"Méthode {method} non supportée"}
        
        if response.status_code == 200:
            return {
                "success": True,
                "data": response.json(),
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds()
            }
        else:
            return {
                "success": False,
                "error": f"Status {response.status_code}: {response.text}",
                "status_code": response.status_code
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Erreur de connexion: {str(e)}"
        }

def compare_apis():
    """Compare les APIs locale et production"""
    print("🔍 COMPARAISON DES APIs LOCALE ET PRODUCTION")
    print("=" * 50)
    
    # Tests à effectuer
    tests = [
        {"endpoint": "/", "method": "GET", "name": "Root"},
        {"endpoint": "/health", "method": "GET", "name": "Health Check"},
        {"endpoint": "/search", "method": "POST", "data": {"query": "villa", "limit": 3}, "name": "Recherche hybride"},
        {"endpoint": "/search/fast", "method": "POST", "data": {"query": "villa", "limit": 3}, "name": "Recherche rapide"},
        {"endpoint": "/stats", "method": "GET", "name": "Statistiques"}
    ]
    
    results = {"local": {}, "production": {}}
    
    for test in tests:
        print(f"\n📋 Test: {test['name']}")
        print("-" * 30)
        
        # Test local
        print("🏠 Local:")
        local_result = test_endpoint(LOCAL_URL, test["endpoint"], test["method"], test.get("data"))
        results["local"][test["name"]] = local_result
        
        if local_result["success"]:
            print(f"   ✅ Succès ({local_result.get('response_time', 0):.3f}s)")
        else:
            print(f"   ❌ Échec: {local_result['error']}")
        
        # Test production
        print("🌐 Production:")
        prod_result = test_endpoint(PROD_URL, test["endpoint"], test["method"], test.get("data"))
        results["production"][test["name"]] = prod_result
        
        if prod_result["success"]:
            print(f"   ✅ Succès ({prod_result.get('response_time', 0):.3f}s)")
        else:
            print(f"   ❌ Échec: {prod_result['error']}")
        
        # Comparaison des résultats
        if local_result["success"] and prod_result["success"]:
            local_data = local_result["data"]
            prod_data = prod_result["data"]
            
            # Comparaison simple pour les recherches
            if "results" in local_data and "results" in prod_data:
                local_count = len(local_data["results"])
                prod_count = len(prod_data["results"])
                
                if local_count == prod_count:
                    print(f"   ✅ Résultats identiques: {local_count} résultats")
                else:
                    print(f"   ⚠️  Différence: {local_count} vs {prod_count} résultats")
            else:
                print("   ℹ️  Pas de comparaison de résultats possible")
    
    # Résumé
    print("\n📊 RÉSUMÉ")
    print("=" * 30)
    
    local_success = sum(1 for r in results["local"].values() if r["success"])
    prod_success = sum(1 for r in results["production"].values() if r["success"])
    
    print(f"🏠 Local: {local_success}/{len(tests)} tests réussis")
    print(f"🌐 Production: {prod_success}/{len(tests)} tests réussis")
    
    if local_success == len(tests) and prod_success == len(tests):
        print("🎉 Les deux APIs fonctionnent parfaitement !")
    elif local_success == len(tests):
        print("⚠️  API locale OK, problème en production")
    elif prod_success == len(tests):
        print("⚠️  API production OK, problème en local")
    else:
        print("❌ Problèmes sur les deux APIs")

if __name__ == "__main__":
    compare_apis() 