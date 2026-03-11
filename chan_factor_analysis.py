# -*- coding: utf-8 -*-
"""
Chan.py-main 缠论因子分析模块
将缠论分析结果作为量化因子，用于深度分析和策略构建
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass

from chan_adapter import ChanAdapter, ChanAnalysis, get_chan_adapter


@dataclass
class ChanFactor:
    """缠论因子数据类"""
    symbol: str
    date: datetime
    
    # 结构因子
    bi_count: int = 0           # 笔数量
    seg_count: int = 0          # 线段数量
    zs_count: int = 0           # 中枢数量
    
    # 趋势因子
    trend: str = ''             # 趋势方向
    trend_strength: float = 0   # 趋势强度
    
    # 买卖点因子
    has_buy_point: int = 0      # 是否有买点
    has_sell_point: int = 0     # 是否有卖点
    buy_point_type: str = ''    # 买点类型
    sell_point_type: str = ''   # 卖点类型
    
    # 位置因子
    price_to_zs: float = 0      # 价格相对中枢位置 (-1=下方, 0=内部, 1=上方)
    zs_width: float = 0         # 中枢宽度
    
    # 背驰因子
    divergence: int = 0         # 背驰信号
    divergence_strength: float = 0  # 背驰强度
    
    # 综合评分
    chan_score: float = 50      # 缠论综合评分


class ChanFactorExtractor:
    """
    缠论因子提取器
    从缠论分析结果中提取量化因子
    """
    
    def __init__(self):
        self.adapter = get_chan_adapter()
    
    def extract_factors(self, symbol: str, df: pd.DataFrame) -> Optional[ChanFactor]:
        """
        从股票数据提取缠论因子
        
        Args:
            symbol: 股票代码
            df: K线数据
            
        Returns:
            ChanFactor对象
        """
        if not self.adapter or df.empty:
            return None
        
        # 获取缠论分析
        analysis = self.adapter.analyze(symbol, df)
        if not analysis:
            return None
        
        # 最新日期
        date = df['datetime'].iloc[-1] if 'datetime' in df.columns else datetime.now()
        
        # 最新价格
        last_price = df['close'].iloc[-1]
        
        # 提取结构因子
        bi_count = len(analysis.bi_list)
        seg_count = len(analysis.seg_list)
        zs_count = len(analysis.zs_list)
        
        # 提取买卖点因子
        has_buy_point = 1 if analysis.buy_points else 0
        has_sell_point = 1 if analysis.sell_points else 0
        buy_point_type = analysis.buy_points[-1]['type'] if analysis.buy_points else ''
        sell_point_type = analysis.sell_points[-1]['type'] if analysis.sell_points else ''
        
        # 计算位置因子
        price_to_zs = self._calc_price_to_zs(last_price, analysis.zs_list)
        zs_width = self._calc_zs_width(analysis.zs_list)
        
        # 计算趋势强度
        trend_strength = self._calc_trend_strength(analysis)
        
        # 检测背驰
        divergence, divergence_strength = self._detect_divergence(analysis, df)
        
        return ChanFactor(
            symbol=symbol,
            date=date,
            bi_count=bi_count,
            seg_count=seg_count,
            zs_count=zs_count,
            trend=analysis.trend,
            trend_strength=trend_strength,
            has_buy_point=has_buy_point,
            has_sell_point=has_sell_point,
            buy_point_type=buy_point_type,
            sell_point_type=sell_point_type,
            price_to_zs=price_to_zs,
            zs_width=zs_width,
            divergence=divergence,
            divergence_strength=divergence_strength,
            chan_score=analysis.score
        )
    
    def _calc_price_to_zs(self, price: float, zs_list: List[Dict]) -> float:
        """计算价格相对中枢位置"""
        if not zs_list:
            return 0
        
        last_zs = zs_list[-1]
        zg = last_zs.get('zg', price)
        zd = last_zs.get('zd', price)
        
        if price > zg:
            return 1  # 中枢上方
        elif price < zd:
            return -1  # 中枢下方
        else:
            return 0  # 中枢内部
    
    def _calc_zs_width(self, zs_list: List[Dict]) -> float:
        """计算中枢宽度（标准化）"""
        if not zs_list:
            return 0
        
        last_zs = zs_list[-1]
        zg = last_zs.get('zg', 0)
        zd = last_zs.get('zd', 0)
        
        if zg > 0:
            return (zg - zd) / zg
        return 0
    
    def _calc_trend_strength(self, analysis: ChanAnalysis) -> float:
        """计算趋势强度"""
        if not analysis.bi_list:
            return 0
        
        # 基于笔的方向一致性计算趋势强度
        bi_directions = [bi['direction'] for bi in analysis.bi_list[-5:]]  # 最近5笔
        
        if not bi_directions:
            return 0
        
        up_count = bi_directions.count('up')
        down_count = bi_directions.count('down')
        
        # 趋势强度 = (多数方向数量 - 少数方向数量) / 总数
        total = len(bi_directions)
        if total == 0:
            return 0
        
        return abs(up_count - down_count) / total
    
    def _detect_divergence(self, analysis: ChanAnalysis, 
                          df: pd.DataFrame) -> Tuple[int, float]:
        """检测背驰信号"""
        if not analysis.bi_list or len(df) < 10:
            return 0, 0
        
        # 简化背驰检测：比较价格走势和笔力度
        last_bi = analysis.bi_list[-1]
        
        # 如果最后一笔是向下笔，检查是否有底背驰
        if last_bi['direction'] == 'down' and len(analysis.bi_list) >= 2:
            prev_bi = analysis.bi_list[-2]
            
            # 价格创新低但笔的力度减弱
            if last_bi['end_price'] < prev_bi['start_price']:
                # 简化计算背驰强度
                price_change = abs(last_bi['end_price'] - last_bi['start_price'])
                prev_change = abs(prev_bi['end_price'] - prev_bi['start_price'])
                
                if prev_change > 0 and price_change < prev_change:
                    strength = 1 - price_change / prev_change
                    return 1, strength
        
        # 如果最后一笔是向上笔，检查是否有顶背驰
        if last_bi['direction'] == 'up' and len(analysis.bi_list) >= 2:
            prev_bi = analysis.bi_list[-2]
            
            if last_bi['end_price'] > prev_bi['start_price']:
                price_change = abs(last_bi['end_price'] - last_bi['start_price'])
                prev_change = abs(prev_bi['end_price'] - prev_bi['start_price'])
                
                if prev_change > 0 and price_change < prev_change:
                    strength = 1 - price_change / prev_change
                    return -1, strength
        
        return 0, 0
    
    def extract_factors_batch(self, symbols: List[str],
                             data_fetcher) -> pd.DataFrame:
        """
        批量提取因子
        
        Args:
            symbols: 股票代码列表
            data_fetcher: 数据获取函数
            
        Returns:
            因子DataFrame
        """
        factors_list = []
        
        for symbol in symbols:
            try:
                df = data_fetcher(symbol)
                if df is not None and not df.empty:
                    factor = self.extract_factors(symbol, df)
                    if factor:
                        factors_list.append(self._factor_to_dict(factor))
            except Exception as e:
                print(f"提取 {symbol} 因子失败: {e}")
        
        return pd.DataFrame(factors_list)
    
    def _factor_to_dict(self, factor: ChanFactor) -> Dict:
        """将因子对象转为字典"""
        return {
            'symbol': factor.symbol,
            'date': factor.date,
            'bi_count': factor.bi_count,
            'seg_count': factor.seg_count,
            'zs_count': factor.zs_count,
            'trend': factor.trend,
            'trend_strength': factor.trend_strength,
            'has_buy_point': factor.has_buy_point,
            'has_sell_point': factor.has_sell_point,
            'buy_point_type': factor.buy_point_type,
            'sell_point_type': factor.sell_point_type,
            'price_to_zs': factor.price_to_zs,
            'zs_width': factor.zs_width,
            'divergence': factor.divergence,
            'divergence_strength': factor.divergence_strength,
            'chan_score': factor.chan_score
        }


class ChanFactorAnalyzer:
    """
    缠论因子分析器
    对缠论因子进行统计分析和深度解读
    """
    
    def __init__(self):
        self.extractor = ChanFactorExtractor()
    
    def analyze_factors(self, factors_df: pd.DataFrame) -> Dict:
        """
        分析因子数据
        
        Args:
            factors_df: 因子DataFrame
            
        Returns:
            分析结果字典
        """
        if factors_df.empty:
            return {}
        
        analysis = {
            'total_stocks': len(factors_df),
            'date': datetime.now().strftime('%Y-%m-%d'),
            
            # 结构统计
            'structure_stats': {
                'avg_bi_count': factors_df['bi_count'].mean(),
                'avg_seg_count': factors_df['seg_count'].mean(),
                'avg_zs_count': factors_df['zs_count'].mean(),
            },
            
            # 趋势分布
            'trend_distribution': factors_df['trend'].value_counts().to_dict(),
            
            # 买卖点统计
            'signal_stats': {
                'buy_signals': factors_df['has_buy_point'].sum(),
                'sell_signals': factors_df['has_sell_point'].sum(),
                'no_signals': len(factors_df) - factors_df['has_buy_point'].sum() 
                             - factors_df['has_sell_point'].sum()
            },
            
            # 位置分布
            'position_distribution': {
                'above_zs': (factors_df['price_to_zs'] == 1).sum(),
                'in_zs': (factors_df['price_to_zs'] == 0).sum(),
                'below_zs': (factors_df['price_to_zs'] == -1).sum()
            },
            
            # 背驰统计
            'divergence_stats': {
                'bottom_divergence': (factors_df['divergence'] == 1).sum(),
                'top_divergence': (factors_df['divergence'] == -1).sum(),
                'no_divergence': (factors_df['divergence'] == 0).sum()
            },
            
            # 评分分布
            'score_stats': {
                'avg_score': factors_df['chan_score'].mean(),
                'high_score_count': (factors_df['chan_score'] >= 70).sum(),
                'low_score_count': (factors_df['chan_score'] <= 30).sum()
            }
        }
        
        # 优质股票列表（高评分+买点）
        good_stocks = factors_df[
            (factors_df['chan_score'] >= 70) & 
            (factors_df['has_buy_point'] == 1)
        ].sort_values('chan_score', ascending=False)
        
        analysis['recommended_stocks'] = good_stocks['symbol'].tolist()[:10]
        
        # 风险股票列表（低评分+卖点）
        risk_stocks = factors_df[
            (factors_df['chan_score'] <= 30) & 
            (factors_df['has_sell_point'] == 1)
        ].sort_values('chan_score')
        
        analysis['risk_stocks'] = risk_stocks['symbol'].tolist()[:10]
        
        return analysis
    
    def generate_report(self, symbols: List[str], 
                       data_fetcher) -> str:
        """
        生成缠论因子分析报告
        
        Args:
            symbols: 股票代码列表
            data_fetcher: 数据获取函数
            
        Returns:
            报告文本
        """
        # 提取因子
        factors_df = self.extractor.extract_factors_batch(symbols, data_fetcher)
        
        if factors_df.empty:
            return "无法提取因子数据"
        
        # 分析因子
        analysis = self.analyze_factors(factors_df)
        
        # 生成报告
        lines = [
            "=" * 60,
            "缠论因子分析报告",
            "=" * 60,
            f"分析日期: {analysis.get('date', '')}",
            f"股票数量: {analysis.get('total_stocks', 0)}",
            "",
            "【结构统计】",
            f"  平均笔数量: {analysis['structure_stats']['avg_bi_count']:.2f}",
            f"  平均线段数量: {analysis['structure_stats']['avg_seg_count']:.2f}",
            f"  平均中枢数量: {analysis['structure_stats']['avg_zs_count']:.2f}",
            "",
            "【趋势分布】",
        ]
        
        for trend, count in analysis.get('trend_distribution', {}).items():
            lines.append(f"  {trend}: {count}")
        
        lines.extend([
            "",
            "【买卖点统计】",
            f"  买入信号: {analysis['signal_stats']['buy_signals']}",
            f"  卖出信号: {analysis['signal_stats']['sell_signals']}",
            f"  无信号: {analysis['signal_stats']['no_signals']}",
            "",
            "【位置分布】",
            f"  中枢上方: {analysis['position_distribution']['above_zs']}",
            f"  中枢内部: {analysis['position_distribution']['in_zs']}",
            f"  中枢下方: {analysis['position_distribution']['below_zs']}",
            "",
            "【背驰统计】",
            f"  底背驰: {analysis['divergence_stats']['bottom_divergence']}",
            f"  顶背驰: {analysis['divergence_stats']['top_divergence']}",
            f"  无背驰: {analysis['divergence_stats']['no_divergence']}",
            "",
            "【评分统计】",
            f"  平均评分: {analysis['score_stats']['avg_score']:.2f}",
            f"  高评分(>=70): {analysis['score_stats']['high_score_count']}",
            f"  低评分(<=30): {analysis['score_stats']['low_score_count']}",
            "",
            "【推荐关注】",
        ])
        
        for i, symbol in enumerate(analysis.get('recommended_stocks', []), 1):
            lines.append(f"  {i}. {symbol}")
        
        lines.extend([
            "",
            "【风险提示】",
        ])
        
        for i, symbol in enumerate(analysis.get('risk_stocks', []), 1):
            lines.append(f"  {i}. {symbol}")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


class ChanFactorStrategy:
    """
    缠论因子策略
    基于缠论因子构建量化策略
    """
    
    def __init__(self):
        self.extractor = ChanFactorExtractor()
    
    def select_stocks(self, factors_df: pd.DataFrame, 
                     top_n: int = 10) -> pd.DataFrame:
        """
        基于缠论因子选股
        
        选股逻辑：
        1. 有买点信号
        2. 缠论评分高
        3. 趋势向上
        4. 价格在中枢上方或内部
        """
        if factors_df.empty:
            return pd.DataFrame()
        
        # 筛选条件
        mask = (
            (factors_df['has_buy_point'] == 1) &  # 有买点
            (factors_df['chan_score'] >= 60) &    # 评分>=60
            (factors_df['trend'].str.contains('上涨', na=False)) &  # 趋势向上
            (factors_df['price_to_zs'] >= 0)      # 价格在中枢上方或内部
        )
        
        selected = factors_df[mask].copy()
        
        # 计算综合得分
        selected['composite_score'] = (
            selected['chan_score'] * 0.4 +
            selected['trend_strength'] * 30 +
            selected['has_buy_point'] * 20 +
            selected['price_to_zs'] * 10
        )
        
        # 排序并返回前N个
        return selected.sort_values('composite_score', ascending=False).head(top_n)
    
    def rank_stocks(self, factors_df: pd.DataFrame) -> pd.DataFrame:
        """对股票进行缠论排名"""
        if factors_df.empty:
            return pd.DataFrame()
        
        df = factors_df.copy()
        
        # 计算各项排名
        df['score_rank'] = df['chan_score'].rank(ascending=False, pct=True)
        df['trend_rank'] = df['trend_strength'].rank(ascending=False, pct=True)
        df['structure_rank'] = (df['bi_count'] + df['seg_count'] + df['zs_count']).rank(pct=True)
        
        # 综合排名
        df['overall_rank'] = (df['score_rank'] + df['trend_rank'] + df['structure_rank']) / 3
        
        return df.sort_values('overall_rank', ascending=False)


# 便捷函数
def extract_chan_factors(symbol: str, df: pd.DataFrame) -> Optional[ChanFactor]:
    """便捷函数：提取单只股票缠论因子"""
    extractor = ChanFactorExtractor()
    return extractor.extract_factors(symbol, df)


def analyze_chan_factors(symbols: List[str], data_fetcher) -> Dict:
    """便捷函数：分析缠论因子"""
    analyzer = ChanFactorAnalyzer()
    factors_df = analyzer.extractor.extract_factors_batch(symbols, data_fetcher)
    return analyzer.analyze_factors(factors_df)


def generate_chan_report(symbols: List[str], data_fetcher) -> str:
    """便捷函数：生成缠论报告"""
    analyzer = ChanFactorAnalyzer()
    return analyzer.generate_report(symbols, data_fetcher)


if __name__ == '__main__':
    # 测试
    print("缠论因子分析模块测试")
    print("=" * 50)
    
    from stock_data import get_stock_data
    
    test_symbols = ['000001', '600519', '000858']
    
    print(f"\n测试股票: {test_symbols}")
    
    def fetcher(symbol):
        return get_stock_data(symbol, count=100)
    
    # 测试因子提取
    extractor = ChanFactorExtractor()
    factors_df = extractor.extract_factors_batch(test_symbols, fetcher)
    
    if not factors_df.empty:
        print("\n提取的因子:")
        print(factors_df[['symbol', 'bi_count', 'zs_count', 'trend', 
                         'has_buy_point', 'has_sell_point', 'chan_score']])
        
        # 测试因子分析
        print("\n" + "=" * 50)
        print("因子分析:")
        
        analyzer = ChanFactorAnalyzer()
        analysis = analyzer.analyze_factors(factors_df)
        
        print(f"趋势分布: {analysis.get('trend_distribution', {})}")
        print(f"买卖点统计: {analysis.get('signal_stats', {})}")
        print(f"平均评分: {analysis.get('score_stats', {}).get('avg_score', 0):.2f}")
        
        # 测试报告生成
        print("\n" + "=" * 50)
        print("生成报告:")
        report = analyzer.generate_report(test_symbols, fetcher)
        print(report[:500] + "...")
    else:
        print("因子提取失败")
