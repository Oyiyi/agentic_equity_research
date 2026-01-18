# Cache Database Usage Verification

This document shows how `finrpt/module/FinRpt.py` uses `cache.db` and whether it checks the database before making API calls.

## Current Cache-First Behavior

### ✅ 1. Company Info (`get_company_info`)
**Location**: `finrpt/source/Dataer.py`, lines 93-101

**Behavior**: ✅ **Checks database FIRST**
```python
# Line 93-96: Check database
conn = sqlite3.connect(self.database_name)
c.execute('SELECT * FROM company_info WHERE stock_code = ?', (stock_code_ori,))
result = c.fetchone()

# Line 100-101: Return cached data if found
if result:
    return dict(zip(COMPANY_INFO_TABLE_COLUMNS, result))

# Line 113-118: Only calls API if NOT in database
```

**Status**: ✅ **Uses cache when available**

---

### ✅ 2. Company Report (`get_company_report_em`)
**Location**: `finrpt/source/Dataer.py`, lines 124-231

**Behavior**: ✅ **Checks database FIRST** (Updated)
```python
# Lines 160-177: Check database first before API call
report_id_q4 = f'{stock_code}_{year}_Q4'
c.execute('SELECT * FROM company_report WHERE report_id = ?', (report_id_q4,))
query_result = c.fetchone()
if query_result:
    return dict(zip(COMPANY_REPORT_TABLE_COLUMNS, query_result))  # Uses cached data

# Only calls API if not found in database (line 181+)
```

**Status**: ✅ **Uses cache when available** (Updated to check first)

---

### ✅ 3. News (`get_company_news_sina`)
**Location**: `finrpt/source/Dataer.py`, lines 442-612

**Behavior**: ✅ **Checks database FIRST** (Updated)
```python
# Lines 483-510: Check database first for all news in date range
c.execute('''SELECT * FROM news WHERE stock_code = ? AND news_time BETWEEN ? AND ?''', 
          (stock_code, start_date, end_date))
results = c.fetchall()
if results:
    return result_list  # Return all cached news immediately

# Only calls API if not found in database (line 515+)
```

**Status**: ✅ **Uses cache when available** (Updated to check first)

---

### ✅ 4. Announcements (`get_company_announcement`)
**Location**: `finrpt/source/Dataer.py`, lines 315-372

**Behavior**: Similar to news - checks per item but gets list from API first.

---

## Summary

| Data Type | Database Check | API Calls Made | Status |
|-----------|----------------|----------------|--------|
| **Company Info** | ✅ Checks first | ❌ None if cached | ✅ Full cache support |
| **Company Report** | ✅ Checks first | ❌ None if cached | ✅ Full cache support (Updated) |
| **News** | ✅ Checks first | ❌ None if cached | ✅ Full cache support (Updated) |
| **Announcements** | ⚠️ Checks per item | ⚠️ Gets list from API | ⚠️ Partial cache |
| **Financial Data** | ❌ Not cached | ✅ Always from akshare | ❌ No cache |

---

## Current Issues

1. **Announcements still call API** to get lists, even when data exists in cache (could be improved)
2. **Financial data is never cached** - always fetched from akshare (by design)
3. ~~**News and Reports still call API**~~ - **FIXED**: Now checks database first

---

## For Your Test Database

Your test `cache.db` contains:
- ✅ 1 company_info record (600519.SS) - **Will use cache**
- ✅ 1 company_report record (600519.SS_2023_Q4) - **Will use cache** (Updated: checks first)
- ✅ 5 news records (600519.SS) - **Will use cache** (Updated: checks first)
- ✅ 1 announcement record - **Will use cache** (but still calls API for list)

**When you run `python finrpt/module/FinRpt.py`**:
- Company info will be fully from cache ✅
- Company report will be fully from cache ✅ (Updated)
- News will be fully from cache ✅ (Updated)
- Announcements will check cache per item, but may still make initial API calls to get lists ⚠️
- Financial data will always be fetched from akshare (not cached by design) ⚠️
