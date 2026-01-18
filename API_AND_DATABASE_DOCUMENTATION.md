# FinRpt API Calls and Database Structure Documentation

This document lists all external APIs called during report generation and the database structure.

---

## Part 1: External APIs Called During Report Generation

When you run `finrpt.run(date, stock_code)`, the following APIs are called in order to gather data:

### 1. Company Information APIs

#### 1.1 EastMoney - Company Basic Information
- **Endpoint**: `https://datacenter.eastmoney.com/securities/api/data/v1/get`
- **Method**: GET
- **Function**: `get_company_info()` in `Dataer.py`
- **Parameters**:
  - `reportName`: `RPT_F10_BASIC_ORGINFO`
  - `columns`: `ALL`
  - `filter`: `(SECUCODE="STOCK_CODE")`
  - `pageNumber`: `1`
  - `pageSize`: `1`
- **Returns**: Company profile, management info, address, registered capital, etc.
- **Called when**: Company info not found in database cache

**Example URL**:
```
https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_F10_BASIC_ORGINFO&columns=ALL&filter=(SECUCODE%3D%22600519.SH%22)&pageNumber=1&pageSize=1&source=HSF10&client=PC
```

---

### 2. Company Reports APIs

#### 2.1 EastMoney - Announcement List
- **Endpoint**: `https://np-anotice-stock.eastmoney.com/api/security/ann`
- **Method**: GET
- **Function**: `get_company_report_em()` in `Dataer.py`
- **Parameters**:
  - `ann_type`: `A`
  - `stock_list`: `{6-digit stock code}`
  - `page_index`: `1-10`
  - `page_size`: `100`
- **Purpose**: Get list of annual/semi-annual reports
- **Returns**: List of reports with `art_code` identifiers

**Example URL**:
```
https://np-anotice-stock.eastmoney.com/api/security/ann?ann_type=A&stock_list=600519&page_index=1&page_size=100
```

#### 2.2 EastMoney - Report Content (Paginated)
- **Endpoint**: `https://np-cnotice-stock.eastmoney.com/api/content/ann`
- **Method**: GET
- **Function**: `_get_report_content()` in `Dataer.py`
- **Parameters**:
  - `art_code`: Article code from announcement list
  - `client_source`: `web`
  - `page_index`: `1` to `page_size` (for multi-page reports)
- **Purpose**: Fetch full content of annual/semi-annual reports
- **Returns**: HTML/text content of report pages

**Example URLs**:
```
https://np-cnotice-stock.eastmoney.com/api/content/ann?art_code={art_code}&client_source=web
https://np-cnotice-stock.eastmoney.com/api/content/ann?art_code={art_code}&client_source=web&page_index={page_index}
```

#### 2.3 Sina Finance - Quarterly/Annual Reports (Alternative)
- **Endpoints**:
  - Q1: `https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_BulletinYi/stockid/{stock_code}/page_type/yjdbg.phtml`
  - Q2: `https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_BulletinZhong/stockid/{stock_code}/page_type/zqbg.phtml`
  - Q3: `https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_BulletinSan/stockid/{stock_code}/page_type/sjdbg.phtml`
  - Q4: `https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_Bulletin/stockid/{stock_code}/page_type/ndbg.phtml`
- **Method**: GET
- **Function**: `get_company_report()` in `Dataer.py` (alternative method)
- **Purpose**: Fetch quarterly and annual reports from Sina Finance
- **Returns**: HTML pages with report links and content

**Example URLs**:
```
https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_Bulletin/stockid/600519/page_type/ndbg.phtml
```

---

### 3. News APIs

#### 3.1 Sina Finance - Stock News
- **Endpoint**: `https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllNewsStock.php`
- **Method**: GET
- **Function**: `get_company_news_sina()` in `Dataer.py`
- **Parameters**:
  - `symbol`: `{sh/sz}{6-digit stock code}` (e.g., `sh600519`)
  - `Page`: `1-50`
- **Purpose**: Get news articles related to the stock
- **Returns**: HTML page with news list and links

**Example URL**:
```
https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllNewsStock.php?symbol=sh600519&Page=1
```

#### 3.2 Sina Finance - Individual News Article
- **Endpoint**: Various (news article URLs from the list)
- **Method**: GET
- **Function**: `_get_news_from_url()` in `Dataer.py`
- **Purpose**: Fetch full content of individual news articles
- **Returns**: Article text content

#### 3.3 EastMoney Guba - Stock Forum News
- **Endpoint**: `https://guba.eastmoney.com/list,{stock_code},1,f_{page}.html`
- **Method**: GET
- **Function**: `get_company_news()` in `Dataer.py` (alternative method)
- **Parameters**:
  - `{stock_code}`: 6-digit stock code
  - `{page}`: Page number (1-100)
- **Purpose**: Get news from EastMoney stock forum
- **Returns**: HTML page with news threads

**Example URL**:
```
https://guba.eastmoney.com/list,600519,1,f_1.html
```

---

### 4. Financial Data APIs (via akshare Library)

#### 4.1 Akshare - Stock Basic Information
- **Function**: `ak.stock_individual_info_em(symbol={stock_code})`
- **Called in**: `get_finacncials_ak()` in `Dataer.py`
- **Purpose**: Get stock basic information (PE ratio, market cap, etc.)

#### 4.2 Akshare - Historical Stock Price Data
- **Function**: `ak.stock_zh_a_hist_tx(symbol={stock_code}, start_date={date}, end_date={date})`
- **Called in**: `get_finacncials_ak()` in `Dataer.py`
- **Purpose**: Get historical stock price data (OHLCV)
- **Example**: `ak.stock_zh_a_hist_tx(symbol="sh600519", start_date="20241001", end_date="20241105")`

#### 4.3 Akshare - CSI300 Index Data
- **Function**: `ak.stock_zh_a_hist_tx(symbol="sh000300", start_date={date}, end_date={date})`
- **Called in**: `get_finacncials_ak()` in `Dataer.py`
- **Purpose**: Get CSI300 index historical data for comparison

#### 4.4 Akshare - Financial Statements
- **Functions**:
  - `ak.stock_financial_abstract_ths()` - Financial abstract
  - Multiple other financial statement APIs
- **Called in**: `get_finacncials_ak()` in `Dataer.py`
- **Purpose**: Get income statement, balance sheet, cash flow data

---

### 5. Company Announcements APIs

#### 5.1 Sina Finance - All Announcements
- **Endpoint**: `https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletin.php`
- **Method**: GET
- **Function**: `get_company_announcement()` in `Dataer.py`
- **Parameters**:
  - `stockid`: `{6-digit stock code}`
  - `Page`: `1-100`
- **Purpose**: Get list of company announcements
- **Returns**: HTML page with announcement list

**Example URL**:
```
https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletin.php?stockid=600519&Page=1
```

#### 5.2 Sina Finance - Individual Announcement
- **Endpoint**: Various (announcement URLs from the list)
- **Method**: GET
- **Function**: `_get_announcement_from_url()` in `Dataer.py`
- **Purpose**: Fetch full content of individual announcements

---

### 6. LLM API (OpenAI)

#### 6.1 OpenAI API - News Processing
- **Endpoint**: OpenAI Chat Completions API
- **Function**: `OpenAIModel.simple_prompt()` in `OpenAI.py`
- **Purpose**: 
  - Summarize news articles
  - Decide if news is relevant to stock price movement
- **Called in**: `get_company_news_sina()` for each news article

#### 6.2 OpenAI API - Report Processing
- **Endpoint**: OpenAI Chat Completions API
- **Function**: `OpenAIModel.simple_prompt()` in `OpenAI.py`
- **Purpose**: Summarize and reformat company reports for better LLM comprehension
- **Called in**: `get_company_report_em()` after fetching report content

---

## API Call Order During Report Generation

When `finrpt.run(date='2024-11-05', stock_code='600519.SS')` is executed:

1. **Company Info** → EastMoney API (if not cached)
2. **Financial Data** → Akshare library (always called, not cached in DB)
3. **News** → Sina Finance API (if not cached)
   - Each news article processed by OpenAI API (summary + relevance decision)
4. **Company Reports** → EastMoney API (if not cached)
   - Report content processed by OpenAI API (summary)
5. **Trend Data** → SQLite database lookup (if exists)

---

## Part 2: Database Structure

The `cache.db` SQLite database is located at: `finrpt/source/cache.db`

### Table 1: `company_info`

Stores basic company information retrieved from EastMoney.

| Column | Type | Primary Key | Description |
|--------|------|-------------|-------------|
| `stock_code` | TEXT | Yes | Stock code (e.g., "600519.SS") |
| `company_name` | TEXT | No | Company abbreviated name |
| `company_full_name` | TEXT | No | Full company name |
| `company_name_en` | TEXT | No | English company name |
| `stock_category` | TEXT | No | Stock category |
| `industry_category` | TEXT | No | Industry classification |
| `stock_exchange` | TEXT | No | Exchange (SH/SZ) |
| `industry_cs` | TEXT | No | CSRC industry classification |
| `general_manager` | TEXT | No | General manager name |
| `legal_representative` | TEXT | No | Legal representative |
| `board_secretary` | TEXT | No | Board secretary |
| `chairman` | TEXT | No | Chairman name |
| `securities_representative` | TEXT | No | Securities representative |
| `independent_directors` | TEXT | No | Independent directors |
| `website` | TEXT | No | Company website |
| `address` | TEXT | No | Company address |
| `registered_capital` | TEXT | No | Registered capital |
| `employees_number` | TEXT | No | Number of employees |
| `management_number` | TEXT | No | Management team size |
| `company_profile` | TEXT | No | Company profile/description |
| `business_scope` | TEXT | No | Business scope |

**Populated by**: `get_company_info()` → EastMoney API → `company_info_table_insert_em()`

---

### Table 2: `company_report`

Stores annual and semi-annual company reports.

| Column | Type | Primary Key | Description |
|--------|------|-------------|-------------|
| `report_id` | TEXT | Yes | Report ID (e.g., "600519.SS_2023_Q4") |
| `content` | TEXT | No | Full report content (HTML/text) |
| `stock_code` | TEXT | No | Stock code |
| `date` | TEXT | No | Report date |
| `title` | TEXT | No | Report title |
| `core_content` | TEXT | No | Processed core content (from post_process_report) |
| `summary` | TEXT | No | LLM-generated summary of the report |

**Populated by**: `get_company_report_em()` → EastMoney API → `company_report_table_insert()`

---

### Table 3: `news`

Stores news articles with LLM-generated summaries and relevance decisions.

| Column | Type | Primary Key | Description |
|--------|------|-------------|-------------|
| `news_url` | TEXT | Yes | URL of the news article |
| `read_num` | TEXT | No | Number of reads |
| `reply_num` | TEXT | No | Number of replies (for forum posts) |
| `news_title` | TEXT | No | News article title |
| `news_author` | TEXT | No | Author name |
| `news_time` | TEXT | No | Publication time |
| `stock_code` | TEXT | No | Related stock code |
| `news_content` | TEXT | No | Full news content |
| `news_summary` | TEXT | No | LLM-generated summary (max 200 chars) |
| `dec_response` | TEXT | No | Full LLM decision response |
| `news_decision` | TEXT | No | Decision: "是" (Yes) or "否" (No) - whether news affects stock |

**Populated by**: `get_company_news_sina()` → Sina Finance API + OpenAI API → `company_news_table_insert()`

**Note**: Only news with `news_decision = "是"` is used in report generation.

---

### Table 4: `announcement`

Stores company announcements and notices.

| Column | Type | Primary Key | Description |
|--------|------|-------------|-------------|
| `url` | TEXT | Yes | Announcement URL |
| `date` | TEXT | No | Announcement date |
| `title` | TEXT | No | Announcement title |
| `content` | TEXT | No | Full announcement content |
| `stock_code` | TEXT | No | Related stock code |

**Populated by**: `get_company_announcement()` → Sina Finance API → `announcement_table_insert()`

---

## Database Initialization

The database is automatically initialized when `Dataer` is instantiated:

```python
# In finrpt/source/Dataer.py
def _init_db(self):
    company_info_table_init(self.database_name)
    company_report_table_init(self.database_name)
    announcement_table_init(self.database_name)
    company_news_table_init(self.database_name)
```

All tables are created with `CREATE TABLE IF NOT EXISTS`, so initialization is idempotent.

---

## Cache Strategy

The system uses a **cache-first** strategy:

1. **Check database first**: Query database for existing data
2. **If found**: Return cached data (no API call)
3. **If not found**: 
   - Fetch from API
   - Store in database
   - Return fetched data

This reduces API calls and speeds up subsequent report generations for the same stocks/dates.

---

## Notes

- **Financial data** (from akshare) is **NOT cached** in the database and is fetched fresh each time
- **OpenAI API calls** are made for each news article and report to generate summaries/decisions (not cached)
- The database file is created automatically at: `finrpt/source/cache.db`
- Database directory is created automatically if it doesn't exist

