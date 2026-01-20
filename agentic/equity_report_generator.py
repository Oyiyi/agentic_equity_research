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
        
        # Load configuration from config.yaml
        if config_path is None:
            config_path = project_root / 'config.yaml'
        else:
            config_path = Path(config_path)
        
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
        
        # Load financial data
        self.financial_data = load_all_data_from_cache(self.ticker, self.db_path)
        
        # Load company data
        as_of_date = datetime.now().strftime('%Y-%m-%d')
        self.company_data = load_company_data(self.ticker, as_of_date, self.db_path)
        
        # Load key metrics
        self.key_metrics = load_key_metrics(self.ticker, self.db_path)
        
        # Generate analysis using analyst agent
        print(f"Generating analysis for {self.ticker}...")
        analyst = AnalystAgent(
            model_name=self.model_name,
            db_path=self.db_path,
            save_path=str(self.output_dir)
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
        
        # Generate each graph/table in figs/ directory
        try:
            graph_results['price_performance'] = plot_price_performance(
                self.ticker, start_date, end_date, str(figs_dir), self.db_path
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
        
        # Build story (content)
        styles = getSampleStyleSheet()
        
        # Custom styles from config
        typo_scale = self.typography.get('scale', {})
        
        # Title style (H1 from config)
        h1_config = typo_scale.get('h1', {})
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=h1_config.get('font_size_pt', 24),
            textColor=HexColor(h1_config.get('color', '#111111')),
            fontName=self._get_font_name(h1_config.get('font_family', self.font_primary), self.font_primary_fallbacks),
            spaceAfter=12,
            alignment=TA_LEFT,
            leading=h1_config.get('font_size_pt', 24) * h1_config.get('line_height', 1.15)
        )
        
        # Headline style (H2 from config)
        h2_config = typo_scale.get('h2', {})
        headline_style = ParagraphStyle(
            'CustomHeadline',
            parent=styles['Normal'],
            fontSize=h2_config.get('font_size_pt', 14),
            textColor=HexColor(h2_config.get('color', '#111111')),
            fontName=self._get_font_name(h2_config.get('font_family', self.font_primary), self.font_primary_fallbacks),
            spaceAfter=12,
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
        
        # Left column: Company name, headline, analysis paragraphs
        left_story.append(Paragraph(self.company_name, title_style))
        
        # Headline (from analysis or generate one)
        if self.analysis_result and 'key_points' in self.analysis_result:
            headline = " ".join(self.analysis_result['key_points'][:2]) if self.analysis_result['key_points'] else ""
        else:
            headline = f"{self.company_name} Analysis"
        left_story.append(Paragraph(headline, headline_style))
        left_story.append(Spacer(1, 0.15*inch))
        
        # Analysis paragraphs
        if self.analysis_result and 'analysis' in self.analysis_result:
            analysis = self.analysis_result['analysis']
            for para_key in ['paragraph_1', 'paragraph_2', 'paragraph_3']:
                if para_key in analysis:
                    para_text = analysis[para_key]
                    left_story.append(Paragraph(para_text, body_style))
                    left_story.append(Spacer(1, 0.1*inch))
        
        # Add financial data images to left column if available
        # Note: left_frame_width will be calculated later, we'll set image width in PDF generation
        if hasattr(self, 'fig_paths'):
            # Key metrics table (add to left column)
            if self.fig_paths.get('key_metrics_table') and Path(self.fig_paths['key_metrics_table']).exists():
                try:
                    left_story.append(Spacer(1, 0.2*inch))
                    left_story.append(Paragraph("Key Metrics", title_style))
                    left_story.append(Spacer(1, 0.1*inch))
                    img = Image(self.fig_paths['key_metrics_table'])
                    # Width will be set when we know the frame width
                    left_story.append(img)
                    left_story.append(Spacer(1, 0.1*inch))
                except Exception as e:
                    print(f"Warning: Could not add key metrics table: {e}")
        
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
        left_story.append(Spacer(1, 0.1*inch))
        # Source text with brand name from config
        source_text = f"Sources for: Style Exposure – {self.brand_name} Quantitative and Derivatives Strategy; all other tables are company data and {self.brand_name} estimates."
        left_story.append(Paragraph(source_text, source_style))
        
        # Disclosure prompt
        disclosure_text = "See page 11 for analyst certification and important disclosures."
        left_story.append(Paragraph(disclosure_text, source_style))
        
        # Build PDF using Canvas and Frames (similar to ReportBuild.py format)
        print(f"Building PDF: {output_path}")
        
        # Create canvas directly (like ReportBuild.py)
        c = canvas.Canvas(str(output_path), pagesize=LETTER)
        
        # Draw header from config
        header_font_family = self.header_config.get('font_family', 'Roboto')
        header_font_size = self.header_config.get('font_size_pt', 8)
        header_color_hex = self.header_config.get('color', '#4A4A4A')
        header_color = HexColor(header_color_hex)
        
        # Use fallback font if primary not available
        header_font = self._get_font_name(header_font_family, self.font_secondary_fallbacks)
        
        c.setFont(header_font, header_font_size)
        c.setFillColor(header_color)
        
        # Left text: brand name
        left_text = self.header_config.get('left_text', f'{self.brand_name} | Research')
        c.drawString(self.margin_left, self.page_height - self.margin_top + 10, left_text)
        
        # Center text: report type (if specified)
        center_text = self.header_config.get('center_text', 'North America Equity Research')
        if center_text:
            c.drawCentredString(self.page_width / 2, self.page_height - self.margin_top + 10, center_text)
        
        # Right text: report date
        report_date_format = self.config.get('inputs', {}).get('source_report', {}).get('report_date')
        if report_date_format:
            # Parse date from config if provided
            try:
                report_date = datetime.strptime(report_date_format, '%Y-%m-%d')
                right_text = report_date.strftime('%d %B %Y')
            except:
                right_text = datetime.now().strftime('%d %B %Y')
        else:
            right_text = datetime.now().strftime('%d %B %Y')
        
        right_text_config = self.header_config.get('right_text')
        if right_text_config:
            right_text = right_text_config
        
        c.drawRightString(self.page_width - self.margin_right, self.page_height - self.margin_top + 10, right_text)
        
        # Draw divider line below header (from config)
        divider_config = self.header_config.get('divider', {})
        if divider_config.get('show', True):
            divider_color_hex = divider_config.get('color', '#E6E6E6')
            divider_thickness = divider_config.get('thickness_pt', 0.75)
            c.setStrokeColor(HexColor(divider_color_hex))
            c.setLineWidth(divider_thickness)
            c.line(self.margin_left, self.page_height - self.margin_top, 
                   self.page_width - self.margin_right, self.page_height - self.margin_top)
        
        # Define frame dimensions (similar to ReportBuild.py)
        right_frame_width = 185  # Fixed width for right column (in points)
        left_frame_width = self.page_width - self.margin_right - right_frame_width - self.margin_left
        right_frame_x = self.page_width - self.margin_right - right_frame_width
        frame_height = self.page_height - self.margin_top - self.margin_bottom - 95  # Reserve space for header
        
        # Draw vertical divider line between columns
        c.setStrokeColor(self.color_light_grey)
        c.setLineWidth(0.5)
        c.line(right_frame_x, self.margin_bottom, right_frame_x, self.page_height - self.margin_top - 95)
        
        # Create left frame for text content (like ReportBuild.py)
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
        right_y = self.page_height - self.margin_top - 95 - 20
        
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
        
        if self.company_data:
            current_price = self.company_data.get('52w_high', 0) * 0.8 if self.company_data.get('52w_high') else 100
        else:
            current_price = 100
        price_target = current_price * 0.7
        
        c.drawString(right_frame_x + 4, right_y, f"Price ({datetime.now().strftime('%d %b %y')}) ${current_price:.2f}")
        right_y -= 12
        c.drawString(right_frame_x + 4, right_y, f"Price Target (Dec-25) ${price_target:.2f}")
        right_y -= 20
        
        # Sector - use brand colors
        c.setFont(f'{body_font}-Bold' if body_font == 'Helvetica' else body_font, 9)
        c.setFillColor(self.color_dark_grey)  # Use dark grey for sector
        c.drawString(right_frame_x + 4, right_y, "Autos & Auto Parts")
        right_y -= 15
        
        # Analyst contact from config
        author_section = self.config.get('inputs', {}).get('author_section', {})
        analysts = author_section.get('analysts', [])
        
        if analysts:
            # Use first analyst as primary contact
            primary_analyst = analysts[0]
            analyst_font = self._get_font_name(
                author_section.get('typography', {}).get('name_font', {}).get('family', self.font_primary),
                self.font_primary_fallbacks
            )
            analyst_font_size = author_section.get('typography', {}).get('name_font', {}).get('size_pt', 9)
            
            c.setFont(analyst_font, analyst_font_size)
            c.setFillColor(self.color_text)
            
            analyst_info = [
                f"{primary_analyst.get('name', 'Analyst')}, {primary_analyst.get('role', 'AC')}",
                primary_analyst.get('phone', '+1-212-555-1234'),
                primary_analyst.get('email', f'analyst@{self.brand_name.lower().replace(" ", "")}.com')
            ]
            
            # Add legal entity if configured
            if author_section.get('show_legal_entity', False):
                legal_entity = author_section.get('legal_entity', {})
                if legal_entity.get('name'):
                    analyst_info.append(legal_entity['name'])
            
            for info in analyst_info:
                c.drawString(right_frame_x + 4, right_y, info)
                right_y -= 10
            right_y -= 10
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
                        right_y -= 15
                        c.setFont(f'{body_font}-Bold' if body_font == 'Helvetica' else body_font, 9)
                        c.setFillColor(self.color_dark_grey)  # Use dark grey for section titles
                        c.drawString(right_frame_x + 4, right_y, "Price Performance")
                        right_y -= 12
                        
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
                            right_y -= img.drawHeight + 15
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
                        right_y -= 15
                        c.setFont(f'{body_font}-Bold' if body_font == 'Helvetica' else body_font, 9)
                        c.setFillColor(self.color_dark_grey)  # Use dark grey for section titles
                        c.drawString(right_frame_x + 4, right_y, "Company Data")
                        right_y -= 12
                        
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
        
        # Draw footer from config
        if self.footer_config.get('show', True):
            footer_font_family = self.footer_config.get('font_family', 'Roboto')
            footer_font_size = self.footer_config.get('font_size_pt', 7)
            footer_color_hex = self.footer_config.get('color', '#7A7A7A')
            footer_color = HexColor(footer_color_hex)
            footer_font = self._get_font_name(footer_font_family, self.font_secondary_fallbacks)
            
            c.setFont(footer_font, footer_font_size)
            c.setFillColor(footer_color)
            
            # Left text from config template
            left_text_template = self.footer_config.get('left_text_template', '{provider} Research')
            left_text = left_text_template.format(provider=self.brand_name)
            c.drawString(self.margin_left, self.margin_bottom - 15, left_text[:80])
            
            # Right text from config template (page number or URL)
            right_text_template = self.footer_config.get('right_text_template', '{page_number}')
            # For now, use a simple URL - page numbers would need page tracking
            right_text = f'www.{self.brand_name.lower().replace(" ", "")}markets.com'
            c.drawRightString(self.page_width - self.margin_right, self.margin_bottom - 15, right_text)
        
        c.save()
        
        print(f"Report generated successfully: {output_path}")
        return str(output_path)


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
