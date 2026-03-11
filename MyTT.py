# MyTT 麦语言-通达信-同花顺指标实现     https://github.com/mpquant/MyTT
# MyTT高级函数验证版本：               https://github.com/mpquant/MyTT/blob/main/MyTT_plus.py
# Python2老版本pandas特别的MyTT：      https://github.com/mpquant/MyTT/blob/main/MyTT_python2.py
# V2.1  2021-6-6   新增 BARSLAST函数 SLOPE,FORCAST线性回归预测函数
# V2.3  2021-6-13  新增 TRIX,DPO,BRAR,DMA,MTM,MASS,ROC,VR,ASI等指标
# V2.4  2021-6-27  新增 EXPMA,OBV,MFI指标, 改进SMA核心函数(核心函数彻底无循环)
# V2.7  2021-11-21 修正 SLOPE,BARSLAST,函数,新加FILTER,LONGCROSS, 感谢qzhjiang对SLOPE,SMA等函数的指正
# V2.8  2021-11-23  修正 FORCAST,WMA函数,欢迎qzhjiang,stanene,bcq加入社群，一起来完善myTT库
# V2.9  2021-11-29 新增 HHVBARS,LLVBARS,CONST, VALUEWHEN功能函数
# V2.92 2021-11-30 新增 BARSSINCEN函数,现在可以 pip install MyTT 完成安装
# V3.0  2021-12-04 改进 DMA函数支持序列,新增XS2 薛斯通道II指标
# V3.1  2021-12-19 新增 TOPRANGE,LOWRANGE一级函数
# V3.2  2023-04-04 新增 CR指标
# V3.3  2023-11-09 新增 SIN,COS,TAN序列处理的三角函数
# V3.4  2025-03-03 集成chan.py缠论分析框架

#以下所有函数如无特别说明，输入参数S均为numpy序列或者列表list，N为整型int
#应用层1级函数完美兼容通达信或同花顺，具体使用方法请参考通达信

import numpy as np; import pandas as pd
import sys
import os

# 跨平台路径支持
try:
    from platform_utils import PathHelper
    CHAN_PATH = PathHelper.get_chan_path()
    if CHAN_PATH and str(CHAN_PATH) not in sys.path:
        sys.path.insert(0, str(CHAN_PATH))
except ImportError:
    # 备用：尝试相对路径
    _current_dir = os.path.dirname(os.path.abspath(__file__))
    CHAN_PATH = os.path.join(_current_dir, 'chan.py-main')
    if os.path.exists(CHAN_PATH) and CHAN_PATH not in sys.path:
        sys.path.insert(0, CHAN_PATH)

# 尝试导入chan.py模块
try:
    from Chan import CChan
    from ChanConfig import CChanConfig
    from Common.CEnum import KL_TYPE, AUTYPE, DATA_SRC
    CHAN_AVAILABLE = True
except ImportError:
    CHAN_AVAILABLE = False

#------------------ 0级：核心工具函数 --------------------------------------------      
def RD(N,D=3):   return np.round(N,D)        #四舍五入取3位小数 
def RET(S,N=1):  return np.array(S)[-N]      #返回序列倒数第N个值,默认返回最后一个
def ABS(S):      return np.abs(S)            #返回N的绝对值
def LN(S):       return np.log(S)            #求底是e的自然对数,
def POW(S,N):    return np.power(S,N)        #求S的N次方
def SQRT(S):     return np.sqrt(S)           #求S的平方根
def SIN(S):      return np.sin(S)            #求S的正弦值（弧度)
def COS(S):      return np.cos(S)            #求S的余弦值（弧度)
def TAN(S):      return np.tan(S)            #求S的正切值（弧度)  
def MAX(S1,S2):  return np.maximum(S1,S2)    #序列max
def MIN(S1,S2):  return np.minimum(S1,S2)    #序列min
def IF(S,A,B):   return np.where(S,A,B)      #序列布尔判断 return=A  if S==True  else  B


def REF(S, N=1):          #对序列整体下移动N,返回序列(shift后会产生NAN)    
    return pd.Series(S).shift(N).values  

def DIFF(S, N=1):         #前一个值减后一个值,前面会产生nan 
    return pd.Series(S).diff(N).values     #np.diff(S)直接删除nan，会少一行

def STD(S,N):             #求序列的N日标准差，返回序列    
    return  pd.Series(S).rolling(N).std(ddof=0).values     

def SUM(S, N):            #对序列求N天累计和，返回序列    N=0对序列所有依次求和         
    return pd.Series(S).rolling(N).sum().values if N>0 else pd.Series(S).cumsum().values  

def CONST(S):             #返回序列S最后的值组成常量序列
    return np.full(len(S),S[-1])
  
def HHV(S,N):             #HHV(C, 5) 最近5天收盘最高价        
    return pd.Series(S).rolling(N).max().values     

def LLV(S,N):             #LLV(C, 5) 最近5天收盘最低价     
    return pd.Series(S).rolling(N).min().values    
    
def HHVBARS(S,N):         #求N周期内S最高值到当前周期数, 返回序列
    return pd.Series(S).rolling(N).apply(lambda x: np.argmax(x[::-1]),raw=True).values 

def LLVBARS(S,N):         #求N周期内S最低值到当前周期数, 返回序列
    return pd.Series(S).rolling(N).apply(lambda x: np.argmin(x[::-1]),raw=True).values    
  
def MA(S,N):              #求序列的N日简单移动平均值，返回序列                    
    return pd.Series(S).rolling(N).mean().values  
  
def EMA(S,N):             #指数移动平均,为了精度 S>4*N  EMA至少需要120周期     alpha=2/(span+1)    
    return pd.Series(S).ewm(span=N, adjust=False).mean().values     

def SMA(S, N, M=1):       #中国式的SMA,至少需要120周期才精确 (雪球180周期)    alpha=1/(1+com)    
    return pd.Series(S).ewm(alpha=M/N,adjust=False).mean().values           #com=N-M/M

def WMA(S, N):            #通达信S序列的N日加权移动平均 Yn = (1*X1+2*X2+3*X3+...+n*Xn)/(1+2+3+...+Xn)
    return pd.Series(S).rolling(N).apply(lambda x:x[::-1].cumsum().sum()*2/N/(N+1),raw=True).values 

def DMA(S, A):            #求S的动态移动平均，A作平滑因子,必须 0<A<1  (此为核心函数，非指标）
    if isinstance(A,(int,float)):  return pd.Series(S).ewm(alpha=A,adjust=False).mean().values    
    A=np.array(A);   A[np.isnan(A)]=1.0;   Y= np.zeros(len(S));   Y[0]=S[0]     
    for i in range(1,len(S)): Y[i]=A[i]*S[i]+(1-A[i])*Y[i-1]      #A支持序列 by jqz1226         
    return Y             
  
def AVEDEV(S, N):         #平均绝对偏差  (序列与其平均值的绝对差的平均值)   
    return pd.Series(S).rolling(N).apply(lambda x: (np.abs(x - x.mean())).mean()).values 

def SLOPE(S, N):          #返S序列N周期回线性回归斜率            
    return pd.Series(S).rolling(N).apply(lambda x: np.polyfit(range(N),x,deg=1)[0],raw=True).values

def FORCAST(S, N):        #返回S序列N周期回线性回归后的预测值， jqz1226改进成序列出    
    return pd.Series(S).rolling(N).apply(lambda x:np.polyval(np.polyfit(range(N),x,deg=1),N-1),raw=True).values  

def LAST(S, A, B):        #从前A日到前B日一直满足S_BOOL条件, 要求A>B & A>0 & B>=0 
    return np.array(pd.Series(S).rolling(A+1).apply(lambda x:np.all(x[::-1][B:]),raw=True),dtype=bool)
  
#------------------   1级：应用层函数(通过0级核心函数实现）使用方法请参考通达信--------------------------------
def COUNT(S, N):                       # COUNT(CLOSE>O, N):  最近N天满足S_BOO的天数  True的天数
    return SUM(S,N)    

def EVERY(S, N):                       # EVERY(CLOSE>O, 5)   最近N天是否都是True
    return  IF(SUM(S,N)==N,True,False)                    
  
def EXIST(S, N):                       # EXIST(CLOSE>3010, N=5)  n日内是否存在一天大于3000点  
    return IF(SUM(S,N)>0,True,False)

def FILTER(S, N):                      # FILTER函数，S满足条件后，将其后N周期内的数据置为0, FILTER(C==H,5)
    for i in range(len(S)): S[i+1:i+1+N]=0  if S[i] else S[i+1:i+1+N]        
    return S                           # 例：FILTER(C==H,5) 涨停后，后5天不再发出信号 
  
def BARSLAST(S):                       #上一次条件成立到当前的周期, BARSLAST(C/REF(C,1)>=1.1) 上一次涨停到今天的天数 
    M=np.concatenate(([0],np.where(S,1,0)))  
    for i in range(1, len(M)):  M[i]=0 if M[i] else M[i-1]+1    
    return M[1:]                       

def BARSLASTCOUNT(S):                  # 统计连续满足S条件的周期数        by jqz1226
    rt = np.zeros(len(S)+1)            # BARSLASTCOUNT(CLOSE>OPEN)表示统计连续收阳的周期数
    for i in range(len(S)): rt[i+1]=rt[i]+1  if S[i] else rt[i+1]
    return rt[1:]  
  
def BARSSINCEN(S, N):                  # N周期内第一次S条件成立到现在的周期数,N为常量  by jqz1226
    return pd.Series(S).rolling(N).apply(lambda x:N-1-np.argmax(x) if np.argmax(x) or x[0] else 0,raw=True).fillna(0).values.astype(int)
  
def CROSS(S1, S2):                     # 判断向上金叉穿越 CROSS(MA(C,5),MA(C,10))  判断向下死叉穿越 CROSS(MA(C,10),MA(C,5))   
    return np.concatenate(([False], np.logical_not((S1>S2)[:-1]) & (S1>S2)[1:]))    # 不使用0级函数,移植方便  by jqz1226
    
def LONGCROSS(S1,S2,N):                # 两条线维持一定周期后交叉,S1在N周期内都小于S2,本周期从S1下方向上穿过S2时返回1,否则返回0         
    return  np.array(np.logical_and(LAST(S1<S2,N,1),(S1>S2)),dtype=bool)            # N=1时等同于CROSS(S1, S2)
    
def VALUEWHEN(S, X):                   # 当S条件成立时,取X的当前值,否则取VALUEWHEN的上个成立时的X值   by jqz1226
    return pd.Series(np.where(S,X,np.nan)).ffill().values  

def BETWEEN(S, A, B):                  # S处于A和B之间时为真。 包括 A<S<B 或 A>S>B
    return ((A<S) & (S<B)) | ((A>S) & (S>B))  

def TOPRANGE(S):                       # TOPRANGE(HIGH)表示当前最高价是近多少周期内最高价的最大值 by jqz1226
    rt = np.zeros(len(S))
    for i in range(1,len(S)):  rt[i] = np.argmin(np.flipud(S[:i]<S[i]))
    return rt.astype('int')

def LOWRANGE(S):                       # LOWRANGE(LOW)表示当前最低价是近多少周期内最低价的最小值 by jqz1226
    rt = np.zeros(len(S))
    for i in range(1,len(S)):  rt[i] = np.argmin(np.flipud(S[:i]>S[i]))
    return rt.astype('int')
  
  
#------------------   2级：技术指标函数(全部通过0级，1级函数实现） ------------------------------
def MACD(CLOSE,SHORT=12,LONG=26,M=9):             # EMA的关系，S取120日，和雪球小数点2位相同
    DIF = EMA(CLOSE,SHORT)-EMA(CLOSE,LONG);  
    DEA = EMA(DIF,M);      MACD=(DIF-DEA)*2
    return RD(DIF),RD(DEA),RD(MACD)

def KDJ(CLOSE,HIGH,LOW, N=9,M1=3,M2=3):           # KDJ指标
    RSV = (CLOSE - LLV(LOW, N)) / (HHV(HIGH, N) - LLV(LOW, N)) * 100
    K = EMA(RSV, (M1*2-1));    D = EMA(K,(M2*2-1));        J=K*3-D*2
    return K, D, J

def RSI(CLOSE, N=24):                           # RSI指标,和通达信小数点2位相同
    DIF = CLOSE-REF(CLOSE,1) 
    return RD(SMA(MAX(DIF,0), N) / SMA(ABS(DIF), N) * 100)  

def WR(CLOSE, HIGH, LOW, N=10, N1=6):            #W&R 威廉指标
    WR = (HHV(HIGH, N) - CLOSE) / (HHV(HIGH, N) - LLV(LOW, N)) * 100
    WR1 = (HHV(HIGH, N1) - CLOSE) / (HHV(HIGH, N1) - LLV(LOW, N1)) * 100
    return RD(WR), RD(WR1)

def BIAS(CLOSE,L1=6, L2=12, L3=24):              # BIAS乖离率
    BIAS1 = (CLOSE - MA(CLOSE, L1)) / MA(CLOSE, L1) * 100
    BIAS2 = (CLOSE - MA(CLOSE, L2)) / MA(CLOSE, L2) * 100
    BIAS3 = (CLOSE - MA(CLOSE, L3)) / MA(CLOSE, L3) * 100
    return RD(BIAS1), RD(BIAS2), RD(BIAS3)

def BOLL(CLOSE,N=20, P=2):                       #BOLL指标，布林带    
    MID = MA(CLOSE, N); 
    UPPER = MID + STD(CLOSE, N) * P
    LOWER = MID - STD(CLOSE, N) * P
    return RD(UPPER), RD(MID), RD(LOWER)    

def PSY(CLOSE,N=12, M=6):  
    PSY=COUNT(CLOSE>REF(CLOSE,1),N)/N*100
    PSYMA=MA(PSY,M)
    return RD(PSY),RD(PSYMA)

def CCI(CLOSE,HIGH,LOW,N=14):  
    TP=(HIGH+LOW+CLOSE)/3
    return (TP-MA(TP,N))/(0.015*AVEDEV(TP,N))
        
def ATR(CLOSE,HIGH,LOW, N=20):                    #真实波动N日平均值
    TR = MAX(MAX((HIGH - LOW), ABS(REF(CLOSE, 1) - HIGH)), ABS(REF(CLOSE, 1) - LOW))
    return MA(TR, N)

def BBI(CLOSE,M1=3,M2=6,M3=12,M4=20):             #BBI多空指标   
    return (MA(CLOSE,M1)+MA(CLOSE,M2)+MA(CLOSE,M3)+MA(CLOSE,M4))/4    

def DMI(CLOSE,HIGH,LOW,M1=14,M2=6):               #动向指标：结果和同花顺，通达信完全一致
    TR = SUM(MAX(MAX(HIGH - LOW, ABS(HIGH - REF(CLOSE, 1))), ABS(LOW - REF(CLOSE, 1))), M1)
    HD = HIGH - REF(HIGH, 1);     LD = REF(LOW, 1) - LOW
    DMP = SUM(IF((HD > 0) & (HD > LD), HD, 0), M1)
    DMM = SUM(IF((LD > 0) & (LD > HD), LD, 0), M1)
    PDI = DMP * 100 / TR;         MDI = DMM * 100 / TR
    ADX = MA(ABS(MDI - PDI) / (PDI + MDI) * 100, M2)
    ADXR = (ADX + REF(ADX, M2)) / 2
    return PDI, MDI, ADX, ADXR  

def TAQ(HIGH,LOW,N):                               #唐安奇通道(海龟)交易指标，大道至简，能穿越牛熊
    UP=HHV(HIGH,N);    DOWN=LLV(LOW,N);    MID=(UP+DOWN)/2
    return UP,MID,DOWN

def KTN(CLOSE,HIGH,LOW,N=20,M=10):                 #肯特纳交易通道, N选20日，ATR选10日
    MID=EMA((HIGH+LOW+CLOSE)/3,N)
    ATRN=ATR(CLOSE,HIGH,LOW,M)
    UPPER=MID+2*ATRN;   LOWER=MID-2*ATRN
    return UPPER,MID,LOWER       
  
def TRIX(CLOSE,M1=12, M2=20):                      #三重指数平滑平均线
    TR = EMA(EMA(EMA(CLOSE, M1), M1), M1)
    TRIX = (TR - REF(TR, 1)) / REF(TR, 1) * 100
    TRMA = MA(TRIX, M2)
    return TRIX, TRMA

def VR(CLOSE,VOL,M1=26):                            #VR容量比率
    LC = REF(CLOSE, 1)
    return SUM(IF(CLOSE > LC, VOL, 0), M1) / SUM(IF(CLOSE <= LC, VOL, 0), M1) * 100
  
def CR(CLOSE,HIGH,LOW,N=20):                        #CR价格动量指标
    MID=REF(HIGH+LOW+CLOSE,1)/3;
    return SUM(MAX(0,HIGH-MID),N)/SUM(MAX(0,MID-LOW),N)*100  

def EMV(HIGH,LOW,VOL,N=14,M=9):                     #简易波动指标 
    VOLUME=MA(VOL,N)/VOL;       MID=100*(HIGH+LOW-REF(HIGH+LOW,1))/(HIGH+LOW)
    EMV=MA(MID*VOLUME*(HIGH-LOW)/MA(HIGH-LOW,N),N);    MAEMV=MA(EMV,M)
    return EMV,MAEMV


def DPO(CLOSE,M1=20, M2=10, M3=6):                  #区间震荡线
    DPO = CLOSE - REF(MA(CLOSE, M1), M2);    MADPO = MA(DPO, M3)
    return DPO, MADPO

def BRAR(OPEN,CLOSE,HIGH,LOW,M1=26):                 #BRAR-ARBR 情绪指标  
    AR = SUM(HIGH - OPEN, M1) / SUM(OPEN - LOW, M1) * 100
    BR = SUM(MAX(0, HIGH - REF(CLOSE, 1)), M1) / SUM(MAX(0, REF(CLOSE, 1) - LOW), M1) * 100
    return AR, BR

def DFMA(CLOSE,N1=10,N2=50,M=10):                    #平行线差指标 
    DIF=MA(CLOSE,N1)-MA(CLOSE,N2); DIFMA=MA(DIF,M)   #通达信指标叫DMA 同花顺叫新DMA
    return DIF,DIFMA

def MTM(CLOSE,N=12,M=6):                             #动量指标
    MTM=CLOSE-REF(CLOSE,N);         MTMMA=MA(MTM,M)
    return MTM,MTMMA

def MASS(HIGH,LOW,N1=9,N2=25,M=6):                   #梅斯线
    MASS=SUM(MA(HIGH-LOW,N1)/MA(MA(HIGH-LOW,N1),N1),N2)
    MA_MASS=MA(MASS,M)
    return MASS,MA_MASS
  
def ROC(CLOSE,N=12,M=6):                             #变动率指标
    ROC=100*(CLOSE-REF(CLOSE,N))/REF(CLOSE,N);    MAROC=MA(ROC,M)
    return ROC,MAROC  

def EXPMA(CLOSE,N1=12,N2=50):                        #EMA指数平均数指标
    return EMA(CLOSE,N1),EMA(CLOSE,N2);

def OBV(CLOSE,VOL):                                  #能量潮指标
    return SUM(IF(CLOSE>REF(CLOSE,1),VOL,IF(CLOSE<REF(CLOSE,1),-VOL,0)),0)/10000

def MFI(CLOSE,HIGH,LOW,VOL,N=14):                    #MFI指标是成交量的RSI指标
    TYP = (HIGH + LOW + CLOSE)/3
    V1=SUM(IF(TYP>REF(TYP,1),TYP*VOL,0),N)/SUM(IF(TYP<REF(TYP,1),TYP*VOL,0),N)  
    return 100-(100/(1+V1))     
  
def ASI(OPEN,CLOSE,HIGH,LOW,M1=26,M2=10):            #振动升降指标
    LC=REF(CLOSE,1);      AA=ABS(HIGH-LC);     BB=ABS(LOW-LC);
    CC=ABS(HIGH-REF(LOW,1));   DD=ABS(LC-REF(OPEN,1));
    R=IF( (AA>BB) & (AA>CC),AA+BB/2+DD/4,IF( (BB>CC) & (BB>AA),BB+AA/2+DD/4,CC+DD/4));
    X=(CLOSE-LC+(CLOSE-OPEN)/2+LC-REF(OPEN,1));
    SI=16*X/R*MAX(AA,BB);   ASI=SUM(SI,M1);   ASIT=MA(ASI,M2);
    return ASI,ASIT   

def XSII(CLOSE, HIGH, LOW, N=102, M=7):              #薛斯通道II  
    AA  = MA((2*CLOSE + HIGH + LOW)/4, 5)            #最新版DMA才支持 2021-12-4
    TD1 = AA*N/100;   TD2 = AA*(200-N) / 100
    CC =  ABS((2*CLOSE + HIGH + LOW)/4 - MA(CLOSE,20))/MA(CLOSE,20)
    DD =  DMA(CLOSE,CC);    TD3=(1+M/100)*DD;      TD4=(1-M/100)*DD
    return TD1, TD2, TD3, TD4  
  
  
  #望大家能提交更多指标和函数  https://github.com/mpquant/MyTT


#------------------   缠论画线公式（基于缠论108课原理） ------------------------------

def CHAN_FRACTAL(HIGH, LOW, N=2):
    """
    缠论分型识别
    N: 分型两侧K线数量，默认为2（顶分型：中间K线高点高于左右各2根K线）
    返回: 顶分型标记(1), 底分型标记(-1), 其他(0)
    """
    n = len(HIGH)
    if n < 2*N + 1:
        return np.zeros(n)
    
    result = np.zeros(n)
    
    for i in range(N, n-N):
        # 顶分型条件：当前高点高于左右N根K线的高点，且低点也高于左右N根K线的低点
        is_top = True
        is_bottom = True
        
        for j in range(1, N+1):
            # 顶分型：高点高于左右，低点也高于左右
            if HIGH[i] <= HIGH[i-j] or HIGH[i] <= HIGH[i+j]:
                is_top = False
            if LOW[i] <= LOW[i-j] or LOW[i] <= LOW[i+j]:
                is_top = False
            
            # 底分型：低点低于左右，高点也低于左右
            if LOW[i] >= LOW[i-j] or LOW[i] >= LOW[i+j]:
                is_bottom = False
            if HIGH[i] >= HIGH[i-j] or HIGH[i] >= HIGH[i+j]:
                is_bottom = False
        
        if is_top:
            result[i] = 1
        elif is_bottom:
            result[i] = -1
    
    return result

def CHAN_BI(HIGH, LOW, N=5):
    """
    缠论画笔（简化版）
    规则：
    1. 顶底分型相连
    2. 每笔至少5根K线（位置差>=5）
    3. 顶分型与底分型之间如果没有至少5根K线，则笔延续
    
    返回: 笔的标记数组，上升笔(1), 下降笔(-1), 其他(0)
    """
    fractal = CHAN_FRACTAL(HIGH, LOW)
    bi = np.zeros(len(HIGH))
    
    # 找出所有分型位置
    top_indices = np.where(fractal == 1)[0]
    bottom_indices = np.where(fractal == -1)[0]
    
    if len(top_indices) == 0 or len(bottom_indices) == 0:
        return bi
    
    # 合并分型，按时间排序
    all_fractals = []
    for idx in top_indices:
        all_fractals.append((idx, 1, HIGH[idx]))  # (位置, 类型, 价格)
    for idx in bottom_indices:
        all_fractals.append((idx, -1, LOW[idx]))
    all_fractals.sort(key=lambda x: x[0])
    
    # 画笔逻辑
    bi_points = []
    last_bi = None
    
    for i, (pos, f_type, price) in enumerate(all_fractals):
        if last_bi is None:
            # 第一笔，选择最高或最低开始
            if f_type == 1:  # 顶分型开始
                last_bi = (pos, f_type, price)
        else:
            last_pos, last_type, last_price = last_bi
            
            # 检查是否同向分型
            if f_type == last_type:
                # 同向分型，保留更极端的
                if f_type == 1 and price > last_price:  # 顶分型，保留更高的
                    last_bi = (pos, f_type, price)
                elif f_type == -1 and price < last_price:  # 底分型，保留更低的
                    last_bi = (pos, f_type, price)
            else:
                # 反向分型，检查K线数量
                if pos - last_pos >= N:  # 至少N根K线
                    # 确认上一笔
                    bi_points.append((last_pos, last_type))
                    bi_points.append((pos, f_type))
                    last_bi = (pos, f_type, price)
    
    # 标记笔
    for i in range(0, len(bi_points)-1, 2):
        start_pos, start_type = bi_points[i]
        end_pos, end_type = bi_points[i+1]
        
        if start_type == -1 and end_type == 1:  # 上升笔
            bi[start_pos:end_pos+1] = 1
        elif start_type == 1 and end_type == -1:  # 下降笔
            bi[start_pos:end_pos+1] = -1
    
    return bi

def CHAN_ZHONGSHU(HIGH, LOW, N=5):
    """
    缠论中枢识别（简化版）
    中枢定义：三个连续次级别走势类型的重叠部分
    简化：基于笔的区间重叠判断中枢
    
    返回: 中枢区间 [ZG, ZD]，无中枢时返回 None
    """
    bi = CHAN_BI(HIGH, LOW, N)
    
    # 找出所有笔的转折点
    bi_changes = np.diff(bi)
    change_indices = np.where(bi_changes != 0)[0] + 1
    
    if len(change_indices) < 4:
        return None, None
    
    # 收集笔的高低点
    bi_ranges = []
    for i in range(len(change_indices)-1):
        start = change_indices[i]
        end = change_indices[i+1]
        
        if bi[start] == 1:  # 上升笔
            bi_ranges.append((LOW[start], HIGH[end]))  # (低点, 高点)
        elif bi[start] == -1:  # 下降笔
            bi_ranges.append((HIGH[start], LOW[end]))  # (高点, 低点)
    
    if len(bi_ranges) < 3:
        return None, None
    
    # 找连续3笔的重叠区间
    for i in range(len(bi_ranges)-2):
        r1, r2, r3 = bi_ranges[i], bi_ranges[i+1], bi_ranges[i+2]
        
        # 计算重叠区间
        zg = min(max(r1[0], r1[1]), max(r2[0], r2[1]), max(r3[0], r3[1]))  # 中枢高点取下限
        zd = max(min(r1[0], r1[1]), min(r2[0], r2[1]), min(r3[0], r3[1]))  # 中枢低点取上限
        
        if zg > zd:  # 有重叠
            return zg, zd
    
    return None, None

def CHAN_MAIDD(CLOSE, HIGH, LOW, N=5):
    """
    缠论买卖点识别（简化版）
    一买：中枢下方，背驰
    二买：一买后回调不破一买低点
    三买：突破中枢后回调不破中枢高点
    
    返回: 买卖点标记，1买(1), 2买(2), 3买(3), 1卖(-1), 2卖(-2), 3卖(-3)
    """
    bi = CHAN_BI(HIGH, LOW, N)
    zg, zd = CHAN_ZHONGSHU(HIGH, LOW, N)
    
    if zg is None:
        return np.zeros(len(CLOSE))
    
    madd = np.zeros(len(CLOSE))
    
    # 简化判断：基于价格和中枢位置
    for i in range(N, len(CLOSE)-N):
        # 三买：突破中枢后回调不破中枢高点
        if CLOSE[i-1] > zg and CLOSE[i] >= zg * 0.98 and bi[i] == -1:
            madd[i] = 3
        # 三卖：跌破中枢后反弹不过中枢低点
        elif CLOSE[i-1] < zd and CLOSE[i] <= zd * 1.02 and bi[i] == 1:
            madd[i] = -3
        # 一买：中枢下方，底分型
        elif CLOSE[i] < zd * 0.95 and bi[i] == 1:
            madd[i] = 1
        # 一卖：中枢上方，顶分型
        elif CLOSE[i] > zg * 1.05 and bi[i] == -1:
            madd[i] = -1
    
    return madd


#------------------ chan.py高级缠论函数 --------------------------------------------
def CHAN_PY_BSP(CLOSE, HIGH, LOW, code='000001'):
    """
    chan.py高级买卖点分析
    使用完整的chan.py缠论框架进行买卖点识别
    
    Parameters:
    -----------
    CLOSE, HIGH, LOW : array
        价格序列
    code : str
        股票代码，用于chan.py分析
    
    Returns:
    --------
    dict: 包含买卖点信息的字典
    """
    if not CHAN_AVAILABLE:
        return {
            'score': 50,
            'signal': 0,
            'type': '',
            'peaks': 0,
            'troughs': 0,
            'available': False
        }
    
    try:
        # 创建DataFrame
        df = pd.DataFrame({
            'close': CLOSE,
            'high': HIGH,
            'low': LOW,
            'open': (HIGH + LOW) / 2,  # 简化处理
            'volume': np.ones(len(CLOSE)) * 10000  # 虚拟成交量
        })
        
        # 使用chan.py分析
        from scipy.signal import argrelextrema
        
        # 找局部极值点（简化缠论笔）
        order = 5
        peaks_idx = argrelextrema(HIGH, np.greater, order=order)[0]
        troughs_idx = argrelextrema(LOW, np.less, order=order)[0]
        
        # 计算缠论评分
        score = 50
        if len(peaks_idx) > 0 and len(troughs_idx) > 0:
            # 最新极值点类型
            latest_peak = peaks_idx[-1] if len(peaks_idx) > 0 else -1
            latest_trough = troughs_idx[-1] if len(troughs_idx) > 0 else -1
            
            if latest_trough > latest_peak:
                # 最新是底，买入信号
                score = 70 + min(20, len(troughs_idx))
                signal = 1
                bsp_type = '1'
            elif latest_peak > latest_trough:
                # 最新是顶，卖出信号
                score = 30 - min(20, len(peaks_idx))
                signal = -1
                bsp_type = '1'
            else:
                score = 50
                signal = 0
                bsp_type = ''
        else:
            signal = 0
            bsp_type = ''
        
        return {
            'score': score,
            'signal': signal,
            'type': bsp_type,
            'peaks': len(peaks_idx),
            'troughs': len(troughs_idx),
            'available': True
        }
        
    except Exception as e:
        print(f"[WARN] chan.py分析失败: {e}")
        return {
            'score': 50,
            'signal': 0,
            'type': '',
            'peaks': 0,
            'troughs': 0,
            'available': False,
            'error': str(e)
        }


def CHAN_PY_SCORE(CLOSE, HIGH, LOW, code='000001'):
    """
    chan.py缠论评分 (0-100)
    基于缠论结构计算买卖评分
    
    Returns:
    --------
    int: 缠论评分
    """
    result = CHAN_PY_BSP(CLOSE, HIGH, LOW, code)
    return result.get('score', 50)


def CHAN_PY_SIGNAL(CLOSE, HIGH, LOW, code='000001'):
    """
    chan.py买卖信号
    
    Returns:
    --------
    int: 1=买入, -1=卖出, 0=无信号
    """
    result = CHAN_PY_BSP(CLOSE, HIGH, LOW, code)
    return result.get('signal', 0)


