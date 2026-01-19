# res_data 生成流程详解

## 概述

`res_data` 是在 `FinRpt.run()` 方法中逐步构建的数据字典，包含了报告生成所需的所有信息。它通过以下步骤生成：

1. **数据收集**：从数据库或API获取原始数据
2. **数据处理**：清洗和预处理数据
3. **LLM分析**：使用多个分析器通过LLM生成分析内容
4. **最终组装**：将所有数据整合到 `res_data` 中

---

## 1. 初始化阶段（FinRpt.py 第108-113行）

```python
data = {"save":{}}  # 初始化空字典
data["save"]["id"] = stock_code + "_" + date
data["save"]["stock_code"] = stock_code
data["save"]["date"] = date
data["model_name"] = self.model_name
data["date"] = date
```

**初始状态**：
- `data["save"]`：用于保存到 `result.pkl` 的备份数据
- `data["date"]`：分析日期
- `data["model_name"]`：使用的LLM模型名称

---

## 2. 数据收集阶段（FinRpt.py 第115-180行）

### 2.1 公司基本信息

**位置**：第117-123行

```python
data["company_info"] = self.dataer.get_company_info(stock_code=stock_code, company_name=company_name)
data["save"]["company_info"] = data["company_info"]
data["stock_code"] = data["company_info"]["stock_code"]
data["company_name"] = data["company_info"]["company_name"]
```

**数据来源**：
- `Dataer.get_company_info()`：从数据库或 EastMoney API 获取

**生成的字段**：
- `data["company_info"]`：公司信息字典（包含 `stock_code`, `company_name`, `industry_category`, `stock_exchange` 等）
- `data["stock_code"]`：股票代码
- `data["company_name"]`：公司名称

---

### 2.2 财务数据

**位置**：第125-131行

```python
data["financials"] = self.dataer.get_finacncials_ak(stock_code=data["stock_code"], end_date=date)
data["save"]["financials"] = data["financials"]
```

**数据来源**：
- `Dataer.get_finacncials_ak()`：
  - **US股票**：调用 `get_finacncials_yf()` 使用 `yfinance` API

**生成的字段**：
- `data["financials"]`：字典，包含：
  - `stock_info`：股票基本信息（`yfinance` 的 `ticker.info`）
  - `stock_data`：历史价格数据（pandas DataFrame）
  - `stock_income`：利润表（pandas DataFrame）
  - `stock_balance_sheet`：资产负债表（pandas DataFrame）
  - `stock_cash_flow`：现金流量表（pandas DataFrame）
  - `sp500_stock_data` 或 `csi300_stock_data`：基准指数数据

---

### 2.3 新闻数据

**位置**：第133-144行

```python
news = self.dataer.get_company_news_sina(stock_code=data["stock_code"], end_date=date, company_name=data["company_name"])
# 过滤出 news_decision == '是' 的新闻
new_news = []
for new in news:
    if new['news_decision'] == '是':
        new_news.append(new)
news = new_news
data["news"] = self.post_process_news(news)
data["save"]["news"] = data["news"]
```

**数据来源**：
- `Dataer.get_company_news_sina()`：从数据库或 Sina Finance API 获取

**后处理**（`post_process_news()`，第207-213行）：
1. `short_eliminate()`：过滤短新闻
2. `duplication_eliminate_bert()`：使用BERT去重
3. `duplication_eliminate_hash()`：使用哈希去重
4. `filter_news_by_date()`：按日期过滤
5. `limit_by_amount(news, 50)`：限制最多50条新闻

**生成的字段**：
- `data["news"]`：新闻列表，每条新闻包含：
  - `news_url`, `news_title`, `news_time`, `news_content`, `news_summary`, `news_decision` 等

---

### 2.4 公司报告

**位置**：第146-163行

```python
report = self.dataer.get_company_report_em(stock_code=stock_code, date=date)
if not report:
    report = {...}  # 创建空报告
data["report"] = report
data["save"]["report"] = data["report"]
```

**数据来源**：
- `Dataer.get_company_report_em()`：从数据库或 EastMoney API 获取年度/半年度报告

**生成的字段**：
- `data["report"]`：报告字典，包含：
  - `report_id`, `date`, `content`, `title`, `core_content`, `summary` 等

---

### 2.5 趋势数据

**位置**：第166-180行

```python
conn = sqlite3.connect(self.dataer.database_name)
c.execute(f"SELECT * FROM trend WHERE id='{stock_code}_{date}'")
trend = c.fetchone()

if trend is not None and len(trend) > 3:
    data["trend"] = 1 if trend[3] > 0 else 0
else:
    data["trend"] = 0
```

**数据来源**：
- 直接查询 `trend` 表

**生成的字段**：
- `data["trend"]`：0 或 1（趋势指标）

---

## 3. LLM分析阶段（FinRpt.py 第182-195行）

### 3.1 新闻分析（NewsAnalyzer）

**位置**：第182-183行

```python
data["analyze_news"] = self.news_analyzer.run(data, run_path=run_path)
```

**分析过程**（`NewsAnalyzer.run()`, `NewsAnalyzer.py` 第49-84行）：
1. **构建Prompt**：
   - 输入：公司名称 + 所有新闻（每条包含日期、标题、摘要）
   - 提示词：要求LLM选择最多10条最重要的新闻
2. **LLM调用**：`self.model.robust_prompt(prompt)`
3. **结果解析**：解析JSON，提取 `key_news` 列表
4. **后处理**：为每条新闻添加 `concise_new` 字段

**生成的字段**：
- `data["analyze_news"]`：关键新闻列表，每条包含：
  - `date`, `content`, `potential_impact`, `concise_new` 等

---

### 3.2 财务分析（FinancialsAnalyzer）

**位置**：第185-186行

```python
data["analyze_income"], data["analyze_balance"], data["analyze_cash"] = self.financials_analyzer.run(data, run_path=run_path)
```

**分析过程**（`FinancialsAnalyzer.run()`, `FinancialsAnalyzer.py` 第81-121行）：
1. **损益表分析**：
   - 输入：`data["financials"]['stock_income']` (pandas DataFrame)
   - Prompt：`INCOME_PROMPT_ZH`（要求分析收入、成本、盈利能力、EPS等）
   - LLM调用：`self.model.robust_prompt(income_prompt)`
2. **资产负债表分析**：
   - 输入：`data["financials"]['stock_balance_sheet']`
   - Prompt：`BALANCE_PROMPT_ZH`（要求分析资产结构、负债、权益等）
3. **现金流量表分析**：
   - 输入：`data["financials"]['stock_cash_flow']`
   - Prompt：`CASH_PROMPT_ZH`（要求分析经营、投资、融资活动现金流）

**生成的字段**：
- `data["analyze_income"]`：损益表分析文本（字符串）
- `data["analyze_balance"]`：资产负债表分析文本（字符串）
- `data["analyze_cash"]`：现金流量表分析文本（字符串）

---

### 3.3 综合建议生成（Advisor）

**位置**：第188-189行

```python
data['analyze_advisor'] = self.advisor.run(data, run_path=run_path)
```

**分析过程**（`Advisor.run()`, `Advisor.py` 第83-162行）：

分三个子任务：

**a) 财务段落**（第90-108行）：
- 输入：`data['analyze_income']` + `data['analyze_balance']` + `data['analyze_cash']`
- Prompt：`PROMPT_FINANCE`（要求生成200字内的财务分析段落）
- LLM调用：`OpenAIModel().json_prompt(finance_write_prompt)`
- 返回：`{"段落": "...", "标题": "..."}`

**b) 新闻段落**（第110-129行）：
- 输入：`data['analyze_news']` 的关键新闻摘要
- Prompt：`PROMPT_NEWS`（要求生成200字内的新闻影响分析段落）
- LLM调用：`OpenAIModel().json_prompt(news_write_prompt)`
- 返回：`{"段落": "...", "标题": "..."}`

**c) 报告段落**（第131-153行）：
- 输入：`data['report']['title']` + `data['report']['summary']`
- Prompt：`PROMPT_REPORT`（要求生成200字内的战略分析段落）
- LLM调用：`OpenAIModel().json_prompt(report_write_prompt)`
- 返回：`{"段落": "...", "标题": "..."}`

**最终组装**（第155-162行）：
```python
response_json['report'].append({'content': finance_response_json["段落"], 'title': finance_response_json["标题"]})
response_json['report'].append({'content': news_response_json["段落"], 'title': news_response_json["标题"]})
response_json['report'].append({'content': report_response_json["段落"], 'title': report_response_json["标题"]})
return response_json['report']
```

**生成的字段**：
- `data['analyze_advisor']`：列表，包含3个字典：
  ```python
  [
    {'content': '财务分析段落', 'title': '财务分析标题'},
    {'content': '新闻分析段落', 'title': '新闻分析标题'},
    {'content': '报告分析段落', 'title': '报告分析标题'}
  ]
  ```

---

### 3.4 风险评估（RiskAssessor）

**位置**：第191-192行

```python
data['analyze_risk'] = self.risk_assessor.run(data, run_path=run_path)
```

**分析过程**（`RiskAssessor.run()`, `RiskAssessor.py` 第34-47行）：
1. **构建Prompt**：
   - 输入：`data["analyze_advisor"]`（综合建议）+ `data['report']['summary']`（报告摘要）
   - Prompt：`PROMPT_ZH`（要求分析至少3个风险因素，每个不超过10个字）
2. **LLM调用**：`self.model.json_prompt(risk_prompt)`
3. **结果解析**：提取 `risks` 列表

**生成的字段**：
- `data['analyze_risk']`：风险列表（字符串列表），例如：
  ```python
  ["市场竞争加剧", "原材料价格上涨", "政策监管风险"]
  ```

---

### 3.5 预测分析（Predictor）

**位置**：第194-195行

```python
data['analyze_predict'] = self.predictor.run(data, run_path=run_path)
```

**分析过程**（`Predictor.run()`, `Predictor.py` 第22-59行）：
1. **构建Prompt**：
   - 输入：
     - `data['analyze_advisor']`（综合建议的3个段落）
     - `data['analyze_risk']`（风险评估）
     - `data['financials']['stock_data']`（股票历史价格）
     - `data['financials']['csi300_stock_data']`（沪深300指数价格）
   - Prompt：`PROMPT_TREND`（要求预测未来三周趋势，给出买入/卖出评级）
2. **LLM调用**：`OpenAIModel().json_prompt(trend_write_prompt)`
3. **结果解析**：提取 `{"段落": "...", "标题": "...", "评级": "买入/卖出"}`
4. **添加到analyze_advisor**（第57行）：
   ```python
   data['analyze_advisor'].append({'content': trend_response_json["段落"], 'title': trend_response_json["标题"], "rating": trend_response_json["评级"]})
   ```

**生成的字段**：
- `data['analyze_predict']`：预测结果字典：
  ```python
  {"段落": "预测分析段落", "标题": "预测标题", "评级": "买入/卖出"}
  ```
- **注意**：预测结果也会追加到 `data['analyze_advisor']` 中（第57行），使其成为第4个元素

---

## 4. 最终组装阶段（FinRpt.py 第197行）

```python
data['report_title'] = data["company_info"]["company_name"] + "研报（" + date + "）"
```

**生成的字段**：
- `data['report_title']`：报告标题字符串

---

## 5. 数据保存（FinRpt.py 第199-200行）

```python
result_save_path = os.path.join(run_path, 'result.pkl')
pickle.dump(data['save'], open(result_save_path, 'wb'))
```

**保存内容**：
- 只保存 `data['save']` 到 `result.pkl`（原始数据，不包括LLM分析结果）

---

## 6. res_data 最终结构

在 `build_report(data, date, run_path)` 调用时，`data`（即 `res_data`）的完整结构：

```python
res_data = {
    # === 基础信息 ===
    "stock_code": "600519.SS",
    "company_name": "贵州茅台",
    "date": "2024-11-05",
    "model_name": "gpt-4o",
    "report_title": "贵州茅台研报（2024-11-05）",
    
    # === 原始数据（从API/数据库获取） ===
    "company_info": {...},           # 公司基本信息
    "financials": {                  # 财务数据
        "stock_info": {...},
        "stock_data": DataFrame,
        "stock_income": DataFrame,
        "stock_balance_sheet": DataFrame,
        "stock_cash_flow": DataFrame,
        "csi300_stock_data": DataFrame
    },
    "news": [...],                   # 新闻列表（已过滤和处理）
    "report": {...},                 # 公司报告
    "trend": 0,                      # 趋势指标（0或1）
    
    # === LLM分析结果 ===
    "analyze_news": [...],           # 关键新闻列表（NewsAnalyzer生成）
    "analyze_income": "文本",        # 损益表分析（FinancialsAnalyzer生成）
    "analyze_balance": "文本",       # 资产负债表分析（FinancialsAnalyzer生成）
    "analyze_cash": "文本",          # 现金流量表分析（FinancialsAnalyzer生成）
    "analyze_advisor": [             # 综合建议列表（Advisor生成，Predictor追加）
        {"content": "...", "title": "..."},  # 财务分析
        {"content": "...", "title": "..."},  # 新闻分析
        {"content": "...", "title": "..."},  # 报告分析
        {"content": "...", "title": "...", "rating": "买入/卖出"}  # 预测分析（由Predictor追加）
    ],
    "analyze_risk": ["风险1", "风险2", ...],  # 风险评估列表（RiskAssessor生成）
    "analyze_predict": {...},        # 预测结果（Predictor生成）
    
    # === 备份数据（用于保存到pkl） ===
    "save": {
        "id": "...",
        "stock_code": "...",
        "date": "...",
        "company_info": {...},
        "financials": {...},
        "news": [...],
        "report": {...},
        # ... (还包括各种prompt和response的备份)
    }
}
```

---

## 7. 数据流向图

```
FinRpt.run()
    │
    ├─→ 初始化 data 字典
    │
    ├─→ 数据收集阶段
    │   ├─→ Dataer.get_company_info() → data["company_info"]
    │   ├─→ Dataer.get_finacncials_ak() → data["financials"]
    │   ├─→ Dataer.get_company_news_sina() → data["news"]
    │   ├─→ Dataer.get_company_report_em() → data["report"]
    │   └─→ 直接查询trend表 → data["trend"]
    │
    ├─→ LLM分析阶段（依赖顺序）
    │   ├─→ NewsAnalyzer.run() → data["analyze_news"]
    │   ├─→ FinancialsAnalyzer.run() → data["analyze_income/balance/cash"]
    │   ├─→ Advisor.run() → data["analyze_advisor"][0:3]
    │   ├─→ RiskAssessor.run() → data["analyze_risk"]
    │   └─→ Predictor.run() → data["analyze_predict"] + data["analyze_advisor"][3]
    │
    └─→ 最终组装
        ├─→ data["report_title"] = ...
        └─→ pickle.dump(data["save"], ...)
        
        └─→ build_report(data, date, run_path)
                └─→ 使用 res_data 生成PDF报告
```

---

## 8. 关键依赖关系

1. **Advisor 依赖 FinancialsAnalyzer 和 NewsAnalyzer**：
   - `Advisor.run()` 需要 `data["analyze_income/balance/cash"]` 和 `data["analyze_news"]`

2. **RiskAssessor 依赖 Advisor**：
   - `RiskAssessor.run()` 需要 `data["analyze_advisor"]`

3. **Predictor 依赖 Advisor 和 RiskAssessor**：
   - `Predictor.run()` 需要 `data["analyze_advisor"]` 和 `data["analyze_risk"]`
   - `Predictor` 还会修改 `data["analyze_advisor"]`（追加第4个元素）

这就是为什么分析阶段有严格的顺序：**NewsAnalyzer → FinancialsAnalyzer → Advisor → RiskAssessor → Predictor**。
