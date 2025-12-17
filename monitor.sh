#!/bin/bash
# Quick monitoring script for News Aggregator

echo "======================================"
echo "News Aggregator Monitoring Dashboard"
echo "======================================"
echo ""

# Check if container is running
echo "📦 Container Status:"
docker-compose -f docker-compose.prod.yml ps
echo ""

# Check configuration
echo "⚙️  Configuration:"
docker-compose -f docker-compose.prod.yml exec -T news-aggregator python -c "
from config import SEND_TO_API, API_BASE_URL, API_SUBMIT_ENDPOINT
print(f'  Backend URL: {API_BASE_URL}')
print(f'  API Endpoint: {API_SUBMIT_ENDPOINT}')
print(f'  Send to API: {SEND_TO_API}')
" 2>/dev/null || echo "  ⚠️  Container not running"
echo ""

# Count articles
echo "📊 Article Statistics:"
if [ -f "data/news.json" ]; then
    total=$(cat data/news.json | grep -c '"id":' || echo "0")
    echo "  Total articles stored: $total"
else
    echo "  ⚠️  No data/news.json file found"
fi
echo ""

# Show recent logs
echo "📋 Recent Activity (last 20 lines):"
docker-compose -f docker-compose.prod.yml logs --tail=20 2>/dev/null || echo "  ⚠️  No logs available"
echo ""

# Check for API submissions in logs
echo "✅ Recent API Submissions:"
api_count=$(docker-compose -f docker-compose.prod.yml logs 2>/dev/null | grep -c "→ API" || echo "0")
echo "  Articles sent to backend: $api_count"

if [ "$api_count" -gt 0 ]; then
    echo "  Last 5 submissions:"
    docker-compose -f docker-compose.prod.yml logs 2>/dev/null | grep "→ API" | tail -5
fi
echo ""

# Test backend connectivity
echo "🔌 Testing Backend Connection:"
docker-compose -f docker-compose.prod.yml run --rm news-aggregator python test_backend.py 2>/dev/null || echo "  ⚠️  Cannot run test (container may not be running)"
echo ""

echo "======================================"
echo "Monitoring Complete"
echo "======================================"
