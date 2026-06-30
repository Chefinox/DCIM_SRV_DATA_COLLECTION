#!/bin/bash
# Quick test Ralph API dengan curl

TOKEN="1cd05b8d36e258399a52c59f1a4016addb2346a3"
RALPH_URL="http://192.168.101.73:8000"

echo "========================================================================"
echo "Ralph API Connection Test"
echo "========================================================================"
echo ""

echo "Test 1: API Root"
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "Authorization: Token $TOKEN" \
  "$RALPH_URL/api/" | head -5
echo ""

echo "------------------------------------------------------------------------"
echo "Test 2: Data Center Assets Count"
curl -s -H "Authorization: Token $TOKEN" \
  "$RALPH_URL/api/data-center-assets/" | grep -o '"count":[0-9]*'
echo ""

echo "------------------------------------------------------------------------"
echo "Test 3: Search CCTV"
curl -s -H "Authorization: Token $TOKEN" \
  "$RALPH_URL/api/data-center-assets/?search=CCTV" | grep -o '"count":[0-9]*'
echo ""

echo "========================================================================"
echo "If you see 'count' values above, API token is working!"
echo "========================================================================"
