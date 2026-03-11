# -*- coding: utf-8 -*-
"""
策略回测引擎 - 从OpenBB-develop整合
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class Signal:
    """交易信号"""
    date: datetime
    symbol: str
    action: str  # 'BUY', 'SELL'
    price: float
    reason: str


class Strategy:
    """策略基类"""
    
    def __init__(self, name: str):
        self.name = name
        self.signals: List[Signal] = []
        self.position = 0  # 持仓数量
        self.cash = 100000.0
        self.initial_capital = 100000.0
    
    def on_data(self, df: pd.DataFrame, symbol: str) -> Optional[Signal]:
        """处理数据生成信号，子类需重写"""
        return None
    
    def reset(self):
        """重置策略状态"""
        self.signals = []
        self.position = 0
        self.cash = self.initial_capital


class MACDStrategy(Strategy):
    """MACD金叉死叉策略"""
    
    def __init__(self, fast=12, slow=26, signal=9):
        super().__init__("MACD策略")
        self.fast = fast
        self.slow = slow
        self.signal = signal
    
    def on_data(self, df: pd.DataFrame, symbol: str) -> Optional[Signal]:
        if len(df) < self.slow + 5:
            return None
        
        close = df['close']
        
        # 计算MACD
        ema_fast = close.ewm(span=self.fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=self.signal, adjust=False).mean()
        macd = (dif - dea) * 2
        
        # 获取最新两期数据
        if len(dif) < 2:
            return None
        
        prev_dif, curr_dif = dif.iloc[-2], dif.iloc[-1]
        prev_dea, curr_dea = dea.iloc[-2], dea.iloc[-1]
        
        curr_price = close.iloc[-1]
        curr_date = df.index[-1] if isinstance(df.index[-1], datetime) else datetime.now()
        
        # 金叉买入
        if prev_dif <= prev_dea and curr_dif > curr_dea and self.position == 0:
            return Signal(curr_date, symbol, 'BUY', curr_price, 'MACD金叉')
        
        # 死叉卖出
        if prev_dif >= prev_dea and curr_dif < curr_dea and self.position > 0:
            return Signal(curr_date, symbol, 'SELL', curr_price, 'MACD死叉')
        
        return None


class MAStrategy(Strategy):
    """双均线策略"""
    
    def __init__(self, short=5, long=20):
        super().__init__(f"MA{short}-MA{long}策略")
        self.short = short
        self.long = long
    
    def on_data(self, df: pd.DataFrame, symbol: str) -> Optional[Signal]:
        if len(df) < self.long + 5:
            return None
        
        close = df['close']
        ma_short = close.rolling(self.short).mean()
        ma_long = close.rolling(self.long).mean()
        
        if len(ma_short) < 2:
            return None
        
        # 金叉买入
        if ma_short.iloc[-2] <= ma_long.iloc[-2] and ma_short.iloc[-1] > ma_long.iloc[-1] and self.position == 0:
            return Signal(datetime.now(), symbol, 'BUY', close.iloc[-1], f'MA{self.short}上穿MA{self.long}')
        
        # 死叉卖出
        if ma_short.iloc[-2] >= ma_long.iloc[-2] and ma_short.iloc[-1] < ma_long.iloc[-1] and self.position > 0:
            return Signal(datetime.now(), symbol, 'SELL', close.iloc[-1], f'MA{self.short}下穿MA{self.long}')
        
        return None


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, strategy: Strategy, initial_capital: float = 100000.0,
                 commission: float = 0.001, slippage: float = 0.001):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        
        self.equity_curve: List[float] = []
        self.dates: List[datetime] = []
        self.trades: List[Dict] = []
    
    def run(self, df: pd.DataFrame, symbol: str) -> Dict:
        """
        运行回测
        
        Args:
            df: 股票数据DataFrame
            symbol: 股票代码
            
        Returns:
            回测报告字典
        """
        if len(df) < 30:
            return {'error': '数据不足，至少需要30条数据'}
        
        # 重置策略
        self.strategy.reset()
        self.strategy.initial_capital = self.initial_capital
        self.strategy.cash = self.initial_capital
        
        self.equity_curve = []
        self.dates = []
        self.trades = []
        
        position = 0  # 持仓股数
        
        # 逐日回测
        for i in range(30, len(df)):
            current_data = df.iloc[:i+1]
            current_price = current_data['close'].iloc[-1]
            current_date = current_data.index[-1]
            
            # 更新策略持仓状态
            self.strategy.position = position
            
            # 生成信号
            signal = self.strategy.on_data(current_data, symbol)
            
            if signal:
                # 考虑滑点
                if signal.action == 'BUY':
                    executed_price = signal.price * (1 + self.slippage)
                    # 计算可买入股数（使用90%资金）
                    max_shares = int(self.strategy.cash * 0.9 / executed_price / 100) * 100
                    if max_shares >= 100:
                        cost = max_shares * executed_price * (1 + self.commission)
                        if cost <= self.strategy.cash:
                            position = max_shares
                            self.strategy.cash -= cost
                            self.trades.append({
                                'date': current_date,
                                'action': 'BUY',
                                'price': executed_price,
                                'shares': max_shares,
                                'cost': cost,
                                'reason': signal.reason
                            })
                
                elif signal.action == 'SELL' and position > 0:
                    executed_price = signal.price * (1 - self.slippage)
                    revenue = position * executed_price * (1 - self.commission)
                    self.strategy.cash += revenue
                    
                    # 计算盈亏
                    buy_trade = [t for t in self.trades if t['action'] == 'BUY'][-1]
                    buy_cost = buy_trade['cost']
                    pnl = revenue - buy_cost
                    
                    self.trades.append({
                        'date': current_date,
                        'action': 'SELL',
                        'price': executed_price,
                        'shares': position,
                        'revenue': revenue,
                        'pnl': pnl,
                        'reason': signal.reason
                    })
                    position = 0
            
            # 计算当前权益
            equity = self.strategy.cash + position * current_price
            self.equity_curve.append(equity)
            self.dates.append(current_date)
        
        # 生成报告
        return self._generate_report(df, symbol)
    
    def _generate_report(self, df: pd.DataFrame, symbol: str) -> Dict:
        """生成回测报告"""
        if not self.equity_curve:
            return {'error': '没有生成权益曲线'}
        
        equity_series = pd.Series(self.equity_curve, index=self.dates)
        
        # 计算收益率
        total_return = (self.equity_curve[-1] - self.initial_capital) / self.initial_capital
        
        # 年化收益率
        days = len(self.equity_curve)
        annual_return = (1 + total_return) ** (252 / days) - 1 if days > 0 else 0
        
        # 最大回撤
        cummax = equity_series.cummax()
        drawdown = (equity_series - cummax) / cummax
        max_drawdown = drawdown.min()
        
        # 计算胜率
        sell_trades = [t for t in self.trades if t['action'] == 'SELL']
        win_trades = [t for t in sell_trades if t.get('pnl', 0) > 0]
        win_rate = len(win_trades) / len(sell_trades) * 100 if sell_trades else 0
        
        # 总盈亏
        total_pnl = sum(t.get('pnl', 0) for t in sell_trades)
        
        return {
            'symbol': symbol,
            'strategy': self.strategy.name,
            'initial_capital': self.initial_capital,
            'final_equity': self.equity_curve[-1],
            'total_return': total_return * 100,
            'annual_return': annual_return * 100,
            'max_drawdown': max_drawdown * 100,
            'win_rate': win_rate,
            'total_trades': len(sell_trades),
            'winning_trades': len(win_trades),
            'losing_trades': len(sell_trades) - len(win_trades),
            'total_pnl': total_pnl,
            'trades': self.trades,
            'equity_curve': equity_series
        }


def run_backtest(df: pd.DataFrame, symbol: str, strategy_type: str = 'macd') -> Dict:
    """
    便捷回测函数
    
    Args:
        df: 股票数据
        symbol: 股票代码
        strategy_type: 策略类型 ('macd' 或 'ma')
        
    Returns:
        回测报告
    """
    if strategy_type == 'macd':
        strategy = MACDStrategy()
    elif strategy_type == 'ma':
        strategy = MAStrategy()
    else:
        return {'error': f'未知策略类型: {strategy_type}'}
    
    engine = BacktestEngine(strategy)
    return engine.run(df, symbol)
