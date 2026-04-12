"""
Telegram 通知模块
"""
import requests
from typing import Dict, List
import logging
import os

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Telegram 通知器"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}"
    
    def send_message(self, text: str, parse_mode: str = 'Markdown') -> bool:
        """发送消息"""
        url = f"{self.base_url}/sendMessage"
        data = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': parse_mode
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                logger.info("Message sent successfully")
                return True
            else:
                logger.error(f"Failed to send message: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    def send_signal(self, result: dict, signals: dict) -> bool:
        """发送调仓信号"""
        message = self._format_signal_message(result, signals)
        return self.send_message(message)
    
    def _format_signal_message(self, result: dict, signals: dict) -> str:
        """格式化信号消息"""
        date = result['date']
        
        lines = [
            f"📊 *指数轮动信号* - {date}",
            "",
            "🏆 *综合得分 TOP 5*:",
        ]
        
        # 前 5 名
        for i, (code, score) in enumerate(result['ranked'][:5], 1):
            name = result['all_data'].get(code, {}).get('name', code)
            breakdown = result['score_breakdowns'].get(code, {})
            
            # 显示主要因子得分
            value_s = breakdown.get('value', 0)
            momentum_s = breakdown.get('momentum', 0)
            vol_s = breakdown.get('volatility', 0)
            
            lines.append(
                f"{i}. *{name}* ({code})\n"
                f"   综合：{score:.2f} | 估值：{value_s:.2f} | 动量：{momentum_s:.2f} | 波动：{vol_s:.2f}"
            )
        
        # 调仓建议
        lines.extend([
            "",
            "💡 *调仓建议*:",
        ])
        
        if signals['buy']:
            buy_list = []
            for code in signals['buy']:
                name = result['all_data'].get(code, {}).get('name', code)
                buy_list.append(f"{name} ({code})")
            lines.append(f"🟢 *买入*: {', '.join(buy_list)}")
        
        if signals['sell']:
            sell_list = []
            for code in signals['sell']:
                name = result['all_data'].get(code, {}).get('name', code)
                sell_list.append(f"{name} ({code})")
            lines.append(f"🔴 *卖出*: {', '.join(sell_list)}")
        
        if signals['hold']:
            hold_list = []
            for code in signals['hold']:
                name = result['all_data'].get(code, {}).get('name', code)
                hold_list.append(f"{name}")
            lines.append(f"⚪ *持有*: {', '.join(hold_list)}")
        
        # 估值提示
        lines.extend([
            "",
            "⚠️ *估值提示*:",
        ])
        
        for code, data in result['all_data'].items():
            pe = data.get('current_pe')
            if pe:
                name = data.get('name', code)
                pe_percentile = result['all_data'][code].get('pe_df', None)
                if pe_percentile is not None:
                    pass  # 简化处理
                lines.append(f"- {name}: PE={pe:.1f}")
        
        return '\n'.join(lines)
    
    def send_portfolio_summary(self, summary: dict, date: str) -> bool:
        """发送组合摘要"""
        lines = [
            f"💼 *组合摘要* - {date}",
            "",
            f"💰 总资产：¥{summary['total_value']:,.0f}",
            f"💵 现金：¥{summary['cash']:,.0f}",
            f"📈 收益率：{summary['return']*100:.2f}%",
            f"📊 持仓数：{summary['num_positions']}",
            "",
            "*持仓明细*:",
        ]
        
        for pos in summary['positions']:
            weight = pos['weight'] * 100
            pnl = (pos['current_price'] - pos['avg_price']) / pos['avg_price'] * 100
            lines.append(
                f"- {pos['name']} ({pos['code']}): {weight:.1f}% "
                f"(盈亏：{pnl:+.1f}%)"
            )
        
        message = '\n'.join(lines)
        return self.send_message(message)


def get_notifier_from_config(config: dict) -> TelegramNotifier:
    """从配置创建通知器"""
    telegram_config = config.get('telegram', {})
    
    if not telegram_config.get('enabled', False):
        logger.info("Telegram notifications disabled")
        return None
    
    bot_token = telegram_config.get('bot_token', '')
    chat_id = telegram_config.get('chat_id', '')
    
    # 支持环境变量
    if bot_token.startswith('${') and bot_token.endswith('}'):
        env_var = bot_token[2:-1]
        bot_token = os.environ.get(env_var, '')
    
    if not bot_token or not chat_id:
        logger.warning("Telegram credentials not configured")
        return None
    
    return TelegramNotifier(bot_token, chat_id)
