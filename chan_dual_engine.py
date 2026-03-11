# -*- coding: utf-8 -*-
"""
缠论双引擎分析集成模块
为 6 个核心功能提供 czsc + chan.py 双引擎缠论分析
"""
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class ChanDualEngine:
    """缠论双引擎分析器（czsc + chan.py）"""
    
    def __init__(self):
        """初始化双引擎分析器"""
        self.czsc_available = False
        self.chan_available = False
        
        # 尝试导入 czsc
        try:
            from czsc_adapter import CzscAdapter
            from czsc_scanner import CzscScanner
            self.czsc_available = True
        except ImportError:
            pass
        
        # 尝试导入 chan.py
        try:
            from chan_adapter import quick_analyze_chan
            self.chan_available = True
        except ImportError:
            pass
    
    def analyze_stock(self, df: pd.DataFrame, symbol: str = "STOCK") -> Dict:
        """
        对单只股票进行双引擎缠论分析
        
        Args:
            df: DataFrame，包含 ['日期', '开盘', '最高', '最低', '收盘', '成交量']
            symbol: 股票代码
            
        Returns:
            双引擎分析结果
        """
        result = {
            'symbol': symbol,
            'timestamp': datetime.now(),
            'czsc_analysis': None,
            'chan_analysis': None,
            'consensus': None,
            'recommendation': 'NEUTRAL'
        }
        
        # 转换数据格式
        df_new = df.copy()
        if '日期' in df_new.columns:
            df_new.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            df_new['date'] = pd.to_datetime(df_new['date'])
        
        # czsc 引擎分析
        if self.czsc_available:
            try:
                from czsc_adapter import CzscAdapter
                adapter = CzscAdapter.from_tdx_data(df, symbol=symbol)
                czsc_result = adapter.analyze()
                result['czsc_analysis'] = czsc_result
            except Exception as e:
                result['czsc_analysis'] = {'error': str(e)}
        
        # chan.py 引擎分析
        if self.chan_available:
            try:
                from chan_adapter import quick_analyze_chan
                chan_result = quick_analyze_chan(df_new, symbol)
                result['chan_analysis'] = chan_result
            except Exception as e:
                result['chan_analysis'] = {'error': str(e)}
        
        # 综合判断
        result['consensus'] = self._calculate_consensus(result)
        result['recommendation'] = self._generate_recommendation(result)
        
        return result
    
    def _calculate_consensus(self, result: Dict) -> Dict:
        """计算双引擎共识度"""
        consensus = {
            'signal_agreement': False,
            'score_difference': 0,
            'confidence': 'LOW'
        }
        
        czsc = result.get('czsc_analysis')
        chan = result.get('chan_analysis')
        
        if not czsc or not chan or 'error' in czsc or 'error' in chan:
            return consensus
        
        # 信号一致性
        czsc_buy = czsc.get('signal') in ['BUY', 'STRONG_BUY']
        chan_buy = chan.get('signal') == 'BUY'
        consensus['signal_agreement'] = (czsc_buy == chan_buy)
        
        # 评分差异
        czsc_score = czsc.get('total_score', 50)
        chan_score = chan.get('score', 50)
        consensus['score_difference'] = abs(czsc_score - chan_score)
        
        # 置信度
        if consensus['signal_agreement'] and consensus['score_difference'] < 20:
            consensus['confidence'] = 'HIGH'
        elif consensus['signal_agreement']:
            consensus['confidence'] = 'MEDIUM'
        
        return consensus
    
    def _generate_recommendation(self, result: Dict) -> str:
        """生成投资建议"""
        czsc = result.get('czsc_analysis')
        chan = result.get('chan_analysis')
        consensus = result.get('consensus', {})
        
        if not czsc or not chan:
            return 'NEUTRAL'
        
        # 获取信号
        czsc_signal = czsc.get('signal', 'NEUTRAL')
        chan_signal = chan.get('signal', 'NEUTRAL')
        
        # 高置信度情况
        if consensus.get('confidence') == 'HIGH':
            if czsc_signal in ['STRONG_BUY', 'BUY'] and chan_signal == 'BUY':
                return 'STRONG_BUY'
            elif czsc_signal in ['STRONG_SELL', 'SELL'] and chan_signal == 'SELL':
                return 'STRONG_SELL'
        
        # 中等置信度
        if consensus.get('confidence') == 'MEDIUM':
            if czsc_signal in ['BUY', 'STRONG_BUY']:
                return 'BUY'
            elif czsc_signal in ['SELL', 'STRONG_SELL']:
                return 'SELL'
        
        # 低置信度或分歧
        return 'NEUTRAL'
    
    def batch_analyze(self, stock_data_dict: Dict[str, pd.DataFrame]) -> Dict[str, Dict]:
        """
        批量分析多只股票
        
        Args:
            stock_data_dict: {股票代码：DataFrame} 字典
            
        Returns:
            {股票代码：分析结果} 字典
        """
        results = {}
        for symbol, df in stock_data_dict.items():
            try:
                results[symbol] = self.analyze_stock(df, symbol)
            except Exception as e:
                results[symbol] = {'error': str(e)}
        return results
    
    def get_summary_report(self, results: Dict[str, Dict]) -> str:
        """
        生成汇总报告
        
        Args:
            results: batch_analyze 返回的结果字典
            
        Returns:
            格式化报告文本
        """
        lines = []
        lines.append("=" * 70)
        lines.append("缠论双引擎分析汇总报告")
        lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 70)
        
        buy_list = []
        sell_list = []
        neutral_list = []
        
        for symbol, result in results.items():
            if 'error' in result:
                continue
            
            recommendation = result.get('recommendation', 'NEUTRAL')
            consensus = result.get('consensus', {})
            
            if recommendation in ['BUY', 'STRONG_BUY']:
                buy_list.append((symbol, recommendation, consensus.get('confidence', 'LOW')))
            elif recommendation in ['SELL', 'STRONG_SELL']:
                sell_list.append((symbol, recommendation, consensus.get('confidence', 'LOW')))
            else:
                neutral_list.append((symbol, consensus.get('confidence', 'LOW')))
        
        # 买入信号
        if buy_list:
            lines.append("\n【买入信号】")
            for symbol, rec, conf in sorted(buy_list, key=lambda x: 0 if rec == 'STRONG_BUY' else 1):
                conf_text = "高" if conf == 'HIGH' else ("中" if conf == 'MEDIUM' else "低")
                lines.append(f"  {symbol}: {rec} (置信度：{conf_text})")
        
        # 卖出信号
        if sell_list:
            lines.append("\n【卖出信号】")
            for symbol, rec, conf in sorted(sell_list, key=lambda x: 0 if rec == 'STRONG_SELL' else 1):
                conf_text = "高" if conf == 'HIGH' else ("中" if conf == 'MEDIUM' else "低")
                lines.append(f"  {symbol}: {rec} (置信度：{conf_text})")
        
        # 观望
        if neutral_list:
            lines.append("\n【观望】")
            for symbol, conf in neutral_list:
                conf_text = "高" if conf == 'HIGH' else ("中" if conf == 'MEDIUM' else "低")
                lines.append(f"  {symbol}: NEUTRAL (置信度：{conf_text})")
        
        lines.append("\n" + "=" * 70)
        lines.append(f"总计：{len(results)}只股票 | 买入：{len(buy_list)} | 卖出：{len(sell_list)} | 观望：{len(neutral_list)}")
        lines.append("=" * 70)
        
        return "\n".join(lines)


# 便捷函数
def get_dual_engine() -> ChanDualEngine:
    """获取双引擎分析器实例"""
    return ChanDualEngine()


def analyze_with_dual_engine(df: pd.DataFrame, symbol: str) -> Dict:
    """便捷函数：分析单只股票"""
    engine = get_dual_engine()
    return engine.analyze_stock(df, symbol)


if __name__ == "__main__":
    # 测试
    print("缠论双引擎分析模块测试")
    print("=" * 70)
    
    import akshare as ak
    
    # 测试股票
    test_symbol = "600519"
    print(f"\n测试股票：{test_symbol}")
    
    try:
        # 获取数据
        df = ak.stock_zh_a_hist(symbol=test_symbol, period="daily", 
                               start_date="20240101", end_date="20241231")
        df = df[['日期', '开盘', '收盘', '最高', '最低', '成交量']]
        
        # 双引擎分析
        engine = ChanDualEngine()
        result = engine.analyze_stock(df, test_symbol)
        
        print(f"\nczsc 引擎:")
        czsc = result.get('czsc_analysis', {})
        if 'error' not in czsc:
            print(f"  信号：{czsc.get('signal')}")
            print(f"  评分：{czsc.get('total_score')}")
            print(f"  笔数：{czsc.get('bi_count')}")
        else:
            print(f"  错误：{czsc.get('error')}")
        
        print(f"\nchan.py 引擎:")
        chan = result.get('chan_analysis', {})
        if 'error' not in chan:
            print(f"  信号：{chan.get('signal')}")
            print(f"  评分：{chan.get('score')}")
            print(f"  笔数：{chan.get('bi_count')}")
        else:
            print(f"  错误：{chan.get('error')}")
        
        print(f"\n共识度:")
        consensus = result.get('consensus', {})
        print(f"  信号一致：{'是' if consensus.get('signal_agreement') else '否'}")
        print(f"  置信度：{consensus.get('confidence')}")
        
        print(f"\n最终建议：{result.get('recommendation')}")
        
    except Exception as e:
        print(f"测试失败：{e}")
