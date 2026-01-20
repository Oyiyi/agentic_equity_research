#!/usr/bin/env python
"""
Equity Report Generator

This module generates a professional equity research report page similar to J.P. Morgan style.
It integrates:
- analyst_agent: For generating 3-paragraph analysis and recommendation
- fmp_data_puller: For financial data
- fmp_graph_generator: For tables and charts
- reportlab: For PDF generation

Usage:
    python agentic/equity_report_generator.py TSLA
    
    Or from Python:
    from agentic.equity_report_generator import EquityReportGenerator
    generator = EquityReportGenerator(ticker='TSLA', company_name='Tesla Inc')
    generator.generate_report()
"""

import os
import sys
import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import dotenv

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ReportLab imports
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.colors import Color, HexColor, black, white
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, Frame, PageTemplate
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfgen import canvas

# Import agentic modules
from agentic.analyst_agent import AnalystAgent
from agentic.fmp_data_puller import pull_tesla_data, DEFAULT_DB_PATH
from agentic.financial_forecastor_agent import load_all_data_from_cache
from agentic.fmp_graph_generator import generate_all_graphs, load_key_metrics, load_company_data, load_financial_statements

# Load .env file
env_path = project_root / '.env'
if env_path.exists():
    dotenv.load_dotenv(dotenv_path=str(env_path), override=True)
else:
    dotenv.load_dotenv(override=True)


def hex_to_color(hex_color: str) -> Color:
    """Convert hex color string to ReportLab Color object"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return Color(r, g, b)
    return black


class EquityReportGenerator:
    """
    Generator for professional equity research reports.
    Style and branding are loaded from config.yaml.
    """
    
    def __init__(
        self,
        ticker: str,
        company_name: str = None,
        db_path: str = None,
        output_dir: str = None,
        model_name: str = None,
        config_path: str = None
    ):
        """
        Initialize the Equity Report Generator.
        
        Args:
            ticker: Stock ticker symbol
            company_name: Company name (default: uses ticker)
            db_path: Path to database (default: finrpt/source/cache.db)
            output_dir: Directory to save reports (default: ./reports)
            model_name: OpenAI model name for analyst agent
            config_path: Path to config.yaml (default: project_root/config.yaml)
        """
        self.ticker = ticker
        self.company_name = company_name or ticker
        self.db_path = db_path or str(DEFAULT_DB_PATH)
        self.output_dir = Path(output_dir) if output_dir else project_root / 'reports'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        # Store project root for later use (e.g., logo path resolution)
        self._project_root = project_root
        
        # Load configuration from config.yaml
        if config_path is None:
            config_path = project_root / 'config.yaml'
        else:
            config_path = Path(config_path)
        
        # Store config_path for later use (e.g., passing to AnalystAgent)
        self._config_path = config_path
        self.config = self._load_config(config_path)
        
        # Load brand and styling from config
        self.brand_name = self.config.get('brand', {}).get('name', 'Morgan Stanley')
        self.brand_colors = self.config.get('brand', {}).get('colors', {})
        self.typography = self.config.get('typography', {})
        self.layout = self.config.get('layout', {})
        self.header_config = self.layout.get('header', {})
        self.footer_config = self.layout.get('footer', {})
        
        # Set colors from config
        primary_color_hex = self.brand_colors.get('primary', {}).get('hex', '#0060A0')
        self.color_primary = HexColor(primary_color_hex)
        
        secondary_color_hex = self.brand_colors.get('secondary', {}).get('hex', '#1090D0')
        self.color_secondary = HexColor(secondary_color_hex)
        
        accent_color_hex = self.brand_colors.get('accent', {}).get('hex', '#D0B060')
        self.color_accent = HexColor(accent_color_hex)
        
        neutrals = self.brand_colors.get('neutrals', {})
        self.color_text = HexColor(neutrals.get('black', {}).get('hex', '#111111'))
        self.color_dark_grey = HexColor(neutrals.get('dark_grey', {}).get('hex', '#4A4A4A'))
        self.color_grey = HexColor(neutrals.get('mid_grey', {}).get('hex', '#7A7A7A'))
        self.color_light_grey = HexColor(neutrals.get('light_grey', {}).get('hex', '#E6E6E6'))
        self.color_white = HexColor(neutrals.get('white', {}).get('hex', '#FFFFFF'))
        
        # Get table style colors from config
        table_style_config = self.config.get('components', {}).get('table_style', {})
        if table_style_config:
            header_style = table_style_config.get('header', {})
            body_style = table_style_config.get('body', {})
            border_style = table_style_config.get('borders', {})
            
            self.table_header_fill = HexColor(header_style.get('fill', primary_color_hex))
            self.table_header_text_color = HexColor(header_style.get('text_color', '#FFFFFF'))
            self.table_body_text_color = HexColor(body_style.get('text_color', neutrals.get('black', {}).get('hex', '#111111')))
            self.table_stripe_fill = HexColor(body_style.get('stripe_fill', '#F5F5F5'))
            self.table_border_color = HexColor(border_style.get('color', neutrals.get('light_grey', {}).get('hex', '#E6E6E6')))
            self.table_border_thickness = border_style.get('thickness_pt', 0.5)
            self.table_zebra_stripes = body_style.get('zebra_stripes', True)
        else:
            # Fallback to brand colors
            self.table_header_fill = self.color_primary
            self.table_header_text_color = self.color_white
            self.table_body_text_color = self.color_text
            self.table_stripe_fill = HexColor('#F5F5F5')
            self.table_border_color = self.color_light_grey
            self.table_border_thickness = 0.5
            self.table_zebra_stripes = True
        
        # Page dimensions from config
        self.page_width, self.page_height = LETTER
        margins = self.layout.get('page', {}).get('margins_in', {})
        self.margin_left = margins.get('left', 0.65) * inch
        self.margin_right = margins.get('right', 0.65) * inch
        self.margin_top = margins.get('top', 0.6) * inch
        self.margin_bottom = margins.get('bottom', 0.6) * inch
        
        # Column widths from config
        gutter_in = self.layout.get('page', {}).get('grid', {}).get('gutter_in', 0.35)
        self.gutter = gutter_in * inch
        self.left_col_width = 4.5 * inch
        self.right_col_width = 2.0 * inch
        
        # Font families from config
        primary_font = self.typography.get('primary_family', {})
        self.font_primary = primary_font.get('name', 'MSGloriolaIIStd')
        self.font_primary_fallbacks = primary_font.get('fallbacks', ['Georgia', 'Times New Roman', 'serif'])
        
        secondary_font = self.typography.get('secondary_family', {})
        self.font_secondary = secondary_font.get('name', 'Roboto')
        self.font_secondary_fallbacks = secondary_font.get('fallbacks', ['Arial', 'Helvetica', 'sans-serif'])
        
        # Data storage
        self.analysis_result = None
        self.financial_data = None
        self.company_data = None
        self.key_metrics = None
    
    def _get_font_name(self, preferred_font: str, fallbacks: List[str]) -> str:
        """
        Get font name, using fallback if preferred font is not available.
        ReportLab has limited built-in fonts, so we use fallbacks for custom fonts.
        """
        # ReportLab built-in fonts: Helvetica, Times-Roman, Courier, Symbol
        # For custom fonts like MSGloriolaIIStd, use fallback
        builtin_fonts = ['Helvetica', 'Times-Roman', 'Courier', 'Symbol', 
                        'Helvetica-Bold', 'Times-Bold', 'Courier-Bold',
                        'Helvetica-Oblique', 'Times-Italic', 'Courier-Oblique']
        
        # Check if preferred font is a built-in font
        if preferred_font in builtin_fonts:
            return preferred_font
        
        # For custom fonts, use first fallback that's built-in, or default to Helvetica
        for fallback in fallbacks:
            if fallback in builtin_fonts:
                return fallback
        
        # Default to Helvetica if no built-in fallback found
        return 'Helvetica'
    
    def _load_config(self, config_path: Path) -> Dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            print(f"Loaded configuration from {config_path}")
            return config or {}
        except FileNotFoundError:
            print(f"Warning: Config file not found at {config_path}, using defaults")
            return {}
        except Exception as e:
            print(f"Warning: Error loading config file: {e}, using defaults")
            return {}
        
    def load_data(self):
        """Load all required data from database and generate analysis."""
        print(f"Loading data for {self.ticker}...")
        
        # Get report date from config
        report_date_format = self.config.get('inputs', {}).get('source_report', {}).get('report_date')
        if report_date_format:
            try:
                report_date = datetime.strptime(report_date_format, '%Y-%m-%d')
                report_date_str = report_date.strftime('%Y-%m-%d')
            except:
                report_date = datetime.now()
                report_date_str = datetime.now().strftime('%Y-%m-%d')
        else:
            report_date = datetime.now()
            report_date_str = datetime.now().strftime('%Y-%m-%d')
        
        # Load financial data
        self.financial_data = load_all_data_from_cache(self.ticker, self.db_path)
        
        # Load company data for report date (will pull from API if not in cache)
        self.company_data = load_company_data(self.ticker, report_date_str, self.db_path)
        
        # If company_data not found in cache, try to pull from API
        if not self.company_data:
            print(f"Company data not in cache for {report_date_str}, attempting to pull from API...")
            from agentic.fmp_data_puller import pull_tesla_data
            try:
                result = pull_tesla_data(
                    ticker=self.ticker,
                    as_of_date=report_date_str,
                    end_date=report_date_str,
                    db_path=self.db_path
                )
                if result and result.get('company_data'):
                    self.company_data = result['company_data']
                    print("Company data pulled from API and cached")
            except Exception as e:
                print(f"Warning: Could not pull company data from API: {e}")
        
        # Load price performance data to get price for report date
        from agentic.fmp_graph_generator import load_price_performance_data
        from datetime import timedelta
        # Get price performance data for a range including report date
        start_date = (report_date - timedelta(days=30)).strftime('%Y-%m-%d')  # 30 days before report date
        end_date = report_date_str
        self.price_performance = load_price_performance_data(
            self.ticker, start_date, end_date, self.db_path
        )
        
        # If price_performance not in cache, try to pull from API
        if not self.price_performance:
            print(f"Price performance not in cache for {report_date_str}, attempting to pull from API...")
            from agentic.fmp_data_puller import pull_tesla_data
            try:
                result = pull_tesla_data(
                    ticker=self.ticker,
                    start_date=start_date,
                    end_date=end_date,
                    db_path=self.db_path
                )
                if result and result.get('price_performance'):
                    self.price_performance = result['price_performance']
                    print("Price performance pulled from API and cached")
            except Exception as e:
                print(f"Warning: Could not pull price performance from API: {e}")
        
        # Load key metrics
        self.key_metrics = load_key_metrics(self.ticker, self.db_path)
        
        # Generate analysis using analyst agent
        print(f"Generating analysis for {self.ticker}...")
        analyst = AnalystAgent(
            model_name=self.model_name,
            db_path=self.db_path,
            save_path=str(self.output_dir),
            config_path=str(self._config_path) if hasattr(self, '_config_path') else None
        )
        # Set save_dir attribute so analyst_agent saves to analysts folder
        if hasattr(self, '_current_analysts_dir'):
            analyst._save_dir = self._current_analysts_dir
        elif hasattr(self, '_current_base_dir'):
            # Fallback: use base_dir if analysts_dir not set yet
            analyst._save_dir = self._current_base_dir
        self.analysis_result = analyst.run(self.ticker, refine=True)
        
        print("Data loading complete.")
    
    def generate_key_changes_table(self) -> Table:
        """
        Generate Key Changes table showing Adj. EPS changes for forecast years.
        
        Returns:
            ReportLab Table object
        """
        if not self.key_metrics or not self.key_metrics.get('metrics'):
            return None
        
        metrics = self.key_metrics['metrics']
        
        # Get forecast years (next 2 years after latest actual)
        all_years = sorted(metrics.keys(), reverse=True, key=lambda x: int(x) if x.isdigit() else 0)
        current_year = int(datetime.now().strftime('%Y'))
        actual_years = [y for y in all_years if y.isdigit() and int(y) <= current_year]
        
        if not actual_years:
            return None
        
        latest_actual = max(actual_years, key=int)
        forecast_year_1 = str(int(latest_actual) + 1)
        forecast_year_2 = str(int(latest_actual) + 2)
        
        # For now, we'll use current values as both Prev and Cur
        # In a real system, you'd track previous forecasts
        data = [
            ['', 'Prev', 'Cur'],
            [f'Adj. EPS - {forecast_year_1[-2:]}E ($)', 
             f"{metrics.get(forecast_year_1, {}).get('adj_eps', 0):.2f}",
             f"{metrics.get(forecast_year_1, {}).get('adj_eps', 0):.2f}"],
            [f'Adj. EPS - {forecast_year_2[-2:]}E ($)',
             f"{metrics.get(forecast_year_2, {}).get('adj_eps', 0):.2f}",
             f"{metrics.get(forecast_year_2, {}).get('adj_eps', 0):.2f}"]
        ]
        
        table = Table(data, colWidths=[2.0*inch, 0.8*inch, 0.8*inch])
        
        # Use config colors for table styling
        table_font = self._get_font_name(
            self.config.get('components', {}).get('table_style', {}).get('header', {}).get('font_family', self.font_secondary),
            self.font_secondary_fallbacks
        )
        header_size = self.config.get('components', {}).get('table_style', {}).get('header', {}).get('font_size_pt', 9)
        body_size = self.config.get('components', {}).get('table_style', {}).get('body', {}).get('font_size_pt', 8)
        
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.table_header_fill),  # Use brand primary color
            ('TEXTCOLOR', (0, 0), (-1, 0), self.table_header_text_color),  # White text on header
            ('TEXTCOLOR', (0, 1), (-1, -1), self.table_body_text_color),  # Body text color from config
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), f'{table_font}-Bold' if table_font == 'Helvetica' else table_font),
            ('FONTSIZE', (0, 0), (-1, 0), header_size),
            ('FONTNAME', (0, 1), (-1, -1), table_font),
            ('FONTSIZE', (0, 1), (-1, -1), body_size),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), self.table_border_thickness, self.table_border_color),
        ])
        
        # Add zebra stripes if enabled
        if self.table_zebra_stripes and len(data) > 1:
            for i in range(1, len(data)):
                if i % 2 == 0:
                    style.add('BACKGROUND', (0, i), (-1, i), self.table_stripe_fill)
                else:
                    style.add('BACKGROUND', (0, i), (-1, i), self.color_white)
        
        table.setStyle(style)
        return table
    
    def generate_quarterly_forecasts_table(self) -> Table:
        """
        Generate Quarterly Forecasts table showing Adj. EPS by quarter.
        
        Returns:
            ReportLab Table object
        """
        if not self.key_metrics or not self.key_metrics.get('metrics'):
            return None
        
        metrics = self.key_metrics['metrics']
        
        # Get years
        all_years = sorted(metrics.keys(), reverse=True, key=lambda x: int(x) if x.isdigit() else 0)
        current_year = int(datetime.now().strftime('%Y'))
        actual_years = [y for y in all_years if y.isdigit() and int(y) <= current_year]
        
        if not actual_years:
            return None
        
        latest_actual = max(actual_years, key=int)
        forecast_year_1 = str(int(latest_actual) + 1)
        forecast_year_2 = str(int(latest_actual) + 2)
        
        # Get annual EPS and divide by 4 for quarterly (simplified)
        eps_2024 = metrics.get(latest_actual, {}).get('adj_eps', 0)
        eps_2025 = metrics.get(forecast_year_1, {}).get('adj_eps', 0)
        eps_2026 = metrics.get(forecast_year_2, {}).get('adj_eps', 0)
        
        data = [
            ['', '2024A', '2025E', '2026E'],
            ['Q1', f"{eps_2024/4:.2f}", f"{eps_2025/4:.2f}", f"{eps_2026/4:.2f}"],
            ['Q2', f"{eps_2024/4:.2f}", f"{eps_2025/4:.2f}", f"{eps_2026/4:.2f}"],
            ['Q3', f"{eps_2024/4:.2f}", f"{eps_2025/4:.2f}", f"{eps_2026/4:.2f}"],
            ['Q4', f"{eps_2024/4:.2f}", f"{eps_2025/4:.2f}", f"{eps_2026/4:.2f}"],
            ['FY', f"{eps_2024:.2f}", f"{eps_2025:.2f}", f"{eps_2026:.2f}"]
        ]
        
        table = Table(data, colWidths=[0.5*inch, 0.5*inch, 0.5*inch, 0.5*inch])
        
        # Use config colors for table styling
        table_font = self._get_font_name(
            self.config.get('components', {}).get('table_style', {}).get('header', {}).get('font_family', self.font_secondary),
            self.font_secondary_fallbacks
        )
        header_size = self.config.get('components', {}).get('table_style', {}).get('header', {}).get('font_size_pt', 9)
        body_size = self.config.get('components', {}).get('table_style', {}).get('body', {}).get('font_size_pt', 8)
        
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.table_header_fill),  # Use brand primary color
            ('TEXTCOLOR', (0, 0), (-1, 0), self.table_header_text_color),  # White text on header
            ('TEXTCOLOR', (0, 1), (-1, -1), self.table_body_text_color),  # Body text color from config
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), f'{table_font}-Bold' if table_font == 'Helvetica' else table_font),
            ('FONTSIZE', (0, 0), (-1, 0), header_size),
            ('FONTNAME', (0, 1), (-1, -1), table_font),
            ('FONTSIZE', (0, 1), (-1, -1), body_size),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), self.table_border_thickness, self.table_border_color),
            ('BACKGROUND', (0, 5), (-1, 5), self.table_stripe_fill),  # Highlight FY row with stripe color
        ])
        
        # Add zebra stripes if enabled
        if self.table_zebra_stripes and len(data) > 1:
            for i in range(1, len(data)):
                if i != 5 and i % 2 == 0:  # Skip FY row (already styled)
                    style.add('BACKGROUND', (0, i), (-1, i), self.table_stripe_fill)
                elif i != 5:
                    style.add('BACKGROUND', (0, i), (-1, i), self.color_white)
        
        table.setStyle(style)
        return table
    
    def generate_style_exposure_table(self) -> Table:
        """
        Generate Style Exposure table showing quant factor rankings.
        
        Returns:
            ReportLab Table object
        """
        # Placeholder data - in a real system, this would come from quant analysis
        data = [
            ['Quant Factors', 'Current', '1Y', '3Y', '5Y'],
            ['Value', '45', '52', '48', '55'],
            ['Growth', '78', '82', '75', '70'],
            ['Momentum', '62', '58', '65', '60'],
            ['Quality', '55', '60', '58', '62'],
            ['Low Vol', '35', '40', '38', '42'],
            ['EBQQ', '50', '48', '52', '50']
        ]
        
        table = Table(data, colWidths=[1.0*inch, 0.4*inch, 0.4*inch, 0.4*inch, 0.4*inch])
        
        # Use config colors for table styling
        table_font = self._get_font_name(
            self.config.get('components', {}).get('table_style', {}).get('header', {}).get('font_family', self.font_secondary),
            self.font_secondary_fallbacks
        )
        header_size = self.config.get('components', {}).get('table_style', {}).get('header', {}).get('font_size_pt', 8)
        body_size = self.config.get('components', {}).get('table_style', {}).get('body', {}).get('font_size_pt', 7)
        
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.table_header_fill),  # Use brand primary color
            ('TEXTCOLOR', (0, 0), (-1, 0), self.table_header_text_color),  # White text on header
            ('TEXTCOLOR', (0, 1), (-1, -1), self.table_body_text_color),  # Body text color from config
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), f'{table_font}-Bold' if table_font == 'Helvetica' else table_font),
            ('FONTSIZE', (0, 0), (-1, 0), header_size),
            ('FONTNAME', (0, 1), (-1, -1), table_font),
            ('FONTSIZE', (0, 1), (-1, -1), body_size),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), self.table_border_thickness, self.table_border_color),
        ])
        
        # Add zebra stripes if enabled
        if self.table_zebra_stripes and len(data) > 1:
            for i in range(1, len(data)):
                if i % 2 == 0:
                    style.add('BACKGROUND', (0, i), (-1, i), self.table_stripe_fill)
                else:
                    style.add('BACKGROUND', (0, i), (-1, i), self.color_white)
        
        table.setStyle(style)
        return table
    
    def regenerate_report_from_folder(self, base_dir_path: str, output_filename: str = None) -> str:
        """
        Regenerate report using existing files in a folder.
        
        Args:
            base_dir_path: Path to existing folder (e.g., 'reports/Tesla Inc_20260119_195917')
            output_filename: Output filename (default: auto-generated)
            
        Returns:
            Path to generated PDF file
        """
        base_dir = Path(base_dir_path)
        if not base_dir.exists():
            raise ValueError(f"Folder not found: {base_dir_path}")
        
        figs_dir = base_dir / "figs"
        report_dir = base_dir / "report"
        analysts_dir = base_dir / "analysts"
        
        # Load analysis result from analysts folder if exists
        analysis_json_path = analysts_dir / 'analysis_result.json'
        if analysis_json_path.exists():
            with open(analysis_json_path, 'r', encoding='utf-8') as f:
                self.analysis_result = json.load(f)
            print(f"Loaded analysis result from {analysis_json_path}")
        
        # Load existing images from figs folder
        self.fig_paths = {}
        if (figs_dir / 'graph_price_performance.png').exists():
            self.fig_paths['price_performance'] = str(figs_dir / 'graph_price_performance.png')
        if (figs_dir / 'table_company_data.png').exists():
            self.fig_paths['company_data_table'] = str(figs_dir / 'table_company_data.png')
        if (figs_dir / 'table_key_metrics.png').exists():
            self.fig_paths['key_metrics_table'] = str(figs_dir / 'table_key_metrics.png')
        
        # Set output filename - save PDF in report/ directory (overwrite existing)
        if not output_filename:
            output_filename = f"{self.ticker}_equity_report.pdf"
        
        output_path = report_dir / output_filename
        
        # Build and save PDF (reuse the rest of generate_report logic)
        return self._build_pdf(output_path, figs_dir)
    
    def generate_report(self, output_filename: str = None) -> str:
        """
        Generate the complete equity research report PDF.
        
        Args:
            output_filename: Output filename (default: auto-generated)
            
        Returns:
            Path to generated PDF file
        """
        # Create directory structure FIRST: reports/{company}_{timestamp}/
        #   - figs/ (for charts and tables)
        #   - report/ (for PDF report)
        #   - analysis_result files (from analyst_agent)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_dir = self.output_dir / f"{self.company_name}_{timestamp}"
        base_dir.mkdir(parents=True, exist_ok=True)
        
        figs_dir = base_dir / "figs"
        figs_dir.mkdir(parents=True, exist_ok=True)
        
        report_dir = base_dir / "report"
        report_dir.mkdir(parents=True, exist_ok=True)
        
        analysts_dir = base_dir / "analysts"
        analysts_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Creating output structure: {base_dir}")
        print(f"  - figs/: {figs_dir}")
        print(f"  - report/: {report_dir}")
        print(f"  - analysts/: {analysts_dir}")
        
        # Store base_dir and analysts_dir for use in load_data
        self._current_base_dir = base_dir
        self._current_analysts_dir = analysts_dir
        
        # Load data if not already loaded (this will use the base_dir for analyst_agent)
        if not self.analysis_result:
            self.load_data()
        
        # Generate graphs/tables in figs/ directory
        print("Generating graphs and tables...")
        from agentic.fmp_graph_generator import (
            plot_price_performance, generate_company_data_table, 
            generate_key_metrics_table
        )
        from datetime import timedelta
        
        as_of_date = datetime.now().strftime('%Y-%m-%d')
        end_date = as_of_date
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        
        graph_results = {}
        
        # Get config path for graph generation
        config_path = self._project_root / 'config.yaml' if hasattr(self, '_project_root') else None
        
        # Generate each graph/table in figs/ directory
        try:
            graph_results['price_performance'] = plot_price_performance(
                self.ticker, start_date, end_date, str(figs_dir), self.db_path, 
                config_path=str(config_path) if config_path else None
            )
        except Exception as e:
            print(f"Warning: Could not generate price performance graph: {e}")
        
        try:
            graph_results['company_data_table'] = generate_company_data_table(
                self.ticker, as_of_date, str(figs_dir), self.db_path
            )
        except Exception as e:
            print(f"Warning: Could not generate company data table: {e}")
        
        try:
            graph_results['key_metrics_table'] = generate_key_metrics_table(
                self.ticker, str(figs_dir), self.db_path
            )
        except Exception as e:
            print(f"Warning: Could not generate key metrics table: {e}")
        
        # Store paths to generated images
        self.fig_paths = {}
        for key in ['price_performance', 'company_data_table', 'key_metrics_table']:
            if graph_results.get(key):
                fig_path = Path(graph_results[key])
                if fig_path.exists():
                    self.fig_paths[key] = str(fig_path)
                else:
                    # Fallback: search in figs_dir
                    pattern_map = {
                        'price_performance': 'graph_price_performance.png',
                        'company_data_table': 'table_company_data.png',
                        'key_metrics_table': 'table_key_metrics.png'
                    }
                    if key in pattern_map:
                        found_files = list(figs_dir.glob(pattern_map[key]))
                        if found_files:
                            self.fig_paths[key] = str(found_files[0])
        
        # Set output filename - save PDF in report/ directory
        if not output_filename:
            output_filename = f"{self.ticker}_equity_report.pdf"
        
        output_path = report_dir / output_filename
        
        # Build PDF using Canvas and Frames (similar to ReportBuild.py format)
        return self._build_pdf(output_path, figs_dir)
    
    def _draw_frame_title(self, text: str, bg_color, col_width: float, font_name: str) -> Table:
        """
        Draw a frame title with background color (like ReportBuild.py draw_frame_title).
        Made very compact with minimal padding (almost same height as text) and bold font.
        
        Args:
            text: Title text
            bg_color: Background color (Color object)
            col_width: Column width
            font_name: Font name
            
        Returns:
            Table object for the title
        """
        data = [[text]]
        table = Table(data, colWidths=[col_width])
        
        # Get table header style from config
        table_style_config = self.config.get('components', {}).get('table_style', {})
        if table_style_config:
            header_style = table_style_config.get('header', {})
            header_font_raw = header_style.get('font_family', font_name)
            header_font = self._get_font_name(header_font_raw, self.font_secondary_fallbacks)
            header_size = header_style.get('font_size_pt', 9)
            # For light grey background, use dark text; for dark background, use white text
            # Check if bg_color is light (we'll use dark text for light grey)
            if bg_color == self.color_light_grey:
                text_color = self.color_text  # Dark text on light background
            else:
                text_color = HexColor(header_style.get('text_color', '#FFFFFF'))  # White text on dark background
        else:
            header_font = self._get_font_name(font_name, self.font_secondary_fallbacks)
            header_size = 9
            # For light grey background, use dark text
            if bg_color == self.color_light_grey:
                text_color = self.color_text
            else:
                text_color = self.color_white
        
        # Make font bold - use Bold variant if available
        if header_font == 'Helvetica':
            bold_font = 'Helvetica-Bold'
        elif header_font == 'Times-Roman':
            bold_font = 'Times-Bold'
        elif header_font == 'Courier':
            bold_font = 'Courier-Bold'
        else:
            bold_font = header_font  # Fallback
        
        # Minimal padding - almost same height as text
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), bg_color),
            ('TEXTCOLOR', (0, 0), (-1, -1), text_color),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Vertical center
            ('FONTSIZE', (0, 0), (-1, -1), header_size),
            ('FONTNAME', (0, 0), (-1, -1), bold_font),  # Bold font
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),  # Minimal padding - almost same as text height
            ('TOPPADDING', (0, 0), (-1, -1), 1),  # Minimal padding
            ('LEFTPADDING', (0, 0), (-1, -1), 4),  # Left padding for text
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),  # Right padding for text
        ]))
        return table
    
    def _prepare_left_story(self, styles) -> List:
        """
        Prepare left column content (story).
        
        Args:
            styles: ReportLab styles object
            
        Returns:
            List of flowables for left column
        """
        # Custom styles from config
        typo_scale = self.typography.get('scale', {})
        
        # Title style (H1 from config) - keep original spaceAfter for company name
        h1_config = typo_scale.get('h1', {})
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=h1_config.get('font_size_pt', 24),
            textColor=HexColor(h1_config.get('color', '#111111')),
            fontName=self._get_font_name(h1_config.get('font_family', self.font_primary), self.font_primary_fallbacks),
            spaceAfter=12,  # Keep original spacing after company name
            alignment=TA_LEFT,
            leading=h1_config.get('font_size_pt', 24) * h1_config.get('line_height', 1.15)
        )
        
        # Headline style (H2 from config) - keep original spaceAfter
        h2_config = typo_scale.get('h2', {})
        headline_style = ParagraphStyle(
            'CustomHeadline',
            parent=styles['Normal'],
            fontSize=h2_config.get('font_size_pt', 14),
            textColor=HexColor(h2_config.get('color', '#111111')),
            fontName=self._get_font_name(h2_config.get('font_family', self.font_primary), self.font_primary_fallbacks),
            spaceAfter=12,  # Keep original spacing
            alignment=TA_LEFT,
            leading=h2_config.get('font_size_pt', 14) * h2_config.get('line_height', 1.2)
        )
        
        # Body style (body from config)
        body_config = typo_scale.get('body', {})
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=body_config.get('font_size_pt', 9),
            textColor=HexColor(body_config.get('color', '#111111')),
            fontName=self._get_font_name(body_config.get('font_family', self.font_primary), self.font_primary_fallbacks),
            spaceAfter=10,
            alignment=TA_JUSTIFY,
            leading=body_config.get('font_size_pt', 9) * body_config.get('line_height', 1.35)
        )
        
        # Prepare left column content (right column will be drawn directly on canvas)
        left_story = []
        
        # Left column: Company name (use primary color like neutral blue, bold)
        company_name_para = Paragraph(
            f'<b><font color="{self.brand_colors.get("primary", {}).get("hex", "#0060A0")}">{self.company_name}</font></b>',
            title_style
        )
        left_story.append(company_name_para)
        
        # Headline (from analysis or generate one)
        if self.analysis_result and 'key_points' in self.analysis_result:
            headline = " ".join(self.analysis_result['key_points'][:2]) if self.analysis_result['key_points'] else ""
        else:
            headline = f"{self.company_name} Analysis"
        left_story.append(Paragraph(headline, headline_style))
        # Keep original spacing after headline (before paragraphs)
        left_story.append(Spacer(1, 0.15*inch))
        
        # Analysis paragraphs - bold first line and highlight financial keywords
        if self.analysis_result and 'analysis' in self.analysis_result:
            analysis = self.analysis_result['analysis']
            # Get number of paragraphs from config or default to 4
            num_paragraphs = self.config.get('inputs', {}).get('analyst_analysis', {}).get('num_paragraphs', 4)
            for i in range(1, num_paragraphs + 1):
                para_key = f'paragraph_{i}'
                if para_key in analysis:
                    para_text = analysis[para_key]
                    
                    # Highlight financial keywords (before bold formatting)
                    para_text = self._highlight_financial_keywords(para_text)
                    
                    # Bold the first line (first sentence ending with period)
                    sentences = para_text.split('. ', 1)
                    if len(sentences) > 1:
                        first_line = sentences[0] + '. '
                        rest_text = sentences[1]
                        # Format first line as bold
                        formatted_text = f'<b>{first_line}</b>{rest_text}'
                    else:
                        # If no period, try to find first sentence end
                        period_idx = para_text.find('.')
                        if period_idx > 0:
                            first_line = para_text[:period_idx+1] + ' '
                            rest_text = para_text[period_idx+1:]
                            formatted_text = f'<b>{first_line}</b>{rest_text}'
                        else:
                            # Fallback: bold first ~80 characters
                            if len(para_text) > 80:
                                first_line = para_text[:80]
                                rest_text = para_text[80:]
                                formatted_text = f'<b>{first_line}</b>{rest_text}'
                            else:
                                formatted_text = f'<b>{para_text}</b>'
                    
                    left_story.append(Paragraph(formatted_text, body_style))
                    left_story.append(Spacer(1, 0.1*inch))
        
        # Key metrics removed per user request
        
        # Source note (caption style from config)
        caption_config = typo_scale.get('caption', {})
        source_style = ParagraphStyle(
            'Source',
            parent=styles['Normal'],
            fontSize=caption_config.get('font_size_pt', 8),
            textColor=HexColor(caption_config.get('color', '#4A4A4A')),
            fontName=self._get_font_name(caption_config.get('font_family', self.font_secondary), self.font_secondary_fallbacks),
            spaceAfter=6,
            alignment=TA_LEFT,
            leading=caption_config.get('font_size_pt', 8) * caption_config.get('line_height', 1.25)
        )
        # Removed source and disclosure text from left column - now in footer
        
        return left_story
    
    def _highlight_financial_keywords(self, text: str) -> str:
        """
        Convert LLM-generated <highlight> tags to blue font tags.
        
        The LLM should mark important financial metrics and insights using <highlight> tags
        in the generated text. This method converts those tags to blue HTML font tags.
        No regex pattern matching is used - all highlighting is done by the LLM during generation.
        
        Args:
            text: Input text with <highlight> tags from LLM
            
        Returns:
            Text with <highlight> tags converted to blue HTML font tags
        """
        import re
        
        # Primary color for highlighting
        highlight_color = self.brand_colors.get("primary", {}).get("hex", "#0060A0")
        
        # Replace LLM highlight tags with blue font tags
        # LLM should use <highlight>text to highlight</highlight> format
        # No regex pattern matching - all highlighting is done by the LLM during generation
        if '<highlight>' in text and '</highlight>' in text:
            text = re.sub(
                r'<highlight>(.*?)</highlight>',
                f'<font color="{highlight_color}">\\1</font>',
                text,
                flags=re.IGNORECASE | re.DOTALL
            )
        
        return text
    
    def _build_pdf(self, output_path: Path, figs_dir: Path) -> str:
        """
        Build the PDF report (internal method).
        
        Args:
            output_path: Path to output PDF file
            figs_dir: Directory containing figure files
            
        Returns:
            Path to generated PDF file
        """
        print(f"Building PDF: {output_path}")
        
        # Build story (content)
        styles = getSampleStyleSheet()
        
        # Prepare left column content
        left_story = self._prepare_left_story(styles)
        
        # Create canvas directly (like ReportBuild.py)
        c = canvas.Canvas(str(output_path), pagesize=LETTER)
        
        # Draw header from config
        header_font_family = self.header_config.get('font_family', 'Roboto')
        header_font_size = self.header_config.get('font_size_pt', 8)
        header_color_hex = self.header_config.get('color', '#4A4A4A')
        header_color = HexColor(header_color_hex)
        
        # Use fallback font if primary not available
        header_font = self._get_font_name(header_font_family, self.font_secondary_fallbacks)
        
        # Draw logo in top-left corner with vertical line and "Research" text
        logo_path = self.header_config.get('logo_path', 'front/figs/logo.png')
        logo_path_obj = Path(logo_path)
        if not logo_path_obj.is_absolute():
            # Relative to project root - use stored project_root from __init__
            if hasattr(self, '_project_root'):
                project_root = self._project_root
            else:
                # Fallback: try to get from current file location
                try:
                    current_file = Path(__file__)
                    if current_file.exists():
                        project_root = current_file.parent.parent
                    else:
                        project_root = Path.cwd()
                except:
                    project_root = Path.cwd()
            logo_path_obj = project_root / logo_path
        
        # Initialize variables for right side alignment
        logo_center_y = None
        right_text_y = None
        
        if logo_path_obj.exists():
            try:
                logo_img = Image(str(logo_path_obj))
                # Get original image dimensions
                original_width = logo_img.imageWidth
                original_height = logo_img.imageHeight
                
                # Scale logo to 2x the original size (was 35, now 70 points height - half of 4x)
                logo_height = 35 * 2  # 70 points (half of previous 140)
                # Calculate width maintaining aspect ratio
                logo_width = logo_height * (original_width / original_height)
                
                # Set both dimensions explicitly
                logo_img.drawWidth = logo_width
                logo_img.drawHeight = logo_height
                
                # Draw logo at top-left corner (moved to page top)
                logo_y = self.page_height - logo_height - 5  # Move to very top, just 5 points from edge
                logo_img.drawOn(c, self.margin_left, logo_y)
                
                # Calculate "Research" text position - center it vertically with logo
                c.setFont(header_font, header_font_size)
                c.setFillColor(header_color)
                research_text = "Research"
                logo_center_y = self.page_height - logo_height / 2 - 5
                
                # Calculate vertical line - make it longer and center "Research" with it
                line_x = self.margin_left + logo_img.drawWidth + 8
                # Make line longer (about 1.5x the text height)
                line_height = header_font_size * 1.5  # Longer line
                line_center_y = logo_center_y  # Center line with logo center
                line_y_top = line_center_y + line_height / 2
                line_y_bottom = line_center_y - line_height / 2
                
                # Draw vertical line first
                c.setStrokeColor(header_color)
                c.setLineWidth(0.5)
                c.line(line_x, line_y_bottom, line_x, line_y_top)
                
                # Draw "Research" text - center it vertically with the line
                research_x = line_x + 8
                # Center text vertically with the line (text baseline is at y, so adjust)
                research_y = line_center_y - header_font_size / 2 + 2  # Adjust for text baseline
                c.drawString(research_x, research_y, research_text)
                
                # Store logo_center_y for right side alignment
                logo_center_y = logo_center_y
            except Exception as e:
                print(f"Warning: Could not load logo: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"Warning: Logo not found at {logo_path_obj.absolute()}")
        
        # Right side: "North America Equity Research" in blue, with report date below in black
        # Align with left side logo and "Research" text
        right_text = self.header_config.get('right_text', 'North America Equity Research')
        right_text_color_hex = self.header_config.get('right_text_color', self.brand_colors.get('primary', {}).get('hex', '#0060A0'))
        right_text_color = HexColor(right_text_color_hex)
        
        # Get logo center Y position if logo was drawn, otherwise use default
        if logo_center_y is not None:
            # Align right text with logo center (where "Research" is)
            right_text_y = logo_center_y + header_font_size / 2 - 2
        else:
            # Fallback: use position near page top
            right_text_y = self.page_height - header_font_size - 5
        
        c.setFont(header_font, header_font_size)
        c.setFillColor(right_text_color)
        # Draw right text (blue) - aligned with "Research" text on left
        c.drawRightString(self.page_width - self.margin_right, right_text_y, right_text)
        
        # Report date below right text (black, smaller) - aligned lower
        report_date_format = self.config.get('inputs', {}).get('source_report', {}).get('report_date')
        if report_date_format:
            # Parse date from config if provided
            try:
                report_date = datetime.strptime(report_date_format, '%Y-%m-%d')
                report_date_str = report_date.strftime('%d %B %Y')
            except:
                report_date_str = datetime.now().strftime('%d %B %Y')
        else:
            report_date_str = datetime.now().strftime('%d %B %Y')
        
        report_date_font_size = self.header_config.get('report_date_font_size_pt', 7)
        report_date_color_hex = self.header_config.get('report_date_color', '#111111')
        report_date_color = HexColor(report_date_color_hex)
        
        # Position date below the right text, with spacing
        if logo_center_y is not None:
            # Align date lower, below the right text
            date_y = right_text_y - header_font_size - 3
        else:
            # Fallback: use default position
            date_y = self.page_height - self.margin_top - 5
        
        c.setFont(header_font, report_date_font_size)
        c.setFillColor(report_date_color)
        c.drawRightString(self.page_width - self.margin_right, date_y, report_date_str)
        
        # Remove divider line below header (user requested to delete the grey line)
        
        # Define frame dimensions (similar to ReportBuild.py)
        # Get gutter width from config, default to 0.35 inches, reduce to 2/3 of current
        gutter_in = self.layout.get('page', {}).get('grid', {}).get('gutter_in', 0.35)
        gutter_pts = gutter_in * 72 * (2/3)  # Convert to points and reduce to 2/3 of original
        
        right_frame_width = 185  # Fixed width for right column (in points)
        # Add gutter space between columns (reduced to 2/3)
        left_frame_width = self.page_width - self.margin_right - right_frame_width - self.margin_left - gutter_pts
        right_frame_x = self.page_width - self.margin_right - right_frame_width
        
        # Reduce header reserve space from 95 to 1/3 (about 32 points) to bring content closer to top
        header_reserve = 95 / 3  # Reduce to 1/3 of original
        frame_height = self.page_height - self.margin_top - self.margin_bottom - header_reserve  # Reduced header space
        
        # Remove vertical divider line - just leave white space (gutter reduced to 2/3)
        
        # Create left frame for text content (like ReportBuild.py)
        # Start frame higher up (reduce top margin by reducing header_reserve)
        frame_top_y = self.page_height - self.margin_top - header_reserve
        frame_left = Frame(
            x1=self.margin_left,
            y1=self.margin_bottom,
            width=left_frame_width,
            height=frame_height,
            showBoundary=0,
            topPadding=0,
            leftPadding=4,
            rightPadding=4
        )
        
        # Adjust image widths in left_story now that we know left_frame_width
        for item in left_story:
            if isinstance(item, Image):
                item.drawWidth = left_frame_width - 8
                if hasattr(item, 'imageHeight') and hasattr(item, 'imageWidth'):
                    item.drawHeight = item.drawWidth * (item.imageHeight / item.imageWidth)
        
        # Draw right column content on first page (like ReportBuild.py)
        # This needs to be done BEFORE frame_left.addFromList to ensure it's on the first page
        # Calculate headline Y position to align NEUTRAL with headline
        # Frame starts at: frame_top_y = self.page_height - self.margin_top - header_reserve
        frame_top_y = self.page_height - self.margin_top - header_reserve
        
        # Calculate left column content positions:
        # 1. Company name: title_style (font_size: 24, line_height: 1.15, spaceAfter: 12)
        h1_config = self.typography.get('scale', {}).get('h1', {})
        company_name_font_size = h1_config.get('font_size_pt', 24)
        company_name_line_height = h1_config.get('line_height', 1.15)
        company_name_height = company_name_font_size * company_name_line_height
        company_name_space_after = 12  # From title_style spaceAfter
        
        # 2. Headline: headline_style (font_size: 14, line_height: 1.2)
        h2_config = self.typography.get('scale', {}).get('h2', {})
        headline_font_size = h2_config.get('font_size_pt', 14)
        headline_line_height = h2_config.get('line_height', 1.2)
        headline_height = headline_font_size * headline_line_height
        
        # Headline baseline Y position (from top of frame, going down)
        # Company name takes: company_name_height (leading) + company_name_space_after
        # Headline baseline is at: company_name_height + company_name_space_after + (headline_font_size * 0.75)
        # 0.75 accounts for baseline position within the font (baseline is typically ~75% down from top of font)
        headline_baseline_offset = company_name_height + company_name_space_after + (headline_font_size * 0.75)
        headline_y = frame_top_y - headline_baseline_offset
        
        # Align NEUTRAL with headline baseline
        right_y = headline_y
        
        # Rating and price info - use brand colors
        rating_font = self._get_font_name(self.font_primary, self.font_primary_fallbacks)
        c.setFont(f'{rating_font}-Bold' if rating_font == 'Helvetica' else rating_font, 12)
        c.setFillColor(self.color_primary)  # Use brand primary color for rating
        recommendation = self.analysis_result.get('recommendation', 'NEUTRAL') if self.analysis_result else 'NEUTRAL'
        c.drawString(right_frame_x + 4, right_y, recommendation)
        right_y -= 15
        
        body_font = self._get_font_name(self.font_secondary, self.font_secondary_fallbacks)
        c.setFont(body_font, 9)
        c.setFillColor(self.color_text)
        c.drawString(right_frame_x + 4, right_y, f"{self.ticker}, {self.ticker} US")
        right_y -= 12
        
        # Get report date from config
        report_date_format = self.config.get('inputs', {}).get('source_report', {}).get('report_date')
        if report_date_format:
            try:
                report_date = datetime.strptime(report_date_format, '%Y-%m-%d')
                report_date_str = report_date.strftime('%d %b %y')
            except:
                report_date = datetime.now()
                report_date_str = datetime.now().strftime('%d %b %y')
        else:
            report_date = datetime.now()
            report_date_str = datetime.now().strftime('%d %b %y')
        
        # Get current price from price_performance data (for report date) or company_data
        current_price = None
        
        # Try to get price from price_performance data (most accurate for specific date)
        if hasattr(self, 'price_performance') and self.price_performance:
            stock_data = self.price_performance.get('stock_data', [])
            if stock_data:
                # Find price closest to report date
                report_date_str_for_match = report_date.strftime('%Y-%m-%d')
                # Try exact match first
                for data_point in stock_data:
                    if data_point.get('date') == report_date_str_for_match:
                        current_price = data_point.get('close')
                        break
                # If exact match not found, use the latest price before or on report date
                if current_price is None:
                    sorted_data = sorted(
                        [d for d in stock_data if d.get('date', '') <= report_date_str_for_match],
                        key=lambda x: x.get('date', ''),
                        reverse=True
                    )
                    if sorted_data:
                        current_price = sorted_data[0].get('close')
        
        # Fallback: try to get from company_data (market_cap / shares_outstanding)
        if current_price is None and self.company_data:
            market_cap = self.company_data.get('market_cap')
            shares_outstanding = self.company_data.get('shares_outstanding')
            if market_cap and shares_outstanding and shares_outstanding > 0:
                current_price = market_cap / shares_outstanding
        
        # Final fallback: use 52w_high * 0.8 as estimate
        if current_price is None:
            if self.company_data and self.company_data.get('52w_high'):
                current_price = self.company_data.get('52w_high', 0) * 0.8
            else:
                current_price = 100
        
        # Price target (can be improved later with actual analyst target)
        price_target = current_price * 0.7
        
        c.drawString(right_frame_x + 4, right_y, f"Price ({report_date_str}) ${current_price:.2f}")
        right_y -= 12
        c.drawString(right_frame_x + 4, right_y, f"Price Target (Dec-25) ${price_target:.2f}")
        right_y -= 20
        
        # Sector/Industry - get from config, use same format as Price Performance (with light grey background)
        industry = self.config.get('inputs', {}).get('source_report', {}).get('industry', 'N/A')
        sector_title = self._draw_frame_title(
            industry,
            self.color_light_grey,  # Light grey background from config (same as Price Performance)
            right_frame_width - 4,
            body_font
        )
        title_width, title_height = sector_title.wrap(0, 0)
        right_y -= title_height + 3  # Reduced spacing (same as Price Performance)
        sector_title.drawOn(c, right_frame_x + 2, right_y)
        right_y -= 15  # Increased spacing after industry title to avoid overlap with analyst names
        author_section = self.config.get('inputs', {}).get('author_section', {})
        analysts = author_section.get('analysts', [])
        
        if analysts:
            analyst_font = self._get_font_name(
                author_section.get('typography', {}).get('name_font', {}).get('family', self.font_primary),
                self.font_primary_fallbacks
            )
            analyst_font_size = author_section.get('typography', {}).get('name_font', {}).get('size_pt', 9)
            role_font_size = author_section.get('typography', {}).get('role_font', {}).get('size_pt', 8.5)
            contact_font_size = author_section.get('typography', {}).get('contact_font', {}).get('size_pt', 8)
            
            # Display all analysts - name only (bold), no role/title
            for analyst in analysts:
                # Name only (bold) - no role/title
                c.setFont(f'{analyst_font}-Bold' if analyst_font == 'Helvetica' else analyst_font, analyst_font_size)
                c.setFillColor(self.color_text)
                analyst_name = analyst.get('name', 'Analyst')
                c.drawString(right_frame_x + 4, right_y, analyst_name)
                right_y -= 12
                
                # Phone
                c.setFont(header_font, contact_font_size)
                c.setFillColor(HexColor(author_section.get('typography', {}).get('contact_font', {}).get('color', '#7A7A7A')))
                c.drawString(right_frame_x + 4, right_y, analyst.get('phone', '+1-212-555-1234'))
                right_y -= 10
                
                # Email
                c.drawString(right_frame_x + 4, right_y, analyst.get('email', f'analyst@{self.brand_name.lower().replace(" ", "")}.com'))
                right_y -= 12
            
            # Add legal entity if configured
            if author_section.get('show_legal_entity', False):
                legal_entity = author_section.get('legal_entity', {})
                if legal_entity.get('name'):
                    c.setFont(header_font, contact_font_size)
                    c.setFillColor(HexColor(author_section.get('typography', {}).get('contact_font', {}).get('color', '#7A7A7A')))
                    c.drawString(right_frame_x + 4, right_y, legal_entity['name'])
                    right_y -= 10
            
            right_y -= 5
        else:
            # Fallback if no analysts in config
            c.setFont(self._get_font_name(self.font_secondary, self.font_secondary_fallbacks), 8)
            c.setFillColor(self.color_text)
            analyst_info = [
                "Analyst Contact",
                "+1-212-555-1234",
                f"analyst@{self.brand_name.lower().replace(' ', '')}.com"
            ]
            for info in analyst_info:
                c.drawString(right_frame_x + 4, right_y, info)
                right_y -= 10
            right_y -= 10
        
        # Define consistent width for all right column images/tables
        right_col_content_width = right_frame_width - 8  # Consistent width for all right column content
        
        # Add images to right column - only graph_price_performance.png and table_company_data.png
        if hasattr(self, 'fig_paths'):
            # Price performance graph (first, at the top)
            price_perf_path = self.fig_paths.get('price_performance')
            if price_perf_path:
                price_perf_path_obj = Path(price_perf_path)
                if not price_perf_path_obj.exists():
                    # Try to find it in figs_dir
                    price_perf_path_obj = figs_dir / 'graph_price_performance.png'
                
                if price_perf_path_obj.exists():
                    try:
                        # Draw title with light grey background (like ReportBuild.py)
                        price_perf_title = self._draw_frame_title(
                            "Price Performance",
                            self.color_light_grey,  # Light grey background from config
                            right_frame_width - 4,
                            body_font
                        )
                        title_width, title_height = price_perf_title.wrap(0, 0)
                        right_y -= title_height + 3  # Reduced spacing
                        price_perf_title.drawOn(c, right_frame_x + 2, right_y)
                        right_y -= 3  # Reduced spacing
                        
                        # Load image and get raw dimensions (like ReportBuild.py)
                        img = Image(str(price_perf_path_obj))
                        raw_width = img.imageWidth
                        raw_height = img.imageHeight
                        
                        # Set width to fit right column, maintain aspect ratio
                        img.drawWidth = right_col_content_width
                        img.drawHeight = img.drawWidth * (raw_height / raw_width)
                        
                        # Only add if there's space
                        if right_y - img.drawHeight > self.margin_bottom + 20:
                            # Draw image at calculated position (like ReportBuild.py)
                            img.drawOn(c, right_frame_x + 4, right_y - img.drawHeight)
                            right_y -= img.drawHeight + 10
                        else:
                            print(f"Warning: Not enough space for price performance graph (need {img.drawHeight:.1f}, have {right_y - self.margin_bottom:.1f})")
                    except Exception as e:
                        print(f"Warning: Could not add price performance graph: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"Warning: Price performance graph not found at {price_perf_path_obj}")
            
            # Company data table (second, below price performance)
            company_data_path = self.fig_paths.get('company_data_table')
            if company_data_path:
                company_data_path_obj = Path(company_data_path)
                if not company_data_path_obj.exists():
                    # Try to find it in figs_dir
                    company_data_path_obj = figs_dir / 'table_company_data.png'
                
                if company_data_path_obj.exists():
                    try:
                        # Draw title with light grey background (like ReportBuild.py)
                        company_data_title = self._draw_frame_title(
                            "Company Data",
                            self.color_light_grey,  # Light grey background from config
                            right_frame_width - 4,
                            body_font
                        )
                        title_width, title_height = company_data_title.wrap(0, 0)
                        right_y -= title_height + 3  # Reduced spacing
                        company_data_title.drawOn(c, right_frame_x + 2, right_y)
                        right_y -= 3  # Reduced spacing
                        
                        # Load image and get raw dimensions (like ReportBuild.py)
                        img = Image(str(company_data_path_obj))
                        raw_width = img.imageWidth
                        raw_height = img.imageHeight
                        
                        # Set width to fit right column (same as price performance), maintain aspect ratio
                        img.drawWidth = right_col_content_width
                        img.drawHeight = img.drawWidth * (raw_height / raw_width)
                        
                        # Only add if there's space
                        if right_y - img.drawHeight > self.margin_bottom + 20:
                            # Draw image at calculated position (like ReportBuild.py)
                            img.drawOn(c, right_frame_x + 4, right_y - img.drawHeight)
                        else:
                            print(f"Warning: Not enough space for company data table (need {img.drawHeight:.1f}, have {right_y - self.margin_bottom:.1f})")
                    except Exception as e:
                        print(f"Warning: Could not add company data table: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"Warning: Company data table not found at {company_data_path_obj}")
        
        # Now add left column content to frame (this handles automatic page breaks and creates new pages as needed)
        frame_left.addFromList(left_story, c)
        
        # Draw footer from config - full width footnote at bottom of page
        if self.footer_config.get('show', True):
            footer_font_family = self.footer_config.get('font_family', 'Roboto')
            footer_font_size = self.footer_config.get('font_size_pt', 7)
            footer_color_hex = self.footer_config.get('color', '#7A7A7A')
            footer_color = HexColor(footer_color_hex)
            footer_font = self._get_font_name(footer_font_family, self.font_secondary_fallbacks)
            
            # New footer text - full width footnote spanning both columns (BLACK text)
            footer_text = (
                "See following pages for analyst certification and important disclosures. "
                f"{self.brand_name} and its affiliates may seek to conduct business with the companies discussed in this research report. "
                "As a result, investors should be aware that potential conflicts of interest may exist that could influence the objectivity of the analysis. "
                "This report is intended for informational purposes only and should be considered as one input among many when making investment decisions, rather than as a sole basis for action."
            )
            
            # Calculate footer position - at the very bottom of the page
            footer_y = self.margin_bottom - 5  # 5 points from bottom edge
            
            # Split footer text into multiple lines to fit page width
            # Available width spans from left column left edge to right column right edge
            # Use full page width minus margins (full width)
            footer_width = self.page_width - self.margin_left - self.margin_right
            
            # Use ReportLab's stringWidth for accurate text width calculation
            from reportlab.pdfbase.pdfmetrics import stringWidth
            footer_lines = []
            
            # Word wrapping with accurate width calculation
            words = footer_text.split()
            current_line = ""
            for word in words:
                test_line = current_line + (" " if current_line else "") + word
                # Use ReportLab's stringWidth for accurate measurement
                text_width = stringWidth(test_line, footer_font, footer_font_size)
                if text_width > footer_width and current_line:
                    footer_lines.append(current_line)
                    current_line = word
                else:
                    current_line = test_line
            if current_line:
                footer_lines.append(current_line)
            
            # Draw disclosure text (BLACK) - positioned above brand/website
            # Use full width from left margin to right margin (spanning both columns)
            line_height = footer_font_size * 1.2
            disclosure_height = len(footer_lines) * line_height
            disclosure_start_y = footer_y + line_height + 5  # Start above brand/website (5 points spacing)
            
            c.setFont(footer_font, footer_font_size)
            c.setFillColor(HexColor('#111111'))  # Black color for disclosure text
            for i, line in enumerate(reversed(footer_lines)):
                y_pos = disclosure_start_y + (i * line_height)
                # Draw from left margin to right margin (full width)
                c.drawString(self.margin_left, y_pos, line)
            
            # Add brand name and website at the very bottom (GRAY, like original)
            # Position: at the bottom of the page
            brand_y = footer_y  # At the very bottom
            
            c.setFont(footer_font, footer_font_size)
            c.setFillColor(footer_color)  # Gray color for brand/website (original color)
            
            # Left text from config template
            left_text_template = self.footer_config.get('left_text_template', '{provider} Research')
            left_text = left_text_template.format(provider=self.brand_name)
            c.drawString(self.margin_left, brand_y, left_text[:80])
            
            # Right text from config template (website)
            right_text = f'www.{self.brand_name.lower().replace(" ", "")}markets.com'
            c.drawRightString(self.page_width - self.margin_right, brand_y, right_text)
        
        c.save()
        
        print(f"Report generated successfully: {output_path}")
        return str(output_path)
    
    def regenerate_report_from_folder(self, base_dir_path: str, output_filename: str = None) -> str:
        """
        Regenerate report using existing files in a folder.
        
        Args:
            base_dir_path: Path to existing folder (e.g., 'reports/Tesla Inc_20260119_195917')
            output_filename: Output filename (default: auto-generated)
            
        Returns:
            Path to generated PDF file
        """
        base_dir = Path(base_dir_path)
        if not base_dir.exists():
            raise ValueError(f"Folder not found: {base_dir_path}")
        
        figs_dir = base_dir / "figs"
        report_dir = base_dir / "report"
        analysts_dir = base_dir / "analysts"
        
        # Load analysis result from analysts folder if exists
        analysis_json_path = analysts_dir / 'analysis_result.json'
        if analysis_json_path.exists():
            with open(analysis_json_path, 'r', encoding='utf-8') as f:
                self.analysis_result = json.load(f)
            print(f"Loaded analysis result from {analysis_json_path}")
        
        # Load existing images from figs folder
        self.fig_paths = {}
        if (figs_dir / 'graph_price_performance.png').exists():
            self.fig_paths['price_performance'] = str(figs_dir / 'graph_price_performance.png')
        if (figs_dir / 'table_company_data.png').exists():
            self.fig_paths['company_data_table'] = str(figs_dir / 'table_company_data.png')
        if (figs_dir / 'table_key_metrics.png').exists():
            self.fig_paths['key_metrics_table'] = str(figs_dir / 'table_key_metrics.png')
        
        # Set output filename - save PDF in report/ directory (overwrite existing)
        if not output_filename:
            output_filename = f"{self.ticker}_equity_report.pdf"
        
        output_path = report_dir / output_filename
        
        # Build and save PDF (reuse the _build_pdf method)
        return self._build_pdf(output_path, figs_dir)


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate Equity Research Report')
    parser.add_argument('ticker', type=str, help='Stock ticker symbol (e.g., TSLA)')
    parser.add_argument('--company-name', type=str, help='Company name (default: uses ticker)')
    parser.add_argument('--db-path', type=str, help='Path to database file')
    parser.add_argument('--output-dir', type=str, help='Output directory (default: ./reports)')
    parser.add_argument('--model', type=str, help='OpenAI model name')
    parser.add_argument('--output', type=str, help='Output filename')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Equity Research Report Generator")
    print("=" * 60)
    
    generator = EquityReportGenerator(
        ticker=args.ticker,
        company_name=args.company_name,
        db_path=args.db_path,
        output_dir=args.output_dir,
        model_name=args.model
    )
    
    output_path = generator.generate_report(output_filename=args.output)
    
    print("\n" + "=" * 60)
    print("Report Generation Complete")
    print("=" * 60)
    print(f"Output: {output_path}")


if __name__ == '__main__':
    main()
