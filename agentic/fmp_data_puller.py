#!/usr/bin/env python
"""
FMP Data Puller for Tesla

This script pulls two types of data for a given company ticker (default: TSLA):
- S1: Price Performance - Historical price curve comparing stock vs base index (SPY)
- S2: Company Data - Static snapshot metrics (shares outstanding, market cap, etc.)

All data is cached in SQLite database with field-level checking before API calls.
"""

import os
import sys
import sqlite3
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import statistics
import dotenv

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env file
env_path = project_root / '.env'
if env_path.exists():
    dotenv.load_dotenv(dotenv_path=str(env_path), override=True)
else:
    dotenv.load_dotenv(override=True)

# FMP API Configuration
FMP_API_BASE = "https://financialmodelingprep.com/stable"
FMP_API_KEY = os.getenv('FMP_API_KEY')

if not FMP_API_KEY:
    raise ValueError("FMP_API_KEY not found in .env file. Please add FMP_API_KEY=your_key to .env")

# Database path (following existing pattern)
DEFAULT_DB_PATH = project_root / 'finrpt' / 'source' / 'cache.db'


def init_tables(db_path: str = None) -> None:
    """
    Initialize database tables for price_performance and company_data.
    
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
    
    # Create price_performance table
    c.execute('''
    CREATE TABLE IF NOT EXISTS price_performance (
        id TEXT PRIMARY KEY,
        ticker TEXT,
        base_index TEXT,
        start_date TEXT,
        end_date TEXT,
        stock_data TEXT,
        index_data TEXT,
        created_at TEXT
    )
    ''')
    
    # Create company_data table
    c.execute('''
    CREATE TABLE IF NOT EXISTS company_data (
        id TEXT PRIMARY KEY,
        ticker TEXT,
        as_of_date TEXT,
        shares_outstanding REAL,
        market_cap REAL,
        currency TEXT,
        fx_rate REAL,
        free_float_pct REAL,
        avg_daily_volume_3m_shares REAL,
        avg_daily_volume_3m_usd REAL,
        volatility_90d REAL,
        "52w_high" REAL,
        "52w_low" REAL,
        primary_index_name TEXT,
        analyst_rating_counts TEXT,
        consensus_rating TEXT,
        num_analysts INTEGER,
        created_at TEXT
    )
    ''')
    
    # Create key_metrics table
    c.execute('''
    CREATE TABLE IF NOT EXISTS key_metrics (
        id TEXT PRIMARY KEY,
        ticker TEXT,
        fiscal_year_end TEXT,
        metrics_data TEXT,
        created_at TEXT
    )
    ''')
    
    conn.commit()
    conn.close()


def check_price_performance_cache(
    ticker: str,
    start_date: str,
    end_date: str,
    base_index: str,
    db_path: str = None
) -> Optional[Dict]:
    """
    Check if price performance data exists in cache with all required fields non-empty.
    
    Args:
        ticker: Stock ticker symbol
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        base_index: Base index symbol (e.g., 'SPY')
        db_path: Path to database. If None, uses default.
        
    Returns:
        Dictionary with cached data if all fields are present, None otherwise.
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)
    
    if not Path(db_path).exists():
        return None
    
    cache_id = f"{ticker}_{start_date}_{end_date}"
    
    try:
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute(
            'SELECT stock_data, index_data FROM price_performance WHERE id = ?',
            (cache_id,)
        )
        result = c.fetchone()
        conn.close()
        
        if result and result[0] and result[1]:
            # Verify JSON is valid and non-empty
            try:
                stock_data = json.loads(result[0])
                index_data = json.loads(result[1])
                if stock_data and index_data:
                    return {
                        'stock_data': stock_data,
                        'index_data': index_data
                    }
            except json.JSONDecodeError:
                return None
    except Exception as e:
        print(f"Error checking price performance cache: {e}")
    
    return None


def check_company_data_cache(
    ticker: str,
    as_of_date: str,
    db_path: str = None
) -> Optional[Dict]:
    """
    Check if company data exists in cache with all required fields non-empty.
    
    Args:
        ticker: Stock ticker symbol
        as_of_date: Date in YYYY-MM-DD format
        db_path: Path to database. If None, uses default.
        
    Returns:
        Dictionary with cached data if all fields are present, None otherwise.
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)
    
    if not Path(db_path).exists():
        return None
    
    cache_id = f"{ticker}_{as_of_date}"
    
    try:
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute(
            '''SELECT shares_outstanding, market_cap, currency, fx_rate, 
               free_float_pct, avg_daily_volume_3m_shares, avg_daily_volume_3m_usd,
               volatility_90d, "52w_high", "52w_low", primary_index_name,
               analyst_rating_counts, consensus_rating, num_analysts
               FROM company_data WHERE id = ?''',
            (cache_id,)
        )
        result = c.fetchone()
        conn.close()
        
        if result:
            # Check if all required fields are non-empty
            required_fields = [
                result[0],  # shares_outstanding
                result[1],  # market_cap
                result[2],  # currency
                result[4],  # free_float_pct
                result[5],  # avg_daily_volume_3m_shares
                result[6],  # avg_daily_volume_3m_usd
                result[7],  # volatility_90d
                result[8],  # 52w_high
                result[9],  # 52w_low
            ]
            
            # Check if all numeric fields are not None
            if all(field is not None for field in required_fields):
                return {
                    'shares_outstanding': result[0],
                    'market_cap': result[1],
                    'currency': result[2],
                    'fx_rate': result[3] or 1.0,
                    'free_float_pct': result[4],
                    'avg_daily_volume_3m_shares': result[5],
                    'avg_daily_volume_3m_usd': result[6],
                    'volatility_90d': result[7],
                    '52w_high': result[8],
                    '52w_low': result[9],
                    'primary_index_name': result[10],
                    'analyst_rating_counts': json.loads(result[11]) if result[11] else {},
                    'consensus_rating': result[12],
                    'num_analysts': result[13] or 0
                }
    except Exception as e:
        print(f"Error checking company data cache: {e}")
    
    return None


def fetch_price_performance_fmp(
    ticker: str,
    base_index: str,
    start_date: str,
    end_date: str,
    api_key: str
) -> Tuple[Optional[List[Dict]], Optional[List[Dict]]]:
    """
    Fetch historical price data from FMP API for both ticker and base index.
    
    Args:
        ticker: Stock ticker symbol
        base_index: Base index symbol (e.g., 'SPY')
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        api_key: FMP API key
        
    Returns:
        Tuple of (stock_data, index_data) where each is a list of dicts with date, close, rebased_close.
        Returns (None, None) on error.
    """
    def fetch_historical_prices(symbol: str) -> Optional[List[Dict]]:
        """Fetch and process historical prices for a symbol."""
        url = f"{FMP_API_BASE}/historical-price-eod/full"
        params = {
            'symbol': symbol,
            'from': start_date,
            'to': end_date,
            'apikey': api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            if response.status_code != 200:
                print(f"Error fetching {symbol}: HTTP {response.status_code}")
                return None
            
            data = response.json()
            # FMP API returns either an object with 'historical' key or array directly
            if isinstance(data, dict) and 'historical' in data:
                historical = data['historical']
            elif isinstance(data, list):
                historical = data
            else:
                print(f"No historical data found for {symbol}")
                return None
            
            if not historical:
                print(f"Empty historical data for {symbol}")
                return None
            
            # Sort by date (oldest first)
            historical.sort(key=lambda x: x['date'])
            
            # Get first close price for rebasing
            first_close = historical[0]['close']
            if first_close == 0:
                print(f"Invalid first close price for {symbol}")
                return None
            
            # Process and rebase data
            processed = []
            for entry in historical:
                close = entry['close']
                rebased_close = (close / first_close) * 100
                processed.append({
                    'date': entry['date'],
                    'close': close,
                    'rebased_close': rebased_close
                })
            
            return processed
            
        except Exception as e:
            print(f"Error fetching historical prices for {symbol}: {e}")
            return None
    
    # Fetch data for both ticker and base index
    stock_data = fetch_historical_prices(ticker)
    index_data = fetch_historical_prices(base_index)
    
    return stock_data, index_data


def calculate_volatility_90d(historical_data: List[Dict]) -> float:
    """
    Calculate 90-day volatility from historical price data.
    
    Args:
        historical_data: List of dicts with 'changePercent' or 'close' prices
        
    Returns:
        Volatility as standard deviation of daily returns (as percentage)
    """
    if not historical_data or len(historical_data) < 2:
        return 0.0
    
    # Get last 90 trading days (or all available if less)
    data = historical_data[-90:] if len(historical_data) > 90 else historical_data
    
    # Calculate daily returns
    returns = []
    for i in range(1, len(data)):
        if 'changePercent' in data[i] and data[i]['changePercent'] is not None:
            returns.append(data[i]['changePercent'] / 100.0)  # Convert percentage to decimal
        elif 'close' in data[i] and 'close' in data[i-1]:
            prev_close = data[i-1]['close']
            curr_close = data[i]['close']
            if prev_close and prev_close > 0:
                daily_return = (curr_close - prev_close) / prev_close
                returns.append(daily_return)
    
    if not returns:
        return 0.0
    
    # Calculate standard deviation of returns
    if len(returns) < 2:
        return 0.0
    volatility = statistics.stdev(returns) * 100  # Convert back to percentage
    return float(volatility)


def fetch_company_data_fmp(
    ticker: str,
    as_of_date: str,
    api_key: str
) -> Optional[Dict]:
    """
    Fetch company data from multiple FMP API endpoints.
    
    Args:
        ticker: Stock ticker symbol
        as_of_date: Date in YYYY-MM-DD format
        api_key: FMP API key
        
    Returns:
        Dictionary with all company data fields, or None on error.
    """
    result = {}
    current_price = None
    profile_data = None
    historical = None
    
    try:
        # 1. Fetch company profile
        url = f"{FMP_API_BASE}/profile"
        params = {'symbol': ticker, 'apikey': api_key}
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            profile_data = response.json()
            if profile_data and len(profile_data) > 0:
                profile = profile_data[0]
                result['market_cap'] = profile.get('mktCap') or profile.get('marketCap')
                result['currency'] = profile.get('currency', 'USD')
                result['primary_index_name'] = profile.get('exchangeShortName') or profile.get('exchange', '')
        else:
            print(f"Error fetching profile: HTTP {response.status_code}")
        
        # 2. Fetch shares float
        url = f"{FMP_API_BASE}/shares-float"
        params = {'symbol': ticker, 'apikey': api_key}
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            float_data = response.json()
            if float_data and len(float_data) > 0:
                float_info = float_data[0]
                result['shares_outstanding'] = float_info.get('sharesOutstanding') or float_info.get('sharesOutstanding')
                result['free_float_pct'] = float_info.get('freeFloat') or float_info.get('freeFloatPercentage')
        else:
            print(f"Error fetching shares float: HTTP {response.status_code}")
        
        # 3. Fetch quote
        url = f"{FMP_API_BASE}/quote"
        params = {'symbol': ticker, 'apikey': api_key}
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            quote_data = response.json()
            if quote_data and len(quote_data) > 0:
                quote = quote_data[0]
                result['52w_high'] = quote.get('yearHigh') or quote.get('fiftyTwoWeekHigh')
                result['52w_low'] = quote.get('yearLow') or quote.get('fiftyTwoWeekLow')
                result['avg_daily_volume_3m_shares'] = quote.get('avgVolume') or quote.get('volume')
                current_price = quote.get('price') or quote.get('previousClose')
        else:
            print(f"Error fetching quote: HTTP {response.status_code}")
        
        # If avg_daily_volume_3m_shares not found, try calculating from historical data
        if not result.get('avg_daily_volume_3m_shares'):
            # We'll calculate this from historical data if needed
            pass
        
        # If shares_outstanding not found, try calculating from market cap and price
        if not result.get('shares_outstanding'):
            if result.get('market_cap') and current_price and current_price > 0:
                result['shares_outstanding'] = result['market_cap'] / current_price
                print(f"Calculated shares_outstanding from market_cap and price: {result['shares_outstanding']:,.0f}")
        
        # Calculate avg_daily_volume_3m_usd
        if result.get('avg_daily_volume_3m_shares') and current_price:
            result['avg_daily_volume_3m_usd'] = result['avg_daily_volume_3m_shares'] * current_price
        elif result.get('avg_daily_volume_3m_shares'):
            # Use market cap / shares outstanding as fallback price estimate
            if result.get('market_cap') and result.get('shares_outstanding'):
                est_price = result['market_cap'] / result['shares_outstanding']
                result['avg_daily_volume_3m_usd'] = result['avg_daily_volume_3m_shares'] * est_price
            else:
                result['avg_daily_volume_3m_usd'] = None
        else:
            result['avg_daily_volume_3m_usd'] = None
        
        # 4. Fetch grades consensus
        url = f"{FMP_API_BASE}/grades-consensus"
        params = {'symbol': ticker, 'apikey': api_key}
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            grades_data = response.json()
            if grades_data and len(grades_data) > 0:
                grades = grades_data[0]
                result['analyst_rating_counts'] = {
                    'strongBuy': grades.get('strongBuy', 0),
                    'buy': grades.get('buy', 0),
                    'hold': grades.get('hold', 0),
                    'sell': grades.get('sell', 0),
                    'strongSell': grades.get('strongSell', 0)
                }
                result['consensus_rating'] = grades.get('consensus', '')
                result['num_analysts'] = grades.get('total', 0)
        else:
            print(f"Error fetching grades consensus: HTTP {response.status_code}")
            result['analyst_rating_counts'] = {}
            result['consensus_rating'] = ''
            result['num_analysts'] = 0
        
        # 5. Fetch historical prices for volatility calculation
        # Calculate 90 days before as_of_date
        as_of_dt = datetime.strptime(as_of_date, '%Y-%m-%d')
        start_dt = as_of_dt - timedelta(days=120)  # Get extra days to ensure 90 trading days
        start_date_vol = start_dt.strftime('%Y-%m-%d')
        
        url = f"{FMP_API_BASE}/historical-price-eod/full"
        params = {
            'symbol': ticker,
            'from': start_date_vol,
            'to': as_of_date,
            'apikey': api_key
        }
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            hist_data = response.json()
            # FMP API returns either an object with 'historical' key or array directly
            if isinstance(hist_data, dict) and 'historical' in hist_data:
                historical = hist_data['historical']
            elif isinstance(hist_data, list):
                historical = hist_data
            else:
                historical = None
            
            if historical:
                result['volatility_90d'] = calculate_volatility_90d(historical)
            else:
                result['volatility_90d'] = None
        else:
            print(f"Error fetching historical data for volatility: HTTP {response.status_code}")
            result['volatility_90d'] = None
        
        # Set fx_rate (default to 1.0 for USD)
        result['fx_rate'] = 1.0 if result.get('currency', 'USD') == 'USD' else 1.0
        
        # Try to calculate missing fields from historical data if available
        if not result.get('avg_daily_volume_3m_shares') and 'historical' in locals():
            # Calculate from historical data
            if historical and len(historical) > 0:
                # Get last 90 days of volume data
                recent_data = historical[-90:] if len(historical) > 90 else historical
                volumes = [d.get('volume', 0) for d in recent_data if d.get('volume')]
                if volumes:
                    result['avg_daily_volume_3m_shares'] = sum(volumes) / len(volumes)
                    if current_price:
                        result['avg_daily_volume_3m_usd'] = result['avg_daily_volume_3m_shares'] * current_price
        
        # Validate that we have all required fields
        required_fields = [
            'shares_outstanding', 'market_cap', 'currency', 'free_float_pct',
            'avg_daily_volume_3m_shares', 'avg_daily_volume_3m_usd',
            'volatility_90d', '52w_high', '52w_low'
        ]
        
        missing_fields = [field for field in required_fields if result.get(field) is None]
        if missing_fields:
            print(f"Warning: Missing required fields: {missing_fields}")
            # Don't return None - save what we have, but log the missing fields
            # Set defaults for missing non-critical fields
            if 'free_float_pct' in missing_fields:
                result['free_float_pct'] = None  # Can be None
            if 'avg_daily_volume_3m_shares' in missing_fields:
                result['avg_daily_volume_3m_shares'] = 0
            if 'avg_daily_volume_3m_usd' in missing_fields:
                result['avg_daily_volume_3m_usd'] = 0
            if 'volatility_90d' in missing_fields:
                result['volatility_90d'] = 0.0
            # Only fail if critical fields are missing
            if any(field in missing_fields for field in ['shares_outstanding', 'market_cap', '52w_high', '52w_low']):
                print("Critical fields missing, cannot save company data")
                return None
        
        return result
        
    except Exception as e:
        print(f"Error fetching company data: {e}")
        return None


def save_price_performance(
    db_path: str,
    ticker: str,
    base_index: str,
    start_date: str,
    end_date: str,
    stock_data: List[Dict],
    index_data: List[Dict]
) -> bool:
    """
    Save price performance data to database.
    
    Args:
        db_path: Path to database
        ticker: Stock ticker symbol
        base_index: Base index symbol
        start_date: Start date
        end_date: End date
        stock_data: List of stock price data dicts
        index_data: List of index price data dicts
        
    Returns:
        True if successful, False otherwise
    """
    cache_id = f"{ticker}_{start_date}_{end_date}"
    created_at = datetime.now().isoformat()
    
    try:
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        
        c.execute('''
        INSERT OR REPLACE INTO price_performance 
        (id, ticker, base_index, start_date, end_date, stock_data, index_data, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            cache_id,
            ticker,
            base_index,
            start_date,
            end_date,
            json.dumps(stock_data),
            json.dumps(index_data),
            created_at
        ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving price performance: {e}")
        return False


def save_company_data(
    db_path: str,
    ticker: str,
    as_of_date: str,
    data_dict: Dict
) -> bool:
    """
    Save company data to database.
    
    Args:
        db_path: Path to database
        ticker: Stock ticker symbol
        as_of_date: Date in YYYY-MM-DD format
        data_dict: Dictionary with all company data fields
        
    Returns:
        True if successful, False otherwise
    """
    cache_id = f"{ticker}_{as_of_date}"
    created_at = datetime.now().isoformat()
    
    try:
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        
        c.execute('''
        INSERT OR REPLACE INTO company_data 
        (id, ticker, as_of_date, shares_outstanding, market_cap, currency, fx_rate,
         free_float_pct, avg_daily_volume_3m_shares, avg_daily_volume_3m_usd,
         volatility_90d, "52w_high", "52w_low", primary_index_name,
         analyst_rating_counts, consensus_rating, num_analysts, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            cache_id,
            ticker,
            as_of_date,
            data_dict.get('shares_outstanding'),
            data_dict.get('market_cap'),
            data_dict.get('currency', 'USD'),
            data_dict.get('fx_rate', 1.0),
            data_dict.get('free_float_pct'),
            data_dict.get('avg_daily_volume_3m_shares'),
            data_dict.get('avg_daily_volume_3m_usd'),
            data_dict.get('volatility_90d'),
            data_dict.get('52w_high'),
            data_dict.get('52w_low'),
            data_dict.get('primary_index_name', ''),
            json.dumps(data_dict.get('analyst_rating_counts', {})),
            data_dict.get('consensus_rating', ''),
            data_dict.get('num_analysts', 0),
            created_at
        ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving company data: {e}")
        return False


def fetch_financial_statements_fmp(
    ticker: str,
    api_key: str,
    period: str = 'annual',
    limit: int = 5
) -> Tuple[Optional[List[Dict]], Optional[List[Dict]], Optional[List[Dict]]]:
    """
    Fetch financial statements from FMP API.
    
    Args:
        ticker: Stock ticker symbol
        api_key: FMP API key
        period: 'annual' or 'quarter'
        limit: Number of periods to fetch
        
    Returns:
        Tuple of (income_statements, balance_sheets, cash_flow_statements)
    """
    try:
        # Fetch income statement
        url = f"{FMP_API_BASE}/income-statement"
        params = {'symbol': ticker, 'period': period, 'limit': limit, 'apikey': api_key}
        response = requests.get(url, params=params, timeout=30)
        income_statements = response.json() if response.status_code == 200 else None
        
        # Fetch balance sheet
        url = f"{FMP_API_BASE}/balance-sheet-statement"
        params = {'symbol': ticker, 'period': period, 'limit': limit, 'apikey': api_key}
        response = requests.get(url, params=params, timeout=30)
        balance_sheets = response.json() if response.status_code == 200 else None
        
        # Fetch cash flow statement
        url = f"{FMP_API_BASE}/cash-flow-statement"
        params = {'symbol': ticker, 'period': period, 'limit': limit, 'apikey': api_key}
        response = requests.get(url, params=params, timeout=30)
        cash_flows = response.json() if response.status_code == 200 else None
        
        return income_statements, balance_sheets, cash_flows
    except Exception as e:
        print(f"Error fetching financial statements: {e}")
        return None, None, None


def calculate_key_metrics(
    income_statements: List[Dict],
    balance_sheets: List[Dict],
    cash_flows: List[Dict],
    market_cap: float = None,
    shares_outstanding: float = None,
    current_price: float = None
) -> Dict[str, Dict]:
    """
    Calculate key metrics from financial statements.
    
    Args:
        income_statements: List of income statement dicts (most recent first)
        balance_sheets: List of balance sheet dicts (most recent first)
        cash_flows: List of cash flow dicts (most recent first)
        market_cap: Current market cap
        shares_outstanding: Current shares outstanding
        current_price: Current stock price
        
    Returns:
        Dictionary with fiscal years as keys and metrics as values
    """
    metrics = {}
    
    # Process each year (assuming statements are sorted most recent first)
    num_years = min(len(income_statements), len(balance_sheets), len(cash_flows))
    
    for i in range(num_years):
        income = income_statements[i]
        balance = balance_sheets[i]
        cashflow = cash_flows[i]
        
        # Extract fiscal year from date field (format: YYYY-MM-DD)
        date_str = income.get('date', '')
        if date_str:
            fiscal_year = date_str[:4]  # Extract year from date string
        else:
            fiscal_year = income.get('calendarYear', '')
        
        if not fiscal_year:
            continue
        
        # Extract key values
        revenue = income.get('revenue', 0) or 0
        ebitda = income.get('ebitda', 0) or 0
        ebit = income.get('operatingIncome', income.get('ebit', 0)) or 0
        net_income = income.get('netIncome', 0) or 0
        # Adjusted values (using reported if adjusted not available)
        adj_ebitda = income.get('ebitda', 0) or ebitda
        adj_ebit = income.get('operatingIncome', income.get('ebit', 0)) or ebit
        adj_net_income = income.get('netIncome', 0) or net_income
        
        # Cash flow items
        cfo = cashflow.get('operatingCashFlow', 0) or 0
        capex = abs(cashflow.get('capitalExpenditure', 0) or 0)
        fcff = cfo - capex
        
        # Balance sheet items
        total_debt = balance.get('totalDebt', 0) or 0
        cash = balance.get('cashAndCashEquivalents', 0) or 0
        net_debt = total_debt - cash
        total_equity = balance.get('totalStockholdersEquity', 0) or 0
        total_assets = balance.get('totalAssets', 0) or 0
        
        # Tax and interest
        income_tax = abs(income.get('incomeTaxExpense', 0) or 0)
        interest_expense = abs(income.get('interestExpense', 0) or 0)
        adj_tax_rate = (income_tax / (adj_net_income + income_tax)) * 100 if (adj_net_income + income_tax) > 0 else 0
        
        # Calculate metrics
        net_margin = (adj_net_income / revenue * 100) if revenue > 0 else 0
        ebitda_margin = (adj_ebitda / revenue * 100) if revenue > 0 else 0
        ebit_margin = (adj_ebit / revenue * 100) if revenue > 0 else 0
        
        # EPS (using shares outstanding if available, otherwise estimate)
        shares = shares_outstanding or (market_cap / current_price if market_cap and current_price else 0)
        adj_eps = (adj_net_income / shares) if shares > 0 else 0
        
        # Growth rates (year-over-year)
        revenue_growth = 0
        ebitda_growth = 0
        eps_growth = 0
        if i < num_years - 1:
            prev_revenue = income_statements[i+1].get('revenue', 0) or 0
            prev_ebitda = income_statements[i+1].get('ebitda', 0) or 0
            prev_net_income = income_statements[i+1].get('netIncome', 0) or 0
            prev_shares = shares  # Simplified
            prev_eps = (prev_net_income / prev_shares) if prev_shares > 0 else 0
            
            revenue_growth = ((revenue - prev_revenue) / prev_revenue * 100) if prev_revenue > 0 else 0
            ebitda_growth = ((adj_ebitda - prev_ebitda) / prev_ebitda * 100) if prev_ebitda > 0 else 0
            eps_growth = ((adj_eps - prev_eps) / prev_eps * 100) if prev_eps > 0 else 0
        
        # Ratios
        interest_cover = (adj_ebit / interest_expense) if interest_expense > 0 else None
        net_debt_equity = (net_debt / total_equity * 100) if total_equity > 0 else None
        net_debt_ebitda = (net_debt / adj_ebitda) if adj_ebitda > 0 else None
        
        # ROCE and ROE
        roce = (adj_ebit / (total_assets - cash) * 100) if (total_assets - cash) > 0 else 0
        roe = (adj_net_income / total_equity * 100) if total_equity > 0 else 0
        
        # Valuation metrics (if market data available)
        ev = market_cap + net_debt if market_cap else None
        fcff_yield = (fcff / ev * 100) if ev and ev > 0 else None
        ev_ebitda = (ev / adj_ebitda) if ev and adj_ebitda > 0 else None
        ev_revenue = (ev / revenue) if ev and revenue > 0 else None
        adj_pe = (current_price / adj_eps) if current_price and adj_eps > 0 else None
        
        metrics[fiscal_year] = {
            'revenue': revenue / 1e6,  # Convert to millions
            'adj_ebitda': adj_ebitda / 1e6,
            'adj_ebit': adj_ebit / 1e6,
            'adj_net_income': adj_net_income / 1e6,
            'net_margin': net_margin,
            'adj_eps': adj_eps,
            'cfo': cfo / 1e6,
            'fcff': fcff / 1e6,
            'revenue_growth': revenue_growth,
            'ebitda_margin': ebitda_margin,
            'ebitda_growth': ebitda_growth,
            'ebit_margin': ebit_margin,
            'adj_eps_growth': eps_growth,
            'adj_tax_rate': adj_tax_rate,
            'interest_cover': interest_cover,
            'net_debt_equity': net_debt_equity,
            'net_debt_ebitda': net_debt_ebitda,
            'roce': roce,
            'roe': roe,
            'fcff_yield': fcff_yield,
            'dividend_yield': None,  # Not available from statements
            'ev_ebitda': ev_ebitda,
            'ev_revenue': ev_revenue,
            'adj_pe': adj_pe,
        }
    
    return metrics


def forecast_next_fiscal_year(
    latest_metrics: Dict,
    previous_metrics: Dict = None
) -> Dict:
    """
    Forecast next fiscal year metrics using latest year as proxy.
    This is a placeholder function that will be replaced with LLM-based forecasting.
    
    Args:
        latest_metrics: Metrics for the most recent fiscal year
        previous_metrics: Metrics for the previous fiscal year (optional, for trend analysis)
        
    Returns:
        Dictionary with forecasted metrics for next fiscal year
    """
    # For now, use latest year as proxy (simple placeholder)
    # In the future, this will use LLM to generate intelligent forecasts
    
    forecast = {}
    
    # List of forecast items that need to be generated
    forecast_items = [
        'revenue', 'adj_ebitda', 'adj_ebit', 'adj_net_income', 'net_margin',
        'adj_eps', 'cfo', 'fcff', 'revenue_growth', 'ebitda_margin',
        'ebitda_growth', 'ebit_margin', 'adj_eps_growth', 'adj_tax_rate',
        'interest_cover', 'net_debt_equity', 'net_debt_ebitda', 'roce', 'roe',
        'fcff_yield', 'dividend_yield', 'ev_ebitda', 'ev_revenue', 'adj_pe'
    ]
    
    # Simple proxy: use latest year values
    # Growth rates are set to 0 or calculated from trend if previous year available
    for item in forecast_items:
        if item in latest_metrics:
            if item.endswith('_growth'):
                # For growth metrics, use average of recent growth or 0
                if previous_metrics and item in previous_metrics:
                    # Simple trend: maintain similar growth rate
                    forecast[item] = latest_metrics.get(item, 0)
                else:
                    forecast[item] = 0  # No growth assumption
            elif item in ['net_margin', 'ebitda_margin', 'ebit_margin', 'adj_tax_rate', 
                         'roce', 'roe', 'fcff_yield', 'dividend_yield']:
                # Margins and rates: use latest year
                forecast[item] = latest_metrics.get(item, 0)
            elif item in ['interest_cover', 'net_debt_equity', 'net_debt_ebitda', 
                         'ev_ebitda', 'ev_revenue', 'adj_pe']:
                # Ratios: use latest year (may be None)
                forecast[item] = latest_metrics.get(item)
            else:
                # Absolute values: use latest year as proxy
                forecast[item] = latest_metrics.get(item, 0)
        else:
            forecast[item] = None
    
    return forecast


def check_key_metrics_cache(
    ticker: str,
    db_path: str = None
) -> Optional[Dict]:
    """
    Check if key metrics data exists in cache.
    
    Args:
        ticker: Stock ticker symbol
        db_path: Path to database. If None, uses default.
        
    Returns:
        Dictionary with cached metrics data, or None if not found.
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)
    
    if not Path(db_path).exists():
        return None
    
    cache_id = f"{ticker}_key_metrics"
    
    try:
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute(
            'SELECT metrics_data FROM key_metrics WHERE id = ?',
            (cache_id,)
        )
        result = c.fetchone()
        conn.close()
        
        if result and result[0]:
            try:
                return json.loads(result[0])
            except json.JSONDecodeError:
                return None
    except Exception as e:
        print(f"Error checking key metrics cache: {e}")
    
    return None


def save_key_metrics(
    db_path: str,
    ticker: str,
    metrics_data: Dict,
    fiscal_year_end: str = None
) -> bool:
    """
    Save key metrics data to database.
    
    Args:
        db_path: Path to database
        ticker: Stock ticker symbol
        metrics_data: Dictionary with all metrics data
        fiscal_year_end: Fiscal year end month (e.g., 'Dec')
        
    Returns:
        True if successful, False otherwise
    """
    cache_id = f"{ticker}_key_metrics"
    created_at = datetime.now().isoformat()
    
    try:
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        
        c.execute('''
        INSERT OR REPLACE INTO key_metrics 
        (id, ticker, fiscal_year_end, metrics_data, created_at)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            cache_id,
            ticker,
            fiscal_year_end or 'Dec',
            json.dumps(metrics_data),
            created_at
        ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving key metrics: {e}")
        return False


def pull_key_metrics(
    ticker: str,
    db_path: str = None,
    market_cap: float = None,
    shares_outstanding: float = None,
    current_price: float = None,
    use_openai_forecast: bool = True,
    model_name: str = None,
    temperature: float = 0.3
) -> Optional[Dict]:
    """
    Pull key metrics data for a ticker (with caching and forecasting).
    
    Args:
        ticker: Stock ticker symbol
        db_path: Path to database
        market_cap: Current market cap (for valuation metrics)
        shares_outstanding: Current shares outstanding
        current_price: Current stock price
        use_openai_forecast: If True, use OpenAI-based forecasting (default: True)
        model_name: OpenAI model name (only used if use_openai_forecast=True)
        temperature: Temperature for OpenAI generation (only used if use_openai_forecast=True)
        
    Returns:
        Dictionary with metrics for past 2 years and forecast for next year
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)
    
    # Initialize database tables
    init_tables(db_path)
    
    # Check cache first
    cached = check_key_metrics_cache(ticker, db_path)
    if cached:
        print("Using cached key metrics data")
        # If using OpenAI forecast and forecasts don't exist, generate them
        if use_openai_forecast:
            # Determine latest actual year from cached data
            # We need to identify which years are actual (from API) vs forecast
            # Strategy: Fetch fresh data from API to see what the latest actual year is
            # Then compare with cache to see if forecasts are needed
            print("Checking if forecasts need to be generated...")
            income_statements, balance_sheets, cash_flows = fetch_financial_statements_fmp(
                ticker, FMP_API_KEY, period='annual', limit=3
            )
            
            if income_statements and balance_sheets and cash_flows:
                # Calculate metrics to get actual years from API
                temp_metrics = calculate_key_metrics(
                    income_statements, balance_sheets, cash_flows,
                    market_cap, shares_outstanding, current_price
                )
                actual_years_from_api = sorted(temp_metrics.keys(), reverse=True, key=int)
                
                if len(actual_years_from_api) >= 2:
                    latest_actual_year = actual_years_from_api[0]  # Most recent actual year from API
                    forecast_year_1 = str(int(latest_actual_year) + 1)
                    forecast_year_2 = str(int(latest_actual_year) + 2)
                    
                    print(f"Latest actual fiscal year from API: {latest_actual_year}")
                    print(f"Forecast years needed: {forecast_year_1}, {forecast_year_2}")
                    
                    # Check if forecasts exist in cache
                    if forecast_year_1 not in cached or forecast_year_2 not in cached:
                        print("Generating missing forecasts using OpenAI...")
                        try:
                            from agentic.financial_forecastor import generate_forecast_for_years
                            forecasts = generate_forecast_for_years(
                                ticker=ticker,
                                latest_actual_year=latest_actual_year,
                                forecast_years=[forecast_year_1, forecast_year_2],
                                db_path=db_path,
                                model_name=model_name,
                                temperature=temperature,
                                force_regenerate=False
                            )
                            if forecasts:
                                cached.update(forecasts)
                                save_key_metrics(db_path, ticker, cached)
                                print("Forecasts generated and saved to cache")
                        except Exception as e:
                            print(f"Warning: Could not generate OpenAI forecasts: {e}")
                            print("Falling back to simple forecast method")
                            import traceback
                            traceback.print_exc()
        return cached
    
    # Fetch from API
    print(f"Fetching key metrics from FMP API for {ticker}...")
    income_statements, balance_sheets, cash_flows = fetch_financial_statements_fmp(
        ticker, FMP_API_KEY, period='annual', limit=3
    )
    
    if not (income_statements and balance_sheets and cash_flows):
        print("Failed to fetch financial statements")
        return None
    
    # Calculate metrics for past years (only actual API data)
    metrics = calculate_key_metrics(
        income_statements, balance_sheets, cash_flows,
        market_cap, shares_outstanding, current_price
    )
    
    # Get actual years from API (sorted, most recent first)
    # These are the actual fiscal years from financial statements
    actual_years = sorted(metrics.keys(), reverse=True, key=int)
    
    if len(actual_years) < 2:
        print("Not enough actual years of data")
        return metrics
    
    # Determine latest complete fiscal year from financial statements
    # The most recent year in the API data is the latest actual fiscal year
    latest_actual_year = actual_years[0]
    previous_actual_year = actual_years[1]
    
    # Calculate forecast years: next 2 fiscal years after latest actual
    forecast_year_1 = str(int(latest_actual_year) + 1)
    forecast_year_2 = str(int(latest_actual_year) + 2)
    
    print(f"Latest actual fiscal year: {latest_actual_year}")
    print(f"Previous actual fiscal year: {previous_actual_year}")
    print(f"Forecast years needed: {forecast_year_1}, {forecast_year_2}")
    
    # Store only actual data first
    result = {
        previous_actual_year: metrics[previous_actual_year],  # 2 years ago (actual)
        latest_actual_year: metrics[latest_actual_year],  # Latest year (actual)
    }
    
    # Save actual data first so forecast function can access it
    save_key_metrics(db_path, ticker, result)
    print("Actual key metrics data saved to cache")
    
    # Generate forecasts using OpenAI if requested, otherwise use simple method
    if use_openai_forecast:
        try:
            from agentic.financial_forecastor import generate_forecast_for_years
            print(f"Generating forecasts using OpenAI for {ticker}...")
            print(f"  Latest actual fiscal year: {latest_actual_year}")
            print(f"  Forecasting fiscal years: {forecast_year_1}, {forecast_year_2}")
            
            # Generate forecasts for the specific years needed
            forecasts = generate_forecast_for_years(
                ticker=ticker,
                latest_actual_year=latest_actual_year,
                forecast_years=[forecast_year_1, forecast_year_2],
                db_path=db_path,
                model_name=model_name,
                temperature=temperature,
                force_regenerate=False
            )
            
            if forecasts:
                if forecast_year_1 in forecasts:
                    result[forecast_year_1] = forecasts[forecast_year_1]
                    print(f"Forecast for FY{forecast_year_1[-2:]} generated successfully")
                if forecast_year_2 in forecasts:
                    result[forecast_year_2] = forecasts[forecast_year_2]
                    print(f"Forecast for FY{forecast_year_2[-2:]} generated successfully")
            else:
                print("Warning: OpenAI forecast failed, using simple method")
                # Fall back to simple forecast
                forecast_1 = forecast_next_fiscal_year(
                    metrics[latest_actual_year],
                    metrics.get(previous_actual_year)
                )
                result[forecast_year_1] = forecast_1
                
                forecast_2 = forecast_next_fiscal_year(
                    result.get(forecast_year_1, metrics[latest_actual_year]),
                    metrics[latest_actual_year]
                )
                result[forecast_year_2] = forecast_2
            
        except Exception as e:
            print(f"Warning: OpenAI forecast failed: {e}")
            print("Falling back to simple forecast method")
            # Fall back to simple forecast
            forecast_1 = forecast_next_fiscal_year(
                metrics[latest_actual_year],
                metrics.get(previous_actual_year)
            )
            result[forecast_year_1] = forecast_1
            
            forecast_2 = forecast_next_fiscal_year(
                result.get(forecast_year_1, metrics[latest_actual_year]),
                metrics[latest_actual_year]
            )
            result[forecast_year_2] = forecast_2
    else:
        # Use simple forecast method
        forecast_1 = forecast_next_fiscal_year(
            metrics[latest_actual_year],
            metrics.get(previous_actual_year)
        )
        result[forecast_year_1] = forecast_1
        
        forecast_2 = forecast_next_fiscal_year(
            result.get(forecast_year_1, metrics[latest_actual_year]),
            metrics[latest_actual_year]
        )
        result[forecast_year_2] = forecast_2
    
    # Save to cache with forecasts
    save_key_metrics(db_path, ticker, result)
    print("Key metrics data with forecasts saved to cache")
    
    return result


def pull_tesla_data(
    ticker: str = 'TSLA',
    base_index: str = 'SPY',
    end_date: str = None,
    start_date: str = None,
    as_of_date: str = None,
    db_path: str = None,
    use_openai_forecast: bool = True,
    model_name: str = None,
    temperature: float = 0.3
) -> Dict:
    """
    Main function to pull data for Tesla (or any ticker).
    
    Args:
        ticker: Stock ticker symbol (default: 'TSLA')
        base_index: Base index symbol (default: 'SPY')
        end_date: End date for price performance (default: today)
        start_date: Start date for price performance (default: today - 1 year)
        as_of_date: Date for company data snapshot (default: today)
        db_path: Path to database (default: finrpt/source/cache.db)
        
    Returns:
        Dictionary with 'price_performance' and 'company_data' keys
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)
    
    # Initialize database tables
    init_tables(db_path)
    
    # Set default dates
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    if as_of_date is None:
        as_of_date = datetime.now().strftime('%Y-%m-%d')
    
    result = {
        'price_performance': None,
        'company_data': None,
        'key_metrics': None
    }
    
    # Fetch S1: Price Performance
    print(f"Fetching price performance for {ticker} vs {base_index}...")
    cached_pp = check_price_performance_cache(ticker, start_date, end_date, base_index, db_path)
    
    if cached_pp:
        print("Using cached price performance data")
        result['price_performance'] = cached_pp
    else:
        print("Fetching price performance from FMP API...")
        stock_data, index_data = fetch_price_performance_fmp(
            ticker, base_index, start_date, end_date, FMP_API_KEY
        )
        
        if stock_data and index_data:
            save_price_performance(
                db_path, ticker, base_index, start_date, end_date,
                stock_data, index_data
            )
            result['price_performance'] = {
                'stock_data': stock_data,
                'index_data': index_data
            }
            print("Price performance data saved to cache")
        else:
            print("Failed to fetch price performance data")
    
    # Fetch S2: Company Data
    print(f"Fetching company data for {ticker} as of {as_of_date}...")
    cached_cd = check_company_data_cache(ticker, as_of_date, db_path)
    
    market_cap = None
    shares_outstanding = None
    current_price = None
    
    if cached_cd:
        print("Using cached company data")
        result['company_data'] = cached_cd
        market_cap = cached_cd.get('market_cap')
        shares_outstanding = cached_cd.get('shares_outstanding')
        # Estimate current price from market cap and shares
        if market_cap and shares_outstanding:
            current_price = market_cap / shares_outstanding
    else:
        print("Fetching company data from FMP API...")
        company_data = fetch_company_data_fmp(ticker, as_of_date, FMP_API_KEY)
        
        if company_data:
            save_company_data(db_path, ticker, as_of_date, company_data)
            result['company_data'] = company_data
            market_cap = company_data.get('market_cap')
            shares_outstanding = company_data.get('shares_outstanding')
            if market_cap and shares_outstanding:
                current_price = market_cap / shares_outstanding
            print("Company data saved to cache")
        else:
            print("Failed to fetch company data")
    
    # Fetch S3: Key Metrics
    print(f"Fetching key metrics for {ticker}...")
    key_metrics = pull_key_metrics(
        ticker, db_path, market_cap, shares_outstanding, current_price,
        use_openai_forecast=use_openai_forecast,
        model_name=model_name,
        temperature=temperature
    )
    result['key_metrics'] = key_metrics
    
    return result


if __name__ == '__main__':
    # Pull data for Tesla
    print("=" * 60)
    print("FMP Data Puller for Tesla")
    print("=" * 60)
    
    data = pull_tesla_data()
    
    print("\n" + "=" * 60)
    print("Data Pull Complete")
    print("=" * 60)
    
    if data['price_performance']:
        stock_points = len(data['price_performance']['stock_data'])
        index_points = len(data['price_performance']['index_data'])
        print(f"\nPrice Performance: {stock_points} stock points, {index_points} index points")
    
    if data['company_data']:
        print(f"\nCompany Data:")
        print(f"  Market Cap: ${data['company_data'].get('market_cap', 0):,.0f}")
        print(f"  Shares Outstanding: {data['company_data'].get('shares_outstanding', 0):,.0f}")
        print(f"  52W High: ${data['company_data'].get('52w_high', 0):.2f}")
        print(f"  52W Low: ${data['company_data'].get('52w_low', 0):.2f}")
        print(f"  Volatility (90d): {data['company_data'].get('volatility_90d', 0):.2f}%")
        print(f"  Consensus Rating: {data['company_data'].get('consensus_rating', 'N/A')}")
        print(f"  Number of Analysts: {data['company_data'].get('num_analysts', 0)}")
