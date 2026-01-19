# 数据库文件保存机制说明

## 一、数据库文件位置

### 默认路径
```
finrpt/source/cache.db
```

### 路径设置
**在 `FinRpt.__init__()` 中设置**:
```python
if database_name is None:
    project_root = Path(__file__).parent.parent.parent
    database_name = project_root / 'finrpt' / 'source' / 'cache.db'
```

**在 `Dataer.__init__()` 中**:
```python
def __init__(self, database_name='/data/name/FinRpt_v1/finrpt/source/cache.db', ...):
    self.database_name = database_name
    self._init_db()  # 初始化所有表
```

**实际使用**: `FinRpt` 会将动态计算的路径传递给 `Dataer`

---

## 二、数据库初始化流程

### 1. 表初始化 (`_init_db()`)
**位置**: `finrpt/source/Dataer.py::_init_db()`

```python
def _init_db(self):
    company_info_table_init(self.database_name)
    company_report_table_init(self.database_name)
    announcement_table_init(self.database_name)
    company_news_table_init(self.database_name)
```

### 2. 每个表的初始化函数
**位置**: `finrpt/source/database_init.py`

**初始化步骤**:
1. **确保目录存在**:
   ```python
   db_path = Path(db)
   db_path.parent.mkdir(parents=True, exist_ok=True)  # 自动创建目录
   ```

2. **连接数据库**:
   ```python
   conn = sqlite3.connect(str(db))  # 如果文件不存在会自动创建
   ```

3. **创建表**:
   ```python
   c.execute('''
       CREATE TABLE IF NOT EXISTS table_name (
           column1 TYPE PRIMARY KEY,
           column2 TYPE,
           ...
       )
   ''')
   ```

4. **提交并关闭**:
   ```python
   conn.commit()
   conn.close()
   ```

---

## 三、数据库表结构

### 1. `company_info` 表
**用途**: 存储公司基本信息

**字段**:
- `stock_code` (PRIMARY KEY): 股票代码
- `company_name`: 公司名称
- `company_full_name`: 公司全称
- `company_name_en`: 英文名称
- `industry_category`: 行业分类
- `stock_exchange`: 交易所
- `general_manager`: 总经理
- `legal_representative`: 法人代表
- ... (共21个字段)

**保存时机**: API调用成功后立即保存

---

### 2. `company_report` 表
**用途**: 存储公司年报/半年报

**字段**:
- `report_id` (PRIMARY KEY): 报告ID (`{stock_code}_{date}`)
- `content`: 报告完整内容
- `stock_code`: 股票代码
- `date`: 报告日期
- `title`: 报告标题
- `core_content`: 核心内容（LLM提取）
- `summary`: 摘要（LLM生成）

**保存时机**: 报告内容获取并处理后保存

---

### 3. `news` 表
**用途**: 存储新闻数据

**字段**:
- `news_url` (PRIMARY KEY): 新闻URL
- `read_num`: 阅读数
- `reply_num`: 回复数
- `news_title`: 标题
- `news_author`: 作者
- `news_time`: 发布时间
- `stock_code`: 股票代码
- `news_content`: 内容
- `news_summary`: 摘要（LLM生成）
- `dec_response`: LLM决策响应
- `news_decision`: 是否影响股价（"是"/"否"）

**保存时机**: 每条新闻处理完成后保存

---

### 4. `announcement` 表
**用途**: 存储公司公告

**字段**:
- `url` (PRIMARY KEY): 公告URL
- `date`: 公告日期
- `title`: 标题
- `content`: 内容
- `stock_code`: 股票代码

**保存时机**: 公告内容获取后保存

---

### 5. `financials` 表（已注释，未使用）
**用途**: 原本用于存储财务数据（已禁用）

**字段** (在代码中定义但未启用):
- `id` (PRIMARY KEY): `{stock_code}_{date}`
- `stock_info` (BLOB): 股票信息（pickle序列化）
- `stock_data` (BLOB): 历史股价数据
- `stock_income` (BLOB): 利润表
- `stock_balance_sheet` (BLOB): 资产负债表
- `stock_cash_flow` (BLOB): 现金流表
- `csi300_stock_data` (BLOB): CSI300数据

**状态**: ❌ 代码中已注释，当前不缓存财务数据

---

## 四、数据保存机制

### 1. 保存流程

```
API调用 → 获取数据 → 数据转换 → 插入数据库 → commit → 关闭连接
```

### 2. 保存时机

#### A. 公司信息 (`company_info`)
**位置**: `finrpt/source/Dataer.py::get_company_info()`

```python
# 1. 先查询数据库
conn = sqlite3.connect(self.database_name)
c.execute('SELECT * FROM company_info WHERE stock_code = ?', (stock_code_ori,))
result = c.fetchone()

# 2. 如果不存在，调用API
if not result:
    response = self._request_get(url)
    data = response.json()['result']['data'][0]
    
    # 3. 保存到数据库
    company_info_table_insert_em(db=self.database_name, data=data, stock_code=stock_code_ori)
```

**保存函数**: `finrpt/source/database_insert.py::company_info_table_insert_em()`

```python
def company_info_table_insert_em(db, data, stock_code):
    conn = sqlite3.connect(db)
    c = conn.cursor()
    c.execute('''
        INSERT INTO company_info (...) VALUES (?, ?, ...)
    ''', (stock_code, data.get('SECURITY_NAME_ABBR'), ...))
    conn.commit()  # 立即提交
    conn.close()
```

---

#### B. 公司报告 (`company_report`)
**位置**: `finrpt/source/Dataer.py::get_company_report_em()`

```python
# 1. 先查询数据库
c.execute('SELECT * FROM company_report WHERE report_id = ?', (report_id,))
result = c.fetchone()

# 2. 如果不存在，获取报告内容
if not result:
    # 获取报告内容...
    result = {...}
    
    # 3. 保存到数据库
    company_report_table_insert(db=self.database_name, data=result)
```

---

#### C. 新闻 (`news`)
**位置**: `finrpt/source/Dataer.py::get_company_news_sina()`

```python
# 1. 先查询数据库（按日期范围）
c.execute('''SELECT * FROM news 
             WHERE stock_code = ? AND news_time BETWEEN ? AND ?''', 
          (stock_code, start_date, end_date))
results = c.fetchall()

# 2. 如果不存在，调用API
if not results:
    # 获取新闻列表...
    for news_item in news_list:
        # 处理新闻（LLM摘要和决策）
        one_news = {...}
        
        # 3. 保存每条新闻
        company_news_table_insert(db=self.database_name, data=one_news)
```

---

### 3. 保存特点

#### ✅ **立即提交 (Immediate Commit)**
每次插入操作后立即调用 `conn.commit()`，确保数据持久化：

```python
c.execute('INSERT INTO ...')
conn.commit()  # 立即提交
conn.close()
```

#### ✅ **自动创建目录**
如果数据库文件路径的目录不存在，会自动创建：

```python
db_path = Path(db)
db_path.parent.mkdir(parents=True, exist_ok=True)  # 创建目录
conn = sqlite3.connect(str(db))  # 创建数据库文件
```

#### ✅ **缓存优先策略**
所有数据获取都遵循"先查数据库，再调用API"的策略：

```python
# 1. 先查数据库
if cached_data:
    return cached_data

# 2. 如果不存在，调用API
api_data = call_api()

# 3. 保存到数据库
save_to_db(api_data)

# 4. 返回数据
return api_data
```

---

## 五、数据库文件创建

### SQLite3 特性

1. **自动创建文件**:
   - 如果文件不存在，`sqlite3.connect()` 会自动创建
   - 文件创建在首次连接时

2. **文件格式**:
   - 单文件数据库
   - 二进制格式
   - 跨平台兼容

3. **目录创建**:
   - 代码中确保目录存在：
   ```python
   db_path.parent.mkdir(parents=True, exist_ok=True)
   ```

---

## 六、数据保存示例

### 示例1: 保存公司信息

```python
# 在 get_company_info() 中
if not result_from_db:
    # API调用
    response = self._request_get(url)
    data = response.json()['result']['data'][0]
    
    # 保存到数据库
    company_info_table_insert_em(
        db=self.database_name, 
        data=data, 
        stock_code=stock_code_ori
    )
```

### 示例2: 保存新闻

```python
# 在 get_company_news_sina() 中
for news_item in news_list:
    # LLM处理
    news_summary = self.model.simple_prompt(...)
    news_decision = self.model.simple_prompt(...)
    
    # 构建数据
    one_news = {
        'news_url': url,
        'news_title': title,
        'news_content': content,
        'news_summary': news_summary,
        'news_decision': news_decision,
        ...
    }
    
    # 保存到数据库
    company_news_table_insert(db=self.database_name, data=one_news)
```

---

## 七、数据库文件信息

### 文件位置
```
{project_root}/finrpt/source/cache.db
```

### 默认绝对路径（旧代码）
```
/data/name/FinRpt_v1/finrpt/source/cache.db
```
⚠️ 注意：这是硬编码的旧路径，新代码已改为相对路径

### 实际路径（当前）
```python
# 在 FinRpt.__init__() 中动态计算
project_root = Path(__file__).parent.parent.parent  # 项目根目录
database_name = project_root / 'finrpt' / 'source' / 'cache.db'
```

---

## 八、数据持久化机制

### 1. **事务处理**
- 每次操作独立事务
- `INSERT` → `commit()` → `close()`
- 确保数据不丢失

### 2. **错误处理**
```python
try:
    conn = sqlite3.connect(db)
    c = conn.cursor()
    c.execute('INSERT INTO ...')
    conn.commit()
except Exception as e:
    print(e)
finally:
    if conn:
        conn.close()
```

### 3. **重复数据处理**
- 使用 `PRIMARY KEY` 防止重复
- `INSERT` 失败时会捕获异常（不中断程序）

---

## 九、当前缓存状态

| 数据类型 | 是否缓存 | 表名 | 状态 |
|---------|---------|------|------|
| 公司信息 | ✅ | `company_info` | 已实现 |
| 公司报告 | ✅ | `company_report` | 已实现 |
| 新闻数据 | ✅ | `news` | 已实现 |
| 公告数据 | ✅ | `announcement` | 已实现 |
| 财务数据 | ❌ | `financials` | **未启用**（代码已注释）|

---

## 十、总结

### 数据库保存流程

1. **初始化**: `Dataer.__init__()` → 创建所有表
2. **数据获取**: 先查数据库 → 不存在则调用API
3. **数据保存**: API数据 → 转换格式 → `INSERT INTO ...` → `commit()`
4. **持久化**: SQLite自动持久化到文件

### 关键特性

- ✅ **自动创建**: 目录和文件自动创建
- ✅ **立即提交**: 每次插入后立即commit
- ✅ **缓存优先**: 先查数据库再调用API
- ✅ **错误处理**: 异常不影响程序运行
- ✅ **单文件**: SQLite单文件数据库，易于管理

### 数据库文件

- **文件名**: `cache.db`
- **位置**: `finrpt/source/cache.db`
- **格式**: SQLite3
- **大小**: 取决于缓存的数据量
- **备份**: 直接复制 `.db` 文件即可备份
