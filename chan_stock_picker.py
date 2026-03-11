# -*- coding: utf-8 -*-
"""
Chan.py-main 缠论选股模块
基于缠论买卖点进行股票筛选和监控
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from chan_adapter import ChanAdapter, ChanSignal, ChanAnalysis, get_chan_adapter


@dataclass
class ChanPickResult:
    """选股结果"""
    symbol: str
    name: str
    signal_type: str      # buy/sell/hold
    bsp_type: str         # 买卖点类型
    score: int            # 综合评分 0-100
    price: float
    trend: str
    strength: str         # 信号强度：极强/强/中等/弱
    bi_count: int
    zs_count: int
    description: str
    update_time: datetime


class ChanStockPicker:
    """
    缠论选股器
    基于chan.py的买卖点识别进行选股
    """
    
    def __init__(self, min_score: int = 60, max_workers: int = 5):
        """
        初始化选股器
        
        Args:
            min_score: 最小信号强度阈值
            max_workers: 并行扫描线程数
        """
        self.adapter = get_chan_adapter()
        self.min_score = min_score
        self.max_workers = max_workers
        self.results: List[ChanPickResult] = []
        
    def pick_single(self, symbol: str, df: pd.DataFrame, 
                    name: str = '') -> Optional[ChanPickResult]:
        """
        分析单只股票
        
        Args:
            symbol: 股票代码
            df: K线数据
            name: 股票名称
            
        Returns:
            选股结果或None
        """
        if not self.adapter or df.empty or len(df) < 60:
            return None
        
        try:
            # 获取缠论信号
            signal = self.adapter.get_latest_signal(symbol, df)
            if not signal:
                return None
            
            # 过滤掉hold信号和低强度信号
            if signal.signal_type == 'hold' or signal.strength < self.min_score:
                return None
            
            # 判断信号强度
            if signal.strength >= 80:
                strength = '极强'
            elif signal.strength >= 70:
                strength = '强'
            elif signal.strength >= 60:
                strength = '中等'
            else:
                strength = '弱'
            
            return ChanPickResult(
                symbol=symbol,
                name=name or symbol,
                signal_type=signal.signal_type,
                bsp_type=signal.bsp_type,
                score=signal.strength,
                price=signal.price,
                trend=signal.trend,
                strength=strength,
                bi_count=signal.bi_count,
                zs_count=signal.zs_count,
                description=signal.description,
                update_time=datetime.now()
            )
            
        except Exception as e:
            print(f"分析 {symbol} 失败: {e}")
            return None
    
    def pick_batch(self, symbols: List[str], 
                   data_fetcher: Callable[[str], pd.DataFrame],
                   name_map: Dict[str, str] = None) -> List[ChanPickResult]:
        """
        批量选股
        
        Args:
            symbols: 股票代码列表
            data_fetcher: 数据获取函数
            name_map: 代码到名称的映射
            
        Returns:
            选股结果列表
        """
        results = []
        name_map = name_map or {}
        
        def analyze_one(symbol):
            try:
                df = data_fetcher(symbol)
                if df is not None and not df.empty:
                    return self.pick_single(symbol, df, name_map.get(symbol, symbol))
            except Exception as e:
                print(f"获取 {symbol} 数据失败: {e}")
            return None
        
        # 并行处理
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(analyze_one, s): s for s in symbols}
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)
        
        # 按评分排序
        results.sort(key=lambda x: x.score, reverse=True)
        self.results = results
        return results
    
    def get_buy_candidates(self, top_n: int = 10) -> List[ChanPickResult]:
        """获取买入候选"""
        buys = [r for r in self.results if r.signal_type == 'buy']
        return buys[:top_n]
    
    def get_sell_candidates(self, top_n: int = 10) -> List[ChanPickResult]:
        """获取卖出候选"""
        sells = [r for r in self.results if r.signal_type == 'sell']
        return sells[:top_n]
    
    def get_watchlist_recommendations(self, watchlist: List[str],
                                     data_fetcher) -> Dict:
        """
        为监控列表生成推荐
        
        Args:
            watchlist: 监控列表股票代码
            data_fetcher: 数据获取函数
            
        Returns:
            推荐结果字典
        """
        results = self.pick_batch(watchlist, data_fetcher)
        
        buy_signals = [r for r in results if r.signal_type == 'buy']
        sell_signals = [r for r in results if r.signal_type == 'sell']
        
        return {
            'total_scanned': len(watchlist),
            'signals_found': len(results),
            'buy_count': len(buy_signals),
            'sell_count': len(sell_signals),
            'buy_recommendations': buy_signals[:5],
            'sell_recommendations': sell_signals[:5],
            'all_signals': results
        }
    
    def format_result_for_display(self, result: ChanPickResult) -> Dict:
        """格式化结果为显示格式"""
        signal_emoji = '买入' if result.signal_type == 'buy' else '卖出'
        
        return {
            '代码': result.symbol,
            '名称': result.name,
            '信号': signal_emoji,
            '类型': result.bsp_type,
            '评分': result.score,
            '强度': result.strength,
            '价格': f"{result.price:.2f}",
            '趋势': result.trend,
            '笔/中枢': f"{result.bi_count}/{result.zs_count}",
            '描述': result.description
        }


class ChanMonitor:
    """
    缠论监控器
    持续监控股票列表的缠论信号变化
    """
    
    def __init__(self, picker: ChanStockPicker = None):
        self.picker = picker or ChanStockPicker()
        self.last_signals: Dict[str, ChanSignal] = {}
        self.signal_history: List[Dict] = []
        
    def check_new_signals(self, symbols: List[str], 
                         data_fetcher) -> List[ChanPickResult]:
        """
        检查新的买卖信号
        
        Returns:
            新出现的信号列表
        """
        new_signals = []
        
        for symbol in symbols:
            try:
                df = data_fetcher(symbol)
                if df is None or df.empty:
                    continue
                
                signal = self.picker.adapter.get_latest_signal(symbol, df)
                if not signal:
                    continue
                
                # 检查是否是新信号
                last_signal = self.last_signals.get(symbol)
                
                if signal.signal_type != 'hold':
                    if last_signal is None or \
                       (last_signal.signal_type != signal.signal_type or 
                        last_signal.bsp_type != signal.bsp_type):
                        # 新信号出现
                        new_signals.append(
                            self.picker.pick_single(symbol, df)
                        )
                
                # 更新缓存
                self.last_signals[symbol] = signal
                
            except Exception as e:
                print(f"检查 {symbol} 信号失败: {e}")
        
        return new_signals
    
    def get_signal_summary(self) -> Dict:
        """获取信号汇总"""
        buy_count = sum(1 for s in self.last_signals.values() if s.signal_type == 'buy')
        sell_count = sum(1 for s in self.last_signals.values() if s.signal_type == 'sell')
        hold_count = sum(1 for s in self.last_signals.values() if s.signal_type == 'hold')
        
        return {
            'total_monitored': len(self.last_signals),
            'buy_signals': buy_count,
            'sell_signals': sell_count,
            'hold': hold_count
        }


# 便捷函数
def quick_chan_pick(symbols: List[str], 
                   min_score: int = 60,
                   data_fetcher=None) -> List[ChanPickResult]:
    """
    快速选股便捷函数
    
    Args:
        symbols: 股票代码列表
        min_score: 最小评分
        data_fetcher: 数据获取函数，为None则使用默认
        
    Returns:
        选股结果列表
    """
    if data_fetcher is None:
        from stock_data import get_stock_data
        data_fetcher = lambda s: get_stock_data(s, count=100)
    
    picker = ChanStockPicker(min_score=min_score)
    return picker.pick_batch(symbols, data_fetcher)


def scan_chan_signals(symbols: List[str]) -> Dict:
    """
    扫描缠论信号便捷函数
    
    Args:
        symbols: 股票代码列表
        
    Returns:
        扫描结果字典
    """
    from stock_data import get_stock_data
    
    picker = ChanStockPicker(min_score=50)
    
    def fetcher(symbol):
        return get_stock_data(symbol, count=100)
    
    results = picker.pick_batch(symbols, fetcher)
    
    return {
        'buy_signals': [r for r in results if r.signal_type == 'buy'],
        'sell_signals': [r for r in results if r.signal_type == 'sell'],
        'all_results': results
    }


if __name__ == '__main__':
    # 测试
    print("缠论选股模块测试")
    print("=" * 50)
    
    from stock_data import get_stock_data
    
    # 测试股票列表
    test_symbols = ['000001', '600519', '000858', '002594', '300750']
    
    print(f"\n扫描 {len(test_symbols)} 只股票...")
    
    results = quick_chan_pick(test_symbols, min_score=50)
    
    print(f"\n发现 {len(results)} 个信号:")
    print("-" * 50)
    
    for r in results:
        signal_type = "买入" if r.signal_type == 'buy' else "卖出"
        print(f"{r.symbol} {r.name}: {signal_type}信号 [{r.bsp_type}] "
              f"评分:{r.score} 强度:{r.strength} 价格:{r.price:.2f}")
        print(f"  描述: {r.description}")
        print()
