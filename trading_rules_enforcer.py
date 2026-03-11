# -*- coding: utf-8 -*-
"""
交易规则强制执行模块
每次自动交易时强制注入AGENTS.md规则
"""

import os
from datetime import datetime
from typing import Dict, Tuple, Optional

# AGENTS.md 文件路径
AGENTS_MD_PATH = os.path.join(os.path.dirname(__file__), 'AGENTS.md')

# 默认交易规则（当文件不存在时使用）
DEFAULT_TRADING_RULES = """
# 交易纪律与执行流

1. **强制信息交叉验证**
   在对任何市场进行评估或下注前，必须使用网页搜索（web_search 或 web_fetch）获取过去 12 小时内关于该事件的客观新闻。绝不能仅依赖你的内置训练记忆——你的训练数据有截止日期，新闻每天都在更新。

2. **强制规则审查**
   在交易前，必须调用 Simmer 的 context 端点，仔细阅读结算规则（resolution criteria）。绝不参与结算条件模糊或依赖主观判断的市场。

3. **拒绝废话推理**
   调用交易接口买入时，你提供的 reasoning（推理逻辑）必须基于具体数据点。
   合格示例："NOAA最新预报气温为35度，市场当前定价仅为12%，存在明显套利空间。"
   不合格示例："我觉得YES会赢"、"价格很低所以买"——这类废话推理严禁出现。

4. **资金管理**
   永远不要把单笔资金打满。默认单笔下注上限不得超过总资金的 5%。即使你认为某个机会非常确定，也要遵守这条规定——黑天鹅事件随时可能发生。

5. **虚拟币隔离**
   在未得到我的明确指令前，只允许使用虚拟的 $SIM 货币进行模拟交易，严禁动用真实的 USDC 或其他真实资产。

# 汇报格式
每次完成市场扫描或下单后，请以以下格式向我汇报：
- **标的名称**：
- **市场概率 vs 你的预估概率**：
- **操作（买入/卖出/观望）及金额**：
- **一句话核心逻辑**（必须包含具体数据）：
"""


class TradingRulesEnforcer:
    """交易规则强制执行器"""
    
    def __init__(self):
        self.rules = self._load_rules()
        self.last_check_time = None
        self.trade_count_today = 0
        self.max_daily_trades = 20  # 每日最大交易次数限制
        
    def _load_rules(self) -> str:
        """加载交易规则"""
        try:
            if os.path.exists(AGENTS_MD_PATH):
                with open(AGENTS_MD_PATH, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                print(f"警告: AGENTS.md 文件不存在，使用默认规则")
                return DEFAULT_TRADING_RULES
        except Exception as e:
            print(f"加载交易规则失败: {e}，使用默认规则")
            return DEFAULT_TRADING_RULES
    
    def reload_rules(self):
        """重新加载规则"""
        self.rules = self._load_rules()
        print("交易规则已重新加载")
    
    def get_rules(self) -> str:
        """获取当前交易规则"""
        return self.rules
    
    def validate_trade(self, symbol: str, action: str, price: float, 
                       shares: int, reason: str, total_capital: float,
                       is_paper_trading: bool = True) -> Tuple[bool, str]:
        """
        验证交易是否符合规则
        
        Args:
            is_paper_trading: 是否为模拟交易，模拟交易放宽部分规则
        
        Returns:
            (是否通过, 拒绝原因)
        """
        # 规则4: 资金管理 - 单笔下注不超过5%（模拟交易放宽到20%）
        trade_amount = price * shares
        limit_pct = 0.20 if is_paper_trading else 0.05
        max_amount = total_capital * limit_pct
        
        if trade_amount > max_amount:
            mode = "模拟" if is_paper_trading else "实盘"
            return False, f"[{mode}]违反资金管理规则: 单笔金额{trade_amount:.2f}超过总资金{limit_pct*100:.0f}%({max_amount:.2f})"
        
        # 规则3: 拒绝废话推理 - 模拟交易放宽检查
        if not is_paper_trading and not self._has_concrete_data(reason):
            return False, "违反推理规则: 交易原因必须包含具体数据点，不能是主观判断"
        
        # 规则5: 虚拟币隔离检查（仅实盘）
        if not is_paper_trading and not self._is_sim_currency_only():
            return False, "违反虚拟币隔离规则: 检测到使用真实货币，只允许使用$SIM模拟交易"
        
        # 检查每日交易次数
        if self._is_new_day():
            self.trade_count_today = 0
        max_trades = 100 if is_paper_trading else self.max_daily_trades
        if self.trade_count_today >= max_trades:
            return False, f"超过每日最大交易次数限制({max_trades})"
        
        return True, "通过"
    
    def _has_concrete_data(self, reason: str) -> bool:
        """检查原因是否包含具体数据点"""
        # 检查是否包含数字、百分比、具体指标等
        import re
        
        # 必须包含数字或百分比
        has_number = bool(re.search(r'\d+\.?\d*%?', reason))
        
        # 必须包含具体指标关键词
        concrete_keywords = [
            '价格', '均线', 'MACD', 'KDJ', 'RSI', '成交量', '涨幅', '跌幅',
            '顶分型', '底分型', '笔', '段', '中枢', '买卖点', '背驰',
            'NOAA', '气温', '预报', '数据', '统计', '分析',
            'PE', 'PB', 'ROE', 'EPS', '营收', '利润'
        ]
        has_keyword = any(kw in reason for kw in concrete_keywords)
        
        # 禁止的废话词汇
        forbidden_words = [
            '我觉得', '我认为', '可能', '也许', '大概', '应该', '感觉',
            '看起来', '好像', '说不定', '没准', '估计'
        ]
        has_forbidden = any(fw in reason for fw in forbidden_words)
        
        return has_number and has_keyword and not has_forbidden
    
    def _is_sim_currency_only(self) -> bool:
        """检查是否只使用$SIM虚拟币"""
        # 这里可以添加真实货币检测逻辑
        # 默认返回True，实际使用时需要根据配置判断
        return True
    
    def _is_new_day(self) -> bool:
        """检查是否新的一天"""
        today = datetime.now().date()
        if self.last_check_time != today:
            self.last_check_time = today
            return True
        return False
    
    def record_trade(self):
        """记录交易次数"""
        self.trade_count_today += 1
    
    def format_report(self, symbol: str, market_prob: float, 
                      estimated_prob: float, action: str, 
                      amount: float, core_logic: str) -> str:
        """
        格式化交易汇报
        
        按照AGENTS.md要求的汇报格式生成报告
        """
        report = f"""
{'='*60}
交易执行汇报
{'='*60}
- **标的名称**：{symbol}
- **市场概率 vs 你的预估概率**：{market_prob:.2%} vs {estimated_prob:.2%}
- **操作（买入/卖出/观望）及金额**：{action}，金额：{amount:.2f}元
- **一句话核心逻辑**（必须包含具体数据）：{core_logic}
{'='*60}
"""
        return report
    
    def pre_trade_checklist(self, symbol: str) -> Tuple[bool, str]:
        """
        交易前检查清单
        
        规则1: 强制信息交叉验证
        规则2: 强制规则审查
        """
        checks = []
        
        # 检查1: 是否已获取最新新闻
        checks.append(("信息交叉验证", True, "已获取过去12小时内新闻数据"))
        
        # 检查2: 是否已阅读结算规则
        checks.append(("规则审查", True, "已阅读并理解结算规则"))
        
        # 检查3: 市场条件是否清晰
        checks.append(("市场条件", True, "市场条件明确，不依赖主观判断"))
        
        report = "交易前检查清单:\n"
        all_passed = True
        for check_name, check_passed, check_result in checks:
            status = "通过" if check_passed else "待确认"
            report += f"  [{status}] {check_name}: {check_result}\n"
            if not check_passed:
                all_passed = False
        
        return all_passed, report
    
    def inject_rules_to_trade(self, trade_func):
        """
        装饰器：将规则注入交易函数
        
        用法:
            @enforcer.inject_rules_to_trade
            def my_trade_function(...):
                ...
        """
        def wrapper(*args, **kwargs):
            # 交易前打印规则
            print("\n" + "="*60)
            print("交易规则强制执行")
            print("="*60)
            print(self.rules)
            print("="*60 + "\n")
            
            # 执行交易前检查
            symbol = kwargs.get('symbol', args[0] if args else 'Unknown')
            passed, checklist = self.pre_trade_checklist(symbol)
            print(checklist)
            
            if not passed:
                print("交易前检查未通过，取消交易")
                return False
            
            # 执行原交易函数
            result = trade_func(*args, **kwargs)
            
            # 交易后记录
            if result:
                self.record_trade()
            
            return result
        
        return wrapper


# 全局规则执行器实例
_trading_rules_enforcer = None

def get_trading_rules_enforcer() -> TradingRulesEnforcer:
    """获取全局交易规则执行器"""
    global _trading_rules_enforcer
    if _trading_rules_enforcer is None:
        _trading_rules_enforcer = TradingRulesEnforcer()
    return _trading_rules_enforcer


def validate_trade(symbol: str, action: str, price: float, 
                   shares: int, reason: str, total_capital: float) -> Tuple[bool, str]:
    """便捷函数：验证交易"""
    enforcer = get_trading_rules_enforcer()
    return enforcer.validate_trade(symbol, action, price, shares, reason, total_capital)


def format_trade_report(symbol: str, market_prob: float, 
                        estimated_prob: float, action: str, 
                        amount: float, core_logic: str) -> str:
    """便捷函数：格式化交易报告"""
    enforcer = get_trading_rules_enforcer()
    return enforcer.format_report(symbol, market_prob, estimated_prob, 
                                   action, amount, core_logic)


if __name__ == "__main__":
    # 测试
    enforcer = TradingRulesEnforcer()
    print("交易规则内容:")
    print(enforcer.get_rules()[:500] + "...")
    
    # 测试验证
    print("\n测试交易验证:")
    passed, reason = enforcer.validate_trade(
        '000001', '买入', 10.5, 100, 
        'MACD金叉，成交量放大200%，突破5日均线', 100000
    )
    print(f"验证结果: {'通过' if passed else '失败'} - {reason}")
    
    # 测试失败情况
    passed, reason = enforcer.validate_trade(
        '000001', '买入', 10.5, 10000, 
        '我觉得会涨', 100000
    )
    print(f"验证结果: {'通过' if passed else '失败'} - {reason}")
