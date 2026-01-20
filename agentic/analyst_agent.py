#!/usr/bin/env python
"""
Analyst Agent for Equity Research

This agent acts as an equity research analyst with:
- Memory/scratch paper (log file for tracking analysis)
- Access to all database fields
- Multiple analysis loops for refinement
- Generates investment recommendation (overweight/neutral/underweight)
- Produces 3-paragraph main analysis
"""

import os
import sys
import sqlite3
import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import dotenv

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import OpenAI model
from agentic.openai_model import OpenAIModel

# Import data loading functions
from agentic.financial_forecastor_agent import load_all_data_from_cache
from agentic.fmp_data_puller import DEFAULT_DB_PATH
from agentic.fmp_graph_generator import load_financial_statements

# Load .env file
env_path = project_root / '.env'
if env_path.exists():
    dotenv.load_dotenv(dotenv_path=str(env_path), override=True)
else:
    dotenv.load_dotenv(override=True)


class AnalystAgent:
    """
    Equity Research Analyst Agent with memory and iterative analysis capability.
    """
    
    def __init__(
        self,
        model_name: str = None,
        temperature: float = 0.7,
        max_rounds: int = 3,
        db_path: str = None,
        log_path: str = None,
        save_path: str = None,
        config_path: str = None
    ):
        """
        Initialize the Analyst Agent.
        
        Args:
            model_name: OpenAI model name (default: from env or 'gpt-4')
            temperature: Temperature for generation (default: 0.7 for more creative analysis)
            max_rounds: Maximum number of analysis rounds (default: 3)
            db_path: Path to database. If None, uses default.
            log_path: Path to log file for memory/scratch paper. If None, uses default.
            save_path: Base directory to save analysis results. If None, uses './reports'.
            config_path: Path to config.yaml. If None, uses project_root/config.yaml.
        """
        self.model = OpenAIModel(
            model_name=model_name or os.getenv('OPENAI_MODEL', 'gpt-4'),
            temperature=temperature
        )
        self.max_rounds = max_rounds
        self.db_path = db_path or str(DEFAULT_DB_PATH)
        self.save_path = Path(save_path) if save_path else project_root / 'reports'
        self.model_name = model_name or os.getenv('OPENAI_MODEL', 'gpt-4')
        
        # Load configuration from config.yaml
        if config_path is None:
            config_path = project_root / 'config.yaml'
        else:
            config_path = Path(config_path)
        
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = {}
            print(f"Warning: Config file not found at {config_path}, using defaults")
        
        # Get analysis configuration from config
        analyst_config = self.config.get('inputs', {}).get('analyst_analysis', {})
        self.num_paragraphs = analyst_config.get('num_paragraphs', 4)  # Default to 4 paragraphs
        self.paragraph_length = analyst_config.get('paragraph_length', {})
        self.paragraph_topics = analyst_config.get('paragraph_topics', [
            "Context and key observations about recent performance/events",
            "Deep dive into financial fundamentals and trends",
            "Investment thesis and recommendation rationale",
            "Risk assessment and market outlook"
        ])
        
        # Get key points configuration from config
        key_points_config = analyst_config.get('key_points', {})
        self.key_points_num = key_points_config.get('num_points', 3)
        self.key_points_length_multiplier = key_points_config.get('length_multiplier', 1.75)
        self.key_points_prompt = key_points_config.get('prompt', 
            "Generate 3 concise but descriptive key points that capture the most important investment insights.")
        
        # Set up log file for memory/scratch paper
        if log_path is None:
            log_dir = project_root / 'agentic' / 'logs'
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / f'analyst_agent_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        self.log_path = Path(log_path)
        self.memory = []  # In-memory scratch paper
        
        # Build system prompt dynamically based on config
        topics_list = "\n   - ".join([f"Paragraph {i+1}: {topic}" for i, topic in enumerate(self.paragraph_topics[:self.num_paragraphs])])
        self.system_prompt = f"""You are a senior equity research analyst at a leading investment bank. 
Your role is to provide comprehensive, data-driven investment analysis and recommendations.

Key Responsibilities:
1. Analyze all available financial data, market data, and company information
2. Identify key trends, strengths, and risks
3. Provide clear investment recommendation: OVERWEIGHT, NEUTRAL, or UNDERWEIGHT
4. Write a compelling {self.num_paragraphs}-paragraph analysis that:
   - {topics_list}

Your analysis should be:
- Data-driven and evidence-based
- Balanced (acknowledge both strengths and weaknesses)
- Clear and professional
- Focused on actionable insights
- Similar in style to top-tier equity research reports (e.g., Morgan Stanley, Goldman Sachs)

Always base your recommendations on fundamental analysis, not speculation."""
    
    def log(self, message: str, round_num: int = None):
        """
        Log message to scratch paper/memory.
        
        Args:
            message: Message to log
            round_num: Analysis round number (optional)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if round_num is not None:
            log_entry = f"[Round {round_num}] {timestamp}: {message}"
        else:
            log_entry = f"{timestamp}: {message}"
        
        self.memory.append(log_entry)
        
        # Write to file
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(log_entry + '\n')
    
    def load_all_data(self, ticker: str) -> Dict:
        """
        Load all available data from database for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dictionary containing all available data
        """
        self.log(f"Loading all data for {ticker}")
        
        # Load data using existing functions
        data = load_all_data_from_cache(ticker, self.db_path)
        
        # Also load financial statements
        income_statements = load_financial_statements(ticker, 'income', 'annual', self.db_path)
        balance_sheets = load_financial_statements(ticker, 'balance', 'annual', self.db_path)
        cash_flows = load_financial_statements(ticker, 'cashflow', 'annual', self.db_path)
        
        data['financial_statements'] = {
            'income': income_statements,
            'balance': balance_sheets,
            'cashflow': cash_flows
        }
        
        # Load news from database
        news_list = self.load_news_from_db(ticker)
        data['news'] = news_list
        
        self.log(f"Loaded data: key_metrics={data.get('key_metrics') is not None}, "
                f"company_data={data.get('company_data') is not None}, "
                f"price_performance={data.get('price_performance') is not None}, "
                f"income_statements={income_statements is not None}, "
                f"balance_sheets={balance_sheets is not None}, "
                f"cash_flows={cash_flows is not None}, "
                f"news={len(news_list) if news_list else 0} articles")
        
        return data
    
    def load_news_from_db(self, ticker: str, limit: int = 20) -> List[Dict]:
        """
        Load recent news articles from database for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            limit: Maximum number of news articles to load (default: 20)
            
        Returns:
            List of news article dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Get most recent news articles
            c.execute('''
                SELECT news_title, news_time, news_summary, news_content, news_url, news_author
                FROM news
                WHERE stock_code = ?
                ORDER BY news_time DESC
                LIMIT ?
            ''', (ticker, limit))
            
            rows = c.fetchall()
            conn.close()
            
            news_list = []
            for row in rows:
                news_list.append({
                    'title': row[0],
                    'time': row[1],
                    'summary': row[2],
                    'content': row[3] or row[2],  # Use summary if content is empty
                    'url': row[4],
                    'source': row[5]
                })
            
            return news_list
            
        except Exception as e:
            self.log(f"Error loading news from database: {e}")
            return []
    
    def format_data_for_prompt(self, data: Dict, ticker: str) -> str:
        """
        Format all data into a comprehensive prompt for the analyst.
        
        Args:
            data: Dictionary containing all data
            ticker: Stock ticker symbol
            
        Returns:
            Formatted prompt string
        """
        prompt_parts = []
        prompt_parts.append(f"# Equity Research Analysis Request for {ticker}\n")
        prompt_parts.append(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d')}\n")
        
        # Key Metrics
        if data.get('key_metrics') and data['key_metrics'].get('metrics'):
            prompt_parts.append("\n## Key Financial Metrics\n")
            metrics = data['key_metrics']['metrics']
            fiscal_year_end = data['key_metrics'].get('fiscal_year_end', 'Dec')
            prompt_parts.append(f"Fiscal Year End: {fiscal_year_end}\n")
            
            # Sort years
            all_years = sorted(metrics.keys(), reverse=True, key=lambda x: int(x) if x.isdigit() else 0)
            current_year = int(datetime.now().strftime('%Y'))
            actual_years = [y for y in all_years if y.isdigit() and int(y) <= current_year]
            forecast_years = [y for y in all_years if y.isdigit() and int(y) > current_year]
            
            if actual_years:
                prompt_parts.append("\n### Actual Historical Data\n")
                for year in sorted(actual_years, reverse=True, key=int)[:3]:
                    year_data = metrics[year]
                    prompt_parts.append(f"\n**FY{year[-2:]} (Actual):**")
                    prompt_parts.append(f"- Revenue: ${year_data.get('revenue', 0):,.0f}M")
                    prompt_parts.append(f"- Adj. EBITDA: ${year_data.get('adj_ebitda', 0):,.0f}M")
                    prompt_parts.append(f"- Adj. Net Income: ${year_data.get('adj_net_income', 0):,.0f}M")
                    prompt_parts.append(f"- Net Margin: {year_data.get('net_margin', 0):.1f}%")
                    prompt_parts.append(f"- EBITDA Margin: {year_data.get('ebitda_margin', 0):.1f}%")
                    prompt_parts.append(f"- Revenue Growth Y/Y: {year_data.get('revenue_growth', 0):.1f}%")
                    prompt_parts.append(f"- Adj. EPS: ${year_data.get('adj_eps', 0):.2f}")
                    prompt_parts.append(f"- ROE: {year_data.get('roe', 0):.1f}%")
                    prompt_parts.append(f"- ROCE: {year_data.get('roce', 0):.1f}%")
            
            if forecast_years:
                prompt_parts.append("\n### Forecast Data\n")
                for year in sorted(forecast_years, key=int)[:2]:
                    year_data = metrics[year]
                    prompt_parts.append(f"\n**FY{year[-2:]} (Forecast):**")
                    prompt_parts.append(f"- Revenue: ${year_data.get('revenue', 0):,.0f}M")
                    prompt_parts.append(f"- Adj. EBITDA: ${year_data.get('adj_ebitda', 0):,.0f}M")
                    prompt_parts.append(f"- Adj. Net Income: ${year_data.get('adj_net_income', 0):,.0f}M")
                    prompt_parts.append(f"- Revenue Growth Y/Y: {year_data.get('revenue_growth', 0):.1f}%")
                    prompt_parts.append(f"- EBITDA Margin: {year_data.get('ebitda_margin', 0):.1f}%")
        
        # Company Data
        if data.get('company_data'):
            cd = data['company_data']
            prompt_parts.append("\n## Company Information\n")
            prompt_parts.append(f"As of Date: {cd.get('as_of_date')}")
            prompt_parts.append(f"- Market Cap: ${cd.get('market_cap', 0):,.0f}")
            prompt_parts.append(f"- Shares Outstanding: {cd.get('shares_outstanding', 0):,.0f}")
            prompt_parts.append(f"- 52W High: ${cd.get('52w_high', 0):.2f}")
            prompt_parts.append(f"- 52W Low: ${cd.get('52w_low', 0):.2f}")
            prompt_parts.append(f"- Volatility (90d): {cd.get('volatility_90d', 0):.2f}%")
            if cd.get('consensus_rating'):
                prompt_parts.append(f"- Analyst Consensus: {cd.get('consensus_rating')} ({cd.get('num_analysts', 0)} analysts)")
        
        # Price Performance
        if data.get('price_performance'):
            pp = data['price_performance']
            prompt_parts.append("\n## Price Performance Context\n")
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
        
        # Financial Statements Summary
        if data.get('financial_statements'):
            fs = data['financial_statements']
            prompt_parts.append("\n## Financial Statements Summary\n")
            
            if fs.get('income') and len(fs['income']) > 0:
                latest_income = fs['income'][0]
                prompt_parts.append(f"\nLatest Income Statement ({latest_income.get('date', 'N/A')}):")
                prompt_parts.append(f"- Revenue: ${(latest_income.get('revenue', 0) or 0) / 1e6:,.0f}M")
                prompt_parts.append(f"- Operating Income: ${(latest_income.get('operatingIncome', 0) or 0) / 1e6:,.0f}M")
                prompt_parts.append(f"- Net Income: ${(latest_income.get('netIncome', 0) or 0) / 1e6:,.0f}M")
            
            if fs.get('balance') and len(fs['balance']) > 0:
                latest_balance = fs['balance'][0]
                prompt_parts.append(f"\nLatest Balance Sheet ({latest_balance.get('date', 'N/A')}):")
                prompt_parts.append(f"- Total Assets: ${(latest_balance.get('totalAssets', 0) or 0) / 1e6:,.0f}M")
                prompt_parts.append(f"- Total Liabilities: ${(latest_balance.get('totalLiabilities', 0) or 0) / 1e6:,.0f}M")
                prompt_parts.append(f"- Total Equity: ${(latest_balance.get('totalStockholdersEquity', 0) or 0) / 1e6:,.0f}M")
            
            if fs.get('cashflow') and len(fs['cashflow']) > 0:
                latest_cf = fs['cashflow'][0]
                prompt_parts.append(f"\nLatest Cash Flow ({latest_cf.get('date', 'N/A')}):")
                prompt_parts.append(f"- Operating Cash Flow: ${(latest_cf.get('operatingCashFlow', 0) or 0) / 1e6:,.0f}M")
                prompt_parts.append(f"- Free Cash Flow: ${((latest_cf.get('operatingCashFlow', 0) or 0) - abs(latest_cf.get('capitalExpenditure', 0) or 0)) / 1e6:,.0f}M")
        
        # Recent News
        if data.get('news') and len(data['news']) > 0:
            prompt_parts.append("\n## Recent News & Events\n")
            prompt_parts.append("The following recent news articles may be relevant to the investment thesis:\n")
            
            # Show most recent news (limit to 10 most recent)
            recent_news = data['news'][:10]
            for i, news_item in enumerate(recent_news, 1):
                prompt_parts.append(f"\n**News {i} ({news_item.get('time', 'N/A')}):**")
                prompt_parts.append(f"- Title: {news_item.get('title', 'N/A')}")
                if news_item.get('summary'):
                    summary = news_item.get('summary', '')[:200]  # Limit summary length
                    prompt_parts.append(f"- Summary: {summary}{'...' if len(news_item.get('summary', '')) > 200 else ''}")
                if news_item.get('source'):
                    prompt_parts.append(f"- Source: {news_item.get('source', 'N/A')}")
        
        # Memory/Previous Analysis
        if self.memory:
            prompt_parts.append("\n## Previous Analysis Notes (Memory)\n")
            for entry in self.memory[-5:]:  # Last 5 entries
                prompt_parts.append(f"- {entry}")
        
        prompt_parts.append("\n## Analysis Task\n")
        prompt_parts.append("Based on all the data above, provide:")
        prompt_parts.append("1. Investment Recommendation: OVERWEIGHT, NEUTRAL, or UNDERWEIGHT")
        prompt_parts.append(f"2. A {self.num_paragraphs}-paragraph analysis covering:")
        
        # Add paragraph topics from config
        for i, topic in enumerate(self.paragraph_topics[:self.num_paragraphs], 1):
            prompt_parts.append(f"   - Paragraph {i}: {topic}")
        
        # Add word/character length requirements from config
        if self.paragraph_length:
            target_words = self.paragraph_length.get('target_words_per_paragraph', 80)
            min_words = self.paragraph_length.get('min_words_per_paragraph', 60)
            max_words = self.paragraph_length.get('max_words_per_paragraph', 100)
            target_chars = self.paragraph_length.get('target_chars_per_paragraph', 500)
            min_chars = self.paragraph_length.get('min_chars_per_paragraph', 400)
            max_chars = self.paragraph_length.get('max_chars_per_paragraph', 600)
            
            prompt_parts.append(f"\nLength Requirements (per paragraph):")
            prompt_parts.append(f"   - Target: {target_words} words ({target_chars} characters)")
            prompt_parts.append(f"   - Range: {min_words}-{max_words} words ({min_chars}-{max_chars} characters)")
            prompt_parts.append(f"   - Total target: {target_words * self.num_paragraphs} words ({target_chars * self.num_paragraphs} characters) across all {self.num_paragraphs} paragraphs")
        
        # Add key points requirements from config
        prompt_parts.append(f"\n3. Key Points ({self.key_points_num} points):")
        prompt_parts.append(self.key_points_prompt)
        prompt_parts.append(f"\n   - Each key point should be approximately {self.key_points_length_multiplier}x longer than typical bullet points")
        prompt_parts.append(f"   - Target length: 8-15 words per key point (1.5-2x longer than short phrases)")
        prompt_parts.append(f"   - These will be used to generate the report headline, so they should be descriptive and meaningful")
        
        # Add highlighting instructions
        prompt_parts.append("\n4. Text Highlighting:")
        prompt_parts.append("   - In your analysis paragraphs, wrap important financial metrics, key numbers, and")
        prompt_parts.append("     critical insights with <highlight> tags.")
        prompt_parts.append("   - Examples of what to highlight:")
        prompt_parts.append("     * Financial metrics with numbers: 'EBITDA margin of 15.1%', 'revenue growth of 0.9% YoY'")
        prompt_parts.append("     * Key performance indicators: 'EPS of $2.50', 'ROE of 18.5%'")
        prompt_parts.append("     * Important trends: 'sluggish revenue growth', 'stable margins'")
        prompt_parts.append("     * Critical numbers: 'net income of $500M', 'price target of $150'")
        prompt_parts.append("   - Format: <highlight>text to highlight</highlight>")
        prompt_parts.append("   - Highlight 3-5 key phrases per paragraph that are most important for investors.")
        
        prompt_parts.append("\nReturn your response as a JSON object with the following structure:")
        
        # Build JSON structure dynamically based on num_paragraphs and key_points_num
        paragraph_keys = ", ".join([f'"paragraph_{i}": "..."' for i in range(1, self.num_paragraphs + 1)])
        key_points_example = ", ".join([f'"point{i}"' for i in range(1, self.key_points_num + 1)])
        json_structure = f"""{{
  "recommendation": "OVERWEIGHT" | "NEUTRAL" | "UNDERWEIGHT",
  "analysis": {{
    {paragraph_keys}
  }},
  "key_points": [{key_points_example}],
  "risks": ["risk1", "risk2"],
  "catalysts": ["catalyst1", "catalyst2"]
}}"""
        prompt_parts.append(json_structure)
        prompt_parts.append("\nImportant: Return ONLY valid JSON, no additional text or explanation.")
        prompt_parts.append("Remember: Use <highlight> tags in your paragraph text to mark important financial metrics and insights.")
        
        return "\n".join(prompt_parts)
    
    def analyze(
        self,
        ticker: str,
        round_num: int = 1
    ) -> Optional[Dict]:
        """
        Perform one round of analysis.
        
        Args:
            ticker: Stock ticker symbol
            round_num: Current round number
            
        Returns:
            Dictionary with analysis results, or None on error
        """
        self.log(f"Starting analysis round {round_num} for {ticker}", round_num)
        
        # Load all data
        data = self.load_all_data(ticker)
        
        # Format prompt
        prompt = self.format_data_for_prompt(data, ticker)
        self.log(f"Prompt length: {len(prompt)} characters", round_num)
        
        # Get analysis from OpenAI
        try:
            self.log("Calling OpenAI API for analysis", round_num)
            response_tuple, response_json = self.model.json_prompt(prompt)
            
            _, prompt_tokens, completion_tokens = response_tuple
            self.log(f"Analysis generated (tokens: {prompt_tokens} prompt + {completion_tokens} completion)", round_num)
            
            # Validate response
            if isinstance(response_json, dict):
                # Log key findings
                recommendation = response_json.get('recommendation', 'UNKNOWN')
                self.log(f"Recommendation: {recommendation}", round_num)
                
                if 'analysis' in response_json:
                    self.log("Analysis paragraphs generated", round_num)
                
                return response_json
            else:
                self.log(f"Error: Expected dict, got {type(response_json)}", round_num)
                return None
                
        except Exception as e:
            self.log(f"Error generating analysis: {e}", round_num)
            import traceback
            traceback.print_exc()
            return None
    
    def run(
        self,
        ticker: str,
        refine: bool = True
    ) -> Dict:
        """
        Run complete analysis with multiple rounds.
        
        Args:
            ticker: Stock ticker symbol
            refine: If True, run multiple rounds to refine analysis (default: True)
            
        Returns:
            Dictionary with final analysis results
        """
        self.log(f"Starting analysis for {ticker}")
        self.log(f"Max rounds: {self.max_rounds}, Refine: {refine}")
        
        # Load data once to get company name
        self._last_loaded_data = self.load_all_data(ticker)
        
        results = []
        
        # Run analysis rounds
        for round_num in range(1, self.max_rounds + 1):
            self.log(f"\n{'='*60}", round_num)
            self.log(f"Analysis Round {round_num}", round_num)
            self.log(f"{'='*60}", round_num)
            
            analysis = self.analyze(ticker, round_num)
            
            if analysis:
                results.append(analysis)
                self.log(f"Round {round_num} completed successfully", round_num)
                
                # If not refining, return first result
                if not refine:
                    break
                
                # Add analysis to memory for next round
                if 'analysis' in analysis:
                    memory_entry = f"Round {round_num} Analysis: {analysis.get('recommendation', 'N/A')} - "
                    if 'key_points' in analysis:
                        memory_entry += f"Key points: {', '.join(analysis['key_points'][:3])}"
                    self.memory.append(memory_entry)
            else:
                self.log(f"Round {round_num} failed", round_num)
                if results:
                    # Use last successful result
                    break
        
        # Return final result (last round if refining, first if not)
        if results:
            final_result = results[-1]
            final_result['rounds_completed'] = len(results)
            final_result['log_path'] = str(self.log_path)
            final_result['ticker'] = ticker
            final_result['analysis_date'] = datetime.now().strftime('%Y-%m-%d')
            final_result['model_name'] = self.model_name
            self.log(f"Analysis complete. Final recommendation: {final_result.get('recommendation', 'N/A')}")
            
            # Save results to file (use save_dir if provided via attribute)
            save_dir = getattr(self, '_save_dir', None)
            self.save_results(ticker, final_result, save_dir=save_dir)
            
            return final_result
        else:
            self.log("Analysis failed - no successful rounds")
            error_result = {
                'recommendation': 'N/A',
                'analysis': {
                    **{f'paragraph_{i}': f'Analysis failed to generate (paragraph {i}).' for i in range(1, self.num_paragraphs + 1)}
                },
                'rounds_completed': 0,
                'log_path': str(self.log_path),
                'ticker': ticker,
                'analysis_date': datetime.now().strftime('%Y-%m-%d'),
                'model_name': self.model_name
            }
            # Still save error result
            self.save_results(ticker, error_result)
            return error_result
    
    def save_results(self, ticker: str, result: Dict, save_dir: Path = None):
        """
        Save analysis results to file.
        
        Args:
            ticker: Stock ticker symbol
            result: Analysis result dictionary
            save_dir: Optional directory to save results. If None, creates new directory.
        """
        try:
            if save_dir is None:
                # Try to get company name from loaded data, otherwise use ticker
                # Format: {ticker}_{timestamp} or {company_name}_{timestamp} (matching equity_report_generator format)
                company_name = ticker
                if hasattr(self, '_last_loaded_data') and self._last_loaded_data:
                    # Try to get company name from FMP API response if available
                    # For now, use ticker to match user's example: TSLA_20260119_192828
                    pass
                
                # Create save directory: {ticker}_{timestamp} (matching equity_report_generator format)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                save_dir = self.save_path / f"{ticker}_{timestamp}"
            
            # Ensure directory exists
            save_dir = Path(save_dir)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # Save as JSON
            json_path = save_dir / 'analysis_result.json'
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            # Also save as pickle for compatibility with existing system
            import pickle
            pickle_path = save_dir / 'analysis_result.pkl'
            with open(pickle_path, 'wb') as f:
                pickle.dump(result, f)
            
            # Save a human-readable text file
            text_path = save_dir / 'analysis_result.txt'
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("Equity Research Analysis Result\n")
                f.write("=" * 60 + "\n\n")
                f.write(f"Ticker: {ticker}\n")
                f.write(f"Analysis Date: {result.get('analysis_date', 'N/A')}\n")
                f.write(f"Model: {result.get('model_name', 'N/A')}\n")
                f.write(f"Rounds Completed: {result.get('rounds_completed', 0)}\n")
                f.write(f"\nRecommendation: {result.get('recommendation', 'N/A')}\n")
                f.write("\n" + "=" * 60 + "\n")
                f.write("Analysis\n")
                f.write("=" * 60 + "\n\n")
                
                if 'analysis' in result:
                    analysis = result['analysis']
                    for i in range(1, self.num_paragraphs + 1):
                        f.write(f"Paragraph {i}:\n")
                        f.write(analysis.get(f'paragraph_{i}', 'N/A') + "\n\n")
                
                if 'key_points' in result and result['key_points']:
                    f.write("=" * 60 + "\n")
                    f.write("Key Points\n")
                    f.write("=" * 60 + "\n")
                    for point in result['key_points']:
                        f.write(f"- {point}\n")
                    f.write("\n")
                
                if 'risks' in result and result['risks']:
                    f.write("=" * 60 + "\n")
                    f.write("Key Risks\n")
                    f.write("=" * 60 + "\n")
                    for risk in result['risks']:
                        f.write(f"- {risk}\n")
                    f.write("\n")
                
                if 'catalysts' in result and result['catalysts']:
                    f.write("=" * 60 + "\n")
                    f.write("Key Catalysts\n")
                    f.write("=" * 60 + "\n")
                    for catalyst in result['catalysts']:
                        f.write(f"- {catalyst}\n")
                    f.write("\n")
                
                f.write("=" * 60 + "\n")
                f.write(f"Log File: {result.get('log_path', 'N/A')}\n")
                f.write("=" * 60 + "\n")
            
            self.log(f"Results saved to: {save_dir}")
            result['save_path'] = str(save_dir)
            
        except Exception as e:
            self.log(f"Error saving results: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Equity Research Analyst Agent')
    parser.add_argument('ticker', type=str, help='Stock ticker symbol (e.g., TSLA)')
    parser.add_argument('--model', type=str, help='OpenAI model name (default: from env or gpt-4)')
    parser.add_argument('--temperature', type=float, default=0.7, help='Temperature for generation (default: 0.7)')
    parser.add_argument('--max-rounds', type=int, default=3, help='Maximum analysis rounds (default: 3)')
    parser.add_argument('--no-refine', action='store_true', help='Disable multi-round refinement')
    parser.add_argument('--db-path', type=str, help='Path to database file')
    parser.add_argument('--log-path', type=str, help='Path to log file')
    parser.add_argument('--save-path', type=str, default='./reports', help='Base directory to save results (default: ./reports)')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Equity Research Analyst Agent")
    print("=" * 60)
    
    # Create agent
    agent = AnalystAgent(
        model_name=args.model,
        temperature=args.temperature,
        max_rounds=args.max_rounds,
        db_path=args.db_path,
        log_path=args.log_path,
        save_path=args.save_path
    )
    
    # Run analysis
    result = agent.run(args.ticker, refine=not args.no_refine)
    
    # Print results
    print("\n" + "=" * 60)
    print("Analysis Complete")
    print("=" * 60)
    print(f"\nRecommendation: {result.get('recommendation', 'N/A')}")
    print(f"Rounds Completed: {result.get('rounds_completed', 0)}")
    print(f"Log File: {result.get('log_path', 'N/A')}")
    print(f"Results Saved To: {result.get('save_path', 'N/A')}")
    
    if 'analysis' in result:
        print("\n" + "=" * 60)
        print("Analysis")
        print("=" * 60)
        analysis = result['analysis']
        for i in range(1, self.num_paragraphs + 1):
            print(f"\nParagraph {i}:\n{analysis.get(f'paragraph_{i}', 'N/A')}")
    
    if 'key_points' in result:
        print("\n" + "=" * 60)
        print("Key Points")
        print("=" * 60)
        for point in result['key_points']:
            print(f"- {point}")
    
    if 'risks' in result:
        print("\n" + "=" * 60)
        print("Key Risks")
        print("=" * 60)
        for risk in result['risks']:
            print(f"- {risk}")
    
    if 'catalysts' in result:
        print("\n" + "=" * 60)
        print("Key Catalysts")
        print("=" * 60)
        for catalyst in result['catalysts']:
            print(f"- {catalyst}")
    
    print("\n" + "=" * 60)


if __name__ == '__main__':
    main()
