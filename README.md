# Equity Research Report Generator

A comprehensive system for automated equity research report generation using multi-agent LLM frameworks. This project provides tools for data collection, financial analysis, and professional equity research report generation.

## 🕹️ Environment Setup

1. Create a new virtual environment
```bash
conda create --name equity_research python=3.10
conda activate equity_research
```

2. Install requirement packages
```bash
pip install -r requirements.txt
```

3. Add Python environment variables
```bash
export PYTHONPATH="${PYTHONPATH}:<path_to_this_repo>"
```

4. Configure API keys
   - Create a `.env` file in the project root with your API keys:
     ```bash
     FMP_API_KEY=your_fmp_api_key_here
     OPENAI_API_KEY=your_openai_api_key_here
     ```
   - Optionally configure report settings in `config.yaml`:
     - `ticker`: Stock ticker symbol (e.g., "AAPL")
     - `report_date`: Report date in YYYY-MM-DD format (e.g., "2026-01-13")
     - `industry`: Industry sector for the company

## 🔧 Project Structure

### Agentic Framework (`agentic/`)
Multi-agent system for equity report generation:
- `equity_report_generator.py` - Main report generation orchestrator
- `analyst_agent.py` - Financial analysis agent
- `financial_forecastor_agent.py` - Financial forecasting agent
- `news_collector.py` - News collection and analysis agent
- `fmp_data_puller.py` - Financial data collection from FMP API
- `fmp_graph_generator.py` - Financial charts and tables generation
- `run_equity_report.py` - Main entry point for report generation


### Frontend (`front/`)
Web interface for report generation:
- Flask-based web application
- Interactive report generation interface

## 🚀 Quick Start

### Generate an Equity Research Report

#### Method 1: Using Command Line (Recommended)

The easiest way to generate a report is using the command-line script:

```bash
python agentic/run_equity_report.py <TICKER> [COMPANY_NAME]
```

**Examples:**
```bash
# Generate report for Apple Inc
python agentic/run_equity_report.py AAPL "Apple Inc"

# Generate report for Tesla (company name optional)
python agentic/run_equity_report.py TSLA "Tesla Inc"

# Generate report using ticker from config.yaml
python agentic/run_equity_report.py AAPL
```

**Note:** The script will automatically:
- Read `ticker` and `report_date` from `config.yaml` if available
- Pull financial data from FMP API (with caching)
- Generate AI-powered analysis using OpenAI
- Create professional PDF report with charts and tables
- Save results to `reports/{Company}_{timestamp}/` directory

#### Method 2: Using Python API

```python
from agentic.equity_report_generator import EquityReportGenerator

generator = EquityReportGenerator(
    ticker="AAPL",
    company_name="Apple Inc"
)

output_path = generator.generate_report()
print(f"Report saved to: {output_path}")
```

#### Report Output Structure

After generation, reports are saved in the following structure:
```
reports/
  └── {Company}_{timestamp}/
      ├── figs/                    # Generated charts and tables
      │   ├── graph_price_performance.png
      │   ├── table_company_data.png
      │   ├── table_key_metrics.png
      │   └── ...
      ├── report/                  # PDF report
      │   └── {TICKER}_equity_report.pdf
      └── analysts/                # Analysis results
          ├── analysis_result.json
          ├── analysis_result.pkl
          └── analysis_result.txt
```

#### Example Report

Here's an example of a generated equity research report for Tesla Inc. (TSLA):

**Report Preview (First Page):**

![TSLA Equity Research Report](reports/TSLA_20260119_230955/report/TSLA_equity_report_preview.png)

**Full Report:** [Download TSLA Equity Research Report PDF](reports/TSLA_20260119_230955/report/TSLA_equity_report.pdf)


## 📊 Features

- **Multi-Agent Framework**: Specialized agents for different aspects of equity analysis
- **Financial Data Integration**: Automated collection of financial statements, key metrics, and market data
- **AI-Powered Analysis**: LLM-generated investment analysis with iterative refinement
- **Financial Forecasting**: Automated financial projections and forecasts using AI
- **News Analysis**: Integration of news sentiment and analysis
- **Professional Report Generation**: PDF reports with charts, tables, and comprehensive analysis
- **Data Caching**: Efficient caching system to minimize API calls

## 🔄 Analysis Workflow

The system follows a structured multi-step workflow to generate comprehensive equity research reports:

### 1. Data Collection Phase
```
┌─────────────────────────────────────────────────────────┐
│  FMP Data Puller (fmp_data_puller.py)                  │
│  ├── Check cache database for existing data            │
│  ├── If not cached: Pull from FMP API                  │
│  │   ├── Price Performance (stock vs index)            │
│  │   ├── Company Data (market cap, shares, etc.)       │
│  │   ├── Financial Statements (income, balance, CF)    │
│  │   └── Key Metrics (calculated from statements)      │
│  └── Save to cache database (data/cache.db)            │
└─────────────────────────────────────────────────────────┘
```

### 2. Financial Forecasting Phase
```
┌─────────────────────────────────────────────────────────┐
│  Financial Forecastor Agent                             │
│  ├── Load historical financial data from cache         │
│  ├── Prepare comprehensive prompt with:                │
│  │   ├── Historical metrics (revenue, EBITDA, EPS)     │
│  │   ├── Company information                           │
│  │   └── Price performance context                     │
│  ├── Generate forecasts using OpenAI API               │
│  │   └── Forecast next 2 fiscal years                  │
│  └── Save forecasts back to cache database             │
└─────────────────────────────────────────────────────────┘
```

### 3. Analysis Generation Phase
```
┌─────────────────────────────────────────────────────────┐
│  Analyst Agent (analyst_agent.py)                      │
│  ├── Load all data (metrics, statements, news)         │
│  ├── Format comprehensive prompt with:                 │
│  │   ├── Key financial metrics (actual + forecast)     │
│  │   ├── Company data and market context               │
│  │   ├── Financial statements summary                  │
│  │   └── Recent news articles                          │
│  ├── Multi-round analysis (default: 3 rounds)          │
│  │   ├── Round 1: Initial analysis                     │
│  │   ├── Round 2: Refinement with memory               │
│  │   └── Round 3: Final polished analysis              │
│  ├── Generate:                                          │
│  │   ├── Investment recommendation (OW/NEUT/UW)        │
│  │   ├── 4-paragraph analysis                          │
│  │   ├── Key points (for headline)                     │
│  │   └── Risks and catalysts                           │
│  └── Save analysis results to JSON/PKL/TXT             │
└─────────────────────────────────────────────────────────┘
```

### 4. Visualization Generation Phase
```
┌─────────────────────────────────────────────────────────┐
│  Graph Generator (fmp_graph_generator.py)              │
│  ├── Load data from cache database                     │
│  ├── Generate charts:                                  │
│  │   └── Price Performance (stock vs benchmark)        │
│  └── Generate tables:                                  │
│      ├── Company Data table                            │
│      ├── Key Metrics table                             │
│      ├── Income Statement table                        │
│      ├── Balance Sheet table                           │
│      └── Cash Flow Statement table                     │
└─────────────────────────────────────────────────────────┘
```

### 5. Report Assembly Phase
```
┌─────────────────────────────────────────────────────────┐
│  Report Generator (equity_report_generator.py)         │
│  ├── Load analysis results from Analyst Agent          │
│  ├── Load generated charts and tables                  │
│  ├── Apply branding and styling from config.yaml       │
│  ├── Build PDF using ReportLab:                        │
│  │   ├── Page 1: Company analysis + charts             │
│  │   └── Page 2: Financial statements + metrics        │
│  └── Save final PDF report                             │
└─────────────────────────────────────────────────────────┘
```

### Key Features of the Workflow

- **Intelligent Caching**: First run pulls data from API and caches it. Subsequent runs use cached data, reducing API calls and costs.
- **Iterative Refinement**: Analyst Agent uses multiple rounds of analysis with memory/scratch paper to refine insights.
- **Comprehensive Context**: Each agent has access to all available data (financials, market data, news) for informed analysis.
- **Error Handling**: System gracefully handles missing data and API errors, using cached data when available.

## 🔑 Key Components

### Data Collection
- Financial statements (Income Statement, Balance Sheet, Cash Flow)
- Key financial metrics and ratios
- Price performance data
- Company information and analyst ratings
- News articles and sentiment analysis

### Report Generation
- Executive summary
- Company overview
- Financial analysis
- Risk assessment
- Investment recommendations
- Professional formatting with charts and tables

## 🌹 Acknowledgments

This project uses:
- [ReportLab](https://www.reportlab.com/) for PDF report generation
- [Financial Modeling Prep API](https://financialmodelingprep.com/) for financial data
- [OpenAI API](https://platform.openai.com/) for LLM-powered analysis and forecasting
- [Matplotlib](https://matplotlib.org/) and [Pandas](https://pandas.pydata.org/) for data visualization

Special thanks to these projects for providing the foundation for this work.

## 📚 License

MIT License

## ⚠️ Disclaimer

This project is shared for academic and research purposes under the MIT license. Nothing herein constitutes financial advice, and this is NOT a recommendation to trade real money. Please use common sense and always consult a professional financial advisor before making any trading or investment decisions.
