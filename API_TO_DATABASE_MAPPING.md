# API to Database Field Mapping Guide

This document shows where API response fields are mapped to database columns.

---

## Overview

The mapping happens in two steps:

1. **API Response → Data Dictionary** (`finrpt/source/Dataer.py`)
   - Parse API responses into Python dictionaries
   - Extract and transform data from API JSON/HTML responses

2. **Data Dictionary → Database** (`finrpt/source/database_insert.py`)
   - Map dictionary keys to database column names
   - Insert into SQLite tables

---

## 1. Company Info Table

### API Source
**EastMoney API**: `https://datacenter.eastmoney.com/securities/api/data/v1/get`

### Step 1: API Response → Dictionary (Dataer.py)

**Location**: `finrpt/source/Dataer.py`, lines 113-117

```python
response = self._request_get(url)
data = response.json()['result']['data'][0]  # Extract first item from API response
company_info_table_insert_em(db=self.database_name, data=data, stock_code=stock_code_ori)
```

The API returns JSON with fields like: `SECURITY_NAME_ABBR`, `ORG_NAME`, `ORG_NAME_EN`, etc.

### Step 2: Dictionary → Database (database_insert.py)

**Location**: `finrpt/source/database_insert.py`, lines 4-46

**Mapping Table**:

| Database Column | API Response Field (from `data.get()`) |
|----------------|----------------------------------------|
| `stock_code` | `stock_code` (parameter, not from API) |
| `company_name` | `'SECURITY_NAME_ABBR'` |
| `company_full_name` | `'ORG_NAME'` |
| `company_name_en` | `'ORG_NAME_EN'` |
| `stock_category` | `'SECURITY_TYPE'` |
| `industry_category` | `'EM2016'` |
| `stock_exchange` | `'TRADE_MARKET'` |
| `industry_cs` | `'INDUSTRYCSRC1'` |
| `general_manager` | `'PRESIDENT'` |
| `legal_representative` | `'LEGAL_PERSON'` |
| `board_secretary` | `'SECRETARY'` |
| `chairman` | `'CHAIRMAN'` |
| `securities_representative` | `'SECPRESENT'` |
| `independent_directors` | `'INDEDIRECTORS'` |
| `website` | `'ORG_WEB'` |
| `address` | `'ADDRESS'` |
| `registered_capital` | `'REG_CAPITAL'` |
| `employees_number` | `'EMP_NUM'` |
| `management_number` | `'TATOLNUMBER'` |
| `company_profile` | `'ORG_PROFILE'` |
| `business_scope` | `'BUSINESS_SCOPE'` |

**Key Code**:
```python
# Lines 16-37 in database_insert.py
data.get('SECURITY_NAME_ABBR'),  # Maps to company_name
data.get('ORG_NAME'),            # Maps to company_full_name
data.get('ORG_NAME_EN'),         # Maps to company_name_en
# ... etc
```

**To Change Mapping**: Edit `finrpt/source/database_insert.py`, lines 17-36

---

## 2. Company Report Table

### API Source
**EastMoney API**: Multiple endpoints for report content

### Step 1: API Response → Dictionary (Dataer.py)

**Location**: `finrpt/source/Dataer.py`, lines 124-231

```python
# Extract from API response
date = report['notice_date'][:10]
title = report['title']
art_code = report['art_code']
content = _get_report_content(art_code=art_code)  # Fetched from another API call
core_content = post_process_report(content)
summary = self.model.simple_prompt(...)  # LLM-generated summary

# Build dictionary
result = {
    'report_id': the_report_id,
    'date': date,
    'content': content,
    'stock_code': stock_code,
    'title': title,
    'core_content': core_content,
    'summary': report_agent_summary
}
company_report_table_insert(db=self.database_name, data=result)
```

### Step 2: Dictionary → Database (database_insert.py)

**Location**: `finrpt/source/database_insert.py`, lines 49-73

**Mapping Table**:

| Database Column | Dictionary Key |
|----------------|----------------|
| `report_id` | `'report_id'` |
| `content` | `'content'` |
| `stock_code` | `'stock_code'` |
| `date` | `'date'` |
| `title` | `'title'` |
| `core_content` | `'core_content'` |
| `summary` | `'summary'` |

**Key Code**:
```python
# Lines 58-64 in database_insert.py
data.get('report_id'),
data.get('content'),
data.get('stock_code'),
data.get('date'),
data.get('title'),
data.get('core_content'),
data.get('summary')
```

**To Change Mapping**: Edit `finrpt/source/Dataer.py`, lines 221-229 (build the dictionary) OR `finrpt/source/database_insert.py`, lines 58-64 (insertion)

---

## 3. News Table

### API Source
**Sina Finance API**: News list and individual news articles

### Step 1: API Response → Dictionary (Dataer.py)

**Location**: `finrpt/source/Dataer.py`, lines 442-612

```python
# Extract from API response (HTML parsing)
title = element.text.strip()
link = element.get('href')
content = _get_news_from_url(link)  # Fetched from individual news URL
news_summary = self.model.simple_prompt(...)  # LLM-generated
dec_response = self.model.simple_prompt(...)  # LLM decision
dec = "是" if "[[[是]]]" in dec_response else "否"

# Build dictionary
one_news = {
    "read_num": 0,
    "reply_num": 0,
    "news_url": link,
    "news_title": title,
    "news_author": "sina",
    "news_time": ann_date[id],
    "news_content": content,
    "stock_code": stock_code,
    "news_summary": news_summary,
    "dec_response": dec_response,
    "news_decision": dec
}
company_news_table_insert(db=self.database_name, data=one_news)
```

### Step 2: Dictionary → Database (database_insert.py)

**Location**: `finrpt/source/database_insert.py`, lines 76-104

**Mapping Table**:

| Database Column | Dictionary Key |
|----------------|----------------|
| `news_url` | `'news_url'` |
| `read_num` | `'read_num'` |
| `reply_num` | `'reply_num'` |
| `news_title` | `'news_title'` |
| `news_author` | `'news_author'` |
| `news_time` | `'news_time'` |
| `stock_code` | `'stock_code'` |
| `news_content` | `'news_content'` |
| `news_summary` | `'news_summary'` |
| `dec_response` | `'dec_response'` |
| `news_decision` | `'news_decision'` |

**Key Code**:
```python
# Lines 85-95 in database_insert.py
data.get('news_url'),
data.get('read_num'),
data.get('reply_num'),
data.get('news_title'),
data.get('news_author'),
data.get('news_time'),
data.get('stock_code'),
data.get('news_content'),
data.get('news_summary'),
data.get('dec_response'),
data.get('news_decision'),
```

**To Change Mapping**: Edit `finrpt/source/Dataer.py`, lines 577-589 (build dictionary) OR `finrpt/source/database_insert.py`, lines 85-95 (insertion)

---

## 4. Announcement Table

### API Source
**Sina Finance API**: Announcement list and individual announcements

### Step 1: API Response → Dictionary (Dataer.py)

**Location**: `finrpt/source/Dataer.py`, lines 315-372

```python
# Extract from API response (HTML parsing)
title = element.text.strip()
link = element.get('href')
content = _get_announcement_from_url(top_url + link)

# Build dictionary
one_announcement = {
    "title": title,
    "date": ann_date[id],
    "content": content,
    "stock_code": stock_code,
    "url": link
}
announcement_table_insert(db=self.database_name, data=one_announcement)
```

### Step 2: Dictionary → Database (database_insert.py)

**Location**: `finrpt/source/database_insert.py`, lines 109-131

**Mapping Table**:

| Database Column | Dictionary Key |
|----------------|----------------|
| `url` | `'url'` |
| `date` | `'date'` |
| `title` | `'title'` |
| `content` | `'content'` |
| `stock_code` | `'stock_code'` |

**Key Code**:
```python
# Lines 118-122 in database_insert.py
data.get('url'),
data.get('date'),
data.get('title'),
data.get('content'),
data.get('stock_code')
```

**To Change Mapping**: Edit `finrpt/source/Dataer.py`, lines 360-366 (build dictionary) OR `finrpt/source/database_insert.py`, lines 118-122 (insertion)

---

## How to Modify Field Mappings

### Example: Change Company Name Mapping

**Current**: `company_name` ← `SECURITY_NAME_ABBR`

**To Change to**: `company_name` ← `ORG_NAME`

**Edit**: `finrpt/source/database_insert.py`, line 17

**Change from**:
```python
data.get('SECURITY_NAME_ABBR'),  # company_name
```

**Change to**:
```python
data.get('ORG_NAME'),  # company_name
```

### Example: Add a New Field

1. **Add column to database**: Edit `finrpt/source/database_init.py` to add column to table
2. **Extract from API**: Edit `finrpt/source/Dataer.py` to extract the field from API response
3. **Add to dictionary**: Add the field to the dictionary being built
4. **Insert into DB**: Edit `finrpt/source/database_insert.py` to include the field in INSERT statement

---

## Summary

| Table | API Response → Dict | Dict → Database |
|-------|---------------------|-----------------|
| `company_info` | `Dataer.py` line 116 | `database_insert.py` lines 17-36 |
| `company_report` | `Dataer.py` lines 221-229 | `database_insert.py` lines 58-64 |
| `news` | `Dataer.py` lines 577-589 | `database_insert.py` lines 85-95 |
| `announcement` | `Dataer.py` lines 360-366 | `database_insert.py` lines 118-122 |

**Key Files**:
- `finrpt/source/Dataer.py` - API response parsing and dictionary creation
- `finrpt/source/database_insert.py` - Dictionary to database column mapping
- `finrpt/source/database_init.py` - Database schema definition

