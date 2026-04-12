"""
回测共享工具。

把两个脚本里重复的配置、选股、日期处理和结果统计逻辑收敛到同一处。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

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


def load_etf_history(fetcher, indices: Iterable[dict], start_date: str, force_refresh: bool = False) -> Dict[str, pd.DataFrame]:
    data: Dict[str, pd.DataFrame] = {}
    for idx in indices:
        code = idx.get("code")
        etf = idx.get("etf")
        if not code or not etf:
            continue
        df = fetcher.fetch_etf_history(etf, start_date, force_refresh=force_refresh)
        if not df.empty:
            data[code] = df
    return data


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
