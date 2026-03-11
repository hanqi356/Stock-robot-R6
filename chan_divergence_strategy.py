"""
缠论 + 背离双引擎策略
整合缠论背驰和 MACD 背离，提供高胜率交易信号
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
import talib


class ChanDivergenceStrategy:
    """缠论背离双重确认策略"""
    
    def __init__(self, df: pd.DataFrame, fastperiod=11, slowperiod=26, signalperiod=9):
        """
        初始化策略
        
        Args:
            df: DataFrame，包含 open/high/low/close/vol 列
            fastperiod: MACD 快周期
            slowperiod: MACD 慢周期
            signalperiod: MACD 信号线周期
        """
        self.df = df.copy()
        self.fastperiod = fastperiod
        self.slowperiod = slowperiod
        self.signalperiod = signalperiod
        
        # 计算 MACD
        self.dif, self.dea, self.macd = talib.MACD(
            df['close'].values,
            fastperiod=self.fastperiod,
            slowperiod=self.slowperiod,
            signalperiod=self.signalperiod
        )
        
        # 背驰状态缓存
        self.chan_divergence = None
        self.macd_divergence = None
        
    def calculate_macd_divergence(self) -> int:
        """
        检测 MACD 背离
        
        Returns:
            0: 无背离
            1: 顶背离（看跌）
            -1: 底背离（看涨）
        """
        if len(self.df) < (self.fastperiod + self.slowperiod + self.signalperiod) * 5:
            return 0
        
        macd = self.macd
        dif = self.dif
        close = self.df['close'].values
        
        # 检查最新状态
        if macd[-1] > 0 > macd[-2]:
            # 金叉，检查底背离
            idx_gold = np.where((macd[:-1] < 0) & (macd[1:] > 0))[0] + 1
            if len(idx_gold) > 1:
                if close[idx_gold[-1]] < close[idx_gold[-2]] and dif[idx_gold[-1]] > dif[idx_gold[-2]]:
                    return -1  # 底背离
                    
        elif macd[-1] < 0 < macd[-2]:
            # 死叉，检查顶背离
            idx_dead = np.where((macd[:-1] > 0) & (macd[1:] < 0))[0] + 1
            if len(idx_dead) > 1:
                if close[idx_dead[-1]] > close[idx_dead[-2]] and dif[idx_dead[-1]] < dif[idx_dead[-2]]:
                    return 1  # 顶背离
        
        return 0
    
    def calculate_chan_divergence(self, bi_list: list) -> Tuple[int, float]:
        """
        检测缠论背驰
        
        Args:
            bi_list: 笔列表，每笔包含 direction/start_price/end_price
            
        Returns:
            divergence: 0-无背驰，1-底背驰，-1-顶背驰
            strength: 背驰强度 0-1
        """
        if not bi_list or len(bi_list) < 2:
            return 0, 0.0
        
        last_bi = bi_list[-1]
        prev_bi = bi_list[-2]
        
        # 底背驰检测：向下笔 + 价格新低 + 力度减弱
        if last_bi['direction'] == 'down':
            if last_bi['end_price'] < prev_bi['start_price']:
                price_change = abs(last_bi['end_price'] - last_bi['start_price'])
                prev_change = abs(prev_bi['end_price'] - prev_bi['start_price'])
                
                if prev_change > 0 and price_change < prev_change:
                    strength = 1 - price_change / prev_change
                    return 1, round(strength, 3)
        
        # 顶背驰检测：向上笔 + 价格新高 + 力度减弱
        elif last_bi['direction'] == 'up':
            if last_bi['end_price'] > prev_bi['start_price']:
                price_change = abs(last_bi['end_price'] - last_bi['start_price'])
                prev_change = abs(prev_bi['end_price'] - prev_bi['start_price'])
                
                if prev_change > 0 and price_change > prev_change:
                    strength = (price_change - prev_change) / prev_change
                    return -1, round(min(strength, 1.0), 3)
        
        return 0, 0.0
    
    def generate_signal(self, chan_analysis=None) -> Dict:
        """
        生成交易信号（双重确认）
        
        Args:
            chan_analysis: 缠论分析结果，包含 bi_list
            
        Returns:
            信号字典
        """
        # 1. MACD 背离
        macd_div = self.calculate_macd_divergence()
        
        # 2. 缠论背驰
        chan_div = 0
        chan_strength = 0.0
        if chan_analysis and 'bi_list' in chan_analysis:
            chan_div, chan_strength = self.calculate_chan_divergence(chan_analysis['bi_list'])
        
        # 3. 双重确认逻辑
        signal = "HOLD"
        action = 0  # -1:卖出，0:持有，1:买入
        confidence = 0
        reason = []
        
        # 强烈买入：缠论底背驰 + MACD 底背离
        if chan_div == 1 and macd_div == -1:
            signal = "STRONG_BUY"
            action = 1
            confidence = 90
            reason.append("双重底背离确认")
            reason.append(f"缠论底背驰强度：{chan_strength:.1%}")
            
        # 一般买入：单一底背离信号
        elif chan_div == 1 or macd_div == -1:
            signal = "BUY"
            action = 1
            confidence = 60
            if chan_div == 1:
                reason.append("缠论底背驰")
            if macd_div == -1:
                reason.append("MACD 底背离")
                
        # 强烈卖出：缠论顶背驰 + MACD 顶背离
        elif chan_div == -1 and macd_div == 1:
            signal = "STRONG_SELL"
            action = -1
            confidence = 90
            reason.append("双重顶背离确认")
            reason.append(f"缠论顶背驰强度：{chan_strength:.1%}")
            
        # 一般卖出：单一顶背离信号
        elif chan_div == -1 or macd_div == 1:
            signal = "SELL"
            action = -1
            confidence = 60
            if chan_div == -1:
                reason.append("缠论顶背驰")
            if macd_div == 1:
                reason.append("MACD 顶背离")
        
        # 无信号
        else:
            signal = "HOLD"
            action = 0
            confidence = 50
            reason.append("无明确背离信号")
        
        return {
            'signal': signal,
            'action': action,  # 新增：标准化动作
            'confidence': confidence,
            'reason': reason,
            'chan_divergence': chan_div,
            'chan_strength': chan_strength,
            'macd_divergence': macd_div,
            'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def get_latest_data(self) -> Dict:
        """获取最新数据"""
        latest_close = self.df['close'].iloc[-1]
        latest_dif = self.dif[-1]
        latest_dea = self.dea[-1]
        latest_macd = self.macd[-1]
        
        # 判断 MACD 状态
        macd_status = "金叉" if latest_dif > latest_dea else "死叉"
        
        return {
            'close': latest_close,
            'dif': latest_dif,
            'dea': latest_dea,
            'macd': latest_macd,
            'macd_status': macd_status
        }


def test_strategy():
    """测试策略"""
    print("="*70)
    print("缠论 + 背离双引擎策略测试")
    print("="*70)
    
    # 生成测试数据
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    
    # 构造一个有背离的走势
    close = np.cumsum(np.random.randn(100)) + 100
    # 制造底背离：价格新低但指标不新低
    close[80:] = close[80:] - 10  # 价格下跌
    close[90:] = close[90:] + 5   # 反弹
    
    df = pd.DataFrame({
        'open': close * 0.99,
        'high': close * 1.02,
        'low': close * 0.98,
        'close': close,
        'volume': np.random.randint(1000, 10000, 100)
    }, index=dates)
    
    # 创建策略实例
    strategy = ChanDivergenceStrategy(df)
    
    # 模拟缠论分析结果
    chan_analysis = {
        'bi_list': [
            {'direction': 'down', 'start_price': 110, 'end_price': 105},
            {'direction': 'up', 'start_price': 105, 'end_price': 108},
            {'direction': 'down', 'start_price': 108, 'end_price': 102},  # 创新低
        ]
    }
    
    # 生成信号
    signal_result = strategy.generate_signal(chan_analysis)
    
    print("\n最新数据:")
    latest = strategy.get_latest_data()
    print(f"  收盘价：{latest['close']:.2f}")
    print(f"  DIF: {latest['dif']:.4f}")
    print(f"  DEA: {latest['dea']:.4f}")
    print(f"  MACD: {latest['macd']:.4f}")
    print(f"  MACD 状态：{latest['macd_status']}")
    
    print("\n交易信号:")
    print(f"  信号：{signal_result['signal']}")
    print(f"  置信度：{signal_result['confidence']}%")
    print(f"  原因:")
    for r in signal_result['reason']:
        print(f"    - {r}")
    
    print("\n背驰状态:")
    print(f"  缠论背驰：{signal_result['chan_divergence']} (强度：{signal_result['chan_strength']:.1%})")
    print(f"  MACD 背离：{signal_result['macd_divergence']}")
    
    print("\n" + "="*70)
    print("测试完成！")
    print("="*70)


if __name__ == '__main__':
    test_strategy()
