# Kazakhstan Youth News Aggregator

Automated service for collecting news from Kazakh news websites, specifically targeting content relevant to youth in Қарағанды облысы (Karaganda Region).

## Quick Start

### Development

```bash
# Using Docker (recommended)
docker-compose up -d
docker-compose logs -f

# Using Python virtual environment
source .venv/bin/activate
python scheduler.py
```

### Production

```bash
# Deploy with 20-hour fetch interval
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Stop service
docker-compose -f docker-compose.prod.yml down

# Restart after updates
docker-compose -f docker-compose.prod.yml up -d --build
```

## Backend Integration

The aggregator automatically sends fetched articles to your backend API (Tabys).

### Configuration

1. **Copy environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Edit .env with your settings:**
   ```bash
   API_BASE_URL=https://soft09.tech
   API_SUBMIT_ENDPOINT=/api/v2/parser/news/submit
   SEND_TO_API=true
   ```

3. **Test backend connectivity:**
   ```bash
   # Using Python directly
   python test_backend.py

   # Using Docker
   docker-compose -f docker-compose.prod.yml run --rm news-aggregator python test_backend.py
   ```

### How to Check if Articles Are Being Sent to Backend

**Method 1: Watch aggregator logs in real-time**
```bash
# Look for "→ API" suffix on article lines
docker-compose -f docker-compose.prod.yml logs -f

# Example successful output:
#   ✓ Жастар бағдарламасы туралы... [education] (12 keywords) → API
#   ✓ Студенттерге грант... [education] (8 keywords) → API
```

**Method 2: Check backend (Tabys) logs**
```bash
cd ../Tabys
docker-compose logs -f api

# Look for POST requests to /api/v2/parser/news/submit
# Status 201 = article created successfully
# Status 409 = article already exists (duplicate)
```

**Method 3: Check backend database**
```bash
# Access backend database to see received articles
cd ../Tabys
docker-compose exec postgres psql -U <username> -d <database>

# Query news articles table
SELECT id, title_kz, source_name, created_at
FROM news_articles
ORDER BY created_at DESC
LIMIT 10;
```

**Method 4: Monitor aggregator data file**
```bash
# Check locally saved articles
cat data/news.json | grep "source_name" | wc -l

# Watch file changes
watch -n 10 "ls -lh data/news.json"
```

### Backend Communication Statuses

The aggregator logs show these statuses when sending to backend:

- `✓ ... → API` - Successfully sent to backend (201 Created)
- `ℹ Article already exists in backend` - Duplicate article (409 Conflict)
- `⚠ API returned status XXX` - Unexpected response from backend
- `✗ Error sending to API` - Connection or network error

### Troubleshooting Backend Integration

**Problem: No "→ API" in logs**

Check if API submission is enabled:
```bash
docker-compose -f docker-compose.prod.yml exec news-aggregator python -c "from config import SEND_TO_API; print(f'SEND_TO_API: {SEND_TO_API}')"
```

If False, set in .env:
```bash
SEND_TO_API=true
```

**Problem: Connection errors**

1. Verify backend is running:
   ```bash
   curl https://soft09.tech/docs
   ```

2. Test connectivity from aggregator:
   ```bash
   docker-compose -f docker-compose.prod.yml run --rm news-aggregator python test_backend.py
   ```

3. Check network connectivity:
   ```bash
   docker-compose -f docker-compose.prod.yml exec news-aggregator ping soft09.tech -c 3
   ```

**Problem: Articles rejected by backend (422/401)**

- Check if backend requires authentication
- Verify payload matches backend schema
- Review backend API documentation at `/docs`

## Production Deployment

The production configuration (`docker-compose.prod.yml`) is optimized for:
- **20-hour fetch interval** (1200 minutes) - reduces server load and respects source websites
- **Backend API integration** - automatically sends articles to Tabys
- **Automatic restart** - ensures service resilience
- **Log rotation** - prevents disk space issues (max 10MB per file, 3 files)
- **Health monitoring** - automatic health checks every hour

### Custom Fetch Interval

To change the fetch interval in production:

**Option 1: Edit docker-compose.prod.yml**
```yaml
command: python scheduler.py <MINUTES>
```
Examples:
- 12 hours: `command: python scheduler.py 720`
- 24 hours: `command: python scheduler.py 1440`
- 6 hours: `command: python scheduler.py 360`

**Option 2: Override command at runtime**
```bash
docker-compose -f docker-compose.prod.yml run -d \
  --name kz-news-aggregator-prod \
  news-aggregator python scheduler.py 720
```

### Manual Operations in Production

```bash
# Run one-time fetch
docker-compose -f docker-compose.prod.yml run --rm news-aggregator python aggregator.py fetch

# Check pending articles
docker-compose -f docker-compose.prod.yml run --rm news-aggregator python aggregator.py pending

# Approve/reject articles
docker-compose -f docker-compose.prod.yml run --rm news-aggregator python aggregator.py approve 123
docker-compose -f docker-compose.prod.yml run --rm news-aggregator python aggregator.py reject 456

# View statistics
docker-compose -f docker-compose.prod.yml run --rm news-aggregator python aggregator.py stats

# Export approved articles
docker-compose -f docker-compose.prod.yml run --rm news-aggregator python aggregator.py export-crm

# Access container shell
docker-compose -f docker-compose.prod.yml exec news-aggregator /bin/bash
```

## Available Commands

### Development Commands

```bash
# Activate virtual environment first
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate  # Windows

# Fetch news from all sources
python aggregator.py fetch

# Fetch from a single source
python aggregator.py fetch-source "Stan.kz"

# View pending articles
python aggregator.py pending

# Approve/reject articles by ID
python aggregator.py approve 123
python aggregator.py reject 123

# Show statistics
python aggregator.py stats

# Export approved articles for CRM
python aggregator.py export-crm

# Run scheduler
python scheduler.py              # default 30-minute interval
python scheduler.py 1200         # 20-hour interval
```

### Docker Commands

```bash
# Development (30-minute interval)
docker-compose up -d
docker-compose logs -f
docker-compose down

# Production (20-hour interval)
docker-compose -f docker-compose.prod.yml up -d
docker-compose -f docker-compose.prod.yml logs -f
docker-compose -f docker-compose.prod.yml down

# Rebuild after code changes
docker-compose -f docker-compose.prod.yml up -d --build

# Run commands inside container
docker-compose -f docker-compose.prod.yml run --rm news-aggregator <command>

# Test backend connectivity
docker-compose -f docker-compose.prod.yml run --rm news-aggregator python test_backend.py
```

## Monitoring Quick Reference

### Check if articles are being sent to backend

```bash
# 1. Watch live logs for "→ API" indicator
docker-compose -f docker-compose.prod.yml logs -f | grep "→ API"

# 2. Test backend connection
docker-compose -f docker-compose.prod.yml run --rm news-aggregator python test_backend.py

# 3. Check if SEND_TO_API is enabled
docker-compose -f docker-compose.prod.yml exec news-aggregator python -c "from config import SEND_TO_API, API_BASE_URL; print(f'Backend: {API_BASE_URL}'); print(f'Enabled: {SEND_TO_API}')"

# 4. View last 50 log lines
docker-compose -f docker-compose.prod.yml logs --tail=50

# 5. Count articles in local storage
docker-compose -f docker-compose.prod.yml exec news-aggregator sh -c "cat data/news.json | grep '\"id\":' | wc -l"
```

### Check backend received the articles

```bash
# Option 1: Check backend logs for POST requests
cd ../Tabys && docker-compose logs api | grep "POST /api/v2/parser/news/submit"

# Option 2: Query backend database
cd ../Tabys && docker-compose exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT COUNT(*) FROM news_articles;"

# Option 3: Check backend API directly
curl -X GET https://soft09.tech/api/v2/parser/news | jq '.[] | {title_kz, source_name}'
```

## Configuration

### Fetch Interval

The scheduler accepts an interval in minutes:
- **Development**: 30 minutes (default in `docker-compose.yml`)
- **Production**: 1200 minutes / 20 hours (in `docker-compose.prod.yml`)

### News Sources

Configured in `config.py` - currently fetching from 18 Kazakh news sources including:
- Stan.kz, Baq.kz, InformBuro, QazSport TV
- Ministry of Health, Test Center, QazTourism
- Orda.kz, Sputnik KZ, Akorda, Azattyq
- And more...

### Keywords & Categories

The system filters articles using 60-80 keywords in Kazakh and Russian, categorizing them into:
- Education, Employment, Business, Finance
- Sports, Culture, Tourism, Social
- IT, Health, Regional news

## Data Persistence

All data is stored in the `./data` directory which is mounted as a Docker volume:
- `data/news.json` - All fetched articles
- `data/seen_urls.json` - Processed URL tracking
- `data/crm_export.json` - CRM export file

This directory persists even when containers are removed.

## Monitoring

### Check Service Status

```bash
# Docker status
docker-compose -f docker-compose.prod.yml ps

# Container health
docker inspect --format='{{.State.Health.Status}}' kz-news-aggregator-prod

# Recent logs
docker-compose -f docker-compose.prod.yml logs --tail=100
```

### Health Checks

The production setup includes automatic health checks:
- Runs every hour
- Verifies that `news.json` file exists
- Automatically restarts if unhealthy after 3 retries

## Troubleshooting

### Service not starting

```bash
# Check logs for errors
docker-compose -f docker-compose.prod.yml logs

# Rebuild image
docker-compose -f docker-compose.prod.yml up -d --build --force-recreate
```

### No articles being fetched

```bash
# Run manual fetch to see errors
docker-compose -f docker-compose.prod.yml run --rm news-aggregator python aggregator.py fetch

# Check if data directory is writable
docker-compose -f docker-compose.prod.yml exec news-aggregator ls -la /app/data
```

### Clear and restart

```bash
# Stop and remove container
docker-compose -f docker-compose.prod.yml down

# Optional: Clear data (WARNING: deletes all fetched news)
# rm -rf data/*

# Restart
docker-compose -f docker-compose.prod.yml up -d
```

## Tech Stack

- **Python**: 3.9
- **HTTP Client**: httpx (async)
- **Web Scraping**: trafilatura, BeautifulSoup4
- **Scheduling**: APScheduler
- **Storage**: JSON files
- **Containerization**: Docker, Docker Compose

## Adding New Sources

1. Edit `config.py` and add to SOURCES list
2. (Optional) Create custom parser in `parsers.py`
3. Test: `python aggregator.py fetch-source "NewSourceName"`
4. Rebuild Docker image if in production

## Integration with CRM

Approved articles can be exported in CRM format:

```bash
# Export to data/crm_export.json
docker-compose -f docker-compose.prod.yml run --rm news-aggregator python aggregator.py export-crm
```

The CRM system can then import this file via the Tabys API endpoint configured in `config.py`.
