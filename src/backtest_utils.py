"""
回测共享工具。

把两个脚本里重复的配置、选股、日期处理和结果统计逻辑收敛到同一处。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

from src.config_loader import load_app_config
from src.portfolio import SimulatedPortfolio


def load_strategy_config(root_dir: Path) -> dict:
    return load_app_config(root_dir)


def resolve_backtest_start_date(config: dict, override_start_date: Optional[str] = None) -> str:
    if override_start_date:
        return override_start_date
    return str(config.get("backtest", {}).get("start_date", "20240101"))


def compute_fetch_start_date(start_date: str, warmup_days: int = 370) -> str:
    start_dt = pd.to_datetime(start_date)
    fetch_start = start_dt - pd.Timedelta(days=warmup_days)
    return fetch_start.strftime("%Y%m%d")


def create_portfolio(config: dict, initial_capital: Optional[float] = None) -> SimulatedPortfolio:
    portfolio_config = config.get("portfolio", {})
    stop_loss_config = config.get("stop_loss", {})
    return SimulatedPortfolio(
        initial_capital=initial_capital or portfolio_config.get("initial_capital", 1_000_000),
        commission_rate=portfolio_config.get("commission", 0.0003),
        slippage=portfolio_config.get("slippage", 0.001),
        stop_loss_config=stop_loss_config or None,
        cooldown_days=stop_loss_config.get("cooldown_days", 5) if stop_loss_config else 5,
    )


def load_etf_history(
    fetcher,
    indices: Iterable[dict],
    start_date: str,
    force_refresh: bool = False,
    allow_stale_cache: bool = False,
) -> Dict[str, pd.DataFrame]:
    data: Dict[str, pd.DataFrame] = {}
    for idx in indices:
        code = idx.get("code")
        etf = idx.get("etf")
        if not code or not etf:
            continue
        df = fetcher.fetch_etf_history(
            etf,
            start_date,
            force_refresh=force_refresh,
            allow_stale_cache=allow_stale_cache,
        )
        if not df.empty:
            data[code] = df
    return data


def validate_etf_history_coverage(
    data: Dict[str, pd.DataFrame],
    indices: Iterable[dict],
    start_date: str,
    min_history_days: int = 120,
    required_price_mode: Optional[str] = None,
) -> List[str]:
    issues: List[str] = []
    start_ts = pd.to_datetime(start_date)
    for idx in indices:
        code = idx.get("code")
        etf = idx.get("etf")
        name = idx.get("name", code or "")
        df = data.get(code or "")
        if not code or not etf:
            continue
        if df is None or df.empty:
            issues.append(f"{code} {name} ({etf}) 缺少历史行情")
            continue
        sliced = df[df.index >= start_ts]
        if len(sliced) < min_history_days:
            issues.append(f"{code} {name} ({etf}) 行情天数不足: {len(sliced)}")
        price_mode_used = str(df.attrs.get("adjust_used", "") or "")
        if required_price_mode and price_mode_used != required_price_mode:
            issues.append(
                f"{code} {name} ({etf}) 数据口径不一致: 需要 {required_price_mode}, 实际 {price_mode_used or 'unknown'}"
            )
    return issues


def load_flow_supporting_data(
    fetcher,
    indices: Iterable[dict],
    start_date: str,
) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    northbound_df = fetcher.fetch_northbound_flow(start_date)
    etf_shares_data: Dict[str, pd.DataFrame] = {}
    for idx in indices:
        code = idx.get("code")
        etf = idx.get("etf")
        if not code or not etf:
            continue
        shares_df = fetcher.fetch_etf_shares(etf, start_date)
        if not shares_df.empty:
            etf_shares_data[code] = shares_df
    return northbound_df, etf_shares_data


def slice_flow_metrics(
    fetcher,
    code: str,
    date: pd.Timestamp,
    northbound_df: Optional[pd.DataFrame],
    etf_shares_data: Dict[str, pd.DataFrame],
) -> Tuple[Optional[dict], Optional[dict]]:
    northbound_metrics = None
    etf_shares_metrics = None

    if northbound_df is not None and not northbound_df.empty:
        nb_slice = northbound_df.loc[:date]
        if not nb_slice.empty:
            northbound_metrics = fetcher.calc_northbound_metrics(nb_slice)

    shares_df = etf_shares_data.get(code)
    if shares_df is not None and not shares_df.empty:
        shares_slice = shares_df.loc[:date]
        if not shares_slice.empty:
            etf_shares_metrics = fetcher.calc_etf_shares_metrics(shares_slice)

    return northbound_metrics, etf_shares_metrics


def select_rebalance_dates(trade_dates: List[pd.Timestamp], rebalance_frequency: str) -> List[pd.Timestamp]:
    rebalance_dates: List[pd.Timestamp] = []
    for date in trade_dates:
        if is_rebalance_day(date, rebalance_frequency):
            rebalance_dates.append(date)
        elif rebalance_frequency not in {"weekly", "monthly"}:
            rebalance_dates.append(date)
    return rebalance_dates or trade_dates[:1]


def is_rebalance_day(date: pd.Timestamp, rebalance_frequency: str) -> bool:
    if rebalance_frequency == "weekly":
        return date.weekday() == 0
    if rebalance_frequency == "monthly":
        return date.day <= 5
    return True


def build_rebalance_signals(ranking: pd.DataFrame, current_codes: set[str], top_n: int, buffer_n: int) -> Dict[str, List[str]]:
    if ranking.empty:
        return {"buy": [], "sell": []}
    selected = ranking.head(top_n)["code"].tolist()
    hold_range = ranking.head(buffer_n)["code"].tolist()
    return {
        "buy": [code for code in selected if code not in current_codes],
        "sell": [code for code in current_codes if code not in hold_range],
    }


def build_rebalance_targets(ranking: pd.DataFrame, current_codes: set[str], top_n: int, buffer_n: int) -> List[str]:
    """目标持仓集合：新买前 top_n，已有持仓在 buffer_n 内则继续持有。"""
    if ranking.empty:
        return []
    selected = ranking.head(top_n)["code"].tolist()
    hold_range = set(ranking.head(buffer_n)["code"].tolist())
    target_codes = list(selected)
    for code in ranking["code"].tolist():
        if code in current_codes and code in hold_range and code not in target_codes:
            target_codes.append(code)
    return target_codes


def compute_backtest_metrics(values_df: pd.DataFrame, initial_capital: float) -> pd.DataFrame:
    metrics_df = values_df.copy()
    metrics_df["date"] = pd.to_datetime(metrics_df["date"])
    metrics_df["return"] = metrics_df["value"].pct_change()
    metrics_df["cum_return"] = (1 + metrics_df["return"]).cumprod() - 1
    metrics_df["rolling_max"] = metrics_df["value"].cummax()
    metrics_df["drawdown"] = (metrics_df["value"] - metrics_df["rolling_max"]) / metrics_df["rolling_max"]

    final_value = metrics_df["value"].iloc[-1]
    total_return = (final_value - initial_capital) / initial_capital
    days = (metrics_df["date"].iloc[-1] - metrics_df["date"].iloc[0]).days
    years = days / 365 if days > 0 else 0
    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else total_return

    daily_returns = metrics_df["return"].dropna()
    sharpe = daily_returns.mean() / daily_returns.std() * (252 ** 0.5) if len(daily_returns) > 20 else 0
    max_drawdown = metrics_df["drawdown"].min() if not metrics_df.empty else 0

    metrics_df["sharpe"] = sharpe
    metrics_df["max_dd"] = max_drawdown
    metrics_df.attrs["summary"] = {
        "final_value": final_value,
        "total_return": total_return,
        "annual_return": annual_return,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "trading_days": len(metrics_df),
    }
    return metrics_df
