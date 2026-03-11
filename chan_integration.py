# -*- coding: utf-8 -*-
"""
Chan.py-main 综合集成模块
将chan.py-main的所有功能整合到量化交易系统R6

集成内容：
1. K线图缠论叠加显示
2. 监控列表缠论选股
3. 自动交易缠论信号
4. 策略因子缠论分析
5. 深度分析缠论结论
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime

# 导入所有chan.py相关模块
from chan_adapter import (
    ChanAdapter, ChanSignal, ChanAnalysis, 
    get_chan_adapter, analyze_stock_chan, get_chan_signal
)
from chan_plot_overlay import (
    ChanPlotOverlay, plot_kline_with_chan, PlotConfig
)
from chan_stock_picker import (
    ChanStockPicker, ChanPickResult, ChanMonitor,
    quick_chan_pick, scan_chan_signals
)
from chan_auto_trader import (
    ChanAutoTrader, ChanStrategy, TradeDecision, TradeAction,
    get_chan_trader, analyze_trade_opportunity
)
from chan_factor_analysis import (
    ChanFactorExtractor, ChanFactorAnalyzer, ChanFactorStrategy,
    extract_chan_factors, analyze_chan_factors, generate_chan_report
)


class ChanIntegration:
    """
    Chan.py-main 综合集成类
    提供统一的接口访问所有chan.py功能
    """
    
    def __init__(self, config: Dict = None):
        """
        初始化集成模块
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.adapter = get_chan_adapter(self.config.get('chan_config'))
        self.picker = ChanStockPicker(
            min_score=self.config.get('min_score', 60),
            max_workers=self.config.get('max_workers', 5)
        )
        self.trader = ChanAutoTrader(
            initial_capital=self.config.get('initial_capital', 100000),
            position_size=self.config.get('position_size', 0.2),
            min_confidence=self.config.get('min_confidence', 70)
        )
        self.factor_analyzer = ChanFactorAnalyzer()
        self.plot_overlay = ChanPlotOverlay()
        
        # 状态缓存
        self.last_analysis: Dict[str, ChanAnalysis] = {}
        self.last_signals: Dict[str, ChanSignal] = {}
        
    # ==================== 1. K线图叠加显示 ====================
    
    def plot_kline_with_chan(self, df: pd.DataFrame, symbol: str,
                            ax=None, figsize=(14, 8)) -> Any:
        """
        绘制带缠论叠加的K线图
        
        Args:
            df: K线数据
            symbol: 股票代码
            ax: matplotlib axes对象（可选）
            figsize: 图大小
            
        Returns:
            matplotlib Figure或axes
        """
        # 获取缠论分析
        analysis = self.get_analysis(symbol, df)
        
        if ax is not None:
            # 在指定axes上绘制
            self.plot_overlay.plot_on_ax(ax, df, analysis)
            return ax
        else:
            # 创建新图
            return plot_kline_with_chan(df, symbol, analysis, figsize)
    
    # ==================== 2. 监控列表选股 ====================
    
    def scan_watchlist(self, watchlist: List[str],
                      data_fetcher: Callable) -> Dict:
        """
        扫描监控列表，返回缠论选股结果
        
        Args:
            watchlist: 监控股票列表
            data_fetcher: 数据获取函数
            
        Returns:
            选股结果字典
        """
        return self.picker.get_watchlist_recommendations(watchlist, data_fetcher)
    
    def get_chan_signals(self, symbols: List[str],
                        data_fetcher: Callable) -> List[ChanPickResult]:
        """
        获取股票的缠论信号
        
        Args:
            symbols: 股票代码列表
            data_fetcher: 数据获取函数
            
        Returns:
            信号列表
        """
        return self.picker.pick_batch(symbols, data_fetcher)
    
    # ==================== 3. 自动交易信号 ====================
    
    def analyze_for_trade(self, symbol: str, df: pd.DataFrame,
                         position: Dict = None) -> Optional[TradeDecision]:
        """
        分析股票并生成交易决策
        
        Args:
            symbol: 股票代码
            df: K线数据
            position: 当前持仓（如果有）
            
        Returns:
            交易决策
        """
        return self.trader.analyze_for_trade(symbol, df, position)
    
    def execute_auto_scan(self, symbols: List[str],
                         data_fetcher: Callable) -> List[TradeDecision]:
        """
        执行自动扫描，生成交易决策列表
        
        Args:
            symbols: 股票代码列表
            data_fetcher: 数据获取函数
            
        Returns:
            交易决策列表
        """
        return self.trader.execute_scan(symbols, data_fetcher)
    
    # ==================== 4. 策略因子分析 ====================
    
    def extract_factors(self, symbol: str, df: pd.DataFrame) -> Optional[Dict]:
        """
        提取缠论因子
        
        Args:
            symbol: 股票代码
            df: K线数据
            
        Returns:
            因子字典
        """
        factor = self.factor_analyzer.extractor.extract_factors(symbol, df)
        if factor:
            return {
                'symbol': factor.symbol,
                'bi_count': factor.bi_count,
                'seg_count': factor.seg_count,
                'zs_count': factor.zs_count,
                'trend': factor.trend,
                'trend_strength': factor.trend_strength,
                'has_buy_point': factor.has_buy_point,
                'has_sell_point': factor.has_sell_point,
                'price_to_zs': factor.price_to_zs,
                'divergence': factor.divergence,
                'chan_score': factor.chan_score
            }
        return None
    
    def analyze_factors_batch(self, symbols: List[str],
                             data_fetcher: Callable) -> pd.DataFrame:
        """
        批量分析缠论因子
        
        Args:
            symbols: 股票代码列表
            data_fetcher: 数据获取函数
            
        Returns:
            因子DataFrame
        """
        return self.factor_analyzer.extractor.extract_factors_batch(symbols, data_fetcher)
    
    def generate_factor_report(self, symbols: List[str],
                              data_fetcher: Callable) -> str:
        """
        生成缠论因子分析报告
        
        Args:
            symbols: 股票代码列表
            data_fetcher: 数据获取函数
            
        Returns:
            报告文本
        """
        return self.factor_analyzer.generate_report(symbols, data_fetcher)
    
    # ==================== 5. 深度分析结论 ====================
    
    def get_deep_analysis(self, symbol: str, df: pd.DataFrame) -> Dict:
        """
        获取股票的缠论深度分析
        
        Args:
            symbol: 股票代码
            df: K线数据
            
        Returns:
            深度分析结果
        """
        analysis = self.get_analysis(symbol, df)
        if not analysis:
            return {'error': '分析失败'}
        
        # 提取因子
        factor = self.extract_factors(symbol, df)
        
        # 获取最新信号
        signal = self.adapter.get_latest_signal(symbol, df) if self.adapter else None
        
        # 生成交易建议
        decision = self.analyze_for_trade(symbol, df)
        
        return {
            'symbol': symbol,
            'analysis': analysis,
            'factor': factor,
            'signal': signal,
            'trade_decision': decision,
            'conclusion': self._generate_conclusion(analysis, factor, signal, decision)
        }
    
    def _generate_conclusion(self, analysis: ChanAnalysis, factor: Dict,
                            signal: ChanSignal, decision: TradeDecision) -> str:
        """生成分析结论"""
        conclusions = []
        
        # 结构分析
        conclusions.append(f"【结构分析】")
        conclusions.append(f"  笔数量: {len(analysis.bi_list)}")
        conclusions.append(f"  线段数量: {len(analysis.seg_list)}")
        conclusions.append(f"  中枢数量: {len(analysis.zs_list)}")
        
        # 趋势分析
        conclusions.append(f"\n【趋势判断】")
        conclusions.append(f"  当前趋势: {analysis.trend}")
        if factor:
            conclusions.append(f"  趋势强度: {factor.get('trend_strength', 0):.2f}")
        
        # 买卖点分析
        conclusions.append(f"\n【买卖点分析】")
        if analysis.buy_points:
            latest_buy = analysis.buy_points[-1]
            conclusions.append(f"  最新买点: {latest_buy['type']} @ {latest_buy['price']:.2f}")
        if analysis.sell_points:
            latest_sell = analysis.sell_points[-1]
            conclusions.append(f"  最新卖点: {latest_sell['type']} @ {latest_sell['price']:.2f}")
        
        # 背驰分析
        if factor and factor.get('divergence') != 0:
            div_type = "底背驰" if factor['divergence'] == 1 else "顶背驰"
            conclusions.append(f"\n【背驰信号】")
            conclusions.append(f"  检测到{div_type}")
            conclusions.append(f"  背驰强度: {factor.get('divergence_strength', 0):.2f}")
        
        # 位置分析
        if factor:
            conclusions.append(f"\n【位置分析】")
            pos_map = {-1: "中枢下方", 0: "中枢内部", 1: "中枢上方"}
            conclusions.append(f"  相对位置: {pos_map.get(factor.get('price_to_zs'), '未知')}")
        
        # 交易建议
        conclusions.append(f"\n【交易建议】")
        if decision:
            action = "买入" if decision.action == TradeAction.BUY else "卖出"
            conclusions.append(f"  建议操作: {action}")
            conclusions.append(f"  置信度: {decision.confidence}")
            conclusions.append(f"  理由: {decision.reason}")
        elif signal:
            if signal.signal_type == 'buy':
                conclusions.append(f"  建议: 关注买入机会 ({signal.bsp_type})")
            elif signal.signal_type == 'sell':
                conclusions.append(f"  建议: 关注卖出机会 ({signal.bsp_type})")
            else:
                conclusions.append(f"  建议: 持仓观望")
        
        # 综合评分
        conclusions.append(f"\n【综合评分】")
        conclusions.append(f"  缠论评分: {analysis.score}/100")
        if analysis.score >= 80:
            conclusions.append(f"  评级: 强烈看多")
        elif analysis.score >= 60:
            conclusions.append(f"  评级: 看多")
        elif analysis.score >= 40:
            conclusions.append(f"  评级: 中性")
        elif analysis.score >= 20:
            conclusions.append(f"  评级: 看空")
        else:
            conclusions.append(f"  评级: 强烈看空")
        
        return "\n".join(conclusions)
    
    # ==================== 辅助方法 ====================
    
    def get_analysis(self, symbol: str, df: pd.DataFrame) -> Optional[ChanAnalysis]:
        """获取分析结果（带缓存）"""
        cache_key = f"{symbol}_{len(df)}"
        
        if cache_key not in self.last_analysis:
            if self.adapter:
                self.last_analysis[cache_key] = self.adapter.analyze(symbol, df)
        
        return self.last_analysis.get(cache_key)
    
    def clear_cache(self):
        """清除缓存"""
        self.last_analysis.clear()
        self.last_signals.clear()
    
    def get_status(self) -> Dict:
        """获取集成模块状态"""
        return {
            'adapter_ready': self.adapter is not None,
            'picker_ready': self.picker is not None,
            'trader_ready': self.trader is not None,
            'factor_analyzer_ready': self.factor_analyzer is not None,
            'cached_analysis_count': len(self.last_analysis),
            'cached_signal_count': len(self.last_signals)
        }


# 便捷函数
def get_chan_integration(config: Dict = None) -> Optional[ChanIntegration]:
    """获取集成模块实例"""
    try:
        return ChanIntegration(config)
    except Exception as e:
        print(f"Chan.py集成模块初始化失败: {e}")
        return None


# 快速使用函数
def quick_chan_analysis(symbol: str, df: pd.DataFrame) -> Dict:
    """快速缠论分析"""
    integration = get_chan_integration()
    if integration:
        return integration.get_deep_analysis(symbol, df)
    return {'error': 'Chan.py模块不可用'}


def quick_chan_scan(symbols: List[str], data_fetcher: Callable) -> Dict:
    """快速缠论扫描"""
    integration = get_chan_integration()
    if integration:
        return integration.scan_watchlist(symbols, data_fetcher)
    return {'error': 'Chan.py模块不可用'}


def quick_chan_plot(df: pd.DataFrame, symbol: str):
    """快速绘制缠论K线图"""
    integration = get_chan_integration()
    if integration:
        return integration.plot_kline_with_chan(df, symbol)
    return None


if __name__ == '__main__':
    # 测试集成模块
    print("Chan.py-main 综合集成模块测试")
    print("=" * 60)
    
    from stock_data import get_stock_data
    
    # 初始化集成模块
    integration = get_chan_integration()
    
    if not integration:
        print("集成模块初始化失败")
        exit(1)
    
    print(f"模块状态: {integration.get_status()}")
    print()
    
    # 测试单只股票分析
    symbol = '000001'
    print(f"测试股票: {symbol}")
    
    df = get_stock_data(symbol, count=100)
    if not df.empty:
        # 深度分析
        analysis = integration.get_deep_analysis(symbol, df)
        
        print("\n深度分析结论:")
        print(analysis.get('conclusion', '无结论'))
        
        # 因子提取
        factor = integration.extract_factors(symbol, df)
        if factor:
            print(f"\n缠论评分: {factor.get('chan_score', 0)}")
            print(f"趋势: {factor.get('trend', '未知')}")
        
        # 交易决策
        decision = integration.analyze_for_trade(symbol, df)
        if decision:
            print(f"\n交易决策: {decision.action.value}")
            print(f"置信度: {decision.confidence}")
    else:
        print("获取数据失败")
    
    print("\n" + "=" * 60)
    print("测试完成")
