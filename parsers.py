"""
News parsers for different websites
"""
import re
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse
from datetime import datetime
import trafilatura
from config import USER_AGENT, FETCH_TIMEOUT


class BaseParser:
    """Base parser with common functionality"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'kk-KZ,kk;q=0.9,ru-RU;q=0.8,ru;q=0.7,en-US;q=0.6,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
    
    async def fetch_page(self, url: str, client: httpx.AsyncClient) -> Optional[str]:
        """Fetch a page and return HTML"""
        try:
            response = await client.get(url, headers=self.headers, timeout=FETCH_TIMEOUT, follow_redirects=True)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def extract_with_trafilatura(self, html: str, url: str) -> Dict:
        """Use trafilatura for generic article extraction"""
        try:
            # Try to extract metadata separately
            metadata = trafilatura.extract_metadata(html, default_url=url)
            text_content = trafilatura.extract(html, url=url, include_comments=False, include_tables=False)
            
            if text_content or metadata:
                title = metadata.title if metadata and metadata.title else ''
                description = metadata.description if metadata and metadata.description else ''
                date = metadata.date if metadata and metadata.date else ''
                
                # Fallback: try to get title from HTML if missing
                if not title and html:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, 'lxml')
                    title_tag = soup.find('title') or soup.find('h1')
                    if title_tag:
                        title = title_tag.get_text().strip()
                
                return {
                    'title': title,
                    'description': description or (text_content[:200] + '...' if text_content else ''),
                    'content': text_content or '',
                    'date': date,
                    'image': '',
                }
        except Exception as e:
            print(f"Trafilatura error for {url[:50]}: {e}")
        return {}
    
    def find_article_links(self, html: str, base_url: str, patterns: List[str] = None) -> List[str]:
        """Find article links on a page"""
        soup = BeautifulSoup(html, 'lxml')
        links = set()
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = urljoin(base_url, href)
            
            # Basic filtering
            parsed = urlparse(full_url)
            if not parsed.scheme.startswith('http'):
                continue
            
            # Skip non-article links
            skip_patterns = [
                '/tag/', '/category/', '/author/', '/page/', 
                '/login', '/register', '/search', '/rss',
                '.jpg', '.png', '.pdf', '.mp3', '.mp4',
                'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com',
                'telegram.me', 't.me', 'wa.me'
            ]
            if any(p in full_url.lower() for p in skip_patterns):
                continue
            
            # Check if matches article patterns
            if patterns:
                if any(re.search(p, full_url) for p in patterns):
                    links.add(full_url)
            else:
                # Generic article detection (has path with multiple segments or numbers/dates)
                path = parsed.path
                if len(path) > 10 and (
                    re.search(r'/\d{4}/', path) or  # Year in path
                    re.search(r'/\d+', path) or      # ID in path
                    re.search(r'-[a-z]+-', path) or  # Slug pattern
                    path.count('/') >= 2             # Multiple path segments
                ):
                    links.add(full_url)
        
        return list(links)


class StanKzParser(BaseParser):
    """Parser for stan.kz"""
    
    async def get_article_links(self, client: httpx.AsyncClient) -> List[str]:
        html = await self.fetch_page('https://stan.kz/', client)
        if not html:
            return []
        return self.find_article_links(html, 'https://stan.kz/', [r'/news/\d+', r'/\d{4}/\d{2}/'])
    
    async def parse_article(self, url: str, client: httpx.AsyncClient) -> Optional[Dict]:
        html = await self.fetch_page(url, client)
        if not html:
            return None
        
        data = self.extract_with_trafilatura(html, url)
        
        # Fallback with BeautifulSoup if needed
        if not data.get('title'):
            soup = BeautifulSoup(html, 'lxml')
            title_el = soup.find('h1') or soup.find('title')
            if title_el:
                data['title'] = title_el.get_text(strip=True)
        
        return data


class BaqKzParser(BaseParser):
    """Parser for baq.kz"""
    
    async def get_article_links(self, client: httpx.AsyncClient) -> List[str]:
        html = await self.fetch_page('https://baq.kz/', client)
        if not html:
            return []
        return self.find_article_links(html, 'https://baq.kz/', [r'/kz/news/', r'/news/'])
    
    async def parse_article(self, url: str, client: httpx.AsyncClient) -> Optional[Dict]:
        html = await self.fetch_page(url, client)
        if not html:
            return None
        return self.extract_with_trafilatura(html, url)


class InformBuroParser(BaseParser):
    """Parser for informburo.kz"""
    
    async def get_article_links(self, client: httpx.AsyncClient) -> List[str]:
        html = await self.fetch_page('https://informburo.kz/', client)
        if not html:
            return []
        return self.find_article_links(html, 'https://informburo.kz/', [r'/novosti/', r'/stati/'])
    
    async def parse_article(self, url: str, client: httpx.AsyncClient) -> Optional[Dict]:
        html = await self.fetch_page(url, client)
        if not html:
            return None
        return self.extract_with_trafilatura(html, url)


class OrdaKzParser(BaseParser):
    """Parser for orda.kz"""
    
    async def get_article_links(self, client: httpx.AsyncClient) -> List[str]:
        urls = []
        for section in ['', 'posts', 'news']:
            html = await self.fetch_page(f'https://orda.kz/{section}', client)
            if html:
                urls.extend(self.find_article_links(html, 'https://orda.kz/', [r'/posts/', r'/\d{4}/']))
        return list(set(urls))
    
    async def parse_article(self, url: str, client: httpx.AsyncClient) -> Optional[Dict]:
        html = await self.fetch_page(url, client)
        if not html:
            return None
        return self.extract_with_trafilatura(html, url)


class SputnikKzParser(BaseParser):
    """Parser for ru.sputnik.kz"""
    
    async def get_article_links(self, client: httpx.AsyncClient) -> List[str]:
        html = await self.fetch_page('https://ru.sputnik.kz/', client)
        if not html:
            return []
        return self.find_article_links(html, 'https://ru.sputnik.kz/', [r'/\d{8}/'])
    
    async def parse_article(self, url: str, client: httpx.AsyncClient) -> Optional[Dict]:
        html = await self.fetch_page(url, client)
        if not html:
            return None
        return self.extract_with_trafilatura(html, url)


class TwentyFourKzParser(BaseParser):
    """Parser for 24.kz"""
    
    async def get_article_links(self, client: httpx.AsyncClient) -> List[str]:
        html = await self.fetch_page('https://24.kz/kz/zha-aly-tar', client)
        if not html:
            return []
        return self.find_article_links(html, 'https://24.kz/', [r'/kz/.*\d+'])
    
    async def parse_article(self, url: str, client: httpx.AsyncClient) -> Optional[Dict]:
        html = await self.fetch_page(url, client)
        if not html:
            return None
        return self.extract_with_trafilatura(html, url)


class ZakonKzParser(BaseParser):
    """Parser for kaz.zakon.kz"""
    
    async def get_article_links(self, client: httpx.AsyncClient) -> List[str]:
        html = await self.fetch_page('https://kaz.zakon.kz/', client)
        if not html:
            return []
        return self.find_article_links(html, 'https://kaz.zakon.kz/', [r'/doc/', r'/news/'])
    
    async def parse_article(self, url: str, client: httpx.AsyncClient) -> Optional[Dict]:
        html = await self.fetch_page(url, client)
        if not html:
            return None
        return self.extract_with_trafilatura(html, url)


class GenericParser(BaseParser):
    """Generic parser for any news site"""
    
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
    
    async def get_article_links(self, client: httpx.AsyncClient) -> List[str]:
        html = await self.fetch_page(self.base_url, client)
        if not html:
            return []
        return self.find_article_links(html, self.base_url)
    
    async def parse_article(self, url: str, client: httpx.AsyncClient) -> Optional[Dict]:
        html = await self.fetch_page(url, client)
        if not html:
            return None
        
        data = self.extract_with_trafilatura(html, url)
        
        # Additional image extraction if trafilatura missed it
        if not data.get('image'):
            soup = BeautifulSoup(html, 'lxml')
            # Try Open Graph image
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                data['image'] = og_image['content']
            else:
                # Try first large image in article
                for img in soup.find_all('img', src=True):
                    src = img['src']
                    if any(x in src.lower() for x in ['thumb', 'icon', 'logo', 'avatar']):
                        continue
                    data['image'] = urljoin(url, src)
                    break
        
        return data


# Parser registry
def get_parser(source_name: str, source_url: str) -> BaseParser:
    """Get appropriate parser for a source"""
    parsers = {
        'Stan.kz': StanKzParser(),
        'Baq.kz': BaqKzParser(),
        'InformBuro': InformBuroParser(),
        'Orda.kz': OrdaKzParser(),
        'Sputnik KZ': SputnikKzParser(),
        '24.kz': TwentyFourKzParser(),
        'Zakon.kz': ZakonKzParser(),
    }
    return parsers.get(source_name, GenericParser(source_url))
