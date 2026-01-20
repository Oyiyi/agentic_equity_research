#!/usr/bin/env python
"""
News Collector using Finnhub API

This script uses FINNHUB_API_KEY from .env file to pull latest news based on stock from config.yaml.
Note: Free tier quota is 60 requests/minute for Company News. https://finnhub.io
News is saved to cache.db using time, ticker and news_content.
"""

import os
import sys
import sqlite3
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict
import dotenv
import yaml
import time

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env file
env_path = project_root / '.env'
if env_path.exists():
    dotenv.load_dotenv(dotenv_path=str(env_path), override=True)
else:
    dotenv.load_dotenv(override=True)

# Finnhub API Configuration
FINNHUB_API_BASE = "https://finnhub.io/api/v1"
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY')

if not FINNHUB_API_KEY:
    print("Warning: FINNHUB_API_KEY not found in .env file. Please add FINNHUB_API_KEY=your_key to .env")
    print("News collection will be skipped.")

# Database path
DEFAULT_DB_PATH = project_root / 'data' / 'cache.db'


def init_news_table(db_path: str = None) -> None:
    """
    Initialize news table in database if it doesn't exist.
    
    Args:
        db_path: Path to SQLite database. If None, uses default cache.db location.
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)
    
    # Ensure directory exists
    db_path_obj = Path(db_path)
    db_path_obj.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    
    # Create news table (matching existing schema)
    c.execute('''
    CREATE TABLE IF NOT EXISTS news (
        news_url TEXT PRIMARY KEY,
        read_num TEXT,
        reply_num TEXT,
        news_title TEXT,
        news_author TEXT,
        news_time TEXT,
        stock_code TEXT,
        news_content TEXT,
        news_summary TEXT,
        dec_response TEXT,
        news_decision TEXT
    )
    ''')
    
    conn.commit()
    conn.close()


def fetch_company_news_finnhub(
    ticker: str,
    start_date: str = None,
    end_date: str = None,
    limit: int = 100
) -> Optional[List[Dict]]:
    """
    Fetch company news from Finnhub API.
    
    Args:
        ticker: Stock ticker symbol (e.g., 'TSLA', 'AAPL')
        start_date: Start date in YYYY-MM-DD format. If None, defaults to 30 days ago.
        end_date: End date in YYYY-MM-DD format. If None, defaults to today.
        limit: Maximum number of news articles to fetch (default: 100)
        
    Returns:
        List of news articles (dictionaries) or None if error
    """
    if not FINNHUB_API_KEY:
        print("Error: FINNHUB_API_KEY not configured")
        return None
    
    # Set default dates if not provided
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    # Convert dates to Unix timestamps (Finnhub API requirement)
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        start_timestamp = int(start_dt.timestamp())
        end_timestamp = int(end_dt.timestamp())
    except ValueError as e:
        print(f"Error parsing dates: {e}")
        return None
    
    url = f"{FINNHUB_API_BASE}/company-news"
    params = {
        'symbol': ticker,
        'from': start_date,
        'to': end_date,
        'token': FINNHUB_API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        news_data = response.json()
        
        # Finnhub returns a list of news articles
        if isinstance(news_data, list):
            # Limit the number of articles
            return news_data[:limit]
        else:
            print(f"Unexpected response format: {type(news_data)}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching news from Finnhub API: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return None


def save_news_to_db(
    news_list: List[Dict],
    ticker: str,
    db_path: str = None
) -> int:
    """
    Save news articles to database.
    
    Args:
        news_list: List of news article dictionaries from Finnhub API
        ticker: Stock ticker symbol
        db_path: Path to SQLite database. If None, uses default cache.db location.
        
    Returns:
        Number of news articles successfully saved
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)
    
    # Initialize table if needed
    init_news_table(db_path)
    
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    
    saved_count = 0
    skipped_count = 0
    
    for news_item in news_list:
        try:
            # Convert Unix timestamp to datetime string
            datetime_ts = news_item.get('datetime', 0)
            if datetime_ts:
                news_time = datetime.fromtimestamp(datetime_ts).strftime('%Y-%m-%d %H:%M:%S')
            else:
                news_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Extract news data
            news_url = news_item.get('url', '')
            news_title = news_item.get('headline', '')
            news_summary = news_item.get('summary', '')
            news_source = news_item.get('source', 'Finnhub')
            
            # Use URL as primary key, skip if already exists
            c.execute('SELECT news_url FROM news WHERE news_url = ?', (news_url,))
            if c.fetchone():
                skipped_count += 1
                continue
            
            # Insert news article
            c.execute('''
            INSERT OR IGNORE INTO news (
                news_url, read_num, reply_num, news_title, news_author, 
                news_time, stock_code, news_content, news_summary, 
                dec_response, news_decision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                news_url,
                '0',  # read_num - not available from Finnhub
                '0',  # reply_num - not available from Finnhub
                news_title,
                news_source,  # Use source as author
                news_time,
                ticker,
                news_summary,  # Use summary as content
                news_summary,
                '',  # dec_response - empty initially
                ''   # news_decision - empty initially
            ))
            
            saved_count += 1
            
        except sqlite3.IntegrityError:
            # Skip duplicate entries
            skipped_count += 1
            continue
        except Exception as e:
            print(f"Error saving news article: {e}")
            continue
    
    conn.commit()
    conn.close()
    
    print(f"Saved {saved_count} news articles, skipped {skipped_count} duplicates")
    return saved_count


def collect_news_from_config(
    config_path: str = 'config.yaml',
    db_path: str = None,
    days_back: int = 30
) -> int:
    """
    Collect news based on ticker from config.yaml.
    
    Args:
        config_path: Path to config.yaml file
        db_path: Path to SQLite database. If None, uses default cache.db location.
        days_back: Number of days to look back for news (default: 30)
        
    Returns:
        Number of news articles saved
    """
    # Load config.yaml
    config_file = project_root / config_path
    if not config_file.exists():
        print(f"Error: Config file not found at {config_file}")
        return 0
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Get ticker from config
    ticker = None
    if config and 'inputs' in config and 'source_report' in config['inputs']:
        ticker = config['inputs']['source_report'].get('ticker')
    
    if not ticker:
        print("Error: No ticker found in config.yaml")
        return 0
    
    print(f"Collecting news for {ticker}...")
    
    # Calculate date range
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    
    # Fetch news from Finnhub
    news_list = fetch_company_news_finnhub(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        limit=100
    )
    
    if not news_list:
        print("No news found or error occurred")
        return 0
    
    print(f"Fetched {len(news_list)} news articles from Finnhub")
    
    # Save to database
    saved_count = save_news_to_db(news_list, ticker, db_path)
    
    return saved_count


def collect_news(
    ticker: str,
    start_date: str = None,
    end_date: str = None,
    db_path: str = None,
    limit: int = 100
) -> int:
    """
    Collect news for a specific ticker.
    
    Args:
        ticker: Stock ticker symbol
        start_date: Start date in YYYY-MM-DD format. If None, defaults to 30 days ago.
        end_date: End date in YYYY-MM-DD format. If None, defaults to today.
        db_path: Path to SQLite database. If None, uses default cache.db location.
        limit: Maximum number of news articles to fetch (default: 100)
        
    Returns:
        Number of news articles saved
    """
    print(f"Collecting news for {ticker}...")
    
    # Fetch news from Finnhub
    news_list = fetch_company_news_finnhub(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )
    
    if not news_list:
        print("No news found or error occurred")
        return 0
    
    print(f"Fetched {len(news_list)} news articles from Finnhub")
    
    # Save to database
    saved_count = save_news_to_db(news_list, ticker, db_path)
    
    return saved_count


if __name__ == '__main__':
    # Example usage: collect news from config.yaml
    import argparse
    
    parser = argparse.ArgumentParser(description='Collect company news using Finnhub API')
    parser.add_argument('--ticker', type=str, help='Stock ticker symbol (e.g., TSLA)')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--days-back', type=int, default=30, help='Days to look back (default: 30)')
    parser.add_argument('--config', type=str, default='config.yaml', help='Path to config.yaml')
    parser.add_argument('--db-path', type=str, help='Path to database file')
    
    args = parser.parse_args()
    
    if args.ticker:
        # Collect news for specific ticker
        saved = collect_news(
            ticker=args.ticker,
            start_date=args.start_date,
            end_date=args.end_date,
            db_path=args.db_path
        )
    else:
        # Collect news from config.yaml
        saved = collect_news_from_config(
            config_path=args.config,
            db_path=args.db_path,
            days_back=args.days_back
        )
    
    print(f"Total news articles saved: {saved}")
