# FinRpt.py 与数据库通信机制

## 概述

`FinRpt.py` 通过两种方式与 SQLite 数据库 (`cache.db`) 通信：
1. **通过 `Dataer` 类间接访问**（主要方式）
2. **直接使用 SQLite 连接查询**（用于 `trend` 表）

---

## 1. 通过 Dataer 类访问数据库

### 1.1 初始化 Dataer

```python
# FinRpt.py 第95行
self.dataer = Dataer(database_name=str(database_name))
```

`Dataer` 类在初始化时：
- 设置数据库路径：`self.database_name = database_name`
- 初始化数据库表结构：`self._init_db()` （调用 `database_init.py` 中的函数）

### 1.2 数据库表结构

`Dataer._init_db()` 会创建以下表（如果不存在）：

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `company_info` | 公司基本信息 | `stock_code` (主键) |
| `company_report` | 公司报告 | `report_id` (主键) |
| `news` | 新闻数据 | `news_url` (主键) |
| `announcement` | 公告数据 | `url` (主键) |

### 1.3 数据获取流程（缓存优先策略）

`FinRpt.run()` 通过 `self.dataer` 调用以下方法，这些方法都实现了**缓存优先**策略：

#### 1.3.1 `get_company_info()` - 获取公司信息

**位置**：`FinRpt.py` 第118行
```python
data["company_info"] = self.dataer.get_company_info(stock_code=stock_code, company_name=company_name)
```

**数据流程**：
1. **查询数据库**（`Dataer.py` 第113-121行）：
   ```python
   conn = sqlite3.connect(self.database_name)
   c.execute('SELECT * FROM company_info WHERE stock_code = ?', (stock_code,))
   result = c.fetchone()
   ```
2. **如果数据库中存在**：直接返回字典格式的数据
3. **如果数据库中不存在**：
   - 调用 EastMoney API 获取数据
   - 调用 `company_info_table_insert_em()` 将数据插入数据库
   - 递归调用 `get_company_info()` 再次查询（此时数据已在数据库中）

---

#### 1.3.2 `get_finacncials_ak()` - 获取财务数据

**位置**：`FinRpt.py` 第126行
```python
data["financials"] = self.dataer.get_finacncials_ak(stock_code=data["stock_code"], end_date=date)
```

**数据流程**：
- **US 股票**：调用 `get_finacncials_yf()` 使用 `yfinance` API（**当前不缓存到数据库**）
- **中国股票**：使用 `akshare` API 获取数据（**当前不缓存到数据库**）
- 注意：代码中有一段注释掉的缓存逻辑（`Dataer.py` 第741-756行），说明之前可能支持缓存，但目前被禁用了

---

#### 1.3.3 `get_company_news_sina()` - 获取新闻数据

**位置**：`FinRpt.py` 第134行
```python
news = self.dataer.get_company_news_sina(stock_code=data["stock_code"], end_date=date, company_name=data["company_name"])
```

**数据流程**：
1. **查询数据库**（`Dataer.py` 第531-557行）：
   ```python
   c.execute('''SELECT * FROM news WHERE stock_code = ? AND news_time BETWEEN ? AND ?''', 
             (stock_code, start_date, end_date))
   results = c.fetchall()
   ```
2. **如果数据库中存在**：直接返回范围内的所有新闻
3. **如果数据库中不存在**：
   - 遍历 API 获取新闻
   - 对每条新闻调用 `company_news_table_query_by_url()` 检查是否已存在
   - 如果不存在，则：
     - 获取新闻内容
     - 使用 LLM 生成摘要（`news_summary`）
     - 使用 LLM 判断是否影响股价（`news_decision`）
     - 调用 `company_news_table_insert()` 插入数据库

---

#### 1.3.4 `get_company_report_em()` - 获取公司报告

**位置**：`FinRpt.py` 第147行
```python
report = self.dataer.get_company_report_em(stock_code=stock_code, date=date)
```

**数据流程**：
1. **查询数据库**（`Dataer.py` 第184-208行）：
   ```python
   # 尝试查找年度报告（Q4）
   report_id_q4 = f'{stock_code}_{year}_Q4'
   c.execute('SELECT * FROM company_report WHERE report_id = ?', (report_id_q4,))
   # 如果不存在，尝试半年度报告（Q2）
   report_id_q2 = f'{stock_code}_{year}_Q2'
   ```
2. **如果数据库中存在**：直接返回报告数据
3. **如果数据库中不存在**：
   - 调用 EastMoney API 搜索报告列表
   - 对每个报告 ID，再次查询数据库（第238-248行）
   - 如果数据库中不存在该报告：
     - 调用 `_get_report_content()` 获取完整报告内容
     - 使用 LLM 生成摘要（`summary`）
     - 调用 `company_report_table_insert()` 插入数据库

---

## 2. 直接使用 SQLite 查询

### 2.1 查询 `trend` 表

**位置**：`FinRpt.py` 第166-180行

```python
try:
    conn = sqlite3.connect(self.dataer.database_name)
    c = conn.cursor()
    c.execute(f''' SELECT * FROM trend WHERE id='{stock_code}_{date}' ''')
    trend = c.fetchone()
    c.close()
    conn.close()
except Exception as e:
    trend = None

# 处理 trend 数据
if trend is not None and len(trend) > 3:
    data["trend"] = 1 if trend[3] > 0 else 0
else:
    data["trend"] = 0  # 默认值
```

**说明**：
- 直接使用 `sqlite3.connect()` 连接数据库
- 查询 `trend` 表（注意：此表不在 `Dataer._init_db()` 中初始化，可能在其他地方创建）
- 如果查询失败或数据不存在，默认 `data["trend"] = 0`

---

## 3. 数据库插入操作

所有插入操作都通过 `database_insert.py` 中的函数完成：

| 函数 | 调用位置 | 插入的表 |
|------|----------|----------|
| `company_info_table_insert_em()` | `Dataer.get_company_info()` | `company_info` |
| `company_report_table_insert()` | `Dataer.get_company_report_em()` | `company_report` |
| `company_news_table_insert()` | `Dataer.get_company_news_sina()` | `news` |
| `announcement_table_insert()` | `Dataer.get_company_announcement()` | `announcement` |

---

## 4. 数据流程总结

```
FinRpt.run()
    │
    ├─→ Dataer.get_company_info()
    │       ├─→ 查询数据库 (company_info 表)
    │       └─→ 如果不存在 → API 获取 → 插入数据库
    │
    ├─→ Dataer.get_finacncials_ak()
    │       ├─→ US股票: yfinance API (不缓存)
    │       └─→ 中国股票: akshare API (不缓存)
    │
    ├─→ Dataer.get_company_news_sina()
    │       ├─→ 查询数据库 (news 表, 按日期范围)
    │       └─→ 如果不存在 → API获取 → LLM处理 → 插入数据库
    │
    ├─→ Dataer.get_company_report_em()
    │       ├─→ 查询数据库 (company_report 表, 按report_id)
    │       └─→ 如果不存在 → API获取 → LLM处理 → 插入数据库
    │
    └─→ 直接SQLite查询 (trend 表)
            └─→ SELECT * FROM trend WHERE id = 'stock_code_date'
```

---

## 5. 关键设计模式

### 缓存优先策略（Cache-First）

所有通过 `Dataer` 获取数据的方法都遵循：
1. **先查数据库**：如果数据已存在，直接返回
2. **再查 API**：如果数据不存在，调用外部 API
3. **自动保存**：从 API 获取的数据会自动插入数据库，供下次使用

这种设计的优势：
- 减少 API 调用次数（节省成本和避免限流）
- 提高数据获取速度
- 支持离线测试（如果数据库已填充数据）

---

## 6. 注意事项

1. **财务数据不缓存**：`get_finacncials_ak()` 目前不将数据缓存到数据库（有注释掉的代码）
2. **trend 表**：不在 `Dataer._init_db()` 中初始化，可能在其他脚本中创建
3. **数据库路径**：由 `FinRpt.__init__()` 传递给 `Dataer`，默认为 `finrpt/source/cache.db`
4. **错误处理**：所有数据库操作都有 `try-except` 处理，失败时会回退到 API 调用
