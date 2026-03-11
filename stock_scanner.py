# -*- coding: utf-8 -*-
"""
实时选股扫描器 - 从OpenBB-develop整合
基于通达信选股指标进行实时扫描
"""

import pandas as pd
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed


class StockScanner:
    """股票扫描器"""
    
    def __init__(self, score_threshold: int = 60):
        """
        初始化扫描器
        
        Args:
            score_threshold: 买入评分阈值，默认60分
        """
        self.score_threshold = score_threshold
        self.results = []
    
    def scan_stock(self, code: str, df: pd.DataFrame) -> Dict:
        """
        扫描单只股票
        
        Args:
            code: 股票代码
            df: 股票数据
            
        Returns:
            扫描结果字典
        """
        try:
            from tdx_stock_picker import TDXStockPicker
            
            if len(df) < 60:
                return {'code': code, 'score': 0, 'error': '数据不足'}
            
            picker = TDXStockPicker(df)
            score_result = picker.get_latest_score()
            
            score = score_result['score']
            signals = score_result['signals']
            
            # 判断是否满足买入条件
            is_candidate = score >= self.score_threshold
            
            return {
                'code': code,
                'score': score,
                'price': score_result['price'],
                'ma5': score_result['ma5'],
                'ma20': score_result['ma20'],
                'signals': signals,
                'components': score_result['components'],
                'is_candidate': is_candidate,
                'zhongshu_upper': score_result['zhongshu_upper'],
                'zhongshu_lower': score_result['zhongshu_lower']
            }
            
        except Exception as e:
            return {'code': code, 'score': 0, 'error': str(e)}
    
    def scan_stocks(self, stock_codes: List[str], data_fetcher) -> List[Dict]:
        """
        批量扫描股票
        
        Args:
            stock_codes: 股票代码列表
            data_fetcher: 数据获取函数，接收code返回df
            
        Returns:
            扫描结果列表（按评分排序）
        """
        results = []
        
        def fetch_and_scan(code):
            try:
                df = data_fetcher(code)
                if df is not None and not df.empty:
                    return self.scan_stock(code, df)
            except Exception as e:
                return {'code': code, 'score': 0, 'error': str(e)}
            return {'code': code, 'score': 0, 'error': '无数据'}
        
        # 使用线程池并行扫描
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(fetch_and_scan, code): code for code in stock_codes}
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)
        
        # 按评分排序
        results.sort(key=lambda x: x.get('score', 0), reverse=True)
        return results
    
    def get_candidates(self, results: List[Dict], top_n: int = 10) -> List[Dict]:
        """
        获取候选股票（评分>=阈值）
        
        Args:
            results: 扫描结果列表
            top_n: 返回前N个
            
        Returns:
            候选股票列表
        """
        candidates = [r for r in results if r.get('is_candidate', False)]
        return candidates[:top_n]


def quick_scan(codes: List[str], score_threshold: int = 60) -> List[Dict]:
    """
    快速扫描便捷函数
    
    Args:
        codes: 股票代码列表
        score_threshold: 评分阈值
        
    Returns:
        按评分排序的结果列表
    """
    from stock_data import get_stock_data
    
    scanner = StockScanner(score_threshold)
    
    def fetcher(code):
        return get_stock_data(code, count=100)
    
    return scanner.scan_stocks(codes, fetcher)


def scan_watch_list(watch_list: List[str], score_threshold: int = 60) -> Dict:
    """
    扫描监控列表
    
    Args:
        watch_list: 监控列表
        score_threshold: 评分阈值
        
    Returns:
        扫描结果汇总
    """
    results = quick_scan(watch_list, score_threshold)
    
    scanner = StockScanner(score_threshold)
    candidates = scanner.get_candidates(results, top_n=20)
    
    return {
        'total_scanned': len(watch_list),
        'candidates_count': len(candidates),
        'candidates': candidates,
        'all_results': results[:20]  # 前20名
    }
