#!/usr/bin/env python
"""
Regenerate report from existing folder.

Usage:
    python agentic/regenerate_report.py "reports/Tesla Inc_20260119_195917"
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agentic.equity_report_generator import EquityReportGenerator

def main():
    if len(sys.argv) < 2:
        print("Usage: python agentic/regenerate_report.py <folder_path>")
        print("Example: python agentic/regenerate_report.py 'reports/Tesla Inc_20260119_195917'")
        sys.exit(1)
    
    folder_path = sys.argv[1]
    
    # Extract ticker and company name from folder path if possible
    folder_name = Path(folder_path).name
    parts = folder_name.split('_')
    if len(parts) >= 1:
        company_name = parts[0]
        # Try to get ticker from analysis result
        ticker = "TSLA"  # Default, will try to load from analysis result
    else:
        company_name = "Unknown"
        ticker = "UNKNOWN"
    
    print("=" * 60)
    print("Regenerating Equity Research Report")
    print("=" * 60)
    print(f"Folder: {folder_path}")
    print(f"Company: {company_name}")
    print("=" * 60)
    
    # Create generator
    generator = EquityReportGenerator(
        ticker=ticker,
        company_name=company_name
    )
    
    # Try to load ticker from analysis result
    analysis_json_path = Path(folder_path) / "analysts" / "analysis_result.json"
    if analysis_json_path.exists():
        import json
        with open(analysis_json_path, 'r', encoding='utf-8') as f:
            analysis_result = json.load(f)
            if 'ticker' in analysis_result:
                generator.ticker = analysis_result['ticker']
                print(f"Loaded ticker from analysis: {generator.ticker}")
    
    # Regenerate report
    try:
        output_path = generator.regenerate_report_from_folder(folder_path)
        print("\n" + "=" * 60)
        print("✓ Report regenerated successfully!")
        print("=" * 60)
        print(f"Output: {output_path}")
    except Exception as e:
        print(f"\n✗ Error regenerating report: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
