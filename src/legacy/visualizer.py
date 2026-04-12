#!/usr/bin/env python3
"""
可视化报告生成器

功能:
1. 权益曲线图
2. 回撤分布图
3. 持仓热力图
4. 因子贡献分解
5. 月度收益 heatmap
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class ReportGenerator:
    """可视化报告生成器"""
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_all(self, 
                     equity_curve: pd.DataFrame,
                     trades: pd.DataFrame,
                     daily_scores: Optional[pd.DataFrame] = None,
                     report_name: str = "backtest_report"):
        """生成所有报告"""
        logger.info("Generating reports...")
        
        # 1. 权益曲线图
        self.plot_equity_curve(equity_curve, f"{report_name}_equity_curve.png")
        
        # 2. 回撤分布图
        self.plot_drawdown_distribution(equity_curve, f"{report_name}_drawdown.png")
        
        # 3. 月度收益 Heatmap
        self.plot_monthly_returns(equity_curve, f"{report_name}_monthly_heatmap.png")
        
        # 4. 持仓分布
        if not trades.empty:
            self.plot_position_distribution(trades, f"{report_name}_positions.png")
        
        # 5. 交易记录表
        if not trades.empty:
            self.save_trades_table(trades, f"{report_name}_trades.html")
        
        # 6. 综合报告 HTML
        self.generate_html_report(equity_curve, trades, f"{report_name}_summary.html")
        
        logger.info(f"Reports saved to {self.output_dir}")
    
    def plot_equity_curve(self, df: pd.DataFrame, filename: str):
        """绘制权益曲线图"""
        try:
            import matplotlib.pyplot as plt
            from matplotlib import font_manager
            import matplotlib
            
            # 设置中文字体
            plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
            
            fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
            
            # 1. 权益曲线
            ax1 = axes[0]
            ax1.plot(df.index, df['equity'], 'b-', linewidth=1.5, label='组合价值')
            
            # 添加初始资金参考线
            initial = df['equity'].iloc[0]
            ax1.axhline(y=initial, color='gray', linestyle='--', alpha=0.5, label=f'初始资金 {initial:,.0f}')
            
            ax1.set_ylabel('组合价值')
            ax1.set_title('权益曲线')
            ax1.legend(loc='upper left')
            ax1.grid(True, alpha=0.3)
            
            # 标注最终值
            final = df['equity'].iloc[-1]
            total_return = (final - initial) / initial * 100
            ax1.annotate(f'最终：{final:,.0f}\n收益：{total_return:+.1f}%',
                        xy=(0.98, 0.02), xycoords='axes fraction',
                        fontsize=10, verticalalignment='bottom', horizontalalignment='right',
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
            
            # 2. 回撤曲线
            ax2 = axes[1]
            ax2.fill_between(df.index, df['drawdown']*100, 0, color='red', alpha=0.3, label='回撤')
            ax2.set_ylabel('回撤 %')
            ax2.set_title('回撤分析')
            ax2.legend(loc='lower left')
            ax2.grid(True, alpha=0.3)
            
            # 标注最大回撤
            max_dd = df['drawdown'].min() * 100
            max_dd_idx = df['drawdown'].idxmin()
            ax2.annotate(f'最大回撤：{max_dd:.1f}%',
                        xy=(max_dd_idx, max_dd),
                        xytext=(0.02, 0.98), textcoords='axes fraction',
                        fontsize=10, verticalalignment='top', horizontalalignment='left',
                        bbox=dict(boxstyle='round', facecolor='salmon', alpha=0.5))
            
            # 3. 每日收益
            ax3 = axes[2]
            daily_returns = df['equity'].pct_change() * 100
            colors = ['green' if r > 0 else 'red' for r in daily_returns]
            ax3.bar(df.index, daily_returns, color=colors, alpha=0.5, width=1)
            ax3.set_ylabel('日收益 %')
            ax3.set_title('每日收益分布')
            ax3.grid(True, alpha=0.3)
            ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            
            plt.xlabel('日期')
            plt.tight_layout()
            
            filepath = self.output_dir / filename
            plt.savefig(filepath, dpi=150, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Equity curve saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to plot equity curve: {e}")
    
    def plot_drawdown_distribution(self, df: pd.DataFrame, filename: str):
        """绘制回撤分布图"""
        try:
            import matplotlib.pyplot as plt
            
            plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
            
            fig, axes = plt.subplots(2, 1, figsize=(14, 8))
            
            # 1. 回撤直方图
            ax1 = axes[0]
            drawdowns = df['drawdown'] * 100
            ax1.hist(drawdowns, bins=50, color='skyblue', edgecolor='black', alpha=0.7)
            ax1.set_xlabel('回撤 %')
            ax1.set_ylabel('天数')
            ax1.set_title('回撤分布直方图')
            ax1.grid(True, alpha=0.3)
            
            # 标注统计值
            stats_text = f"均值：{drawdowns.mean():.2f}%\n"
            stats_text += f"中位数：{drawdowns.median():.2f}%\n"
            stats_text += f"标准差：{drawdowns.std():.2f}%\n"
            stats_text += f"最小值：{drawdowns.min():.2f}%"
            ax1.annotate(stats_text,
                        xy=(0.98, 0.98), xycoords='axes fraction',
                        fontsize=10, verticalalignment='top', horizontalalignment='right',
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
            
            # 2. 回撤持续时间
            ax2 = axes[1]
            
            # 计算回撤持续时间
            in_drawdown = df['drawdown'] < -0.01  # 回撤超过 1%
            drawdown_periods = []
            current_period = 0
            
            for idx, is_dd in enumerate(in_drawdown):
                if is_dd:
                    current_period += 1
                else:
                    if current_period > 0:
                        drawdown_periods.append(current_period)
                    current_period = 0
            
            if current_period > 0:
                drawdown_periods.append(current_period)
            
            if drawdown_periods:
                ax2.hist(drawdown_periods, bins=20, color='coral', edgecolor='black', alpha=0.7)
                ax2.set_xlabel('持续天数')
                ax2.set_ylabel('发生次数')
                ax2.set_title('回撤持续时间分布')
                ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            filepath = self.output_dir / filename
            plt.savefig(filepath, dpi=150, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Drawdown distribution saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to plot drawdown distribution: {e}")
    
    def plot_monthly_returns(self, df: pd.DataFrame, filename: str):
        """绘制月度收益 Heatmap"""
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns
            
            plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
            
            # 计算月度收益
            df = df.copy()
            df['month'] = df.index.to_period('M')
            monthly_returns = df.groupby('month')['equity'].apply(
                lambda x: (x.iloc[-1] / x.iloc[0] - 1) * 100
            )
            
            # 转换为矩阵
            returns_matrix = []
            years = sorted(set([str(p)[:4] for p in monthly_returns.index]))
            months = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
            
            for year in years:
                row = []
                for month in months:
                    period = f"{year}-{month}"
                    matching = [p for p in monthly_returns.index if str(p) == period]
                    if matching:
                        row.append(monthly_returns[matching[0]])
                    else:
                        row.append(np.nan)
                returns_matrix.append(row)
            
            returns_df = pd.DataFrame(returns_matrix, index=years, columns=range(1, 13))
            
            # 绘制 Heatmap
            fig, ax = plt.subplots(figsize=(12, 6))
            sns.heatmap(returns_df, annot=True, fmt='.1f', cmap='RdYlGn', 
                       center=0, ax=ax, cbar_kws={'label': '月收益 %'},
                       vmin=-15, vmax=15)
            
            ax.set_xlabel('月份')
            ax.set_ylabel('年份')
            ax.set_title('月度收益 Heatmap')
            ax.set_xticklabels(['1 月', '2 月', '3 月', '4 月', '5 月', '6 月', 
                               '7 月', '8 月', '9 月', '10 月', '11 月', '12 月'])
            
            plt.tight_layout()
            
            filepath = self.output_dir / filename
            plt.savefig(filepath, dpi=150, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Monthly returns heatmap saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to plot monthly returns: {e}")
    
    def plot_position_distribution(self, trades: pd.DataFrame, filename: str):
        """绘制持仓分布图"""
        try:
            import matplotlib.pyplot as plt
            
            plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
            
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))
            
            # 1. ETF 持仓次数
            ax1 = axes[0, 0]
            position_counts = trades[trades['action'] == 'buy']['etf_code'].value_counts()
            position_counts.plot(kind='bar', ax=ax1, color='steelblue')
            ax1.set_xlabel('ETF 代码')
            ax1.set_ylabel('交易次数')
            ax1.set_title('各 ETF 交易次数')
            ax1.tick_params(axis='x', rotation=45)
            ax1.grid(True, alpha=0.3)
            
            # 2. 买入 vs 卖出
            ax2 = axes[0, 1]
            action_counts = trades['action'].value_counts()
            colors = ['green', 'red']
            ax2.pie(action_counts, labels=action_counts.index, autopct='%1.1f%%', colors=colors)
            ax2.set_title('买入/卖出分布')
            
            # 3. 交易金额分布
            ax3 = axes[1, 0]
            ax3.hist(trades['amount'], bins=30, color='purple', alpha=0.7, edgecolor='black')
            ax3.set_xlabel('交易金额')
            ax3.set_ylabel('次数')
            ax3.set_title('交易金额分布')
            ax3.grid(True, alpha=0.3)
            
            # 4. 交易成本分布
            ax4 = axes[1, 1]
            ax4.hist(trades['cost'], bins=30, color='orange', alpha=0.7, edgecolor='black')
            ax4.set_xlabel('交易成本')
            ax4.set_ylabel('次数')
            ax4.set_title('交易成本分布')
            ax4.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            filepath = self.output_dir / filename
            plt.savefig(filepath, dpi=150, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Position distribution saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to plot position distribution: {e}")
    
    def save_trades_table(self, trades: pd.DataFrame, filename: str):
        """保存交易记录表为 HTML"""
        try:
            # 格式化
            trades_html = trades.copy()
            if 'date' in trades_html.columns:
                trades_html['date'] = pd.to_datetime(trades_html['date']).dt.strftime('%Y-%m-%d')
            
            # 金额格式化
            for col in ['amount', 'cost', 'price']:
                if col in trades_html.columns:
                    trades_html[col] = trades_html[col].apply(lambda x: f"¥{x:,.0f}")
            
            html = trades_html.to_html(index=False, classes='table table-striped', border=0)
            
            # 添加样式
            styled_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>交易记录</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    table {{ border-collapse: collapse; width: 100%; }}
                    th {{ background-color: #4CAF50; color: white; padding: 12px; text-align: left; }}
                    td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
                    tr:hover {{ background-color: #f5f5f5; }}
                    .buy {{ color: green; font-weight: bold; }}
                    .sell {{ color: red; font-weight: bold; }}
                </style>
            </head>
            <body>
                <h1>交易记录</h1>
                <p>总交易次数：{len(trades)}</p>
                {html}
            </body>
            </html>
            """
            
            filepath = self.output_dir / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(styled_html)
            
            logger.info(f"Trades table saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save trades table: {e}")
    
    def generate_html_report(self, equity_curve: pd.DataFrame, trades: pd.DataFrame, filename: str):
        """生成综合 HTML 报告"""
        try:
            # 计算统计指标
            initial = equity_curve['equity'].iloc[0]
            final = equity_curve['equity'].iloc[-1]
            total_return = (final - initial) / initial * 100
            
            days = (equity_curve.index[-1] - equity_curve.index[0]).days
            annual_return = (1 + total_return/100) ** (365 / days) - 1 if days > 0 else 0
            annual_return *= 100
            
            max_dd = equity_curve['drawdown'].min() * 100
            
            daily_returns = equity_curve['equity'].pct_change()
            sharpe = (daily_returns.mean() - 0.03/252) / daily_returns.std() * np.sqrt(252) if len(daily_returns) > 1 else 0
            
            total_trades = len(trades)
            total_cost = trades['cost'].sum() if not trades.empty else 0
            
            # 生成 HTML
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>回测报告</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                    .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                    h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
                    h2 {{ color: #555; margin-top: 30px; }}
                    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
                    .stat-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; }}
                    .stat-card.good {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }}
                    .stat-card.bad {{ background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); }}
                    .stat-value {{ font-size: 28px; font-weight: bold; margin: 10px 0; }}
                    .stat-label {{ font-size: 14px; opacity: 0.9; }}
                    img {{ max-width: 100%; height: auto; margin: 20px 0; border-radius: 4px; }}
                    table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                    th {{ background: #4CAF50; color: white; padding: 12px; text-align: left; }}
                    td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
                    .positive {{ color: green; }}
                    .negative {{ color: red; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>📊 量化回测报告</h1>
                    <p>生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>回测期间：{equity_curve.index[0].strftime('%Y-%m-%d')} ~ {equity_curve.index[-1].strftime('%Y-%m-%d')} ({days} 天)</p>
                    
                    <h2>核心指标</h2>
                    <div class="stats">
                        <div class="stat-card {'good' if total_return > 0 else 'bad'}">
                            <div class="stat-label">总收益率</div>
                            <div class="stat-value">{total_return:+.2f}%</div>
                        </div>
                        <div class="stat-card {'good' if annual_return > 0 else 'bad'}">
                            <div class="stat-label">年化收益</div>
                            <div class="stat-value">{annual_return:+.2f}%</div>
                        </div>
                        <div class="stat-card {'good' if sharpe > 0 else 'bad'}">
                            <div class="stat-label">夏普比率</div>
                            <div class="stat-value">{sharpe:.2f}</div>
                        </div>
                        <div class="stat-card {'bad' if abs(max_dd) > 10 else 'good'}">
                            <div class="stat-label">最大回撤</div>
                            <div class="stat-value">{max_dd:.2f}%</div>
                        </div>
                    </div>
                    
                    <div class="stats">
                        <div class="stat-card">
                            <div class="stat-label">初始资金</div>
                            <div class="stat-value">¥{initial:,.0f}</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">最终价值</div>
                            <div class="stat-value">¥{final:,.0f}</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">交易次数</div>
                            <div class="stat-value">{total_trades}</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">交易成本</div>
                            <div class="stat-value">¥{total_cost:,.0f}</div>
                        </div>
                    </div>
                    
                    <h2>权益曲线</h2>
                    <img src="{Path(filename).stem}_equity_curve.png" alt="权益曲线">
                    
                    <h2>回撤分析</h2>
                    <img src="{Path(filename).stem}_drawdown.png" alt="回撤分析">
                    
                    <h2>月度收益</h2>
                    <img src="{Path(filename).stem}_monthly_heatmap.png" alt="月度收益">
                    
                    <h2>交易统计</h2>
                    <img src="{Path(filename).stem}_positions.png" alt="交易统计">
                </div>
            </body>
            </html>
            """
            
            filepath = self.output_dir / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html)
            
            logger.info(f"HTML report saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to generate HTML report: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 测试：加载回测数据生成报告
    reports_dir = Path("reports")
    
    equity_file = reports_dir / "backtest_enhanced_20250101.csv"
    trades_file = reports_dir / "trades_enhanced_20250101.csv"
    
    if equity_file.exists():
        df = pd.read_csv(equity_file, index_col='date', parse_dates=True)
        
        trades = pd.DataFrame()
        if trades_file.exists():
            trades = pd.read_csv(trades_file)
        
        generator = ReportGenerator()
        generator.generate_all(df, trades, report_name="test_report")
        
        print("\n✅ 报告生成完成!")
        print(f"查看：{generator.output_dir / 'test_report_summary.html'}")
    else:
        print("❌ 回测数据文件不存在，请先运行回测")
