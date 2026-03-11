# -*- coding: utf-8 -*-
"""
通达信选股指标 - 从OpenBB-develop整合
包含：缠论笔段、中枢、买卖点评分系统
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List


class TDXIndicatorAdapter:
    """通达信指标适配器"""
    
    @staticmethod
    def ma(series, n):
        """简单移动平均线 MA(X,N)"""
        return series.rolling(window=n).mean()
    
    @staticmethod
    def ema(series, n):
        """指数移动平均线 EMA(X,N)"""
        return series.ewm(span=n, adjust=False).mean()
    
    @staticmethod
    def sma(series, n, m):
        """平滑移动平均 SMA(X,N,M)"""
        result = series.copy()
        for i in range(1, len(series)):
            result.iloc[i] = (m * series.iloc[i] + (n - m) * result.iloc[i-1]) / n
        return result
    
    @staticmethod
    def ref(series, n):
        """向前引用 REF(X,N)"""
        return series.shift(n)
    
    @staticmethod
    def hhv(series, n):
        """最高值 HHV(X,N)"""
        return series.rolling(window=n).max()
    
    @staticmethod
    def llv(series, n):
        """最低值 LLV(X,N)"""
        return series.rolling(window=n).min()
    
    @staticmethod
    def cross(series1, series2):
        """上穿 CROSS(X,Y)"""
        return (series1 > series2) & (series1.shift(1) <= series2.shift(1))
    
    @staticmethod
    def count(condition, n):
        """统计满足条件的周期数 COUNT(X,N)"""
        return condition.rolling(window=n).sum()


class TDXStockPicker:
    """通达信选股指标实现"""
    
    def __init__(self, df: pd.DataFrame):
        if len(df) < 60:
            raise ValueError(f"数据量不足，需要至少60条数据，当前仅有{len(df)}条")
        
        self.df = df.copy()
        self.tdx = TDXIndicatorAdapter()
        
        # 计算基础指标
        self._calculate_ma()
        self._calculate_macd()
        self._calculate_local_points()
        self._calculate_bi_duan()
        self._calculate_zhongshu()
    
    def _calculate_ma(self):
        """计算均线"""
        close = self.df['close']
        self.df['MA5'] = self.tdx.ma(close, 5)
        self.df['MA13'] = self.tdx.ma(close, 13)
        self.df['MA20'] = self.tdx.ma(close, 20)
        self.df['MA60'] = self.tdx.ma(close, 60)
        
        # 均线交叉
        self.df['均线金叉'] = self.tdx.cross(self.df['MA5'], self.df['MA13'])
        self.df['均线死叉'] = self.tdx.cross(self.df['MA13'], self.df['MA5'])
    
    def _calculate_macd(self):
        """计算MACD"""
        close = self.df['close']
        dif = self.tdx.ema(close, 6) - self.tdx.ema(close, 13)
        dea = self.tdx.ema(dif, 5)
        macd = (dif - dea) * 2
        
        self.df['DIF'] = dif
        self.df['DEA'] = dea
        self.df['MACD'] = macd
        self.df['MACD金叉'] = self.tdx.cross(dif, dea)
        self.df['MACD死叉'] = self.tdx.cross(dea, dif)
    
    def _calculate_local_points(self):
        """计算局部高低点"""
        h = self.df['high']
        l = self.df['low']
        
        # KU1/KD1: 3日高低点
        ku1 = (h == self.tdx.hhv(h, 3)).astype(int)
        kd1 = (l == self.tdx.llv(l, 3)).astype(int)
        
        self.df['KU1'] = ku1
        self.df['KD1'] = kd1
    
    def _calculate_bi_duan(self):
        """计算笔和段（简化版）"""
        # 使用局部高低点作为笔
        h = self.df['high']
        l = self.df['low']
        
        # 局部高点：3日高点且高于前后
        high_point = (h == self.tdx.hhv(h, 3)) & (h > self.tdx.ref(h, 1)) & (h > self.tdx.ref(h, -1))
        # 局部低点：3日低点且低于前后
        low_point = (l == self.tdx.llv(l, 3)) & (l < self.tdx.ref(l, 1)) & (l < self.tdx.ref(l, -1))
        
        self.df['顶分型'] = high_point.astype(int)
        self.df['底分型'] = low_point.astype(int)
        
        # 笔：顶底分型交替
        bi = pd.Series(0, index=self.df.index)
        last_type = 0  # 0=无, 1=顶, -1=底
        for i in range(len(self.df)):
            if high_point.iloc[i] and last_type != 1:
                bi.iloc[i] = 1
                last_type = 1
            elif low_point.iloc[i] and last_type != -1:
                bi.iloc[i] = -1
                last_type = -1
        
        self.df['笔'] = bi
    
    def _calculate_zhongshu(self):
        """计算中枢（简化版）"""
        h = self.df['high']
        l = self.df['low']
        
        # 计算最近的高点和低点
        p1 = self.tdx.hhv(h, 10)
        t1 = self.tdx.llv(l, 10)
        p2 = self.tdx.ref(p1, 10)
        t2 = self.tdx.ref(t1, 10)
        
        # 中枢上下沿
        zd = pd.Series(np.maximum(t1, t2), index=self.df.index)
        zg = pd.Series(np.minimum(p1, p2), index=self.df.index)
        
        self.df['中枢下沿'] = zd
        self.df['中枢上沿'] = zg
        self.df['中枢区间'] = zg - zd
    
    def calculate_buy_score(self) -> pd.DataFrame:
        """计算买入评分"""
        close = self.df['close']
        high = self.df['high']
        low = self.df['low']
        vol = self.df.get('volume', self.df.get('vol', pd.Series([0]*len(self.df), index=self.df.index)))
        dif = self.df['DIF']
        bi = self.df['笔']
        
        # 基础得分
        base_score = 30
        
        # 1. 中枢背离 (+20分)
        divergence1 = (low < self.tdx.ref(self.tdx.llv(low, 10), 1)) & \
                     (dif > self.tdx.ref(self.tdx.llv(dif, 10), 1))
        divergence2 = (high > self.tdx.ref(self.tdx.hhv(high, 10), 1)) & \
                     (dif < self.tdx.ref(self.tdx.hhv(dif, 10), 1))
        zhongshu_divergence = (divergence1 | divergence2).astype(int)
        zhongshu_score = zhongshu_divergence * 20
        
        # 2. 笔内部背离 (+20分)
        bi_divergence = ((bi == -1) & 
                        (low < self.tdx.ref(self.tdx.llv(low, 5), 1)) & 
                        (dif > self.tdx.ref(self.tdx.llv(dif, 5), 1))).astype(int)
        bi_divergence_score = bi_divergence * 20
        
        # 3. 多次衰竭 (+10分/次)
        exhaustion_count = self.tdx.count(bi_divergence, 10)
        exhaustion_score = exhaustion_count * 10
        
        # 4. 最有杀伤力分型 (+15分)
        most_powerful = ((self.tdx.ref(close, 1) < self.tdx.ref(close, 2) * 0.98) &
                        (close > self.tdx.ref(close, 1) * 1.02) &
                        (vol > self.tdx.ref(vol, 1) * 1.2)).astype(int)
        most_powerful_score = most_powerful * 15
        
        # 5. 次有杀伤力分型 (+10分)
        secondary_powerful = ((self.tdx.ref(close, 1) < self.tdx.ref(close, 2)) &
                             (close > self.tdx.ref(close, 1)) &
                             (vol > self.tdx.ref(vol, 1))).astype(int)
        secondary_powerful_score = secondary_powerful * 10
        
        # 6. MACD金叉 (+10分)
        macd_gold_score = self.df['MACD金叉'].astype(int) * 10
        
        # 7. 均线金叉 (+5分)
        ma_gold_score = self.df['均线金叉'].astype(int) * 5
        
        # 总分
        total_score = base_score + zhongshu_score + bi_divergence_score + \
                     exhaustion_score + most_powerful_score + secondary_powerful_score + \
                     macd_gold_score + ma_gold_score
        
        # 限制在0-100
        total_score = total_score.clip(0, 100)
        
        self.df['买入评分'] = total_score
        self.df['中枢背离分'] = zhongshu_score
        self.df['笔背离分'] = bi_divergence_score
        self.df['衰竭分'] = exhaustion_score
        self.df['强分型分'] = most_powerful_score + secondary_powerful_score
        self.df['MACD分'] = macd_gold_score
        self.df['均线分'] = ma_gold_score
        
        return self.df
    
    def get_latest_score(self) -> Dict:
        """获取最新评分"""
        if '买入评分' not in self.df.columns:
            self.calculate_buy_score()
        
        latest = self.df.iloc[-1]
        
        return {
            'score': int(latest['买入评分']),
            'components': {
                '中枢背离': int(latest['中枢背离分']),
                '笔背离': int(latest['笔背离分']),
                '衰竭': int(latest['衰竭分']),
                '强分型': int(latest['强分型分']),
                'MACD': int(latest['MACD分']),
                '均线': int(latest['均线分'])
            },
            'signals': {
                '顶分型': bool(latest['顶分型']),
                '底分型': bool(latest['底分型']),
                'MACD金叉': bool(latest['MACD金叉']),
                '均线金叉': bool(latest['均线金叉'])
            },
            'price': latest['close'],
            'ma5': latest['MA5'],
            'ma20': latest['MA20'],
            'zhongshu_upper': latest['中枢上沿'],
            'zhongshu_lower': latest['中枢下沿']
        }


def analyze_stock_score(df: pd.DataFrame) -> Dict:
    """
    分析股票评分（便捷函数）
    
    Args:
        df: 包含open, high, low, close, volume的DataFrame
        
    Returns:
        评分结果字典
    """
    try:
        picker = TDXStockPicker(df)
        return picker.get_latest_score()
    except Exception as e:
        return {'error': str(e), 'score': 0}
