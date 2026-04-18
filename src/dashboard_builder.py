"""
前端数据构建器。

把 generate_data.py 中重复的策略初始化、排名映射和推荐拼装逻辑沉到 src 层。
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd

from src.strategy_baostock import RotationStrategy
from src.strategy_summary import build_strategy_summary


class DashboardDataBuilder:
    def __init__(self, root_dir: Path, strategy: Optional[RotationStrategy] = None):
        self.root_dir = root_dir
        self.strategy = strategy or RotationStrategy()
        self.config = self.strategy.config
        self.indices = self.config.get("indices", [])
        factor_model = self.config.get("factor_model", {})
        self.active_factors = factor_model.get("active_factors", ["momentum", "trend", "flow"])
        self.auxiliary_factors = factor_model.get("auxiliary_factors", [])
        self.factor_weights = self.config.get("factor_weights", {})

    def prepare(self) -> tuple[Dict[str, pd.DataFrame], pd.DataFrame]:
        self.strategy.load_benchmark()
        data_dict = self.strategy.fetch_all_data()
        ranking_df = self.strategy.run_scoring(data_dict)
        return data_dict, ranking_df

    def generate_backtest_data(self) -> dict:
        parquet_file = self.root_dir / "backtest_results" / "current.parquet"
        if not parquet_file.exists():
            return {"summary": {}, "chart_data": []}

        df = pd.read_parquet(parquet_file).copy()
        df["date"] = pd.to_datetime(df["date"])

        if "drawdown" not in df.columns:
            df["rolling_max"] = df["value"].cummax()
            df["drawdown"] = (df["value"] - df["rolling_max"]) / df["rolling_max"]
        if "return" not in df.columns:
            df["return"] = df["value"].pct_change()
        if "cum_return" not in df.columns:
            df["cum_return"] = (df["value"] / df["value"].iloc[0]) - 1

        initial_capital = df["value"].iloc[0]
        final_value = df["value"].iloc[-1]
        total_return = (final_value - initial_capital) / initial_capital
        days = (df["date"].iloc[-1] - df["date"].iloc[0]).days
        years = days / 365
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else total_return
        max_drawdown = df["drawdown"].min()
        max_drawdown_date = df.loc[df["drawdown"].idxmin(), "date"]
        daily_returns = df["return"].dropna()
        sharpe = daily_returns.mean() / daily_returns.std() * (252 ** 0.5) if len(daily_returns) > 20 else 0

        chart_data = [
            {
                "date": row["date"].strftime("%Y-%m-%d"),
                "value": round(row["value"], 2),
                "cum_return": round(row["cum_return"], 4) if pd.notna(row["cum_return"]) else 0,
                "drawdown": round(row["drawdown"], 4) if pd.notna(row["drawdown"]) else 0,
            }
            for _, row in df.iterrows()
        ]
        return {
            "summary": {
                "initial_capital": initial_capital,
                "final_value": round(final_value, 2),
                "total_return": round(total_return, 4),
                "annual_return": round(annual_return, 4),
                "max_drawdown": round(max_drawdown, 4),
                "max_drawdown_date": max_drawdown_date.strftime("%Y-%m-%d") if pd.notna(max_drawdown_date) else "",
                "sharpe_ratio": round(sharpe, 2),
                "trading_days": len(df),
                "period": {
                    "start": df["date"].iloc[0].strftime("%Y-%m-%d"),
                    "end": df["date"].iloc[-1].strftime("%Y-%m-%d"),
                },
            },
            "chart_data": chart_data,
        }

    def _index_info(self, code: str) -> dict:
        return next((idx for idx in self.indices if idx.get("code") == code), {})

    def _extract_factors(self, row: pd.Series) -> dict:
        factors = {}
        for factor in self.active_factors:
            value = row.get(factor)
            factors[factor] = round(float(value), 4) if pd.notna(value) else 0.5
        return factors

    def ranking_to_payload(self, ranking_df: pd.DataFrame) -> list[dict]:
        payload = []
        for _, row in ranking_df.iterrows():
            code = row["code"]
            idx_info = self._index_info(code)
            payload.append(
                {
                    "code": code,
                    "name": idx_info.get("name", code),
                    "etf": idx_info.get("etf", ""),
                    "rank": int(row["rank"]),
                    "score": round(float(row["total_score"]), 4),
                    "factors": self._extract_factors(row),
                    "attribution": row.get("attribution", {}),
                }
            )
        return payload

    def generate_history_data(self, etf_data_dict: Dict[str, pd.DataFrame], weeks: int = 12) -> list[dict]:
        end_date = pd.Timestamp.now().normalize()
        start_date = end_date - pd.Timedelta(days=weeks * 7 + 7)
        dates = pd.date_range(start_date, end_date, freq="W-MON")
        history = []

        active_indices = [idx for idx in self.indices if idx.get("enabled", True)]
        first_code = active_indices[0]["code"] if active_indices else None
        if not first_code or first_code not in etf_data_dict:
            return history

        trade_index = pd.DatetimeIndex(etf_data_dict[first_code].index).sort_values().normalize().unique()
        if len(trade_index) == 0:
            return history

        for date in dates:
            anchor_date = pd.Timestamp(date).normalize()
            trade_pos = trade_index.searchsorted(anchor_date, side="right") - 1
            if trade_pos < 0:
                continue

            trade_date = trade_index[trade_pos]
            if (anchor_date - trade_date).days > 10:
                continue

            data_dict = {}
            for code, df in etf_data_dict.items():
                df_cutoff = df[df.index <= trade_date]
                if len(df_cutoff) >= 60:
                    data_dict[code] = df_cutoff.tail(252)
            if not data_dict:
                continue

            benchmark_data = None
            if self.strategy.benchmark_data is not None and not self.strategy.benchmark_data.empty:
                benchmark_data = self.strategy.benchmark_data[self.strategy.benchmark_data.index <= trade_date]

            scores_dict = {}
            for code, df in data_dict.items():
                scores_dict[code] = self.strategy.scorer.score_index(df, benchmark_data)

            ranking_df = self.strategy.scorer.rank_indices(scores_dict)
            if ranking_df.empty:
                continue

            holdings = []
            for _, row in ranking_df.head(self.strategy.top_n).iterrows():
                code = row["code"]
                idx_info = self._index_info(code)
                holdings.append(
                    {
                        "code": code,
                        "name": idx_info.get("name", code),
                        "etf": idx_info.get("etf", ""),
                        "rank": int(row["rank"]),
                        "score": round(float(row["total_score"]), 4),
                        "factors": self._extract_factors(row),
                    }
                )

            history.append({"date": trade_date.strftime("%Y-%m-%d"), "holdings": holdings})

        history.sort(key=lambda item: item["date"], reverse=True)
        return history

    def generate_recommendation(self, ranking_df: pd.DataFrame, history: list[dict]) -> dict:
        prev_holdings = {item["code"] for item in history[0].get("holdings", [])} if history else set()
        recommendation = self.strategy.build_recommendation(ranking_df, signals=[])

        selected_codes = recommendation.get("selected_codes", [])
        hold_range_codes = set(recommendation.get("hold_range_codes", []))
        signals = []
        for code in sorted(prev_holdings):
            if code not in hold_range_codes:
                idx_info = self._index_info(code)
                signals.append({"action": "sell", "code": code, "name": idx_info.get("name", code)})
        for code in selected_codes:
            if code not in prev_holdings:
                idx_info = self._index_info(code)
                signals.append({"action": "buy", "code": code, "name": idx_info.get("name", code)})

        recommendation["signals"] = signals
        return recommendation

    def generate_universe(self) -> dict:
        active = list(self.indices)
        inactive = list(self.config.get("inactive_indices", []))
        return {
            "active": [{"code": idx["code"], "name": idx.get("name", idx["code"]), "etf": idx.get("etf", "")} for idx in active],
            "inactive": [{"code": idx["code"], "name": idx.get("name", idx["code"]), "etf": idx.get("etf", "")} for idx in inactive],
        }

    def build_payloads(self) -> tuple[dict, dict]:
        data_dict, ranking_df = self.prepare()
        backtest = self.generate_backtest_data()
        current_health = deepcopy(self.strategy.data_health)
        history = self.generate_history_data(data_dict)
        ranking = self.ranking_to_payload(ranking_df)
        recommendation = self.generate_recommendation(ranking_df, history)
        health = current_health
        universe = self.generate_universe()
        update_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        market_regime = getattr(self.strategy.scorer, "current_regime", "sideways")
        market_regime_desc = {"bull": "多头市", "bear": "空头市", "sideways": "震荡市"}.get(market_regime, market_regime)
        summary = build_strategy_summary(
            root_dir=self.root_dir,
            indices=self.indices,
            inactive_indices=self.config.get("inactive_indices", []),
            recommendation=recommendation,
            health=health,
            market_regime=market_regime,
            market_regime_desc=market_regime_desc,
            update_time=update_time,
            backtest_summary=backtest.get("summary"),
        )

        combined = {
            "backtest": backtest,
            "history": history,
            "ranking": ranking,
            "recommendation": recommendation,
            "health": health,
            "universe": universe,
            "strategy_summary": summary,
            "update_time": update_time,
            "market_regime": market_regime,
            "market_regime_desc": market_regime_desc,
            "factor_weights": self.factor_weights,
            "factor_model": {
                "active_factors": self.active_factors,
                "auxiliary_factors": self.auxiliary_factors,
            },
        }
        ranking_output = {
            "ranking": ranking,
            "recommendation": recommendation,
            "health": health,
            "universe": universe,
            "strategy_summary": summary,
            "factor_weights": self.factor_weights,
            "factor_model": {
                "active_factors": self.active_factors,
                "auxiliary_factors": self.auxiliary_factors,
            },
            "dynamic_weights": getattr(self.strategy.scorer, "current_weights", {}),
            "market_regime": market_regime,
            "market_regime_desc": market_regime_desc,
            "strategy": self.config.get("strategy", {}),
            "update_time": update_time,
        }
        return combined, ranking_output

    def write_outputs(self, output_dir: Path) -> tuple[Path, Path]:
        combined, ranking_output = self.build_payloads()
        output_dir.mkdir(parents=True, exist_ok=True)
        data_path = output_dir / "data.json"
        ranking_path = output_dir / "ranking.json"
        history_path = output_dir / "history.json"
        backtest_path = output_dir / "backtest.json"
        data_path.write_text(json.dumps(_json_safe(combined), indent=2, ensure_ascii=False), encoding="utf-8")
        ranking_path.write_text(json.dumps(_json_safe(ranking_output), indent=2, ensure_ascii=False), encoding="utf-8")
        history_path.write_text(
            json.dumps(
                _json_safe(
                    {
                        "history": combined.get("history", []),
                        "update_time": combined.get("update_time", ""),
                    }
                ),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        backtest_path.write_text(
            json.dumps(_json_safe(combined.get("backtest", {})), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return data_path, ranking_path

    def close(self) -> None:
        self.strategy.close()


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value
