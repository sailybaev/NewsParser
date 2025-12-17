"""
News Aggregator Service
Fetches news from Kazakh websites, filters by keywords, and stores for moderation
"""
import asyncio
import httpx
import os
import re
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from config import (
    SOURCES, KEYWORDS_KZ, KEYWORDS_RU, CATEGORY_MAPPING,
    DATA_DIR, NEWS_FILE, SEEN_URLS_FILE, MAX_ARTICLES_PER_SOURCE,
    PROXY_URL, API_BASE_URL, API_SUBMIT_ENDPOINT, SEND_TO_API
)
from models import NewsArticle, NewsStorage, SeenURLsTracker
from parsers import get_parser


class NewsAggregator:
    """Main news aggregation service"""
    
    def __init__(self):
        # Ensure data directory exists
        os.makedirs(DATA_DIR, exist_ok=True)
        
        # Initialize storage
        self.storage = NewsStorage(os.path.join(DATA_DIR, NEWS_FILE))
        self.seen_urls = SeenURLsTracker(os.path.join(DATA_DIR, SEEN_URLS_FILE))
        
        # Compile keyword patterns for faster matching
        self.kz_patterns = self._compile_patterns(KEYWORDS_KZ)
        self.ru_patterns = self._compile_patterns(KEYWORDS_RU)
    
    def _compile_patterns(self, keywords: List[str]) -> List[Tuple[re.Pattern, str]]:
        """Compile keyword patterns for case-insensitive matching"""
        patterns = []
        for kw in keywords:
            # Create pattern that matches the keyword as a whole word
            pattern = re.compile(rf'\b{re.escape(kw)}\b', re.IGNORECASE | re.UNICODE)
            patterns.append((pattern, kw))
        return patterns
    
    def detect_language(self, text: str) -> str:
        """Detect if text is primarily Kazakh or Russian"""
        if not text:
            return "unknown"
        
        # Kazakh-specific letters
        kz_chars = set('әіңғүұқөһ')
        # Russian-specific patterns (letters not used much in Kazakh transliteration)
        ru_indicators = ['ы', 'э', 'ё', 'щ']
        
        text_lower = text.lower()
        
        # Check for Kazakh-specific characters
        kz_count = sum(1 for c in text_lower if c in kz_chars)
        ru_count = sum(text_lower.count(c) for c in ru_indicators)
        
        if kz_count > ru_count:
            return "kz"
        elif ru_count > kz_count:
            return "ru"
        else:
            # Default based on character frequency analysis
            # Kazakh uses certain letter combinations more
            if 'қ' in text_lower or 'ң' in text_lower or 'ү' in text_lower:
                return "kz"
            return "ru"
    
    def match_keywords(self, text: str) -> List[str]:
        """Find all matching keywords in text"""
        if not text:
            return []
        
        matches = set()
        
        # Check Kazakh keywords
        for pattern, keyword in self.kz_patterns:
            if pattern.search(text):
                matches.add(keyword)
        
        # Check Russian keywords
        for pattern, keyword in self.ru_patterns:
            if pattern.search(text):
                matches.add(keyword)
        
        return list(matches)
    
    def determine_category(self, text: str, matched_keywords: List[str]) -> str:
        """Determine article category based on content and matched keywords"""
        if not text and not matched_keywords:
            return "general"
        
        combined_text = text.lower() + ' ' + ' '.join(matched_keywords).lower()
        
        category_scores = {}
        for category, keywords in CATEGORY_MAPPING.items():
            score = sum(1 for kw in keywords if kw.lower() in combined_text)
            if score > 0:
                category_scores[category] = score
        
        if category_scores:
            return max(category_scores, key=category_scores.get)
        return "general"
    
    def create_description(self, content: str, max_length: int = 200) -> str:
        """Create a description from content if not provided"""
        if not content:
            return ""
        
        # Clean up whitespace
        content = ' '.join(content.split())
        
        if len(content) <= max_length:
            return content
        
        # Try to cut at sentence boundary
        truncated = content[:max_length]
        last_period = truncated.rfind('.')
        last_question = truncated.rfind('?')
        last_exclaim = truncated.rfind('!')
        
        cut_point = max(last_period, last_question, last_exclaim)
        if cut_point > max_length // 2:
            return truncated[:cut_point + 1]
        
        # Cut at word boundary
        last_space = truncated.rfind(' ')
        if last_space > max_length // 2:
            return truncated[:last_space] + '...'
        
        return truncated + '...'

    async def send_to_api(self, article: NewsArticle, client: httpx.AsyncClient) -> bool:
        """Send article to backend API"""
        if not SEND_TO_API:
            return False

        try:
            url = f"{API_BASE_URL}{API_SUBMIT_ENDPOINT}"

            # Prepare payload matching NewsSubmit schema
            payload = {
                "title_kz": article.title_kz,
                "title_ru": article.title_ru,
                "description_kz": article.description_kz,
                "description_ru": article.description_ru,
                "content_text_kz": article.content_text_kz,
                "content_text_ru": article.content_text_ru,
                "source_url": article.source_url,
                "source_name": article.source_name,
                "language": article.language,
                "category": article.category,
                "keywords_matched": ', '.join(article.matched_keywords) if article.matched_keywords else "",
                "photo_url": article.photo_url
            }

            # Log the attempt to send to backend
            print(f"  📤 Sending to backend API: {url}")
            print(f"     Title: {article.title[:60]}...")
            print(f"     Source: {article.source_name}")
            print(f"     Category: {article.category} | Language: {article.language}")
            
            response = await client.post(url, json=payload, timeout=10.0)

            if response.status_code == 201:
                print(f"  ✅ Successfully sent to backend (Status: 201 Created)")
                return True
            elif response.status_code == 409:
                print(f"  ℹ️  Article already exists in backend (Status: 409 Conflict)")
                return False
            else:
                print(f"  ⚠️  Backend returned status {response.status_code}")
                print(f"     Response: {response.text[:150]}")
                return False

        except httpx.ConnectError as e:
            print(f"  ❌ Connection error sending to API: Cannot reach {API_BASE_URL}")
            print(f"     Error: {e}")
            return False
        except httpx.TimeoutException:
            print(f"  ❌ Timeout sending to API: Backend did not respond within 10 seconds")
            return False
        except Exception as e:
            print(f"  ❌ Unexpected error sending to API: {type(e).__name__}: {e}")
            return False

    async def fetch_source(self, source: dict, client: httpx.AsyncClient) -> List[NewsArticle]:
        """Fetch and process news from a single source"""
        source_name = source['name']
        source_url = source['url']
        source_lang = source.get('lang', 'unknown')
        
        print(f"\n📰 Processing: {source_name}")
        
        articles = []
        parser = get_parser(source_name, source_url)
        
        try:
            # Get article links
            links = await parser.get_article_links(client)
            print(f"  Found {len(links)} potential articles")
            
            # Filter out already seen URLs
            new_links = [url for url in links if not self.seen_urls.is_seen(url)]
            print(f"  {len(new_links)} new articles to process")
            
            # Limit articles per source
            new_links = new_links[:MAX_ARTICLES_PER_SOURCE]
            
            # Process each article
            for url in new_links:
                try:
                    data = await parser.parse_article(url, client)
                    if not data:
                        print(f"  ⚠️  Failed to parse: {url}")
                        continue
                    
                    title = data.get('title', '')
                    content = data.get('content', '')
                    
                    if not title:
                        print(f"  ⚠️  No title found: {url}")
                        continue
                    
                    # Combine text for keyword matching
                    full_text = f"{title} {data.get('description', '')} {content}"
                    
                    # Match keywords
                    matched_keywords = self.match_keywords(full_text)
                    
                    # TEMPORARY: Accept all articles for testing (remove keyword filter)
                    if not matched_keywords:
                        matched_keywords = ["test"]  # Add dummy keyword for testing
                        print(f"  ⚠️  No keywords matched, accepting anyway (TEST MODE): {title[:60]}...")
                    else:
                        print(f"  ✨ Keywords matched: {', '.join(matched_keywords[:3])}...")
                    
                    # Detect language
                    lang = self.detect_language(full_text) or source_lang
                    
                    # Determine category
                    category = self.determine_category(full_text, matched_keywords)
                    
                    # Create description if not present
                    description = data.get('description', '') or self.create_description(content)
                    
                    # Parse date
                    date_str = data.get('date', '')
                    if date_str:
                        try:
                            # Try to parse and normalize date
                            parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            date_str = parsed_date.isoformat()
                        except:
                            date_str = datetime.now().isoformat()
                    else:
                        date_str = datetime.now().isoformat()
                    
                    # Create article object
                    article = NewsArticle(
                        title=title,
                        description=description,
                        content_text=content,
                        photo_url=data.get('image', ''),
                        category=category,
                        date=date_str,
                        source_url=url,
                        source_name=source_name,
                        language=lang,
                        matched_keywords=matched_keywords,
                        status='pending'
                    )
                    
                    # Fill language-specific fields
                    if lang == 'kz':
                        article.title_kz = title
                        article.description_kz = description
                        article.content_text_kz = content
                    elif lang == 'ru':
                        article.title_ru = title
                        article.description_ru = description
                        article.content_text_ru = content
                    
                    # Send to API if enabled
                    if SEND_TO_API:
                        print(f"\n  📝 Article processed: {title[:60]}...")
                        print(f"     Category: [{category}] | Keywords: {len(matched_keywords)} | Language: {lang}")
                        api_success = await self.send_to_api(article, client)
                    else:
                        api_success = False
                        print(f"  ✓ {title[:50]}... [{category}] ({len(matched_keywords)} keywords) → JSON only (API disabled)")

                    # Always save to JSON as backup
                    articles.append(article)
                    self.seen_urls.mark_seen(url)
                    
                except Exception as e:
                    print(f"  ✗ Error processing {url}: {e}")
                    continue
                
                # Small delay between articles
                await asyncio.sleep(0.5)
        
        except Exception as e:
            print(f"  ✗ Error with source {source_name}: {e}")
        
        return articles
    
    async def run(self, sources: List[dict] = None) -> dict:
        """Run the aggregator for all or specified sources"""
        sources = sources or SOURCES
        
        print("=" * 60)
        print(f"🚀 News Aggregator Started at {datetime.now().isoformat()}")
        print(f"   Sources: {len(sources)}")
        print(f"   Keywords: {len(KEYWORDS_KZ)} KZ, {len(KEYWORDS_RU)} RU")
        print("=" * 60)
        
        all_articles = []
        
        async with httpx.AsyncClient(proxy=PROXY_URL) as client:
            for source in sources:
                articles = await self.fetch_source(source, client)
                all_articles.extend(articles)
                
                # Delay between sources
                await asyncio.sleep(1)
        
        # Save new articles
        if all_articles:
            self.storage.add_many(all_articles)
        
        # Summary
        counts = self.storage.count()
        
        print("\n" + "=" * 60)
        print("📊 Summary:")
        print(f"   New articles found: {len(all_articles)}")
        print(f"   Total in storage: {counts['total']}")
        print(f"   Pending moderation: {counts['pending']}")
        print(f"   Approved: {counts['approved']}")
        print(f"   Rejected: {counts['rejected']}")
        print("=" * 60)
        
        return {
            'new_articles': len(all_articles),
            'total': counts['total'],
            'pending': counts['pending'],
            'approved': counts['approved'],
            'rejected': counts['rejected'],
        }
    
    async def run_single_source(self, source_name: str) -> dict:
        """Run aggregator for a single source by name"""
        source = next((s for s in SOURCES if s['name'] == source_name), None)
        if not source:
            print(f"Source '{source_name}' not found")
            return {'error': 'Source not found'}
        
        return await self.run([source])
    
    def get_pending_articles(self) -> List[NewsArticle]:
        """Get all articles pending moderation"""
        return self.storage.get_by_status('pending')
    
    def approve_article(self, article_id: int) -> bool:
        """Approve an article"""
        return self.storage.update_status(article_id, 'approved')
    
    def reject_article(self, article_id: int) -> bool:
        """Reject an article"""
        return self.storage.update_status(article_id, 'rejected')
    
    def get_approved_for_crm(self) -> List[dict]:
        """Get approved articles in CRM format"""
        articles = self.storage.get_by_status('approved')
        return [a.to_crm_format() for a in articles]


# CLI interface
async def main():
    """Main entry point"""
    import sys
    
    aggregator = NewsAggregator()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'fetch':
            # Fetch all sources
            await aggregator.run()
        
        elif command == 'fetch-source' and len(sys.argv) > 2:
            # Fetch single source
            source_name = sys.argv[2]
            await aggregator.run_single_source(source_name)
        
        elif command == 'pending':
            # List pending articles
            pending = aggregator.get_pending_articles()
            print(f"\n📋 Pending Articles ({len(pending)}):\n")
            for a in pending:
                print(f"  [{a.id}] {a.title[:60]}...")
                print(f"      Source: {a.source_name} | Category: {a.category}")
                print(f"      Keywords: {', '.join(a.matched_keywords[:5])}")
                print()
        
        elif command == 'approve' and len(sys.argv) > 2:
            # Approve article
            article_id = int(sys.argv[2])
            if aggregator.approve_article(article_id):
                print(f"✓ Article {article_id} approved")
            else:
                print(f"✗ Article {article_id} not found")
        
        elif command == 'reject' and len(sys.argv) > 2:
            # Reject article
            article_id = int(sys.argv[2])
            if aggregator.reject_article(article_id):
                print(f"✓ Article {article_id} rejected")
            else:
                print(f"✗ Article {article_id} not found")
        
        elif command == 'export-crm':
            # Export approved articles in CRM format
            import json
            articles = aggregator.get_approved_for_crm()
            output_file = os.path.join(DATA_DIR, 'crm_export.json')
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(articles, f, ensure_ascii=False, indent=2)
            print(f"✓ Exported {len(articles)} articles to {output_file}")
        
        elif command == 'stats':
            # Show statistics
            counts = aggregator.storage.count()
            print("\n📊 Storage Statistics:")
            print(f"   Total articles: {counts['total']}")
            print(f"   Pending: {counts['pending']}")
            print(f"   Approved: {counts['approved']}")
            print(f"   Rejected: {counts['rejected']}")
        
        else:
            print("Usage:")
            print("  python aggregator.py fetch              - Fetch from all sources")
            print("  python aggregator.py fetch-source NAME  - Fetch from specific source")
            print("  python aggregator.py pending            - List pending articles")
            print("  python aggregator.py approve ID         - Approve article")
            print("  python aggregator.py reject ID          - Reject article")
            print("  python aggregator.py export-crm         - Export approved to CRM format")
            print("  python aggregator.py stats              - Show statistics")
    else:
        # Default: fetch all
        await aggregator.run()


if __name__ == '__main__':
    asyncio.run(main())
