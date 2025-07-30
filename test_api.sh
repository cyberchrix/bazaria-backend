#!/bin/bash

# Script de test pour l'API Bazaria Search
# URL de base de l'API
BASE_URL="https://bazaria-backend.onrender.com"

echo "🧪 Tests de l'API Bazaria Search"
echo "=================================="
echo "URL de base: $BASE_URL"
echo ""

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

# Test 1: Health Check
echo -e "${YELLOW}1. Test Health Check${NC}"
response=$(curl -s -w "\n%{http_code}" "$BASE_URL/health")
status_code=$(echo "$response" | tail -n1)
response_body=$(echo "$response" | head -n -1)
print_result "Health Check" "$status_code" "$response_body"

# Test 2: Page d'accueil
echo -e "${YELLOW}2. Test Page d'accueil${NC}"
response=$(curl -s -w "\n%{http_code}" "$BASE_URL/")
status_code=$(echo "$response" | tail -n1)
response_body=$(echo "$response" | head -n -1)
print_result "Page d'accueil" "$status_code" "$response_body"

# Test 3: Statistiques
echo -e "${YELLOW}3. Test Statistiques${NC}"
response=$(curl -s -w "\n%{http_code}" "$BASE_URL/stats")
status_code=$(echo "$response" | tail -n1)
response_body=$(echo "$response" | head -n -1)
print_result "Statistiques" "$status_code" "$response_body"

# Test 4: Recherche GET
echo -e "${YELLOW}4. Test Recherche GET${NC}"
response=$(curl -s -w "\n%{http_code}" "$BASE_URL/search/villa?limit=3")
status_code=$(echo "$response" | tail -n1)
response_body=$(echo "$response" | head -n -1)
print_result "Recherche GET (villa)" "$status_code" "$response_body"

# Test 5: Recherche POST
echo -e "${YELLOW}5. Test Recherche POST${NC}"
response=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{"query": "vélo électrique", "limit": 3}' \
    "$BASE_URL/search")
status_code=$(echo "$response" | tail -n1)
response_body=$(echo "$response" | head -n -1)
print_result "Recherche POST (vélo électrique)" "$status_code" "$response_body"

# Test 6: Recherche POST - Samsung
echo -e "${YELLOW}6. Test Recherche POST - Samsung${NC}"
response=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{"query": "Samsung", "limit": 2}' \
    "$BASE_URL/search")
status_code=$(echo "$response" | tail -n1)
response_body=$(echo "$response" | head -n -1)
print_result "Recherche POST (Samsung)" "$status_code" "$response_body"

# Test 7: Recherche POST - Très bon état
echo -e "${YELLOW}7. Test Recherche POST - Très bon état${NC}"
response=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{"query": "Très bon état", "limit": 2}' \
    "$BASE_URL/search")
status_code=$(echo "$response" | tail -n1)
response_body=$(echo "$response" | head -n -1)
print_result "Recherche POST (Très bon état)" "$status_code" "$response_body"

echo -e "${GREEN}🎉 Tests terminés !${NC}"
echo ""
echo -e "${BLUE}📊 Résumé :${NC}"
echo "- Health Check: Vérifie l'état de l'API"
echo "- Page d'accueil: Point d'entrée principal"
echo "- Statistiques: Informations sur l'index"
echo "- Recherche GET: Recherche via URL"
echo "- Recherche POST: Recherche via JSON (recommandé)"
echo ""
echo -e "${YELLOW}💡 Pour tester d'autres requêtes :${NC}"
echo "curl -X POST -H 'Content-Type: application/json' \\"
echo "  -d '{\"query\": \"votre recherche\", \"limit\": 5}' \\"
echo "  $BASE_URL/search" 