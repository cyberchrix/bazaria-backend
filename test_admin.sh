#!/bin/bash

# Script de test pour les endpoints d'administration
BASE_URL="https://bazaria-backend.onrender.com"

echo "🔧 Tests des endpoints d'administration"
echo "====================================="

# Couleurs pour l'affichage
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonction pour afficher les résultats
print_result() {
    local test_name="$1"
    local status_code="$2"
    local response="$3"
    
    if [ "$status_code" -eq 200 ]; then
        echo -e "${GREEN}✅ $test_name (Status: $status_code)${NC}"
    else
        echo -e "${RED}❌ $test_name (Status: $status_code)${NC}"
    fi
    echo -e "${BLUE}Réponse:${NC}"
    echo "$response" | jq '.' 2>/dev/null || echo "$response"
    echo ""
}

# Test 1: Statistiques
echo -e "${YELLOW}1. Test Statistiques${NC}"
response=$(curl -s -w "\n%{http_code}" "$BASE_URL/stats")
status_code=$(echo "$response" | tail -n1)
response_body=$(echo "$response" | head -n -1)
print_result "Statistiques" "$status_code" "$response_body"

# Test 2: Mise à jour de l'index
echo -e "${YELLOW}2. Test Mise à jour de l'index${NC}"
response=$(curl -s -w "\n%{http_code}" \
    -X POST \
    "$BASE_URL/admin/update-index")
status_code=$(echo "$response" | tail -n1)
response_body=$(echo "$response" | head -n -1)
print_result "Mise à jour index" "$status_code" "$response_body"

# Test 3: Reconstruction de l'index
echo -e "${YELLOW}3. Test Reconstruction de l'index${NC}"
response=$(curl -s -w "\n%{http_code}" \
    -X POST \
    "$BASE_URL/admin/rebuild-index")
status_code=$(echo "$response" | tail -n1)
response_body=$(echo "$response" | head -n -1)
print_result "Reconstruction index" "$status_code" "$response_body"

echo -e "${GREEN}🎉 Tests d'administration terminés !${NC}"
echo ""
echo -e "${BLUE}📊 Utilisation :${NC}"
echo "- POST /admin/update-index : Met à jour l'index avec les nouvelles annonces"
echo "- POST /admin/rebuild-index : Force la reconstruction complète de l'index"
echo "- GET /stats : Affiche les statistiques de l'index" 