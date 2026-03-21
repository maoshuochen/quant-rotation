#!/usr/bin/env python3
"""
回测脚本 - AKShare 版本（获取长期数据）
"""
import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import logging
import pandas as pd
import numpy as np
from datetime import datetime
import yaml
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def load_config() -> dict:
    config_path = root_dir / 'config' / 'config.yaml'
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}


def fetch_etf_data_akshare(etf_code: str, start_date: str = "20240101") -> pd.DataFrame:
    """使用 AKShare 获取 ETF 历史行情"""
    try:
        import akshare as ak
        
        # 使用 Sina 接口（更稳定）
        df = ak.fund_etf_hist_sina(symbol=f"sh{etf_code}" if len(etf_code) == 6 else etf_code)
        
        if df.empty:
            return df
        
        # 数据清洗
        df = df.rename(columns={
            '日期': 'date',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'volume',
            '成交额': 'amount'
        })
        
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date').sort_index()
        
        # 转换数值列
        for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        logger.info(f"AKShare 获取 {etf_code} 成功：{len(df)} rows")
        return df
        
    except Exception as e:
        logger.error(f"获取 {etf_code} 失败：{e}")
        return pd.DataFrame()


def calculate_momentum(prices: pd.Series, window: int = 126) -> float:
    """动量因子：过去 N 天收益率"""
    if len(prices) < window:
        return 0.5
    return (prices.iloc[-1] / prices.iloc[-window] - 1)


def calculate_volatility(prices: pd.Series) -> float:
    """波动因子：年化波动率（越低越好）"""
    if len(prices) < 60:
        return 0.5
    returns = prices.pct_change().dropna()
    ann_vol = returns.std() * np.sqrt(252)
    # 归一化到 0-1，波动越低分数越高
    return max(0, min(1, 1 - ann_vol))


def calculate_trend(prices: pd.Series) -> float:
    """趋势因子：价格相对 MA20/MA60 位置"""
    if len(prices) < 60:
        return 0.5
    ma20 = prices.rolling(20).mean().iloc[-1]
    ma60 = prices.rolling(60).mean().iloc[-1]
    current = prices.iloc[-1]
    
    # 价格在均线上方越多越好
    score = 0
    if current > ma20:
        score += 0.5
    if current > ma60:
        score += 0.5
    return score


def calculate_value(prices: pd.Series, lookback: int = 2520) -> float:
    """估值因子：价格历史分位（越低越好）"""
    if len(prices) < 252:
        return 0.5
    window = min(lookback, len(prices))
    recent = prices.tail(window)
    current = prices.iloc[-1]
    
    # 计算分位点
    percentile = (recent < current).sum() / len(recent)
    # 分位越低（越便宜）分数越高
    return 1 - percentile


def calculate_relative_strength(prices: pd.Series, benchmark: pd.Series) -> float:
    """相对强弱：相对基准的表现"""
    if len(prices) < 60 or len(benchmark) < 60:
        return 0.5
    
    # 对齐日期
    common_idx = prices.index.intersection(benchmark.index)
    if len(common_idx) < 60:
        return 0.5
    
    p = prices.loc[common_idx]
    b = benchmark.loc[common_idx]
    
    # 过去 60 天相对收益
    ret_p = (p.iloc[-1] / p.iloc[-60]) - 1
    ret_b = (b.iloc[-1] / b.iloc[-60]) - 1
    
    # 相对强弱
    relative = ret_p - ret_b
    # 归一化到 0-1
    return max(0, min(1, 0.5 + relative))


def score_index(prices: pd.Series, benchmark: pd.Series, config: dict) -> dict:
    """计算综合评分"""
    strategy = config.get('strategy', {})
    weights = config.get('factor_weights', {})
    
    # 计算各因子得分
    scores = {
        'momentum': calculate_momentum(prices, strategy.get('momentum_window', 126)),
        'volatility': calculate_volatility(prices),
        'trend': calculate_trend(prices),
        'value': calculate_value(prices, strategy.get('lookback_pe', 2520)),
        'relative_strength': calculate_relative_strength(prices, benchmark)
    }
    
    # 加权综合得分
    total_score = 0
    for factor, weight in weights.items():
        if factor in scores:
            total_score += scores[factor] * weight
    
    scores['total'] = total_score
    return scores


def run_backtest(start_date: str = "20240101", 
                 end_date: str = None,
                 initial_capital: float = 1_000_000):
    """运行回测"""
    config = load_config()
    end_date = end_date or datetime.now().strftime('%Y%m%d')
    
    logger.info("=" * 60)
    logger.info(f"回测期间：{start_date} ~ {end_date}")
    logger.info(f"初始资金：{initial_capital:,.0f}")
    logger.info("=" * 60)
    
    # 获取 ETF 数据
    indices = config.get('indices', [])
    etf_data = {}
    
    for idx in indices:
        etf = idx.get('etf')
        code = idx.get('code')
        if etf:
            df = fetch_etf_data_akshare(etf, start_date)
            if not df.empty:
                etf_data[code] = df['close']
                logger.info(f"  {code} ({etf}): {len(df)} rows")
    
    if not etf_data:
        logger.error("没有获取到任何数据!")
        return
    
    # 基准（沪深 300）
    benchmark = etf_data.get('000300.SH', pd.Series())
    
    # 合并所有日期
    all_dates = pd.DataFrame(etf_data).index.sort_values()
    
    # 筛选日期范围
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    trade_dates = [d for d in all_dates if start_dt <= d <= end_dt]
    
    if not trade_dates:
        logger.error("没有交易日期!")
        return
    
    logger.info(f"交易日期数：{len(trade_dates)}")
    
    # 调仓日期（每周一）
    rebalance_dates = [d for d in trade_dates if d.weekday() == 0]
    if not rebalance_dates:
        rebalance_dates = [trade_dates[0]]
    
    logger.info(f"调仓次数：{len(rebalance_dates)}")
    
    # 策略参数
    strategy = config.get('strategy', {})
    top_n = strategy.get('top_n', 5)
    buffer_n = strategy.get('buffer_n', 8)
    
    # 初始化
    cash = initial_capital
    positions = {}  # code -> shares
    daily_values = []
    commission_rate = config.get('portfolio', {}).get('commission', 0.0003)
    slippage = config.get('portfolio', {}).get('slippage', 0.001)
    
    # 回测循环
    for i, date in enumerate(trade_dates):
        date_str = date.strftime('%Y-%m-%d')
        
        # 获取当日价格
        prices = {code: series.loc[date] for code, series in etf_data.items() if date in series.index}
        
        if not prices:
            continue
        
        # 计算当日净值
        stock_value = sum(positions.get(code, 0) * prices.get(code, 0) for code in positions)
        total_value = cash + stock_value
        daily_values.append({'date': date_str, 'value': total_value, 'cash': cash})
        
        # 调仓日
        if date in rebalance_dates and i > 20:  # 至少 20 天数据
            logger.info(f"\n调仓日：{date_str}")
            
            # 计算评分
            scores_dict = {}
            for code, series in etf_data.items():
                hist = series[series.index <= date]
                if len(hist) >= 20:
                    scores = score_index(hist, benchmark[benchmark.index <= date], config)
                    scores_dict[code] = scores
            
            # 排名
            ranking = sorted(scores_dict.items(), key=lambda x: x[1]['total'], reverse=True)
            
            if not ranking:
                continue
            
            # 选中前 top_n
            selected = [code for code, _ in ranking[:top_n]]
            hold_range = [code for code, _ in ranking[:buffer_n]]
            
            logger.info(f"  选中：{selected}")
            
            # 卖出不在持有范围的
            to_sell = [code for code in positions if code not in hold_range]
            for code in to_sell:
                shares = positions[code]
                price = prices.get(code, 0)
                if price > 0:
                    amount = shares * price * (1 - slippage) * (1 - commission_rate)
                    cash += amount
                    logger.info(f"  SELL {code}: {shares} @ {price:.3f}")
                del positions[code]
            
            # 买入选中的（等权重）
            to_buy = [code for code in selected if code not in positions]
            if to_buy:
                available = cash * 0.95  # 留 5% 现金
                per_stock = available / len(to_buy)
                
                for code in to_buy:
                    price = prices.get(code, 0)
                    if price > 0:
                        exec_price = price * (1 + slippage)
                        shares = int(per_stock / exec_price / 100) * 100  # 整百股
                        if shares > 0:
                            cost = shares * exec_price * (1 + commission_rate)
                            if cost <= cash:
                                cash -= cost
                                positions[code] = shares
                                logger.info(f"  BUY {code}: {shares} @ {exec_price:.3f}")
    
    # 结果统计
    values_df = pd.DataFrame(daily_values)
    values_df['date'] = pd.to_datetime(values_df['date'])
    values_df['return'] = values_df['value'].pct_change()
    values_df['cum_return'] = (1 + values_df['return']).cumprod() - 1
    values_df['rolling_max'] = values_df['value'].cummax()
    values_df['drawdown'] = (values_df['value'] - values_df['rolling_max']) / values_df['rolling_max']
    
    final_value = values_df['value'].iloc[-1]
    total_return = (final_value - initial_capital) / initial_capital
    
    days = (values_df['date'].iloc[-1] - values_df['date'].iloc[0]).days
    years = days / 365
    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else total_return
    
    max_drawdown = values_df['drawdown'].min()
    
    daily_returns = values_df['return'].dropna()
    sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(252) if len(daily_returns) > 20 else 0
    
    print(f"\n📊 回测结果")
    print(f"  初始资金：{initial_capital:,.0f}")
    print(f"  最终价值：{final_value:,.0f}")
    print(f"  总收益率：{total_return*100:.2f}%")
    print(f"  年化收益：{annual_return*100:.2f}%")
    print(f"  最大回撤：{max_drawdown*100:.2f}%")
    print(f"  夏普比率：{sharpe:.2f}")
    print(f"  交易天数：{len(values_df)}")
    print(f"  调仓次数：{len(rebalance_dates)}")
    
    # 保存结果
    results_dir = root_dir / 'backtest_results'
    results_dir.mkdir(exist_ok=True)
    result_file = results_dir / f'backtest_akshare_{start_date}_{end_date}.csv'
    values_df.to_csv(result_file, index=False)
    logger.info(f"\n结果已保存：{result_file}")
    
    # 生成 JSON 供前端使用
    chart_data = []
    for _, row in values_df.iterrows():
        chart_data.append({
            'date': row['date'].strftime('%Y-%m-%d'),
            'value': round(row['value'], 2),
            'cum_return': round(row['cum_return'], 4) if pd.notna(row['cum_return']) else 0,
            'drawdown': round(row['drawdown'], 4) if pd.notna(row['drawdown']) else 0
        })
    
    output = {
        'summary': {
            'initial_capital': initial_capital,
            'final_value': round(final_value, 2),
            'total_return': round(total_return, 4),
            'annual_return': round(annual_return, 4),
            'max_drawdown': round(max_drawdown, 4),
            'sharpe_ratio': round(sharpe, 2),
            'trading_days': len(values_df),
            'period': {
                'start': values_df['date'].iloc[0].strftime('%Y-%m-%d'),
                'end': values_df['date'].iloc[-1].strftime('%Y-%m-%d')
            }
        },
        'chart_data': chart_data
    }
    
    json_file = root_dir / 'web' / 'dist' / 'backtest.json'
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    logger.info(f"前端数据已更新：{json_file}")


if __name__ == "__main__":
    start = sys.argv[1] if len(sys.argv) > 1 else "20240101"
    end = sys.argv[2] if len(sys.argv) > 2 else None
    run_backtest(start, end)
