# -*- coding: utf-8 -*-
"""
缠论K线图叠加显示模块
在matplotlib K线图上叠加显示缠论元素：笔、段、中枢、买卖点
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from chan_adapter import ChanAnalysis, ChanSignal, get_chan_adapter


@dataclass
class PlotConfig:
    """绘图配置"""
    show_bi: bool = True          # 显示笔
    show_seg: bool = True         # 显示线段
    show_zs: bool = True          # 显示中枢
    show_bsp: bool = True         # 显示买卖点
    show_macd: bool = False       # 显示MACD
    
    # 颜色配置
    bi_up_color: str = '#FF6B6B'      # 向上笔颜色（红）
    bi_down_color: str = '#4ECDC4'    # 向下笔颜色（绿）
    seg_up_color: str = '#FF0000'     # 向上线段颜色
    seg_down_color: str = '#00FF00'   # 向下线段颜色
    zs_color: str = 'rgba(128,128,128,0.3)'  # 中枢颜色
    bsp_buy_color: str = '#FF0000'    # 买点颜色
    bsp_sell_color: str = '#00FF00'   # 卖点颜色


class ChanPlotOverlay:
    """
    缠论K线图叠加绘制器
    在现有K线图上叠加缠论元素
    """
    
    def __init__(self, config: Optional[PlotConfig] = None):
        self.config = config or PlotConfig()
        self.chan_adapter = get_chan_adapter()
    
    def plot_on_ax(self, ax, df: pd.DataFrame, chan_analysis: ChanAnalysis,
                   x_offset: int = 0) -> Dict:
        """
        在指定的axes上绘制缠论元素
        
        Args:
            ax: matplotlib axes对象
            df: K线数据
            chan_analysis: 缠论分析结果
            x_offset: X轴偏移量（用于多子图）
            
        Returns:
            绘制的元素字典
        """
        if not chan_analysis:
            return {}
        
        plotted = {
            'bi_lines': [],
            'seg_lines': [],
            'zs_patches': [],
            'bsp_markers': []
        }
        
        # 绘制笔
        if self.config.show_bi and chan_analysis.bi_list:
            plotted['bi_lines'] = self._plot_bi(ax, chan_analysis.bi_list, df, x_offset)
        
        # 绘制线段
        if self.config.show_seg and chan_analysis.seg_list:
            plotted['seg_lines'] = self._plot_seg(ax, chan_analysis.seg_list, df, x_offset)
        
        # 绘制中枢
        if self.config.show_zs and chan_analysis.zs_list:
            plotted['zs_patches'] = self._plot_zs(ax, chan_analysis.zs_list, df, x_offset)
        
        # 绘制买卖点
        if self.config.show_bsp:
            if chan_analysis.buy_points:
                plotted['bsp_markers'].extend(
                    self._plot_bsp(ax, chan_analysis.buy_points, df, True, x_offset)
                )
            if chan_analysis.sell_points:
                plotted['bsp_markers'].extend(
                    self._plot_bsp(ax, chan_analysis.sell_points, df, False, x_offset)
                )
        
        return plotted
    
    def _plot_bi(self, ax, bi_list: List[Dict], df: pd.DataFrame, 
                 x_offset: int) -> List[Line2D]:
        """绘制笔"""
        lines = []
        
        for bi in bi_list:
            # 获取笔的起点和终点在df中的索引
            start_idx = min(bi['start_idx'], len(df) - 1)
            end_idx = min(bi['end_idx'], len(df) - 1)
            
            # 转换到实际x坐标
            x1 = start_idx + x_offset
            x2 = end_idx + x_offset
            
            # 根据方向确定价格
            if bi['direction'] == 'up':
                y1 = df.iloc[start_idx]['low']
                y2 = df.iloc[end_idx]['high']
                color = self.config.bi_up_color
            else:
                y1 = df.iloc[start_idx]['high']
                y2 = df.iloc[end_idx]['low']
                color = self.config.bi_down_color
            
            # 绘制笔
            line = ax.plot([x1, x2], [y1, y2], 
                          color=color, 
                          linewidth=2, 
                          alpha=0.8,
                          linestyle='-')[0]
            lines.append(line)
            
            # 在笔的端点标记小圆点
            ax.plot(x1, y1, 'o', color=color, markersize=4, alpha=0.6)
            ax.plot(x2, y2, 'o', color=color, markersize=4, alpha=0.6)
        
        return lines
    
    def _plot_seg(self, ax, seg_list: List[Dict], df: pd.DataFrame,
                  x_offset: int) -> List[Line2D]:
        """绘制线段"""
        lines = []
        
        for seg in seg_list:
            start_idx = min(seg['start_idx'], len(df) - 1)
            end_idx = min(seg['end_idx'], len(df) - 1)
            
            x1 = start_idx + x_offset
            x2 = end_idx + x_offset
            
            # 线段使用笔的高低点
            if seg['direction'] == 'up':
                y1 = df.iloc[start_idx]['low']
                y2 = df.iloc[end_idx]['high']
                color = self.config.seg_up_color
            else:
                y1 = df.iloc[start_idx]['high']
                y2 = df.iloc[end_idx]['low']
                color = self.config.seg_down_color
            
            # 绘制线段（比笔更粗）
            line = ax.plot([x1, x2], [y1, y2],
                          color=color,
                          linewidth=3,
                          alpha=0.7,
                          linestyle='--')[0]
            lines.append(line)
        
        return lines
    
    def _plot_zs(self, ax, zs_list: List[Dict], df: pd.DataFrame,
                 x_offset: int) -> List[patches.Rectangle]:
        """绘制中枢"""
        patches_list = []
        
        for zs in zs_list:
            start_idx = min(zs['start_idx'], len(df) - 1)
            end_idx = min(zs['end_idx'], len(df) - 1)
            
            x = start_idx + x_offset
            width = end_idx - start_idx
            
            # 中枢高低点
            y_low = zs['zd']
            y_high = zs['zg']
            height = y_high - y_low
            
            # 绘制中枢矩形
            rect = patches.Rectangle(
                (x - 0.4, y_low),
                width + 0.8,
                height,
                linewidth=1,
                edgecolor='gray',
                facecolor='lightgray',
                alpha=0.3
            )
            ax.add_patch(rect)
            patches_list.append(rect)
            
            # 标注中枢中轴
            mid_price = (y_high + y_low) / 2
            ax.text(x + width/2, y_high, f'ZS', 
                   fontsize=8, ha='center', va='bottom', color='gray')
        
        return patches_list
    
    def _plot_bsp(self, ax, bsp_list: List[Dict], df: pd.DataFrame,
                  is_buy: bool, x_offset: int) -> List:
        """绘制买卖点标记"""
        markers = []
        
        for bsp in bsp_list:
            idx = min(bsp['idx'], len(df) - 1)
            x = idx + x_offset
            price = bsp['price']
            
            # 买点在下方，卖点在上方
            if is_buy:
                y_offset = -0.02
                color = self.config.bsp_buy_color
                marker = '^'
                label = f"买{bsp['type']}"
            else:
                y_offset = 0.02
                color = self.config.bsp_sell_color
                marker = 'v'
                label = f"卖{bsp['type']}"
            
            # 绘制标记
            y = price * (1 + y_offset)
            scatter = ax.scatter(x, y, marker=marker, s=100, 
                               c=color, edgecolors='black', 
                               linewidths=1, zorder=5)
            markers.append(scatter)
            
            # 添加文字标注
            ax.annotate(label, (x, y), 
                       textcoords="offset points",
                       xytext=(0, 10 if is_buy else -15),
                       ha='center', fontsize=8, color=color,
                       fontweight='bold')
        
        return markers
    
    def create_legend_elements(self) -> List:
        """创建图例元素"""
        legend_elements = [
            Line2D([0], [0], color=self.config.bi_up_color, lw=2, label='向上笔'),
            Line2D([0], [0], color=self.config.bi_down_color, lw=2, label='向下笔'),
            Line2D([0], [0], color=self.config.seg_up_color, lw=3, 
                  linestyle='--', label='向上线段'),
            Line2D([0], [0], color=self.config.seg_down_color, lw=3,
                  linestyle='--', label='向下线段'),
            patches.Patch(facecolor='lightgray', edgecolor='gray',
                         alpha=0.3, label='中枢'),
            Line2D([0], [0], marker='^', color='w', markerfacecolor=self.config.bsp_buy_color,
                  markersize=10, label='买点'),
            Line2D([0], [0], marker='v', color='w', markerfacecolor=self.config.bsp_sell_color,
                  markersize=10, label='卖点'),
        ]
        return legend_elements


def plot_kline_with_chan(df: pd.DataFrame, symbol: str = '',
                         chan_analysis: Optional[ChanAnalysis] = None,
                         figsize: Tuple[int, int] = (14, 8),
                         title: str = None) -> plt.Figure:
    """
    绘制带缠论叠加的K线图
    
    Args:
        df: K线数据DataFrame
        symbol: 股票代码
        chan_analysis: 缠论分析结果（为None则自动计算）
        figsize: 图大小
        title: 图表标题
        
    Returns:
        matplotlib Figure对象
    """
    from matplotlib.dates import DateFormatter
    import matplotlib.dates as mdates
    
    # 如果没有提供分析结果，自动计算
    if chan_analysis is None and symbol:
        adapter = get_chan_adapter()
        if adapter:
            chan_analysis = adapter.analyze(symbol, df)
    
    # 创建图形
    fig, ax = plt.subplots(figsize=figsize)
    
    # 准备数据
    x = np.arange(len(df))
    
    # 绘制K线
    for i, (idx, row) in enumerate(df.iterrows()):
        open_price = row['open']
        close_price = row['close']
        high_price = row['high']
        low_price = row['low']
        
        # 确定颜色
        if close_price >= open_price:
            color = '#FF6B6B'  # 红色涨
            edgecolor = '#FF6B6B'
        else:
            color = '#4ECDC4'  # 绿色跌
            edgecolor = '#4ECDC4'
        
        # 绘制实体
        height = abs(close_price - open_price)
        bottom = min(open_price, close_price)
        rect = patches.Rectangle((i - 0.4, bottom), 0.8, height,
                                  facecolor=color, edgecolor=edgecolor, alpha=0.8)
        ax.add_patch(rect)
        
        # 绘制影线
        ax.plot([i, i], [low_price, high_price], color=edgecolor, linewidth=1)
    
    # 叠加缠论元素
    if chan_analysis:
        overlay = ChanPlotOverlay()
        overlay.plot_on_ax(ax, df, chan_analysis)
        
        # 添加图例
        legend_elements = overlay.create_legend_elements()
        ax.legend(handles=legend_elements, loc='upper left', fontsize=9)
        
        # 添加缠论信息文本
        info_text = f"笔:{chan_analysis.chan_structure.get('bi_count',0)} " \
                   f"线段:{chan_analysis.chan_structure.get('seg_count',0)} " \
                   f"中枢:{chan_analysis.chan_structure.get('zs_count',0)} " \
                   f"买点:{chan_analysis.chan_structure.get('buy_point_count',0)} " \
                   f"卖点:{chan_analysis.chan_structure.get('sell_point_count',0)}"
        ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
               fontsize=9, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # 设置标题和标签
    if title:
        ax.set_title(title, fontsize=14, fontweight='bold')
    elif symbol:
        ax.set_title(f'{symbol} K线缠论分析图', fontsize=14, fontweight='bold')
    
    ax.set_xlabel('时间', fontsize=11)
    ax.set_ylabel('价格', fontsize=11)
    
    # 设置x轴刻度
    n = len(df)
    step = max(1, n // 10)
    ax.set_xticks(range(0, n, step))
    
    if 'datetime' in df.columns:
        labels = [str(d)[:10] for d in df['datetime'].iloc[::step]]
    elif 'date' in df.columns:
        labels = [str(d)[:10] for d in df['date'].iloc[::step]]
    else:
        labels = [str(i) for i in range(0, n, step)]
    
    ax.set_xticklabels(labels, rotation=45, ha='right')
    
    # 网格
    ax.grid(True, alpha=0.3, linestyle='--')
    
    # 自动调整y轴范围
    ax.autoscale_view()
    
    plt.tight_layout()
    return fig


if __name__ == '__main__':
    # 测试
    print("缠论K线图叠加显示测试")
    print("=" * 50)
    
    from stock_data import get_stock_data
    
    symbol = '000001'
    df = get_stock_data(symbol, count=100)
    
    if not df.empty:
        fig = plot_kline_with_chan(df, symbol)
        plt.savefig('chan_kline_test.png', dpi=150, bbox_inches='tight')
        print("已保存测试图片: chan_kline_test.png")
        plt.show()
    else:
        print("获取数据失败")
