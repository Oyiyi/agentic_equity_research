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


FINE2C = {
    'Tax Effect Of Unusual Items': '异常项目的税收影响',
    'Tax Rate For Calcs': '计算用税率',
    'Normalized EBITDA': '标准化息税折旧摊销前利润',
    'Total Unusual Items': '总异常项目',
    'Total Unusual Items Excluding Goodwill': '不含商誉的总异常项目',
    'Net Income From Continuing Operation Net Minority Interest': '持续经营净收入（扣除少数股东权益）',
    'Reconciled Cost Of Revenue': '调整后的收入成本',
    'EBITDA': '息税折旧摊销前利润',
    'EBIT': '息税前利润',
    'Net Interest Income': '净利息收入',
    'Interest Expense': '利息支出',
    'Interest Income': '利息收入',
    'Normalized Income': '标准化收入',
    'Net Income From Continuing And Discontinued Operation': '持续和非持续经营净收入',
    'Total Expenses': '总费用',
    'Total Operating Income As Reported': '报告的总营业收入',
    'Diluted Average Shares': '稀释平均股数',
    'Basic Average Shares': '基本平均股数',
    'Diluted EPS': '稀释每股收益',
    'Basic EPS': '基本每股收益',
    'Net Income Common Stockholders': '普通股股东净收入',
    'Otherunder Preferred Stock Dividend': '优先股股息下的其他',
    'Net Income': '净收入',
    'Minority Interests': '少数股东权益',
    'Net Income Including Noncontrolling Interests': '包括非控股权益的净收入',
    'Net Income Continuous Operations': '持续经营净收入',
    'Tax Provision': '税项准备',
    'Pretax Income': '税前收入',
    'Other Non Operating Income Expenses': '其他非经营性收入费用',
    'Special Income Charges': '特殊收入费用',
    'Other Special Charges': '其他特殊费用',
    'Write Off': '核销',
    'Net Non Operating Interest Income Expense': '净非经营性利息收入费用',
    'Total Other Finance Cost': '其他财务费用总计',
    'Interest Expense Non Operating': '非经营性利息支出',
    'Interest Income Non Operating': '非经营性利息收入',
    'Operating Income': '营业收入',
    'Operating Expense': '营业费用',
    'Other Operating Expenses': '其他营业费用',
    'Research And Development': '研发费用',
    'Selling General And Administration': '销售、一般及行政费用',
    'Selling And Marketing Expense': '销售和营销费用',
    'General And Administrative Expense': '一般及行政费用',
    'Gross Profit': '毛利润',
    'Cost Of Revenue': '收入成本',
    'Total Revenue': '总收入',
    'Operating Revenue': '营业收入'
}

TARGETMAP = {
    'Total Revenue': '总收入(百万元)',
    'Net Income': '净收入(百万元)',
    'EBITDA': '息税前利润(百万元)',
    'Gross Profit': '毛利润(百万元)',
    'Operating Income': '营业收入(百万元)',
    'Net Income From Continuing Operation Net Minority Interest': '持续经营净收入(百万元)',
    'Operating Expense': '营业费用(百万元)',
    'Pretax Income': '税前收入(百万元)',
    'Tax Provision': '税项准备(百万元)',
    'EBIT': '息税前利润(百万元)',
    'Cost Of Revenue': '收入成本(百万元)',
    'Total Operating Income As Reported': '报告的总营业收入(百万元)',
    'Net Income Including Noncontrolling Interests': '包括非控股权益的净收入(百万元)'
}

BASE_key_mapping = {
    '6m avg daily vol (CNYmn)': '日均成交量(百万元)',
    'Closing Price (CNY)': '收盘价(元)',
    '52 Week Price Range (CNY)': '52周价格范围(元)'
}


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


def get_font_name(config, font_key='primary_family'):
    """Get font name from config with fallback"""
    if not config or 'typography' not in config:
        return 'Helvetica'
    
    typo = config['typography']
    if font_key in typo:
        font_info = typo[font_key]
        if isinstance(font_info, dict) and 'name' in font_info:
            return font_info['name']
        elif isinstance(font_info, str):
            return font_info
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
        
        custom_style = ParagraphStyle(
            'CustomStyle',
            parent=styles['Normal'],
            fontName=font_name,  
            fontSize=font_size,
            leading=font_size * line_height,
            spaceAfter=12,
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
        header_font = header_style.get('font_family', font_name)
        header_size = header_style.get('font_size_pt', 12)
        header_weight = header_style.get('font_weight', 700)
        text_color = hex_to_color(header_style.get('text_color', '#FFFFFF'))
    else:
        header_font = font_name
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
        header_font = header_style.get('font_family', font_name)
        header_size = header_style.get('font_size_pt', 8)
        
        body_font = body_style.get('font_family', font_name)
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
    
    figs_path = os.path.join(save_path, "figs")
    if not os.path.exists(figs_path):
        os.mkdir(figs_path)
    get_share_performance(res_data, res_data['stock_code'], date, save_path=figs_path)
    get_pe_eps_performance(res_data, res_data['stock_code'], date, save_path=figs_path)
    get_revenue_performance(res_data, res_data['stock_code'], date, save_path=figs_path)
    share_performance_image_path = os.path.join(figs_path, "share_performance.png")
    pe_eps_performance_image_path = os.path.join(figs_path, "pe_eps.png")
    revenue_performance_image_path = os.path.join(figs_path, "revenue_performance.png")
    
    company_name = res_data['company_name']
    stock_code = res_data['stock_code']
    
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
        os.path.join(figs_path, "logo.png"),
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
            header_font = header_config.get('font_family', secondary_font)
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

    title = company_name + ":" + res_data['report_title'] if \
        company_name not in res_data['report_title'] else res_data['report_title']
    
    # Get title style from config
    if config and 'components' in config and 'title_block' in config['components']:
        title_config = config['components']['title_block']['title_font']
        title_font = title_config.get('family', font_name)
        title_size = title_config.get('size_pt', 24)
        title_color = hex_to_color(title_config.get('color', primary_color_hex))
    elif config and 'typography' in config and 'scale' in config['typography']:
        h1_style = config['typography']['scale'].get('h1', {})
        title_font = h1_style.get('font_family', font_name)
        title_size = h1_style.get('font_size_pt', 24)
        title_color = hex_to_color(h1_style.get('color', '#111111'))
    else:
        title_font = font_name
        title_size = 17
        title_color = color1
    
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
    
    frame_title1 = draw_frame_title("核心观点", color1, left_frame_width - 8, font_name, config)
    frame_left_list.append(frame_title1)
    frame_left_list.append(Spacer(1, 4))
    
    # Try to find icon path
    icon_paths = [
        os.path.join(figs_path, "icon.png"),
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
    
    for sub_advisor in res_data["analyze_advisor"]:
        paragraph_text = f'<font color="{accent_color_hex}"><b>{sub_advisor["title"]}：</b></font>{sub_advisor["content"]}'
        try:
            paragraph_advisor = BulletParagraph(icon_path, paragraph_text, font_name, config)
        except:
            # Fallback if icon not found
            paragraph_advisor = Paragraph(paragraph_text.replace(f'<font color="{accent_color_hex}"><b>', '<b>').replace('</b></font>', '</b>'), 
                                         ParagraphStyle(name='Custom', parent=styles['Normal'], fontName=font_name))
        frame_left_list.append(paragraph_advisor)
        frame_left_list.append(Spacer(1, 4))
        
    risk_assessment = ""
    for idx, risk in enumerate(res_data["analyze_risk"]):
        risk_assessment += "(" + str(idx + 1) + ")" + risk + ";"
    paragraph_text = f'<font color="{accent_color_hex}"><b>风险评估：</b></font>{risk_assessment}'
    try:
        paragraph_advisor = BulletParagraph(icon_path, paragraph_text, font_name, config)
    except:
        paragraph_advisor = Paragraph(paragraph_text.replace(f'<font color="{accent_color_hex}"><b>', '<b>').replace('</b></font>', '</b>'), 
                                     ParagraphStyle(name='Custom', parent=styles['Normal'], fontName=font_name))
    frame_left_list.append(paragraph_advisor)
    frame_left_list.append(Spacer(1, 4))
        
    frame_title2 = draw_frame_title("财务数据", color1, left_frame_width - 8, font_name, config)
    frame_left_list.append(frame_title2)
    frame_left_list.append(Spacer(1, 5))
    df = res_data["financials"]['stock_income']
    
    # for akshare stock_income
    df['日期'] = df['日期'].apply(lambda x: x[:-4] + '-' + x[4:6] + '-' + x[-2:])
    df.set_index('日期', inplace=True)
    df = df.head(4)
    df = df.transpose()
    df.reset_index(inplace=True)
    df.rename(columns={'index': ''}, inplace=True)
    
    table_data = []
    table_data += [df.columns.to_list()] + df.values.tolist()
    financias_table = get_financias_table(font_name, table_data, config)
    frame_left_list.append(financias_table)
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
    
    frame_title3 = draw_frame_title("作者", color1, right_frame_width - 4, font_name, config)
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
    
    c.setStrokeColor(body_color)
    c.setFont(font_name, body_size)
    height_1 = page_height - margin_top - 95 - 70
    c.drawString(right_frame_x + 4, height_1, "分析师: FinRpt")
    c.drawString(right_frame_x + 4, height_1 - 20, "版权: ****")
    c.drawString(right_frame_x + 4, height_1 - 40, "地址: ****")
    
    frame_title4 = draw_frame_title("基本状况", color1, right_frame_width - 4, font_name, config)
    _1, _2 = frame_title4.wrap(0, 0)
    frame_title4.drawOn(c, right_frame_x + 2, page_height - margin_top - 95 - 170)
    
    key_data = get_key_data(stock_code, date)
    base_data = {BASE_key_mapping[key]: value for key, value in key_data.items()}
    base_data["交易所"] = res_data["company_info"]["stock_exchange"]
    base_data["行业"] = res_data["company_info"]["industry_category"][-11:]
    base_data = [[k, v] for k, v in base_data.items()]
    base_table = get_base_table(font_name, base_data, config)
    base_table.wrap(0, 0)
    base_table.drawOn(c, right_frame_x + 3, page_height - margin_top - 95 - 270)
    
    frame_title5 = draw_frame_title("股市与市场走势对比", color1, right_frame_width - 4, font_name, config)
    _1, _2 = frame_title5.wrap(0, 0)
    frame_title5.drawOn(c, right_frame_x + 2, page_height - margin_top - 95 - 300)
    img = Image(share_performance_image_path)
    raw_width = img.imageWidth
    raw_height = img.imageHeight
    img.drawWidth = right_frame_width - 8
    img.drawHeight = img.drawWidth * (raw_height / raw_width)
    img.drawOn(c, right_frame_x + 3, page_height - margin_top - 95 - 410)
    
    frame_title6 = draw_frame_title("PE & EPS", color1, right_frame_width - 4, font_name, config)
    frame_title6.wrap(0, 0)
    frame_title6.drawOn(c, right_frame_x + 2, page_height - margin_top - 95 - 435)
    img = Image(pe_eps_performance_image_path)
    raw_width = img.imageWidth
    raw_height = img.imageHeight
    img.drawWidth = right_frame_width - 8
    img.drawHeight = img.drawWidth * (raw_height / raw_width)
    img.drawOn(c, right_frame_x + 3, page_height - margin_top - 95 - 545)
    
    frame_title6 = draw_frame_title("单季营业收入及增速", color1, right_frame_width - 4, font_name, config)
    frame_title6.wrap(0, 0)
    frame_title6.drawOn(c, right_frame_x + 2, page_height - margin_top - 95 - 570)
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
            footer_font = footer_config.get('font_family', secondary_font)
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
    