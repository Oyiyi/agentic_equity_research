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
    db_path: str = None
) -> Optional[str]:
    """
    Generate price performance graph comparing stock vs base index.
    
    Args:
        ticker: Stock ticker symbol
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        save_path: Directory to save the graph
        db_path: Path to database. If None, uses default.
        
    Returns:
        Path to saved graph file, or None on error.
    """
    data = load_price_performance_data(ticker, start_date, end_date, db_path)
    if not data:
        return None
    
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
    
    # Create figure
    plt.figure(figsize=(12, 7))
    
    # Plot rebased close prices
    plt.plot(stock_df.index, stock_df['rebased_close'], 
             label=ticker, color='#9E1F00', linewidth=3)
    plt.plot(index_df.index, index_df['rebased_close'], 
             label=base_index, color='#d45716', linewidth=3)
    
    # Formatting
    plt.xlabel('Date', fontsize=14, color='#6a6a6a')
    plt.ylabel('Rebased Price (Base = 100)', fontsize=14, color='#6a6a6a', fontweight='bold')
    # Title removed as requested
    
    # Format x-axis dates
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=45)
    
    # Format y-axis
    plt.gca().yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'{y:.0f}'))
    
    # Legend
    plt.legend(loc='upper left', fontsize=12, frameon=False, labelcolor='#6a6a6a')
    
    # Grid and spines
    plt.grid(visible=True, alpha=0.3, linestyle='--')
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#6a6a6a')
    ax.spines['bottom'].set_color('#6a6a6a')
    ax.tick_params(colors='#6a6a6a', labelsize=11)
    
    plt.tight_layout()
    
    # Save figure
    save_dir = Path(save_path)
    save_dir.mkdir(parents=True, exist_ok=True)
    plot_path = save_dir / 'graph_price_performance.png'
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
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
    
    # Style the table - tightest vertical spacing, no borders
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 0.5)  # Very tight rows
    
    # Style cells - remove all borders, minimal padding
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
            cell.set_height(0.02)
            cell.PAD = 0.0  # Zero padding
    
    # Add title - use the latest complete fiscal year in the title
    # The title should reflect the most recent actual data year
    title_text = f'Key Metrics (FYE {fiscal_year_end})'
    # Add subtitle showing the actual years covered
    subtitle_text = f'Latest Actual: FY{latest_complete_fy[-2:]}'
    fig.text(0.5, 0.98, title_text, fontsize=12, fontweight='bold', 
             ha='center', va='top')
    fig.text(0.5, 0.96, '$ in millions', fontsize=9, 
             ha='center', va='top')
    
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    
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


def generate_all_graphs(
    ticker: str,
    company_name: str = None,
    start_date: str = None,
    end_date: str = None,
    as_of_date: str = None,
    base_save_path: str = './figs',
    db_path: str = None
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
        ticker, start_date, end_date, str(save_path), db_path
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
