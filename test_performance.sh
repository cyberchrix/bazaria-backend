#!/bin/bash

# Script de test de performance pour comparer les endpoints de recherche
BASE_URL="https://bazaria-backend.onrender.com"

echo "⚡ Test de performance des endpoints de recherche"
echo "==============================================="

# Couleurs pour l'affichage
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonction pour mesurer le temps
measure_time() {
    local endpoint="$1"
    local query="$2"
    local limit="$3"
    
    echo -e "${YELLOW}Test: $endpoint${NC}"
    echo -e "${BLUE}Query: '$query' (limit: $limit)${NC}"
    
    # Mesurer le temps avec time
    start_time=$(date +%s.%N)
    
    if [[ "$endpoint" == "fast" ]]; then
        response=$(curl -s -X POST \
            -H "Content-Type: application/json" \
            -d "{\"query\": \"$query\", \"limit\": $limit}" \
            "$BASE_URL/search/fast")
    else
        response=$(curl -s -X POST \
            -H "Content-Type: application/json" \
            -d "{\"query\": \"$query\", \"limit\": $limit}" \
            "$BASE_URL/search")
    fi
    
    end_time=$(date +%s.%N)
    duration=$(echo "$end_time - $start_time" | bc)
    
    # Vérifier si la réponse contient une erreur
    if echo "$response" | grep -q "error"; then
        echo -e "${RED}❌ Erreur: $response${NC}"
    else
        echo -e "${GREEN}✅ Succès (${duration}s)${NC}"
        # Compter les résultats
        result_count=$(echo "$response" | jq '.total_results' 2>/dev/null || echo "0")
        echo -e "${BLUE}📊 Résultats: $result_count${NC}"
    fi
    
    echo ""
}

# Tests de performance
echo -e "${BLUE}1. Test avec 'villa' (limit: 2)${NC}"
measure_time "hybrid" "villa" 2
measure_time "fast" "villa" 2

echo -e "${BLUE}2. Test avec 'vélo' (limit: 3)${NC}"
measure_time "hybrid" "vélo" 3
measure_time "fast" "vélo" 3

echo -e "${BLUE}3. Test avec 'Samsung' (limit: 2)${NC}"
measure_time "hybrid" "Samsung" 2
measure_time "fast" "Samsung" 2

echo -e "${BLUE}4. Test avec 'iPhone' (limit: 2)${NC}"
measure_time "hybrid" "iPhone" 2
measure_time "fast" "iPhone" 2

echo -e "${GREEN}🎉 Tests de performance terminés !${NC}"
echo ""
echo -e "${BLUE}📊 Résumé :${NC}"
echo "- /search : Recherche hybride complète (plus lente)"
echo "- /search/fast : Recherche rapide (utilise uniquement FAISS)"
echo ""
echo -e "${YELLOW}💡 Recommandation :${NC}"
echo "Utilisez /search/fast pour de meilleures performances en production" 