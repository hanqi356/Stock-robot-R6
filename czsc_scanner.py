"""
czsc 缠论扫描器模块
集成 czsc 缠论分析到股票扫描器
"""
import pandas as pd
from typing import Dict, List, Optional

try:
  from czsc_adapter import CzscAdapter
except ImportError:
    CzscAdapter= None


class CzscScanner:
    """czsc 缠论扫描器"""
    
    def __init__(self):
        """初始化扫描器"""
        pass
    
    def scan_by_bi(self, adapter: CzscAdapter) -> Dict:
        """
        基于笔的扫描
        
        Args:
            adapter: CzscAdapter 实例
            
        Returns:
            扫描结果
        """
        result = {
            'bi_signal': 'NEUTRAL',
            'bi_direction': None,
            'bi_count': 0,
            'score': 0
        }
        
        bi_list = adapter.get_bi_list()
        if not bi_list:
            return result
        
        result['bi_count'] = len(bi_list)
        last_bi = bi_list[-1]
        result['bi_direction'] = 'UP' if last_bi.direction == 1 else 'DOWN'
        
        # 向上笔加分
        if result['bi_direction'] == 'UP':
            result['bi_signal'] = 'BUY'
            result['score'] = 80
        else:
            result['bi_signal'] = 'SELL'
            result['score'] = 20
        
        return result
    
    def scan_by_fx(self, adapter: CzscAdapter) -> Dict:
        """
        基于分型的扫描
        
        Args:
            adapter: CzscAdapter 实例
            
        Returns:
            扫描结果
        """
        result = {
            'fx_signal': 'NEUTRAL',
            'last_fx_mark': None,
            'fx_count': 0,
            'score': 0
        }
        
        fx_list = adapter.get_fx_list()
        if not fx_list:
            return result
        
        result['fx_count'] = len(fx_list)
        last_fx = fx_list[-1]
        result['last_fx_mark'] = 'BOTTOM' if '底' in str(last_fx.mark) else 'TOP'
        
        # 底分型加分
        if result['last_fx_mark'] == 'BOTTOM':
            result['fx_signal'] = 'BUY'
            result['score'] = 70
        else:
            result['fx_signal'] = 'SELL'
            result['score'] = 30
        
        return result
    
    def scan_comprehensive(self, adapter: CzscAdapter) -> Dict:
        """
        综合缠论扫描
        
        Args:
            adapter: CzscAdapter 实例
            
        Returns:
            综合扫描结果
        """
        # 获取基础分析
        analysis = adapter.analyze()
        
        # 笔扫描
        bi_result = self.scan_by_bi(adapter)
        
        # 分型扫描
        fx_result = self.scan_by_fx(adapter)
        
        # 综合评分
        total_score = (bi_result['score'] * 0.6 + fx_result['score'] * 0.4)
        
        # 最终信号
        if total_score >= 70:
            final_signal = 'STRONG_BUY'
        elif total_score >= 50:
            final_signal = 'BUY'
        elif total_score >= 30:
            final_signal = 'SELL'
        else:
            final_signal = 'STRONG_SELL'
        
        return {
            'symbol': analysis.get('symbol'),
            'final_signal': final_signal,
            'total_score': round(total_score, 2),
            'bi_signal': bi_result['bi_signal'],
            'bi_direction': bi_result['bi_direction'],
            'fx_signal': fx_result['fx_signal'],
            'fx_mark': fx_result['last_fx_mark'],
            'bi_count': bi_result['bi_count'],
            'fx_count': fx_result['fx_count'],
            'kline_count': analysis.get('kline_count', 0)
        }
    
    def scan_stock(self, df: pd.DataFrame, symbol: str = "STOCK") -> Dict:
        """
        扫描单只股票（主接口）
        
        Args:
            df: DataFrame，包含 ['日期', '开盘', '最高', '最低', '收盘', '成交量']
            symbol: 股票代码
            
        Returns:
            扫描结果
        """
        try:
            # 创建适配器
            adapter = CzscAdapter.from_tdx_data(df, symbol=symbol)
            
            # 综合扫描
            result = self.scan_comprehensive(adapter)
            
            return result
            
        except Exception as e:
            return {
                'symbol': symbol,
                'error': str(e),
                'final_signal': 'ERROR',
                'total_score': 0
            }


# 与 stock_scanner.py 集成示例
def integrate_with_stock_scanner():
    """
    将 czsc 扫描器集成到现有 stock_scanner.py
    
    在 stock_scanner.py 中添加以下代码:
    
    def scan_stock(self, code: str, df: pd.DataFrame) -> Dict:
        try:
            # ... 原有 TDX 扫描逻辑 ...
            
            # 添加 czsc 缠论扫描
            from czsc_scanner import CzscScanner
            czsc_scanner = CzscScanner()
            czsc_result = czsc_scanner.scan_stock(df, code)
            
            # 合并评分
            czsc_score = czsc_result['total_score']
            signals['czsc_signal'] = czsc_result['final_signal']
            
            # 更新总分（TDX 占 70%, czsc 缠论占 30%）
            score = score * 0.7 + czsc_score * 0.3
            
            # ... 返回结果 ...
    """
    pass


if __name__ == "__main__":
    import akshare as ak
    
    print("=" * 60)
    print("czsc 缠论扫描器测试")
    print("=" * 60)
    
    # 测试股票
    test_stocks = ["600519", "000858", "002415"]
    
    scanner = CzscScanner()
    
    for symbol in test_stocks[:1]:  # 只测试一只，避免网络问题
        print(f"\n扫描 {symbol}...")
        try:
            # 获取数据
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", 
                                   start_date="20240101", end_date="20241231")
            df = df[['日期', '开盘', '收盘', '最高', '最低', '成交量']]
            
            # 扫描
            result = scanner.scan_stock(df, symbol=symbol)
            
            print(f"  最终信号：{result['final_signal']}")
            print(f"  综合评分：{result['total_score']}")
            print(f"  笔信号：{result['bi_signal']} ({result['bi_direction']})")
            print(f"  分型信号：{result['fx_signal']} ({result['fx_mark']})")
            print(f"  笔数：{result['bi_count']}, 分型数：{result['fx_count']}")
            
        except Exception as e:
            print(f"  ✗ 扫描失败：{e}")
    
    print("\n✓ 扫描器测试完成")
