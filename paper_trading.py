"""
模拟盘交易模块
支持连接实盘行情进行模拟交易测试
"""

import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
import pandas as pd
import numpy as np

from stock_data import StockDataAPI
from indicators import calculate_indicators
from strategy import ChanlunStrategy, Trade, Position

# 导入交易规则强制执行器
try:
    from trading_rules_enforcer import get_trading_rules_enforcer, format_trade_report
    TRADING_RULES_AVAILABLE = True
except ImportError:
    TRADING_RULES_AVAILABLE = False


@dataclass
class PaperTrade:
    """模拟交易记录"""
    id: str
    datetime: str
    symbol: str
    action: str
    price: float
    shares: int
    amount: float
    reason: str
    score: int
    is_real: bool = False  # 是否为实盘同步交易


@dataclass
class PaperPosition:
    """模拟持仓"""
    symbol: str
    shares: int
    avg_cost: float
    buy_time: str
    buy_price: float
    buy_score: int
    current_price: float = 0.0
    profit_pct: float = 0.0
    market_value: float = 0.0


class PaperTrading:
    """
    模拟盘交易系统
    
    功能：
    1. 使用真实行情数据进行模拟交易
    2. 支持手动/自动两种模式
    3. 可同步到实盘（可选）
    4. 实时计算盈亏和绩效
    """
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        sync_to_real: bool = False,
        data_source: str = 'pytdx'
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.sync_to_real = sync_to_real
        self.data_source = data_source
        
        # 状态
        self.positions: Dict[str, PaperPosition] = {}
        self.trades: List[PaperTrade] = []
        self.equity_history: List[Dict] = []
        
        # 数据接口
        self.api = StockDataAPI()
        self.connected = False
        
        # 自动交易
        self.strategy = ChanlunStrategy(
            initial_capital=initial_capital,
            position_size=0.2,
            stop_loss=0.05,
            take_profit=0.10,
            min_buy_score=60
        )
        self.auto_trading = False
        self.trading_thread = None
        self.watch_list: List[str] = []
        
        # 回调函数
        self.on_trade: Optional[Callable] = None
        self.on_price_update: Optional[Callable] = None
        
        # 加载历史数据
        self._load_data()
    
    def _load_data(self):
        """加载本地数据"""
        try:
            with open('paper_trading_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.cash = data.get('cash', self.initial_capital)
                self.positions = {
                    k: PaperPosition(**v) 
                    for k, v in data.get('positions', {}).items()
                }
                self.trades = [PaperTrade(**t) for t in data.get('trades', [])]
                print(f"已加载模拟盘数据，当前资金: {self.cash:.2f}")
        except FileNotFoundError:
            print("新建模拟盘账户")
    
    def _save_data(self):
        """保存数据到本地"""
        data = {
            'cash': self.cash,
            'positions': {
                k: asdict(v) for k, v in self.positions.items()
            },
            'trades': [asdict(t) for t in self.trades[-100:]]  # 只保存最近100笔
        }
        with open('paper_trading_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def connect(self) -> bool:
        """连接数据源"""
        if not self.connected:
            self.connected = self.api.connect()
        return self.connected
    
    def get_account_info(self) -> Dict:
        """获取账户信息"""
        total_market_value = sum(p.market_value for p in self.positions.values())
        total_assets = self.cash + total_market_value
        
        return {
            '初始资金': self.initial_capital,
            '可用资金': self.cash,
            '总市值': total_market_value,
            '总资产': total_assets,
            '总盈亏': total_assets - self.initial_capital,
            '总盈亏率': (total_assets - self.initial_capital) / self.initial_capital * 100,
            '持仓数量': len(self.positions),
            '当日时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def get_positions(self) -> List[Dict]:
        """获取持仓列表"""
        self._update_prices()
        positions = []
        for p in self.positions.values():
            # 获取股票名称
            name = self._get_stock_name(p.symbol)
            positions.append({
                '代码': p.symbol,
                '名称': name,
                '股数': p.shares,
                '成本价': p.avg_cost,
                '现价': p.current_price,
                '市值': p.market_value,
                '盈亏率': p.profit_pct,
                '买入时间': p.buy_time
            })
        return positions
    
    def _get_stock_name(self, symbol: str) -> str:
        """获取股票名称"""
        try:
            if not self.connect():
                return symbol
            quotes = self.api.get_realtime_quotes([symbol])
            if not quotes.empty and 'name' in quotes.columns:
                return quotes.iloc[0]['name']
            return symbol
        except:
            return symbol
    
    def _update_prices(self):
        """更新持仓价格"""
        if not self.connect():
            return
        
        for symbol in list(self.positions.keys()):
            try:
                quotes = self.api.get_realtime_quotes([symbol])
                if not quotes.empty:
                    price = float(quotes.iloc[0]['price'])
                    p = self.positions[symbol]
                    p.current_price = price
                    if p.avg_cost > 0:
                        p.profit_pct = (price - p.avg_cost) / p.avg_cost * 100
                    else:
                        p.profit_pct = 0
                    p.market_value = p.shares * price
            except Exception as e:
                print(f"更新 {symbol} 价格失败: {e}")
    
    def buy(self, symbol: str, price: float = None, shares: int = None, 
            reason: str = "手动买入", score: int = 0) -> bool:
        """
        模拟买入
        
        Parameters:
            symbol: 股票代码
            price: 买入价格（None则使用最新价）
            shares: 买入股数（None则自动计算）
            reason: 买入原因
            score: 买点得分
        """
        # 强制注入交易规则检查
        if TRADING_RULES_AVAILABLE:
            enforcer = get_trading_rules_enforcer()
            
            # 打印交易规则
            print("\n" + "="*60)
            print("AGENTS.md 交易规则强制执行")
            print("="*60)
            print(enforcer.get_rules())
            print("="*60 + "\n")
            
            # 交易前检查清单
            passed, checklist = enforcer.pre_trade_checklist(symbol)
            print(checklist)
            if not passed:
                print("交易前检查未通过，取消交易")
                return False
            
            # 验证交易合规性
            total_capital = self.initial_capital
            if price is None or shares is None:
                # 临时获取价格用于验证
                if self.connect():
                    quotes = self.api.get_realtime_quotes([symbol])
                    if not quotes.empty:
                        check_price = quotes.iloc[0]['price']
                        check_shares = int(self.cash * 0.1 / check_price / 100) * 100
                        if check_shares < 100:
                            check_shares = 100
                    else:
                        check_price = 0
                        check_shares = 0
                else:
                    check_price = price or 0
                    check_shares = shares or 0
            else:
                check_price = price
                check_shares = shares
            
            valid, msg = enforcer.validate_trade(symbol, '买入', check_price,
                                                  check_shares, reason, total_capital,
                                                  is_paper_trading=True)
            if not valid:
                print(f"交易规则验证失败: {msg}")
                return False

            print(f"交易规则验证通过: {msg}")
        
        if not self.connect():
            print("未连接数据源")
            return False
        
        # 获取最新价格
        if price is None:
            quotes = self.api.get_realtime_quotes([symbol])
            if quotes.empty:
                print(f"无法获取 {symbol} 行情")
                return False
            price = quotes.iloc[0]['price']
        
        # 计算买入股数
        if shares is None:
            position_value = self.cash * 0.1  # 默认10%仓位（降低避免高价股）
            shares = int(position_value / price / 100) * 100
        
        if shares < 100:
            shares = 100  # 至少1手
        
        # 检查资金是否足够
        amount = price * shares
        if amount > self.cash:
            # 资金不足时减少股数
            shares = int(self.cash / price / 100) * 100
            if shares < 100:
                print(f"资金不足，无法买入 {symbol}")
                return False
            amount = price * shares
        
        amount = price * shares
        if amount > self.cash:
            print(f"可用资金不足: {self.cash:.2f} < {amount:.2f}")
            return False
        
        # 执行买入
        self.cash -= amount
        
        # 记录交易次数
        if TRADING_RULES_AVAILABLE:
            get_trading_rules_enforcer().record_trade()
        
        now = datetime.now()
        trade_id = f"PT{now.strftime('%Y%m%d%H%M%S')}{len(self.trades):04d}"
        
        # 更新持仓
        if symbol in self.positions:
            p = self.positions[symbol]
            total_cost = p.avg_cost * p.shares + amount
            p.shares += shares
            p.avg_cost = total_cost / p.shares
        else:
            self.positions[symbol] = PaperPosition(
                symbol=symbol,
                shares=shares,
                avg_cost=price,
                buy_time=now.strftime('%Y-%m-%d %H:%M:%S'),
                buy_price=price,
                buy_score=score,
                current_price=price,
                market_value=amount
            )
        
        # 记录交易
        trade = PaperTrade(
            id=trade_id,
            datetime=now.strftime('%Y-%m-%d %H:%M:%S'),
            symbol=symbol,
            action='buy',
            price=price,
            shares=shares,
            amount=amount,
            reason=reason,
            score=score
        )
        self.trades.append(trade)
        self._save_data()
        
        print(f"[模拟买入] {symbol} @ {price:.2f} x {shares}股 = {amount:.2f}")
        
        # 触发回调
        if self.on_trade:
            self.on_trade(trade)
        
        # 同步到实盘
        if self.sync_to_real:
            self._sync_to_real_account('buy', symbol, price, shares)
        
        return True
    
    def sell(self, symbol: str, price: float = None, shares: int = None,
             reason: str = "手动卖出", score: int = 0) -> bool:
        """模拟卖出"""
        # 强制注入交易规则检查
        if TRADING_RULES_AVAILABLE:
            enforcer = get_trading_rules_enforcer()
            
            # 打印交易规则
            print("\n" + "="*60)
            print("AGENTS.md 交易规则强制执行")
            print("="*60)
            print(enforcer.get_rules())
            print("="*60 + "\n")
            
            # 交易前检查清单
            passed, checklist = enforcer.pre_trade_checklist(symbol)
            print(checklist)
            if not passed:
                print("交易前检查未通过，取消交易")
                return False
        
        if symbol not in self.positions:
            print(f"未持有 {symbol}")
            return False
        
        if not self.connect():
            print("未连接数据源")
            return False
        
        position = self.positions[symbol]
        
        # 获取最新价格
        if price is None:
            quotes = self.api.get_realtime_quotes([symbol])
            if quotes.empty:
                print(f"无法获取 {symbol} 行情")
                return False
            price = quotes.iloc[0]['price']
        
        # 卖出股数
        if shares is None or shares >= position.shares:
            shares = position.shares
        
        amount = price * shares
        profit = (price - position.avg_cost) * shares
        profit_pct = (price - position.avg_cost) / position.avg_cost * 100
        
        # 执行卖出
        self.cash += amount
        
        now = datetime.now()
        trade_id = f"PT{now.strftime('%Y%m%d%H%M%S')}{len(self.trades):04d}"
        
        # 更新持仓
        if shares >= position.shares:
            del self.positions[symbol]
        else:
            position.shares -= shares
            position.market_value = position.shares * price
        
        # 记录交易
        trade = PaperTrade(
            id=trade_id,
            datetime=now.strftime('%Y-%m-%d %H:%M:%S'),
            symbol=symbol,
            action='sell',
            price=price,
            shares=shares,
            amount=amount,
            reason=reason,
            score=score
        )
        self.trades.append(trade)
        self._save_data()
        
        print(f"[模拟卖出] {symbol} @ {price:.2f} x {shares}股 = {amount:.2f}, 盈亏: {profit_pct:+.2f}%")
        
        # 生成交易汇报
        if TRADING_RULES_AVAILABLE:
            report = format_trade_report(
                symbol=symbol,
                market_prob=0.5,
                estimated_prob=score/100 if score else 0.5,
                action='卖出',
                amount=amount,
                core_logic=reason
            )
            print(report)
        
        # 触发回调
        if self.on_trade:
            self.on_trade(trade)
        
        # 同步到实盘
        if self.sync_to_real:
            self._sync_to_real_account('sell', symbol, price, shares)
        
        return True
    
    def _sync_to_real_account(self, action: str, symbol: str, price: float, shares: int):
        """同步到实盘账户"""
        print(f"[实盘同步] {action.upper()} {symbol} @ {price:.2f} x {shares}")
        # 这里可以接入easytrader进行实盘下单
        # 示例：self.real_trader.buy(symbol, price, shares)
    
    def auto_scan(self, symbols: List[str]):
        """
        自动扫描并交易
        
        Parameters:
            symbols: 监控的股票列表
        """
        self.watch_list = symbols
        self.auto_trading = True
        
        # 强制注入AGENTS.md交易规则
        if TRADING_RULES_AVAILABLE:
            enforcer = get_trading_rules_enforcer()
            print("\n" + "="*60)
            print("AGENTS.md 交易规则强制执行 - 自动交易模式")
            print("="*60)
            print(enforcer.get_rules())
            print("="*60)
            print("警告：所有自动交易必须遵守上述规则")
            print("="*60 + "\n")
        
        print(f"开始自动扫描，监控 {len(symbols)} 只股票")
        
        for symbol in symbols:
            try:
                # 获取数据
                df = self.api.get_kline(symbol, 'day', 100)
                if df.empty:
                    continue
                
                # 计算指标
                df = calculate_indicators(df)
                latest = df.iloc[-1]
                
                # 检查买入信号
                if symbol not in self.positions:
                    should_buy, reason = self._check_buy_signal(latest)
                    if should_buy:
                        self.buy(
                            symbol=symbol,
                            price=latest['close'],
                            reason=f"自动买入: {reason}",
                            score=int(latest['买点得分'])
                        )
                
                # 检查卖出信号
                else:
                    position = self.positions[symbol]
                    should_sell, reason = self._check_sell_signal(latest, position)
                    if should_sell:
                        self.sell(
                            symbol=symbol,
                            price=latest['close'],
                            reason=f"自动卖出: {reason}",
                            score=int(latest.get('卖点得分', 0))
                        )
                
            except Exception as e:
                print(f"扫描 {symbol} 出错: {e}")
    
    def _check_buy_signal(self, row: pd.Series) -> tuple:
        """检查买入信号"""
        if row['买点得分'] < 60:
            return False, "买点得分不足"
        if not row['MACD金叉']:
            return False, "无MACD金叉"
        if row['close'] <= row['MA5']:
            return False, "未突破MA5"
        return True, f"买点得分{row['买点得分']:.0f}"
    
    def _check_sell_signal(self, row: pd.Series, position: PaperPosition) -> tuple:
        """检查卖出信号"""
        current_price = row['close']
        profit_pct = (current_price - position.avg_cost) / position.avg_cost
        
        if profit_pct <= -0.05:
            return True, f"止损: {profit_pct*100:.2f}%"
        if profit_pct >= 0.10:
            return True, f"止盈: {profit_pct*100:.2f}%"
        if row.get('MACD死叉', False):
            return True, "MACD死叉"
        
        return False, ""
    
    def start_auto_trading(self, symbols: List[str], interval: int = 60):
        """
        启动自动交易循环
        
        Parameters:
            symbols: 监控列表
            interval: 扫描间隔（秒）
        """
        self.watch_list = symbols
        self.auto_trading = True
        
        def trading_loop():
            while self.auto_trading:
                print(f"\n[{datetime.now()}] 自动扫描中...")
                self.auto_scan(symbols)
                self._update_prices()
                self._save_data()
                
                # 记录权益
                info = self.get_account_info()
                self.equity_history.append({
                    'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'total_assets': info['总资产'],
                    'profit': info['总盈亏']
                })
                
                time.sleep(interval)
        
        self.trading_thread = threading.Thread(target=trading_loop)
        self.trading_thread.daemon = True
        self.trading_thread.start()
        print(f"自动交易已启动，每{interval}秒扫描一次")
    
    def stop_auto_trading(self):
        """停止自动交易"""
        self.auto_trading = False
        if self.trading_thread:
            self.trading_thread.join(timeout=5)
        print("自动交易已停止")
    
    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        """获取交易历史"""
        trades = self.trades[-limit:]
        return [{
            '时间': t.datetime,
            '代码': t.symbol,
            '操作': '买入' if t.action == 'buy' else '卖出',
            '价格': t.price,
            '股数': t.shares,
            '金额': t.amount,
            '原因': t.reason
        } for t in reversed(trades)]
    
    def reset(self):
        """重置账户"""
        self.cash = self.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_history = []
        self._save_data()
        print("模拟盘已重置")


# ============ Web界面支持 ============

class PaperTradingWebAPI:
    """模拟盘Web API（用于前端界面）"""
    
    def __init__(self, paper_trading: PaperTrading):
        self.pt = paper_trading
    
    def get_dashboard(self) -> Dict:
        """获取仪表盘数据"""
        return {
            'account': self.pt.get_account_info(),
            'positions': self.pt.get_positions(),
            'recent_trades': self.pt.get_trade_history(10)
        }
    
    def buy(self, symbol: str, price: float = None, shares: int = None) -> Dict:
        """买入接口"""
        success = self.pt.buy(symbol, price, shares)
        return {'success': success, 'account': self.pt.get_account_info()}
    
    def sell(self, symbol: str, price: float = None, shares: int = None) -> Dict:
        """卖出接口"""
        success = self.pt.sell(symbol, price, shares)
        return {'success': success, 'account': self.pt.get_account_info()}


if __name__ == '__main__':
    # 测试模拟盘
    print("=" * 50)
    print("模拟盘交易系统测试")
    print("=" * 50)
    
    # 创建模拟盘账户
    pt = PaperTrading(initial_capital=100000)
    
    # 查看账户信息
    print("\n账户信息:")
    info = pt.get_account_info()
    for k, v in info.items():
        print(f"  {k}: {v}")
    
    # 手动买入测试
    print("\n手动买入测试:")
    pt.buy('600519', shares=100, reason="测试买入")
    
    # 查看持仓
    print("\n当前持仓:")
    positions = pt.get_positions()
    for p in positions:
        print(f"  {p}")
    
    # 查看账户
    print("\n更新后账户:")
    info = pt.get_account_info()
    for k, v in info.items():
        print(f"  {k}: {v}")
    
    # 自动扫描测试
    print("\n自动扫描测试:")
    pt.auto_scan(['600519', '000001', '000858'])
    
    print("\n模拟盘测试完成")
