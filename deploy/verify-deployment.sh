#!/bin/bash
# Post-Migration Verification Script for MyApp
# Run this after deploying to AWS to verify everything works

set -e

DOMAIN="${1:-api.example.com}"
BASE_URL="https://$DOMAIN"

echo "=== MyApp Deployment Verification ==="
echo "Testing: $BASE_URL"
echo ""

PASS=0
FAIL=0

# Function to test an endpoint
test_endpoint() {
    local name="$1"
    local url="$2"
    local expected_status="${3:-200}"
    
    printf "%-40s" "Testing $name..."
    
    status=$(curl -s -o /dev/null -w "%{http_code}" "$url" --max-time 10 2>/dev/null || echo "000")
    
    if [ "$status" = "$expected_status" ]; then
        echo "✓ PASS (HTTP $status)"
        ((PASS++))
    else
        echo "✗ FAIL (Expected $expected_status, got $status)"
        ((FAIL++))
    fi
}

# Test health check endpoint
test_endpoint "Health Check" "$BASE_URL/health/"

# Test API root (adjust based on your actual endpoints)
test_endpoint "API Root" "$BASE_URL/api/" "200"

# Test admin page loads
test_endpoint "Admin Login Page" "$BASE_URL/admin/login/" "200"

# Test SSL certificate
echo ""
printf "%-40s" "Testing SSL Certificate..."
if curl -s --head "$BASE_URL" 2>/dev/null | grep -q "HTTP/2 200\|HTTP/1.1 200"; then
    ssl_expiry=$(echo | openssl s_client -servername "$DOMAIN" -connect "$DOMAIN:443" 2>/dev/null | openssl x509 -noout -dates 2>/dev/null | grep notAfter | cut -d= -f2)
    echo "✓ PASS (Expires: $ssl_expiry)"
    ((PASS++))
else
    echo "✗ FAIL (Could not verify SSL)"
    ((FAIL++))
fi

# Test WebSocket endpoint (basic connectivity)
echo ""
printf "%-40s" "Testing WebSocket Upgrade..."
ws_response=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Connection: Upgrade" \
    -H "Upgrade: websocket" \
    -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
    -H "Sec-WebSocket-Version: 13" \
    "$BASE_URL/" --max-time 10 2>/dev/null || echo "000")

# WebSocket upgrade should return 101 or 400 (if path doesn't exist)
if [ "$ws_response" = "101" ] || [ "$ws_response" = "400" ] || [ "$ws_response" = "200" ]; then
    echo "✓ PASS (Server supports WebSocket headers)"
    ((PASS++))
else
    echo "? WARN (HTTP $ws_response - verify WebSocket manually)"
fi

# Check Docker containers are running
echo ""
echo "=== Docker Container Status ==="
if command -v docker &> /dev/null; then
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "(Docker not accessible from this context)"
else
    echo "(Docker command not available)"
fi

# Summary
echo ""
echo "=== Verification Summary ==="
echo "Passed: $PASS"
echo "Failed: $FAIL"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "✓ All tests passed! Deployment looks healthy."
    exit 0
else
    echo "✗ Some tests failed. Please investigate."
    exit 1
fi
