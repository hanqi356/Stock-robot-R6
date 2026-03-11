# -*- coding: utf-8 -*-
"""
PandaFactor 风格量化因子库 - 简化版
提供常用因子计算和阿里云百炼大模型分析
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Callable
import threading
import tkinter as tk
from tkinter import messagebox, Toplevel, Text, Scrollbar, ttk


class FactorCalculator:
    """因子计算器 - 参考PandaFactor风格"""
    
    @staticmethod
    def delay(series: pd.Series, periods: int = 1) -> pd.Series:
        """延迟N期"""
        return series.shift(periods)
    
    @staticmethod
    def rank(series: pd.Series) -> pd.Series:
        """排名标准化"""
        return series.rank(pct=True)
    
    @staticmethod
    def stddev(series: pd.Series, window: int = 20) -> pd.Series:
        """N期标准差"""
        return series.rolling(window=window).std()
    
    @staticmethod
    def sum(series: pd.Series, window: int = 20) -> pd.Series:
        """N期求和"""
        return series.rolling(window=window).sum()
    
    @staticmethod
    def mean(series: pd.Series, window: int = 20) -> pd.Series:
        """N期均值"""
        return series.rolling(window=window).mean()
    
    @staticmethod
    def correlation(x: pd.Series, y: pd.Series, window: int = 20) -> pd.Series:
        """N期相关系数"""
        return x.rolling(window=window).corr(y)
    
    @staticmethod
    def scale(series: pd.Series) -> pd.Series:
        """标准化到[-1,1]"""
        return 2 * (series - series.min()) / (series.max() - series.min()) - 1
    
    @staticmethod
    def if_else(condition: pd.Series, true_val, false_val) -> pd.Series:
        """条件判断"""
        return pd.Series(np.where(condition, true_val, false_val), index=condition.index)
    
    @staticmethod
    def returns(close: pd.Series, periods: int = 1) -> pd.Series:
        """收益率"""
        return close.pct_change(periods)
    
    @staticmethod
    def log_returns(close: pd.Series, periods: int = 1) -> pd.Series:
        """对数收益率"""
        return np.log(close / FactorCalculator.delay(close, periods))
    
    @staticmethod
    def volatility(close: pd.Series, window: int = 20) -> pd.Series:
        """波动率"""
        returns = FactorCalculator.returns(close)
        return FactorCalculator.stddev(returns, window)
    
    @staticmethod
    def momentum(close: pd.Series, window: int = 20) -> pd.Series:
        """动量因子"""
        return close / FactorCalculator.delay(close, window) - 1
    
    @staticmethod
    def rsi(close: pd.Series, window: int = 14) -> pd.Series:
        """RSI指标"""
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """MACD指标"""
        ema_fast = close.ewm(span=fast).mean()
        ema_slow = close.ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        return pd.DataFrame({
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        })
    
    @staticmethod
    def bollinger_bands(close: pd.Series, window: int = 20, num_std: int = 2) -> pd.DataFrame:
        """布林带"""
        middle = FactorCalculator.mean(close, window)
        std = FactorCalculator.stddev(close, window)
        upper = middle + num_std * std
        lower = middle - num_std * std
        return pd.DataFrame({
            'upper': upper,
            'middle': middle,
            'lower': lower
        })
    
    @staticmethod
    def ema(series: pd.Series, span: int = 20) -> pd.Series:
        """指数移动平均"""
        return series.ewm(span=span, adjust=False).mean()
    
    @staticmethod
    def sma(series: pd.Series, window: int = 20) -> pd.Series:
        """简单移动平均"""
        return series.rolling(window=window).mean()
    
    @staticmethod
    def wma(series: pd.Series, window: int = 20) -> pd.Series:
        """加权移动平均"""
        weights = np.arange(1, window + 1)
        return series.rolling(window=window).apply(
            lambda x: np.dot(x, weights) / weights.sum(), raw=True
        )
    
    @staticmethod
    def kdj(high: pd.Series, low: pd.Series, close: pd.Series, 
            n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
        """KDJ指标"""
        rsv = (close - low.rolling(window=n).min()) / (
            high.rolling(window=n).max() - low.rolling(window=n).min()
        ) * 100
        k = rsv.ewm(alpha=1/m1, adjust=False).mean()
        d = k.ewm(alpha=1/m2, adjust=False).mean()
        j = 3 * k - 2 * d
        return pd.DataFrame({'k': k, 'd': d, 'j': j})
    
    @staticmethod
    def cci(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
        """CCI指标"""
        tp = (high + low + close) / 3
        ma = tp.rolling(window=window).mean()
        md = tp.rolling(window=window).apply(lambda x: np.abs(x - x.mean()).mean())
        return (tp - ma) / (0.015 * md)
    
    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
        """ATR平均真实波幅"""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=window).mean()
    
    @staticmethod
    def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """OBV能量潮"""
        return (np.sign(close.diff()) * volume).cumsum()
    
    @staticmethod
    def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
        """威廉指标"""
        highest_high = high.rolling(window=window).max()
        lowest_low = low.rolling(window=window).min()
        return (highest_high - close) / (highest_high - lowest_low) * -100
    
    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
        """ADX趋向指标"""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        atr = tr.rolling(window=window).mean()
        plus_di = 100 * plus_dm.rolling(window=window).mean() / atr
        minus_di = 100 * minus_dm.rolling(window=window).mean() / atr
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        return dx.rolling(window=window).mean()
    
    @staticmethod
    def sharpe_ratio(returns: pd.Series, window: int = 20, risk_free_rate: float = 0.02) -> pd.Series:
        """夏普比率"""
        excess_returns = returns - risk_free_rate / 252
        return excess_returns.rolling(window=window).mean() / returns.rolling(window=window).std()
    
    @staticmethod
    def max_drawdown(close: pd.Series, window: int = 60) -> pd.Series:
        """最大回撤"""
        rolling_max = close.rolling(window=window, min_periods=1).max()
        return (close - rolling_max) / rolling_max
    
    @staticmethod
    def beta(returns: pd.Series, market_returns: pd.Series, window: int = 60) -> pd.Series:
        """Beta系数"""
        covariance = returns.rolling(window=window).cov(market_returns)
        market_variance = market_returns.rolling(window=window).var()
        return covariance / market_variance
    
    @staticmethod
    def alpha(returns: pd.Series, market_returns: pd.Series, window: int = 60, risk_free_rate: float = 0.02) -> pd.Series:
        """Alpha超额收益"""
        beta = FactorCalculator.beta(returns, market_returns, window)
        return returns - (risk_free_rate / 252 + beta * (market_returns - risk_free_rate / 252))
    
    @staticmethod
    def ts_argmax(series: pd.Series, window: int = 20) -> pd.Series:
        """N周期内最大值位置"""
        return series.rolling(window=window).apply(lambda x: x.argmax(), raw=True)
    
    @staticmethod
    def ts_argmin(series: pd.Series, window: int = 20) -> pd.Series:
        """N周期内最小值位置"""
        return series.rolling(window=window).apply(lambda x: x.argmin(), raw=True)
    
    @staticmethod
    def ts_rank(series: pd.Series, window: int = 20) -> pd.Series:
        """N周期内排名"""
        return series.rolling(window=window).rank(pct=True)
    
    @staticmethod
    def decay_linear(series: pd.Series, window: int = 20) -> pd.Series:
        """线性衰减加权平均"""
        weights = np.arange(window, 0, -1)
        return series.rolling(window=window).apply(
            lambda x: np.dot(x, weights) / weights.sum(), raw=True
        )
    
    @staticmethod
    def correlation_rank(x: pd.Series, y: pd.Series, window: int = 20) -> pd.Series:
        """秩相关系数"""
        return x.rolling(window=window).corr(y).rank(pct=True)
    
    @staticmethod
    def covariance(x: pd.Series, y: pd.Series, window: int = 20) -> pd.Series:
        """协方差"""
        return x.rolling(window=window).cov(y)


class PandaFactorIntegration:
    """PandaFactor 整合类"""
    
    def __init__(self, parent_window=None, colors=None):
        self.parent = parent_window
        self.colors = colors or {
            'bg': '#0d1117',
            'bg_secondary': '#161b22',
            'text': '#c9d1d9',
            'text_highlight': '#ffffff',
            'accent': '#58a6ff',
            'up': '#f85149',
            'down': '#3fb950'
        }
        self.calculator = FactorCalculator()
        
    def calculate_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算常用因子"""
        if df.empty or 'close' not in df.columns:
            return pd.DataFrame()
        
        factors = pd.DataFrame(index=df.index)
        close = df['close']
        
        # 基础价格因子
        factors['returns_1d'] = self.calculator.returns(close, 1)
        factors['returns_5d'] = self.calculator.returns(close, 5)
        factors['returns_20d'] = self.calculator.returns(close, 20)
        
        # 动量因子
        factors['momentum_5d'] = self.calculator.momentum(close, 5)
        factors['momentum_20d'] = self.calculator.momentum(close, 20)
        
        # 波动率因子
        factors['volatility_20d'] = self.calculator.volatility(close, 20)
        
        # RSI
        factors['rsi_14'] = self.calculator.rsi(close, 14)
        
        # MACD
        macd_df = self.calculator.macd(close)
        factors['macd'] = macd_df['macd']
        factors['macd_signal'] = macd_df['signal']
        factors['macd_hist'] = macd_df['histogram']
        
        # 布林带
        bb_df = self.calculator.bollinger_bands(close)
        factors['bb_upper'] = bb_df['upper']
        factors['bb_lower'] = bb_df['lower']
        factors['bb_position'] = (close - bb_df['lower']) / (bb_df['upper'] - bb_df['lower'])
        
        # 移动平均线因子
        factors['ma5'] = self.calculator.sma(close, 5)
        factors['ma10'] = self.calculator.sma(close, 10)
        factors['ma20'] = self.calculator.sma(close, 20)
        factors['ma60'] = self.calculator.sma(close, 60)
        factors['ema12'] = self.calculator.ema(close, 12)
        factors['ema26'] = self.calculator.ema(close, 26)
        
        # 价格位置因子
        factors['price_position'] = (close - close.rolling(20).min()) / (close.rolling(20).max() - close.rolling(20).min())
        
        # 需要高低开数据的因子
        if all(col in df.columns for col in ['high', 'low', 'open']):
            high, low, open_price = df['high'], df['low'], df['open']
            
            # KDJ
            kdj_df = self.calculator.kdj(high, low, close)
            factors['kdj_k'] = kdj_df['k']
            factors['kdj_d'] = kdj_df['d']
            factors['kdj_j'] = kdj_df['j']
            
            # CCI
            factors['cci_14'] = self.calculator.cci(high, low, close, 14)
            
            # ATR
            factors['atr_14'] = self.calculator.atr(high, low, close, 14)
            
            # 威廉指标
            factors['williams_r'] = self.calculator.williams_r(high, low, close, 14)
            
            # ADX
            factors['adx_14'] = self.calculator.adx(high, low, close, 14)
            
            # 价格振幅
            factors['amplitude'] = (high - low) / open_price
            
            # 实体因子
            factors['body_ratio'] = abs(close - open_price) / (high - low + 0.001)
        
        # 成交量因子
        if 'volume' in df.columns:
            volume = df['volume']
            factors['volume_ma5'] = self.calculator.mean(volume, 5)
            factors['volume_ma20'] = self.calculator.mean(volume, 20)
            factors['volume_ratio'] = volume / factors['volume_ma20']
            
            # OBV
            factors['obv'] = self.calculator.obv(close, volume)
            
            # 量价相关性
            factors['price_volume_corr'] = self.calculator.correlation(close, volume, 20)
        
        # 风险因子
        factors['max_drawdown_20d'] = self.calculator.max_drawdown(close, 20)
        factors['sharpe_20d'] = self.calculator.sharpe_ratio(factors['returns_1d'], 20)
        
        # 时间序列因子
        factors['ts_rank_20d'] = self.calculator.ts_rank(close, 20)
        factors['ts_argmax_20d'] = self.calculator.ts_argmax(close, 20)
        factors['ts_argmin_20d'] = self.calculator.ts_argmin(close, 20)
        
        return factors
    
    def analyze_with_llm(self, stock_code: str, factors_df: pd.DataFrame, 
                        api_key: str, model_name: str = "qwen-max", callback: Callable = None):
        """使用大模型分析因子
        
        Args:
            stock_code: 股票代码
            factors_df: 因子 DataFrame
            api_key: API 密钥
            model_name: 模型名称，默认 qwen-max
            callback: 回调函数
        """
        def run_analysis():
            try:
                # 准备因子摘要
                latest = factors_df.iloc[-1] if not factors_df.empty else {}
                summary = {
                    '股票代码': stock_code,
                    '最新日期': str(factors_df.index[-1]) if not factors_df.empty else 'N/A',
                    '1 日收益率': f"{latest.get('returns_1d', 0):.2%}" if 'returns_1d' in latest else 'N/A',
                    '5 日收益率': f"{latest.get('returns_5d', 0):.2%}" if 'returns_5d' in latest else 'N/A',
                    '20 日收益率': f"{latest.get('returns_20d', 0):.2%}" if 'returns_20d' in latest else 'N/A',
                    'RSI(14)': f"{latest.get('rsi_14', 0):.2f}" if 'rsi_14' in latest else 'N/A',
                    'MACD': f"{latest.get('macd', 0):.4f}" if 'macd' in latest else 'N/A',
                    '布林带位置': f"{latest.get('bb_position', 0):.2%}" if 'bb_position' in latest else 'N/A',
                    '20 日波动率': f"{latest.get('volatility_20d', 0):.2%}" if 'volatility_20d' in latest else 'N/A',
                    'KDJ-K': f"{latest.get('kdj_k', 0):.2f}" if 'kdj_k' in latest else 'N/A',
                    'KDJ-D': f"{latest.get('kdj_d', 0):.2f}" if 'kdj_d' in latest else 'N/A',
                    'CCI(14)': f"{latest.get('cci_14', 0):.2f}" if 'cci_14' in latest else 'N/A',
                    'ATR(14)': f"{latest.get('atr_14', 0):.2f}" if 'atr_14' in latest else 'N/A',
                    '威廉指标': f"{latest.get('williams_r', 0):.2f}" if 'williams_r' in latest else 'N/A',
                    'ADX(14)': f"{latest.get('adx_14', 0):.2f}" if 'adx_14' in latest else 'N/A',
                    '成交量比': f"{latest.get('volume_ratio', 0):.2f}" if 'volume_ratio' in latest else 'N/A',
                    '20 日最大回撤': f"{latest.get('max_drawdown_20d', 0):.2%}" if 'max_drawdown_20d' in latest else 'N/A',
                    '20 日夏普': f"{latest.get('sharpe_20d', 0):.2f}" if 'sharpe_20d' in latest else 'N/A',
                }
                
                # 构建提示词
                prompt = f"""请作为量化分析师，基于以下因子数据给出投资建议：

{chr(10).join([f"{k}: {v}" for k, v in summary.items()])}

请分析：
1. 当前技术形态（趋势、超买超卖）
2. 风险水平
3. 操作建议（买入/卖出/观望）
4. 理由
"""
                
                # 调用阿里云百炼
                from openai import OpenAI
                
                client = OpenAI(
                    api_key=api_key,
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
                )
                
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "你是专业的量化投资分析师，擅长技术分析和因子投资。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=2000
                )
                
                analysis = response.choices[0].message.content
                
                # 构建结果
                class FactorAnalysisResult:
                    def __init__(self, code, summary, analysis):
                        self.stock_code = code
                        self.stock_name = code
                        self.summary = summary
                        self.analysis = analysis
                        self.action = self._extract_action(analysis)
                    
                    def _extract_action(self, text):
                        if '买入' in text or '建议买入' in text:
                            return '买入'
                        elif '卖出' in text or '建议卖出' in text:
                            return '卖出'
                        else:
                            return '观望'
                
                result = FactorAnalysisResult(stock_code, summary, analysis)
                
                if callback:
                    self.parent.after(0, lambda: callback(result))
                    
            except Exception as e:
                error_msg = f"因子分析失败: {str(e)}"
                if callback:
                    self.parent.after(0, lambda: callback(None, error_msg))
        
        thread = threading.Thread(target=run_analysis, daemon=True)
        thread.start()
    
    def show_factor_result(self, result, title="因子分析结果"):
        """显示因子分析结果"""
        if result is None:
            messagebox.showerror("错误", "分析结果为空")
            return
        
        window = Toplevel(self.parent)
        window.title(title)
        window.geometry("800x600")
        window.configure(bg=self.colors['bg'])
        
        # 标题
        header_frame = tk.Frame(window, bg=self.colors['bg_secondary'], height=60)
        header_frame.pack(fill='x', padx=10, pady=10)
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text=f"{result.stock_code} 因子分析", 
                font=('微软雅黑', 18, 'bold'),
                bg=self.colors['bg_secondary'], 
                fg=self.colors['text_highlight']).pack(side='left', padx=15, pady=10)
        
        # 操作建议
        action_color = self.colors['down'] if result.action == '卖出' else \
                      self.colors['up'] if result.action == '买入' else \
                      self.colors['accent']
        
        tk.Label(header_frame, text=result.action, 
                font=('微软雅黑', 14, 'bold'),
                bg=self.colors['bg_secondary'], 
                fg=action_color).pack(side='right', padx=15, pady=10)
        
        # 因子摘要
        summary_frame = tk.LabelFrame(window, text=" 因子摘要 ", 
                                     font=('微软雅黑', 11),
                                     bg=self.colors['bg'], 
                                     fg=self.colors['text'])
        summary_frame.pack(fill='x', padx=10, pady=5)
        
        summary_text = tk.Text(summary_frame, height=6, font=('微软雅黑', 10),
                              bg=self.colors['bg_secondary'], 
                              fg=self.colors['text'],
                              relief='flat')
        summary_text.pack(fill='x', padx=5, pady=5)
        
        for k, v in result.summary.items():
            summary_text.insert('end', f"{k}: {v}\n")
        summary_text.config(state='disabled')
        
        # AI分析结果
        analysis_frame = tk.Frame(window, bg=self.colors['bg'])
        analysis_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        tk.Label(analysis_frame, text="AI分析", font=('微软雅黑', 11, 'bold'),
                bg=self.colors['bg'], fg=self.colors['text']).pack(anchor='w')
        
        text_widget = Text(analysis_frame, 
                          font=('微软雅黑', 10),
                          bg=self.colors['bg_secondary'],
                          fg=self.colors['text'],
                          relief='flat',
                          wrap='word')
        text_widget.pack(side='left', fill='both', expand=True)
        
        scrollbar = Scrollbar(analysis_frame, command=text_widget.yview)
        scrollbar.pack(side='right', fill='y')
        text_widget.config(yscrollcommand=scrollbar.set)
        
        text_widget.insert('1.0', result.analysis)
        text_widget.config(state='disabled')
        
        # 关闭按钮
        tk.Button(window, text="关闭", command=window.destroy,
                 bg=self.colors['accent'], fg='white',
                 font=('微软雅黑', 11),
                 relief='flat', cursor='hand2',
                 width=10).pack(pady=10)
