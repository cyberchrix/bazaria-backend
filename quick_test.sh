#!/bin/bash

# Test rapide de l'API Bazaria Search
BASE_URL="https://bazaria-backend.onrender.com"

echo "🚀 Test rapide de l'API Bazaria Search"
echo "======================================"

# Test Health Check
echo "1. Health Check:"
curl -s "$BASE_URL/health" | jq '.'
echo ""

# Test Recherche simple
echo "2. Recherche 'villa':"
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "villa", "limit": 2}' \
  "$BASE_URL/search" | jq '.'
echo ""

# Test Recherche Samsung
echo "3. Recherche 'Samsung':"
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "Samsung", "limit": 2}' \
  "$BASE_URL/search" | jq '.'
echo ""

echo "✅ Tests terminés !" 