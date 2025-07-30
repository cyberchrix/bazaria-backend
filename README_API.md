# Bazaria Search API - Déploiement Render

## 🚀 Déploiement sur Render

### Prérequis
- Compte Render.com
- Variables d'environnement configurées

### Étapes de déploiement

1. **Connecter votre repository GitHub à Render**
   - Allez sur [render.com](https://render.com)
   - Créez un nouveau "Web Service"
   - Connectez votre repository GitHub

2. **Configuration automatique**
   - Render détectera automatiquement le fichier `render.yaml`
   - Le service sera configuré automatiquement

3. **Variables d'environnement à configurer**
   
   Dans l'interface Render, ajoutez ces variables :
   
   ```
   OPENAI_API_KEY=sk-proj-...
   APPWRITE_ENDPOINT=https://cloud.appwrite.io/v1
   APPWRITE_PROJECT_ID=votre_project_id
   APPWRITE_API_KEY=votre_api_key
   APPWRITE_DATABASE_ID=votre_database_id
   APPWRITE_COLLECTION_ID=votre_collection_id
   ```

4. **Déploiement**
   - Render déploiera automatiquement votre API
   - L'URL sera générée automatiquement (ex: `https://bazaria-search-api.onrender.com`)

### 🔧 Configuration

- **Plan**: Free (limité à 750h/mois)
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `./render_start.sh`
- **Port**: Automatiquement géré par Render

### 📊 Monitoring

- **Health Check**: `/health`
- **Documentation**: `/docs` (Swagger UI)
- **API Docs**: `/redoc` (ReDoc)

### 🔍 Endpoints disponibles

- `GET /` - Page d'accueil
- `GET /health` - Vérification de l'état
- `POST /search` - Recherche d'annonces
- `GET /search/{query}` - Recherche GET
- `GET /stats` - Statistiques de l'index

### ⚠️ Notes importantes

1. **Index FAISS**: L'index sera généré au premier démarrage
2. **Timeout**: Le plan gratuit a des limitations de timeout
3. **Cold Start**: Le premier appel peut être lent (génération de l'index)
4. **Variables d'environnement**: Toutes doivent être configurées dans Render

### 🐛 Dépannage

- **Erreur de build**: Vérifiez `requirements.txt`
- **Erreur de démarrage**: Vérifiez les variables d'environnement
- **Timeout**: Le plan gratuit a des limitations

### 📝 Logs

Les logs sont disponibles dans l'interface Render :
- Build logs
- Runtime logs
- Error logs 