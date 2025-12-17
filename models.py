"""
Data models for the news aggregator
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List
import json


@dataclass
class NewsArticle:
    """News article model matching CRM structure"""
    # Main fields (will use detected language)
    title: str = ""
    description: str = ""
    content_text: str = ""
    
    # Kazakh fields
    title_kz: str = ""
    description_kz: str = ""
    content_text_kz: str = ""
    
    # Russian fields
    title_ru: str = ""
    description_ru: str = ""
    content_text_ru: str = ""
    
    # Metadata
    photo_url: str = ""
    category: str = ""
    date: str = ""
    
    # Extended fields (for your service)
    source_url: str = ""
    source_name: str = ""
    language: str = ""  # "kz" or "ru"
    matched_keywords: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, approved, rejected
    
    # Auto-generated
    id: Optional[int] = None
    fetched_at: str = ""
    
    def __post_init__(self):
        if not self.fetched_at:
            self.fetched_at = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'NewsArticle':
        """Create from dictionary"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def to_crm_format(self) -> dict:
        """Convert to CRM-compatible format"""
        return {
            "title": self.title,
            "description": self.description,
            "content_text": self.content_text,
            "title_kz": self.title_kz,
            "description_kz": self.description_kz,
            "content_text_kz": self.content_text_kz,
            "title_ru": self.title_ru,
            "description_ru": self.description_ru,
            "content_text_ru": self.content_text_ru,
            "photo_url": self.photo_url,
            "category": self.category,
            "date": self.date,
            "id": self.id,
        }


class NewsStorage:
    """Simple JSON-based storage for news articles"""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self._load()
    
    def _load(self):
        """Load existing data from file"""
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.articles = [NewsArticle.from_dict(a) for a in data.get('articles', [])]
                self._next_id = data.get('next_id', 1)
        except FileNotFoundError:
            self.articles = []
            self._next_id = 1
    
    def save(self):
        """Save data to file"""
        data = {
            'articles': [a.to_dict() for a in self.articles],
            'next_id': self._next_id,
            'last_updated': datetime.now().isoformat(),
        }
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add(self, article: NewsArticle) -> NewsArticle:
        """Add a new article"""
        article.id = self._next_id
        self._next_id += 1
        self.articles.append(article)
        self.save()
        return article
    
    def add_many(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Add multiple articles"""
        for article in articles:
            article.id = self._next_id
            self._next_id += 1
            self.articles.append(article)
        self.save()
        return articles
    
    def get_all(self) -> List[NewsArticle]:
        """Get all articles"""
        return self.articles
    
    def get_by_status(self, status: str) -> List[NewsArticle]:
        """Get articles by status"""
        return [a for a in self.articles if a.status == status]
    
    def get_by_id(self, article_id: int) -> Optional[NewsArticle]:
        """Get article by ID"""
        for a in self.articles:
            if a.id == article_id:
                return a
        return None
    
    def update_status(self, article_id: int, status: str) -> bool:
        """Update article status"""
        for a in self.articles:
            if a.id == article_id:
                a.status = status
                self.save()
                return True
        return False
    
    def count(self) -> dict:
        """Get article counts by status"""
        counts = {'total': len(self.articles), 'pending': 0, 'approved': 0, 'rejected': 0}
        for a in self.articles:
            if a.status in counts:
                counts[a.status] += 1
        return counts


class SeenURLsTracker:
    """Track already processed URLs to avoid duplicates"""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self._load()
    
    def _load(self):
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                self.urls = set(json.load(f))
        except FileNotFoundError:
            self.urls = set()
    
    def save(self):
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(list(self.urls), f, ensure_ascii=False, indent=2)
    
    def is_seen(self, url: str) -> bool:
        return url in self.urls
    
    def mark_seen(self, url: str):
        self.urls.add(url)
        self.save()
    
    def mark_many_seen(self, urls: List[str]):
        self.urls.update(urls)
        self.save()
