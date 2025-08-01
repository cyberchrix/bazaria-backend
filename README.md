# Bazaria Search API

API de recherche hybride pour les annonces Bazaria, déployée sur Render.

## 📁 Structure du projet

```
bazaria-backend/
├── api.py                 # API FastAPI principale
├── hybrid_search.py       # Système de recherche hybride
├── criteria_utils.py      # Utilitaires pour les critères
├── generate_index_paginated.py  # Génération d'index avec pagination
├── update_index.py        # Mise à jour incrémentale de l'index
├── auto_update_index.py   # Script automatique de mise à jour
├── render.yaml           # Configuration Render
├── render_start.sh       # Script de démarrage Render
├── requirements.txt      # Dépendances Python
├── README_API.md        # Documentation API complète
└── index_bazaria/       # Index FAISS (généré automatiquement)
```

## 🚀 Déploiement sur Render

### 1. Configuration
1. Connectez votre repo GitHub à Render
2. Créez un nouveau **Web Service**
3. Configurez la variable d'environnement :
   - `OPENAI_API_KEY`: Votre clé API OpenAI

### 2. Fichiers de configuration
- `render.yaml`: Configuration automatique
- `render_start.sh`: Script de démarrage
- `requirements.txt`: Dépendances Python

## 🔧 Développement local

### 1. Installation
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Génération de l'index
```bash
python auto_update_index.py --rebuild
```

### 3. Démarrage de l'API
```bash
python api.py
```

### 4. Test de l'API
```bash
curl http://localhost:8000/health
curl http://localhost:8000/search/villa
```

## 📡 Endpoints API

- `GET /` - Health check
- `GET /health` - État de l'API
- `GET /stats` - Statistiques
- `GET /search/{query}` - Recherche GET
- `POST /search` - Recherche POST (recommandé)
- `GET /docs` - Documentation Swagger

## 📱 Intégration Flutter

Voir `README_API.md` pour la documentation complète d'intégration Flutter.

## 🔄 Mise à jour de l'index

### Mise à jour manuelle
```bash
python auto_update_index.py
```

### Mise à jour complète
```bash
python auto_update_index.py --rebuild
```

## 📊 Fonctionnalités

- ✅ **Recherche hybride** (textuelle + sémantique)
- ✅ **Recherche dans tous les champs** (titre, description, caractéristiques)
- ✅ **Libellés des critères** (Type de vélo, Marque, État, etc.)
- ✅ **CORS configuré** pour Flutter
- ✅ **Documentation automatique** (Swagger)
- ✅ **Health checks** et statistiques
- ✅ **Gestion d'erreurs** complète

## 🚀 Exemples de recherche

- `"villa"` → Trouve les villas
- `"Samsung"` → Trouve les Samsung Galaxy
- `"Vélo électrique"` → Trouve les vélos électriques
- `"Très bon état"` → Trouve les objets en bon état
- `"Marque: Trek"` → Trouve les vélos Trek # Force restart


<!-- Force restart: 2025-08-01 19:33:19 -->


<!-- Force complete rebuild: 2025-08-01 19:56:44 -->
