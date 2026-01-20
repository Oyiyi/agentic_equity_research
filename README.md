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
   - Set up your Financial Modeling Prep (FMP) API key in `config.yaml`
   - Configure OpenAI API key if using OpenAI models

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

```bash
python agentic/run_equity_report.py <TICKER> [COMPANY_NAME]
```

Example:
```bash
python agentic/run_equity_report.py TSLA "Tesla Inc"
```

### Using the Python API

```python
from agentic.equity_report_generator import EquityReportGenerator

generator = EquityReportGenerator(
    ticker="TSLA",
    company_name="Tesla Inc"
)

output_path = generator.generate_report()
print(f"Report saved to: {output_path}")
```

## 📊 Features

- **Multi-Agent Framework**: Specialized agents for different aspects of equity analysis
- **Financial Data Integration**: Automated collection of financial statements, key metrics, and market data
- **News Analysis**: Integration of news sentiment and analysis
- **Financial Forecasting**: Automated financial projections and forecasts
- **Professional Report Generation**: PDF reports with charts, tables, and comprehensive analysis
- **Data Caching**: Efficient caching system to minimize API calls

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
- [LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory) for model fine-tuning
- [verl](https://github.com/volcengine/verl) for reinforcement learning
- [ReportLab](https://www.reportlab.com/) for PDF report generation
- [Financial Modeling Prep API](https://financialmodelingprep.com/) for financial data

Special thanks to these projects for providing the foundation for this work.

## 📚 License

MIT License

## ⚠️ Disclaimer

This project is shared for academic and research purposes under the MIT license. Nothing herein constitutes financial advice, and this is NOT a recommendation to trade real money. Please use common sense and always consult a professional financial advisor before making any trading or investment decisions.
