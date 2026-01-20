from reportlab.pdfgen import canvas
from reportlab.platypus import Image, Table, TableStyle, Spacer
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.colors import Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import  colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Frame, Flowable
from finrpt.utils.charting import get_share_performance, get_pe_eps_performance, get_revenue_performance
import pandas as pd
from datetime import timedelta, datetime
import yfinance as yf
import requests
import pickle
import os
import pdb
import json
import yaml
from pathlib import Path
try:
    from agentic.fmp_graph_generator import generate_all_graphs
    FMP_GRAPH_GENERATOR_AVAILABLE = True
except ImportError:
    FMP_GRAPH_GENERATOR_AVAILABLE = False
    print("Warning: fmp_graph_generator not available, skipping FMP table generation")


# FINE2C and TARGETMAP are no longer used - all financial data comes from agentic modules as PNG tables
# Keeping these for reference but they are not actively used in the report generation
FINE2C = {}  # Deprecated - not used
TARGETMAP = {}  # Deprecated - not used

# BASE_key_mapping removed - keys from get_key_data() are already in English


def load_config(config_path='config.yaml'):
    """Load configuration from YAML file"""
    config_paths = [
        config_path,
        os.path.join(os.path.dirname(__file__), '..', '..', config_path),
        os.path.join(os.getcwd(), config_path)
    ]
    
    for path in config_paths:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
    
    print(f"Warning: Config file not found, using default values")
    return None


def hex_to_color(hex_color):
    """Convert hex color string to ReportLab Color object"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return Color(r, g, b)
    return colors.black


def map_to_builtin_font(font_name):
    """Map any font name to a built-in ReportLab font"""
    if not font_name:
        return 'Helvetica'
    
    font_lower = font_name.lower()
    
    # Check if already a built-in font
    if font_name in ['Helvetica', 'Times-Roman', 'Courier']:
        return font_name
    
    # Map common fonts to built-ins
    if 'arial' in font_lower or 'helvetica' in font_lower or 'roboto' in font_lower or 'sans' in font_lower:
        return 'Helvetica'
    elif 'times' in font_lower or 'georgia' in font_lower or 'serif' in font_lower or 'gloriola' in font_lower:
        return 'Times-Roman'
    elif 'courier' in font_lower or 'monospace' in font_lower:
        return 'Courier'
    else:
        return 'Helvetica'  # Default fallback


def get_font_name(config, font_key='primary_family'):
    """Get font name from config with fallback to built-in ReportLab fonts"""
    if not config or 'typography' not in config:
        return 'Helvetica'
    
    typo = config['typography']
    if font_key in typo:
        font_info = typo[font_key]
        font_name = None
        fallbacks = []
        
        if isinstance(font_info, dict):
            font_name = font_info.get('name')
            fallbacks = font_info.get('fallbacks', [])
        elif isinstance(font_info, str):
            font_name = font_info
        
        # Try the primary font name first
        if font_name:
            mapped = map_to_builtin_font(font_name)
            if mapped:
                return mapped
        
        # Try fallbacks in order
        for fallback in fallbacks:
            mapped = map_to_builtin_font(fallback)
            if mapped:
                return mapped
    
    # Default to Helvetica
    return 'Helvetica'


def get_page_size(config):
    """Get page size from config"""
    if not config or 'layout' not in config or 'page' not in config['layout']:
        return A4
    
    page_config = config['layout']['page']
    size = page_config.get('size', 'A4')
    
    if size.upper() == 'LETTER':
        return LETTER
    return A4


def get_next_weekday(date):

    if not isinstance(date, datetime):
        date = datetime.strptime(date, "%Y-%m-%d")

    if date.weekday() >= 5:
        days_to_add = 7 - date.weekday()
        next_weekday = date + timedelta(days=days_to_add)
        return next_weekday
    else:
        return date

def get_historical_market_cap(
    ticker_symbol,
    date
) -> str:
    """Get the historical market capitalization for a given stock on a given date"""
    date = get_next_weekday(date).strftime("%Y-%m-%d")
    url = f"https://financialmodelingprep.com/api/v3/historical-market-capitalization/{ticker_symbol}?limit=100&from={date}&to={date}&apikey={fmp_api_key}"

    # 发送GET请求
    mkt_cap = None
    response = requests.get(url)

    # 确保请求成功
    if response.status_code == 200:
        # 解析JSON数据
        data = response.json()
        mkt_cap = data[0]["marketCap"]
        return mkt_cap
    else:
        return f"Failed to retrieve data: {response.status_code}"
    
def get_historical_bvps(
    ticker_symbol,
    target_date
):
    """Get the historical book value per share for a given stock on a given date"""
    # 从FMP API获取历史关键财务指标数据
    url = f"https://financialmodelingprep.com/api/v3/key-metrics/{ticker_symbol}?limit=40&apikey={fmp_api_key}"
    response = requests.get(url)
    data = response.json()

    if not data:
        return "No data available"

    # 找到最接近目标日期的数据
    closest_data = None
    min_date_diff = float("inf")
    target_date = datetime.strptime(target_date, "%Y-%m-%d")
    for entry in data:
        date_of_data = datetime.strptime(entry["date"], "%Y-%m-%d")
        date_diff = abs(target_date - date_of_data).days
        if date_diff < min_date_diff:
            min_date_diff = date_diff
            closest_data = entry

    if closest_data:
        return closest_data.get("bookValuePerShare", "No BVPS data available")
    else:
        return "No close date data found"


def get_key_data(ticker_symbol, filing_date):

    if not isinstance(filing_date, datetime):
        filing_date = datetime.strptime(filing_date, "%Y-%m-%d")

    # Fetch historical market data for the past 6 months
    start = (filing_date - timedelta(weeks=52)).strftime("%Y-%m-%d")
    end = filing_date.strftime("%Y-%m-%d")
    
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(start=start, end=end)
        info = ticker.info
        if hist.empty:
            raise ValueError("No historical data available")
        close_price = hist["Close"].iloc[-1]
    except Exception as e:
        print(f"Warning: Could not fetch data from yfinance for {ticker_symbol}: {e}")
        # Return empty/default data if yfinance fails
        info = {"currency": "CNY"}
        close_price = 0
        hist = pd.DataFrame()

    # Calculate the average daily trading volume
    if hist.empty:
        avg_daily_volume_6m = 0
        fiftyTwoWeekLow = 0
        fiftyTwoWeekHigh = 0
    else:
        six_months_start = (filing_date - timedelta(weeks=26)).strftime("%Y-%m-%d")
        hist_last_6_months = hist[
            (hist.index >= six_months_start) & (hist.index <= end)
        ]

        # 计算这6个月的平均每日交易量
        avg_daily_volume_6m = (
            hist_last_6_months["Volume"].mean()
            if not hist_last_6_months["Volume"].empty
            else 0
        )

        fiftyTwoWeekLow = hist["High"].min()
        fiftyTwoWeekHigh = hist["Low"].max()

    # avg_daily_volume_6m = hist['Volume'].mean()

    # convert back to str for function calling
    filing_date = filing_date.strftime("%Y-%m-%d")

    # Print the result
    # print(f"Over the past 6 months, the average daily trading volume for {ticker_symbol} was: {avg_daily_volume_6m:.2f}")
    # rating, _ = YFinanceUtils.get_analyst_recommendations(ticker_symbol)
    # target_price = FMPUtils.get_target_price(ticker_symbol, filing_date)
    # Get currency with fallback
    currency = info.get('currency', 'CNY')
    
    result = {
        # "Rating": rating,
        # "Target Price": target_price,
        f"6m avg daily vol ({currency}mn)": "{:.2f}".format(
            avg_daily_volume_6m / 1e6 if avg_daily_volume_6m > 0 else 0
        ),
        f"Closing Price ({currency})": "{:.2f}".format(close_price),
        # f"Market Cap ({currency}mn)": "{:.2f}".format(
        #     get_historical_market_cap(ticker_symbol, filing_date) / 1e6
        # ),
        f"52 Week Price Range ({currency})": "{:.2f} - {:.2f}".format(
            fiftyTwoWeekLow, fiftyTwoWeekHigh
        ),
        # f"BVPS ({currency})": "{:.2f}".format(
        #     get_historical_bvps(ticker_symbol, filing_date)
        # ),
    }
    return result


class BulletParagraph(Flowable):
    def __init__(self, icon_path, text, font_name, config=None):
        Flowable.__init__(self)
        self.icon_path = icon_path
        styles = getSampleStyleSheet()
        
        # Get body text style from config
        if config and 'typography' in config and 'scale' in config['typography']:
            body_style = config['typography']['scale'].get('body', {})
            font_size = body_style.get('font_size_pt', 10)
            line_height = body_style.get('line_height', 1.35)
            text_color = hex_to_color(body_style.get('color', '#111111'))
        else:
            font_size = 10
            line_height = 1.35
            text_color = colors.black
        
        # More condensed spacing for bullet paragraphs
        custom_style = ParagraphStyle(
            'CustomStyle',
            parent=styles['Normal'],
            fontName=font_name,  
            fontSize=font_size,
            leading=font_size * max(line_height - 0.2, 1.1),  # Tighter line spacing
            spaceAfter=6,  # Reduced from 12 to 6
            textColor=text_color,
            alignment=0  
        )
        self.paragraph = Paragraph(text, custom_style)
        self.icon = Image(self.icon_path, 10, 10)

    def wrap(self, availWidth, availHeight):
        icon_width, icon_height = self.icon.drawWidth, self.icon.drawHeight
        para_width, para_height = self.paragraph.wrap(availWidth - icon_width - 6, availHeight)
        self.width = icon_width + 6 + para_width
        self.height = max(icon_height, para_height)
        return self.width, self.height

    def draw(self):
        self.icon.drawOn(self.canv, 0, self.height - self.icon.drawHeight - 3)
        self.paragraph.drawOn(self.canv, self.icon.drawWidth + 6, 0)
 
def draw_frame_title(text, set_color, col_width, font_name, config=None):
    data = [[text]]
    table = Table(data, colWidths=col_width)
    
    # Get table header style from config
    if config and 'components' in config and 'table_style' in config['components']:
        header_style = config['components']['table_style'].get('header', {})
        header_font_raw = header_style.get('font_family', font_name)
        header_font = map_to_builtin_font(header_font_raw)
        header_size = header_style.get('font_size_pt', 12)
        header_weight = header_style.get('font_weight', 700)
        text_color = hex_to_color(header_style.get('text_color', '#FFFFFF'))
    else:
        header_font = map_to_builtin_font(font_name)
        header_size = 12
        header_weight = 700
        text_color = colors.white
    
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), set_color),
        ('TEXTCOLOR', (0, 0), (-1, -1), text_color),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), header_size),
        ('FONTNAME', (0, 0), (-1, -1), header_font),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
    ]))
    return table

def get_base_table(font_name, data, config=None):
    styles = getSampleStyleSheet()
    
    # Get body text style from config
    if config and 'typography' in config and 'scale' in config['typography']:
        body_style = config['typography']['scale'].get('body', {})
        font_size = body_style.get('font_size_pt', 9)
        text_color = hex_to_color(body_style.get('color', '#111111'))
    else:
        font_size = 9
        text_color = colors.black
    
    style_left = styles['Normal']
    style_left.fontName = font_name
    style_left.fontSize = font_size
    style_left.textColor = text_color

    style_right = styles['Normal']
    style_right.fontName = font_name
    style_right.fontSize = font_size
    style_right.textColor = text_color

    for da in data:
        [Paragraph(da[0], style_left), Paragraph(da[1], style_right)]
        

    table = Table(data, colWidths=[90, 90])

    table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TEXTCOLOR', (0, 0), (0, -1), text_color),
        ('TEXTCOLOR', (1, 0), (1, -1), text_color),
        ('FONT', (0, 0), (0, -1), font_name, font_size),
        ('FONT', (1, 0), (1, -1), font_name, font_size),
    ]))
    
    return table


def get_financias_table(font_name, data, config=None):
    col_widths = [115, 55, 55, 55, 55]

    table = Table(data, colWidths=col_widths)

    # Get table styles from config
    if config and 'components' in config and 'table_style' in config['components']:
        table_config = config['components']['table_style']
        header_style = table_config.get('header', {})
        body_style = table_config.get('body', {})
        border_style = table_config.get('borders', {})
        
        header_fill = hex_to_color(header_style.get('fill', '#0060A0'))
        header_text_color = hex_to_color(header_style.get('text_color', '#FFFFFF'))
        header_font_raw = header_style.get('font_family', font_name)
        header_font = map_to_builtin_font(header_font_raw)
        header_size = header_style.get('font_size_pt', 8)
        
        body_font_raw = body_style.get('font_family', font_name)
        body_font = map_to_builtin_font(body_font_raw)
        body_size = body_style.get('font_size_pt', 8)
        body_text_color = hex_to_color(body_style.get('text_color', '#111111'))
        zebra_stripes = body_style.get('zebra_stripes', True)
        stripe_fill = hex_to_color(body_style.get('stripe_fill', '#F5F5F5'))
        
        border_color = hex_to_color(border_style.get('color', '#E6E6E6'))
        border_thickness = border_style.get('thickness_pt', 0.5)
    else:
        header_fill = colors.lightgrey
        header_text_color = colors.white
        header_font = font_name
        header_size = 8
        body_font = font_name
        body_size = 8
        body_text_color = colors.black
        zebra_stripes = True
        stripe_fill = colors.whitesmoke
        border_color = colors.lightgrey
        border_thickness = 0.5

    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), header_fill),
        ('TEXTCOLOR', (0, 0), (-1, 0), header_text_color),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), header_font),
        ('FONTSIZE', (0, 0), (-1, 0), header_size),
        ('FONTNAME', (0, 1), (-1, -1), body_font),
        ('FONTSIZE', (0, 1), (-1, -1), body_size),
        ('TEXTCOLOR', (0, 1), (-1, -1), body_text_color),
        ('GRID', (0, 0), (-1, -1), border_thickness, border_color),
    ])

    if zebra_stripes:
        for i in range(1, len(data)):
            if i % 2 == 0:
                style.add('BACKGROUND', (0, i), (-1, i), stripe_fill)
            else:
                style.add('BACKGROUND', (0, i), (-1, i), colors.white)

    table.setStyle(style)
    return table

def build_report(
    res_data,
    date,   
    save_path='./reports/',
    config_path='config.yaml'
):
    # Load configuration
    config = load_config(config_path)
    
    company_name = res_data.get('company_name', res_data.get('stock_code', 'Unknown'))
    stock_code = res_data['stock_code']
    
    # Use figs folder from save_path (generated by EP.py)
    # This ensures we use the same folder that EP.py created, avoiding duplicate folders
    save_figs_path = os.path.join(save_path, "figs")
    if not os.path.exists(save_figs_path):
        os.makedirs(save_figs_path)
    
    # Use save_path/figs as the primary figs path
    figs_path = Path(save_figs_path)
    
    # Note: FMP tables and graphs should already be generated by EP.py
    # We only generate legacy charts here if they don't exist
    # Convert figs_path to string for path operations
    figs_path_str = str(figs_path)
    
    # Generate legacy charts only if they don't exist (EP.py may have already generated them)
    share_performance_image_path = os.path.join(figs_path_str, "share_performance.png")
    pe_eps_performance_image_path = os.path.join(figs_path_str, "pe_eps.png")
    revenue_performance_image_path = os.path.join(figs_path_str, "revenue_performance.png")
    
    if not os.path.exists(share_performance_image_path):
        get_share_performance(res_data, stock_code, date, save_path=figs_path_str)
    if not os.path.exists(pe_eps_performance_image_path):
        get_pe_eps_performance(res_data, stock_code, date, save_path=figs_path_str)
    if not os.path.exists(revenue_performance_image_path):
        get_revenue_performance(res_data, stock_code, date, save_path=figs_path_str)
    # Check for graph_price_performance.png and table_company_data.png
    graph_price_performance_path = os.path.join(figs_path_str, "graph_price_performance.png")
    table_company_data_path = os.path.join(figs_path_str, "table_company_data.png")
    table_key_metrics_path = os.path.join(figs_path_str, "table_key_metrics.png")
    table_income_statement_path = os.path.join(figs_path_str, "table_income_statement.png")
    table_balance_sheet_path = os.path.join(figs_path_str, "table_balance_sheet.png")
    table_cash_flow_path = os.path.join(figs_path_str, "table_cash_flow_statement.png")
    
    # If graph_price_performance.png doesn't exist, fall back to share_performance.png
    if not os.path.exists(graph_price_performance_path):
        graph_price_performance_path = share_performance_image_path
    
    # Check for analyst agent analysis result
    analyst_analysis = None
    if 'analyst_analysis' in res_data:
        analyst_analysis = res_data['analyst_analysis']
    else:
        # Try to load from saved analysis result file
        analysis_result_path = os.path.join(save_path, 'analysis_result.json')
        if os.path.exists(analysis_result_path):
            try:
                with open(analysis_result_path, 'r', encoding='utf-8') as f:
                    analyst_analysis = json.load(f)
            except:
                pass
    
    # company_name and stock_code already set above
    
    # Get primary color from config
    if config and 'brand' in config and 'colors' in config['brand']:
        primary_color_hex = config['brand']['colors']['primary'].get('hex', '#0060A0')
        color1 = hex_to_color(primary_color_hex)
    else:
        color1 = Color(red=158 / 255.0, green=31 / 255.0, blue=0)
    
    # Get font from config
    primary_font = get_font_name(config, 'primary_family')
    secondary_font = get_font_name(config, 'secondary_family')
    
    # Try to register Chinese font, fallback to default if not found
    font_name = primary_font  # Default font from config
    try:
        # Try multiple possible font paths
        font_paths = ['msyh.ttf', './msyh.ttf', '../msyh.ttf', '/System/Library/Fonts/PingFang.ttc']
        font_registered = False
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('微软雅黑', font_path))
                    font_registered = True
                    font_name = '微软雅黑'
                    break
                except:
                    continue
        if not font_registered:
            # Use config font or default built-in font if Chinese font not found
            if font_name not in ['Helvetica', 'Arial']:
                print(f"Warning: Chinese font not found, using config font: {font_name}")
            else:
                print("Warning: Chinese font not found, using default built-in font (Helvetica)")
                font_name = 'Helvetica'
    except Exception as e:
        print(f"Warning: Could not register Chinese font: {e}, using config font: {font_name}")
        font_name = primary_font if primary_font else 'Helvetica'
    
    # Get page size from config
    page_size = get_page_size(config)
    
    styles = getSampleStyleSheet()

    filename = (
            os.path.join(save_path, f"{stock_code}_{date}_{res_data['model_name']}.pdf")
            if os.path.isdir(save_path)
            else save_path
        )
    c = canvas.Canvas(filename, pagesize=page_size)

    # Try to load logo, use multiple possible paths
    logo_paths = [
        os.path.join(figs_path_str, "logo.png"),
        "figs/logo.png",
        "./figs/logo.png",
        "../figs/logo.png",
        "./finrpt/utils/figs/logo.png",
        os.path.join(os.path.dirname(__file__), "figs", "logo.png")
    ]
    logo_path = None
    for path in logo_paths:
        if os.path.exists(path):
            logo_path = path
            break
    
    # Get page dimensions
    page_width, page_height = page_size
    
    # Get layout margins from config
    if config and 'layout' in config and 'page' in config['layout'] and 'margins_in' in config['layout']['page']:
        margins = config['layout']['page']['margins_in']
        margin_top = margins.get('top', 0.6) * 72  # Convert inches to points
        margin_left = margins.get('left', 0.65) * 72
        margin_right = margins.get('right', 0.65) * 72
        margin_bottom = margins.get('bottom', 0.6) * 72
    else:
        margin_top = 0.6 * 72
        margin_left = 0.65 * 72
        margin_right = 0.65 * 72
        margin_bottom = 0.6 * 72
    
    # Draw header if configured
    if config and 'layout' in config and 'header' in config['layout']:
        header_config = config['layout']['header']
        if header_config.get('show', True):
            # Use map_to_builtin_font to ensure fallback to built-in fonts
            header_font_raw = header_config.get('font_family', secondary_font)
            header_font = map_to_builtin_font(header_font_raw)
            header_size = header_config.get('font_size_pt', 8)
            header_color = hex_to_color(header_config.get('color', '#4A4A4A'))
            
            left_text = header_config.get('left_text', '')
            right_text = header_config.get('right_text', '')
            
            c.setFont(header_font, header_size)
            c.setFillColor(header_color)
            c.drawString(margin_left, page_height - margin_top + 10, left_text)
            c.drawRightString(page_width - margin_right, page_height - margin_top + 10, right_text)
            
            # Draw divider if configured
            if header_config.get('divider', {}).get('show', True):
                divider_config = header_config['divider']
                divider_color = hex_to_color(divider_config.get('color', '#E6E6E6'))
                divider_thickness = divider_config.get('thickness_pt', 0.75)
                c.setStrokeColor(divider_color)
                c.setLineWidth(divider_thickness)
                c.line(margin_left, page_height - margin_top, page_width - margin_right, page_height - margin_top)
                c.setLineWidth(1)
    
    if logo_path:
        try:
            img = Image(logo_path)
            raw_width = img.imageWidth
            raw_height = img.imageHeight
            img.drawHeight = 40
            img.drawWidth = img.drawHeight * (raw_width / raw_height)
            img.drawOn(c, margin_left, page_height - margin_top - 30)
        except Exception as e:
            print(f"Warning: Could not load logo: {e}")
    else:
        print("Warning: Logo file not found, skipping logo")
    
    # Get typography for company name and date
    if config and 'typography' in config and 'scale' in config['typography']:
        h2_style = config['typography']['scale'].get('h2', {})
        h2_size = h2_style.get('font_size_pt', 12)
        h2_color = hex_to_color(h2_style.get('color', '#111111'))
    else:
        h2_size = 12
        h2_color = colors.black
    
    c.setStrokeColor(h2_color)
    c.setFont(font_name, h2_size)
    c.drawString(margin_left, page_height - margin_top - 50, f"{company_name}（{stock_code}）")
    c.drawString(margin_left + 180, page_height - margin_top - 50, f"{date}")

    # Get title from config.yaml, fallback to res_data
    if config and 'components' in config and 'title_block' in config['components']:
        title_from_config = config['components']['title_block'].get('title', '')
        if title_from_config:
            title = title_from_config
        else:
            # Fallback to res_data if config title is empty
            title = company_name + ":" + res_data.get('report_title', '') if \
                company_name not in res_data.get('report_title', '') else res_data.get('report_title', '')
    else:
        # Fallback to res_data if no config
        title = company_name + ":" + res_data.get('report_title', '') if \
            company_name not in res_data.get('report_title', '') else res_data.get('report_title', '')
    
    # Get title style from config
    if config and 'components' in config and 'title_block' in config['components']:
        title_config = config['components']['title_block']['title_font']
        title_font_raw = title_config.get('family', font_name)
        title_size = title_config.get('size_pt', 24)
        title_color = hex_to_color(title_config.get('color', primary_color_hex))
    elif config and 'typography' in config and 'scale' in config['typography']:
        h1_style = config['typography']['scale'].get('h1', {})
        title_font_raw = h1_style.get('font_family', font_name)
        title_size = h1_style.get('font_size_pt', 24)
        title_color = hex_to_color(h1_style.get('color', '#111111'))
    else:
        title_font_raw = font_name
        title_size = 17
        title_color = color1
    
    # Map to built-in ReportLab font
    title_font = map_to_builtin_font(title_font_raw) if title_font_raw else 'Times-Roman'
    
    title_style = ParagraphStyle(
        name='CustomStyle',
        parent=styles['Normal'],  
        fontName=title_font,
        fontSize=title_size,
        leading=title_size * 1.15,
        textColor=title_color,
        alignment=1, 
        spaceBefore=10,
        spaceAfter=10
    )
    title_paragraph = Paragraph(title, title_style)
    frame_title = Frame(
        x1=margin_left + 130, 
        y1=page_height - margin_top - 70, 
        width=400, 
        height=30, 
        showBoundary=0
    )
    frame_title.addFromList([title_paragraph], c)
    
    
    c.setStrokeColor(color1)
    c.line(page_width - margin_right - 185, page_height - margin_top - 95, page_width - margin_right - 185, margin_bottom)
    
    # frame_left
    c.setStrokeColor(colors.black)
    frame_left_list = []
    left_frame_width = page_width - margin_right - 185 - margin_left
    frame_left = Frame(
        x1=margin_left, 
        y1=margin_bottom, 
        width=left_frame_width, 
        height=page_height - margin_top - margin_bottom - 95, 
        showBoundary=0,
        topPadding=0,
        leftPadding=4, 
        rightPadding=4
    )
    
    # Get section titles from config
    section_titles = {}
    if config and 'components' in config and 'section_titles' in config['components']:
        section_titles = config['components']['section_titles']
    
    core_insights_title = section_titles.get('core_insights', 'Core Insights')
    frame_title1 = draw_frame_title(core_insights_title, color1, left_frame_width - 8, font_name, config)
    frame_left_list.append(frame_title1)
    frame_left_list.append(Spacer(1, 4))
    
    # Try to find icon path
    icon_paths = [
        os.path.join(figs_path_str, "icon.png"),
        "figs/icon.png",
        "./figs/icon.png",
        "./finrpt/utils/figs/icon.png",
        os.path.join(os.path.dirname(__file__), "figs", "icon.png")
    ]
    icon_path = "figs/icon.png"  # default
    for path in icon_paths:
        if os.path.exists(path):
            icon_path = path
            break
    
    # Get accent color for titles in paragraphs
    if config and 'brand' in config and 'colors' in config['brand']:
        accent_color_hex = config['brand']['colors'].get('primary', {}).get('hex', '#0060A0')
    else:
        accent_color_hex = '#9E1F00'
    
    # Use analyst agent analysis if available, otherwise fall back to analyze_advisor
    if analyst_analysis and 'analysis' in analyst_analysis:
        # Use the 3-paragraph analysis from analyst agent
        analysis = analyst_analysis['analysis']
        paragraphs = [
            analysis.get('paragraph_1', ''),
            analysis.get('paragraph_2', ''),
            analysis.get('paragraph_3', '')
        ]
        for para in paragraphs:
            if para:
                paragraph_text = para
                try:
                    paragraph_advisor = BulletParagraph(icon_path, paragraph_text, font_name, config)
                except:
                    # Fallback if icon not found - use more condensed style
                    para_style = ParagraphStyle(
                        name='Custom', 
                        parent=styles['Normal'], 
                        fontName=font_name,
                        fontSize=9,  # Smaller font
                        leading=11,  # Tighter line spacing
                        spaceAfter=3  # Less space after
                    )
                    paragraph_advisor = Paragraph(paragraph_text, para_style)
                frame_left_list.append(paragraph_advisor)
                frame_left_list.append(Spacer(1, 2))  # Reduced from 4 to 2
    elif "analyze_advisor" in res_data:
        # Fallback to original analyze_advisor format - more condensed
        for sub_advisor in res_data["analyze_advisor"]:
            paragraph_text = f'<font color="{accent_color_hex}"><b>{sub_advisor["title"]}: </b></font>{sub_advisor["content"]}'
            try:
                paragraph_advisor = BulletParagraph(icon_path, paragraph_text, font_name, config)
            except:
                # Fallback if icon not found - use more condensed style
                para_style = ParagraphStyle(
                    name='Custom', 
                    parent=styles['Normal'], 
                    fontName=font_name,
                    fontSize=9,  # Smaller font
                    leading=11,  # Tighter line spacing
                    spaceAfter=3  # Less space after
                )
                paragraph_advisor = Paragraph(paragraph_text.replace(f'<font color="{accent_color_hex}"><b>', '<b>').replace('</b></font>', '</b>'), para_style)
            frame_left_list.append(paragraph_advisor)
            frame_left_list.append(Spacer(1, 2))  # Reduced from 4 to 2
        
    risk_assessment = ""
    for idx, risk in enumerate(res_data["analyze_risk"]):
        risk_assessment += "(" + str(idx + 1) + ")" + risk + ";"
    risk_title = section_titles.get('risk_assessment', 'Risk Assessment')
    paragraph_text = f'<font color="{accent_color_hex}"><b>{risk_title}: </b></font>{risk_assessment}'
    try:
        paragraph_advisor = BulletParagraph(icon_path, paragraph_text, font_name, config)
    except:
        # More condensed style for risk assessment
        para_style = ParagraphStyle(
            name='Custom', 
            parent=styles['Normal'], 
            fontName=font_name,
            fontSize=9,  # Smaller font
            leading=11,  # Tighter line spacing
            spaceAfter=3  # Less space after
        )
        paragraph_advisor = Paragraph(paragraph_text.replace(f'<font color="{accent_color_hex}"><b>', '<b>').replace('</b></font>', '</b>'), para_style)
    frame_left_list.append(paragraph_advisor)
    frame_left_list.append(Spacer(1, 2))  # Reduced from 4 to 2
        
    financial_data_title = section_titles.get('financial_data', 'Financial Data')
    frame_title2 = draw_frame_title(financial_data_title, color1, left_frame_width - 8, font_name, config)
    frame_left_list.append(frame_title2)
    frame_left_list.append(Spacer(1, 5))
    
    # Add FMP tables if available (key metrics, income statement, balance sheet, cash flow)
    
    # Key Metrics Table
    if os.path.exists(table_key_metrics_path):
        key_metrics_title = section_titles.get('key_metrics', 'Key Metrics')
        frame_title_key_metrics = draw_frame_title(key_metrics_title, color1, left_frame_width - 8, font_name, config)
        frame_left_list.append(frame_title_key_metrics)
        frame_left_list.append(Spacer(1, 3))
        key_metrics_img = Image(table_key_metrics_path)
        # Scale to fit frame width
        key_metrics_img.drawWidth = left_frame_width - 8
        key_metrics_img.drawHeight = key_metrics_img.drawWidth * (key_metrics_img.imageHeight / key_metrics_img.imageWidth)
        frame_left_list.append(key_metrics_img)
        frame_left_list.append(Spacer(1, 5))
    
    # Income Statement Table
    if os.path.exists(table_income_statement_path):
        income_title = section_titles.get('income_statement', 'Income Statement')
        frame_title_income = draw_frame_title(income_title, color1, left_frame_width - 8, font_name, config)
        frame_left_list.append(frame_title_income)
        frame_left_list.append(Spacer(1, 3))
        income_img = Image(table_income_statement_path)
        income_img.drawWidth = left_frame_width - 8
        income_img.drawHeight = income_img.drawWidth * (income_img.imageHeight / income_img.imageWidth)
        frame_left_list.append(income_img)
        frame_left_list.append(Spacer(1, 5))
    
    # Balance Sheet Table
    if os.path.exists(table_balance_sheet_path):
        balance_title = section_titles.get('balance_sheet', 'Balance Sheet')
        frame_title_balance = draw_frame_title(balance_title, color1, left_frame_width - 8, font_name, config)
        frame_left_list.append(frame_title_balance)
        frame_left_list.append(Spacer(1, 3))
        balance_img = Image(table_balance_sheet_path)
        balance_img.drawWidth = left_frame_width - 8
        balance_img.drawHeight = balance_img.drawWidth * (balance_img.imageHeight / balance_img.imageWidth)
        frame_left_list.append(balance_img)
        frame_left_list.append(Spacer(1, 5))
    
    # Cash Flow Statement Table
    if os.path.exists(table_cash_flow_path):
        cashflow_title = section_titles.get('cash_flow', 'Cash Flow Statement')
        frame_title_cashflow = draw_frame_title(cashflow_title, color1, left_frame_width - 8, font_name, config)
        frame_left_list.append(frame_title_cashflow)
        frame_left_list.append(Spacer(1, 3))
        cashflow_img = Image(table_cash_flow_path)
        cashflow_img.drawWidth = left_frame_width - 8
        cashflow_img.drawHeight = cashflow_img.drawWidth * (cashflow_img.imageHeight / cashflow_img.imageWidth)
        frame_left_list.append(cashflow_img)
        frame_left_list.append(Spacer(1, 5))
    
    # If no FMP tables are available, show a message
    if not any([os.path.exists(table_key_metrics_path), os.path.exists(table_income_statement_path), 
                os.path.exists(table_balance_sheet_path), os.path.exists(table_cash_flow_path)]):
        # No financial data available - add a message
        no_data_text = "Financial data not available"
        no_data_para = Paragraph(no_data_text, 
                                ParagraphStyle(name='Custom', parent=styles['Normal'], 
                                             fontName=font_name, fontSize=9))
        frame_left_list.append(no_data_para)
    
    frame_left.addFromList(frame_left_list, c)
    
    
    # frame_right
    right_frame_width = 185
    right_frame_x = page_width - margin_right - right_frame_width
    frame_right_list = []
    frame_right = Frame(
        x1=right_frame_x, 
        y1=margin_bottom, 
        width=right_frame_width, 
        height=page_height - margin_top - margin_bottom - 95, 
        showBoundary=0,
        topPadding=0
    )
    frame_right.addFromList(frame_right_list, c)
    
    author_title = section_titles.get('author', 'Authors')
    frame_title3 = draw_frame_title(author_title, color1, right_frame_width - 4, font_name, config)
    _1, _2 = frame_title3.wrap(0, 0)
    frame_title3.drawOn(c, right_frame_x + 2, page_height - margin_top - 95 - 21)
    
    # Get section divider style from config
    if config and 'components' in config and 'section_heading' in config['components']:
        section_config = config['components']['section_heading']
        if section_config.get('rule', {}).get('show', True):
            rule_config = section_config['rule']
            divider_color = hex_to_color(rule_config.get('color', '#E6E6E6'))
            divider_thickness = rule_config.get('thickness_pt', 1.0)
        else:
            divider_color = color1
            divider_thickness = 1.0
    else:
        divider_color = color1
        divider_thickness = 1.0
    
    c.setStrokeColor(divider_color)
    c.setLineWidth(divider_thickness)
    c.line(right_frame_x + 2, page_height - margin_top - 95 - 50, right_frame_x + right_frame_width - 2, page_height - margin_top - 95 - 50)
    c.setLineWidth(1)
    
    # Get body text style for author info
    if config and 'typography' in config and 'scale' in config['typography']:
        body_style = config['typography']['scale'].get('body', {})
        body_size = body_style.get('font_size_pt', 9)
        body_color = hex_to_color(body_style.get('color', '#111111'))
    else:
        body_size = 9
        body_color = colors.black
    
    # Get author section from config
    author_y = page_height - margin_top - 95 - 70
    if config and 'inputs' in config and 'author_section' in config['inputs']:
        author_config = config['inputs']['author_section']
        analysts = author_config.get('analysts', [])
        legal_entity = author_config.get('legal_entity', {})
        
        # Get typography settings for author section
        if 'typography' in author_config:
            typo = author_config['typography']
            name_font = typo.get('name_font', {})
            role_font = typo.get('role_font', {})
            contact_font = typo.get('contact_font', {})
            
            name_size = name_font.get('size_pt', body_size)
            name_color = hex_to_color(name_font.get('color', '#111111'))
            role_size = role_font.get('size_pt', body_size - 0.5)
            role_color = hex_to_color(role_font.get('color', '#4A4A4A'))
            contact_size = contact_font.get('size_pt', body_size - 1)
            contact_color = hex_to_color(contact_font.get('color', '#7A7A7A'))
        else:
            name_size = body_size
            name_color = body_color
            role_size = body_size - 0.5
            role_color = body_color
            contact_size = body_size - 1
            contact_color = body_color
        
        spacing = author_config.get('spacing', {})
        analyst_block_margin = spacing.get('analyst_block_margin_pt', 4)  # Reduced from 6 to 4
        
        current_y = author_y
        for analyst in analysts:
            # Name - more condensed
            c.setFont(font_name, name_size)
            c.setFillColor(name_color)
            # Truncate if too long to prevent overlap
            name_text = analyst.get('name', '')
            if len(name_text) > 20:
                name_text = name_text[:17] + '...'
            c.drawString(right_frame_x + 4, current_y, name_text)
            current_y -= name_size + 1  # Reduced from 2 to 1
            
            # Role - more condensed
            c.setFont(font_name, role_size)
            c.setFillColor(role_color)
            role_text = analyst.get('role', '')
            if len(role_text) > 25:
                role_text = role_text[:22] + '...'
            c.drawString(right_frame_x + 4, current_y, role_text)
            current_y -= role_size + 1  # Reduced from 2 to 1
            
            # Contact info - more condensed, smaller font
            c.setFont(font_name, contact_size - 0.5)  # Even smaller
            c.setFillColor(contact_color)
            if analyst.get('phone'):
                phone_text = analyst.get('phone', '')
                if len(phone_text) > 25:
                    phone_text = phone_text[:22] + '...'
                c.drawString(right_frame_x + 4, current_y, phone_text)
                current_y -= contact_size  # Reduced spacing
            if analyst.get('email'):
                email_text = analyst.get('email', '')
                if len(email_text) > 25:
                    email_text = email_text[:22] + '...'
                c.drawString(right_frame_x + 4, current_y, email_text)
                current_y -= contact_size  # Reduced spacing
            
            current_y -= analyst_block_margin
        
        # Legal entity if configured
        if author_config.get('show_legal_entity', False) and legal_entity:
            current_y -= 10
            c.setFont(font_name, contact_size)
            c.setFillColor(contact_color)
            if legal_entity.get('name'):
                c.drawString(right_frame_x + 4, current_y, legal_entity.get('name', ''))
                current_y -= contact_size + 2
            if legal_entity.get('address'):
                addr = legal_entity['address']
                address_parts = []
                if addr.get('line1'):
                    address_parts.append(addr['line1'])
                if addr.get('city'):
                    address_parts.append(addr['city'])
                if addr.get('state'):
                    address_parts.append(addr['state'])
                if addr.get('postal_code'):
                    address_parts.append(addr['postal_code'])
                if address_parts:
                    c.drawString(right_frame_x + 4, current_y, ', '.join(address_parts))
    else:
        # Fallback to default
        c.setStrokeColor(body_color)
        c.setFont(font_name, body_size)
        c.drawString(right_frame_x + 4, author_y, "Analyst: FinRpt")
        c.drawString(right_frame_x + 4, author_y - 20, "Copyright: ****")
        c.drawString(right_frame_x + 4, author_y - 40, "Address: ****")
    
    # Use section_titles already defined above (reuse from left frame section)
    company_data_title = section_titles.get('company_data', 'Company Data')
    frame_title4 = draw_frame_title(company_data_title, color1, right_frame_width - 4, font_name, config)
    _1, _2 = frame_title4.wrap(0, 0)
    frame_title4.drawOn(c, right_frame_x + 2, page_height - margin_top - 95 - 170)
    
    # Use table_company_data.png if available, otherwise fall back to generated table
    if os.path.exists(table_company_data_path):
        img = Image(table_company_data_path)
        raw_width = img.imageWidth
        raw_height = img.imageHeight
        img.drawWidth = right_frame_width - 8
        img.drawHeight = img.drawWidth * (raw_height / raw_width)
        img.drawOn(c, right_frame_x + 3, page_height - margin_top - 95 - 270)
    else:
        # Fallback to original table generation (if PNG not available)
        key_data = get_key_data(stock_code, date)
        # Use keys directly (already in English)
        base_data = dict(key_data)
        base_data["Exchange"] = res_data["company_info"].get("stock_exchange", "N/A")
        industry = res_data["company_info"].get("industry_category", "N/A")
        base_data["Industry"] = industry[-11:] if len(industry) > 11 else industry
        base_data = [[k, v] for k, v in base_data.items()]
        base_table = get_base_table(font_name, base_data, config)
        base_table.wrap(0, 0)
        base_table.drawOn(c, right_frame_x + 3, page_height - margin_top - 95 - 270)
    
    # Price Performance Chart
    price_performance_title = section_titles.get('price_performance', 'Price Performance')
    frame_title5 = draw_frame_title(price_performance_title, color1, right_frame_width - 4, font_name, config)
    _1, _2 = frame_title5.wrap(0, 0)
    frame_title5.drawOn(c, right_frame_x + 2, page_height - margin_top - 95 - 300)
    # Use graph_price_performance.png (which may fall back to share_performance.png)
    img = Image(graph_price_performance_path)
    raw_width = img.imageWidth
    raw_height = img.imageHeight
    img.drawWidth = right_frame_width - 8
    img.drawHeight = img.drawWidth * (raw_height / raw_width)
    img.drawOn(c, right_frame_x + 3, page_height - margin_top - 95 - 410)
    
    # PE & EPS Chart
    pe_eps_title = section_titles.get('pe_eps', 'PE & EPS')
    frame_title6 = draw_frame_title(pe_eps_title, color1, right_frame_width - 4, font_name, config)
    frame_title6.wrap(0, 0)
    frame_title6.drawOn(c, right_frame_x + 2, page_height - margin_top - 95 - 435)
    img = Image(pe_eps_performance_image_path)
    raw_width = img.imageWidth
    raw_height = img.imageHeight
    img.drawWidth = right_frame_width - 8
    img.drawHeight = img.drawWidth * (raw_height / raw_width)
    img.drawOn(c, right_frame_x + 3, page_height - margin_top - 95 - 545)
    
    # Revenue Performance Chart
    revenue_title = section_titles.get('revenue', 'Revenue Performance')
    frame_title7 = draw_frame_title(revenue_title, color1, right_frame_width - 4, font_name, config)
    frame_title7.wrap(0, 0)
    frame_title7.drawOn(c, right_frame_x + 2, page_height - margin_top - 95 - 570)
    img = Image(revenue_performance_image_path)
    raw_width = img.imageWidth
    raw_height = img.imageHeight
    img.drawWidth = right_frame_width - 8
    img.drawHeight = img.drawWidth * (raw_height / raw_width)
    img.drawOn(c, right_frame_x + 3, page_height - margin_top - 95 - 680)
    
    # Draw footer if configured
    if config and 'layout' in config and 'footer' in config['layout']:
        footer_config = config['layout']['footer']
        if footer_config.get('show', True):
            # Use built-in ReportLab font with fallback
            footer_font_raw = footer_config.get('font_family', secondary_font)
            footer_font = map_to_builtin_font(footer_font_raw)
            footer_size = footer_config.get('font_size_pt', 7)
            footer_color = hex_to_color(footer_config.get('color', '#7A7A7A'))
            
            provider = config.get('inputs', {}).get('source_report', {}).get('provider', '')
            left_text = footer_config.get('left_text_template', '{provider} Research').format(provider=provider)
            right_text = footer_config.get('right_text_template', '{page_number}').format(page_number='1')
            
            c.setFont(footer_font, footer_size)
            c.setFillColor(footer_color)
            c.drawString(margin_left, margin_bottom - 15, left_text)
            c.drawRightString(page_width - margin_right, margin_bottom - 15, right_text)
    
    c.save()

    
if __name__ == "__main__":
    date = '2024-11-05'
    data_ = pickle.load(open('300750_mini_1027', 'rb'))
    data = pickle.load(open('result.pkl', 'rb'))
    data["analyze_risk"] = json.loads(data["risk_response"])['risks']
    data["company_name"] = data["company_info"]["company_name"]
    data["model_name"] = "gpt-4o"
    data['report_title'] = "业绩增长韧性延续，全年目标完成在望"
    data["analyze_advisor"] = []
    finance_response_json = json.loads(data["finance_write_response"])
    news_response_json = json.loads(data["news_write_response"])
    report_response_json = json.loads(data["report_write_response"])
    trend_response_json = json.loads(data["trend_write_response"])
    data["analyze_advisor"].append({'content': finance_response_json["段落"], 'title': finance_response_json["标题"]})
    data["analyze_advisor"].append({'content': news_response_json["段落"], 'title': news_response_json["标题"]})
    data["analyze_advisor"].append({'content': report_response_json["段落"], 'title': report_response_json["标题"]})
    data['analyze_advisor'].append({'content': trend_response_json["段落"], 'title': trend_response_json["标题"], "rating": trend_response_json["评级"]})
    build_report(data, date) 
    