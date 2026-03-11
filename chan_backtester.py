"""
缠论回测适配器
支持使用 chan.py 和 czsc 双引擎进行策略回测
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class ChanBacktester:
    """缠论回测器"""
    
    def __init__(self, initial_capital: float = 100000.0):
        """
        初始化回测器
        
        Args:
            initial_capital: 初始资金
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []
        
        # 回测统计
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = 0.0
        self.max_drawdown = 0.0
    
    def backtest(self, df: pd.DataFrame, signals: List[Dict], 
                 engine: str = 'chan', commission: float = 0.001) -> Dict:
        """
        执行回测
        
        Args:
            df: DataFrame，包含 OHLCV 数据
            signals: 信号列表，每个信号包含：
                - date: 日期
                - code: 股票代码
                - signal: 买卖信号 (STRONG_BUY/BUY/SELL/STRONG_SELL)
                - action: 动作 (1/-1/0)
                - confidence: 置信度
                - price: 交易价格
            engine: 使用的引擎 ('chan' / 'czsc' / 'unified')
            commission: 手续费率（默认 0.1%）
        
        Returns:
            回测结果字典
        """
        print(f"\n开始回测 - 使用引擎：{engine}")
        print(f"初始资金：¥{self.initial_capital:,.2f}")
        print(f"信号数量：{len(signals)}")
        
        # 按日期排序信号
        signals_sorted = sorted(signals, key=lambda x: x['date'])
        
        # 执行回测
        for i, signal in enumerate(signals_sorted):
            self._execute_signal(signal, df, commission)
            
            # 记录权益曲线
            current_equity = self._calculate_current_equity(df, signal['date'])
            self.equity_curve.append({
                'date': signal['date'],
                'equity': current_equity,
                'capital': self.capital,
                'position_value': current_equity - self.capital
            })
            
            # 进度显示
            if (i + 1) % 10 == 0 or i == len(signals_sorted) - 1:
                print(f"进度：{i+1}/{len(signals_sorted)} ({(i+1)/len(signals_sorted)*100:.1f}%)")
        
        # 计算回测统计
        return self._calculate_statistics()
    
    def _execute_signal(self, signal: Dict, df: pd.DataFrame, commission: float):
        """执行单个交易信号"""
        code = signal['code']
        action = signal['action']
        price = signal.get('price', df[df['date'] == signal['date']]['close'].iloc[0])
        
        # 买入信号
        if action > 0:
            # 计算可买入股数
            available_cash = self.capital * 0.95  # 保留 5% 现金
            shares = int(available_cash / price / 100) * 100  # 100 股的整数倍
            
            if shares > 0:
                cost = shares * price * (1 + commission)
                
                # 更新持仓
                if code in self.positions:
                    old_shares = self.positions[code]['shares']
                    old_avg_price = self.positions[code]['avg_price']
                    new_avg_price = (old_shares * old_avg_price + shares * price) / (old_shares + shares)
                    self.positions[code] = {
                        'shares': old_shares + shares,
                        'avg_price': new_avg_price,
                        'code': code
                    }
                else:
                    self.positions[code] = {
                        'shares': shares,
                        'avg_price': price,
                        'code': code
                    }
                
                # 更新资金
                self.capital -= cost
                
                # 记录交易
                self.trades.append({
                    'date': signal['date'],
                    'code': code,
                    'type': 'BUY',
                    'price': price,
                    'shares': shares,
                    'commission': cost * commission,
                    'signal': signal['signal']
                })
        
        # 卖出信号
        elif action < 0:
            if code in self.positions:
                position = self.positions[code]
                shares = position['shares']
                avg_price = position['avg_price']
                
                # 全部卖出
                revenue = shares * price * (1 - commission)
                profit = revenue - shares * avg_price
                
                # 更新资金
                self.capital += revenue
                
                # 更新统计
                self.total_profit += profit
                if profit > 0:
                    self.winning_trades += 1
                else:
                    self.losing_trades += 1
                
                # 记录交易
                self.trades.append({
                    'date': signal['date'],
                    'code': code,
                    'type': 'SELL',
                    'price': price,
                    'shares': shares,
                    'commission': revenue * commission,
                    'profit': profit,
                    'signal': signal['signal']
                })
                
                # 清除持仓
                del self.positions[code]
        
        self.total_trades = len([t for t in self.trades if t['type'] == 'SELL'])
    
    def _calculate_current_equity(self, df: pd.DataFrame, date: str) -> float:
        """计算当前总权益"""
        # 获取该日期的收盘价
        try:
            current_price = df[df['date'] == date]['close'].iloc[0]
        except:
            current_price = df['close'].iloc[-1]
        
        # 计算持仓市值
        position_value = sum(
            pos['shares'] * current_price 
            for pos in self.positions.values()
        )
        
        return self.capital + position_value
    
    def _calculate_statistics(self) -> Dict:
        """计算回测统计指标"""
        if not self.equity_curve:
            return {'error': '无回测数据'}
        
        # 提取权益序列
        equity_values = [e['equity'] for e in self.equity_curve]
        
        # 计算收益率
        returns = pd.Series(equity_values).pct_change().dropna()
        
        # 计算累计收益
        total_return = (equity_values[-1] - self.initial_capital) / self.initial_capital * 100
        
        # 计算年化收益（假设 250 个交易日）
        n_days = len(equity_values)
        annual_return = ((equity_values[-1] / self.initial_capital) ** (250 / n_days) - 1) * 100
        
        # 计算最大回撤
        max_dd = 0.0
        peak = equity_values[0]
        for value in equity_values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak * 100
            if drawdown > max_dd:
                max_dd = drawdown
        
        # 计算夏普比率（假设无风险利率 3%）
        risk_free_rate = 0.03
        excess_returns = returns - risk_free_rate / 250
        sharpe = np.sqrt(252) * excess_returns.mean() / returns.std() if returns.std() != 0 else 0
        
        # 计算胜率
        win_rate = self.winning_trades / self.total_trades * 100 if self.total_trades > 0 else 0
        
        # 计算盈亏比
        avg_win = np.mean([t['profit'] for t in self.trades if t.get('profit', 0) > 0]) if self.winning_trades > 0 else 0
        avg_loss = abs(np.mean([t['profit'] for t in self.trades if t.get('profit', 0) < 0])) if self.losing_trades > 0 else 0
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0
        
        return {
            'initial_capital': self.initial_capital,
            'final_equity': equity_values[-1],
            'total_return': round(total_return, 2),
            'annual_return': round(annual_return, 2),
            'max_drawdown': round(max_dd, 2),
            'sharpe_ratio': round(sharpe, 2),
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': round(win_rate, 2),
            'profit_loss_ratio': round(profit_loss_ratio, 2),
            'total_profit': round(self.total_profit, 2),
            'equity_curve': self.equity_curve,
            'trades': self.trades
        }


def generate_signals_from_strategy(df: pd.DataFrame, strategy_type: str = 'chan_divergence') -> List[Dict]:
    """
    从策略生成信号
    
    Args:
        df: DataFrame，包含 OHLCV 数据
        strategy_type: 策略类型
    
    Returns:
        信号列表
    """
    signals = []
    
    if strategy_type == 'chan_divergence':
        # 使用缠论背离策略
        from chan_divergence_strategy import ChanDivergenceStrategy
        
        # 滚动窗口生成信号
        window = 60
        for i in range(window, len(df)):
            subset_df = df.iloc[i-window:i].copy()
            strategy = ChanDivergenceStrategy(subset_df)
            
            # 模拟缠论分析（实际应接入真实缠论）
            # 这里用价格位置模拟笔的方向
            recent_low = subset_df['low'].min()
            recent_high = subset_df['high'].max()
            current_price = subset_df['close'].iloc[-1]
            
            # 简单模拟：价格在低位时生成买入信号
            price_position = (current_price - recent_low) / (recent_high - recent_low)
            
            # 根据价格位置模拟缠论背驰
            if price_position < 0.2:  # 低位，可能底背驰
                simulated_signal = 'BUY' if price_position < 0.1 else 'HOLD'
                action = 1 if simulated_signal != 'HOLD' else 0
            elif price_position > 0.8:  # 高位，可能顶背驰
                simulated_signal = 'SELL' if price_position > 0.9 else 'HOLD'
                action = -1 if simulated_signal != 'HOLD' else 0
            else:
                simulated_signal = 'HOLD'
                action = 0
            
            # 只记录有信号的日期
            if action != 0:
                signals.append({
                    'date': df.iloc[i]['date'],
                    'code': 'TEST',
                    'signal': simulated_signal,
                    'action': action,
                    'confidence': 60 + int((1 - abs(price_position - 0.5) * 2) * 40),  # 60-100
                    'price': df.iloc[i]['close']
                })
    
    elif strategy_type == 'dual_engine':
        # 双引擎策略（chan.py + czsc 共振）
        # TODO: 接入双引擎分析
        pass
    
    return signals


def quick_backtest_demo():
    """快速回测演示"""
    print("="*70)
    print("缠论回测系统演示")
    print("="*70)
    
    # 生成测试数据
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=200, freq='D')
    close = 100 + np.cumsum(np.random.randn(200))
    
    df = pd.DataFrame({
        'date': dates.strftime('%Y-%m-%d'),
        'open': close * 0.99,
        'high': close * 1.02,
        'low': close * 0.98,
        'close': close,
        'volume': np.random.randint(1000, 10000, 200)
    })
    
    # 生成信号
    print("\n生成交易信号...")
    signals = generate_signals_from_strategy(df, 'chan_divergence')
    print(f"生成信号数量：{len(signals)}")
    
    # 执行回测
    backtester = ChanBacktester(initial_capital=100000)
    result = backtester.backtest(df, signals, engine='chan')
    
    # 输出结果
    print("\n" + "="*70)
    print("回测结果")
    print("="*70)
    print(f"初始资金：¥{result['initial_capital']:,.2f}")
    print(f"最终权益：¥{result['final_equity']:,.2f}")
    print(f"总收益率：{result['total_return']:.2f}%")
    print(f"年化收益：{result['annual_return']:.2f}%")
    print(f"最大回撤：{result['max_drawdown']:.2f}%")
    print(f"夏普比率：{result['sharpe_ratio']:.2f}")
    print(f"交易次数：{result['total_trades']}")
    print(f"胜率：{result['win_rate']:.2f}%")
    print(f"盈亏比：{result['profit_loss_ratio']:.2f}")
    print(f"总盈利：¥{result['total_profit']:,.2f}")
    print("="*70)


if __name__ == '__main__':
    quick_backtest_demo()
