import os
from pathlib import Path
import dotenv

# Ensure .env file is loaded before importing other modules
# Try multiple locations to find .env file
if __file__:
    # Try from module location
    project_root = Path(__file__).parent.parent.parent
    env_path = project_root / '.env'
    if env_path.exists():
        dotenv.load_dotenv(dotenv_path=str(env_path), override=True)
    else:
        # Fallback: try current working directory
        cwd_env = Path.cwd() / '.env'
        if cwd_env.exists():
            dotenv.load_dotenv(dotenv_path=str(cwd_env), override=True)
        else:
            # Last fallback: search from current directory up
            dotenv.load_dotenv(override=True)
else:
    # If __file__ is not available, try current working directory and default search
    cwd_env = Path.cwd() / '.env'
    if cwd_env.exists():
        dotenv.load_dotenv(dotenv_path=str(cwd_env), override=True)
    else:
        dotenv.load_dotenv(override=True)

# Verify API key is loaded before importing modules that need it
if not os.getenv('OPENAI_API_KEY'):
    print("Warning: OPENAI_API_KEY not found. Make sure .env file exists in project root with OPENAI_API_KEY=your_key")

# Import agentic modules
# Add project root to path for agentic imports
import sys
# project_root is already defined above, reuse it
if __file__:
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from agentic.analyst_agent import AnalystAgent
from agentic.fmp_graph_generator import (
    plot_price_performance,
    generate_company_data_table,
    generate_key_metrics_table,
    generate_income_statement_table,
    generate_balance_sheet_table,
    generate_cash_flow_table
)
from agentic.fmp_data_puller import DEFAULT_DB_PATH

# Import existing modules for data retrieval
from finrpt.utils.ReportBuild import build_report
from finrpt.module.RiskAssessor import RiskAssessor
from agentic.financial_forecastor_agent import load_all_data_from_cache
from agentic.fmp_graph_generator import load_financial_statements
import logging
import json
import pickle
import sqlite3
import yaml
from datetime import datetime, timedelta


def setup_logger(log_name='ep', log_file='ep.log'):
    logger = logging.getLogger(log_name)
    logger.setLevel(logging.DEBUG)

    if logger.hasHandlers():
        logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    return logger


class EP:
    """
    Equity Research Pipeline using Agentic modules.
    
    This class integrates:
    - AnalystAgent for comprehensive equity analysis
    - FMP graph generator for visualizations
    - Updated report builder with new format
    """
    
    def __init__(
        self, 
        model_name="gpt-4o", 
        temperature=0.7,
        max_rounds=3, 
        language='en', 
        database_name=None, 
        save_path='./reports'
    ):
        """
        Initialize the EP (Equity Pipeline) class.
        
        Args:
            model_name: OpenAI model name (default: 'gpt-4o')
            temperature: Temperature for generation (default: 0.7)
            max_rounds: Maximum analysis rounds (default: 3)
            language: Language for analysis (default: 'zh')
            database_name: Path to database. If None, uses default.
            save_path: Base directory to save reports (default: './reports')
        """
        if "finetune" in model_name:
            real_model_name = model_name
            model_name = 'gpt-4o'
        else:
            real_model_name = model_name
        
        # Set default database path if not provided
        if database_name is None:
            if __file__:
                project_root = Path(__file__).parent.parent.parent
                database_name = project_root / 'finrpt' / 'source' / 'cache.db'
            else:
                database_name = 'finrpt/source/cache.db'
        
        # Initialize analyst agent
        self.analyst_agent = AnalystAgent(
            model_name=real_model_name,
            temperature=temperature,
            max_rounds=max_rounds,
            db_path=str(database_name),
            save_path=save_path
        )
        
        # Initialize risk assessor (still using existing module)
        self.risk_assessor = RiskAssessor(
            model_name=real_model_name, 
            max_rounds=max_rounds, 
            language=language
        )
        
        self.model_name = real_model_name
        self.save_path = save_path
        self.db_path = str(database_name)
        
    def run(self, date=None, stock_code=None, company_name=None, config_path='config.yaml'):
        """
        Run the complete equity research pipeline.
        
        Args:
            date: Analysis date in YYYY-MM-DD format (if None, reads from config.yaml)
            stock_code: Stock ticker symbol (if None, reads from config.yaml)
            company_name: Company name (alternative to stock_code, not used if stock_code from config)
            config_path: Path to config.yaml file (default: 'config.yaml')
        """
        # Load config.yaml to get ticker and report_date if not provided
        if __file__:
            project_root = Path(__file__).parent.parent.parent
            config_file = project_root / config_path
        else:
            config_file = Path(config_path)
        
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Get ticker and date from config if not provided
            if stock_code is None and config.get('inputs', {}).get('source_report', {}).get('ticker'):
                stock_code = config['inputs']['source_report']['ticker']
                logger_temp = logging.getLogger('temp')
                logger_temp.info(f"Loaded ticker from config: {stock_code}")
            
            if date is None and config.get('inputs', {}).get('source_report', {}).get('report_date'):
                date = config['inputs']['source_report']['report_date']
                logger_temp = logging.getLogger('temp')
                logger_temp.info(f"Loaded report_date from config: {date}")
        
        assert stock_code is not None, 'stock_code must be provided or specified in config.yaml'
        assert date is not None, 'date must be provided or specified in config.yaml'
        
        run_path = os.path.join(self.save_path, stock_code + "_" + date + "_" + self.model_name)
        os.makedirs(run_path, exist_ok=True)
        log_file = os.path.join(run_path, 'ep.log')
        if os.path.isfile(log_file):
            os.remove(log_file)
        logger = setup_logger(log_name=run_path, log_file=log_file)
        
        data = {"save": {}}
        data["save"]["id"] = stock_code + "_" + date
        data["save"]["stock_code"] = stock_code
        data["save"]["date"] = date
        data["model_name"] = self.model_name
        data["date"] = date

        logger.info("Starting EP (Equity Pipeline)")
        logger.info(f"Ticker: {stock_code}, Date: {date}")
        
        # Load all data from FMP database
        logger.info(f"Loading data from FMP database for {stock_code}")
        try:
            fmp_data = load_all_data_from_cache(stock_code, self.db_path)
            
            # Get company name from company_data if available
            if fmp_data.get('company_data'):
                company_data = fmp_data['company_data']
                # Try to get company name from database or use ticker
                data["company_name"] = company_data.get('company_name', stock_code)
                data["stock_code"] = stock_code
            else:
                data["company_name"] = stock_code
                data["stock_code"] = stock_code
            
            # Create company_info structure for backward compatibility
            data["company_info"] = {
                "stock_code": stock_code,
                "company_name": data["company_name"],
                "stock_exchange": fmp_data.get('company_data', {}).get('primary_index_name', 'N/A'),
                "industry_category": "N/A"  # Not available in FMP data
            }
            data["save"]["company_info"] = data["company_info"]
            
            logger.info(f"Got company info: {data['company_name']} ({data['stock_code']})")
            
            # Load financial statements from FMP database
            logger.info(f"Loading financial statements for {data['company_name']}")
            income_statements = load_financial_statements(stock_code, 'income', 'annual', self.db_path)
            balance_sheets = load_financial_statements(stock_code, 'balance', 'annual', self.db_path)
            cash_flows = load_financial_statements(stock_code, 'cashflow', 'annual', self.db_path)
            
            # Store FMP data
            # Note: Report builder may expect 'stock_income' format from akshare
            # This is a minimal structure for backward compatibility
            data["financials"] = {
                'fmp_data': fmp_data,
                'income_statements': income_statements,
                'balance_sheets': balance_sheets,
                'cash_flows': cash_flows,
                # Minimal structure for report builder compatibility
                'stock_income': None  # Will be handled by report builder or needs update
            }
            data["save"]["financials"] = data["financials"]
            logger.info("Loaded financial data from FMP database")
            
        except Exception as e:
            logger.error(f"Error loading data from FMP database: {e}")
            import traceback
            traceback.print_exc()
            # Set defaults
            data["company_name"] = stock_code
            data["stock_code"] = stock_code
            data["company_info"] = {
                "stock_code": stock_code,
                "company_name": stock_code,
                "stock_exchange": "N/A",
                "industry_category": "N/A"
            }
            data["financials"] = {
                'stock_income': None  # Minimal structure for backward compatibility
            }
        
        # Set empty news and report (not using akshare anymore)
        data["news"] = []
        data["save"]["news"] = []
        data["report"] = {
            'report_id': stock_code + date,
            'date': date,
            'content': '',
            'stock_code': stock_code,
            'title': '',
            'core_content': ''
        }
        data["save"]["report"] = data["report"]
        
        # Get trend (for backward compatibility)
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute(f''' SELECT * FROM trend WHERE  id='{stock_code}_{date}' ''')
            trend = c.fetchone()
            c.close()
            conn.close()
        except Exception as e:
            logger.warning(f"Error getting trend: {e}")
            trend = None
            
        if trend is not None and len(trend) > 3:
            data["trend"] = 1 if trend[3] > 0 else 0
        else:
            data["trend"] = 0
        
        # Generate graphs using agentic graph generator
        logger.info(f"Generating graphs for {data['company_name']} at {data['date']}")
        figs_path = os.path.join(run_path, "figs")
        os.makedirs(figs_path, exist_ok=True)
        
        # Calculate date range for price performance (1 year back)
        try:
            end_date = datetime.strptime(date, "%Y-%m-%d")
            start_date = (end_date - timedelta(days=365)).strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")
        except Exception as e:
            logger.warning(f"Error parsing date: {e}")
            start_date = None
            end_date_str = date
        
        # Generate price performance graph
        try:
            logger.info("Generating price performance graph...")
            plot_price_performance(
                ticker=data["stock_code"],
                start_date=start_date,
                end_date=end_date_str,
                save_path=figs_path,
                db_path=self.db_path
            )
            logger.info("Price performance graph generated successfully")
        except Exception as e:
            logger.error(f"Error generating price performance graph: {e}")
        
        # Generate company data table
        try:
            logger.info("Generating company data table...")
            generate_company_data_table(
                ticker=data["stock_code"],
                as_of_date=date,
                save_path=figs_path,
                db_path=self.db_path
            )
            logger.info("Company data table generated successfully")
        except Exception as e:
            logger.error(f"Error generating company data table: {e}")
        
        # Generate additional financial statement tables (optional)
        try:
            logger.info("Generating key metrics table...")
            generate_key_metrics_table(
                ticker=data["stock_code"],
                save_path=figs_path,
                db_path=self.db_path
            )
        except Exception as e:
            logger.warning(f"Error generating key metrics table: {e}")
        
        try:
            logger.info("Generating income statement table...")
            generate_income_statement_table(
                ticker=data["stock_code"],
                save_path=figs_path,
                db_path=self.db_path
            )
        except Exception as e:
            logger.warning(f"Error generating income statement table: {e}")
        
        try:
            logger.info("Generating balance sheet table...")
            generate_balance_sheet_table(
                ticker=data["stock_code"],
                save_path=figs_path,
                db_path=self.db_path
            )
        except Exception as e:
            logger.warning(f"Error generating balance sheet table: {e}")
        
        try:
            logger.info("Generating cash flow statement table...")
            generate_cash_flow_table(
                ticker=data["stock_code"],
                save_path=figs_path,
                db_path=self.db_path
            )
        except Exception as e:
            logger.warning(f"Error generating cash flow statement table: {e}")
        
        # Run analyst agent for comprehensive analysis
        logger.info(f"Running analyst agent for {data['company_name']} ({data['stock_code']})")
        try:
            analyst_result = self.analyst_agent.run(
                ticker=data["stock_code"],
                refine=True
            )
            data["analyst_analysis"] = analyst_result
            data["save"]["analyst_analysis"] = analyst_result
            logger.info(f"Analyst agent completed. Recommendation: {analyst_result.get('recommendation', 'N/A')}")
        except Exception as e:
            logger.error(f"Error running analyst agent: {e}")
            import traceback
            traceback.print_exc()
            # Create fallback analysis structure
            data["analyst_analysis"] = {
                'recommendation': 'N/A',
                'analysis': {
                    'paragraph_1': 'Analysis could not be generated.',
                    'paragraph_2': 'Please check data availability and try again.',
                    'paragraph_3': 'Error occurred during analysis.'
                }
            }
        
        # Run risk assessor (for backward compatibility)
        logger.info(f"Analyzing risk for {data['company_name']} at {data['date']}")
        try:
            data['analyze_risk'] = self.risk_assessor.run(data, run_path=run_path)
            data["save"]["analyze_risk"] = data['analyze_risk']
        except Exception as e:
            logger.warning(f"Error analyzing risk: {e}")
            data['analyze_risk'] = []
        
        # Set report title
        data['report_title'] = data["company_info"]["company_name"] + "研报（" + date + "）"
        
        # Save results
        result_save_path = os.path.join(run_path, 'result.pkl')
        pickle.dump(data['save'], open(result_save_path, 'wb'))
        logger.info(f"Results saved to {result_save_path}")
        
        # Build report using updated report builder
        logger.info(f"Building report for {data['company_name']} at {data['date']}")
        try:
            build_report(data, date, run_path)
            logger.info(f"Report built successfully at {run_path}")
        except Exception as e:
            logger.error(f"Error building report: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        return data


if __name__ == '__main__':
    # Example usage - reads from config.yaml by default
    ep = EP(model_name="gpt-4o", max_rounds=3)
    # If config.yaml has ticker and report_date, they will be used automatically
    ep.run()  # Reads from config.yaml
    # Or specify explicitly:
    # ep.run(date='2024-11-05', stock_code='TSLA')
