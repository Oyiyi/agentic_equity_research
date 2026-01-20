#!/usr/bin/env python
"""
FMP Graph Generator

This script reads data saved by fmp_data_puller.py from the SQLite database
and generates various graphs:
- Price Performance: Stock vs Base Index comparison
- Analyst Ratings: Distribution of analyst ratings
- Company Metrics: Key financial metrics visualization
"""

import os
import sys
import sqlite3
import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from matplotlib import dates as mdates
import numpy as np

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Database path (following existing pattern)
DEFAULT_DB_PATH = project_root / 'finrpt' / 'source' / 'cache.db'


def load_graph_config(config_path: str = None) -> Dict:
    """
    Load graph color palette configuration from config.yaml.
    
    Args:
        config_path: Path to config.yaml. If None, uses project_root/config.yaml.
        
    Returns:
        Dictionary with graph palette configuration, or default values if not found.
    """
    if config_path is None:
        config_path = project_root / 'config.yaml'
    else:
        config_path = Path(config_path)
    
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config.get('components', {}).get('report_graph_palette', {})
        except Exception as e:
            print(f"Warning: Could not load graph config: {e}")
    
    # Return default values if config not found
    return {
        'base': {
            'background': '#FFFFFF',
            'grid': '#E6E6E6',
            'axis': '#333333',
            'text_primary': '#111111',
            'text_secondary': '#666666'
        },
        'series': {
            'benchmark': {
                'name': 'Benchmark / Index',
                'color': '#1F77B4',
                'linestyle': '-',
                'linewidth': 2.2
            },
            'stock': {
                'name': 'Stock',
                'color': '#9E1F00',
                'linestyle': '-',
                'linewidth': 3
            }
        },
        'bar_chart': {
            'primary': '#1F77B4',
            'secondary': '#2CB1A1',
            'contrast': '#D4A32F'
        }
    }


def load_price_performance_data(
    ticker: str,
    start_date: str,
    end_date: str,
    db_path: str = None
) -> Optional[Dict]:
    """
    Load price performance data from database.
    
    Args:
        ticker: Stock ticker symbol
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        db_path: Path to database. If None, uses default.
        
    Returns:
        Dictionary with 'stock_data' and 'index_data' keys, or None if not found.
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)
    
    if not Path(db_path).exists():
        print(f"Database not found at {db_path}")
        return None
    
    cache_id = f"{ticker}_{start_date}_{end_date}"
    
    try:
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute(
            '''SELECT ticker, base_index, stock_data, index_data 
               FROM price_performance WHERE id = ?''',
            (cache_id,)
        )
        result = c.fetchone()
        conn.close()
        
        if result and result[2] and result[3]:
            try:
                stock_data = json.loads(result[2])
                index_data = json.loads(result[3])
                return {
                    'ticker': result[0],
                    'base_index': result[1],
                    'stock_data': stock_data,
                    'index_data': index_data
                }
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON data: {e}")
                return None
        else:
            print(f"No price performance data found for {cache_id}")
            return None
    except Exception as e:
        print(f"Error loading price performance data: {e}")
        return None


def load_key_metrics(
    ticker: str,
    db_path: str = None
) -> Optional[Dict]:
    """
    Load key metrics data from database.
    
    Args:
        ticker: Stock ticker symbol
        db_path: Path to database. If None, uses default.
        
    Returns:
        Dictionary with key metrics data, or None if not found.
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)
    
    if not Path(db_path).exists():
        print(f"Database not found at {db_path}")
        return None
    
    cache_id = f"{ticker}_key_metrics"
    
    try:
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute(
            'SELECT metrics_data, fiscal_year_end FROM key_metrics WHERE id = ?',
            (cache_id,)
        )
        result = c.fetchone()
        conn.close()
        
        if result and result[0]:
            try:
                metrics = json.loads(result[0])
                return {
                    'metrics': metrics,
                    'fiscal_year_end': result[1] or 'Dec'
                }
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON data: {e}")
                return None
        else:
            print(f"No key metrics data found for {cache_id}")
            return None
    except Exception as e:
        print(f"Error loading key metrics data: {e}")
        return None


def load_financial_statements(
    ticker: str,
    statement_type: str,
    period: str = 'annual',
    db_path: str = None
) -> Optional[List[Dict]]:
    """
    Load financial statements data from database.
    
    Args:
        ticker: Stock ticker symbol
        statement_type: 'income', 'balance', or 'cashflow'
        period: 'annual' or 'quarter'
        db_path: Path to database. If None, uses default.
        
    Returns:
        List of statement dicts, or None if not found.
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)
    
    if not Path(db_path).exists():
        print(f"Database not found at {db_path}")
        return None
    
    cache_id = f"{ticker}_{statement_type}_{period}"
    
    try:
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute(
            'SELECT statements_data FROM financial_statements WHERE id = ?',
            (cache_id,)
        )
        result = c.fetchone()
        conn.close()
        
        if result and result[0]:
            try:
                return json.loads(result[0])
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON data: {e}")
                return None
        else:
            print(f"No financial statements data found for {cache_id}")
            return None
    except Exception as e:
        print(f"Error loading financial statements data: {e}")
        return None


def load_company_data(
    ticker: str,
    as_of_date: str,
    db_path: str = None
) -> Optional[Dict]:
    """
    Load company data from database.
    
    Args:
        ticker: Stock ticker symbol
        as_of_date: Date in YYYY-MM-DD format
        db_path: Path to database. If None, uses default.
        
    Returns:
        Dictionary with company data fields, or None if not found.
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)
    
    if not Path(db_path).exists():
        print(f"Database not found at {db_path}")
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
        else:
            print(f"No company data found for {cache_id}")
            return None
    except Exception as e:
        print(f"Error loading company data: {e}")
        return None


def plot_price_performance(
    ticker: str,
    start_date: str,
    end_date: str,
    save_path: str = './figs',
    db_path: str = None,
    config_path: str = None
) -> Optional[str]:
    """
    Generate price performance graph comparing stock vs base index.
    
    Args:
        ticker: Stock ticker symbol
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        save_path: Directory to save the graph
        db_path: Path to database. If None, uses default.
        config_path: Path to config.yaml for color palette. If None, uses default.
        
    Returns:
        Path to saved graph file, or None on error.
    """
    data = load_price_performance_data(ticker, start_date, end_date, db_path)
    if not data:
        return None
    
    # Load graph color palette from config
    graph_config = load_graph_config(config_path)
    base_config = graph_config.get('base', {})
    series_config = graph_config.get('series', {})
    
    stock_data = data['stock_data']
    index_data = data['index_data']
    base_index = data['base_index']
    
    # Convert to pandas DataFrame for easier handling
    stock_df = pd.DataFrame(stock_data)
    index_df = pd.DataFrame(index_data)
    
    # Convert date strings to datetime
    stock_df['date'] = pd.to_datetime(stock_df['date'])
    index_df['date'] = pd.to_datetime(index_df['date'])
    
    # Set date as index
    stock_df.set_index('date', inplace=True)
    index_df.set_index('date', inplace=True)
    
    # Get colors from config - use different colors for stock and benchmark
    stock_series_config = series_config.get('stock', {})
    benchmark_series_config = series_config.get('benchmark', {})
    
    stock_color = stock_series_config.get('color', '#9E1F00')
    stock_linewidth = stock_series_config.get('linewidth', 3)
    stock_linestyle = stock_series_config.get('linestyle', '-')
    
    benchmark_color = benchmark_series_config.get('color', '#1F77B4')
    benchmark_linewidth = benchmark_series_config.get('linewidth', 2.2)
    benchmark_linestyle = benchmark_series_config.get('linestyle', '-')
    
    # Create figure with background color from config
    fig = plt.figure(figsize=(12, 7), facecolor=base_config.get('background', '#FFFFFF'))
    ax = plt.gca()
    ax.set_facecolor(base_config.get('background', '#FFFFFF'))
    
    # Plot rebased close prices with colors from config
    plt.plot(stock_df.index, stock_df['rebased_close'], 
             label=ticker, color=stock_color, linewidth=stock_linewidth, linestyle=stock_linestyle)
    plt.plot(index_df.index, index_df['rebased_close'], 
             label=base_index, color=benchmark_color, linewidth=benchmark_linewidth, linestyle=benchmark_linestyle)
    
    # Formatting with colors from config
    text_secondary = base_config.get('text_secondary', '#666666')
    axis_color = base_config.get('axis', '#333333')
    grid_color = base_config.get('grid', '#E6E6E6')
    
    plt.xlabel('Date', fontsize=14, color=text_secondary)
    plt.ylabel('Rebased Price (Base = 100)', fontsize=14, color=text_secondary, fontweight='bold')
    # Title removed as requested
    
    # Format x-axis dates
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=45)
    
    # Format y-axis
    plt.gca().yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'{y:.0f}'))
    
    # Legend with config colors
    plt.legend(loc='upper left', fontsize=12, frameon=False, labelcolor=text_secondary)
    
    # Grid and spines with config colors
    plt.grid(visible=True, alpha=0.3, linestyle='--', color=grid_color)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(axis_color)
    ax.spines['bottom'].set_color(axis_color)
    ax.tick_params(colors=axis_color, labelsize=11)
    
    plt.tight_layout()
    
    # Save figure with config background
    save_dir = Path(save_path)
    save_dir.mkdir(parents=True, exist_ok=True)
    plot_path = save_dir / 'graph_price_performance.png'
    plt.savefig(plot_path, dpi=300, bbox_inches='tight', facecolor=base_config.get('background', '#FFFFFF'))
    plt.close()
    
    print(f"Price performance graph saved to {plot_path}")
    return str(plot_path)


def generate_company_data_table(
    ticker: str,
    as_of_date: str,
    save_path: str = './figs',
    db_path: str = None
) -> Optional[str]:
    """
    Generate company data table similar to the example format.
    
    Args:
        ticker: Stock ticker symbol
        as_of_date: Date in YYYY-MM-DD format
        save_path: Directory to save the table
        db_path: Path to database. If None, uses default.
        
    Returns:
        Path to saved table file, or None on error.
    """
    data = load_company_data(ticker, as_of_date, db_path)
    if not data:
        return None
    
    # Prepare data for table
    shares_outstanding_mn = (data.get('shares_outstanding', 0) or 0) / 1e6
    market_cap_mn = (data.get('market_cap', 0) or 0) / 1e6
    fx_rate = data.get('fx_rate', 1.0) or 1.0
    free_float_pct = data.get('free_float_pct', 0) or 0
    avg_vol_3m_mn = (data.get('avg_daily_volume_3m_shares', 0) or 0) / 1e6
    avg_vol_3m_usd_mn = (data.get('avg_daily_volume_3m_usd', 0) or 0) / 1e6
    volatility_90d = data.get('volatility_90d', 0) or 0
    high_52w = data.get('52w_high', 0) or 0
    low_52w = data.get('52w_low', 0) or 0
    index_name = data.get('primary_index_name', 'N/A') or 'N/A'
    
    # Format analyst ratings
    ratings = data.get('analyst_rating_counts', {}) or {}
    buy_count = ratings.get('buy', 0) + ratings.get('strongBuy', 0)
    hold_count = ratings.get('hold', 0)
    sell_count = ratings.get('sell', 0) + ratings.get('strongSell', 0)
    analyst_ratings = f"{buy_count}|{hold_count}|{sell_count}"
    
    # Create figure for table - narrower and more compact
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.axis('off')
    
    # Table data
    table_data = [
        ['Shares O/S (mn):', f'{shares_outstanding_mn:,.2f}'],
        ['52-week range ($):', f'{high_52w:.2f}-{low_52w:.2f}'],
        ['Market cap ($ mn):', f'{market_cap_mn:,.2f}'],
        ['Exchange rate:', f'{fx_rate:.2f}'],
        ['Free float (%):', f'{free_float_pct:.1f}%'],
        ['3M ADV (mn):', f'{avg_vol_3m_mn:.2f}'],
        ['3M ADV ($ mn):', f'{avg_vol_3m_usd_mn:.1f}'],
        ['Volatility (90 Day):', f'{volatility_90d:.0f}'],
        ['Index:', index_name],
        ['BBG ANR (Buy | Hold | Sell):', analyst_ratings],
    ]
    
    # Create table with mixed alignment (left for labels, right for values)
    table = ax.table(cellText=table_data,
                    colWidths=[0.6, 0.4],
                    cellLoc='left',  # Default, will override for right column
                    loc='center',
                    bbox=[0, 0, 1, 1])
    
    # Style the table - make it very compact
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 1.0)  # Minimal vertical scaling for compact rows
    
    # Style cells with minimal padding
    for i in range(len(table_data)):
        # Left column (labels) - left aligned
        cell = table[(i, 0)]
        cell.set_facecolor('#f0f0f0')
        cell.set_text_props(weight='bold', color='#000000')
        cell.set_edgecolor('#d0d0d0')
        cell.set_linewidth(0.5)
        cell.set_height(0.08)  # Set fixed small height
        cell.PAD = 0.02  # Minimal padding
        
        # Right column (values) - right aligned
        cell = table[(i, 1)]
        cell.set_facecolor('#ffffff')
        cell.set_text_props(color='#000000')
        cell.set_edgecolor('#d0d0d0')
        cell.set_linewidth(0.5)
        cell.set_height(0.08)  # Set fixed small height
        cell.PAD = 0.02  # Minimal padding
        # Set right alignment for text
        cell.get_text().set_ha('right')
    
    # No title/header as requested
    plt.tight_layout()
    
    # Save figure
    save_dir = Path(save_path)
    save_dir.mkdir(parents=True, exist_ok=True)
    table_path = save_dir / 'table_company_data.png'
    plt.savefig(table_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"Company data table saved to {table_path}")
    return str(table_path)


def generate_key_metrics_table(
    ticker: str,
    save_path: str = './figs',
    db_path: str = None
) -> Optional[str]:
    """
    Generate key metrics table similar to the example format.
    
    Args:
        ticker: Stock ticker symbol
        save_path: Directory to save the table
        db_path: Path to database. If None, uses default.
        
    Returns:
        Path to saved table file, or None on error.
    """
    data = load_key_metrics(ticker, db_path)
    if not data:
        return None
    
    metrics = data['metrics']
    fiscal_year_end = data.get('fiscal_year_end', 'Dec')
    
    # Sort years to get latest 2 actual years + forecast
    # The data should have: 2 actual years + 1-2 forecast years
    all_years = sorted(metrics.keys(), reverse=True, key=lambda x: int(x) if x.isdigit() else 0)
    
    # To properly identify actual vs forecast years, we need to check the API
    # But for graph generation, we can use a heuristic:
    # 1. Fetch fresh data from API to see what the latest actual year is
    # 2. Years <= latest_actual_year are actual, years > latest_actual_year are forecasts
    
    # Try to determine latest actual year by checking API
    try:
        from agentic.fmp_data_puller import fetch_financial_statements_fmp, FMP_API_KEY, calculate_key_metrics
        import os
        
        # Fetch fresh data to determine latest actual year
        income_statements, balance_sheets, cash_flows = fetch_financial_statements_fmp(
            ticker, FMP_API_KEY, period='annual', limit=3
        )
        
        if income_statements and balance_sheets and cash_flows:
            # Calculate metrics to get actual years from API
            temp_metrics = calculate_key_metrics(
                income_statements, balance_sheets, cash_flows,
                None, None, None
            )
            actual_years_from_api = sorted(temp_metrics.keys(), reverse=True, key=int)
            if actual_years_from_api:
                latest_actual_year = int(actual_years_from_api[0])
            else:
                latest_actual_year = None
        else:
            latest_actual_year = None
    except:
        latest_actual_year = None
    
    # Separate years into actual and forecast
    actual_years = []
    forecast_years = []
    
    if latest_actual_year:
        # Use API data to determine actual vs forecast
        for year_str in all_years:
            if not year_str.isdigit():
                continue
            year_int = int(year_str)
            if year_int <= latest_actual_year:
                actual_years.append(year_str)
            else:
                forecast_years.append(year_str)
    else:
        # Fallback: use heuristic based on calendar year
        from datetime import datetime
        current_year = int(datetime.now().strftime('%Y'))
        # Assume years that are significantly in the past or match known patterns are actual
        # This is a fallback - ideally we always have API data
        sorted_ascending = sorted(all_years, key=lambda x: int(x) if x.isdigit() else 0)
        for year_str in sorted_ascending:
            if not year_str.isdigit():
                continue
            year_int = int(year_str)
            # If year is > current_year, it's definitely a forecast
            if year_int > current_year:
                forecast_years.append(year_str)
            else:
                # Check for duplicates to identify placeholder forecasts
                is_duplicate = False
                for prev_actual in actual_years:
                    if not prev_actual.isdigit():
                        continue
                    if (abs(metrics[year_str].get('revenue', 0) - metrics[prev_actual].get('revenue', 0)) < 1 and
                        abs(metrics[year_str].get('adj_ebitda', 0) - metrics[prev_actual].get('adj_ebitda', 0)) < 1):
                        is_duplicate = True
                        break
                if not is_duplicate:
                    actual_years.append(year_str)
    
    # Sort actual years (most recent first)
    actual_years = sorted(actual_years, reverse=True, key=int)
    
    if len(actual_years) < 2:
        print("Not enough actual years of data for key metrics table")
        return None
    
    # Get the 2 most recent actual years
    latest_actual = actual_years[0]  # Most recent actual year (e.g., 2024)
    year_2_ago = actual_years[1]     # Second most recent actual year (e.g., 2023)
    
    # Get 2 forecast years (next 2 years after latest actual)
    forecast_year_1 = str(int(latest_actual) + 1)  # e.g., 2025
    forecast_year_2 = str(int(latest_actual) + 2)  # e.g., 2026
    
    # Create forecasts if they don't exist
    from agentic.fmp_data_puller import forecast_next_fiscal_year
    
    if forecast_year_1 not in metrics:
        metrics[forecast_year_1] = forecast_next_fiscal_year(
            metrics[latest_actual],
            metrics.get(year_2_ago) if year_2_ago else None
        )
    
    if forecast_year_2 not in metrics:
        # For second forecast, use first forecast as base
        metrics[forecast_year_2] = forecast_next_fiscal_year(
            metrics.get(forecast_year_1, metrics[latest_actual]),
            metrics[latest_actual]
        )
    
    # Store the latest actual year for title (this is the most recent complete fiscal year)
    latest_complete_fy = latest_actual
    
    # Prepare column headers - show 2 actual years + 2 forecast years (4 columns total)
    col_headers = []
    col_data = []
    
    # Column 1: 2 years ago actual
    col_headers.append(f'FY{year_2_ago[-2:]}A')
    col_data.append(metrics[year_2_ago])
    
    # Column 2: Latest actual year
    col_headers.append(f'FY{latest_actual[-2:]}A')
    col_data.append(metrics[latest_actual])
    
    # Column 3: First forecast year
    col_headers.append(f'FY{forecast_year_1[-2:]}E')
    col_data.append(metrics[forecast_year_1])
    
    # Column 4: Second forecast year
    col_headers.append(f'FY{forecast_year_2[-2:]}E')
    col_data.append(metrics[forecast_year_2])
    
    # Define metric categories and rows
    categories = {
        'Financial Estimates': [
            ('Revenue', 'revenue', '{:,.0f}'),
            ('Adj. EBITDA', 'adj_ebitda', '{:,.0f}'),
            ('Adj. EBIT', 'adj_ebit', '{:,.0f}'),
            ('Adj. net income', 'adj_net_income', '{:,.0f}'),
            ('Net margin', 'net_margin', '{:.1f}%'),
            ('Adj. EPS', 'adj_eps', '{:.2f}'),
            ('BBG EPS', 'adj_eps', '{:.2f}'),  # Using adj_eps as proxy
            ('Cashflow from operations', 'cfo', '{:,.0f}'),
            ('FCFF', 'fcff', '{:,.0f}'),
        ],
        'Margins and Growth': [
            ('Revenue Growth Y/Y (%)', 'revenue_growth', '{:.1f}%'),
            ('EBITDA margin', 'ebitda_margin', '{:.1f}%'),
            ('EBITDA Growth Y/Y (%)', 'ebitda_growth', '{:.1f}%'),
            ('EBIT margin', 'ebit_margin', '{:.1f}%'),
            ('Adj. EPS growth', 'adj_eps_growth', '{:.1f}%'),
        ],
        'Ratios': [
            ('Adj. tax rate', 'adj_tax_rate', '{:.1f}%'),
            ('Interest cover', 'interest_cover', '{:.1f}'),
            ('Net debt/Equity', 'net_debt_equity', '{:.1f}%'),
            ('Net debt/EBITDA', 'net_debt_ebitda', '{:.1f}'),
            ('ROCE', 'roce', '{:.1f}%'),
            ('ROE', 'roe', '{:.1f}%'),
        ],
        'Valuation': [
            ('FCFF yield', 'fcff_yield', '{:.1f}%'),
            ('Dividend yield', 'dividend_yield', ' - '),
            ('EV/EBITDA', 'ev_ebitda', '{:.1f}'),
            ('EV/Revenue', 'ev_revenue', '{:.1f}'),
            ('Adj. P/E', 'adj_pe', '{:.1f}'),
        ]
    }
    
    # Create figure for table - narrow and compact
    fig, ax = plt.subplots(figsize=(6, 10))
    ax.axis('off')
    
    # Build table data
    table_data = []
    table_data.append([''] + col_headers)  # Header row
    
    for category, metric_list in categories.items():
        # Add category header
        table_data.append([category] + [''] * len(col_headers))
        
        for metric_name, metric_key, format_str in metric_list:
            row = [metric_name]
            for col_metrics in col_data:
                value = col_metrics.get(metric_key)
                if value is None:
                    # Handle None values based on metric type
                    if metric_key == 'dividend_yield':
                        row.append(' - ')
                    elif metric_key in ['interest_cover', 'net_debt_equity', 'net_debt_ebitda']:
                        row.append('NM')
                    elif metric_key in ['fcff_yield', 'ev_ebitda', 'ev_revenue', 'adj_pe']:
                        row.append(' - ')
                    else:
                        row.append(' - ')
                else:
                    try:
                        if isinstance(value, (int, float)):
                            # Determine format based on format_str
                            if format_str == ' - ':
                                row.append(' - ')
                            elif '%' in format_str:
                                    # Format as percentage - round to 1 decimal
                                    row.append(f'{round(value, 1):.1f}%')
                            elif ',' in format_str and '.0f' in format_str:
                                # Format with commas, no decimals (for dollar amounts in millions)
                                row.append(f'{round(value):,.0f}')
                            elif '.2f' in format_str:
                                # Format with 2 decimals (for EPS)
                                row.append(f'{round(value, 2):.2f}')
                            elif '.1f' in format_str:
                                # Format with 1 decimal (for ratios)
                                row.append(f'{round(value, 1):.1f}')
                            elif '.0f' in format_str:
                                # Format as integer
                                row.append(f'{round(value):.0f}')
                            else:
                                # Default: format as is
                                row.append(str(value))
                        else:
                            row.append(str(value))
                    except Exception as e:
                        row.append(str(value) if value is not None else ' - ')
            table_data.append(row)
    
    # Create table - adjust width for 4 columns
    # Left column (metric names) gets more space, data columns share remaining space
    metric_col_width = 0.4
    data_col_width = (1.0 - metric_col_width) / len(col_headers)
    col_widths = [metric_col_width] + [data_col_width] * len(col_headers)
    
    table = ax.table(cellText=table_data,
                    colWidths=col_widths,
                    cellLoc='left',
                    loc='center',
                    bbox=[0, 0, 1, 1])
    
    # Style the table - tightest vertical spacing, no borders, no title
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 0.35)  # Very tight rows - more compact
    
    # Style cells - remove all borders, zero padding
    for i in range(len(table_data)):
        for j in range(len(table_data[i])):
            cell = table[(i, j)]
            
            # Header row
            if i == 0:
                cell.set_facecolor('#e0e0e0')
                cell.set_text_props(weight='bold', color='#000000')
                cell.set_edgecolor('none')  # No borders
                cell.set_linewidth(0)
            # Category rows
            elif j == 0 and table_data[i][0] in [cat for cat in categories.keys()]:
                cell.set_facecolor('#f0f0f0')
                cell.set_text_props(weight='bold', color='#000000')
                cell.set_edgecolor('none')  # No borders
                cell.set_linewidth(0)
            # Data rows - left column
            elif j == 0:
                cell.set_facecolor('#ffffff')
                cell.set_text_props(color='#000000')
                cell.set_edgecolor('none')  # No borders
                cell.set_linewidth(0)
            # Data rows - value columns (right align)
            else:
                cell.set_facecolor('#ffffff')
                cell.set_text_props(color='#000000')
                cell.set_edgecolor('none')  # No borders
                cell.set_linewidth(0)
                cell.get_text().set_ha('right')
            
            # Minimal height and zero padding for tightest spacing
            cell.set_height(0.015)  # Even smaller height
            cell.PAD = 0.0  # Zero padding
    
    # No title - use full space
    plt.tight_layout(rect=[0, 0, 1, 1])
    
    # Save figure
    save_dir = Path(save_path)
    save_dir.mkdir(parents=True, exist_ok=True)
    table_path = save_dir / 'table_key_metrics.png'
    plt.savefig(table_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"Key metrics table saved to {table_path}")
    return str(table_path)


def plot_analyst_ratings(
    ticker: str,
    as_of_date: str,
    save_path: str = './figs',
    db_path: str = None
) -> Optional[str]:
    """
    Generate analyst ratings distribution graph.
    
    Args:
        ticker: Stock ticker symbol
        as_of_date: Date in YYYY-MM-DD format
        save_path: Directory to save the graph
        db_path: Path to database. If None, uses default.
        
    Returns:
        Path to saved graph file, or None on error.
    """
    data = load_company_data(ticker, as_of_date, db_path)
    if not data or not data.get('analyst_rating_counts'):
        print(f"No analyst rating data available for {ticker}")
        return None
    
    ratings = data['analyst_rating_counts']
    consensus = data.get('consensus_rating', 'N/A')
    num_analysts = data.get('num_analysts', 0)
    
    # Prepare data for plotting
    labels = ['Strong Buy', 'Buy', 'Hold', 'Sell', 'Strong Sell']
    values = [
        ratings.get('strongBuy', 0),
        ratings.get('buy', 0),
        ratings.get('hold', 0),
        ratings.get('sell', 0),
        ratings.get('strongSell', 0)
    ]
    
    # Filter out zero values for cleaner visualization
    plot_labels = []
    plot_values = []
    colors = []
    color_map = {
        'Strong Buy': '#2e7d32',
        'Buy': '#66bb6a',
        'Hold': '#ffa726',
        'Sell': '#ef5350',
        'Strong Sell': '#c62828'
    }
    
    for label, value in zip(labels, values):
        if value > 0:
            plot_labels.append(label)
            plot_values.append(value)
            colors.append(color_map[label])
    
    if not plot_values:
        print("No analyst ratings to plot")
        return None
    
    # Create figure
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Bar chart
    bars = ax1.bar(plot_labels, plot_values, color=colors, alpha=0.8, edgecolor='#6a6a6a', linewidth=1.5)
    ax1.set_ylabel('Number of Analysts', fontsize=12, color='#6a6a6a', fontweight='bold')
    ax1.set_title(f'Analyst Ratings Distribution\nConsensus: {consensus} ({num_analysts} analysts)', 
                  fontsize=13, fontweight='bold', color='#6a6a6a')
    ax1.tick_params(colors='#6a6a6a', labelsize=10)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.spines['left'].set_color('#6a6a6a')
    ax1.spines['bottom'].set_color('#6a6a6a')
    
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontsize=11, color='#6a6a6a', fontweight='bold')
    
    # Pie chart
    if sum(plot_values) > 0:
        wedges, texts, autotexts = ax2.pie(plot_values, labels=plot_labels, colors=colors,
                                           autopct='%1.1f%%', startangle=90,
                                           textprops={'fontsize': 10, 'color': '#6a6a6a'})
        ax2.set_title('Rating Distribution (%)', fontsize=13, fontweight='bold', color='#6a6a6a')
    
    plt.tight_layout()
    
    # Save figure
    save_dir = Path(save_path)
    save_dir.mkdir(parents=True, exist_ok=True)
    plot_path = save_dir / f'{ticker}_analyst_ratings.png'
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Analyst ratings graph saved to {plot_path}")
    return str(plot_path)


def plot_company_metrics(
    ticker: str,
    as_of_date: str,
    save_path: str = './figs',
    db_path: str = None
) -> Optional[str]:
    """
    Generate company metrics visualization.
    
    Args:
        ticker: Stock ticker symbol
        as_of_date: Date in YYYY-MM-DD format
        save_path: Directory to save the graph
        db_path: Path to database. If None, uses default.
        
    Returns:
        Path to saved graph file, or None on error.
    """
    data = load_company_data(ticker, as_of_date, db_path)
    if not data:
        return None
    
    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f'{ticker} Key Metrics (as of {as_of_date})', 
                 fontsize=16, fontweight='bold', color='#6a6a6a')
    
    # 1. Price Range (52W High/Low)
    ax1 = axes[0, 0]
    high = data.get('52w_high', 0)
    low = data.get('52w_low', 0)
    if high > 0 and low > 0:
        price_range = high - low
        current_pos = (high + low) / 2  # Approximate current position
        ax1.barh(['52W Range'], [price_range], left=low, color='#9E1F00', alpha=0.6)
        ax1.axvline(x=high, color='#d45716', linestyle='--', linewidth=2, label='52W High')
        ax1.axvline(x=low, color='#d45716', linestyle='--', linewidth=2, label='52W Low')
        ax1.axvline(x=current_pos, color='#2e7d32', linewidth=3, label='Approx Current')
        ax1.set_xlabel('Price ($)', fontsize=11, color='#6a6a6a')
        ax1.set_title('52-Week Price Range', fontsize=12, fontweight='bold', color='#6a6a6a')
        ax1.legend(fontsize=9, frameon=False)
        ax1.tick_params(colors='#6a6a6a', labelsize=10)
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        ax1.spines['left'].set_color('#6a6a6a')
        ax1.spines['bottom'].set_color('#6a6a6a')
    
    # 2. Market Metrics
    ax2 = axes[0, 1]
    metrics = {
        'Market Cap': data.get('market_cap', 0) / 1e9,  # Convert to billions
        'Avg Daily Vol\n(3M, USD)': data.get('avg_daily_volume_3m_usd', 0) / 1e6,  # Convert to millions
    }
    if metrics['Market Cap'] > 0:
        bars = ax2.bar(metrics.keys(), metrics.values(), color=['#9E1F00', '#d45716'], alpha=0.8)
        ax2.set_ylabel('Value (Billions/Millions)', fontsize=11, color='#6a6a6a', fontweight='bold')
        ax2.set_title('Market Metrics', fontsize=12, fontweight='bold', color='#6a6a6a')
        ax2.tick_params(colors='#6a6a6a', labelsize=9)
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        ax2.spines['left'].set_color('#6a6a6a')
        ax2.spines['bottom'].set_color('#6a6a6a')
        
        # Add value labels
        for bar in bars:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'${height:.1f}',
                    ha='center', va='bottom', fontsize=9, color='#6a6a6a', fontweight='bold')
    
    # 3. Volatility
    ax3 = axes[1, 0]
    volatility = data.get('volatility_90d', 0)
    if volatility > 0:
        # Create a gauge-like visualization
        categories = ['Low', 'Medium', 'High', 'Very High']
        thresholds = [0, 15, 30, 50, 100]
        colors_vol = ['#2e7d32', '#ffa726', '#ef5350', '#c62828']
        
        # Find which category volatility falls into
        category_idx = 0
        for i, threshold in enumerate(thresholds[1:], 1):
            if volatility <= threshold:
                category_idx = i - 1
                break
        else:
            category_idx = len(categories) - 1
        
        # Bar showing volatility level
        ax3.barh(['90-Day Volatility'], [volatility], color=colors_vol[category_idx], alpha=0.8)
        ax3.axvline(x=15, color='#6a6a6a', linestyle='--', alpha=0.5, linewidth=1)
        ax3.axvline(x=30, color='#6a6a6a', linestyle='--', alpha=0.5, linewidth=1)
        ax3.axvline(x=50, color='#6a6a6a', linestyle='--', alpha=0.5, linewidth=1)
        ax3.set_xlabel('Volatility (%)', fontsize=11, color='#6a6a6a')
        ax3.set_title(f'Volatility: {categories[category_idx]}', 
                     fontsize=12, fontweight='bold', color='#6a6a6a')
        ax3.set_xlim(0, max(volatility * 1.2, 50))
        ax3.tick_params(colors='#6a6a6a', labelsize=10)
        ax3.spines['top'].set_visible(False)
        ax3.spines['right'].set_visible(False)
        ax3.spines['left'].set_color('#6a6a6a')
        ax3.spines['bottom'].set_color('#6a6a6a')
        
        # Add value label
        ax3.text(volatility, 0, f'{volatility:.2f}%',
                ha='left', va='center', fontsize=11, color='#6a6a6a', fontweight='bold',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    # 4. Share Information
    ax4 = axes[1, 1]
    share_info = {
        'Shares\nOutstanding': data.get('shares_outstanding', 0) / 1e9,  # Convert to billions
        'Free Float\n(%)': data.get('free_float_pct', 0),
    }
    if share_info['Shares\nOutstanding'] > 0:
        bars = ax4.bar(share_info.keys(), share_info.values(), 
                      color=['#9E1F00', '#d45716'], alpha=0.8)
        ax4.set_ylabel('Value', fontsize=11, color='#6a6a6a', fontweight='bold')
        ax4.set_title('Share Information', fontsize=12, fontweight='bold', color='#6a6a6a')
        ax4.tick_params(colors='#6a6a6a', labelsize=9)
        ax4.spines['top'].set_visible(False)
        ax4.spines['right'].set_visible(False)
        ax4.spines['left'].set_color('#6a6a6a')
        ax4.spines['bottom'].set_color('#6a6a6a')
        
        # Add value labels
        for i, (key, value) in enumerate(share_info.items()):
            if 'Outstanding' in key:
                label = f'{value:.2f}B'
            else:
                label = f'{value:.1f}%'
            ax4.text(i, value, label,
                    ha='center', va='bottom', fontsize=9, color='#6a6a6a', fontweight='bold')
    
    plt.tight_layout()
    
    # Save figure
    save_dir = Path(save_path)
    save_dir.mkdir(parents=True, exist_ok=True)
    plot_path = save_dir / f'{ticker}_company_metrics.png'
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Company metrics graph saved to {plot_path}")
    return str(plot_path)


def get_actual_and_forecast_years(ticker: str, db_path: str = None):
    """
    Helper function to determine actual and forecast years from API data.
    Returns latest_actual_year, year_2_ago, forecast_year_1, forecast_year_2
    """
    try:
        from agentic.fmp_data_puller import fetch_financial_statements_fmp, FMP_API_KEY
        import os
        
        # Fetch fresh data to determine latest actual year
        income_statements, balance_sheets, cash_flows = fetch_financial_statements_fmp(
            ticker, FMP_API_KEY, period='annual', limit=3
        )
        
        if income_statements and balance_sheets and cash_flows:
            # Get actual years from API
            actual_years = []
            for stmt in income_statements:
                date_str = stmt.get('date', '')
                if date_str:
                    year = date_str[:4]
                    if year.isdigit():
                        actual_years.append(year)
                elif stmt.get('calendarYear'):
                    year = str(stmt.get('calendarYear'))
                    if year.isdigit():
                        actual_years.append(year)
            
            if actual_years:
                actual_years = sorted(list(set(actual_years)), reverse=True, key=int)
                if len(actual_years) >= 2:
                    latest_actual = actual_years[0]
                    year_2_ago = actual_years[1]
                    forecast_year_1 = str(int(latest_actual) + 1)
                    forecast_year_2 = str(int(latest_actual) + 2)
                    return latest_actual, year_2_ago, forecast_year_1, forecast_year_2
    except:
        pass
    
    # Fallback
    from datetime import datetime
    current_year = int(datetime.now().strftime('%Y'))
    latest_actual = str(current_year - 1)
    year_2_ago = str(current_year - 2)
    forecast_year_1 = str(current_year)
    forecast_year_2 = str(current_year + 1)
    return latest_actual, year_2_ago, forecast_year_1, forecast_year_2


def generate_income_statement_table(
    ticker: str,
    save_path: str = './figs',
    db_path: str = None
) -> Optional[str]:
    """
    Generate income statement table similar to key metrics table format.
    
    Args:
        ticker: Stock ticker symbol
        save_path: Directory to save the table
        db_path: Path to database. If None, uses default.
        
    Returns:
        Path to saved table file, or None on error.
    """
    income_statements = load_financial_statements(ticker, 'income', 'annual', db_path)
    if not income_statements:
        print(f"No income statement data found for {ticker}")
        return None
    
    # Get actual and forecast years
    latest_actual, year_2_ago, forecast_year_1, forecast_year_2 = get_actual_and_forecast_years(ticker, db_path)
    
    # Organize statements by year
    statements_by_year = {}
    for stmt in income_statements:
        date_str = stmt.get('date', '')
        if date_str:
            year = date_str[:4]
        else:
            year = str(stmt.get('calendarYear', ''))
        if year.isdigit():
            statements_by_year[year] = stmt
    
    # Get actual data
    actual_data = {}
    if latest_actual in statements_by_year:
        actual_data[latest_actual] = statements_by_year[latest_actual]
    if year_2_ago in statements_by_year:
        actual_data[year_2_ago] = statements_by_year[year_2_ago]
    
    if len(actual_data) < 2:
        print("Not enough actual years of data for income statement table")
        return None
    
    # Get key metrics for forecasts (they contain forecasted income statement items)
    key_metrics_data = load_key_metrics(ticker, db_path)
    forecast_data = {}
    if key_metrics_data and 'metrics' in key_metrics_data:
        metrics = key_metrics_data['metrics']
        if forecast_year_1 in metrics:
            forecast_data[forecast_year_1] = metrics[forecast_year_1]
        if forecast_year_2 in metrics:
            forecast_data[forecast_year_2] = metrics[forecast_year_2]
    
    # Helper function to get value from statement or forecast
    def get_value(year, key, is_forecast=False):
        if is_forecast and year in forecast_data:
            # For forecasts, use key_metrics data
            if key == 'revenue':
                return forecast_data[year].get('revenue', 0)  # Already in millions
            elif key == 'costOfRevenue':
                # Estimate from revenue and gross margin
                revenue = forecast_data[year].get('revenue', 0)
                ebitda_margin = forecast_data[year].get('ebitda_margin', 0) / 100
                # Rough estimate: cost = revenue * (1 - margin)
                return revenue * (1 - ebitda_margin * 0.7)  # Rough estimate
            elif key == 'grossProfit':
                revenue = forecast_data[year].get('revenue', 0)
                cost = get_value(year, 'costOfRevenue', True)
                return revenue - cost
            elif key == 'operatingExpenses':
                revenue = forecast_data[year].get('revenue', 0)
                ebitda = forecast_data[year].get('adj_ebitda', 0)
                ebit = forecast_data[year].get('adj_ebit', 0)
                gross_profit = get_value(year, 'grossProfit', True)
                # Operating expenses = Gross profit - EBIT
                return gross_profit - ebit if gross_profit > ebit else 0
            elif key == 'operatingIncome':
                return forecast_data[year].get('adj_ebit', 0)
            elif key == 'netIncome':
                return forecast_data[year].get('adj_net_income', 0)
            elif key == 'ebitda':
                return forecast_data[year].get('adj_ebitda', 0)
            else:
                return 0
        elif year in actual_data:
            value = actual_data[year].get(key, 0) or 0
            return value / 1e6  # Convert to millions
        return 0
    
    # Prepare column headers
    col_headers = [
        f'FY{year_2_ago[-2:]}A',
        f'FY{latest_actual[-2:]}A',
        f'FY{forecast_year_1[-2:]}E',
        f'FY{forecast_year_2[-2:]}E'
    ]
    
    # Define income statement categories and rows
    categories = {
        'Revenue': [
            ('Revenue', 'revenue', '{:,.0f}'),
        ],
        'Costs and Expenses': [
            ('Cost of Revenue', 'costOfRevenue', '{:,.0f}'),
            ('Gross Profit', 'grossProfit', '{:,.0f}'),
            ('Operating Expenses', 'operatingExpenses', '{:,.0f}'),
        ],
        'Operating Income': [
            ('Operating Income (EBIT)', 'operatingIncome', '{:,.0f}'),
            ('EBITDA', 'ebitda', '{:,.0f}'),
        ],
        'Net Income': [
            ('Net Income', 'netIncome', '{:,.0f}'),
        ]
    }
    
    # Create figure for table - smaller height for very compact table
    fig, ax = plt.subplots(figsize=(6, 3.5))  # Much smaller height for compact table
    ax.axis('off')
    
    # Build table data
    table_data = []
    table_data.append([''] + col_headers)  # Header row
    
    for category, metric_list in categories.items():
        # Add category header
        table_data.append([category] + [''] * len(col_headers))
        
        for metric_name, metric_key, format_str in metric_list:
            row = [metric_name]
            for i, year in enumerate([year_2_ago, latest_actual, forecast_year_1, forecast_year_2]):
                is_forecast = i >= 2
                value = get_value(year, metric_key, is_forecast)
                
                if value is None or value == 0:
                    row.append(' - ')
                else:
                    try:
                        if format_str == '{:,.0f}':
                            row.append(f'{round(value):,.0f}')
                        elif '%' in format_str:
                            row.append(f'{round(value, 1):.1f}%')
                        else:
                            row.append(f'{round(value, 2):.2f}')
                    except:
                        row.append(' - ')
            table_data.append(row)
    
    # Create table
    metric_col_width = 0.4
    data_col_width = (1.0 - metric_col_width) / len(col_headers)
    col_widths = [metric_col_width] + [data_col_width] * len(col_headers)
    
    table = ax.table(cellText=table_data,
                    colWidths=col_widths,
                    cellLoc='left',
                    loc='center',
                    bbox=[0, 0, 1, 1])
    
    # Style the table - extremely tight vertical spacing for very compact table
    table.auto_set_font_size(False)
    table.set_fontsize(7)  # Smaller font for compact table
    table.scale(1, 0.05)  # Extremely tight vertical scaling for very compact table
    
    # Style cells - extremely tight spacing, zero padding
    for i in range(len(table_data)):
        for j in range(len(table_data[i])):
            cell = table[(i, j)]
            
            if i == 0:  # Header row
                cell.set_facecolor('#e0e0e0')
                cell.set_text_props(weight='bold', color='#000000', size=7)
                cell.set_edgecolor('none')  # No borders
                cell.set_linewidth(0)
            elif j == 0 and table_data[i][0] in categories.keys():  # Category rows
                cell.set_facecolor('#f0f0f0')
                cell.set_text_props(weight='bold', color='#000000', size=7)
                cell.set_edgecolor('none')  # No borders
                cell.set_linewidth(0)
            elif j == 0:  # Data rows - left column
                cell.set_facecolor('#ffffff')
                cell.set_text_props(color='#000000', size=7)
                cell.set_edgecolor('none')  # No borders
                cell.set_linewidth(0)
            else:  # Data rows - value columns
                cell.set_facecolor('#ffffff')
                cell.set_text_props(color='#000000', size=7)
                cell.set_edgecolor('none')  # No borders
                cell.set_linewidth(0)
                cell.get_text().set_ha('right')
            
            # Extremely tight vertical spacing - minimal height
            cell.set_height(0.0015)  # Very small height for tightest spacing
            cell.PAD = 0.0  # Zero padding
            # Set minimal vertical padding
            cell.get_text().set_va('center')
    
    # No title - use full space (match key_metrics)
    plt.tight_layout(rect=[0, 0, 1, 1])
    
    # Save figure
    save_dir = Path(save_path)
    save_dir.mkdir(parents=True, exist_ok=True)
    table_path = save_dir / 'table_income_statement.png'
    plt.savefig(table_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"Income statement table saved to {table_path}")
    return str(table_path)


def generate_balance_sheet_table(
    ticker: str,
    save_path: str = './figs',
    db_path: str = None
) -> Optional[str]:
    """
    Generate balance sheet table similar to key metrics table format.
    
    Args:
        ticker: Stock ticker symbol
        save_path: Directory to save the table
        db_path: Path to database. If None, uses default.
        
    Returns:
        Path to saved table file, or None on error.
    """
    balance_sheets = load_financial_statements(ticker, 'balance', 'annual', db_path)
    if not balance_sheets:
        print(f"No balance sheet data found for {ticker}")
        return None
    
    # Get actual and forecast years
    latest_actual, year_2_ago, forecast_year_1, forecast_year_2 = get_actual_and_forecast_years(ticker, db_path)
    
    # Organize statements by year
    statements_by_year = {}
    for stmt in balance_sheets:
        date_str = stmt.get('date', '')
        if date_str:
            year = date_str[:4]
        else:
            year = str(stmt.get('calendarYear', ''))
        if year.isdigit():
            statements_by_year[year] = stmt
    
    # Get actual data
    actual_data = {}
    if latest_actual in statements_by_year:
        actual_data[latest_actual] = statements_by_year[latest_actual]
    if year_2_ago in statements_by_year:
        actual_data[year_2_ago] = statements_by_year[year_2_ago]
    
    if len(actual_data) < 2:
        print("Not enough actual years of data for balance sheet table")
        return None
    
    # Get key metrics for forecasts
    key_metrics_data = load_key_metrics(ticker, db_path)
    forecast_data = {}
    if key_metrics_data and 'metrics' in key_metrics_data:
        metrics = key_metrics_data['metrics']
        if forecast_year_1 in metrics:
            forecast_data[forecast_year_1] = metrics[forecast_year_1]
        if forecast_year_2 in metrics:
            forecast_data[forecast_year_2] = metrics[forecast_year_2]
    
    # Helper function to get value
    def get_value(year, key, is_forecast=False):
        if is_forecast and year in forecast_data:
            # For forecasts, use simple growth assumptions
            if year_2_ago in actual_data and latest_actual in actual_data:
                prev_value = (actual_data[latest_actual].get(key, 0) or 0) / 1e6
                # Simple growth assumption based on revenue growth
                revenue_growth = forecast_data[year].get('revenue_growth', 0) / 100 if forecast_data[year] else 0
                return prev_value * (1 + revenue_growth * 0.5)  # Assets grow slower than revenue
            return 0
        elif year in actual_data:
            value = actual_data[year].get(key, 0) or 0
            return value / 1e6
        return 0
    
    # Prepare column headers
    col_headers = [
        f'FY{year_2_ago[-2:]}A',
        f'FY{latest_actual[-2:]}A',
        f'FY{forecast_year_1[-2:]}E',
        f'FY{forecast_year_2[-2:]}E'
    ]
    
    # Define balance sheet categories
    categories = {
        'Assets': [
            ('Cash and Cash Equivalents', 'cashAndCashEquivalents', '{:,.0f}'),
            ('Total Current Assets', 'totalCurrentAssets', '{:,.0f}'),
            ('Total Assets', 'totalAssets', '{:,.0f}'),
        ],
        'Liabilities': [
            ('Total Current Liabilities', 'totalCurrentLiabilities', '{:,.0f}'),
            ('Total Debt', 'totalDebt', '{:,.0f}'),
            ('Total Liabilities', 'totalLiabilities', '{:,.0f}'),
        ],
        'Equity': [
            ('Total Stockholders Equity', 'totalStockholdersEquity', '{:,.0f}'),
        ]
    }
    
    # Create figure for table - very small height for extremely compact table
    fig, ax = plt.subplots(figsize=(6, 3))  # Very small height for compact table
    ax.axis('off')
    
    # Build table data
    table_data = []
    table_data.append([''] + col_headers)
    
    for category, metric_list in categories.items():
        table_data.append([category] + [''] * len(col_headers))
        
        for metric_name, metric_key, format_str in metric_list:
            row = [metric_name]
            for i, year in enumerate([year_2_ago, latest_actual, forecast_year_1, forecast_year_2]):
                is_forecast = i >= 2
                value = get_value(year, metric_key, is_forecast)
                
                if value is None or value == 0:
                    row.append(' - ')
                else:
                    try:
                        row.append(f'{round(value):,.0f}')
                    except:
                        row.append(' - ')
            table_data.append(row)
    
    # Create and style table - extremely compact
    metric_col_width = 0.4
    data_col_width = (1.0 - metric_col_width) / len(col_headers)
    col_widths = [metric_col_width] + [data_col_width] * len(col_headers)
    
    table = ax.table(cellText=table_data,
                    colWidths=col_widths,
                    cellLoc='left',
                    loc='center',
                    bbox=[0, 0, 1, 1])
    
    table.auto_set_font_size(False)
    table.set_fontsize(7)  # Smaller font for compact table
    table.scale(1, 0.04)  # Extremely tight vertical scaling - very compact
    
    for i in range(len(table_data)):
        for j in range(len(table_data[i])):
            cell = table[(i, j)]
            
            if i == 0:
                cell.set_facecolor('#e0e0e0')
                cell.set_text_props(weight='bold', color='#000000', size=7)
                cell.set_edgecolor('none')  # No borders
                cell.set_linewidth(0)
            elif j == 0 and table_data[i][0] in categories.keys():
                cell.set_facecolor('#f0f0f0')
                cell.set_text_props(weight='bold', color='#000000', size=7)
                cell.set_edgecolor('none')  # No borders
                cell.set_linewidth(0)
            elif j == 0:
                cell.set_facecolor('#ffffff')
                cell.set_text_props(color='#000000', size=7)
                cell.set_edgecolor('none')  # No borders
                cell.set_linewidth(0)
            else:
                cell.set_facecolor('#ffffff')
                cell.set_text_props(color='#000000', size=7)
                cell.set_edgecolor('none')  # No borders
                cell.set_linewidth(0)
                cell.get_text().set_ha('right')
            
            # Extremely tight vertical spacing - minimal height
            cell.set_height(0.0015)  # Very small height for tightest spacing
            cell.PAD = 0.0  # Zero padding
            # Set minimal vertical padding
            cell.get_text().set_va('center')
    
    # No title - use full space (match key_metrics)
    plt.tight_layout(rect=[0, 0, 1, 1])
    
    save_dir = Path(save_path)
    save_dir.mkdir(parents=True, exist_ok=True)
    table_path = save_dir / 'table_balance_sheet.png'
    plt.savefig(table_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"Balance sheet table saved to {table_path}")
    return str(table_path)


def generate_cash_flow_table(
    ticker: str,
    save_path: str = './figs',
    db_path: str = None
) -> Optional[str]:
    """
    Generate cash flow statement table similar to key metrics table format.
    
    Args:
        ticker: Stock ticker symbol
        save_path: Directory to save the table
        db_path: Path to database. If None, uses default.
        
    Returns:
        Path to saved table file, or None on error.
    """
    cash_flows = load_financial_statements(ticker, 'cashflow', 'annual', db_path)
    if not cash_flows:
        print(f"No cash flow statement data found for {ticker}")
        return None
    
    # Get actual and forecast years
    latest_actual, year_2_ago, forecast_year_1, forecast_year_2 = get_actual_and_forecast_years(ticker, db_path)
    
    # Organize statements by year
    statements_by_year = {}
    for stmt in cash_flows:
        date_str = stmt.get('date', '')
        if date_str:
            year = date_str[:4]
        else:
            year = str(stmt.get('calendarYear', ''))
        if year.isdigit():
            statements_by_year[year] = stmt
    
    # Get actual data
    actual_data = {}
    if latest_actual in statements_by_year:
        actual_data[latest_actual] = statements_by_year[latest_actual]
    if year_2_ago in statements_by_year:
        actual_data[year_2_ago] = statements_by_year[year_2_ago]
    
    if len(actual_data) < 2:
        print("Not enough actual years of data for cash flow table")
        return None
    
    # Get key metrics for forecasts
    key_metrics_data = load_key_metrics(ticker, db_path)
    forecast_data = {}
    if key_metrics_data and 'metrics' in key_metrics_data:
        metrics = key_metrics_data['metrics']
        if forecast_year_1 in metrics:
            forecast_data[forecast_year_1] = metrics[forecast_year_1]
        if forecast_year_2 in metrics:
            forecast_data[forecast_year_2] = metrics[forecast_year_2]
    
    # Helper function to get value
    def get_value(year, key, is_forecast=False):
        if is_forecast and year in forecast_data:
            # For forecasts, use key_metrics data
            if key == 'operatingCashFlow':
                return forecast_data[year].get('cfo', 0)  # Already in millions
            elif key == 'capitalExpenditure':
                # Estimate from historical ratio
                if latest_actual in actual_data:
                    prev_capex = abs(actual_data[latest_actual].get('capitalExpenditure', 0) or 0) / 1e6
                    revenue_growth = forecast_data[year].get('revenue_growth', 0) / 100
                    return prev_capex * (1 + revenue_growth * 0.8)
                return 0
            elif key == 'freeCashFlow':
                ocf = get_value(year, 'operatingCashFlow', True)
                capex = get_value(year, 'capitalExpenditure', True)
                return ocf - capex
            elif key in ['netCashUsedForInvestingActivites', 'netCashUsedForInvestingActivities']:
                capex = get_value(year, 'capitalExpenditure', True)
                return -capex  # Typically negative
            elif key == 'netCashUsedProvidedByFinancingActivities':
                # Estimate based on historical patterns
                if latest_actual in actual_data:
                    prev_value = (actual_data[latest_actual].get('netCashUsedProvidedByFinancingActivities', 0) or 0) / 1e6
                    return prev_value * 0.9  # Slight decrease
                return 0
            return 0
        elif year in actual_data:
            # Handle both spellings of investing activities
            if key == 'netCashUsedForInvestingActivities':
                value = (actual_data[year].get('netCashUsedForInvestingActivities', 0) or 
                        actual_data[year].get('netCashUsedForInvestingActivites', 0) or 0)
            else:
                value = actual_data[year].get(key, 0) or 0
            if key == 'capitalExpenditure':
                return abs(value) / 1e6
            return value / 1e6
        return 0
    
    # Prepare column headers
    col_headers = [
        f'FY{year_2_ago[-2:]}A',
        f'FY{latest_actual[-2:]}A',
        f'FY{forecast_year_1[-2:]}E',
        f'FY{forecast_year_2[-2:]}E'
    ]
    
    # Define cash flow categories
    categories = {
        'Operating Activities': [
            ('Operating Cash Flow', 'operatingCashFlow', '{:,.0f}'),
        ],
        'Investing Activities': [
            ('Capital Expenditure', 'capitalExpenditure', '{:,.0f}'),
            ('Net Cash from Investing', 'netCashUsedForInvestingActivities', '{:,.0f}'),
        ],
        'Financing Activities': [
            ('Net Cash from Financing', 'netCashUsedProvidedByFinancingActivities', '{:,.0f}'),
        ],
        'Free Cash Flow': [
            ('Free Cash Flow', 'freeCashFlow', '{:,.0f}'),
        ]
    }
    
    # Create figure for table - smaller height for compact table
    fig, ax = plt.subplots(figsize=(6, 4))  # Reduced height for compact table
    ax.axis('off')
    
    # Build table data
    table_data = []
    table_data.append([''] + col_headers)
    
    for category, metric_list in categories.items():
        table_data.append([category] + [''] * len(col_headers))
        
        for metric_name, metric_key, format_str in metric_list:
            row = [metric_name]
            for i, year in enumerate([year_2_ago, latest_actual, forecast_year_1, forecast_year_2]):
                is_forecast = i >= 2
                value = get_value(year, metric_key, is_forecast)
                
                if value is None:
                    row.append(' - ')
                else:
                    try:
                        row.append(f'{round(value):,.0f}')
                    except:
                        row.append(' - ')
            table_data.append(row)
    
    # Create and style table - match key_metrics exactly
    metric_col_width = 0.4
    data_col_width = (1.0 - metric_col_width) / len(col_headers)
    col_widths = [metric_col_width] + [data_col_width] * len(col_headers)
    
    table = ax.table(cellText=table_data,
                    colWidths=col_widths,
                    cellLoc='left',
                    loc='center',
                    bbox=[0, 0, 1, 1])
    
    table.auto_set_font_size(False)
    table.set_fontsize(7)  # Smaller font for compact table
    table.scale(1, 0.04)  # Extremely tight vertical scaling - very compact
    
    for i in range(len(table_data)):
        for j in range(len(table_data[i])):
            cell = table[(i, j)]
            
            if i == 0:
                cell.set_facecolor('#e0e0e0')
                cell.set_text_props(weight='bold', color='#000000', size=7)
                cell.set_edgecolor('none')  # No borders
                cell.set_linewidth(0)
            elif j == 0 and table_data[i][0] in categories.keys():
                cell.set_facecolor('#f0f0f0')
                cell.set_text_props(weight='bold', color='#000000', size=7)
                cell.set_edgecolor('none')  # No borders
                cell.set_linewidth(0)
            elif j == 0:
                cell.set_facecolor('#ffffff')
                cell.set_text_props(color='#000000', size=7)
                cell.set_edgecolor('none')  # No borders
                cell.set_linewidth(0)
            else:
                cell.set_facecolor('#ffffff')
                cell.set_text_props(color='#000000', size=7)
                cell.set_edgecolor('none')  # No borders
                cell.set_linewidth(0)
                cell.get_text().set_ha('right')
            
            # Extremely tight vertical spacing - minimal height
            cell.set_height(0.0015)  # Very small height for tightest spacing
            cell.PAD = 0.0  # Zero padding
            # Set minimal vertical padding
            cell.get_text().set_va('center')
    
    # No title - use full space (match key_metrics)
    plt.tight_layout(rect=[0, 0, 1, 1])
    
    save_dir = Path(save_path)
    save_dir.mkdir(parents=True, exist_ok=True)
    table_path = save_dir / 'table_cash_flow_statement.png'
    plt.savefig(table_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"Cash flow statement table saved to {table_path}")
    return str(table_path)


def generate_all_graphs(
    ticker: str,
    company_name: str = None,
    start_date: str = None,
    end_date: str = None,
    as_of_date: str = None,
    base_save_path: str = './figs',
    db_path: str = None,
    config_path: str = None
) -> Dict[str, Optional[str]]:
    """
    Generate price performance graph and company data table for a ticker.
    Creates a folder named "company_name + timestamp" under base_save_path.
    
    Args:
        ticker: Stock ticker symbol
        company_name: Company name (default: uses ticker)
        start_date: Start date for price performance (default: today - 1 year)
        end_date: End date for price performance (default: today)
        as_of_date: Date for company data (default: today)
        base_save_path: Base directory to save graphs (default: './figs')
        db_path: Path to database. If None, uses default.
        
    Returns:
        Dictionary with paths to generated files.
    """
    from datetime import timedelta
    
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    if as_of_date is None:
        as_of_date = datetime.now().strftime('%Y-%m-%d')
    
    # Use ticker as company name if not provided
    if company_name is None:
        company_name = ticker
    
    # Create folder with company name + timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    folder_name = f"{company_name}_{timestamp}"
    save_path = Path(base_save_path) / folder_name
    save_path.mkdir(parents=True, exist_ok=True)
    
    print(f"Creating output folder: {save_path}")
    
    results = {}
    
    # Generate price performance graph
    print(f"\nGenerating price performance graph for {ticker}...")
    results['price_performance'] = plot_price_performance(
        ticker, start_date, end_date, str(save_path), db_path, config_path=config_path
    )
    
    # Generate company data table
    print(f"\nGenerating company data table for {ticker}...")
    results['company_data_table'] = generate_company_data_table(
        ticker, as_of_date, str(save_path), db_path
    )
    
    # Generate key metrics table
    print(f"\nGenerating key metrics table for {ticker}...")
    results['key_metrics_table'] = generate_key_metrics_table(
        ticker, str(save_path), db_path
    )
    
    # Generate income statement table
    print(f"\nGenerating income statement table for {ticker}...")
    results['income_statement_table'] = generate_income_statement_table(
        ticker, str(save_path), db_path
    )
    
    # Generate balance sheet table
    print(f"\nGenerating balance sheet table for {ticker}...")
    results['balance_sheet_table'] = generate_balance_sheet_table(
        ticker, str(save_path), db_path
    )
    
    # Generate cash flow statement table
    print(f"\nGenerating cash flow statement table for {ticker}...")
    results['cash_flow_table'] = generate_cash_flow_table(
        ticker, str(save_path), db_path
    )
    
    return results


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate graphs from FMP data')
    parser.add_argument('ticker', type=str, help='Stock ticker symbol (e.g., TSLA)')
    parser.add_argument('--company-name', type=str, help='Company name (default: uses ticker)')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--as-of-date', type=str, help='As of date for company data (YYYY-MM-DD)')
    parser.add_argument('--save-path', type=str, default='./figs', help='Base directory to save graphs')
    parser.add_argument('--db-path', type=str, help='Path to database file')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("FMP Graph Generator")
    print("=" * 60)
    
    results = generate_all_graphs(
        ticker=args.ticker,
        company_name=args.company_name,
        start_date=args.start_date,
        end_date=args.end_date,
        as_of_date=args.as_of_date,
        base_save_path=args.save_path,
        db_path=args.db_path
    )
    
    print("\n" + "=" * 60)
    print("Graph Generation Complete")
    print("=" * 60)
    print("\nGenerated files:")
    for file_type, path in results.items():
        if path:
            print(f"  {file_type}: {path}")
        else:
            print(f"  {file_type}: Failed to generate")
