#!/usr/bin/env python
"""
Script to create a test cache.db with synthetic data for testing report generation.

Usage:
    python create_test_cache_db.py

This will create/overwrite finrpt/source/cache.db with test data.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

# Test data parameters
TEST_STOCK_CODE = '600519.SS'
TEST_DATE = '2024-11-05'
TEST_COMPANY_NAME = '贵州茅台'

def create_test_cache_db():
    """Create cache.db with synthetic test data"""
    
    # Ensure directory exists
    db_dir = Path(__file__).parent / 'finrpt' / 'source'
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / 'cache.db'
    
    # Remove existing database if it exists
    if db_path.exists():
        db_path.unlink()
    
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    
    # ============================================================================
    # Table 1: company_info
    # ============================================================================
    print("Creating company_info table...")
    c.execute('''
    CREATE TABLE IF NOT EXISTS company_info (
        stock_code TEXT PRIMARY KEY,
        company_name TEXT,
        company_full_name TEXT,
        company_name_en TEXT,
        stock_category TEXT,
        industry_category TEXT,
        stock_exchange TEXT,
        industry_cs TEXT,
        general_manager TEXT,
        legal_representative TEXT,
        board_secretary TEXT,
        chairman TEXT,
        securities_representative TEXT,
        independent_directors TEXT,
        website TEXT,
        address TEXT,
        registered_capital TEXT,
        employees_number TEXT,
        management_number TEXT,
        company_profile TEXT,
        business_scope TEXT
    )
    ''')
    
    c.execute('''
    INSERT INTO company_info VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        TEST_STOCK_CODE,                                    # stock_code
        TEST_COMPANY_NAME,                                  # company_name
        '贵州茅台酒股份有限公司',                             # company_full_name
        'Kweichow Moutai Co., Ltd.',                       # company_name_en
        'A股',                                             # stock_category
        '食品饮料',                                         # industry_category
        '上交所',                                           # stock_exchange
        '制造业-酒、饮料和精制茶制造业',                     # industry_cs
        '李静仁',                                          # general_manager
        '丁雄军',                                          # legal_representative
        '刘刚',                                            # board_secretary
        '丁雄军',                                          # chairman
        '刘刚',                                            # securities_representative
        '独立董事A,独立董事B,独立董事C',                    # independent_directors
        'http://www.moutaichina.com',                      # website
        '贵州省仁怀市茅台镇',                                # address
        '12561978000',                                     # registered_capital (元)
        '32000',                                          # employees_number
        '15',                                             # management_number
        '贵州茅台酒股份有限公司是中国白酒行业的龙头企业，主要生产和销售茅台酒系列产品。',  # company_profile
        '白酒生产、销售；包装材料生产、销售；酒店经营管理等。'  # business_scope
    ))
    
    # ============================================================================
    # Table 2: company_report
    # ============================================================================
    print("Creating company_report table...")
    c.execute('''
    CREATE TABLE IF NOT EXISTS company_report (
        report_id TEXT PRIMARY KEY,
        content TEXT,
        stock_code TEXT,
        date TEXT,
        title TEXT,
        core_content TEXT,
        summary TEXT
    )
    ''')
    
    report_id = f'{TEST_STOCK_CODE}_2023_Q4'
    report_content = """第三节 管理层讨论与分析
    
一、公司经营情况回顾
    
报告期内，公司实现营业收入1,321.40亿元，同比增长19.16%；归属于上市公司股东的净利润627.16亿元，同比增长19.16%。公司业绩保持稳健增长态势。

二、主营业务分析
    
1. 主营业务收入
   报告期内，公司主营业务收入主要来自茅台酒及系列酒的销售。其中，茅台酒销售收入继续保持增长，系列酒业务发展良好。

2. 成本费用
   报告期内，公司营业成本为154.28亿元，同比增长15.23%。销售费用、管理费用和研发费用均有所增长，但占营业收入比例保持稳定。

三、财务状况分析
    
1. 资产状况
   报告期末，公司总资产为3,457.12亿元，较期初增长12.35%。其中，货币资金、存货等流动资产占比合理。

2. 盈利能力
   报告期内，公司毛利率为88.33%，净利率为47.45%，盈利能力保持行业领先水平。

四、未来发展展望
    
公司将继续坚持高质量发展理念，加强品牌建设，优化产品结构，提升市场竞争力。预计未来将保持稳健的发展态势。
"""
    
    core_content = """管理层讨论与分析：报告期内公司实现营业收入1321.40亿元，同比增长19.16%；净利润627.16亿元，同比增长19.16%。主营业务收入主要来自茅台酒及系列酒的销售。毛利率88.33%，净利率47.45%。公司将继续加强品牌建设，优化产品结构。"""
    
    summary = """贵州茅台2023年年报显示，公司营业收入1321.40亿元，同比增长19.16%，净利润627.16亿元。主营业务收入来自茅台酒及系列酒销售。毛利率88.33%，盈利能力行业领先。公司将加强品牌建设，优化产品结构，保持稳健发展。"""
    
    c.execute('''
    INSERT INTO company_report VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        report_id,           # report_id
        report_content,      # content
        TEST_STOCK_CODE,     # stock_code
        '2023-12-31',        # date
        '贵州茅台2023年年度报告',  # title
        core_content,        # core_content
        summary              # summary
    ))
    
    # ============================================================================
    # Table 3: news
    # ============================================================================
    print("Creating news table...")
    c.execute('''
    CREATE TABLE IF NOT EXISTS news (
        news_url TEXT PRIMARY KEY,
        read_num TEXT,
        reply_num TEXT,
        news_title TEXT,
        news_author TEXT,
        news_time TEXT,
        stock_code TEXT,
        news_content TEXT,
        news_summary TEXT,
        dec_response TEXT,
        news_decision TEXT
    )
    ''')
    
    # Insert 5 test news articles
    test_news = [
        {
            'url': 'http://finance.sina.com.cn/stock/relnews/cn/2024-10-28/doc-test1.shtml',
            'title': '贵州茅台第三季度业绩超预期 净利润同比增长18%',
            'content': '贵州茅台发布2024年第三季度报告，公司实现营业收入430.5亿元，同比增长17.8%；归属于上市公司股东的净利润205.3亿元，同比增长18.2%。业绩增长主要得益于产品结构优化和市场需求增长。公司表示将继续推进数字化转型，提升市场竞争力。',
            'summary': '贵州茅台2024年第三季度营业收入430.5亿元，净利润205.3亿元，同比增长18.2%，业绩超预期。',
            'dec_response': '该新闻涉及公司财务报告和业绩增长，属于重大财务事项，可能影响公司未来股票走势。[[[是]]]',
            'decision': '是'
        },
        {
            'url': 'http://finance.sina.com.cn/stock/relnews/cn/2024-11-01/doc-test2.shtml',
            'title': '茅台酒价格稳步上涨 市场需求持续旺盛',
            'content': '近期，茅台酒市场价格呈现稳步上涨趋势，53度飞天茅台终端价格较年初上涨约5%。市场分析认为，茅台酒价格上涨主要受供需关系影响，市场需求持续旺盛。有经销商表示，随着消费升级和节日消费需求增加，茅台酒销售情况良好。',
            'summary': '茅台酒市场价格稳步上涨约5%，市场需求旺盛，销售情况良好。',
            'dec_response': '该新闻反映市场需求和产品价格变化，属于市场动态，可能影响公司业绩和股票表现。[[[是]]]',
            'decision': '是'
        },
        {
            'url': 'http://finance.sina.com.cn/stock/relnews/cn/2024-11-02/doc-test3.shtml',
            'title': '贵州茅台与多家电商平台签署战略合作协议',
            'content': '贵州茅台与天猫、京东等主要电商平台签署战略合作协议，共同推进数字化转型和线上销售渠道建设。根据协议，双方将在产品销售、品牌推广、大数据分析等方面展开深度合作。此举有助于公司扩大销售渠道，提升品牌影响力。',
            'summary': '贵州茅台与电商平台签署战略合作协议，推进数字化转型和线上销售渠道建设。',
            'dec_response': '该新闻涉及公司市场战略和销售渠道拓展，属于公司运营重大事项，可能影响未来业绩。[[[是]]]',
            'decision': '是'
        },
        {
            'url': 'http://finance.sina.com.cn/stock/relnews/cn/2024-11-03/doc-test4.shtml',
            'title': '白酒行业整体复苏 高端白酒市场表现亮眼',
            'content': '今年以来，白酒行业整体呈现复苏态势，高端白酒市场表现尤为亮眼。行业数据显示，前三季度高端白酒市场规模同比增长12%，贵州茅台、五粮液等龙头企业市场份额进一步提升。专家分析认为，消费升级和商务需求恢复是主要推动因素。',
            'summary': '白酒行业复苏，高端白酒市场规模增长12%，茅台等龙头企业市场份额提升。',
            'dec_response': '该新闻反映行业整体趋势和市场竞争环境，属于行业动态，可能影响公司在行业中的地位和业绩。[[[是]]]',
            'decision': '是'
        },
        {
            'url': 'http://finance.sina.com.cn/stock/relnews/cn/2024-11-04/doc-test5.shtml',
            'title': '贵州茅台发布新产品 拓展年轻消费群体',
            'content': '贵州茅台近日发布面向年轻消费群体的新产品系列，包括低度酒和果味酒等创新产品。公司表示，此举旨在拓展消费群体，适应市场变化。新产品在包装设计和营销策略上更加年轻化，希望通过创新产品吸引更多年轻消费者。',
            'summary': '贵州茅台发布面向年轻消费群体的新产品系列，拓展消费群体，适应市场变化。',
            'dec_response': '该新闻涉及公司产品创新和市场拓展战略，属于公司业务发展重大事项，可能影响未来市场表现。[[[是]]]',
            'decision': '是'
        }
    ]
    
    for i, news_item in enumerate(test_news):
        news_date = (datetime.strptime(TEST_DATE, '%Y-%m-%d') - timedelta(days=7-i)).strftime('%Y-%m-%d')
        c.execute('''
        INSERT INTO news VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            news_item['url'],                    # news_url
            '10000',                            # read_num
            '500',                              # reply_num
            news_item['title'],                 # news_title
            'sina',                             # news_author
            news_date,                          # news_time
            TEST_STOCK_CODE,                    # stock_code
            news_item['content'],               # news_content
            news_item['summary'],               # news_summary
            news_item['dec_response'],          # dec_response
            news_item['decision']               # news_decision
        ))
    
    # ============================================================================
    # Table 4: announcement
    # ============================================================================
    print("Creating announcement table...")
    c.execute('''
    CREATE TABLE IF NOT EXISTS announcement (
        url TEXT PRIMARY KEY,
        date TEXT,
        title TEXT,
        content TEXT,
        stock_code TEXT
    )
    ''')
    
    # Insert a test announcement
    announcement_date = (datetime.strptime(TEST_DATE, '%Y-%m-%d') - timedelta(days=10)).strftime('%Y-%m-%d')
    c.execute('''
    INSERT INTO announcement VALUES (?, ?, ?, ?, ?)
    ''', (
        'http://www.sse.com.cn/disclosure/bond/announcement/corporate/600519_20241026_1.htm',  # url
        announcement_date,                                                                      # date
        '贵州茅台关于第三季度业绩报告的公告',                                                  # title
        '本公司及董事会全体成员保证公告内容的真实、准确和完整，对公告的虚假记载、误导性陈述或者重大遗漏负连带责任。\n\n贵州茅台酒股份有限公司2024年第三季度报告已于2024年10月26日在中国证券报、上海证券报等媒体披露。',  # content
        TEST_STOCK_CODE                                                                         # stock_code
    ))
    
    conn.commit()
    conn.close()
    
    print(f"\n✓ Test cache.db created successfully at: {db_path}")
    print(f"  - Stock code: {TEST_STOCK_CODE}")
    print(f"  - Test date: {TEST_DATE}")
    print(f"  - Company: {TEST_COMPANY_NAME}")
    print(f"\nYou can now run: python finrpt/module/FinRpt.py")
    print(f"  It will use the cached data instead of making API calls.\n")

if __name__ == '__main__':
    create_test_cache_db()
