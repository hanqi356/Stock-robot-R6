"""
统一分析接口
对外提供单一函数调用，内部自动整合所有分析模块
"""

import pandas as pd
from typing import Dict, Optional
from signal_integrator import SignalIntegrator
from chan_divergence_strategy import ChanDivergenceStrategy


class UnifiedAnalyzer:
    """统一分析器"""
    
    def __init__(self, df: pd.DataFrame, chan_adapter=None):
        """
        初始化统一分析器
        
        Args:
            df: DataFrame，包含 OHLCV 数据
            chan_adapter: 缠论适配器（可选）
        """
        self.df = df
        self.chan_adapter = chan_adapter
        self.integrator = SignalIntegrator()
        self.chan_strategy = ChanDivergenceStrategy(df)
    
    def analyze(self, code: str = None) -> Dict:
        """
        执行完整分析流程
        
        Args:
            code: 股票代码（可选）
        
        Returns:
            完整的分析报告
        """
        # 1. 缠论背离分析
        chan_signal = self._analyze_chan_divergence(code)
        
        # 2. 因子分析（简化版，实际可接入 panda_factor_integration）
        factor_signal = self._analyze_factors()
        
        # 3. AI 分析占位（实际可接入 ai_analyzer）
        ai_signal = self._analyze_ai()
        
        # 4. 技术指标分析
        technical_signal = self._analyze_technicals()
        
        # 5. 整合所有信号
        all_signals = {
            'chan_divergence': chan_signal,
            'factor_analysis': factor_signal,
            'ai_analysis': ai_signal,
            'technical_indicators': technical_signal
        }
        
        integrated_result = self.integrator.integrate_signals(all_signals)
        
        # 6. 生成交易决策
        trading_decision = self.integrator.create_trading_decision(
            integrated_result,
            position_size=0.2,
            stop_loss=0.05,
            take_profit=0.10
        )
        
        return {
            'code': code,
            'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
            'integrated_signal': integrated_result,
            'trading_decision': trading_decision,
            'module_signals': all_signals
        }
    
    def _analyze_chan_divergence(self, code: str = None) -> Optional[Dict]:
        """执行缠论背离分析"""
        try:
            # 获取缠论分析结果
            chan_analysis = None
            if self.chan_adapter:
                try:
                    chan_df = self.df.copy()
                    chan_df['datetime'] = pd.to_datetime(chan_df['date'])
                    chan_df.set_index('datetime', inplace=True)
                    analysis = self.chan_adapter.analyze(code or 'UNKNOWN', chan_df)
                    if analysis and hasattr(analysis, 'bi_list'):
                        chan_analysis = {'bi_list': analysis.bi_list}
                except Exception as e:
                    print(f"缠论分析警告：{e}")
            
            # 生成缠论背离信号
            chan_signal = self.chan_strategy.generate_signal(chan_analysis)
            
            return {
                'signal': chan_signal['signal'],
                'confidence': chan_signal['confidence'],
                'reason': chan_signal['reason'],
                'chan_divergence': chan_signal['chan_divergence'],
                'chan_strength': chan_signal['chan_strength'],
                'macd_divergence': chan_signal['macd_divergence']
            }
        except Exception as e:
            print(f"缠论背离分析失败：{e}")
            return None
    
    def _analyze_factors(self) -> Optional[Dict]:
        """执行因子分析"""
        try:
            # TODO: 接入 PandaFactorIntegration
            # 这里使用简化版本
            
            # 计算简单的估值因子
            if len(self.df) >= 60:
                # 动量因子
                momentum = (self.df['close'].iloc[-1] - self.df['close'].iloc[-20]) / self.df['close'].iloc[-20]
                
                # 波动率因子
                returns = self.df['close'].pct_change()
                volatility = returns.std()
                
                # 综合评分（简化）
                score = 50 + (momentum * 100 - volatility * 50)
                score = max(0, min(100, score))  # 限制在 0-100
                
                return {
                    'score': int(score),
                    'comment': f"动量：{momentum:.2%}, 波动率：{volatility:.2%}"
                }
            else:
                return {'score': 50, 'comment': '数据不足'}
        except Exception as e:
            print(f"因子分析失败：{e}")
            return {'score': 50, 'comment': '分析失败'}
    
    def _analyze_ai(self) -> Optional[Dict]:
        """执行 AI 分析"""
        try:
            # TODO: 接入 BailianAIAnalyzer
            # 这里使用规则-based 简化版本
            
            # 基于价格和成交量的简单规则
            latest_close = self.df['close'].iloc[-1]
            avg_close_20 = self.df['close'].iloc[-20:].mean()
            latest_vol = self.df['volume'].iloc[-1]
            avg_vol_20 = self.df['volume'].iloc[-20:].mean()
            
            price_signal = 1 if latest_close > avg_close_20 else -1
            vol_signal = 1 if latest_vol > avg_vol_20 else -1
            
            # 综合判断
            if price_signal == 1 and vol_signal == 1:
                rec = "BUY"
                analysis = "价涨量增，趋势向好"
            elif price_signal == -1 and vol_signal == -1:
                rec = "SELL"
                analysis = "价跌量缩，趋势向空"
            else:
                rec = "HOLD"
                analysis = "震荡整理，方向不明"
            
            return {
                'recommendation': rec,
                'analysis': analysis
            }
        except Exception as e:
            print(f"AI 分析失败：{e}")
            return {'recommendation': 'HOLD', 'analysis': '分析失败'}
    
    def _analyze_technicals(self) -> Optional[Dict]:
        """执行技术指标分析"""
        try:
            # 计算多个技术指标
            close = self.df['close'].values
            
            # MACD
            dif, dea, macd_hist = self.chan_strategy.dif[-1], self.chan_strategy.dea[-1], self.chan_strategy.macd[-1]
            
            # RSI（简化）
            delta = pd.Series(close).diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean().iloc[-1]
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean().iloc[-1]
            rs = gain / loss if loss != 0 else 0
            rsi = 100 - (100 / (1 + rs))
            
            # 综合评分
            macd_score = 1 if dif > dea else -1
            rsi_score = 1 if rsi > 50 else -1
            
            total_score = (macd_score + rsi_score) / 2 * 50 + 50
            
            return {
                'score': int(total_score),
                'indicators': f"MACD={'金叉' if dif > dea else '死叉'}, RSI={rsi:.1f}"
            }
        except Exception as e:
            print(f"技术分析失败：{e}")
            return {'score': 50, 'indicators': '分析失败'}


def analyze_stock(code: str, df: pd.DataFrame, chan_adapter=None) -> Dict:
    """
    便捷函数：一键分析股票
    
    Args:
        code: 股票代码
        df: DataFrame，包含 OHLCV 数据
        chan_adapter: 缠论适配器（可选）
    
    Returns:
        完整分析报告
    """
    analyzer = UnifiedAnalyzer(df, chan_adapter)
    return analyzer.analyze(code)


# 使用示例
if __name__ == '__main__':
    print("="*70)
    print("统一分析接口测试")
    print("="*70)
    
    # 生成测试数据
    import numpy as np
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    close = np.cumsum(np.random.randn(100)) + 100
    
    df = pd.DataFrame({
        'open': close * 0.99,
        'high': close * 1.02,
        'low': close * 0.98,
        'close': close,
        'volume': np.random.randint(1000, 10000, 100)
    }, index=dates)
    
    # 执行分析
    result = analyze_stock('TEST_STOCK', df)
    
    print("\n【分析报告】")
    print(f"股票代码：{result['code']}")
    print(f"分析时间：{result['timestamp']}")
    
    print("\n【最终信号】")
    print(f"信号：{result['integrated_signal']['final_signal']}")
    print(f"动作：{result['integrated_signal']['action']} (-1 卖出/0 持有/1 买入)")
    print(f"置信度：{result['integrated_signal']['confidence']}%")
    
    print("\n【交易决策】")
    td = result['trading_decision']
    print(f"是否交易：{'是' if td['should_trade'] else '否'}")
    print(f"方向：{td['direction']}")
    print(f"建议仓位：{td['position']*100:.1f}%")
    print(f"止损：{td['stop_loss']*100:.1f}%")
    print(f"止盈：{td['take_profit']*100:.1f}%")
    print(f"风险等级：{td['risk_level']}")
    
    print("\n【各模块信号】")
    for module_name, signal in result['module_signals'].items():
        if signal:
            print(f"  {module_name}: {signal.get('signal', signal.get('recommendation', 'N/A'))}")
    
    print("\n" + "="*70)
