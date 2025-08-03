# demo_multiquery.py

import os
import sys
import logging
from typing import List, Dict

# Charger les variables d'environnement depuis .env
def load_env_vars():
    """Charge les variables d'environnement depuis le fichier .env"""
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

# Charger les variables d'environnement
load_env_vars()

# Ajouter le répertoire parent au path pour importer les modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hybrid_search import HybridSearchAPI

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def demo_multiquery_improvements():
    """Démonstration des améliorations du MultiQueryRetriever"""
    
    print("🚀 Démonstration MultiQueryRetriever")
    print("=" * 60)
    print("Ce script démontre les améliorations apportées par le MultiQueryRetriever")
    print("qui génère automatiquement plusieurs variantes de requête pour améliorer")
    print("la couverture de recherche sémantique.")
    print()
    
    # Demander la clé API OpenAI
    api_key = input("🔑 Entrez votre clé API OpenAI: ").strip()
    if not api_key:
        print("❌ Clé API requise")
        return
    
    # Initialiser l'API
    print("\n🔧 Initialisation de l'API...")
    api = HybridSearchAPI(api_key)
    
    if not api.vectorstore:
        print("❌ Impossible d'initialiser l'API")
        return
    
    print("✅ API initialisée avec succès")
    print("✅ MultiQueryRetriever activé")
    
    # Exemples de requêtes qui bénéficient du MultiQueryRetriever
    demo_queries = [
        {
            "query": "voiture rouge pas cher",
            "description": "Requête avec synonymes et variations de prix",
            "expected_variants": [
                "voiture rouge bon prix",
                "automobile rouge économique", 
                "véhicule rouge pas cher",
                "voiture rouge abordable"
            ]
        },
        {
            "query": "véhicule électrique à vendre",
            "description": "Requête avec termes techniques et commercial",
            "expected_variants": [
                "voiture électrique à vendre",
                "véhicule électrique disponible",
                "auto électrique en vente",
                "voiture électrique à acheter"
            ]
        },
        {
            "query": "moto sportive rapide",
            "description": "Requête avec caractéristiques de performance",
            "expected_variants": [
                "moto sportive performante",
                "moto rapide sportive",
                "motocycle sportif rapide",
                "moto sportive puissante"
            ]
        }
    ]
    
    print(f"\n📋 Démonstration avec {len(demo_queries)} requêtes")
    print("=" * 60)
    
    for i, demo in enumerate(demo_queries, 1):
        query = demo["query"]
        description = demo["description"]
        expected_variants = demo["expected_variants"]
        
        print(f"\n🔍 Démo {i}/{len(demo_queries)}: '{query}'")
        print(f"📝 Description: {description}")
        print("-" * 50)
        
        print("🎯 Variantes attendues:")
        for j, variant in enumerate(expected_variants, 1):
            print(f"  {j}. {variant}")
        
        print(f"\n🧠 Test avec MultiQueryRetriever:")
        
        try:
            # Test de la recherche sémantique avec MultiQueryRetriever
            results = api.semantic_search(query, min_score=0.6)
            
            print(f"✅ Résultats trouvés: {len(results)}")
            
            if results:
                print("📊 Top 5 résultats:")
                for j, result in enumerate(results[:5], 1):
                    print(f"  {j}. {result['title']}")
                    print(f"     Type: {result['match_type']}")
                    print(f"     Score: {result['score']:.4f}")
                    print(f"     Prix: {result['price']} €")
                    print(f"     Localisation: {result['location']}")
                    print()
            else:
                print("⚠️ Aucun résultat trouvé")
                
        except Exception as e:
            print(f"❌ Erreur lors du test: {e}")
    
    # Test de comparaison détaillé
    print("\n🎯 Test de comparaison détaillé")
    print("=" * 60)
    
    comparison_query = "voiture rouge pas chère"
    print(f"\n🔍 Comparaison pour: '{comparison_query}'")
    
    try:
        # Test avec MultiQueryRetriever
        print("\n🧠 Avec MultiQueryRetriever:")
        multi_results = api.semantic_search(comparison_query, min_score=0.6)
        print(f"  Résultats: {len(multi_results)}")
        
        if multi_results:
            print("  Top 5:")
            for i, result in enumerate(multi_results[:5], 1):
                print(f"    {i}. {result['title']} (Score: {result['score']:.4f})")
        
        # Test avec méthode de fallback (classique)
        print("\n📝 Avec méthode classique (fallback):")
        fallback_results = api._semantic_search_fallback(comparison_query, min_score=0.6)
        print(f"  Résultats: {len(fallback_results)}")
        
        if fallback_results:
            print("  Top 5:")
            for i, result in enumerate(fallback_results[:5], 1):
                print(f"    {i}. {result['title']} (Score: {result['score']:.4f})")
        
        # Analyse détaillée
        print(f"\n📊 Analyse détaillée:")
        print(f"  MultiQueryRetriever: {len(multi_results)} résultats")
        print(f"  Méthode classique: {len(fallback_results)} résultats")
        
        # Identifier les résultats uniques
        multi_ids = {r['id'] for r in multi_results}
        fallback_ids = {r['id'] for r in fallback_results}
        
        unique_to_multi = multi_ids - fallback_ids
        unique_to_fallback = fallback_ids - multi_ids
        common = multi_ids & fallback_ids
        
        print(f"  Résultats communs: {len(common)}")
        print(f"  Uniques à MultiQuery: {len(unique_to_multi)}")
        print(f"  Uniques à classique: {len(unique_to_fallback)}")
        
        if unique_to_multi:
            print(f"  ✅ MultiQueryRetriever a trouvé {len(unique_to_multi)} résultats supplémentaires!")
            print("  📋 Résultats supplémentaires:")
            for i, result in enumerate([r for r in multi_results if r['id'] in unique_to_multi][:3], 1):
                print(f"    {i}. {result['title']} (Score: {result['score']:.4f})")
        
        # Calculer l'amélioration
        if len(fallback_results) > 0:
            improvement = len(unique_to_multi) / len(fallback_results) * 100
            print(f"  📈 Amélioration de couverture: +{improvement:.1f}%")
        
    except Exception as e:
        print(f"❌ Erreur lors de la comparaison: {e}")
    
    print("\n🎉 Démonstration terminée!")
    print("\n💡 Avantages du MultiQueryRetriever:")
    print("  ✅ Génération automatique de variantes de requête")
    print("  ✅ Amélioration de la couverture de recherche")
    print("  ✅ Gestion des synonymes et expressions équivalentes")
    print("  ✅ Fallback automatique vers la méthode classique")
    print("  ✅ Cache intelligent pour optimiser les performances")

def interactive_demo():
    """Démonstration interactive"""
    
    print("🎮 Démonstration interactive MultiQueryRetriever")
    print("=" * 60)
    
    api_key = input("🔑 Entrez votre clé API OpenAI: ").strip()
    if not api_key:
        print("❌ Clé API requise")
        return
    
    api = HybridSearchAPI(api_key)
    
    if not api.vectorstore:
        print("❌ Impossible d'initialiser l'API")
        return
    
    print("✅ API initialisée avec succès")
    print("\n💡 Entrez vos requêtes de test (ou 'quit' pour quitter)")
    print("   Le MultiQueryRetriever générera automatiquement des variantes!")
    
    while True:
        query = input("\n🔎 Votre requête: ").strip()
        if query.lower() == 'quit':
            break
        
        if query:
            try:
                print(f"\n🧠 Recherche avec MultiQueryRetriever pour: '{query}'")
                results = api.semantic_search(query, min_score=0.6)
                
                print(f"✅ {len(results)} résultats trouvés")
                
                if results:
                    print("📊 Top 5 résultats:")
                    for i, result in enumerate(results[:5], 1):
                        print(f"  {i}. {result['title']}")
                        print(f"     Type: {result['match_type']}")
                        print(f"     Score: {result['score']:.4f}")
                        print(f"     Prix: {result['price']} €")
                        print(f"     Localisation: {result['location']}")
                        print()
                else:
                    print("⚠️ Aucun résultat trouvé")
                    
            except Exception as e:
                print(f"❌ Erreur: {e}")
    
    print("\n✅ Démonstration interactive terminée!")

if __name__ == "__main__":
    print("🚀 Démonstration MultiQueryRetriever")
    print("1. Démonstration complète avec comparaisons")
    print("2. Démonstration interactive")
    
    choice = input("\nChoisissez une option (1 ou 2): ").strip()
    
    if choice == "1":
        demo_multiquery_improvements()
    elif choice == "2":
        interactive_demo()
    else:
        print("❌ Choix invalide") 