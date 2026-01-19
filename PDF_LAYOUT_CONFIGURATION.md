# PDF报告布局配置说明

## 概述

PDF报告的布局、数据源、表格和分析内容的设置都在 `finrpt/utils/ReportBuild.py` 的 `build_report()` 函数中定义。

---

## 1. PDF布局结构

PDF页面使用 **A4** 纸张，分为三个主要区域：

```
┌─────────────────────────────────────────────────────┐
│ Logo + 标题 + 日期 (顶部)                            │
├─────────────────────────────┬───────────────────────┤
│                             │                       │
│   左侧 Frame (左栏)          │  右侧 Frame (右栏)     │
│   - 核心观点                │   - 作者信息           │
│   - 风险评估                │   - 基本状况表格       │
│   - 财务数据表格            │   - 股价走势图         │
│                             │   - PE/EPS图          │
│                             │   - 营业收入图         │
│                             │                       │
└─────────────────────────────┴───────────────────────┘
```

---

## 2. 数据来源映射

### 2.1 输入数据 (`res_data`)

`build_report(res_data, date, save_path)` 函数接收 `res_data` 字典，包含：

| 数据键 | 来源 | 用途 |
|--------|------|------|
| `res_data['stock_code']` | `FinRpt.run()` → `data['stock_code']` | 股票代码 |
| `res_data['company_name']` | `FinRpt.run()` → `data['company_name']` | 公司名称 |
| `res_data['report_title']` | `FinRpt.run()` → `data['report_title']` | 报告标题 |
| `res_data['analyze_advisor']` | `FinRpt.run()` → `data['analyze_advisor']` | 核心观点列表 |
| `res_data['analyze_risk']` | `FinRpt.run()` → `data['analyze_risk']` | 风险评估列表 |
| `res_data['financials']['stock_income']` | `Dataer.get_finacncials_ak()` | 财务数据表格 |
| `res_data['company_info']` | `Dataer.get_company_info()` | 基本状况表格 |

---

## 3. 左侧Frame（核心内容和财务表格）

### 3.1 Frame定义

**位置**：`ReportBuild.py` 第444-455行

```python
frame_left = Frame(
    x1=25,                           # 左边界：25点
    y1=0,                            # 下边界：0点
    width=A4[0] - 235,               # 宽度：595 - 235 = 360点
    height=A4[1] - 120,              # 高度：842 - 120 = 722点
    showBoundary=0,
    topPadding=0,
    leftPadding=4,
    rightPadding=4
)
```

### 3.2 核心观点（"核心观点"标题）

**位置**：第457-484行

**数据来源**：
```python
res_data["analyze_advisor"]  # 列表，每个元素是字典：{'title': '标题', 'content': '内容'}
```

**生成方式**：
```python
frame_title1 = draw_frame_title("核心观点", color1, A4[0] - 243, font_name)
frame_left_list.append(frame_title1)

for sub_advisor in res_data["analyze_advisor"]:
    paragraph_text = '<font color="#9E1F00"><b>' + sub_advisor['title'] + '：</b></font>' + sub_advisor['content']
    paragraph_advisor = BulletParagraph(icon_path, paragraph_text, font_name)
    frame_left_list.append(paragraph_advisor)
```

**输出位置**：Frame顶部，按顺序垂直排列

---

### 3.3 风险评估

**位置**：第486-492行

**数据来源**：
```python
res_data["analyze_risk"]  # 列表，每个元素是字符串
```

**生成方式**：
```python
risk_assessment = ""
for idx, risk in enumerate(res_data["analyze_risk"]):
    risk_assessment += "(" + str(idx + 1) + ")" + risk + ";"
paragraph_text = '<font color="#9E1F00"><b>风险评估：</b></font>' + risk_assessment
paragraph_advisor = BulletParagraph('figs/icon.png', paragraph_text, font_name)
frame_left_list.append(paragraph_advisor)
```

**输出位置**：核心观点下方

---

### 3.4 财务数据表格（"财务数据"标题）

**位置**：第494-520行

**数据来源**：
```python
df = res_data["financials"]['stock_income']  # pandas DataFrame
```

**数据提取和处理**：
```python
# 第497行：从 res_data 获取 DataFrame
df = res_data["financials"]['stock_income']

# 第500-505行：数据预处理
df['日期'] = df['日期'].apply(lambda x: x[:-4] + '-' + x[4:6] + '-' + x[-2:])
df.set_index('日期', inplace=True)
df = df.head(4)        # 只取前4行（最近4个季度）
df = df.transpose()     # 转置：行变列，列变行
df.reset_index(inplace=True)
df.rename(columns={'index': ''}, inplace=True)

# 第517-519行：构建表格
table_data = []
table_data += [df.columns.to_list()] + df.values.tolist()
financias_table = get_financias_table(font_name, table_data)
```

**表格样式**：
- 函数：`get_financias_table()`（第307-329行）
- 列宽：`[115, 55, 55, 55, 55]`（5列）
- 表头背景色：`colors.lightgrey`
- 交替行背景色：白色和 `colors.whitesmoke`
- 字体大小：8pt

**输出位置**：风险评估下方

---

## 4. 右侧Frame（作者信息、基本状况、图表）

### 4.1 Frame定义

**位置**：第524-534行

```python
frame_right = Frame(
    x1=A4[0] - 210,      # 左边界：595 - 210 = 385点
    y1=0,                 # 下边界：0点
    width=185,            # 宽度：185点
    height=A4[1] - 120,   # 高度：722点
    showBoundary=0,
    topPadding=0
)
```

---

### 4.2 作者信息（"作者"标题）

**位置**：第536-547行

**数据**：硬编码（非动态）

**生成方式**：
```python
frame_title3 = draw_frame_title("作者", color1, 177, font_name)
frame_title3.drawOn(c, A4[0] - 206, A4[1] - 120 - 21)  # 绝对位置绘制

c.drawString(A4[0] - 200, A4[1] - 170, "分析师: FinRpt")
c.drawString(A4[0] - 200, A4[1] - 190, "版权: ****")
c.drawString(A4[0] - 200, A4[1] - 210, "地址: ****")
```

**输出位置**：右侧Frame顶部（绝对坐标：x=389, y=721）

---

### 4.3 基本状况表格（"基本状况"标题）

**位置**：第549-560行

**数据来源**：
1. **`get_key_data()` 函数**（第157-230行）：
   - 调用 `yfinance` API 获取：
     - `6m avg daily vol`（6个月平均日成交量）
     - `Closing Price`（收盘价）
     - `52 Week Price Range`（52周价格范围）
2. **`res_data['company_info']`**：
   - `stock_exchange`（交易所）
   - `industry_category`（行业）

**生成方式**：
```python
# 第553行：获取关键数据
key_data = get_key_data(stock_code, date)

# 第554行：映射字段名（BASE_key_mapping 定义在第87-91行）
base_data = {BASE_key_mapping[key]: value for key, value in key_data.items()}

# 第555-556行：添加公司信息
base_data["交易所"] = res_data["company_info"]["stock_exchange"]
base_data["行业"] = res_data["company_info"]["industry_category"][-11:]  # 取最后11个字符

# 第557-559行：构建表格
base_data = [[k, v] for k, v in base_data.items()]
base_table = get_base_table(font_name, base_data)

# 第560行：绝对位置绘制
base_table.drawOn(c, A4[0] - 205, A4[1] - 345)
```

**表格样式**：
- 函数：`get_base_table()`（第277-304行）
- 列宽：`[90, 90]`（2列，左列标签，右列数值）
- 字体大小：9pt

**输出位置**：绝对坐标（x=390, y=497）

---

### 4.4 股价走势图（"股市与市场走势对比"标题）

**位置**：第562-570行

**数据来源**：
```python
# 第339行：调用 charting.py 生成图表
get_share_performance(res_data, res_data['stock_code'], date, save_path=figs_path)
```

**图表函数**：`finrpt/utils/charting.py` 的 `get_share_performance()`

**生成方式**：
```python
frame_title5 = draw_frame_title("股市与市场走势对比", color1, 177, font_name)
frame_title5.drawOn(c, A4[0] - 206, A4[1] - 375)  # 标题位置

img = Image(share_performance_image_path)
img.drawWidth = 170
img.drawHeight = img.drawWidth * (raw_height / raw_width)
img.drawOn(c, A4[0] - 205, A4[1] - 485)  # 图片位置
```

**输出位置**：
- 标题：绝对坐标（x=389, y=467）
- 图片：绝对坐标（x=390, y=357）

---

### 4.5 PE/EPS图（"PE & EPS"标题）

**位置**：第572-580行

**数据来源**：
```python
# 第340行：调用 charting.py 生成图表
get_pe_eps_performance(res_data, res_data['stock_code'], date, save_path=figs_path)
```

**图表函数**：`finrpt/utils/charting.py` 的 `get_pe_eps_performance()`

**生成方式**：
```python
frame_title6 = draw_frame_title("PE & EPS", color1, 177, font_name)
frame_title6.drawOn(c, A4[0] - 206, A4[1] - 510)  # 标题位置

img = Image(pe_eps_performance_image_path)
img.drawWidth = 170
img.drawHeight = img.drawWidth * (raw_height / raw_width)
img.drawOn(c, A4[0] - 205, A4[1] - 620)  # 图片位置
```

**输出位置**：
- 标题：绝对坐标（x=389, y=332）
- 图片：绝对坐标（x=390, y=222）

---

### 4.6 营业收入图（"单季营业收入及增速"标题）

**位置**：第582-590行

**数据来源**：
```python
# 第341行：调用 charting.py 生成图表
get_revenue_performance(res_data, res_data['stock_code'], date, save_path=figs_path)
```

**图表函数**：`finrpt/utils/charting.py` 的 `get_revenue_performance()`

**生成方式**：
```python
frame_title6 = draw_frame_title("单季营业收入及增速", color1, 177, font_name)
frame_title6.drawOn(c, A4[0] - 206, A4[1] - 645)  # 标题位置

img = Image(revenue_performance_image_path)
img.drawWidth = 170
img.drawHeight = img.drawWidth * (raw_height / raw_width)
img.drawOn(c, A4[0] - 202, A4[1] - 755)  # 图片位置
```

**输出位置**：
- 标题：绝对坐标（x=389, y=197）
- 图片：绝对坐标（x=393, y=87）

---

## 5. 顶部区域（Logo、标题、日期）

**位置**：第380-437行

### 5.1 Logo

```python
# 第397-408行：查找并加载 logo
logo_path = find_logo_path()  # 尝试多个路径
img = Image(logo_path)
img.drawHeight = 40
img.drawOn(c, 40, A4[1] - 70)  # 绝对位置：x=40, y=772
```

### 5.2 公司名称和日期

```python
# 第410-413行
c.drawString(28, A4[1] - 95, f"{company_name}（{stock_code}）")   # x=28, y=747
c.drawString(210, A4[1] - 95, f"{date}")                          # x=210, y=747
```

### 5.3 报告标题

```python
# 第415-437行
title = company_name + ":" + res_data['report_title'] if \
    company_name not in res_data['report_title'] else res_data['report_title']

title_paragraph = Paragraph(title, title_style)
frame_title = Frame(
    x1=160,              # 左边界：160点
    y1=A4[1] - 65,       # 下边界：777点
    width=400,           # 宽度：400点
    height=30,           # 高度：30点
    showBoundary=0
)
frame_title.addFromList([title_paragraph], c)
```

---

## 6. 数据流向总结

```
FinRpt.run()
    │
    ├─→ 收集数据到 data 字典
    │       ├─→ data['analyze_advisor'] = self.advisor.run(...)
    │       ├─→ data['analyze_risk'] = self.risk_assessor.run(...)
    │       ├─→ data['financials'] = self.dataer.get_finacncials_ak(...)
    │       └─→ data['company_info'] = self.dataer.get_company_info(...)
    │
    └─→ build_report(data, date, run_path)
            │
            ├─→ 左侧Frame（核心观点、风险评估、财务表格）
            │       ├─→ res_data['analyze_advisor'] → 核心观点段落
            │       ├─→ res_data['analyze_risk'] → 风险评估段落
            │       └─→ res_data['financials']['stock_income'] → 财务数据表格
            │
            ├─→ 右侧Frame（作者、基本状况、图表）
            │       ├─→ 硬编码 → 作者信息
            │       ├─→ get_key_data() + res_data['company_info'] → 基本状况表格
            │       ├─→ charting.get_share_performance() → 股价走势图
            │       ├─→ charting.get_pe_eps_performance() → PE/EPS图
            │       └─→ charting.get_revenue_performance() → 营业收入图
            │
            └─→ 顶部区域（Logo、标题、日期）
                    ├─→ res_data['company_name'] → 公司名称
                    ├─→ res_data['stock_code'] → 股票代码
                    ├─→ date → 日期
                    └─→ res_data['report_title'] → 报告标题
```

---

## 7. 关键位置坐标汇总

### 7.1 左侧Frame

| 元素 | x坐标 | y坐标（从顶部） | 说明 |
|------|-------|----------------|------|
| Frame左边界 | 25 | - | 固定 |
| Frame右边界 | 385 | - | 固定 |
| 核心观点标题 | 25 | 722 | Frame内顶部 |
| 财务数据标题 | 25 | - | Frame内，风险评估后 |

### 7.2 右侧Frame

| 元素 | x坐标 | y坐标（从顶部） | 说明 |
|------|-------|----------------|------|
| Frame左边界 | 385 | - | 固定 |
| 作者标题 | 389 | 721 | 绝对位置 |
| 作者信息文本 | 395 | 672/652/632 | 绝对位置 |
| 基本状况标题 | 389 | 597 | 绝对位置 |
| 基本状况表格 | 390 | 497 | 绝对位置 |
| 股价走势标题 | 389 | 467 | 绝对位置 |
| 股价走势图 | 390 | 357 | 绝对位置 |
| PE/EPS标题 | 389 | 332 | 绝对位置 |
| PE/EPS图 | 390 | 222 | 绝对位置 |
| 营业收入标题 | 389 | 197 | 绝对位置 |
| 营业收入图 | 393 | 87 | 绝对位置 |

---

## 8. 修改位置的方法

如果要修改某个元素的位置，需要：

1. **Frame内的元素**：修改 `frame_left_list` 或 `frame_right_list` 的顺序，或调整 `Spacer` 的大小
2. **绝对定位的元素**：修改 `drawOn()` 或 `drawString()` 中的坐标参数
3. **图表大小**：修改 `img.drawWidth` 和 `img.drawHeight`

**注意**：坐标系统以**左下角为原点(0,0)**，y轴向上递增。
