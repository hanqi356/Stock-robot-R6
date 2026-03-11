"""
缠论引擎 - 基于 czsc 库实现真正的缠论分析
桥接 pytdx DataFrame 与 czsc 核心算法

功能：
- K线合并 + 分型识别（顶分型/底分型）
- 笔划分（严格缠论定义）
- 中枢识别（至少3笔重叠区域）
- 1/2/3 类买卖点判断
- 背驰检测（笔力度对比）
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Tuple

try:
    import czsc
    from czsc import CZSC, RawBar, Freq, ZS
    CZSC_AVAILABLE = True
except ImportError:
    CZSC_AVAILABLE = False


class ChanlunEngine:
    """缠论分析引擎"""

    def __init__(self, df: pd.DataFrame, symbol: str = 'unknown', freq: str = 'D'):
        """
        初始化缠论引擎

        Parameters:
            df: DataFrame，需包含 open/high/low/close/vol 列，以及 datetime 列
            symbol: 股票代码
            freq: 周期，'D'=日线, 'W'=周线, '60'=60分钟 等
        """
        if not CZSC_AVAILABLE:
            raise ImportError("czsc 库未安装，请运行: pip install czsc")

        self.symbol = symbol
        self.freq_str = freq
        self.freq = self._parse_freq(freq)
        self.df = df.copy()

        # czsc 核心对象
        self.czsc_obj: Optional[CZSC] = None

        # 分析结果缓存
        self._fx_list = []       # 分型列表
        self._bi_list = []       # 笔列表
        self._zs_list = []       # 中枢列表
        self._buy_points = []    # 买点列表
        self._sell_points = []   # 卖点列表

        # 执行分析
        self._run()

    def _parse_freq(self, freq: str):
        """解析周期字符串为 czsc.Freq"""
        freq_map = {
            'D': Freq.D, 'W': Freq.W, 'M': Freq.M,
            '1': Freq.F1, '5': Freq.F5, '15': Freq.F15,
            '30': Freq.F30, '60': Freq.F60, '120': Freq.F120,
        }
        return freq_map.get(freq.upper(), Freq.D)

    def _df_to_bars(self) -> List['RawBar']:
        """将 DataFrame 转换为 czsc.RawBar 列表"""
        bars = []
        df = self.df

        # 确保 datetime 列存在
        if 'datetime' in df.columns:
            dt_col = 'datetime'
        elif 'date' in df.columns:
            dt_col = 'date'
        else:
            dt_col = df.index.name or df.columns[0]

        # 确保 vol 列
        vol_col = 'vol' if 'vol' in df.columns else 'volume'
        if vol_col not in df.columns:
            vol_col = None

        for i, row in df.iterrows():
            dt = row[dt_col]
            if isinstance(dt, str):
                dt = pd.to_datetime(dt)
            elif not isinstance(dt, datetime):
                dt = pd.Timestamp(dt).to_pydatetime()

            bar = RawBar(
                symbol=self.symbol,
                dt=dt,
                freq=self.freq,
                open=float(row['open']),
                close=float(row['close']),
                high=float(row['high']),
                low=float(row['low']),
                vol=float(row[vol_col]) if vol_col else 0.0,
                amount=float(row.get('amount', 0)),
                id=int(i) if isinstance(i, (int, np.integer)) else len(bars)
            )
            bars.append(bar)
        return bars

    def _run(self):
        """执行完整的缠论分析"""
        bars = self._df_to_bars()
        if len(bars) < 10:
            return

        # 初始化 CZSC（自动完成 K线合并 + 分型 + 笔）
        self.czsc_obj = CZSC(bars)

        # 提取分型
        self._fx_list = self.czsc_obj.fx_list

        # 提取笔
        self._bi_list = list(self.czsc_obj.finished_bis)

        # 识别中枢
        self._zs_list = self._find_zhongshu()

        # 识别买卖点
        self._buy_points, self._sell_points = self._find_buy_sell_points()

    # ==================== 中枢识别 ====================

    def _find_zhongshu(self) -> List[Dict]:
        """
        从笔列表中识别中枢
        中枢定义：至少连续3笔存在价格重叠区域
        """
        bis = self._bi_list
        if len(bis) < 3:
            return []

        zs_list = []
        i = 0

        while i <= len(bis) - 3:
            # 取3笔尝试构建中枢
            bi_group = bis[i:i+3]

            # 计算重叠区域
            highs = [bi.high for bi in bi_group]
            lows = [bi.low for bi in bi_group]

            zg = min(highs)   # 中枢上沿 = 最低的高点
            zd = max(lows)    # 中枢下沿 = 最高的低点

            if zd < zg:
                # 有重叠区域，中枢成立
                # 尝试延伸中枢（后续笔是否仍在中枢区间内）
                end_idx = i + 3
                while end_idx < len(bis):
                    next_bi = bis[end_idx]
                    # 笔的高低点与中枢有交集
                    if next_bi.low < zg and next_bi.high > zd:
                        end_idx += 1
                    else:
                        break

                zs_bis = bis[i:end_idx]

                zs_info = {
                    'sdt': zs_bis[0].sdt,          # 中枢起始时间
                    'edt': zs_bis[-1].edt,          # 中枢结束时间
                    'zg': zg,                        # 中枢上沿
                    'zd': zd,                        # 中枢下沿
                    'gg': max(bi.high for bi in zs_bis),  # 中枢最高点
                    'dd': min(bi.low for bi in zs_bis),   # 中枢最低点
                    'bi_count': len(zs_bis),         # 包含笔数
                    'zz': round((zg + zd) / 2, 2),  # 中枢中轴
                }
                zs_list.append(zs_info)
                i = end_idx  # 跳到中枢之后
            else:
                i += 1

        return zs_list

    # ==================== 买卖点识别 ====================

    def _find_buy_sell_points(self) -> Tuple[List[Dict], List[Dict]]:
        """
        识别缠论1/2/3类买卖点

        一类买点：向下笔出现背驰（不依赖中枢）
        二类买点：一买之后的第一次回调不创新低（不依赖中枢）
        三类买点：离开中枢后回踩不进入中枢（依赖中枢）
        """
        buy_points = []
        sell_points = []

        bis = self._bi_list
        if len(bis) < 5:
            return buy_points, sell_points

        # === 一类买卖点（背驰，不依赖中枢） ===
        first_buys = self._find_first_buy_points()
        first_sells = self._find_first_sell_points()
        buy_points.extend(first_buys)
        sell_points.extend(first_sells)

        # === 二类买卖点（不创新低/新高，基于一类买卖点） ===
        buy_points.extend(self._find_second_buy_points(first_buys))
        sell_points.extend(self._find_second_sell_points(first_sells))

        # === 三类买卖点（中枢突破回踩，依赖中枢） ===
        if self._zs_list:
            buy_points.extend(self._find_third_buy_points())
            sell_points.extend(self._find_third_sell_points())

        return buy_points, sell_points

    def _find_first_buy_points(self) -> List[Dict]:
        """一类买点：向下笔背驰（力度减弱）"""
        points = []
        bis = self._bi_list

        for i in range(4, len(bis)):
            bi = bis[i]
            # 向下笔
            if bi.direction.value != '向下':
                continue

            # 找前一个同方向笔
            prev_down = None
            for j in range(i - 2, -1, -2):
                if bis[j].direction.value == '向下':
                    prev_down = bis[j]
                    break

            if prev_down is None:
                continue

            # 背驰条件：当前笔创新低但力度减弱
            if bi.low < prev_down.low and bi.power < prev_down.power:
                points.append({
                    'type': '一买',
                    'dt': bi.edt,
                    'price': bi.low,
                    'power_ratio': round(bi.power / prev_down.power, 2) if prev_down.power > 0 else 0,
                    'bi_index': i,
                })

        return points

    def _find_first_sell_points(self) -> List[Dict]:
        """一类卖点：向上笔背驰（力度减弱）"""
        points = []
        bis = self._bi_list

        for i in range(4, len(bis)):
            bi = bis[i]
            if bi.direction.value != '向上':
                continue

            prev_up = None
            for j in range(i - 2, -1, -2):
                if bis[j].direction.value == '向上':
                    prev_up = bis[j]
                    break

            if prev_up is None:
                continue

            if bi.high > prev_up.high and bi.power < prev_up.power:
                points.append({
                    'type': '一卖',
                    'dt': bi.edt,
                    'price': bi.high,
                    'power_ratio': round(bi.power / prev_up.power, 2) if prev_up.power > 0 else 0,
                    'bi_index': i,
                })

        return points

    def _find_second_buy_points(self, first_buys: List[Dict]) -> List[Dict]:
        """二类买点：一买之后回调不创新低"""
        points = []
        bis = self._bi_list

        for fb in first_buys:
            bi_idx = fb['bi_index']
            # 一买之后至少还有2笔（上+下）
            if bi_idx + 2 < len(bis):
                next_down = bis[bi_idx + 2]  # 回调的向下笔
                if next_down.direction.value == '向下' and next_down.low > fb['price']:
                    points.append({
                        'type': '二买',
                        'dt': next_down.edt,
                        'price': next_down.low,
                        'ref_price': fb['price'],
                        'bi_index': bi_idx + 2,
                    })

        return points

    def _find_second_sell_points(self, first_sells: List[Dict]) -> List[Dict]:
        """二类卖点：一卖之后反弹不创新高"""
        points = []
        bis = self._bi_list

        for fs in first_sells:
            bi_idx = fs['bi_index']
            if bi_idx + 2 < len(bis):
                next_up = bis[bi_idx + 2]
                if next_up.direction.value == '向上' and next_up.high < fs['price']:
                    points.append({
                        'type': '二卖',
                        'dt': next_up.edt,
                        'price': next_up.high,
                        'ref_price': fs['price'],
                        'bi_index': bi_idx + 2,
                    })

        return points

    def _find_third_buy_points(self) -> List[Dict]:
        """三类买点：向上离开中枢后，回踩不进入中枢"""
        points = []
        bis = self._bi_list
        zs_list = self._zs_list

        for zs in zs_list:
            zs_edt = zs['edt']
            zg = zs['zg']
            zd = zs['zd']

            # 找中枢之后的笔
            for i, bi in enumerate(bis):
                if bi.sdt <= zs_edt:
                    continue

                # 向上离开中枢后的回踩
                if bi.direction.value == '向下' and bi.low > zg:
                    points.append({
                        'type': '三买',
                        'dt': bi.edt,
                        'price': bi.low,
                        'zs_zg': zg,
                        'zs_zd': zd,
                        'bi_index': i,
                    })
                    break  # 每个中枢只取第一个三买

        return points

    def _find_third_sell_points(self) -> List[Dict]:
        """三类卖点：向下离开中枢后，反弹不进入中枢"""
        points = []
        bis = self._bi_list
        zs_list = self._zs_list

        for zs in zs_list:
            zs_edt = zs['edt']
            zg = zs['zg']
            zd = zs['zd']

            for i, bi in enumerate(bis):
                if bi.sdt <= zs_edt:
                    continue

                if bi.direction.value == '向上' and bi.high < zd:
                    points.append({
                        'type': '三卖',
                        'dt': bi.edt,
                        'price': bi.high,
                        'zs_zg': zg,
                        'zs_zd': zd,
                        'bi_index': i,
                    })
                    break

        return points

    # ==================== 结果输出 ====================

    def get_fx_df(self) -> pd.DataFrame:
        """获取分型 DataFrame"""
        if not self._fx_list:
            return pd.DataFrame(columns=['datetime', 'mark', 'high', 'low'])

        records = []
        for fx in self._fx_list:
            records.append({
                'datetime': fx.dt,
                'mark': fx.mark.value,
                'high': fx.high,
                'low': fx.low,
            })
        return pd.DataFrame(records)

    def get_bi_df(self) -> pd.DataFrame:
        """获取笔 DataFrame"""
        if not self._bi_list:
            return pd.DataFrame(columns=['sdt', 'edt', 'direction', 'high', 'low', 'power', 'length'])

        records = []
        for bi in self._bi_list:
            records.append({
                'sdt': bi.sdt,
                'edt': bi.edt,
                'direction': bi.direction.value,
                'high': bi.high,
                'low': bi.low,
                'power': round(bi.power, 4),
                'length': bi.length,
            })
        return pd.DataFrame(records)

    def get_zs_df(self) -> pd.DataFrame:
        """获取中枢 DataFrame"""
        if not self._zs_list:
            return pd.DataFrame(columns=['sdt', 'edt', 'zg', 'zd', 'gg', 'dd', 'zz', 'bi_count'])
        return pd.DataFrame(self._zs_list)

    def get_buy_points_df(self) -> pd.DataFrame:
        """获取买点 DataFrame"""
        if not self._buy_points:
            return pd.DataFrame(columns=['type', 'dt', 'price'])
        return pd.DataFrame(self._buy_points)

    def get_sell_points_df(self) -> pd.DataFrame:
        """获取卖点 DataFrame"""
        if not self._sell_points:
            return pd.DataFrame(columns=['type', 'dt', 'price'])
        return pd.DataFrame(self._sell_points)

    def get_latest_signal(self) -> Dict:
        """
        获取最新缠论信号摘要

        返回:
            {
                'bi_count': 笔数量,
                'zs_count': 中枢数量,
                'last_bi_direction': 最后一笔方向,
                'last_bi_power': 最后一笔力度,
                'current_zs': 当前所处中枢信息,
                'latest_buy': 最近买点,
                'latest_sell': 最近卖点,
                'trend': 当前趋势判断,
                'score': 综合评分(0-100),
            }
        """
        result = {
            'bi_count': len(self._bi_list),
            'zs_count': len(self._zs_list),
            'last_bi_direction': None,
            'last_bi_power': 0,
            'current_zs': None,
            'latest_buy': None,
            'latest_sell': None,
            'trend': '未知',
            'score': 50,
        }

        if not self._bi_list:
            return result

        # 最后一笔信息
        last_bi = self._bi_list[-1]
        result['last_bi_direction'] = last_bi.direction.value
        result['last_bi_power'] = round(last_bi.power, 4)

        # 当前中枢
        if self._zs_list:
            result['current_zs'] = self._zs_list[-1]

        # 最近买卖点
        if self._buy_points:
            result['latest_buy'] = self._buy_points[-1]
        if self._sell_points:
            result['latest_sell'] = self._sell_points[-1]

        # 趋势判断
        result['trend'] = self._judge_trend()

        # 综合评分
        result['score'] = self._calculate_score()

        return result

    def _judge_trend(self) -> str:
        """根据笔和中枢判断当前趋势"""
        bis = self._bi_list
        zs_list = self._zs_list

        if len(bis) < 3:
            return '未知'

        last_bi = bis[-1]
        last_price = last_bi.high if last_bi.direction.value == '向上' else last_bi.low

        # 如果有中枢
        if zs_list:
            last_zs = zs_list[-1]
            if last_price > last_zs['zg']:
                return '上涨'
            elif last_price < last_zs['zd']:
                return '下跌'
            else:
                return '盘整'

        # 没有中枢，用笔的高低点判断
        recent_bis = bis[-4:]
        up_bis = [b for b in recent_bis if b.direction.value == '向上']
        down_bis = [b for b in recent_bis if b.direction.value == '向下']

        if len(up_bis) >= 2 and up_bis[-1].high > up_bis[0].high:
            return '上涨'
        if len(down_bis) >= 2 and down_bis[-1].low < down_bis[0].low:
            return '下跌'

        return '盘整'

    def _calculate_score(self) -> int:
        """
        综合评分系统（0-100）
        高分 = 适合买入，低分 = 适合卖出

        评分维度：
        1. 趋势方向 (20分)
        2. 买卖点信号 (30分)
        3. 背驰强度 (20分)
        4. 中枢位置 (15分)
        5. 笔力度变化 (15分)
        """
        score = 50  # 基准分

        bis = self._bi_list
        if len(bis) < 3:
            return score

        last_bi = bis[-1]

        # 1. 趋势方向
        trend = self._judge_trend()
        if trend == '上涨':
            score += 10
        elif trend == '下跌':
            score -= 10

        # 2. 买卖点信号
        if self._buy_points:
            latest_buy = self._buy_points[-1]
            # 最近的买点距今越近，分数越高
            buy_bi_idx = latest_buy.get('bi_index', 0)
            distance = len(bis) - buy_bi_idx
            if distance <= 2:
                if latest_buy['type'] == '一买':
                    score += 25
                elif latest_buy['type'] == '二买':
                    score += 20
                elif latest_buy['type'] == '三买':
                    score += 15

        if self._sell_points:
            latest_sell = self._sell_points[-1]
            sell_bi_idx = latest_sell.get('bi_index', 0)
            distance = len(bis) - sell_bi_idx
            if distance <= 2:
                if latest_sell['type'] == '一卖':
                    score -= 25
                elif latest_sell['type'] == '二卖':
                    score -= 20
                elif latest_sell['type'] == '三卖':
                    score -= 15

        # 3. 背驰强度
        if len(bis) >= 4:
            last_same_dir = None
            for b in reversed(bis[:-1]):
                if b.direction.value == last_bi.direction.value:
                    last_same_dir = b
                    break

            if last_same_dir and last_same_dir.power > 0:
                power_ratio = last_bi.power / last_same_dir.power
                if last_bi.direction.value == '向下' and power_ratio < 0.7:
                    # 下跌力度衰竭，利好
                    score += 15
                elif last_bi.direction.value == '向上' and power_ratio < 0.7:
                    # 上涨力度衰竭，利空
                    score -= 15

        # 4. 中枢位置
        if self._zs_list:
            last_zs = self._zs_list[-1]
            current_price = self.df['close'].iloc[-1]

            if current_price > last_zs['zg']:
                score += 8  # 在中枢上方
            elif current_price < last_zs['zd']:
                score -= 8  # 在中枢下方

        # 5. 最后一笔方向
        if last_bi.direction.value == '向上':
            score += 5
        else:
            score -= 5

        return max(0, min(100, score))

    def enrich_dataframe(self) -> pd.DataFrame:
        """
        将缠论分析结果写入原始 DataFrame

        新增列：
        - chan_fx_mark: 分型标记（顶分型/底分型/None）
        - chan_bi_dir: 所在笔的方向
        - chan_bi_high/chan_bi_low: 所在笔的高低点
        - chan_in_zs: 是否在中枢内
        - chan_zs_zg/chan_zs_zd: 当前中枢上下沿
        - chan_buy_signal: 买点类型
        - chan_sell_signal: 卖点类型
        - chan_score: 当前综合评分
        """
        df = self.df.copy()
        n = len(df)

        # 初始化列
        df['chan_fx_mark'] = None
        df['chan_bi_dir'] = None
        df['chan_bi_high'] = np.nan
        df['chan_bi_low'] = np.nan
        df['chan_in_zs'] = False
        df['chan_zs_zg'] = np.nan
        df['chan_zs_zd'] = np.nan
        df['chan_buy_signal'] = None
        df['chan_sell_signal'] = None

        # 确定 datetime 列
        if 'datetime' in df.columns:
            dt_col = 'datetime'
        elif 'date' in df.columns:
            dt_col = 'date'
        else:
            dt_col = df.columns[0]

        dt_values = pd.to_datetime(df[dt_col])

        # 填充分型标记
        for fx in self._fx_list:
            mask = dt_values == pd.Timestamp(fx.dt)
            if mask.any():
                df.loc[mask, 'chan_fx_mark'] = fx.mark.value

        # 填充笔信息
        for bi in self._bi_list:
            sdt = pd.Timestamp(bi.sdt)
            edt = pd.Timestamp(bi.edt)
            mask = (dt_values >= sdt) & (dt_values <= edt)
            df.loc[mask, 'chan_bi_dir'] = bi.direction.value
            df.loc[mask, 'chan_bi_high'] = bi.high
            df.loc[mask, 'chan_bi_low'] = bi.low

        # 填充中枢信息
        for zs in self._zs_list:
            sdt = pd.Timestamp(zs['sdt'])
            edt = pd.Timestamp(zs['edt'])
            mask = (dt_values >= sdt) & (dt_values <= edt)
            df.loc[mask, 'chan_in_zs'] = True
            df.loc[mask, 'chan_zs_zg'] = zs['zg']
            df.loc[mask, 'chan_zs_zd'] = zs['zd']

        # 填充买卖点信号
        for bp in self._buy_points:
            mask = dt_values == pd.Timestamp(bp['dt'])
            if mask.any():
                df.loc[mask, 'chan_buy_signal'] = bp['type']

        for sp in self._sell_points:
            mask = dt_values == pd.Timestamp(sp['dt'])
            if mask.any():
                df.loc[mask, 'chan_sell_signal'] = sp['type']

        # 填充评分（最后一行）
        signal = self.get_latest_signal()
        df['chan_score'] = signal['score']
        df['chan_trend'] = signal['trend']

        return df

    def summary(self) -> str:
        """生成文字摘要"""
        signal = self.get_latest_signal()
        lines = []
        lines.append(f"[{self.symbol}] 缠论分析")
        lines.append(f"  笔数: {signal['bi_count']}, 中枢数: {signal['zs_count']}")
        lines.append(f"  趋势: {signal['trend']}")
        lines.append(f"  评分: {signal['score']}")

        if signal['last_bi_direction']:
            lines.append(f"  最后笔: {signal['last_bi_direction']}, 力度: {signal['last_bi_power']}")

        if signal['current_zs']:
            zs = signal['current_zs']
            lines.append(f"  当前中枢: {zs['zd']:.2f} ~ {zs['zg']:.2f} (中轴{zs['zz']:.2f})")

        if signal['latest_buy']:
            bp = signal['latest_buy']
            lines.append(f"  最近买点: {bp['type']} @ {bp['price']:.2f}")

        if signal['latest_sell']:
            sp = signal['latest_sell']
            lines.append(f"  最近卖点: {sp['type']} @ {sp['price']:.2f}")

        return '\n'.join(lines)


def analyze_stock(df: pd.DataFrame, symbol: str = 'unknown', freq: str = 'D') -> Dict:
    """
    便捷函数：对股票进行缠论分析

    Parameters:
        df: K线 DataFrame
        symbol: 股票代码
        freq: 周期

    Returns:
        {
            'signal': 最新信号摘要,
            'summary': 文字摘要,
            'fx_df': 分型 DataFrame,
            'bi_df': 笔 DataFrame,
            'zs_df': 中枢 DataFrame,
            'buy_points': 买点 DataFrame,
            'sell_points': 卖点 DataFrame,
            'enriched_df': 带缠论标注的 DataFrame,
        }
    """
    try:
        engine = ChanlunEngine(df, symbol=symbol, freq=freq)
        return {
            'success': True,
            'signal': engine.get_latest_signal(),
            'summary': engine.summary(),
            'fx_df': engine.get_fx_df(),
            'bi_df': engine.get_bi_df(),
            'zs_df': engine.get_zs_df(),
            'buy_points': engine.get_buy_points_df(),
            'sell_points': engine.get_sell_points_df(),
            'enriched_df': engine.enrich_dataframe(),
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
        }


if __name__ == '__main__':
    # 测试
    print("测试缠论引擎...")

    try:
        from stock_data import get_stock_data
        print("获取 000001 日线数据...")
        df = get_stock_data('000001', 'day', 200)

        if not df.empty:
            result = analyze_stock(df, symbol='000001')
            if result['success']:
                print(result['summary'])
                print(f"\n分型数: {len(result['fx_df'])}")
                print(f"笔数: {len(result['bi_df'])}")
                print(f"中枢数: {len(result['zs_df'])}")
                print(f"买点数: {len(result['buy_points'])}")
                print(f"卖点数: {len(result['sell_points'])}")

                if not result['bi_df'].empty:
                    print("\n最近5笔:")
                    print(result['bi_df'].tail())

                if not result['buy_points'].empty:
                    print("\n买点:")
                    print(result['buy_points'])
            else:
                print(f"分析失败: {result['error']}")
        else:
            print("获取数据失败")
    except Exception as e:
        print(f"测试异常: {e}")
        import traceback
        traceback.print_exc()
