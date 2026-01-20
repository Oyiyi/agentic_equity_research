#!/usr/bin/env python
"""
Financial Forecastor Agent using OpenAI API

This script pulls all available information from cache.db and uses OpenAI API
to generate intelligent financial forecasts for the next fiscal year.
The forecasts are saved back to cache.db, clearly marked as forecasted data.
"""

import os
import sys
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import dotenv

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import OpenAI model
from agentic.openai_model import OpenAIModel

# Load .env file
env_path = project_root / '.env'
if env_path.exists():
    dotenv.load_dotenv(dotenv_path=str(env_path), override=True)
else:
    dotenv.load_dotenv(override=True)

# Database path (following existing pattern)
DEFAULT_DB_PATH = project_root / 'finrpt' / 'source' / 'cache.db'


def load_all_data_from_cache(
    ticker: str,
    db_path: str = None
) -> Dict:
    """
    Load all available data from cache.db for a given ticker.
    
    Args:
        ticker: Stock ticker symbol
        db_path: Path to database. If None, uses default.
        
    Returns:
        Dictionary containing:
        - key_metrics: Historical financial metrics
        - company_data: Company information
        - price_performance: Price performance data (if available)
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)
    
    if not Path(db_path).exists():
        print(f"Database not found at {db_path}")
        return {}
    
    result = {
        'key_metrics': None,
        'company_data': None,
        'price_performance': None
    }
    
    try:
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        
        # Load key metrics
        cache_id = f"{ticker}_key_metrics"
        c.execute(
            'SELECT metrics_data, fiscal_year_end FROM key_metrics WHERE id = ?',
            (cache_id,)
        )
        metrics_result = c.fetchone()
        if metrics_result and metrics_result[0]:
            try:
                result['key_metrics'] = {
                    'metrics': json.loads(metrics_result[0]),
                    'fiscal_year_end': metrics_result[1] or 'Dec'
                }
            except json.JSONDecodeError:
                pass
        
        # Load company data (get most recent)
        c.execute(
            '''SELECT as_of_date, shares_outstanding, market_cap, currency, fx_rate,
               free_float_pct, avg_daily_volume_3m_shares, avg_daily_volume_3m_usd,
               volatility_90d, "52w_high", "52w_low", primary_index_name,
               analyst_rating_counts, consensus_rating, num_analysts
               FROM company_data WHERE ticker = ? ORDER BY as_of_date DESC LIMIT 1''',
            (ticker,)
        )
        company_result = c.fetchone()
        if company_result:
            result['company_data'] = {
                'as_of_date': company_result[0],
                'shares_outstanding': company_result[1],
                'market_cap': company_result[2],
                'currency': company_result[3],
                'fx_rate': company_result[4] or 1.0,
                'free_float_pct': company_result[5],
                'avg_daily_volume_3m_shares': company_result[6],
                'avg_daily_volume_3m_usd': company_result[7],
                'volatility_90d': company_result[8],
                '52w_high': company_result[9],
                '52w_low': company_result[10],
                'primary_index_name': company_result[11],
                'analyst_rating_counts': json.loads(company_result[12]) if company_result[12] else {},
                'consensus_rating': company_result[13],
                'num_analysts': company_result[14] or 0
            }
        
        # Load price performance (get most recent)
        c.execute(
            '''SELECT start_date, end_date, base_index, stock_data, index_data
               FROM price_performance WHERE ticker = ? ORDER BY end_date DESC LIMIT 1''',
            (ticker,)
        )
        price_result = c.fetchone()
        if price_result and price_result[3] and price_result[4]:
            try:
                result['price_performance'] = {
                    'start_date': price_result[0],
                    'end_date': price_result[1],
                    'base_index': price_result[2],
                    'stock_data': json.loads(price_result[3]),
                    'index_data': json.loads(price_result[4])
                }
            except json.JSONDecodeError:
                pass
        
        conn.close()
        
    except Exception as e:
        print(f"Error loading data from cache: {e}")
        if conn:
            conn.close()
    
    return result


def prepare_forecast_prompt(
    ticker: str,
    all_data: Dict
) -> str:
    """
    Prepare a comprehensive prompt for OpenAI to generate financial forecasts.
    
    Args:
        ticker: Stock ticker symbol
        all_data: Dictionary containing all cached data
        
    Returns:
        Formatted prompt string for OpenAI
    """
    prompt_parts = []
    
    # Header
    prompt_parts.append(f"You are a financial analyst tasked with forecasting financial metrics for {ticker} for the next fiscal year.")
    prompt_parts.append("\n## Historical Financial Data\n")
    
    # Key metrics
    if all_data.get('key_metrics') and all_data['key_metrics'].get('metrics'):
        metrics = all_data['key_metrics']['metrics']
        fiscal_year_end = all_data['key_metrics'].get('fiscal_year_end', 'Dec')
        
        # Separate actual and forecast years
        all_years = sorted(metrics.keys(), reverse=True, key=lambda x: int(x) if x.isdigit() else 0)
        current_year = int(datetime.now().strftime('%Y'))
        
        actual_years = [y for y in all_years if y.isdigit() and int(y) <= current_year]
        actual_years = sorted(actual_years, reverse=True, key=int)[:3]  # Get up to 3 most recent actual years
        
        # Get forecast years (future years that are already forecasted)
        forecast_years = [y for y in all_years if y.isdigit() and int(y) > current_year]
        forecast_years = sorted(forecast_years, key=int)  # Sort ascending to show progression
        
        prompt_parts.append(f"### Historical Key Metrics (Fiscal Year End: {fiscal_year_end})\n")
        
        for year in actual_years:
            year_data = metrics[year]
            prompt_parts.append(f"\n**FY{year[-2:]} (Actual):**")
            prompt_parts.append(f"- Revenue: ${year_data.get('revenue', 0):,.0f}M")
            prompt_parts.append(f"- Adj. EBITDA: ${year_data.get('adj_ebitda', 0):,.0f}M")
            prompt_parts.append(f"- Adj. EBIT: ${year_data.get('adj_ebit', 0):,.0f}M")
            prompt_parts.append(f"- Adj. Net Income: ${year_data.get('adj_net_income', 0):,.0f}M")
            prompt_parts.append(f"- Net Margin: {year_data.get('net_margin', 0):.1f}%")
            prompt_parts.append(f"- EBITDA Margin: {year_data.get('ebitda_margin', 0):.1f}%")
            prompt_parts.append(f"- EBIT Margin: {year_data.get('ebit_margin', 0):.1f}%")
            prompt_parts.append(f"- Adj. EPS: ${year_data.get('adj_eps', 0):.2f}")
            prompt_parts.append(f"- Revenue Growth Y/Y: {year_data.get('revenue_growth', 0):.1f}%")
            prompt_parts.append(f"- EBITDA Growth Y/Y: {year_data.get('ebitda_growth', 0):.1f}%")
            prompt_parts.append(f"- EPS Growth Y/Y: {year_data.get('adj_eps_growth', 0):.1f}%")
            prompt_parts.append(f"- CFO: ${year_data.get('cfo', 0):,.0f}M")
            prompt_parts.append(f"- FCFF: ${year_data.get('fcff', 0):,.0f}M")
            prompt_parts.append(f"- ROCE: {year_data.get('roce', 0):.1f}%")
            prompt_parts.append(f"- ROE: {year_data.get('roe', 0):.1f}%")
            if year_data.get('net_debt_ebitda') is not None:
                prompt_parts.append(f"- Net Debt/EBITDA: {year_data.get('net_debt_ebitda', 0):.1f}x")
        
        # Include previous forecasts if available (for multi-year forecasting)
        if forecast_years:
            prompt_parts.append(f"\n### Previous Forecasts\n")
            for year in forecast_years:
                year_data = metrics[year]
                prompt_parts.append(f"\n**FY{year[-2:]} (Forecast):**")
                prompt_parts.append(f"- Revenue: ${year_data.get('revenue', 0):,.0f}M")
                prompt_parts.append(f"- Adj. EBITDA: ${year_data.get('adj_ebitda', 0):,.0f}M")
                prompt_parts.append(f"- Adj. Net Income: ${year_data.get('adj_net_income', 0):,.0f}M")
                prompt_parts.append(f"- Revenue Growth Y/Y: {year_data.get('revenue_growth', 0):.1f}%")
                prompt_parts.append(f"- EBITDA Margin: {year_data.get('ebitda_margin', 0):.1f}%")
                prompt_parts.append(f"- Adj. EPS: ${year_data.get('adj_eps', 0):.2f}")
    
    # Company data
    if all_data.get('company_data'):
        cd = all_data['company_data']
        prompt_parts.append(f"\n### Company Information (as of {cd.get('as_of_date')})")
        prompt_parts.append(f"- Market Cap: ${cd.get('market_cap', 0):,.0f}")
        prompt_parts.append(f"- Shares Outstanding: {cd.get('shares_outstanding', 0):,.0f}")
        prompt_parts.append(f"- 52W High: ${cd.get('52w_high', 0):.2f}")
        prompt_parts.append(f"- 52W Low: ${cd.get('52w_low', 0):.2f}")
        prompt_parts.append(f"- Volatility (90d): {cd.get('volatility_90d', 0):.2f}%")
        if cd.get('consensus_rating'):
            prompt_parts.append(f"- Analyst Consensus: {cd.get('consensus_rating')} ({cd.get('num_analysts', 0)} analysts)")
    
    # Price performance context
    if all_data.get('price_performance'):
        pp = all_data['price_performance']
        prompt_parts.append(f"\n### Price Performance Context")
        prompt_parts.append(f"- Period: {pp.get('start_date')} to {pp.get('end_date')}")
        prompt_parts.append(f"- Base Index: {pp.get('base_index')}")
        if pp.get('stock_data'):
            stock_data = pp['stock_data']
            if len(stock_data) > 0:
                latest_price = stock_data[-1].get('close', 0)
                first_price = stock_data[0].get('close', 0)
                if first_price > 0:
                    total_return = ((latest_price - first_price) / first_price) * 100
                    prompt_parts.append(f"- Total Return: {total_return:.1f}%")
    
    # Instructions
    prompt_parts.append("\n## Forecasting Task\n")
    prompt_parts.append("Based on the historical financial data above, provide a forecast for the NEXT fiscal year.")
    prompt_parts.append("Consider:")
    prompt_parts.append("1. Historical growth trends and patterns")
    prompt_parts.append("2. Margin stability or changes")
    prompt_parts.append("3. Industry context and economic conditions")
    prompt_parts.append("4. Company-specific factors")
    prompt_parts.append("\nProvide your forecast as a JSON object with the following structure:")
    prompt_parts.append("""
{
  "revenue": <number in millions>,
  "adj_ebitda": <number in millions>,
  "adj_ebit": <number in millions>,
  "adj_net_income": <number in millions>,
  "net_margin": <percentage>,
  "adj_eps": <number>,
  "cfo": <number in millions>,
  "fcff": <number in millions>,
  "revenue_growth": <percentage>,
  "ebitda_margin": <percentage>,
  "ebitda_growth": <percentage>,
  "ebit_margin": <percentage>,
  "adj_eps_growth": <percentage>,
  "adj_tax_rate": <percentage>,
  "interest_cover": <number or null>,
  "net_debt_equity": <percentage or null>,
  "net_debt_ebitda": <number or null>,
  "roce": <percentage>,
  "roe": <percentage>,
  "fcff_yield": <percentage or null>,
  "dividend_yield": null,
  "ev_ebitda": <number or null>,
  "ev_revenue": <number or null>,
  "adj_pe": <number or null>
}
""")
    prompt_parts.append("\nImportant: Return ONLY valid JSON, no additional text or explanation.")
    
    return "\n".join(prompt_parts)


def generate_forecast_with_openai(
    ticker: str,
    all_data: Dict,
    model_name: str = None,
    temperature: float = 0.3
) -> Optional[Dict]:
    """
    Generate financial forecast using OpenAI API.
    
    Args:
        ticker: Stock ticker symbol
        all_data: Dictionary containing all cached data
        model_name: OpenAI model name (default: from env or 'gpt-4')
        temperature: Temperature for generation (default: 0.3 for more deterministic)
        
    Returns:
        Dictionary with forecasted metrics, or None on error
    """
    try:
        # Initialize OpenAI model
        model = OpenAIModel(
            model_name=model_name or os.getenv('OPENAI_MODEL', 'gpt-4'),
            temperature=temperature
        )
        
        # Prepare prompt
        prompt = prepare_forecast_prompt(ticker, all_data)
        
        print(f"Generating forecast for {ticker} using OpenAI...")
        print("Prompt length:", len(prompt), "characters")
        
        # Get response
        # json_prompt returns (response_tuple, response_json) where response_tuple is (content, prompt_tokens, completion_tokens)
        response_tuple, response_json = model.json_prompt(prompt)
        
        # Extract token usage
        _, prompt_tokens, completion_tokens = response_tuple
        
        print(f"Forecast generated (tokens: {prompt_tokens} prompt + {completion_tokens} completion)")
        
        # Validate and return forecast
        if isinstance(response_json, dict):
            return response_json
        else:
            print(f"Error: Expected dict, got {type(response_json)}")
            print(f"Response: {response_json}")
            return None
            
    except Exception as e:
        print(f"Error generating forecast with OpenAI: {e}")
        import traceback
        traceback.print_exc()
        return None


def save_forecast_to_cache(
    ticker: str,
    forecast_year: str,
    forecast_data: Dict,
    db_path: str = None
) -> bool:
    """
    Save forecast data to cache.db, updating the key_metrics table.
    Forecasts are stored in the same structure as actual data but with future year keys.
    
    Args:
        ticker: Stock ticker symbol
        forecast_year: Fiscal year for the forecast (e.g., "2025")
        forecast_data: Dictionary with forecasted metrics
        db_path: Path to database. If None, uses default.
        
    Returns:
        True if successful, False otherwise
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)
    
    if not Path(db_path).exists():
        print(f"Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        
        # Load existing metrics
        cache_id = f"{ticker}_key_metrics"
        c.execute(
            'SELECT metrics_data, fiscal_year_end FROM key_metrics WHERE id = ?',
            (cache_id,)
        )
        result = c.fetchone()
        
        if result and result[0]:
            # Update existing metrics
            existing_metrics = json.loads(result[0])
            fiscal_year_end = result[1] or 'Dec'
        else:
            # Create new entry
            existing_metrics = {}
            fiscal_year_end = 'Dec'
        
        # Add forecast (marked by year key - forecasts are future years)
        existing_metrics[forecast_year] = forecast_data
        
        # Save back to database
        created_at = datetime.now().isoformat()
        c.execute('''
        INSERT OR REPLACE INTO key_metrics 
        (id, ticker, fiscal_year_end, metrics_data, created_at)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            cache_id,
            ticker,
            fiscal_year_end,
            json.dumps(existing_metrics),
            created_at
        ))
        
        conn.commit()
        conn.close()
        
        print(f"Forecast for FY{forecast_year[-2:]} saved to cache.db")
        return True
        
    except Exception as e:
        print(f"Error saving forecast to cache: {e}")
        if conn:
            conn.close()
        return False


def generate_forecast_for_years(
    ticker: str,
    latest_actual_year: str,
    forecast_years: List[str],
    db_path: str = None,
    model_name: str = None,
    temperature: float = 0.3,
    force_regenerate: bool = False
) -> Optional[Dict]:
    """
    Generate forecasts for specific fiscal years.
    
    This function is called by fmp_data_puller.py with the correct forecast years
    based on the latest actual fiscal year from financial statements.
    
    Args:
        ticker: Stock ticker symbol
        latest_actual_year: Latest actual fiscal year (e.g., "2024")
        forecast_years: List of fiscal years to forecast (e.g., ["2025", "2026"])
        db_path: Path to database. If None, uses default.
        model_name: OpenAI model name (default: from env or 'gpt-4')
        temperature: Temperature for generation (default: 0.3)
        force_regenerate: If True, regenerate even if forecast exists
        
    Returns:
        Dictionary with forecast_years as keys and forecast data as values
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)
    
    # Load all data from cache
    print(f"Loading data from cache.db for {ticker}...")
    all_data = load_all_data_from_cache(ticker, db_path)
    
    if not all_data.get('key_metrics'):
        print(f"Error: No key metrics data found for {ticker} in cache.db")
        print("Please run fmp_data_puller.py first to populate the database.")
        return None
    
    results = {}
    
    # Generate forecast for each requested year
    for i, forecast_year in enumerate(forecast_years):
        print(f"\nGenerating forecast for FY{forecast_year[-2:]}...")
        
        # Check if forecast already exists
        metrics = all_data['key_metrics']['metrics']
        if not force_regenerate and forecast_year in metrics:
            print(f"Forecast for FY{forecast_year[-2:]} already exists in cache.")
            results[forecast_year] = metrics[forecast_year]
            continue
        
        # For the second forecast year, update metrics to include previous forecast
        if i > 0 and forecast_years[i-1] in results:
            # Update the metrics dict to include previous forecast for context
            all_data['key_metrics']['metrics'][forecast_years[i-1]] = results[forecast_years[i-1]]
            print(f"Using previous forecast (FY{forecast_years[i-1][-2:]}) as context for FY{forecast_year[-2:]}")
        
        # Generate forecast using OpenAI
        forecast = generate_forecast_with_openai(
            ticker, all_data, model_name, temperature
        )
        
        if not forecast:
            print(f"Failed to generate forecast for FY{forecast_year[-2:]}")
            continue
        
        # Save forecast to cache
        if save_forecast_to_cache(ticker, forecast_year, forecast, db_path):
            results[forecast_year] = forecast
            # Reload data for next iteration to include this forecast
            all_data = load_all_data_from_cache(ticker, db_path)
        else:
            print(f"Failed to save forecast for FY{forecast_year[-2:]} to cache")
    
    return results if results else None


def generate_forecast_for_years(
    ticker: str,
    latest_actual_year: str,
    forecast_years: List[str],
    db_path: str = None,
    model_name: str = None,
    temperature: float = 0.3,
    force_regenerate: bool = False
) -> Optional[Dict]:
    """
    Generate forecasts for specific fiscal years.
    
    This function is called by fmp_data_puller.py with the correct forecast years
    based on the latest actual fiscal year from financial statements.
    
    Args:
        ticker: Stock ticker symbol
        latest_actual_year: Latest actual fiscal year (e.g., "2024")
        forecast_years: List of fiscal years to forecast (e.g., ["2025", "2026"])
        db_path: Path to database. If None, uses default.
        model_name: OpenAI model name (default: from env or 'gpt-4')
        temperature: Temperature for generation (default: 0.3)
        force_regenerate: If True, regenerate even if forecast exists
        
    Returns:
        Dictionary with forecast_years as keys and forecast data as values
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)
    
    # Load all data from cache
    print(f"Loading data from cache.db for {ticker}...")
    all_data = load_all_data_from_cache(ticker, db_path)
    
    if not all_data.get('key_metrics'):
        print(f"Error: No key metrics data found for {ticker} in cache.db")
        print("Please run fmp_data_puller.py first to populate the database.")
        return None
    
    results = {}
    
    # Generate forecast for each requested year
    for i, forecast_year in enumerate(forecast_years):
        print(f"\nGenerating forecast for FY{forecast_year[-2:]}...")
        
        # Check if forecast already exists
        metrics = all_data['key_metrics']['metrics']
        if not force_regenerate and forecast_year in metrics:
            print(f"Forecast for FY{forecast_year[-2:]} already exists in cache.")
            results[forecast_year] = metrics[forecast_year]
            continue
        
        # For the second forecast year, update metrics to include previous forecast
        if i > 0 and forecast_years[i-1] in results:
            # Update the metrics dict to include previous forecast for context
            all_data['key_metrics']['metrics'][forecast_years[i-1]] = results[forecast_years[i-1]]
            print(f"Using previous forecast (FY{forecast_years[i-1][-2:]}) as context for FY{forecast_year[-2:]}")
        
        # Generate forecast using OpenAI
        forecast = generate_forecast_with_openai(
            ticker, all_data, model_name, temperature
        )
        
        if not forecast:
            print(f"Failed to generate forecast for FY{forecast_year[-2:]}")
            continue
        
        # Save forecast to cache
        if save_forecast_to_cache(ticker, forecast_year, forecast, db_path):
            results[forecast_year] = forecast
            # Reload data for next iteration to include this forecast
            all_data = load_all_data_from_cache(ticker, db_path)
        else:
            print(f"Failed to save forecast for FY{forecast_year[-2:]} to cache")
    
    return results if results else None


def forecast_next_fiscal_year(
    ticker: str,
    db_path: str = None,
    model_name: str = None,
    temperature: float = 0.3,
    force_regenerate: bool = False,
    years_ahead: int = 1
) -> Optional[Dict]:
    """
    Main function to generate financial forecast for the next fiscal year.
    
    This function:
    1. Loads all available data from cache.db
    2. Uses OpenAI API to generate intelligent forecasts
    3. Saves forecasts back to cache.db
    
    Args:
        ticker: Stock ticker symbol
        db_path: Path to database. If None, uses default.
        model_name: OpenAI model name (default: from env or 'gpt-4')
        temperature: Temperature for generation (default: 0.3)
        force_regenerate: If True, regenerate even if forecast exists
        years_ahead: Number of years ahead to forecast (1 = next year, 2 = year after next, etc.)
        
    Returns:
        Dictionary with forecasted metrics, or None on error
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)
    
    # Load all data from cache
    print(f"Loading data from cache.db for {ticker}...")
    all_data = load_all_data_from_cache(ticker, db_path)
    
    if not all_data.get('key_metrics'):
        print(f"Error: No key metrics data found for {ticker} in cache.db")
        print("Please run fmp_data_puller.py first to populate the database.")
        return None
    
    # Determine forecast year
    metrics = all_data['key_metrics']['metrics']
    all_years = sorted(metrics.keys(), reverse=True, key=lambda x: int(x) if x.isdigit() else 0)
    current_year = int(datetime.now().strftime('%Y'))
    
    # Find latest actual year
    actual_years = [y for y in all_years if y.isdigit() and int(y) <= current_year]
    if not actual_years:
        print("Error: No actual historical years found")
        return None
    
    latest_actual_year = max(actual_years, key=int)
    forecast_year = str(int(latest_actual_year) + years_ahead)
    
    # Check if forecast already exists
    if not force_regenerate and forecast_year in metrics:
        print(f"Forecast for FY{forecast_year[-2:]} already exists in cache.")
        print("Use force_regenerate=True to regenerate.")
        return metrics[forecast_year]
    
    # For years_ahead > 1, we need to use the previous forecast as base
    # Update the metrics to include previous forecasts for context
    if years_ahead > 1:
        prev_forecast_year = str(int(latest_actual_year) + years_ahead - 1)
        if prev_forecast_year in metrics:
            # The previous forecast is already in metrics, so it will be included in the prompt
            print(f"Using previous forecast (FY{prev_forecast_year[-2:]}) as context for FY{forecast_year[-2:]}")
    
    # Generate forecast using OpenAI
    forecast = generate_forecast_with_openai(
        ticker, all_data, model_name, temperature
    )
    
    if not forecast:
        print("Failed to generate forecast")
        return None
    
    # Save forecast to cache
    if save_forecast_to_cache(ticker, forecast_year, forecast, db_path):
        return forecast
    else:
        print("Failed to save forecast to cache")
        return None


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate financial forecasts using OpenAI')
    parser.add_argument('ticker', type=str, help='Stock ticker symbol (e.g., TSLA)')
    parser.add_argument('--db-path', type=str, help='Path to database file')
    parser.add_argument('--model', type=str, help='OpenAI model name (default: from env or gpt-4)')
    parser.add_argument('--temperature', type=float, default=0.3, help='Temperature for generation (default: 0.3)')
    parser.add_argument('--force', action='store_true', help='Force regeneration even if forecast exists')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Financial Forecastor Agent using OpenAI API")
    print("=" * 60)
    
    forecast = forecast_next_fiscal_year(
        ticker=args.ticker,
        db_path=args.db_path,
        model_name=args.model,
        temperature=args.temperature,
        force_regenerate=args.force
    )
    
    if forecast:
        print("\n" + "=" * 60)
        print("Forecast Generated Successfully")
        print("=" * 60)
        print("\nKey Forecasted Metrics:")
        print(f"  Revenue: ${forecast.get('revenue', 0):,.0f}M")
        print(f"  Adj. EBITDA: ${forecast.get('adj_ebitda', 0):,.0f}M")
        print(f"  Adj. Net Income: ${forecast.get('adj_net_income', 0):,.0f}M")
        print(f"  Revenue Growth: {forecast.get('revenue_growth', 0):.1f}%")
        print(f"  EBITDA Margin: {forecast.get('ebitda_margin', 0):.1f}%")
        print(f"  Adj. EPS: ${forecast.get('adj_eps', 0):.2f}")
    else:
        print("\nFailed to generate forecast")
