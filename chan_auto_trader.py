# -*- coding: utf-8 -*-
"""
Chan.py-main 自动交易模块
基于缠论买卖点信号执行自动交易
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Callable
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from chan_adapter import ChanAdapter, ChanSignal, ChanAnalysis, get_chan_adapter
from chan_stock_picker import ChanStockPicker, ChanPickResult


class TradeAction(Enum):
    """交易动作"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    WAIT = "wait"


@dataclass
class TradeDecision:
    """交易决策"""
    symbol: str
    action: TradeAction
    price: float
    shares: int
    reason: str
    confidence: int  # 置信度 0-100
    bsp_type: str
    stop_loss: float
    take_profit: float
    chan_analysis: ChanAnalysis


class ChanAutoTrader:
    """
    缠论自动交易器
    基于缠论买卖点执行自动买卖决策
    """
    
    def __init__(self, 
                 initial_capital: float = 100000.0,
                 position_size: float = 0.2,  # 单票仓位比例
                 stop_loss_pct: float = 0.05,  # 止损比例
                 take_profit_pct: float = 0.10,  # 止盈比例
                 min_confidence: int = 70,  # 最小置信度
                 max_positions: int = 5):  # 最大持仓数
        """
        初始化自动交易器
        
        Args:
            initial_capital: 初始资金
            position_size: 单票仓位比例
            stop_loss_pct: 止损比例
            take_profit_pct: 止盈比例
            min_confidence: 最小交易置信度
            max_positions: 最大持仓数
        """
        self.adapter = get_chan_adapter()
        self.picker = ChanStockPicker(min_score=min_confidence)
        
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.min_confidence = min_confidence
        self.max_positions = max_positions
        
        # 持仓状态
        self.positions: Dict[str, Dict] = {}  # 当前持仓
        self.trade_history: List[Dict] = []   # 交易历史
        self.signals_cache: Dict[str, ChanSignal] = {}  # 信号缓存
        
    def analyze_for_trade(self, symbol: str, df: pd.DataFrame,
                         current_position: Dict = None) -> Optional[TradeDecision]:
        """
        分析并生成交易决策
        
        Args:
            symbol: 股票代码
            df: K线数据
            current_position: 当前持仓信息（如果有）
            
        Returns:
            交易决策或None
        """
        if not self.adapter or df.empty:
            return None
        
        # 获取缠论分析
        analysis = self.adapter.analyze(symbol, df)
        if not analysis:
            return None
        
        # 获取最新信号
        signal = self.adapter.get_latest_signal(symbol, df)
        if not signal:
            return None
        
        # 缓存信号
        self.signals_cache[symbol] = signal
        
        current_price = df['close'].iloc[-1]
        
        # 如果有持仓，检查是否需要卖出
        if current_position:
            return self._check_sell_conditions(symbol, current_price, 
                                              current_position, signal, analysis)
        else:
            # 无持仓，检查买入条件
            return self._check_buy_conditions(symbol, current_price, 
                                             signal, analysis)
    
    def _check_buy_conditions(self, symbol: str, price: float,
                             signal: ChanSignal, 
                             analysis: ChanAnalysis) -> Optional[TradeDecision]:
        """检查买入条件"""
        
        # 基本条件：必须是买入信号
        if signal.signal_type != 'buy':
            return None
        
        # 置信度检查
        if signal.strength < self.min_confidence:
            return None
        
        # 检查持仓数量限制
        if len(self.positions) >= self.max_positions:
            return None
        
        # 计算买入股数
        position_value = self.initial_capital * self.position_size
        shares = int(position_value / price / 100) * 100  # 整手
        
        if shares < 100:
            return None
        
        # 根据买卖点类型确定止盈止损
        stop_loss = price * (1 - self.stop_loss_pct)
        take_profit = price * (1 + self.take_profit_pct)
        
        # 1类买点可以放宽止损，3类买点收紧止损
        if '1类' in signal.bsp_type:
            stop_loss = price * (1 - self.stop_loss_pct * 1.5)
            take_profit = price * (1 + self.take_profit_pct * 1.2)
        elif '3类' in signal.bsp_type:
            stop_loss = price * (1 - self.stop_loss_pct * 0.8)
        
        return TradeDecision(
            symbol=symbol,
            action=TradeAction.BUY,
            price=price,
            shares=shares,
            reason=f"缠论{signal.bsp_type}信号，趋势{signal.trend}，{signal.description}",
            confidence=signal.strength,
            bsp_type=signal.bsp_type,
            stop_loss=stop_loss,
            take_profit=take_profit,
            chan_analysis=analysis
        )
    
    def _check_sell_conditions(self, symbol: str, price: float,
                              position: Dict, signal: ChanSignal,
                              analysis: ChanAnalysis) -> Optional[TradeDecision]:
        """检查卖出条件"""
        
        buy_price = position.get('buy_price', price)
        shares = position.get('shares', 0)
        profit_pct = (price - buy_price) / buy_price
        
        # 条件1：止损
        if profit_pct <= -self.stop_loss_pct:
            return TradeDecision(
                symbol=symbol,
                action=TradeAction.SELL,
                price=price,
                shares=shares,
                reason=f"止损触发，亏损{profit_pct*100:.2f}%",
                confidence=100,
                bsp_type='止损',
                stop_loss=0,
                take_profit=0,
                chan_analysis=analysis
            )
        
        # 条件2：止盈
        if profit_pct >= self.take_profit_pct:
            return TradeDecision(
                symbol=symbol,
                action=TradeAction.SELL,
                price=price,
                shares=shares,
                reason=f"止盈触发，盈利{profit_pct*100:.2f}%",
                confidence=100,
                bsp_type='止盈',
                stop_loss=0,
                take_profit=0,
                chan_analysis=analysis
            )
        
        # 条件3：缠论卖点信号
        if signal.signal_type == 'sell' and signal.strength >= self.min_confidence:
            return TradeDecision(
                symbol=symbol,
                action=TradeAction.SELL,
                price=price,
                shares=shares,
                reason=f"缠论{signal.bsp_type}信号，趋势{signal.trend}",
                confidence=signal.strength,
                bsp_type=signal.bsp_type,
                stop_loss=0,
                take_profit=0,
                chan_analysis=analysis
            )
        
        # 条件4：趋势反转（有买点信号但持仓亏损）
        if signal.signal_type == 'buy' and profit_pct < -0.02:
            # 可能是假突破，考虑减仓
            return TradeDecision(
                symbol=symbol,
                action=TradeAction.SELL,
                price=price,
                shares=shares // 2,  # 卖出一半
                reason=f"趋势可能反转，减仓锁定风险",
                confidence=60,
                bsp_type='减仓',
                stop_loss=0,
                take_profit=0,
                chan_analysis=analysis
            )
        
        return None
    
    def execute_scan(self, symbols: List[str], 
                    data_fetcher: Callable[[str], pd.DataFrame]) -> List[TradeDecision]:
        """
        执行扫描并生成交易决策
        
        Args:
            symbols: 股票代码列表
            data_fetcher: 数据获取函数
            
        Returns:
            交易决策列表
        """
        decisions = []
        
        for symbol in symbols:
            try:
                df = data_fetcher(symbol)
                if df is None or df.empty:
                    continue
                
                # 检查是否有持仓
                position = self.positions.get(symbol)
                
                # 分析并生成决策
                decision = self.analyze_for_trade(symbol, df, position)
                if decision:
                    decisions.append(decision)
                    
            except Exception as e:
                print(f"扫描 {symbol} 失败: {e}")
        
        return decisions
    
    def update_position(self, symbol: str, decision: TradeDecision):
        """更新持仓状态"""
        if decision.action == TradeAction.BUY:
            self.positions[symbol] = {
                'symbol': symbol,
                'buy_price': decision.price,
                'shares': decision.shares,
                'buy_time': datetime.now(),
                'bsp_type': decision.bsp_type,
                'stop_loss': decision.stop_loss,
                'take_profit': decision.take_profit
            }
        elif decision.action == TradeAction.SELL and symbol in self.positions:
            # 计算盈亏
            position = self.positions[symbol]
            profit = (decision.price - position['buy_price']) * decision.shares
            profit_pct = (decision.price - position['buy_price']) / position['buy_price']
            
            # 记录交易历史
            self.trade_history.append({
                'symbol': symbol,
                'buy_price': position['buy_price'],
                'sell_price': decision.price,
                'shares': decision.shares,
                'profit': profit,
                'profit_pct': profit_pct,
                'buy_time': position['buy_time'],
                'sell_time': datetime.now(),
                'buy_bsp': position['bsp_type'],
                'sell_bsp': decision.bsp_type
            })
            
            # 移除持仓
            if decision.shares >= position['shares']:
                del self.positions[symbol]
            else:
                position['shares'] -= decision.shares
    
    def get_position_summary(self) -> Dict:
        """获取持仓汇总"""
        return {
            'position_count': len(self.positions),
            'positions': list(self.positions.values()),
            'trade_count': len(self.trade_history),
            'total_profit': sum(t['profit'] for t in self.trade_history)
        }
    
    def format_decision(self, decision: TradeDecision) -> str:
        """格式化交易决策为字符串"""
        action_str = "买入" if decision.action == TradeAction.BUY else "卖出"
        
        lines = [
            f"【{action_str}决策】{decision.symbol}",
            f"价格: {decision.price:.2f}",
            f"数量: {decision.shares}股",
            f"金额: {decision.price * decision.shares:,.2f}元",
            f"置信度: {decision.confidence}",
            f"买卖点: {decision.bsp_type}",
            f"止损: {decision.stop_loss:.2f}" if decision.stop_loss > 0 else "",
            f"止盈: {decision.take_profit:.2f}" if decision.take_profit > 0 else "",
            f"理由: {decision.reason}",
        ]
        
        return "\n".join([l for l in lines if l])


class ChanStrategy:
    """
    缠论策略类
    用于回测和策略评估
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.adapter = get_chan_adapter(self.config)
        
    def generate_signals(self, df: pd.DataFrame, symbol: str = '') -> pd.DataFrame:
        """
        为历史数据生成交易信号
        
        Args:
            df: 历史K线数据
            symbol: 股票代码
            
        Returns:
            带信号标记的DataFrame
        """
        if not self.adapter or df.empty:
            return df
        
        # 复制数据
        result = df.copy()
        
        # 初始化信号列
        result['chan_signal'] = 0  # 0=无信号, 1=买入, -1=卖出
        result['chan_bsp_type'] = ''
        result['chan_score'] = 50
        result['chan_trend'] = ''
        
        # 滑动窗口分析
        window_size = 100
        
        for i in range(window_size, len(result)):
            window_df = result.iloc[i-window_size:i+1]
            
            try:
                signal = self.adapter.get_latest_signal(symbol, window_df)
                if signal:
                    if signal.signal_type == 'buy':
                        result.loc[result.index[i], 'chan_signal'] = 1
                    elif signal.signal_type == 'sell':
                        result.loc[result.index[i], 'chan_signal'] = -1
                    
                    result.loc[result.index[i], 'chan_bsp_type'] = signal.bsp_type
                    result.loc[result.index[i], 'chan_score'] = signal.strength
                    result.loc[result.index[i], 'chan_trend'] = signal.trend
            except Exception as e:
                continue
        
        return result
    
    def backtest(self, df: pd.DataFrame, symbol: str = '',
                 initial_capital: float = 100000) -> Dict:
        """
        回测策略
        
        Args:
            df: 历史数据
            symbol: 股票代码
            initial_capital: 初始资金
            
        Returns:
            回测结果字典
        """
        # 生成信号
        signals_df = self.generate_signals(df, symbol)
        
        # 模拟交易
        capital = initial_capital
        position = 0
        trades = []
        
        for i, row in signals_df.iterrows():
            price = row['close']
            signal = row['chan_signal']
            
            if signal == 1 and position == 0:  # 买入
                shares = int(capital * 0.2 / price / 100) * 100
                if shares >= 100:
                    cost = shares * price
                    capital -= cost
                    position = shares
                    trades.append({
                        'type': 'buy',
                        'price': price,
                        'shares': shares,
                        'cost': cost,
                        'date': i
                    })
            
            elif signal == -1 and position > 0:  # 卖出
                revenue = position * price
                capital += revenue
                profit = revenue - trades[-1]['cost'] if trades else 0
                trades.append({
                    'type': 'sell',
                    'price': price,
                    'shares': position,
                    'revenue': revenue,
                    'profit': profit,
                    'date': i
                })
                position = 0
        
        # 计算回测指标
        total_return = (capital - initial_capital) / initial_capital
        
        buy_trades = [t for t in trades if t['type'] == 'buy']
        sell_trades = [t for t in trades if t['type'] == 'sell']
        
        profits = [t['profit'] for t in sell_trades if 'profit' in t]
        win_trades = [p for p in profits if p > 0]
        
        return {
            'symbol': symbol,
            'initial_capital': initial_capital,
            'final_capital': capital,
            'total_return': total_return * 100,
            'total_trades': len(sell_trades),
            'win_rate': len(win_trades) / len(profits) * 100 if profits else 0,
            'trades': trades
        }


# 便捷函数
def get_chan_trader(config: Dict = None) -> Optional[ChanAutoTrader]:
    """获取交易器实例"""
    if not get_chan_adapter():
        return None
    return ChanAutoTrader(**(config or {}))


def analyze_trade_opportunity(symbol: str, df: pd.DataFrame,
                              position: Dict = None) -> Optional[TradeDecision]:
    """便捷函数：分析交易机会"""
    trader = ChanAutoTrader()
    return trader.analyze_for_trade(symbol, df, position)


if __name__ == '__main__':
    # 测试
    print("缠论自动交易模块测试")
    print("=" * 50)
    
    from stock_data import get_stock_data
    
    symbol = '000001'
    df = get_stock_data(symbol, count=100)
    
    if not df.empty:
        trader = ChanAutoTrader()
        
        # 测试买入分析
        decision = trader.analyze_for_trade(symbol, df)
        
        if decision:
            print(f"\n交易决策:")
            print(trader.format_decision(decision))
        else:
            print("\n无交易信号")
        
        # 测试策略回测
        print("\n" + "=" * 50)
        print("策略回测:")
        
        strategy = ChanStrategy()
        result = strategy.backtest(df, symbol)
        
        print(f"总收益率: {result['total_return']:.2f}%")
        print(f"交易次数: {result['total_trades']}")
        print(f"胜率: {result['win_rate']:.2f}%")
    else:
        print("获取数据失败")
