# Massive API 集成指南

## 概述

Massive API (原 Polygon.io) 提供美国股票市场数据，包括：
- **REST API**: 实时和历史数据查询
- **WebSocket**: 实时数据流
- **Flat Files (S3)**: 大量历史数据文件（CSV格式）

## 当前测试状态

✅ **S3 Flat Files 连接测试通过**
- 成功连接到 `https://files.massive.com`
- 可以列出和访问历史数据文件
- 测试文件：`tests/test_massive_api.py`

## 数据可用性

### 可用的数据类型

1. **Day Aggregates** (每日聚合数据)
   - 路径: `us_stocks_sip/day_aggs_v1/{year}/{month}/{date}.csv.gz`
   - 数据: OHLCV (开盘、最高、最低、收盘、成交量)
   - 历史数据: 从2003年开始

2. **Trades** (交易数据)
   - 路径: `us_stocks_sip/trades_v1/{year}/{month}/{date}.csv.gz`
   - 数据: 每笔交易的详细信息

3. **Quotes** (报价数据)
   - 路径: `us_stocks_sip/quotes_v1/{year}/{month}/{date}.csv.gz`
   - 数据: 买卖报价信息

4. **Minute Aggregates** (分钟聚合数据)
   - 路径: `us_stocks_sip/min_aggs_v1/{year}/{month}/{date}.csv.gz`
   - 数据: 每分钟的OHLCV

### 数据格式

CSV文件包含以下列：
```
ticker,volume,open,close,high,low,window_start,transactions
AAPL,4930,200.29,200.5,200.63,200.29,1744792500000000000,129
```

- `ticker`: 股票代码
- `volume`: 成交量
- `open`, `close`, `high`, `low`: OHLC价格
- `window_start`: Unix时间戳（纳秒）
- `transactions`: 交易笔数

## 环境变量配置

`.env` 文件中需要配置：

```env
# Massive API S3 configuration
MASSIVE_S3_ACCESS_KEY=your_s3_access_key
MASSIVE_S3_SECRET_KEY=your_s3_secret_key
MASSIVE_S3_ENDPOINT=https://files.massive.com
MASSIVE_S3_BUCKET=flatfiles
```

## 使用示例

### 1. 列出可用文件

```python
import boto3
from botocore.config import Config
import os

# 创建S3客户端
session = boto3.Session(
    aws_access_key_id=os.getenv('MASSIVE_S3_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('MASSIVE_S3_SECRET_KEY'),
)

s3 = session.client(
    's3',
    endpoint_url='https://files.massive.com',
    config=Config(signature_version='s3v4'),
)

# 列出US股票数据
response = s3.list_objects_v2(
    Bucket='flatfiles',
    Prefix='us_stocks_sip/day_aggs_v1/2025/01/',
    MaxKeys=10
)

for obj in response['Contents']:
    print(obj['Key'])
```

### 2. 下载文件

```python
# 下载特定日期的数据
object_key = 'us_stocks_sip/day_aggs_v1/2025/01/2025-01-17.csv.gz'
local_file = '2025-01-17.csv.gz'

s3.download_file('flatfiles', object_key, local_file)
```

### 3. 读取CSV数据

```python
import pandas as pd
import gzip

# 解压并读取CSV
with gzip.open('2025-01-17.csv.gz', 'rt') as f:
    df = pd.read_csv(f)

# 过滤特定股票
aapl_data = df[df['ticker'] == 'AAPL']
print(aapl_data)
```

## 集成到项目

### 选项1: 添加到 Dataer 类

可以在 `finrpt/source/Dataer.py` 中添加新方法：

```python
def get_finacncials_massive(self, stock_code, end_date, start_date=None):
    """Get financials data using Massive API (US stocks only)"""
    import boto3
    from botocore.config import Config
    import pandas as pd
    import gzip
    import tempfile
    
    # 创建S3客户端
    session = boto3.Session(
        aws_access_key_id=os.getenv('MASSIVE_S3_ACCESS_KEY'),
        aws_secret_access_key=os.getenv('MASSIVE_S3_SECRET_KEY'),
    )
    
    s3 = session.client(
        's3',
        endpoint_url=os.getenv('MASSIVE_S3_ENDPOINT', 'https://files.massive.com'),
        config=Config(signature_version='s3v4'),
    )
    
    bucket = os.getenv('MASSIVE_S3_BUCKET', 'flatfiles')
    
    # 下载并处理数据
    # ... (实现数据获取逻辑)
    
    return result
```

### 选项2: 替换 yfinance

对于美国股票，可以选择使用Massive API而不是yfinance：
- ✅ 更可靠（直接从交易所数据）
- ✅ 更多历史数据
- ✅ 更详细的数据（trades, quotes）
- ❌ 需要下载和处理CSV文件（比API调用慢）

## REST API 使用

Massive 也提供 REST API（类似原Polygon.io）：

```
https://api.massive.com/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}
```

需要API key（可能不同与S3 credentials）。

## 测试

运行测试验证Massive API访问：

```bash
export MASSIVE_S3_ACCESS_KEY=your_key
export MASSIVE_S3_SECRET_KEY=your_secret
pytest tests/test_massive_api.py -v -s
```

## 注意事项

1. **数据可用时间**: 当日数据通常在第二天11:00 AM ET后可用
2. **数据调整**: Flat Files包含未调整数据（未考虑拆股、分红等）
3. **时区**: 时间戳是UTC，需要转换为ET进行分析
4. **文件大小**: CSV文件可能很大，需要足够存储空间
5. **权限**: 某些数据可能需要特定的订阅计划

## 下一步

1. ✅ 确认Massive API访问（测试通过）
2. 决定如何使用：
   - 选项A: 继续使用yfinance（简单，但可能不稳定）
   - 选项B: 使用Massive REST API（需要API key）
   - 选项C: 使用Massive Flat Files（需要下载和处理CSV）
3. 如需要，集成到 `Dataer` 类中
