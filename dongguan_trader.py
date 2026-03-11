"""
东莞证券实盘交易模块
使用easytrader对接东莞证券掌证宝客户端
支持手动下单和自动策略交易
"""

import easytrader
import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class RealTrade:
    """实盘交易记录"""
    id: str
    datetime: str
    symbol: str
    action: str  # 'buy' or 'sell'
    price: float
    shares: int
    amount: float
    status: str  # 'pending', 'filled', 'cancelled', 'failed'
    order_id: Optional[str] = None
    message: str = ""


class DongguanTrader:
    """
    东莞证券实盘交易接口
    
    功能：
    1. 连接东莞证券掌证宝客户端
    2. 支持买入/卖出/撤单
    3. 查询账户资金和持仓
    4. 自动交易对接
    """
    
    def __init__(self):
        self.user = None
        self.connected = False
        self.account_info: Dict = {}
        self.positions: List[Dict] = []
        self.trades: List[RealTrade] = []
        self.trade_mode = 'paper'  # 'paper' 或 'real'
        
    def connect(self, exe_path: Optional[str] = None) -> bool:
        """
        连接东莞证券掌证宝
        
        Args:
            exe_path: 掌证宝客户端路径，None则自动查找
        """
        try:
            # 使用同花顺客户端模式（东莞证券支持同花顺版）
            self.user = easytrader.use('ths')
            
            if exe_path:
                self.user.connect(exe_path)
            else:
                # 自动连接已启动的客户端
                self.user.connect()
            
            self.connected = True
            self.trade_mode = 'real'
            print("东莞证券实盘连接成功")
            return True
            
        except Exception as e:
            print(f"连接失败: {e}")
            print("请确保东莞证券掌证宝客户端已登录")
            self.connected = False
            return False
    
    def disconnect(self):
        """断开连接"""
        self.connected = False
        self.user = None
        print("已断开连接")
    
    def get_account_info(self) -> Dict:
        """获取账户信息"""
        if not self.connected or not self.user:
            return {'error': '未连接'}
        
        try:
            balance = self.user.balance
            self.account_info = {
                '资金余额': balance.get('资金余额', 0),
                '可用资金': balance.get('可用金额', 0),
                '冻结资金': balance.get('冻结金额', 0),
                '总资产': balance.get('总资产', 0),
                '市值': balance.get('股票市值', 0),
                '更新时间': datetime.now().strftime('%H:%M:%S')
            }
            return self.account_info
        except Exception as e:
            return {'error': str(e)}
    
    def get_positions(self) -> List[Dict]:
        """获取持仓列表"""
        if not self.connected or not self.user:
            return []
        
        try:
            positions = self.user.position
            self.positions = []
            for p in positions:
                pos = {
                    '代码': p.get('证券代码', ''),
                    '名称': p.get('证券名称', ''),
                    '股数': p.get('股票余额', 0),
                    '可用': p.get('可用余额', 0),
                    '成本价': p.get('成本价', 0),
                    '现价': p.get('市价', 0),
                    '市值': p.get('市值', 0),
                    '盈亏': p.get('盈亏', 0),
                    '盈亏率': p.get('盈亏比例(%)', 0)
                }
                self.positions.append(pos)
            return self.positions
        except Exception as e:
            print(f"获取持仓失败: {e}")
            return []
    
    def buy(self, symbol: str, price: float, shares: int, 
            order_type: str = 'limit') -> Tuple[bool, str]:
        """
        买入股票
        
        Args:
            symbol: 股票代码
            price: 买入价格
            shares: 买入股数（100的倍数）
            order_type: 'limit'限价单 / 'market'市价单
        
        Returns:
            (是否成功, 订单ID或错误信息)
        """
        if not self.connected:
            return False, "未连接交易客户端"
        
        # 检查股数
        if shares % 100 != 0:
            return False, "买入股数必须是100的整数倍"
        
        try:
            # 格式化股票代码（港股不做zfill）
            symbol = str(symbol).strip()
            if symbol.isdigit() and len(symbol) > 5:
                symbol = symbol.zfill(6)
            
            # 执行买入
            result = self.user.buy(symbol, price, shares)
            
            # 记录交易
            trade = RealTrade(
                id=f"T{int(time.time() * 1000)}",
                datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                symbol=symbol,
                action='buy',
                price=price,
                shares=shares,
                amount=price * shares,
                status='filled' if result else 'failed',
                order_id=str(result) if result else None,
                message='买入成功' if result else '买入失败'
            )
            self.trades.append(trade)
            
            if result:
                print(f"买入委托成功: {symbol} {shares}股 @ {price}")
                return True, str(result)
            else:
                return False, "买入失败"
                
        except Exception as e:
            error_msg = f"买入异常: {e}"
            print(error_msg)
            return False, error_msg
    
    def sell(self, symbol: str, price: float, shares: int,
             order_type: str = 'limit') -> Tuple[bool, str]:
        """
        卖出股票
        
        Args:
            symbol: 股票代码
            price: 卖出价格
            shares: 卖出股数
            order_type: 'limit'限价单 / 'market'市价单
        """
        if not self.connected:
            return False, "未连接交易客户端"
        
        try:
            # 格式化股票代码（港股不做zfill）
            symbol = str(symbol).strip()
            if symbol.isdigit() and len(symbol) > 5:
                symbol = symbol.zfill(6)
            
            # 执行卖出
            result = self.user.sell(symbol, price, shares)
            
            # 记录交易
            trade = RealTrade(
                id=f"T{int(time.time() * 1000)}",
                datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                symbol=symbol,
                action='sell',
                price=price,
                shares=shares,
                amount=price * shares,
                status='filled' if result else 'failed',
                order_id=str(result) if result else None,
                message='卖出成功' if result else '卖出失败'
            )
            self.trades.append(trade)
            
            if result:
                print(f"卖出委托成功: {symbol} {shares}股 @ {price}")
                return True, str(result)
            else:
                return False, "卖出失败"
                
        except Exception as e:
            error_msg = f"卖出异常: {e}"
            print(error_msg)
            return False, error_msg
    
    def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        if not self.connected:
            return False
        
        try:
            # easytrader暂不支持直接撤单，需通过界面操作
            print("请手动在客户端撤单")
            return False
        except Exception as e:
            print(f"撤单失败: {e}")
            return False
    
    def get_today_trades(self) -> List[Dict]:
        """获取今日成交"""
        if not self.connected:
            return []
        
        try:
            trades = self.user.today_trades
            return trades
        except Exception as e:
            print(f"获取成交失败: {e}")
            return []
    
    def get_entrusts(self) -> List[Dict]:
        """获取委托列表"""
        if not self.connected:
            return []
        
        try:
            entrusts = self.user.entrust
            return entrusts
        except Exception as e:
            print(f"获取委托失败: {e}")
            return []
    
    def switch_mode(self, mode: str):
        """切换交易模式"""
        if mode in ['paper', 'real']:
            self.trade_mode = mode
            print(f"已切换至{'模拟' if mode == 'paper' else '实盘'}模式")
        else:
            print("模式错误，请选择 'paper' 或 'real'")
    
    def auto_trade_buy(self, symbol: str, price: float, shares: int,
                       condition: str = "") -> Tuple[bool, str]:
        """
        自动交易买入（带条件检查）
        
        Args:
            symbol: 股票代码
            price: 买入价格
            shares: 买入股数
            condition: 买入条件描述
        """
        if self.trade_mode == 'paper':
            return False, "当前为模拟模式，请切换到实盘模式"
        
        # 检查可用资金
        account = self.get_account_info()
        available = account.get('可用资金', 0)
        need_amount = price * shares
        
        if available < need_amount:
            return False, f"可用资金不足: {available} < {need_amount}"
        
        # 执行买入
        return self.buy(symbol, price, shares)
    
    def auto_trade_sell(self, symbol: str, price: float, shares: int,
                        condition: str = "") -> Tuple[bool, str]:
        """
        自动交易卖出（带条件检查）
        
        Args:
            symbol: 股票代码
            price: 卖出价格
            shares: 卖出股数
            condition: 卖出条件描述
        """
        if self.trade_mode == 'paper':
            return False, "当前为模拟模式，请切换到实盘模式"
        
        # 检查持仓
        positions = self.get_positions()
        hold_shares = 0
        for p in positions:
            code = str(symbol).strip()
            if code.isdigit() and len(code) > 5:
                code = code.zfill(6)
            if p['代码'] == code:
                hold_shares = p['可用']
                break
        
        if hold_shares < shares:
            return False, f"可用持仓不足: {hold_shares} < {shares}"
        
        # 执行卖出
        return self.sell(symbol, price, shares)
    
    def save_trade_history(self):
        """保存交易记录"""
        data = {
            'trades': [
                {
                    'id': t.id,
                    'datetime': t.datetime,
                    'symbol': t.symbol,
                    'action': t.action,
                    'price': t.price,
                    'shares': t.shares,
                    'amount': t.amount,
                    'status': t.status,
                    'order_id': t.order_id,
                    'message': t.message
                }
                for t in self.trades
            ]
        }
        
        with open('real_trade_history.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_trade_history(self):
        """加载交易记录"""
        try:
            with open('real_trade_history.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.trades = [
                    RealTrade(**t) for t in data.get('trades', [])
                ]
        except FileNotFoundError:
            pass


# 测试代码
if __name__ == '__main__':
    trader = DongguanTrader()
    
    print("东莞证券实盘交易模块")
    print("=" * 50)
    print("使用前请确保：")
    print("1. 东莞证券掌证宝客户端已安装")
    print("2. 客户端已登录")
    print("3. 客户端保持运行状态")
    print("=" * 50)
    
    # 尝试连接
    if trader.connect():
        print("\n账户信息:")
        info = trader.get_account_info()
        for k, v in info.items():
            print(f"  {k}: {v}")
        
        print("\n当前持仓:")
        positions = trader.get_positions()
        for p in positions:
            print(f"  {p['代码']} {p['名称']}: {p['股数']}股 @ {p['成本价']}")
    else:
        print("\n连接失败，请检查客户端状态")
