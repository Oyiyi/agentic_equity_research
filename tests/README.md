# Tests for FinRpt US Stock Support

This directory contains tests for verifying yfinance API integration and US stock support.

## Test Files

### `test_yfinance_api.py`

Tests for yfinance API functionality with US stocks:

1. **Stock Code Detection**: Tests `is_us_stock()` function to correctly identify US vs Chinese stocks
2. **Basic yfinance Fetching**: Tests fetching stock info and historical data from yfinance
3. **Dataer Integration**: Tests `Dataer.get_finacncials_yf()` and routing in `get_finacncials_ak()`
4. **Charting Functions**: Tests chart generation with US stocks:
   - `get_share_performance()` - Share price performance with S&P 500 benchmark
   - `get_pe_eps_performance()` - PE/EPS chart
   - `get_revenue_performance()` - Revenue chart
5. **Environment Variables**: Verifies `YFINANCE_API_TOKEN` can be loaded

## Running Tests

### Prerequisites

Install pytest if not already installed:
```bash
pip install pytest
```

### Run All Tests

```bash
cd /Users/yihan/Documents/GitHub/FinRpt_equityresearch
pytest tests/test_yfinance_api.py -v -s
```

### Run Specific Test Class

```bash
# Test yfinance API only
pytest tests/test_yfinance_api.py::TestYFinanceAPI -v -s

# Test charting functions only
pytest tests/test_yfinance_api.py::TestChartingFunctions -v -s
```

### Run Specific Test

```bash
# Test stock detection
pytest tests/test_yfinance_api.py::TestYFinanceAPI::test_is_us_stock_detection -v -s

# Test chart generation
pytest tests/test_yfinance_api.py::TestChartingFunctions::test_get_share_performance_us_stock -v -s
```

## Environment Setup

Make sure your `.env` file in the project root includes:

```
YFINANCE_API_TOKEN=your_yfinance_api_token_here
```

Note: The token is optional for basic yfinance usage, but may be required for premium features.

## Test Coverage

### US Stock Support
- ✅ Stock code detection (AAPL, MSFT vs 600519.SS)
- ✅ Automatic routing to yfinance for US stocks
- ✅ S&P 500 (SPY) as benchmark instead of CSI300
- ✅ Financial data fetching via yfinance

### Chart Generation
- ✅ Share performance charts with S&P 500 comparison
- ✅ PE/EPS charts (when data available)
- ✅ Revenue performance charts

## Notes

- Tests use real API calls to yfinance, so they require internet connection
- Some tests may take a few seconds to complete due to API calls
- Chart files are created in `tests/temp_figs/` and cleaned up after tests
