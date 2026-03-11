# -*- coding: utf-8 -*-
"""
Chan.py-main 缠论模块适配器
将chan.py-main集成到量化交易系统R6

功能：
1. 数据桥接：将pytdx数据转换为chan.py格式
2. 缠论分析：笔、段、中枢、买卖点识别
3. 选股扫描：基于缠论买卖点的选股
4. 信号输出：买卖信号、趋势判断、背驰检测
"""

import sys
import os
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass

# 添加chan.py-main到路径
CHAN_PY_PATH = os.path.join(os.path.dirname(__file__), 'chan.py-main')
if CHAN_PY_PATH not in sys.path:
    sys.path.insert(0, CHAN_PY_PATH)

# 尝试导入 chan.py 模块
try:
    from Chan import CChan
    from ChanConfig import CChanConfig
    from Common.CEnum import AUTYPE, DATA_SRC, KL_TYPE, BSP_TYPE, DATA_FIELD
    from BuySellPoint.BS_Point import CBS_Point
    from KLine.KLine_Unit import CKLine_Unit
    from Common.CTime import CTime
    from DataAPI.CommonStockAPI import CCommonStockApi
    CHAN_PY_AVAILABLE = True
except ImportError as e:
    print(f"Chan.py-main 导入失败：{e}")
    CHAN_PY_AVAILABLE = False


class DataFrameDataAPI(CCommonStockApi):
    """自定义 DataFrame 数据源，允许直接传入 pandas DataFrame"""
    
    def __init__(self, code, df, k_type=KL_TYPE.K_DAY, begin_date=None, end_date=None, autype=None):
        self.df = df
        super(DataFrameDataAPI, self).__init__(code, k_type, begin_date, end_date, autype)
    
    def get_kl_data(self):
        """从 DataFrame 生成 K 线数据"""
        for idx, row in self.df.iterrows():
            # 转换时间
            time_val = row.get('date', row.get('time'))
            if isinstance(time_val, (pd.Timestamp, datetime)):
                ctime = CTime(time_val.year, time_val.month, time_val.day, 
                             time_val.hour if hasattr(time_val, 'hour') else 0,
                             time_val.minute if hasattr(time_val, 'minute') else 0)
            else:
                # 假设是字符串或数字
                time_str = str(time_val)
                if len(time_str) >= 10:
                    year = int(time_str[:4])
                    month = int(time_str[5:7])
                    day = int(time_str[8:10])
                    hour = minute = 0
                    ctime = CTime(year, month, day, hour, minute)
                else:
                    continue
            
            # 创建 K 线单位
            klu = CKLine_Unit({
                DATA_FIELD.FIELD_TIME: ctime,
                DATA_FIELD.FIELD_OPEN: float(row['open']),
                DATA_FIELD.FIELD_HIGH: float(row['high']),
                DATA_FIELD.FIELD_LOW: float(row['low']),
                DATA_FIELD.FIELD_CLOSE: float(row['close']),
                DATA_FIELD.FIELD_VOLUME: float(row.get('volume', 0))
            })
            yield klu
    
    def SetBasciInfo(self):
        pass
    
    @classmethod
    def do_init(cls):
        pass
    
    @classmethod
    def do_close(cls):
        pass


@dataclass
class ChanSignal:
    """缠论信号数据类"""
    symbol: str
    signal_type: str  # 'buy', 'sell', 'hold'
    bsp_type: str     # '1类买点', '2类买点', '3类买点', '1类卖点'等
    is_sure: bool     # 是否确定
    price: float
    date: datetime
    strength: int     # 信号强度 0-100
    description: str
    bi_count: int = 0
    zs_count: int = 0
    trend: str = ''


@dataclass
class ChanAnalysis:
    """缠论分析结果"""
    symbol: str
    bi_list: List[Dict]      # 笔列表
    seg_list: List[Dict]     # 线段列表
    zs_list: List[Dict]      # 中枢列表
    buy_points: List[Dict]   # 买点列表
    sell_points: List[Dict]  # 卖点列表
    trend: str               # 趋势判断
    score: int               # 综合评分
    last_price: float
    chan_structure: Dict     # 缠论结构数据


class ChanAdapter:
    """
    Chan.py-main 适配器
    桥接pytdx数据和chan.py分析引擎
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化适配器
        
        Args:
            config: 配置字典，可选参数包括：
                - bi_strict: 是否严格笔
                - divergence_rate: 背驰比例阈值
                - min_zs_cnt: 最小中枢数量
                - bs_type: 买卖点类型 '1,2,3a,1p,2s,3b'
        """
        if not CHAN_PY_AVAILABLE:
            raise ImportError("Chan.py-main模块不可用，请检查安装")
        
        self.config = self._create_config(config or {})
        self.chan_cache: Dict[str, CChan] = {}  # 缓存chan对象
        
    def _create_config(self, config_dict: Dict) -> CChanConfig:
        """创建chan.py配置"""
        default_config = {
            "bi_strict": True,
            "trigger_step": False,
            "skip_step": 0,
            "divergence_rate": 0.8,
            "bsp2_follow_1": False,
            "bsp3_follow_1": False,
            "min_zs_cnt": 1,
            "bs1_peak": False,
            "macd_algo": "peak",
            "bs_type": "1,2,3a,1p,2s,3b",
            "print_warning": False,
            "zs_algo": "normal",
        }
        default_config.update(config_dict)
        return CChanConfig(default_config)
    
    def _convert_df_to_chan_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        将pytdx数据格式转换为chan.py格式
        
        chan.py需要的列：
        - date: 日期
        - open: 开盘价
        - high: 最高价
        - low: 最低价
        - close: 收盘价
        - volume: 成交量
        """
        if df.empty:
            return df
        
        # 复制数据避免修改原数据
        data = df.copy()
        
        # 确保datetime列存在
        if 'datetime' in data.columns:
            data['date'] = pd.to_datetime(data['datetime'])
        elif 'date' not in data.columns:
            data['date'] = pd.to_datetime(data.index)
        
        # 统一列名
        column_map = {
            'vol': 'volume',
            'amount': 'turnover'
        }
        data = data.rename(columns=column_map)
        
        # 确保必要列存在
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in data.columns:
                if col == 'volume':
                    data[col] = 0
                else:
                    raise ValueError(f"缺少必要列: {col}")
        
        return data[required_cols]
    
    def analyze(self, symbol: str, df: pd.DataFrame, 
                lv_list: List[str] = None) -> Optional[ChanAnalysis]:
        """
        对股票进行缠论分析
            
        Args:
            symbol: 股票代码
            df: K 线数据 DataFrame
            lv_list: 级别列表，如 ['day', '60min']
                
        Returns:
            ChanAnalysis 对象
        """
        if df.empty or len(df) < 60:
            return None
            
        try:
            # 转换数据格式
            chan_df = self._convert_df_to_chan_format(df)
                
            # 级别映射
            lv_map = {
                'day': KL_TYPE.K_DAY,
                '60min': KL_TYPE.K_60M,
                '30min': KL_TYPE.K_30M,
                '15min': KL_TYPE.K_15M,
                '5min': KL_TYPE.K_5M,
                '1min': KL_TYPE.K_1M,
                'week': KL_TYPE.K_WEEK
            }
                
            if lv_list is None:
                lv_list = ['day']
                
            kl_types = [lv_map.get(lv, KL_TYPE.K_DAY) for lv in lv_list]
                
            # 创建 chan 对象，使用自定义 DataFrame 数据源
            # 通过 monkey patch 方式传入自定义数据
            import DataAPI.AkshareAPI as AkshareAPI
            original_init = AkshareAPI.CAkshare.__init__
            original_get_kl_data = AkshareAPI.CAkshare.get_kl_data
                        
            # 临时修改 CAkshare 类以使用我们的 DataFrame
            def custom_init(self, code, k_type=KL_TYPE.K_DAY, begin_date=None, end_date=None, autype=None):
                self.code = code
                self.df = chan_df
                self.k_type = k_type
                        
            def custom_get_kl_data(self):
                from Common.CEnum import DATA_FIELD
                for idx, row in self.df.iterrows():
                    time_val = row['date']
                    ctime = CTime(
                        year=time_val.year if hasattr(time_val, 'year') else int(str(time_val)[:4]),
                        month=time_val.month if hasattr(time_val, 'month') else int(str(time_val)[5:7]),
                        day=time_val.day if hasattr(time_val, 'day') else int(str(time_val)[8:10]),
                        hour=0,
                        minute=0
                    )
                    klu = CKLine_Unit({
                        DATA_FIELD.FIELD_TIME: ctime,
                        DATA_FIELD.FIELD_OPEN: float(row['open']),
                        DATA_FIELD.FIELD_HIGH: float(row['high']),
                        DATA_FIELD.FIELD_LOW: float(row['low']),
                        DATA_FIELD.FIELD_CLOSE: float(row['close']),
                        DATA_FIELD.FIELD_VOLUME: float(row.get('volume', 0))
                    })
                    yield klu
                        
            AkshareAPI.CAkshare.__init__ = custom_init
            AkshareAPI.CAkshare.get_kl_data = custom_get_kl_data
                        
            # 创建 chan 对象
            chan = CChan(
                code=symbol,
                data_src=DATA_SRC.AKSHARE,  # 使用 AKSHARE 但数据由我们提供
                lv_list=kl_types,
                config=self.config,
                autype=AUTYPE.QFQ
            )
                        
            # 加载数据
            for _ in chan.load():
                pass
                        
            # 恢复原始方法
            AkshareAPI.CAkshare.__init__ = original_init
            AkshareAPI.CAkshare.get_kl_data = original_get_kl_data
                
            # 缓存 chan 对象
            self.chan_cache[symbol] = chan
                
            # 提取分析结果
            return self._extract_analysis(chan, symbol, df)
                    
        except Exception as e:
            print(f"缠论分析失败 {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            pass  # 不再需要清理临时文件
    
    def _extract_analysis(self, chan: CChan, symbol: str, 
                          df: pd.DataFrame) -> ChanAnalysis:
        """从chan对象提取分析结果"""
        
        # 获取日线数据
        kl_type = list(chan.kl_datas.keys())[0] if chan.kl_datas else None
        if kl_type is None:
            return ChanAnalysis(symbol=symbol, bi_list=[], seg_list=[], 
                               zs_list=[], buy_points=[], sell_points=[], 
                               trend='未知', score=50, last_price=0, chan_structure={})
        
        kl_data = chan.kl_datas[kl_type]
        
        # 提取笔
        bi_list = []
        for bi in kl_data.bi_list:
            bi_list.append({
                'start_idx': bi.start_klu.idx if bi.start_klu else 0,
                'end_idx': bi.end_klu.idx if bi.end_klu else 0,
                'start_price': bi.start_klu.low if bi.start_klu and bi.is_down() else (bi.start_klu.high if bi.start_klu else 0),
                'end_price': bi.end_klu.high if bi.end_klu and bi.is_up() else (bi.end_klu.low if bi.end_klu else 0),
                'direction': 'up' if bi.is_up() else 'down',
                'is_sure': bi.is_sure
            })
        
        # 提取线段
        seg_list = []
        for seg in kl_data.seg_list:
            seg_list.append({
                'start_idx': seg.start_bi.idx if seg.start_bi else 0,
                'end_idx': seg.end_bi.idx if seg.end_bi else 0,
                'direction': 'up' if seg.is_up else 'down',
                'is_sure': seg.is_sure
            })
        
        # 提取中枢
        zs_list = []
        for zs in kl_data.zs_list:
            zs_list.append({
                'start_idx': zs.begin_bi.idx if zs.begin_bi else 0,
                'end_idx': zs.end_bi.idx if zs.end_bi else 0,
                'zg': zs.zg,  # 中枢高点
                'zd': zs.zd,  # 中枢低点
                'gg': zs.gg,  # 最高点
                'dd': zs.dd,  # 最低点
            })
        
        # 提取买卖点
        buy_points = []
        sell_points = []
        
        for bsp in kl_data.bs_point_lst:
            bsp_info = {
                'type': bsp.type2str(),
                'is_buy': bsp.is_buy,
                'idx': bsp.klu.idx if bsp.klu else 0,
                'price': bsp.klu.close if bsp.klu else 0,
                'is_sure': True  # 简化处理
            }
            if bsp.is_buy:
                buy_points.append(bsp_info)
            else:
                sell_points.append(bsp_info)
        
        # 趋势判断
        trend = self._judge_trend(bi_list, seg_list)
        
        # 综合评分
        score = self._calculate_score(buy_points, sell_points, trend)
        
        # 最新价格
        last_price = df['close'].iloc[-1] if not df.empty else 0
        
        return ChanAnalysis(
            symbol=symbol,
            bi_list=bi_list,
            seg_list=seg_list,
            zs_list=zs_list,
            buy_points=buy_points,
            sell_points=sell_points,
            trend=trend,
            score=score,
            last_price=last_price,
            chan_structure={
                'bi_count': len(bi_list),
                'seg_count': len(seg_list),
                'zs_count': len(zs_list),
                'buy_point_count': len(buy_points),
                'sell_point_count': len(sell_points)
            }
        )
    
    def _judge_trend(self, bi_list: List[Dict], seg_list: List[Dict]) -> str:
        """判断趋势"""
        if not bi_list:
            return '未知'
        
        # 根据最后一笔方向判断
        last_bi = bi_list[-1]
        
        if seg_list:
            last_seg = seg_list[-1]
            if last_seg['direction'] == 'up':
                return '上涨' if last_bi['direction'] == 'up' else '上涨回调'
            else:
                return '下跌' if last_bi['direction'] == 'down' else '下跌反弹'
        
        return '上涨' if last_bi['direction'] == 'up' else '下跌'
    
    def _calculate_score(self, buy_points: List[Dict], sell_points: List[Dict], 
                         trend: str) -> int:
        """计算综合评分"""
        score = 50  # 基准分
        
        # 买点加分
        if buy_points:
            latest_buy = buy_points[-1]
            if '1类' in latest_buy['type']:
                score += 30
            elif '2类' in latest_buy['type']:
                score += 20
            elif '3类' in latest_buy['type']:
                score += 10
        
        # 卖点减分
        if sell_points:
            latest_sell = sell_points[-1]
            if '1类' in latest_sell['type']:
                score -= 30
            elif '2类' in latest_sell['type']:
                score -= 20
            elif '3类' in latest_sell['type']:
                score -= 10
        
        # 趋势调整
        if '上涨' in trend:
            score += 10
        elif '下跌' in trend:
            score -= 10
        
        return max(0, min(100, score))
    
    def get_latest_signal(self, symbol: str, df: pd.DataFrame) -> Optional[ChanSignal]:
        """
        获取最新买卖信号
        
        Args:
            symbol: 股票代码
            df: K线数据
            
        Returns:
            ChanSignal对象或None
        """
        analysis = self.analyze(symbol, df)
        if not analysis:
            return None
        
        # 优先返回买点信号
        if analysis.buy_points:
            latest = analysis.buy_points[-1]
            return ChanSignal(
                symbol=symbol,
                signal_type='buy',
                bsp_type=latest['type'],
                is_sure=latest['is_sure'],
                price=latest['price'],
                date=datetime.now(),
                strength=analysis.score,
                description=f"缠论{latest['type']}信号，趋势{analysis.trend}",
                bi_count=len(analysis.bi_list),
                zs_count=len(analysis.zs_list),
                trend=analysis.trend
            )
        
        # 其次返回卖点信号
        if analysis.sell_points:
            latest = analysis.sell_points[-1]
            return ChanSignal(
                symbol=symbol,
                signal_type='sell',
                bsp_type=latest['type'],
                is_sure=latest['is_sure'],
                price=latest['price'],
                date=datetime.now(),
                strength=100 - analysis.score,
                description=f"缠论{latest['type']}信号，趋势{analysis.trend}",
                bi_count=len(analysis.bi_list),
                zs_count=len(analysis.zs_list),
                trend=analysis.trend
            )
        
        # 无信号
        return ChanSignal(
            symbol=symbol,
            signal_type='hold',
            bsp_type='无',
            is_sure=False,
            price=analysis.last_price,
            date=datetime.now(),
            strength=50,
            description=f"无明确信号，趋势{analysis.trend}",
            bi_count=len(analysis.bi_list),
            zs_count=len(analysis.zs_list),
            trend=analysis.trend
        )
    
    def scan_for_signals(self, symbols: List[str], 
                         data_fetcher) -> List[ChanSignal]:
        """
        批量扫描股票寻找买卖信号
        
        Args:
            symbols: 股票代码列表
            data_fetcher: 数据获取函数，接收symbol返回DataFrame
            
        Returns:
            信号列表
        """
        signals = []
        
        for symbol in symbols:
            try:
                df = data_fetcher(symbol)
                if df is not None and not df.empty:
                    signal = self.get_latest_signal(symbol, df)
                    if signal and signal.signal_type != 'hold':
                        signals.append(signal)
            except Exception as e:
                print(f"扫描 {symbol} 失败: {e}")
        
        # 按信号强度排序
        signals.sort(key=lambda x: x.strength, reverse=True)
        return signals


# 便捷函数
def get_chan_adapter(config: Optional[Dict] = None) -> Optional[ChanAdapter]:
    """获取适配器实例"""
    if not CHAN_PY_AVAILABLE:
        return None
    return ChanAdapter(config)


def analyze_stock_chan(symbol: str, df: pd.DataFrame, 
                       config: Optional[Dict] = None) -> Optional[ChanAnalysis]:
    """便捷函数：分析单只股票"""
    adapter = get_chan_adapter(config)
    if adapter:
        return adapter.analyze(symbol, df)
    return None


def quick_analyze_chan(df: pd.DataFrame, symbol: str = "STOCK") -> Dict:
    """
    快速分析接口（用于双引擎对比）
    
    Args:
        df: DataFrame，包含 ['日期', '开盘', '最高', '最低', '收盘', '成交量']
        symbol: 股票代码
        
    Returns:
        简化分析结果字典
    """
    if not CHAN_PY_AVAILABLE:
        return {
            'symbol': symbol,
            'signal': 'NEUTRAL',
            'bi_count': 0,
            'duan_count': 0,
            'zs_count': 0,
            'bs_point': None,
            'score': 50,
            'error': 'Chan.py-main模块不可用'
        }
    
    try:
        adapter = ChanAdapter()
        result = adapter.analyze(symbol, df)
        
        if result:
            # 获取最新买卖点
            bs_point = None
            if result.buy_points:
                bs_point = result.buy_points[-1]['type']
            elif result.sell_points:
                bs_point = result.sell_points[-1]['type']
            
            return {
                'symbol': symbol,
                'signal': 'BUY' if result.score >= 60 else ('SELL' if result.score <= 40 else 'NEUTRAL'),
                'bi_count': len(result.bi_list),
                'duan_count': len(result.seg_list),
                'zs_count': len(result.zs_list),
                'bs_point': bs_point,
                'score': result.score
            }
        else:
            return {
                'symbol': symbol,
                'signal': 'NEUTRAL',
                'bi_count': 0,
                'duan_count': 0,
                'zs_count': 0,
                'bs_point': None,
                'score': 50
            }
    except Exception as e:
        return {
            'symbol': symbol,
            'signal': 'ERROR',
            'bi_count': 0,
            'duan_count': 0,
            'zs_count': 0,
            'bs_point': None,
            'score': 0,
            'error': str(e)
        }


def get_chan_signal(symbol: str, df: pd.DataFrame,
                    config: Optional[Dict] = None) -> Optional[ChanSignal]:
    """便捷函数：获取买卖信号"""
    adapter = get_chan_adapter(config)
    if adapter:
        return adapter.get_latest_signal(symbol, df)
    return None


if __name__ == '__main__':
    # 测试
    print("Chan.py-main 适配器测试")
    print("=" * 50)
    
    if not CHAN_PY_AVAILABLE:
        print("Chan.py-main模块不可用")
        sys.exit(1)
    
    # 测试数据
    from stock_data import get_stock_data
    
    symbol = '000001'
    print(f"\n测试股票: {symbol}")
    
    df = get_stock_data(symbol, count=200)
    if not df.empty:
        adapter = ChanAdapter()
        analysis = adapter.analyze(symbol, df)
        
        if analysis:
            print(f"\n分析结果:")
            print(f"  笔数量: {len(analysis.bi_list)}")
            print(f"  线段数量: {len(analysis.seg_list)}")
            print(f"  中枢数量: {len(analysis.zs_list)}")
            print(f"  买点数量: {len(analysis.buy_points)}")
            print(f"  卖点数量: {len(analysis.sell_points)}")
            print(f"  趋势: {analysis.trend}")
            print(f"  评分: {analysis.score}")
            
            signal = adapter.get_latest_signal(symbol, df)
            if signal:
                print(f"\n最新信号:")
                print(f"  类型: {signal.signal_type}")
                print(f"  买卖点: {signal.bsp_type}")
                print(f"  强度: {signal.strength}")
                print(f"  描述: {signal.description}")
        else:
            print("分析失败")
    else:
        print("获取数据失败")
