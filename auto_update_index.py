#!/usr/bin/env python3
# auto_update_index.py

"""
Script automatique pour mettre à jour l'index FAISS
Usage: python auto_update_index.py [--rebuild]
"""

import sys
import os

def main():
    """Script principal"""
    
    print("🤖 Mise à jour automatique de l'index FAISS")
    print("=" * 50)
    
    # Vérifier si l'environnement virtuel existe
    if not os.path.exists("venv/bin/python"):
        print("❌ Environnement virtuel non trouvé. Exécutez d'abord:")
        print("   python3 -m venv venv")
        print("   source venv/bin/activate")
        print("   pip install -r requirements.txt")
        return
    
    # Vérifier si les scripts nécessaires existent
    required_files = ["update_index.py", "hybrid_search.py"]
    for file in required_files:
        if not os.path.exists(file):
            print(f"❌ Fichier {file} non trouvé")
            return
    
    # Déterminer l'action
    if len(sys.argv) > 1 and sys.argv[1] == "--rebuild":
        print("🔄 Reconstruction complète de l'index...")
        os.system("venv/bin/python update_index.py --rebuild")
    else:
        print("🔄 Mise à jour incrémentale de l'index...")
        os.system("venv/bin/python update_index.py")
    
    print("\n✅ Mise à jour terminée!")
    print("\n💡 Pour tester la recherche:")
    print("   python auto_update_index.py")
    print("   venv/bin/python hybrid_search.py")

if __name__ == "__main__":
    main() 