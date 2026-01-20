#!/usr/bin/env python
"""
快速运行Equity Report生成器的脚本
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agentic.equity_report_generator import EquityReportGenerator

def main():
    # 默认使用TSLA作为示例
    ticker = sys.argv[1] if len(sys.argv) > 1 else 'TSLA'
    company_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    print("=" * 60)
    print("Equity Research Report Generator")
    print("=" * 60)
    print(f"Ticker: {ticker}")
    if company_name:
        print(f"Company Name: {company_name}")
    print("=" * 60)
    
    # 创建生成器
    generator = EquityReportGenerator(
        ticker=ticker,
        company_name=company_name
    )
    
    # 生成报告
    try:
        output_path = generator.generate_report()
        print("\n" + "=" * 60)
        print("✓ Report generated successfully!")
        print("=" * 60)
        print(f"Output: {output_path}")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
