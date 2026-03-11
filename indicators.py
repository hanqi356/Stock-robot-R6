"""
通达信指标实现 - 使用MyTT库 + czsc缠论引擎
包含：趋势线、MACD、多空均线、资金流向
缠论核心（分型/笔/中枢/买卖点）已升级为 czsc 真实算法
"""

import numpy as np
import pandas as pd
from MyTT import *

# 尝试导入缠论引擎
try:
    from chanlun_engine import ChanlunEngine
    CHANLUN_ENGINE_AVAILABLE = True
except ImportError:
    CHANLUN_ENGINE_AVAILABLE = False


class ChanlunIndicators:
    """缠论指标系统"""
    
    def __init__(self, df: pd.DataFrame, symbol: str = 'unknown'):
        """
        初始化指标系统
        df: DataFrame with columns [open, high, low, close, vol]
        symbol: 股票代码（用于缠论引擎）
        """
        self.df = df.copy()
        self.symbol = symbol
        self.OPEN = df['open'].values
        self.HIGH = df['high'].values
        self.LOW = df['low'].values
        self.CLOSE = df['close'].values
        self.VOL = df['vol'].values
        self.chan_engine = None  # czsc 缠论引擎实例
        
    def calculate_all(self):
        """计算所有指标"""
        self.trend_lines()
        self.macd_indicator()
        self.ma_system()
        self.fund_flow()
        self.buy_sell_signals()

        # 缠论核心：使用 czsc 真实算法（分型/笔/中枢/买卖点）
        self._run_chanlun_engine()

        # 基于缠论结果的评分系统
        self.scoring_system()
        return self.df
    
    def trend_lines(self):
        """趋势线 - CC1, CC2"""
        HH20 = HHV(self.HIGH, 20)
        LL20 = LLV(self.LOW, 20)
        self.df['HH20'] = HH20
        self.df['LL20'] = LL20
        
    def macd_indicator(self):
        """MACD指标"""
        DIF, DEA, MACD_LINE = MACD(self.CLOSE, SHORT=6, LONG=13, M=5)
        
        self.df['DIF'] = DIF
        self.df['DEA'] = DEA
        self.df['MACD'] = MACD_LINE
        
        self.df['MACD金叉'] = CROSS(DIF, DEA)
        self.df['MACD死叉'] = CROSS(DEA, DIF)
        
    def ma_system(self):
        """多空均线系统"""
        self.df['MA5'] = MA(self.CLOSE, 5)
        self.df['MA20'] = MA(self.CLOSE, 20)
        self.df['TTD1'] = EMA(self.CLOSE, 3)
        self.df['TTD2'] = EMA(self.CLOSE, 13)
        
    def fund_flow(self):
        """资金流向计算"""
        VAR1 = self.VOL / ((self.HIGH - self.LOW) * 2 - ABS(self.CLOSE - self.OPEN))
        
        买入 = IF(self.CLOSE > self.OPEN, 
                 VAR1 * (self.HIGH - self.LOW),
                 IF(self.CLOSE < self.OPEN,
                    VAR1 * ((self.HIGH - self.OPEN) + (self.CLOSE - self.LOW)),
                    self.VOL / 2))
        
        卖出 = IF(self.CLOSE > self.OPEN,
                 0 - VAR1 * ((self.HIGH - self.CLOSE) + (self.OPEN - self.LOW)),
                 IF(self.CLOSE < self.OPEN,
                    0 - VAR1 * (self.HIGH - self.LOW),
                    0 - self.VOL / 2))
        
        self.df['流入资金'] = MA(买入, 4)
        self.df['流出资金'] = MA(np.abs(卖出), 4)

    def _run_chanlun_engine(self):
        """使用 czsc 缠论引擎计算真实的分型/笔/中枢/买卖点"""
        if not CHANLUN_ENGINE_AVAILABLE:
            # 降级：使用简化版
            self._fallback_bi_structure()
            self._fallback_zhongshu()
            return

        try:
            self.chan_engine = ChanlunEngine(self.df, symbol=self.symbol)
            enriched = self.chan_engine.enrich_dataframe()

            # 将缠论结果合并到 df
            chan_cols = [c for c in enriched.columns if c.startswith('chan_')]
            for col in chan_cols:
                self.df[col] = enriched[col].values

            # 兼容旧接口：映射到原有列名
            self.df['局部高点'] = (self.df['chan_fx_mark'] == '顶分型')
            self.df['局部低点'] = (self.df['chan_fx_mark'] == '底分型')
            self.df['中枢高点'] = self.df['chan_zs_zg']
            self.df['中枢低点'] = self.df['chan_zs_zd']
            self.df['三买'] = (self.df['chan_buy_signal'] == '三买')
            self.df['三卖'] = (self.df['chan_sell_signal'] == '三卖')

            # 背驰信号（从缠论引擎的买卖点推导）
            self.df['上升背驰'] = self.df['chan_sell_signal'].isin(['一卖'])
            self.df['下降背驰'] = self.df['chan_buy_signal'].isin(['一买'])

        except Exception as e:
            print(f"缠论引擎异常，降级到简化版: {e}")
            self._fallback_bi_structure()
            self._fallback_zhongshu()

    def _fallback_bi_structure(self):
        """降级：简化版笔结构识别（当 czsc 不可用时）"""
        KU1 = IF(self.HIGH == HHV(self.HIGH, 3), 1, 0)
        KD1 = IF(self.LOW == LLV(self.LOW, 3), 1, 0)

        局部高点预选 = (REF(KU1, 2) == 1) & (REF(KU1, 1) == 0) & (KU1 == 0)
        局部低点预选 = (REF(KD1, 2) == 1) & (REF(KD1, 1) == 0) & (KD1 == 0)

        self.df['局部高点'] = 局部高点预选.astype(bool)
        self.df['局部低点'] = 局部低点预选.astype(bool)

        # 初始化缠论列为默认值
        self.df['chan_fx_mark'] = None
        self.df['chan_bi_dir'] = None
        self.df['chan_bi_high'] = np.nan
        self.df['chan_bi_low'] = np.nan
        self.df['chan_in_zs'] = False
        self.df['chan_zs_zg'] = np.nan
        self.df['chan_zs_zd'] = np.nan
        self.df['chan_buy_signal'] = None
        self.df['chan_sell_signal'] = None
        self.df['chan_score'] = 50
        self.df['chan_trend'] = '未知'
        self.df['上升背驰'] = False
        self.df['下降背驰'] = False

    def _fallback_zhongshu(self):
        """降级：简化版中枢识别"""
        self.df['中枢高点'] = REF(HHV(self.HIGH, 10), 5)
        self.df['中枢低点'] = REF(LLV(self.LOW, 10), 5)

        self.df['三买'] = self.CLOSE > self.df['中枢高点'].values
        self.df['三卖'] = self.CLOSE < self.df['中枢低点'].values

    def buy_sell_signals(self):
        """买卖点辅助信号（RSI等）"""
        LC = REF(self.CLOSE, 1)
        RSI1 = SMA(MAX(self.CLOSE - LC, 0), 6, 1) / SMA(ABS(self.CLOSE - LC), 6, 1) * 100
        self.df['RSI1'] = RSI1
        
    def scoring_system(self):
        """买卖点评分系统 - 融合缠论引擎评分与通达信指标"""
        n = len(self.df)

        # 如果缠论引擎可用，以其评分为基础
        if self.chan_engine is not None:
            chan_score = self.df['chan_score'].values
            if isinstance(chan_score[0], (int, float, np.integer, np.floating)):
                base_score = chan_score.astype(float)
            else:
                base_score = np.full(n, 50.0)
        else:
            base_score = np.full(n, 30.0)

        # 叠加通达信指标加减分
        # 1. MACD金叉 +10
        macd_gold = self.df.get('MACD金叉', np.zeros(n))
        if hasattr(macd_gold, 'values'):
            macd_gold = macd_gold.values
        base_score = base_score + IF(macd_gold == 1, 10, 0)

        # 2. MACD死叉 -10
        macd_dead = self.df.get('MACD死叉', np.zeros(n))
        if hasattr(macd_dead, 'values'):
            macd_dead = macd_dead.values
        base_score = base_score + IF(macd_dead == 1, -10, 0)

        # 3. 量价配合 +5
        vol_up = (self.CLOSE > REF(self.CLOSE, 1)) & (self.VOL > REF(self.VOL, 1))
        base_score = base_score + IF(vol_up, 5, 0)

        # 4. RSI超卖 +5
        rsi = self.df.get('RSI1')
        if rsi is not None:
            rsi_vals = rsi.values if hasattr(rsi, 'values') else rsi
            base_score = base_score + IF(rsi_vals < 30, 5, 0)
            base_score = base_score + IF(rsi_vals > 80, -5, 0)

        # 限制范围
        总得分 = np.clip(base_score, 0, 100)

        self.df['买点得分'] = 总得分
        self.df['卖点得分'] = 100 - 总得分

        # 买点等级
        self.df['买点等级'] = np.where(总得分 >= 80, 1,
                              np.where(总得分 >= 60, 2,
                              np.where(总得分 >= 40, 3,
                              np.where(总得分 >= 20, 4, 5))))


def calculate_indicators(df: pd.DataFrame, symbol: str = 'unknown') -> pd.DataFrame:
    """
    便捷函数：计算所有指标（含缠论）
    
    Example:
        df = get_stock_data('600519', 'day', 100)
        df = calculate_indicators(df, symbol='600519')
    """
    required_cols = ['open', 'high', 'low', 'close', 'vol']
    for col in required_cols:
        if col not in df.columns:
            if col == 'vol' and 'volume' in df.columns:
                df['vol'] = df['volume']
            else:
                df[col] = df['close'] if col != 'vol' else 0
    
    ind = ChanlunIndicators(df, symbol=symbol)
    return ind.calculate_all()


if __name__ == '__main__':
    from stock_data import get_stock_data
    
    print("获取测试数据...")
    df = get_stock_data('600519', 'day', 200)
    
    if not df.empty:
        print("计算指标（含缠论引擎）...")
        df = calculate_indicators(df, symbol='600519')
        
        print("\n基础指标:")
        print(df[['datetime', 'close', 'DIF', 'DEA', 'MACD', 'MA5', 'MA20']].tail(5))
        
        print("\n缠论指标:")
        chan_cols = ['chan_fx_mark', 'chan_bi_dir', 'chan_in_zs', 'chan_buy_signal', 'chan_sell_signal', 'chan_score', 'chan_trend']
        available_cols = [c for c in chan_cols if c in df.columns]
        if available_cols:
            print(df[['datetime', 'close'] + available_cols].tail(10))
        
        print("\n综合评分:")
        print(df[['datetime', 'close', '买点得分', '卖点得分', '买点等级']].tail(10))
    else:
        print("获取数据失败")
