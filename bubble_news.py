#!/usr/bin/env python3
"""
==============================================================================
BUBBLE NEWS — Version 0.1 Beta
==============================================================================
Personal-use, command-line-based news aggregation and AI summarization tool.

Guiding Architecture:
- Python performs mechanical tasks (HTTP, RSS parsing, date filtering, article/image
  extraction, schema validation, HTML email generation, Disroot SMTP delivery).
- Google Gemini performs intellectual tasks (story grouping, cross-source
  deduplication, preserving distinct facts/quotes, summarization, category sorting).
==============================================================================
"""

import argparse
import dataclasses
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
import html
import json
import logging
import os
from pathlib import Path
import re
import smtplib
import ssl
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import urllib.parse
import warnings

# Suppress noisy third-party warnings for clean CLI output
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Third-party styling if available
try:
    import colorama
    from colorama import Fore, Style
    colorama.init(autoreset=True)
except ImportError:
    class Fore:
        GREEN = RED = YELLOW = CYAN = BLUE = MAGENTA = WHITE = RESET = ""
    class Style:
        BRIGHT = NORMAL = RESET_ALL = ""

from bs4 import BeautifulSoup
import dateutil.parser
import feedparser
import requests
import trafilatura

# Core configuration
import config

# Google Gemini SDK (Supports new google.genai and legacy google.generativeai)
USE_NEW_GENAI = False
USE_LEGACY_GENAI = False

try:
    from google import genai as new_genai
    from google.genai import types as new_genai_types
    USE_NEW_GENAI = True
except ImportError:
    new_genai_types = None
    try:
        import google.generativeai as legacy_genai
        USE_LEGACY_GENAI = True
    except ImportError:
        pass

# Browser TLS & HTTP/2 Impersonation via curl_cffi
USE_CURL_CFFI = False
try:
    from curl_cffi import requests as curl_requests
    USE_CURL_CFFI = True
except ImportError:
    curl_requests = None

# ==============================================================================
# CONSTANTS & LOGGING SETUP
# ==============================================================================

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)


def create_browser_session() -> Any:
    """Create an HTTP session using curl_cffi Chrome impersonation (or requests as fallback)."""
    if USE_CURL_CFFI and curl_requests:
        session = curl_requests.Session(impersonate="chrome")
        session.headers.update({
            "Referer": "https://www.google.com/",
            "Accept-Language": "en-US,en;q=0.9",
        })
        return session

    session = requests.Session()
    session.headers.update({
        "User-Agent": DEFAULT_USER_AGENT,
        "Referer": "https://www.google.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Ch-Ua": '"Chromium";v="130", "Google Chrome";v="130"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    })
    return session



# Setup Logger
logger = logging.getLogger("BubbleNews")
logger.setLevel(logging.INFO)
log_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

# File log handler using configured log file path
try:
    file_handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)
except Exception:
    pass


# ==============================================================================
# CONSOLE FORMATTING HELPERS
# ==============================================================================

def print_banner() -> None:
    """Print the Bubble News application banner."""
    print(f"\n{Style.BRIGHT}{Fore.CYAN}==================================================")
    print("               BUBBLE NEWS v0.1 Beta")
    print("      Personal AI News Aggregator & Digest")
    print(f"=================================================={Style.RESET_ALL}\n")


def print_info(msg: str) -> None:
    """Print an info message to stdout and logger."""
    logger.info(msg)
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} {msg}")


def print_ok(msg: str = "") -> None:
    """Print an OK status message to stdout and logger."""
    if msg:
        logger.info(f"OK: {msg}")
        print(f"{Fore.GREEN}[OK]{Style.RESET_ALL} {msg}")
    else:
        logger.info("OK")
        print(f"{Fore.GREEN}[OK]{Style.RESET_ALL}")


def print_warn(msg: str) -> None:
    """Print a warning message to stdout and logger."""
    logger.warning(msg)
    print(f"{Fore.YELLOW}[WARN]{Style.RESET_ALL} {msg}")


def print_error(msg: str) -> None:
    """Print an error message to stderr and logger."""
    logger.error(msg)
    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {msg}", file=sys.stderr)


# ==============================================================================
# DATA MODELS
# ==============================================================================

@dataclasses.dataclass
class RSSArticle:
    """Raw article metadata extracted from an RSS feed entry."""
    title: str
    url: str
    published_at: Optional[datetime.datetime]
    summary: str
    source_name: str
    category: str


@dataclasses.dataclass
class ExtractedArticle:
    """Full article content and extracted media from webpage."""
    title: str
    url: str
    published_at: Optional[datetime.datetime]
    main_text: str
    author: Optional[str]
    featured_image: Optional[str]
    additional_images: List[str]
    source_name: str
    category: str
    extraction_success: bool = True


@dataclasses.dataclass
class StorySource:
    """Source reference for a consolidated story."""
    name: str
    url: str


@dataclasses.dataclass
class ConsolidatedStory:
    """A story consolidated across one or more sources by Gemini."""
    title: str
    summary: str
    key_points: List[str]
    importance: str  # high, medium, low
    sources: List[StorySource]
    images: List[str]


@dataclasses.dataclass
class CategoryDigest:
    """Categorized stories and raw source links for email formatting."""
    name: str
    stories: List[ConsolidatedStory]
    source_links: List[StorySource]


# ==============================================================================
# CONFIGURATION MANAGER
# ==============================================================================

class ConfigManager:
    """
    Manages loading and validating the public RSS feed configuration (bubble_news.json)
    and verifying core configuration parameters.
    """

    def __init__(self, feeds_path: Optional[str] = None):
        self.feeds_path = Path(feeds_path or config.FEEDS_FILE)

    def load_feeds(self) -> Dict[str, List[str]]:
        """
        Load and validate user-defined RSS feeds by category.
        
        Returns:
            Dict mapping category name to list of RSS URLs.
        """
        if not self.feeds_path.exists():
            raise FileNotFoundError(
                f"RSS feeds configuration '{self.feeds_path}' not found. "
                "Please ensure bubble_news.json exists."
            )

        try:
            with open(self.feeds_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Malformed JSON in '{self.feeds_path}': {e}")

        if not isinstance(data, dict):
            raise ValueError(f"Feeds file '{self.feeds_path}' must contain a JSON object (categories to URLs).")

        validated: Dict[str, List[str]] = {}
        for category, urls in data.items():
            if not isinstance(category, str) or not category.strip():
                continue
            cat_name = category.strip()
            if not isinstance(urls, list):
                raise ValueError(f"Category '{category}' in '{self.feeds_path}' must contain a list of URLs.")
            
            clean_urls: List[str] = []
            for u in urls:
                if isinstance(u, str) and u.strip().startswith(("http://", "https://")):
                    clean_urls.append(u.strip())
                elif isinstance(u, str) and u.strip():
                    print_warn(f"Skipping invalid URL in category '{category}': {u}")
            
            if clean_urls:
                validated[cat_name] = clean_urls

        if not validated:
            raise ValueError(f"No valid categories and RSS URLs found in '{self.feeds_path}'.")

        return validated

    @staticmethod
    def is_placeholder(val: str, placeholder_prefix: str = "YOUR_") -> bool:
        """Check if a configuration value is still a placeholder."""
        if not val or not isinstance(val, str):
            return True
        v = val.strip()
        return v.startswith(placeholder_prefix) or "example.com" in v or v == "YOUR_GEMINI_API_KEY" or v == "YOUR_EMAIL_PASSWORD"


# ==============================================================================
# RSS FETCHER & 12-HOUR FILTER
# ==============================================================================

class RSSFetcher:
    """
    Fetches RSS feeds, handles date normalization, and filters articles
    to the defined publication window (default 12 hours).
    """

    def __init__(self, time_window_hours: int = config.TIME_WINDOW_HOURS, user_agent: str = DEFAULT_USER_AGENT):
        self.time_window_hours = time_window_hours
        self.user_agent = user_agent
        self.session = create_browser_session()

    def fetch_all(self, categorized_feeds: Dict[str, List[str]]) -> List[RSSArticle]:
        """
        Fetch all configured RSS feeds across all categories.
        
        Returns:
            List of RSSArticle objects within the publication window.
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        cutoff_utc = now_utc - datetime.timedelta(hours=self.time_window_hours)
        articles: List[RSSArticle] = []
        seen_urls: Set[str] = set()

        for category, urls in categorized_feeds.items():
            cat_articles = 0
            for feed_url in urls:
                try:
                    feed_articles = self._fetch_feed(feed_url, category, cutoff_utc, now_utc, seen_urls)
                    articles.extend(feed_articles)
                    cat_articles += len(feed_articles)
                except Exception as e:
                    print_warn(f"Unable to read RSS feed '{feed_url}': {e}")
            
            print_ok(f"{category}: {cat_articles} article(s) in window")

        return articles

    def _fetch_feed(
        self,
        feed_url: str,
        category: str,
        cutoff_utc: datetime.datetime,
        now_utc: datetime.datetime,
        seen_urls: Set[str]
    ) -> List[RSSArticle]:
        """Fetch a single RSS feed and extract valid articles."""
        content = None
        try:
            response = self.session.get(feed_url, timeout=15)
            if response.status_code == 200:
                content = response.content
            elif response.status_code in (429, 403):
                # Fallback to descriptive feed aggregator User-Agent (required by Phys.org & similar sites)
                alt_resp = requests.get(
                    feed_url,
                    headers={"User-Agent": "BubbleNews/0.1 (+https://github.com/yourname/bubblenews; personal news aggregator)"},
                    timeout=15
                )
                if alt_resp.status_code == 200:
                    content = alt_resp.content
        except Exception:
            pass

        if content is None:
            parsed = feedparser.parse(feed_url)
        else:
            parsed = feedparser.parse(content)

        if parsed.bozo and not parsed.entries:
            raise ValueError(f"Feed parser error or empty feed: {parsed.bozo_exception}")

        source_title = parsed.feed.get("title", urllib.parse.urlparse(feed_url).netloc)
        results: List[RSSArticle] = []

        for entry in parsed.entries:
            link = entry.get("link") or entry.get("id") or ""
            if not link or not link.startswith(("http://", "https://")):
                continue

            clean_url = self._normalize_url(link)
            if clean_url in seen_urls:
                continue

            title = entry.get("title", "Untitled Story").strip()
            summary = entry.get("summary") or entry.get("description") or ""
            # Strip HTML tags from summary if present
            if summary:
                summary = BeautifulSoup(summary, "html.parser").get_text(separator=" ").strip()

            pub_date = self._parse_entry_date(entry)

            # Filter by publication window
            if pub_date is not None:
                # If timestamp is in the future (> 24 hours), adjust to now
                if pub_date > now_utc + datetime.timedelta(hours=24):
                    logger.warning(f"Future timestamp detected ({pub_date}) in {clean_url}, adjusting to current time.")
                    pub_date = now_utc

                if pub_date < cutoff_utc:
                    continue  # Older than configured time window
            else:
                logger.debug(f"Missing publication date for '{title}' ({clean_url})")

            seen_urls.add(clean_url)
            results.append(RSSArticle(
                title=title,
                url=clean_url,
                published_at=pub_date,
                summary=summary,
                source_name=source_title,
                category=category
            ))

        return results

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Strip tracking query parameters like utm_source from URL."""
        parsed = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qsl(parsed.query)
        clean_params = [(k, v) for k, v in query_params if not k.lower().startswith(("utm_", "fbclid", "gclid", "ref"))]
        clean_query = urllib.parse.urlencode(clean_params)
        return urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            clean_query,
            ""  # remove fragment
        ))

    @staticmethod
    def _parse_entry_date(entry: Any) -> Optional[datetime.datetime]:
        """Parse publication date from RSS entry with multi-format fallback."""
        # 1. feedparser struct_time
        for date_field in ["published_parsed", "updated_parsed", "created_parsed"]:
            val = getattr(entry, date_field, None) or entry.get(date_field)
            if val:
                try:
                    return datetime.datetime(*val[:6], tzinfo=datetime.timezone.utc)
                except Exception:
                    pass

        # 2. String date fields
        for date_str_field in ["published", "updated", "pubDate", "dc:date"]:
            val_str = entry.get(date_str_field)
            if val_str and isinstance(val_str, str):
                try:
                    dt = dateutil.parser.parse(val_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=datetime.timezone.utc)
                    else:
                        dt = dt.astimezone(datetime.timezone.utc)
                    return dt
                except Exception:
                    pass

        return None


# ==============================================================================
# ARTICLE & IMAGE EXTRACTOR
# ==============================================================================

class ArticleExtractor:
    """
    Extracts main article text and high-quality images from article web pages
    using Trafilatura and BeautifulSoup.
    """

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT):
        self.user_agent = user_agent
        self.session = create_browser_session()

    def extract_articles(self, rss_articles: List[RSSArticle]) -> List[ExtractedArticle]:
        """
        Extract full content and images for a list of RSS articles.
        
        Returns:
            List of ExtractedArticle objects.
        """
        extracted_list: List[ExtractedArticle] = []
        success_count = 0
        fail_count = 0

        for item in rss_articles:
            try:
                extracted = self._extract_single_article(item)
                if extracted.extraction_success and extracted.main_text:
                    success_count += 1
                else:
                    fail_count += 1
                extracted_list.append(extracted)
            except Exception as e:
                fail_count += 1
                print_warn(f"Unable to extract article ({item.url}): {e}. Using RSS summary.")
                extracted_list.append(ExtractedArticle(
                    title=item.title,
                    url=item.url,
                    published_at=item.published_at,
                    main_text=item.summary or item.title,
                    author=None,
                    featured_image=None,
                    additional_images=[],
                    source_name=item.source_name,
                    category=item.category,
                    extraction_success=False
                ))

        print_ok(f"{success_count} articles extracted")
        if fail_count > 0:
            print_warn(f"{fail_count} article(s) could not be extracted; using RSS description fallback")

        return extracted_list

    def _extract_single_article(self, rss_item: RSSArticle) -> ExtractedArticle:
        """Fetch and extract a single article using browser TLS impersonation."""
        html_content = None
        try:
            response = self.session.get(rss_item.url, timeout=15)
            if response.status_code == 200 and response.text:
                html_content = response.text
            elif response.status_code in (429, 403):
                alt_resp = requests.get(
                    rss_item.url,
                    headers={"User-Agent": "BubbleNews/0.1 (+https://github.com/yourname/bubblenews; personal news aggregator)"},
                    timeout=15
                )
                if alt_resp.status_code == 200 and alt_resp.text:
                    html_content = alt_resp.text
        except Exception:
            pass

        if not html_content:
            html_content = trafilatura.fetch_url(rss_item.url)

        if not html_content:
            raise RuntimeError(f"Could not retrieve HTML content for {rss_item.url}")

        # Extract clean text using Trafilatura
        trafilatura_text = trafilatura.extract(
            html_content,
            include_links=False,
            include_images=False,
            include_tables=False,
            favor_precision=True
        )

        # Parse HTML metadata with BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Extract title (fallback to RSS title)
        title = rss_item.title
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()

        # Extract author
        author = None
        author_meta = (
            soup.find("meta", attrs={"name": "author"}) or
            soup.find("meta", property="article:author") or
            soup.find("meta", attrs={"name": "twitter:creator"})
        )
        if author_meta and author_meta.get("content"):
            author = author_meta["content"].strip()

        # Extract publication date if missing
        published_at = rss_item.published_at
        if published_at is None:
            time_meta = (
                soup.find("meta", property="article:published_time") or
                soup.find("meta", attrs={"name": "pubdate"}) or
                soup.find("meta", attrs={"name": "publishdate"})
            )
            if time_meta and time_meta.get("content"):
                try:
                    dt = dateutil.parser.parse(time_meta["content"])
                    if dt.tzinfo is None:
                        published_at = dt.replace(tzinfo=datetime.timezone.utc)
                    else:
                        published_at = dt.astimezone(datetime.timezone.utc)
                except Exception:
                    pass

        # Extract candidate images
        featured_image, additional_images = self._extract_images(soup, rss_item.url)

        # Validate extracted text
        main_text = trafilatura_text.strip() if trafilatura_text else ""
        if not main_text:
            # Fallback to meta description or RSS summary
            meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", property="og:description")
            if meta_desc and meta_desc.get("content"):
                main_text = meta_desc["content"].strip()
            elif rss_item.summary:
                main_text = rss_item.summary
            else:
                main_text = rss_item.title

        return ExtractedArticle(
            title=title,
            url=rss_item.url,
            published_at=published_at,
            main_text=main_text,
            author=author,
            featured_image=featured_image,
            additional_images=additional_images,
            source_name=rss_item.source_name,
            category=rss_item.category,
            extraction_success=bool(trafilatura_text)
        )

    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> Tuple[Optional[str], List[str]]:
        """Extract Open Graph and article body candidate images."""
        featured_img: Optional[str] = None
        additional_imgs: List[str] = []
        seen_img_urls: Set[str] = set()

        def is_valid_img(img_url: str) -> bool:
            if not img_url or not img_url.startswith(("http://", "https://")):
                return False
            low = img_url.lower()
            bad_keywords = [
                "avatar", "gravatar", "icon", "logo", "tracker", "1x1", "pixel",
                "badge", "button", "spinner", "advertisement", "ad-banner", "emoji"
            ]
            if any(k in low for k in bad_keywords):
                return False
            return any(ext in low for ext in [".jpg", ".jpeg", ".png", ".webp"])

        # 1. OpenGraph & Twitter Image
        for prop in ["og:image", "twitter:image", "image"]:
            tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if tag and tag.get("content"):
                abs_url = urllib.parse.urljoin(base_url, tag["content"].strip())
                if is_valid_img(abs_url) and abs_url not in seen_img_urls:
                    featured_img = abs_url
                    seen_img_urls.add(abs_url)
                    break

        # 2. Body images within <article>, <main>, or content containers
        container = soup.find("article") or soup.find("main") or soup.find("div", class_=re.compile(r"content|body|post|story", re.I))
        if container:
            for img in container.find_all("img"):
                src = img.get("src") or img.get("data-src") or img.get("data-original") or ""
                if src:
                    abs_src = urllib.parse.urljoin(base_url, src.strip())
                    if is_valid_img(abs_src) and abs_src not in seen_img_urls:
                        if featured_img is None:
                            featured_img = abs_src
                        else:
                            additional_imgs.append(abs_src)
                        seen_img_urls.add(abs_src)
                        if len(additional_imgs) >= 3:
                            break

        return featured_img, additional_imgs[:3]


# ==============================================================================
# GEMINI AI CONSOLIDATOR & SUMMARIZER
# ==============================================================================

class GeminiConsolidator:
    """
    Interfaces with Google Gemini SDK to consolidate duplicate/related stories,
    preserve critical differing facts across sources, categorize, and summarize.
    """

    def __init__(self, api_key: str, model_name: str = config.GEMINI_MODEL):
        if not USE_NEW_GENAI and not USE_LEGACY_GENAI:
            raise ImportError(
                "Google GenAI SDK is not installed. Please run 'pip install google-genai'."
            )
        
        self.api_key = api_key
        self.model_name = model_name

        if USE_NEW_GENAI:
            self.client = new_genai.Client(api_key=self.api_key)
        else:
            legacy_genai.configure(api_key=self.api_key)
            self.model = legacy_genai.GenerativeModel(self.model_name)

    def process_and_summarize(
        self,
        articles: List[ExtractedArticle],
        allowed_categories: List[str]
    ) -> List[CategoryDigest]:
        """
        Send extracted articles to Google Gemini for intellectual consolidation and summarization.
        
        Returns:
            List of CategoryDigest objects.
        """
        if not articles:
            return []

        # Prepare structured input payload for Gemini
        input_data = self._prepare_gemini_input(articles)
        prompt = self._build_prompt(input_data, allowed_categories)

        logger.info(f"Sending {len(articles)} articles across {len(allowed_categories)} categories to Gemini ({self.model_name})...")
        
        max_retries = 3
        retry_delay = 3
        raw_text = None
        last_err = None

        for attempt in range(1, max_retries + 1):
            try:
                if USE_NEW_GENAI:
                    gen_config = (
                        new_genai_types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.2,
                        )
                        if new_genai_types
                        else {
                            "response_mime_type": "application/json",
                            "temperature": 0.2,
                        }
                    )
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                        config=gen_config
                    )
                    raw_text = response.text
                else:
                    response = self.model.generate_content(
                        prompt,
                        generation_config={
                            "response_mime_type": "application/json",
                            "temperature": 0.2,
                        }
                    )
                    raw_text = response.text

                if raw_text:
                    break
            except Exception as e:
                last_err = e
                err_str = str(e)
                if ("503" in err_str or "429" in err_str or "UNAVAILABLE" in err_str or "RESOURCE_EXHAUSTED" in err_str) and attempt < max_retries:
                    print_warn(f"Gemini API busy (attempt {attempt}/{max_retries}). Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise RuntimeError(f"Google Gemini API error: {e}")

        if not raw_text:
            raise RuntimeError(f"Google Gemini API error: {last_err or 'Empty response from model'}")


        # Parse and validate JSON
        try:
            ai_output = json.loads(raw_text)
        except json.JSONDecodeError:
            # Attempt recovery from markdown fences if needed
            cleaned = self._clean_json_fences(raw_text)
            ai_output = json.loads(cleaned)

        return self._build_category_digests(ai_output, articles, allowed_categories)

    def _prepare_gemini_input(self, articles: List[ExtractedArticle]) -> List[Dict[str, Any]]:
        """Format articles into concise JSON for AI processing."""
        prepared = []
        for i, a in enumerate(articles, 1):
            max_chars = 3500
            truncated_text = a.main_text[:max_chars] if a.main_text else a.title
            
            candidate_images = []
            if a.featured_image:
                candidate_images.append(a.featured_image)
            candidate_images.extend(a.additional_images)

            prepared.append({
                "id": i,
                "category": a.category,
                "title": a.title,
                "source_name": a.source_name,
                "url": a.url,
                "author": a.author or "",
                "candidate_images": candidate_images[:2],
                "text": truncated_text
            })
        return prepared

    @staticmethod
    def _clean_json_fences(text: str) -> str:
        """Strip markdown code fences from JSON response."""
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text.strip()

    def _build_prompt(self, input_articles: List[Dict[str, Any]], allowed_categories: List[str]) -> str:
        """Construct the prompt enforcing strict consolidation and no fabrication."""
        categories_str = ", ".join(f'"{c}"' for c in allowed_categories)
        json_articles_str = json.dumps(input_articles, indent=2)

        return f"""You are the News Consolidation and Summarization Engine for BUBBLE NEWS.
Your task is to analyze the following raw articles collected from RSS feeds over the past 12 hours, identify related/duplicate stories, consolidate reporting from multiple sources into single unified stories, and produce high-quality, readable summaries.

### STRICT RULES & PRINCIPLES:
1. MECHANICAL vs INTELLECTUAL SEPARATION: Work ONLY with the provided article data. Do NOT search the web or fabricate details.
2. NEVER FABRICATE: Never invent facts, numbers, dates, sources, URLs, or fake quotations. If an article does not state something, do not claim it.
3. STORY CONSOLIDATION & DEDUPLICATION: Multiple sources often report on the exact same underlying event. Combine these sources into ONE consolidated story.
4. PRESERVE MEANINGFUL DIFFERENCES: When combining sources for the same story, preserve unique facts each source provides, while eliminating repetitive fluff.
5. CATEGORIES: Organize the final stories into the user's defined categories: [{categories_str}]. Do NOT invent arbitrary categories like "Trending" or "Miscellaneous". If an article fits better into another allowed category, assign it there.
6. IMAGES: For each story, select 0 or 1 best image URL from the 'candidate_images' of that story's sources. Limit total images in any single category to at most 1 to 3 images. If no candidate image is relevant or available, return an empty image array.
7. SUMMARY QUALITY: Write clear, informative, journalistic summaries (1-3 paragraphs) answering What, Who, Where, When, and Why. Include 2-4 key bullet points highlighting essential numbers or facts.
8. OUTPUT FORMAT: You must return strictly valid JSON matching the exact schema below.

### EXPECTED JSON SCHEMA:
{{
  "categories": [
    {{
      "name": "Tech News",
      "stories": [
        {{
          "title": "Consolidated Headline Representing the Event",
          "summary": "Unified informative summary combining details from all reporting sources...",
          "key_points": [
            "Specific key fact, metric, or outcome",
            "Key reaction, statement, or quote"
          ],
          "importance": "high",
          "sources": [
            {{
              "name": "Reuters",
              "url": "https://..."
            }},
            {{
              "name": "BBC News",
              "url": "https://..."
            }}
          ],
          "images": [
            "https://.../featured.jpg"
          ]
        }}
      ]
    }}
  ]
}}

### RAW ARTICLES TO PROCESS:
{json_articles_str}
"""

    def _build_category_digests(
        self,
        ai_output: Dict[str, Any],
        raw_articles: List[ExtractedArticle],
        allowed_categories: List[str]
    ) -> List[CategoryDigest]:
        """Convert validated AI output into CategoryDigest objects."""
        # Map categories by lowercase for normalized lookup while keeping original display names
        cat_display_map = {c.lower(): c for c in allowed_categories}
        cat_links_map: Dict[str, List[StorySource]] = {c.lower(): [] for c in allowed_categories}
        seen_urls_by_cat: Dict[str, Set[str]] = {c.lower(): set() for c in allowed_categories}

        for art in raw_articles:
            cat_key = art.category.lower()
            if cat_key in cat_links_map and art.url not in seen_urls_by_cat[cat_key]:
                cat_links_map[cat_key].append(StorySource(name=art.source_name, url=art.url))
                seen_urls_by_cat[cat_key].add(art.url)

        digests: List[CategoryDigest] = []
        raw_categories = ai_output.get("categories", [])

        for cat_data in raw_categories:
            raw_cat_name = str(cat_data.get("name", "")).strip()
            cat_key = raw_cat_name.lower()
            if not cat_key:
                continue

            display_name = cat_display_map.get(cat_key, raw_cat_name)

            stories: List[ConsolidatedStory] = []
            for s in cat_data.get("stories", []):
                title = str(s.get("title", "")).strip()
                summary = str(s.get("summary", "")).strip()
                if not title or not summary:
                    continue

                key_points = [str(p).strip() for p in s.get("key_points", []) if str(p).strip()]
                importance = str(s.get("importance", "medium")).strip().lower()
                
                sources: List[StorySource] = []
                for src in s.get("sources", []):
                    s_name = str(src.get("name", "Source")).strip()
                    s_url = str(src.get("url", "")).strip()
                    if s_url.startswith(("http://", "https://")):
                        sources.append(StorySource(name=s_name, url=s_url))

                if not sources:
                    sources = [StorySource(name="Original Source", url="#")]

                images = [str(img).strip() for img in s.get("images", []) if str(img).startswith(("http://", "https://"))]

                stories.append(ConsolidatedStory(
                    title=title,
                    summary=summary,
                    key_points=key_points,
                    importance=importance,
                    sources=sources,
                    images=images[:1]
                ))

            if stories:
                total_cat_images = 0
                for st in stories:
                    if st.images:
                        if total_cat_images >= 3:
                            st.images = []
                        else:
                            total_cat_images += len(st.images)

                digests.append(CategoryDigest(
                    name=display_name,
                    stories=stories,
                    source_links=cat_links_map.get(cat_key, [])
                ))

        return digests


# ==============================================================================
# HTML EMAIL GENERATOR
# ==============================================================================

class EmailGenerator:
    """
    Generates clean, sober, modern, responsive HTML emails with inline CSS.
    """

    @staticmethod
    def generate_html(
        digests: List[CategoryDigest],
        execution_time: Optional[datetime.datetime] = None,
        time_window_hours: int = config.TIME_WINDOW_HOURS
    ) -> str:
        """
        Generate complete HTML newsletter payload.
        """
        if execution_time is None:
            execution_time = datetime.datetime.now(datetime.timezone.utc)

        formatted_date = execution_time.strftime("%B %d, %Y")
        formatted_time = execution_time.strftime("%H:%M UTC")

        # Check if there are no news items
        if not digests or all(len(d.stories) == 0 for d in digests):
            return EmailGenerator._generate_empty_newsletter(formatted_date, formatted_time, time_window_hours)

        categories_html = []
        for digest in digests:
            cat_title = digest.name.upper()
            stories_html = []

            for story in digest.stories:
                # Image element (if present)
                image_tag = ""
                if story.images:
                    primary_url = story.sources[0].url if story.sources else "#"
                    image_tag = f"""
                    <div style="margin-bottom: 14px;">
                        <a href="{html.escape(primary_url)}" target="_blank" style="text-decoration: none;">
                            <img src="{html.escape(story.images[0])}" alt="{html.escape(story.title)}" style="width: 100%; max-height: 280px; object-fit: cover; border-radius: 6px; display: block; border: 1px solid #e2e8f0;" />
                        </a>
                    </div>
                    """

                # Key bullet points
                points_tag = ""
                if story.key_points:
                    items = "".join(f"<li style='margin-bottom: 5px; color: #334155;'>{html.escape(pt)}</li>" for pt in story.key_points)
                    points_tag = f"""
                    <ul style="margin: 12px 0 14px 20px; padding: 0; font-size: 14px; line-height: 1.5;">
                        {items}
                    </ul>
                    """

                # Sources links
                sources_links = " · ".join(
                    f'<a href="{html.escape(src.url)}" target="_blank" style="color: #2563eb; text-decoration: none; font-weight: 500;">{html.escape(src.name)}</a>'
                    for src in story.sources
                )

                story_card = f"""
                <div style="margin-bottom: 24px; padding: 18px; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px;">
                    {image_tag}
                    <h3 style="margin: 0 0 10px 0; font-size: 18px; line-height: 1.35; color: #0f172a; font-weight: 700;">
                        {html.escape(story.title)}
                    </h3>
                    <p style="margin: 0 0 10px 0; font-size: 15px; line-height: 1.6; color: #334155;">
                        {html.escape(story.summary)}
                    </p>
                    {points_tag}
                    <div style="font-size: 13px; color: #64748b; padding-top: 8px; border-top: 1px solid #f1f5f9;">
                        <strong>Sources:</strong> {sources_links}
                    </div>
                </div>
                """
                stories_html.append(story_card)

            # Category bottom article links
            raw_links_tag = ""
            if digest.source_links:
                link_items = "".join(
                    f'<li style="margin-bottom: 4px;"><a href="{html.escape(l.url)}" target="_blank" style="color: #2563eb; text-decoration: none;">{html.escape(l.name)}: {html.escape(l.url)}</a></li>'
                    for l in digest.source_links[:10]
                )
                raw_links_tag = f"""
                <div style="margin-top: 16px; margin-bottom: 28px; padding: 14px; background-color: #f8fafc; border-radius: 6px; font-size: 13px; color: #64748b;">
                    <div style="font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; color: #475569;">
                        {cat_title} — Article Links
                    </div>
                    <ul style="margin: 0 0 0 18px; padding: 0; line-height: 1.4;">
                        {link_items}
                    </ul>
                </div>
                """

            cat_section = f"""
            <div style="margin-bottom: 36px;">
                <div style="border-bottom: 2px solid #0f172a; padding-bottom: 6px; margin-bottom: 18px;">
                    <h2 style="margin: 0; font-size: 20px; font-weight: 800; letter-spacing: 1px; color: #0f172a; text-transform: uppercase;">
                        {cat_title}
                    </h2>
                </div>
                {"".join(stories_html)}
                {raw_links_tag}
            </div>
            """
            categories_html.append(cat_section)

        # Full email template
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BUBBLE NEWS Update</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f4f6f8; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f4f6f8; padding: 24px 0;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" style="max-width: 680px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden;" cellspacing="0" cellpadding="0">
                    <!-- HEADER -->
                    <tr>
                        <td style="padding: 32px 32px 24px 32px; background-color: #0f172a; text-align: left;">
                            <div style="font-size: 26px; font-weight: 900; letter-spacing: 2px; color: #ffffff; text-transform: uppercase;">
                                BUBBLE NEWS
                            </div>
                            <div style="font-size: 14px; font-weight: 500; letter-spacing: 1px; color: #94a3b8; text-transform: uppercase; margin-top: 4px;">
                                Daily Intelligence Digest
                            </div>
                            <div style="font-size: 13px; color: #cbd5e1; margin-top: 12px;">
                                {formatted_date} · {formatted_time}
                            </div>
                        </td>
                    </tr>

                    <!-- CONTENT -->
                    <tr>
                        <td style="padding: 28px 32px 10px 32px; background-color: #f8fafc;">
                            {"".join(categories_html)}
                        </td>
                    </tr>

                    <!-- FOOTER -->
                    <tr>
                        <td style="padding: 24px 32px; background-color: #f1f5f9; border-top: 1px solid #e2e8f0; text-align: center; font-size: 12px; color: #64748b;">
                            <p style="margin: 0 0 6px 0;">
                                <strong>BUBBLE NEWS</strong> Version 0.1 Beta — Personal AI News Aggregator
                            </p>
                            <p style="margin: 0; color: #94a3b8;">
                                Covering news from the previous {time_window_hours} hours.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    @staticmethod
    def _generate_empty_newsletter(formatted_date: str, formatted_time: str, hours: int) -> str:
        """HTML message when no new articles exist within the time window."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BUBBLE NEWS Update</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f4f6f8; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f4f6f8; padding: 32px 0;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" style="max-width: 640px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden;" cellspacing="0" cellpadding="0">
                    <tr>
                        <td style="padding: 30px; background-color: #0f172a; text-align: left;">
                            <div style="font-size: 24px; font-weight: 800; letter-spacing: 2px; color: #ffffff;">BUBBLE NEWS</div>
                            <div style="font-size: 13px; color: #94a3b8; margin-top: 4px;">{formatted_date} · {formatted_time}</div>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px 30px; text-align: center;">
                            <h3 style="margin: 0 0 12px 0; color: #1e293b; font-size: 18px;">No New Articles Found</h3>
                            <p style="margin: 0; color: #64748b; font-size: 15px; line-height: 1.6;">
                                No new articles were found during the last {hours} hours.<br>
                                All configured RSS feeds were checked successfully.
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 18px 30px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center; font-size: 12px; color: #94a3b8;">
                            BUBBLE NEWS Version 0.1 Beta
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


# ==============================================================================
# DISROOT SMTP SENDER
# ==============================================================================

class EmailSender:
    """
    Delivers HTML newsletter via Disroot SMTP (Port 587, STARTTLS).
    """

    def __init__(
        self,
        email_address: str = config.EMAIL_ADDRESS,
        password: str = config.EMAIL_PASSWORD,
        smtp_server: str = config.SMTP_SERVER,
        smtp_port: int = config.SMTP_PORT
    ):
        self.email_address = email_address.strip()
        self.password = password
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port

    def send_newsletter(self, html_content: str, subject: str = "BUBBLE NEWS Update") -> None:
        """
        Send HTML email to the user's configured email address.
        """
        if ConfigManager.is_placeholder(self.email_address) or ConfigManager.is_placeholder(self.password):
            raise ValueError(
                "Cannot send email: EMAIL_ADDRESS or EMAIL_PASSWORD in config.py is still set to placeholder values. "
                "Please configure valid credentials in config.py before sending."
            )

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.email_address
        msg["To"] = self.email_address
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain=self.smtp_server)

        # Plain text fallback
        plain_text = "BUBBLE NEWS Update\nPlease view this email in an HTML-compatible client."
        msg.attach(MIMEText(plain_text, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        context = ssl.create_default_context()

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(self.email_address, self.password)
                server.sendmail(self.email_address, [self.email_address], msg.as_string())
        except smtplib.SMTPAuthenticationError as e:
            raise RuntimeError(f"Disroot SMTP Authentication failed: {e}. Please verify your email credentials in config.py.")
        except Exception as e:
            raise RuntimeError(f"Failed to send email via Disroot SMTP ({self.smtp_server}:{self.smtp_port}): {e}")


# ==============================================================================
# MAIN BUBBLE NEWS ORCHESTRATOR
# ==============================================================================

class BubbleNewsApp:
    """
    Coordinates the end-to-end 6-step pipeline of Bubble News.
    """

    def __init__(
        self,
        feeds_file: Optional[str] = None,
        hours: Optional[int] = None,
        dry_run: bool = False
    ):
        self.feeds_file = feeds_file or config.FEEDS_FILE
        self.hours = hours or config.TIME_WINDOW_HOURS
        self.dry_run = dry_run
        self.config_mgr = ConfigManager(self.feeds_file)

    def run(self) -> bool:
        """
        Execute the full Bubble News pipeline.
        
        Returns:
            bool: True if completed successfully, False otherwise.
        """
        print_banner()
        print(f"{Fore.CYAN}[BUBBLE NEWS] Starting...{Style.RESET_ALL}\n")

        # [1/6] Loading configuration...
        print(f"{Style.BRIGHT}[1/6] Loading configuration...{Style.RESET_ALL}")
        try:
            categorized_feeds = self.config_mgr.load_feeds()
            total_feeds = sum(len(u) for u in categorized_feeds.values())
            print_ok(f"Loaded {len(categorized_feeds)} categories ({total_feeds} feeds) from '{self.feeds_file}'")
        except Exception as e:
            print_error(f"Configuration error: {e}")
            return False

        # [2/6] Reading RSS feeds & [3/6] Filtering articles from publication window...
        print(f"\n{Style.BRIGHT}[2/6] Reading RSS feeds...{Style.RESET_ALL}")
        fetcher = RSSFetcher(time_window_hours=self.hours)
        rss_articles = fetcher.fetch_all(categorized_feeds)

        print(f"\n{Style.BRIGHT}[3/6] Filtering articles from last {self.hours} hours...{Style.RESET_ALL}")
        print_ok(f"{len(rss_articles)} articles selected in window")

        # If no articles found, handle empty digest
        if not rss_articles:
            print_warn(f"No articles found published within the last {self.hours} hours.")
            html_payload = EmailGenerator.generate_html([], time_window_hours=self.hours)
            if self.dry_run:
                self._save_preview(html_payload)
                print_ok("Dry run complete: Saved preview_newsletter.html")
                return True
            else:
                return self._dispatch_email(html_payload)

        # [4/6] Fetching article content...
        print(f"\n{Style.BRIGHT}[4/6] Fetching article content...{Style.RESET_ALL}")
        extractor = ArticleExtractor()
        extracted_articles = extractor.extract_articles(rss_articles)

        # [5/6] Processing with Google Gemini...
        print(f"\n{Style.BRIGHT}[5/6] Processing with Google Gemini...{Style.RESET_ALL}")
        
        # Check if Gemini API key is configured
        if ConfigManager.is_placeholder(config.GEMINI_API_KEY):
            print_warn("GEMINI_API_KEY in config.py is set to placeholder value.")
            if self.dry_run:
                print_info("Dry run mode: Generating fallback preview with extracted articles without Gemini summarization.")
                digests = self._create_fallback_digests(extracted_articles, list(categorized_feeds.keys()))
            else:
                print_error(
                    "Cannot process articles: GEMINI_API_KEY in config.py is set to placeholder value. "
                    "Please set your Gemini API key in config.py."
                )
                return False
        else:
            try:
                consolidator = GeminiConsolidator(
                    api_key=config.GEMINI_API_KEY,
                    model_name=config.GEMINI_MODEL
                )
                digests = consolidator.process_and_summarize(
                    extracted_articles,
                    allowed_categories=list(categorized_feeds.keys())
                )
                total_stories = sum(len(d.stories) for d in digests)
                print_ok(f"Consolidated into {total_stories} stories across {len(digests)} categories")
            except Exception as e:
                print_error(f"Gemini processing error: {e}")
                return False

        # Generate HTML Email
        html_payload = EmailGenerator.generate_html(digests, time_window_hours=self.hours)

        # [6/6] Sending email...
        print(f"\n{Style.BRIGHT}[6/6] Sending email...{Style.RESET_ALL}")
        if self.dry_run:
            self._save_preview(html_payload)
            print_ok("Dry run mode: Email transmission skipped. Output written to 'preview_newsletter.html'.")
            print(f"\n{Fore.GREEN}{Style.BRIGHT}BUBBLE NEWS completed successfully (Dry Run).{Style.RESET_ALL}\n")
            return True

        success = self._dispatch_email(html_payload)
        if success:
            print(f"\n{Fore.GREEN}{Style.BRIGHT}BUBBLE NEWS completed successfully.{Style.RESET_ALL}\n")
        return success

    def _dispatch_email(self, html_payload: str) -> bool:
        """Send email via Disroot SMTP."""
        try:
            sender = EmailSender()
            sender.send_newsletter(html_payload)
            print_ok(f"Email sent successfully to {config.EMAIL_ADDRESS}")
            return True
        except Exception as e:
            print_error(f"Failed to send email: {e}")
            return False

    @staticmethod
    def _create_fallback_digests(articles: List[ExtractedArticle], allowed_categories: List[str]) -> List[CategoryDigest]:
        """Create fallback digests when running in dry-run with placeholder Gemini keys."""
        cat_map: Dict[str, List[ExtractedArticle]] = {c: [] for c in allowed_categories}
        for a in articles:
            if a.category in cat_map:
                cat_map[a.category].append(a)

        digests: List[CategoryDigest] = []
        for cat, items in cat_map.items():
            stories: List[ConsolidatedStory] = []
            source_links: List[StorySource] = []
            for it in items:
                source_links.append(StorySource(name=it.source_name, url=it.url))
                stories.append(ConsolidatedStory(
                    title=it.title,
                    summary=it.main_text[:300] + "..." if len(it.main_text) > 300 else it.main_text,
                    key_points=["Preview extract generated without live Gemini API call."],
                    importance="medium",
                    sources=[StorySource(name=it.source_name, url=it.url)],
                    images=[it.featured_image] if it.featured_image else []
                ))
            if stories:
                digests.append(CategoryDigest(name=cat, stories=stories, source_links=source_links))
        return digests

    @staticmethod
    def _save_preview(html_content: str, filename: str = "preview_newsletter.html") -> None:
        """Save HTML payload for local inspection."""
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"Saved email preview to {filename}")


# ==============================================================================
# CLI PARSER
# ==============================================================================

def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="BUBBLE NEWS - Personal AI News Aggregator & Digest (v0.1 Beta)"
    )
    parser.add_argument(
        "--feeds",
        default=None,
        help=f"Path to RSS feeds JSON file (default: {config.FEEDS_FILE})"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=None,
        help=f"Publication time window in hours (default: {config.TIME_WINDOW_HOURS})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run news aggregation and summarization without sending SMTP email (saves preview_newsletter.html)"
    )

    args = parser.parse_args()

    app = BubbleNewsApp(
        feeds_file=args.feeds,
        hours=args.hours,
        dry_run=args.dry_run
    )

    success = app.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
