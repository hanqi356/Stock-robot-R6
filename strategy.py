"""
交易策略模块
基于缠论买卖信号实现自动交易策略
支持回测和实盘模式
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json

@dataclass
class Trade:
    """交易记录"""
    datetime: datetime
    symbol: str
    action: str  # 'buy' or 'sell'
    price: float
    shares: int
    reason: str
    score: int

@dataclass
class Position:
    """持仓信息"""
    symbol: str
    shares: int
    avg_cost: float
    buy_time: datetime
    buy_price: float
    buy_score: int


class ChanlunStrategy:
    """
    缠论交易策略
    
    买入条件：
    1. 买点得分 >= 60（黄色以上买点）
    2. MACD金叉确认
    3. 价格突破MA5
    
    卖出条件：
    1. 卖点得分 >= 60
    2. MACD死叉
    3. 价格跌破MA20
    4. 止损：亏损超过5%
    5. 止盈：盈利超过10%
    """
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        position_size: float = 0.2,  # 单只股票仓位20%
        stop_loss: float = 0.05,      # 止损5%
        take_profit: float = 0.10,    # 止盈10%
        min_buy_score: int = 60,      # 最小买入得分
        max_positions: int = 5        # 最大持仓数
    ):
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.min_buy_score = min_buy_score
        self.max_positions = max_positions
        
        # 状态
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        
    def reset(self):
        """重置策略状态"""
        self.cash = self.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []
        
    def check_buy_signal(self, row: pd.Series) -> Tuple[bool, str]:
        """
        检查买入信号（融合缠论引擎 + 通达信指标）

        优先级：
        1. 缠论1/2/3类买点（czsc引擎）— 最强信号
        2. 买点得分 + MACD/均线确认 — 辅助信号
        """
        reasons = []

        # === 路径A：缠论买点信号（强信号，放宽辅助条件） ===
        chan_buy = row.get('chan_buy_signal')
        if pd.notna(chan_buy) and chan_buy is not None:
            # 缠论买点直接触发，仅需评分 >= 40
            if row['买点得分'] >= 40:
                reasons.append(f"缠论{chan_buy}")
                if row.get('MACD金叉'):
                    reasons.append("MACD金叉")
                return True, ", ".join(reasons) + f" (评分{row['买点得分']:.0f})"

        # === 路径B：传统条件（需全部满足） ===
        # 条件1：买点得分达标
        if row['买点得分'] < self.min_buy_score:
            return False, "买点得分不足"

        # 条件2：至少满足 MACD金叉 或 背驰信号 之一
        has_macd = bool(row.get('MACD金叉', False))
        has_divergence = bool(row.get('下降背驰', False))
        if not has_macd and not has_divergence:
            return False, "无MACD金叉或背驰信号"

        if has_macd:
            reasons.append("MACD金叉")
        if has_divergence:
            reasons.append("背驰确认")

        # 条件3：趋势不能是强下跌
        chan_trend = row.get('chan_trend', '')
        if chan_trend == '下跌' and row['买点得分'] < 70:
            return False, "下跌趋势中评分不足70"

        reasons.append(f"评分{row['买点得分']:.0f}")
        return True, ", ".join(reasons)
    
    def check_sell_signal(self, symbol: str, row: pd.Series, position: Position) -> Tuple[bool, str]:
        """
        检查卖出信号（融合缠论引擎 + 传统条件）
        """
        current_price = row['close']
        profit_pct = (current_price - position.buy_price) / position.buy_price
        
        # 条件1：止损
        if profit_pct <= -self.stop_loss:
            return True, f"止损触发: 亏损{profit_pct*100:.2f}%"
        
        # 条件2：止盈
        if profit_pct >= self.take_profit:
            return True, f"止盈触发: 盈利{profit_pct*100:.2f}%"

        # 条件3：缠论卖点信号
        chan_sell = row.get('chan_sell_signal')
        if pd.notna(chan_sell) and chan_sell is not None:
            return True, f"缠论{chan_sell} (盈亏{profit_pct*100:+.2f}%)"

        # 条件4：卖点得分达标
        sell_score = row.get('卖点得分', 0)
        if sell_score >= 70:
            return True, f"卖点信号: 得分{sell_score:.0f}"
        
        # 条件5：MACD死叉
        if row.get('MACD死叉'):
            return True, "MACD死叉"
        
        # 条件6：跌破MA20
        if current_price < row.get('MA20', 0):
            return True, "跌破MA20"
        
        return False, ""
    
    def calculate_position_shares(self, price: float) -> int:
        """计算买入股数"""
        position_value = self.cash * self.position_size
        shares = int(position_value / price / 100) * 100  # 整手
        return max(shares, 100)  # 至少1手
    
    def buy(self, symbol: str, row: pd.Series, reason: str):
        """执行买入"""
        if len(self.positions) >= self.max_positions:
            return False
        
        if symbol in self.positions:
            return False
        
        price = row['close']
        shares = self.calculate_position_shares(price)
        cost = price * shares
        
        if cost > self.cash:
            return False
        
        # 执行买入
        self.cash -= cost
        self.positions[symbol] = Position(
            symbol=symbol,
            shares=shares,
            avg_cost=price,
            buy_time=row['datetime'],
            buy_price=price,
            buy_score=row['买点得分']
        )
        
        trade = Trade(
            datetime=row['datetime'],
            symbol=symbol,
            action='buy',
            price=price,
            shares=shares,
            reason=reason,
            score=row['买点得分']
        )
        self.trades.append(trade)
        
        print(f"[买入] {symbol} @ {price:.2f} x {shares}股, 原因: {reason}")
        return True
    
    def sell(self, symbol: str, row: pd.Series, position: Position, reason: str):
        """执行卖出"""
        price = row['close']
        shares = position.shares
        revenue = price * shares
        
        # 计算盈亏
        profit = revenue - position.buy_price * shares
        profit_pct = profit / (position.buy_price * shares) * 100
        
        # 执行卖出
        self.cash += revenue
        del self.positions[symbol]
        
        trade = Trade(
            datetime=row['datetime'],
            symbol=symbol,
            action='sell',
            price=price,
            shares=shares,
            reason=reason,
            score=row.get('卖点得分', 0)
        )
        self.trades.append(trade)
        
        print(f"[卖出] {symbol} @ {price:.2f} x {shares}股, 盈亏: {profit_pct:+.2f}%, 原因: {reason}")
        return True
    
    def update_equity(self, current_time: datetime, prices: Dict[str, float]):
        """更新权益曲线"""
        equity = self.cash
        for symbol, position in self.positions.items():
            if symbol in prices:
                equity += position.shares * prices[symbol]
        self.equity_curve.append((current_time, equity))
    
    def run_backtest(self, data_dict: Dict[str, pd.DataFrame]) -> Dict:
        """
        运行回测
        
        Parameters:
            data_dict: {symbol: DataFrame with indicators}
        
        Returns:
            回测结果统计
        """
        self.reset()
        
        # 合并所有数据，按时间排序
        all_dates = set()
        for df in data_dict.values():
            all_dates.update(df['datetime'].tolist())
        all_dates = sorted(all_dates)
        
        print(f"开始回测，共{len(all_dates)}个交易日")
        
        for date in all_dates:
            current_prices = {}
            
            for symbol, df in data_dict.items():
                # 获取当日数据
                day_data = df[df['datetime'] == date]
                if day_data.empty:
                    continue
                
                row = day_data.iloc[0]
                current_prices[symbol] = row['close']
                
                # 检查持仓卖出
                if symbol in self.positions:
                    position = self.positions[symbol]
                    should_sell, reason = self.check_sell_signal(symbol, row, position)
                    if should_sell:
                        self.sell(symbol, row, position, reason)
                
                # 检查买入信号
                else:
                    should_buy, reason = self.check_buy_signal(row)
                    if should_buy:
                        self.buy(symbol, row, reason)
            
            # 更新权益
            self.update_equity(date, current_prices)
        
        # 强制平仓所有持仓
        for symbol, position in list(self.positions.items()):
            df = data_dict[symbol]
            last_row = df.iloc[-1]
            self.sell(symbol, last_row, position, "回测结束平仓")
        
        return self.get_stats()
    
    def get_stats(self) -> Dict:
        """获取回测统计"""
        trades_df = pd.DataFrame([{
            'datetime': t.datetime,
            'symbol': t.symbol,
            'action': t.action,
            'price': t.price,
            'shares': t.shares,
            'reason': t.reason,
            'score': t.score
        } for t in self.trades])
        
        if trades_df.empty:
            return {"error": "无交易记录"}
        
        # 计算每笔交易盈亏
        profits = []
        buy_trades = trades_df[trades_df['action'] == 'buy']
        sell_trades = trades_df[trades_df['action'] == 'sell']
        
        for _, sell in sell_trades.iterrows():
            matching_buy = buy_trades[
                (buy_trades['symbol'] == sell['symbol']) &
                (buy_trades['datetime'] < sell['datetime'])
            ].iloc[-1:]
            
            if not matching_buy.empty:
                buy = matching_buy.iloc[0]
                profit = (sell['price'] - buy['price']) / buy['price'] * 100
                profits.append(profit)
        
        total_return = (self.cash - self.initial_capital) / self.initial_capital * 100
        
        win_trades = [p for p in profits if p > 0]
        lose_trades = [p for p in profits if p <= 0]

        stats = {
            "初始资金": self.initial_capital,
            "最终资金": self.cash,
            "总收益率": f"{total_return:.2f}%",
            "总交易次数": len(self.trades),
            "买入次数": len(buy_trades),
            "卖出次数": len(sell_trades),
            "盈利次数": len(win_trades),
            "亏损次数": len(lose_trades),
            "胜率": f"{len(win_trades) / len(profits) * 100:.2f}%" if profits else "0%",
            "平均盈利": f"{np.mean(win_trades):.2f}%" if win_trades else "0%",
            "平均亏损": f"{np.mean(lose_trades):.2f}%" if lose_trades else "0%",
            "最大单笔盈利": f"{max(profits):.2f}%" if profits else "0%",
            "最大单笔亏损": f"{min(profits):.2f}%" if profits else "0%"
        }
        
        return stats
    
    def save_results(self, filename: str = 'backtest_results.json'):
        """保存回测结果"""
        stats = self.get_stats()
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        print(f"结果已保存至: {filename}")


# ============ 实盘交易接口 ============

class LiveTrader(ChanlunStrategy):
    """实盘交易器（基于easytrader）"""
    
    def __init__(self, broker: str = 'ht', **kwargs):
        super().__init__(**kwargs)
        self.broker = broker
        self.trader = None
        
    def connect_broker(self):
        """连接券商"""
        try:
            import easytrader
            self.trader = easytrader.use(self.broker)
            self.trader.connect()
            print(f"已连接券商: {self.broker}")
            return True
        except Exception as e:
            print(f"连接券商失败: {e}")
            return False
    
    def buy(self, symbol: str, row: pd.Series, reason: str) -> bool:
        """实盘买入"""
        # 先执行模拟买入检查
        if not super().buy(symbol, row, reason):
            return False
        
        # 实盘下单
        if self.trader:
            try:
                price = row['close']
                shares = self.positions[symbol].shares
                result = self.trader.buy(symbol, price, shares)
                print(f"实盘买入下单: {result}")
                return True
            except Exception as e:
                print(f"实盘买入失败: {e}")
                return False
        return True
    
    def sell(self, symbol: str, row: pd.Series, position: Position, reason: str) -> bool:
        """实盘卖出"""
        # 先执行模拟卖出
        if not super().sell(symbol, row, position, reason):
            return False
        
        # 实盘下单
        if self.trader:
            try:
                price = row['close']
                shares = position.shares
                result = self.trader.sell(symbol, price, shares)
                print(f"实盘卖出下单: {result}")
                return True
            except Exception as e:
                print(f"实盘卖出失败: {e}")
                return False
        return True


if __name__ == '__main__':
    # 回测示例
    from stock_data import get_stock_data
    from indicators import calculate_indicators
    
    print("=" * 50)
    print("缠论策略回测")
    print("=" * 50)
    
    # 获取多只股票数据
    symbols = ['600519', '000001', '000858']
    data_dict = {}
    
    for symbol in symbols:
        print(f"\n获取 {symbol} 数据...")
        df = get_stock_data(symbol, 'day', 252)  # 一年数据
        if not df.empty:
            df = calculate_indicators(df, symbol=symbol)
            data_dict[symbol] = df
    
    if data_dict:
        # 运行回测
        strategy = ChanlunStrategy(
            initial_capital=100000,
            position_size=0.3,
            stop_loss=0.05,
            take_profit=0.15,
            min_buy_score=60
        )
        
        results = strategy.run_backtest(data_dict)
        
        print("\n" + "=" * 50)
        print("回测结果")
        print("=" * 50)
        for key, value in results.items():
            print(f"{key}: {value}")
        
        strategy.save_results()
    else:
        print("获取数据失败，无法回测")
