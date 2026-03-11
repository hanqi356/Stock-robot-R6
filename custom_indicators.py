"""
自定义通达信指标 - 趋势线、买卖点、评分系统
使用MyTT库实现
"""

import numpy as np
import pandas as pd


def HHV(data, n):
    """最高值"""
    result = np.full(len(data), np.nan)
    for i in range(n-1, len(data)):
        result[i] = np.max(data[i-n+1:i+1])
    return result


def LLV(data, n):
    """最低值"""
    result = np.full(len(data), np.nan)
    for i in range(n-1, len(data)):
        result[i] = np.min(data[i-n+1:i+1])
    return result


def EMA(data, n):
    """指数移动平均"""
    result = np.full(len(data), np.nan)
    multiplier = 2 / (n + 1)
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = data[i] * multiplier + result[i-1] * (1 - multiplier)
    return result


def MA(data, n):
    """简单移动平均"""
    result = np.full(len(data), np.nan)
    for i in range(n-1, len(data)):
        result[i] = np.mean(data[i-n+1:i+1])
    return result


def REF(data, n):
    """向前引用"""
    result = np.full(len(data), np.nan)
    result[n:] = data[:-n]
    return result


def CROSS(a, b):
    """上穿"""
    result = np.zeros(len(a), dtype=int)
    for i in range(1, len(a)):
        if a[i-1] <= b[i-1] and a[i] > b[i]:
            result[i] = 1
    return result


def IF(condition, true_val, false_val):
    """条件判断"""
    if isinstance(true_val, (int, float)):
        true_arr = np.full(len(condition), true_val)
    else:
        true_arr = true_val
    if isinstance(false_val, (int, float)):
        false_arr = np.full(len(condition), false_val)
    else:
        false_arr = false_val
    return np.where(condition, true_arr, false_arr)


def COUNT(condition, n):
    """统计满足条件的周期数"""
    result = np.zeros(len(condition))
    for i in range(n-1, len(condition)):
        result[i] = np.sum(condition[i-n+1:i+1])
    return result


def BACKSET(condition, n):
    """向前赋值"""
    result = np.zeros(len(condition))
    for i in range(len(condition)):
        if condition[i]:
            for j in range(max(0, i-n+1), i+1):
                result[j] = 1
    return result


def ABS(data):
    """绝对值"""
    return np.abs(data)


def calculate_trend_lines(df):
    """
    计算趋势线 (CC1, CC2)
    通达信代码:
    CC1:DRAWLINE(H=HHV(H,20),H,L=LLV(L,20),L,0),COLORGREEN,DOTLINE,LINETHICK1;
    CC2:DRAWLINE(L=LLV(L,20),L,H=HHV(H,20),H,0),COLORRED,DOTLINE,LINETHICK1;
    """
    H = df['high'].values
    L = df['low'].values
    n = len(H)
    
    # CC1: 从20日高点画线到20日低点
    cc1 = np.full(n, np.nan)
    hhv20 = HHV(H, 20)
    llv20 = LLV(L, 20)
    
    # 找到20日高点和低点位置
    for i in range(19, n):
        if H[i] == hhv20[i]:
            # 向前找对应的20日低点
            start_idx = i
            for j in range(i, min(i+20, n)):
                if L[j] == llv20[j]:
                    # 画线
                    if j > start_idx:
                        cc1[start_idx:j+1] = np.linspace(H[start_idx], L[j], j-start_idx+1)
                    break
    
    # CC2: 从20日低点画线到20日高点
    cc2 = np.full(n, np.nan)
    for i in range(19, n):
        if L[i] == llv20[i]:
            # 向前找对应的20日高点
            start_idx = i
            for j in range(i, min(i+20, n)):
                if H[j] == hhv20[j]:
                    if j > start_idx:
                        cc2[start_idx:j+1] = np.linspace(L[start_idx], H[j], j-start_idx+1)
                    break
    
    return cc1, cc2


def calculate_pivot_points(df):
    """
    计算局部极值点和画线
    """
    H = df['high'].values
    L = df['low'].values
    C = df['close'].values
    n = len(H)
    
    # KU1, KD1: 3日高低点标记
    ku1 = (H == HHV(H, 3)).astype(int)
    kd1 = (L == LLV(L, 3)).astype(int)
    
    # 计算UL, DL
    ul = np.full(n, np.nan)
    dl = np.full(n, np.nan)
    
    for i in range(2, n):
        if REF(ku1, 2)[i] == 1 and REF(ku1, 1)[i] == 0 and ku1[i] == 0:
            ul[i] = REF(H, 2)[i]
        else:
            # 找最近的满足条件的位置
            for j in range(i-1, max(i-50, 1), -1):
                if ku1[j-2] == 1 and ku1[j-1] == 0 and ku1[j] == 0:
                    ul[i] = H[j-2]
                    break
        
        if REF(kd1, 2)[i] == 1 and REF(kd1, 1)[i] == 0 and kd1[i] == 0:
            dl[i] = REF(L, 2)[i]
        else:
            for j in range(i-1, max(i-50, 1), -1):
                if kd1[j-2] == 1 and kd1[j-1] == 0 and kd1[j] == 0:
                    dl[i] = L[j-2]
                    break
    
    # HV, LV
    hv = (H > ul) & (H > REF(H, 1))
    lv = (L < dl) & (L < REF(L, 1))
    
    return hv, lv, ul, dl


def calculate_macd_signals(df, short=6, long=13, mid=5):
    """
    MACD金叉死叉信号
    """
    C = df['close'].values
    dif = EMA(C, short) - EMA(C, long)
    dea = EMA(dif, mid)
    macd = (dif - dea) * 2
    
    # 金叉死叉
    macd_gold = CROSS(dif, dea)
    macd_dead = CROSS(dea, dif)
    
    return dif, dea, macd, macd_gold, macd_dead


def calculate_ma_signals(df):
    """
    多空均线及资金流判断
    """
    C = df['close'].values
    H = df['high'].values
    L = df['low'].values
    O = df['open'].values
    V = df['volume'].values
    
    ma5 = MA(C, 5)
    ma20 = MA(C, 20)
    
    ttd1 = EMA(C, 3)
    ttd2 = EMA(C, 13)
    
    # 资金流计算
    var1 = V / ((H - L) * 2 - ABS(C - O))
    buy_vol = IF(C > O, var1 * (H - L), IF(C < O, var1 * ((H - O) + (C - L)), V / 2))
    sell_vol = IF(C > O, 0 - var1 * ((H - C) + (O - L)), IF(C < O, 0 - var1 * (H - L), 0 - V / 2))
    
    inflow = MA(buy_vol, 4)
    outflow = MA(0 - sell_vol, 4)
    
    # 根据资金流判断MA20颜色
    ma20_red = IF(inflow > outflow, ma20, np.full(len(C), np.nan))
    ma20_green = IF(inflow < outflow, ma20, np.full(len(C), np.nan))
    
    return ma5, ma20, ma20_red, ma20_green, inflow, outflow


def calculate_pivot_signals(df):
    """
    计算局部高低点及买卖点
    """
    H = df['high'].values
    L = df['low'].values
    C = df['close'].values
    n = len(H)
    
    # 局部高低点预选
    llv5 = LLV(L, 5)
    hhv5 = HHV(H, 5)
    
    local_low_a = BACKSET(LLV(L, 5) < REF(LLV(L, 4), 1), 4)
    local_low_b = BACKSET((local_low_a == 0) & (REF(local_low_a, 1) == 1), 2)
    local_low_c = IF((local_low_b == 1) & (REF(local_low_b, 1) == 0), -1, 0)
    
    local_high_a = BACKSET(HHV(H, 5) > REF(HHV(H, 4), 1), 4)
    local_high_b = BACKSET((local_high_a == 0) & (REF(local_high_a, 1) == 1), 2)
    local_high_c = IF((local_high_b == 1) & (REF(local_high_b, 1) == 0), 1, 0)
    
    return local_low_c, local_high_c


def calculate_buy_score(df, local_low, dif, macd):
    """
    买点评分系统
    """
    C = df['close'].values
    H = df['high'].values
    L = df['low'].values
    V = df['volume'].values
    n = len(C)
    
    # 基础得分
    base_score = 30
    
    # 1. 中枢背离
    center_divergence1 = (L < REF(LLV(L, 10), 1)) & (dif > REF(LLV(dif, 10), 1))
    center_divergence2 = (H > REF(HHV(H, 10), 1)) & (dif < REF(HHV(dif, 10), 1))
    center_divergence = center_divergence1 | center_divergence2
    center_score = IF(center_divergence, 20, 0)
    
    # 2. 笔内部背离
    pen_divergence = (local_low == -1) & (L < REF(LLV(L, 5), 1)) & (dif > REF(LLV(dif, 5), 1))
    pen_score = IF(pen_divergence, 20, 0)
    
    # 3. 多次衰竭
    fatigue_count = COUNT(pen_divergence, 10)
    fatigue_score = fatigue_count * 10
    
    # 4. 最有杀伤力
    most_powerful = (REF(C, 1) < REF(C, 2) * 0.98) & (C > REF(C, 1) * 1.02) & (V > REF(V, 1) * 1.2)
    powerful_score = IF(most_powerful, 15, 0)
    
    # 5. 次有杀伤力
    secondary_powerful = (REF(C, 1) < REF(C, 2)) & (C > REF(C, 1)) & (V > REF(V, 1))
    secondary_score = IF(secondary_powerful, 10, 0)
    
    # 6. 中继分型扣分
    continuation = (ABS(C - REF(C, 1)) / REF(C, 1) < 0.01) & (V < REF(V, 1) * 0.9)
    continuation_penalty = IF(continuation, -10, 0)
    
    total_score = base_score + center_score + pen_score + fatigue_score + powerful_score + secondary_score + continuation_penalty
    
    return total_score


def calculate_sell_score(df, local_high, dif, macd):
    """
    卖点评分系统
    """
    C = df['close'].values
    H = df['high'].values
    L = df['low'].values
    V = df['volume'].values
    
    # 基础得分
    base_score = 30
    
    # 1. 中枢背离
    center_divergence1 = (H > REF(HHV(H, 10), 1)) & (dif < REF(HHV(dif, 10), 1))
    center_divergence2 = (L < REF(LLV(L, 10), 1)) & (dif > REF(LLV(dif, 10), 1))
    center_divergence = center_divergence1 | center_divergence2
    center_score = IF(center_divergence, 20, 0)
    
    # 2. 笔内部背离
    pen_divergence = (local_high == 1) & (H > REF(HHV(H, 5), 1)) & (dif < REF(HHV(dif, 5), 1))
    pen_score = IF(pen_divergence, 20, 0)
    
    # 3. 多次衰竭
    fatigue_count = COUNT(pen_divergence, 10)
    fatigue_score = fatigue_count * 10
    
    # 4. 最有杀伤力
    most_powerful = (REF(C, 1) > REF(C, 2) * 1.02) & (C < REF(C, 1) * 0.98) & (V > REF(V, 1) * 1.2)
    powerful_score = IF(most_powerful, 15, 0)
    
    # 5. 次有杀伤力
    secondary_powerful = (REF(C, 1) > REF(C, 2)) & (C < REF(C, 1)) & (V > REF(V, 1))
    secondary_score = IF(secondary_powerful, 10, 0)
    
    # 6. 中继分型扣分
    continuation = (ABS(C - REF(C, 1)) / REF(C, 1) < 0.01) & (V < REF(V, 1) * 0.9)
    continuation_penalty = IF(continuation, -10, 0)
    
    total_score = base_score + center_score + pen_score + fatigue_score + powerful_score + secondary_score + continuation_penalty
    
    return total_score


def calculate_all_indicators(df):
    """
    计算所有指标
    """
    results = {}
    
    # 趋势线
    cc1, cc2 = calculate_trend_lines(df)
    results['cc1'] = cc1
    results['cc2'] = cc2
    
    # MACD
    dif, dea, macd, macd_gold, macd_dead = calculate_macd_signals(df)
    results['dif'] = dif
    results['dea'] = dea
    results['macd'] = macd
    results['macd_gold'] = macd_gold
    results['macd_dead'] = macd_dead
    
    # 均线
    ma5, ma20, ma20_red, ma20_green, inflow, outflow = calculate_ma_signals(df)
    results['ma5'] = ma5
    results['ma20'] = ma20
    results['ma20_red'] = ma20_red
    results['ma20_green'] = ma20_green
    
    # 局部高低点
    local_low, local_high = calculate_pivot_signals(df)
    results['local_low'] = local_low
    results['local_high'] = local_high
    
    # 买卖点得分
    buy_score = calculate_buy_score(df, local_low, dif, macd)
    sell_score = calculate_sell_score(df, local_high, dif, macd)
    results['buy_score'] = buy_score
    results['sell_score'] = sell_score
    
    # 买卖信号
    results['buy_signal'] = (local_low == -1) & (buy_score >= 40)
    results['sell_signal'] = (local_high == 1) & (sell_score >= 40)
    
    return results


if __name__ == '__main__':
    print("自定义指标模块")
    print("包含：趋势线、MACD、均线、买卖点评分系统")
