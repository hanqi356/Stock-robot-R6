"""
股票数据获取模块
使用pytdx连接通达信获取实时/历史数据
"""

from pytdx.hq import TdxHq_API
from pytdx.exhq import TdxExHq_API
import pandas as pd
from typing import List, Dict, Optional

# 通达信服务器节点列表
TDX_SERVERS = [
    ('119.147.212.81', 7709),   # 上海电信
    ('119.147.212.82', 7709),   # 上海电信
    ('119.147.212.83', 7709),   # 上海电信
    ('218.75.126.9', 7709),     # 深圳电信
    ('221.231.141.60', 7709),   # 武汉电信
]

class StockDataAPI:
    """通达信数据API封装"""
    
    def __init__(self):
        self.api = TdxHq_API()
        self.connected = False
        self.best_server = None
        
    def connect(self, host: str = None, port: int = 7709) -> bool:
        """
        连接通达信服务器
        如果未指定host，自动寻找最佳节点
        """
        if self.connected:
            return True
            
        if host:
            try:
                self.connected = self.api.connect(host, port)
                if self.connected:
                    self.best_server = (host, port)
                    print(f"已连接通达信服务器: {host}:{port}")
                return self.connected
            except Exception as e:
                print(f"连接失败: {e}")
                return False
        else:
            # 自动寻找最佳节点
            for host, port in TDX_SERVERS:
                try:
                    if self.api.connect(host, port):
                        self.connected = True
                        self.best_server = (host, port)
                        print(f"已连接通达信服务器: {host}:{port}")
                        return True
                except:
                    continue
            print("所有服务器节点连接失败")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.connected:
            self.api.disconnect()
            self.connected = False
            print("已断开连接")
    
    def _get_market_code(self, symbol) -> int:
        """
        获取市场代码
        0=深圳, 1=上海
        """
        symbol = str(symbol).upper()
        if symbol.startswith('SZ'):
            return 0
        elif symbol.startswith('SH'):
            return 1
        elif symbol.isdigit():
            # 补齐到6位
            code = symbol.zfill(6)
            # 根据代码规则判断
            if code.startswith(('0', '3', '2')):
                return 0  # 深圳
            elif code.startswith(('6', '5', '9')):
                return 1  # 上海
        return 1  # 默认上海
    
    def _clean_symbol(self, symbol) -> str:
        """清理股票代码，去除前缀"""
        symbol = str(symbol).upper()
        if symbol.startswith('SZ') or symbol.startswith('SH'):
            return symbol[2:]
        return symbol
    
    def get_kline(self, symbol: str, ktype: str = 'day', count: int = 100) -> pd.DataFrame:
        """
        获取K线数据
        
        Parameters:
            symbol: 股票代码 (如 '600000' 或 'SH600000' 或 '03938')
            ktype: K线类型 - '1min', '5min', '15min', '30min', '60min', 'day', 'week', 'month'
            count: 获取条数
        
        Returns:
            DataFrame with columns: [datetime, open, high, low, close, volume, amount]
        """
        if not self.connected:
            if not self.connect():
                return pd.DataFrame()
        
        market = self._get_market_code(symbol)
        code = self._clean_symbol(symbol)
        
        # K线类型映射
        ktype_map = {
            '1min': 8,
            '5min': 0,
            '15min': 1,
            '30min': 2,
            '60min': 3,
            'day': 9,
            'week': 5,
            'month': 6
        }
        
        kline_type = ktype_map.get(ktype, 9)
        
        try:
            data = self.api.get_security_bars(kline_type, market, code, 0, count)
            if not data:
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.sort_values('datetime').reset_index(drop=True)
            
            return df[['datetime', 'open', 'high', 'low', 'close', 'vol', 'amount']]
        except Exception as e:
            print(f"获取K线数据失败: {e}")
            return pd.DataFrame()
    
    def _get_ext_market_kline(self, symbol: str, ktype: str = 'day', count: int = 100) -> pd.DataFrame:
        """
        获取扩展市场K线数据（港股等）
        """
        try:
            # 使用扩展市场API
            ext_api = TdxExHq_API()
            # 尝试连接扩展市场服务器
            ext_servers = [
                ('61.152.107.141', 7727),
                ('61.152.107.141', 7721),
            ]
            connected = False
            for host, port in ext_servers:
                try:
                    if ext_api.connect(host, port):
                        connected = True
                        break
                except:
                    continue
            
            if not connected:
                print(f"扩展市场服务器连接失败，无法获取 {symbol} 数据")
                return pd.DataFrame()
            
            # 港股代码格式：market=1, code=03938
            # 尝试获取港股数据
            code = str(symbol).upper().lstrip('0')
            if not code.isdigit():
                code = symbol
            
            # K线类型映射（扩展市场）
            ktype_map = {
                '1min': 0,
                '5min': 1,
                '15min': 2,
                '30min': 3,
                '60min': 4,
                'day': 5,
                'week': 6,
                'month': 7
            }
            kline_type = ktype_map.get(ktype, 5)
            
            # 尝试获取数据（港股market=1）
            data = ext_api.get_instrument_bars(kline_type, 1, code, 0, count)
            ext_api.disconnect()
            
            if not data:
                print(f"无法获取 {symbol} 的扩展市场数据")
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.sort_values('datetime').reset_index(drop=True)
            return df[['datetime', 'open', 'high', 'low', 'close', 'vol', 'amount']]
        except Exception as e:
            print(f"获取扩展市场K线数据失败: {e}")
            return pd.DataFrame()
    
    def get_realtime_quotes(self, symbols: List[str]) -> pd.DataFrame:
        """
        获取实时行情
        
        Parameters:
            symbols: 股票代码列表
        
        Returns:
            DataFrame with realtime quotes
        """
        if not self.connected:
            if not self.connect():
                return pd.DataFrame()
        
        result = []
        
        for symbol in symbols:
            market = self._get_market_code(symbol)
            code = self._clean_symbol(symbol)
            
            try:
                data = self.api.get_security_quotes([(market, code)])
                if data:
                    result.extend(data)
            except Exception as e:
                print(f"获取 {symbol} 行情失败: {e}")
        
        if result:
            df = pd.DataFrame(result)
            # 重命名列以便统一访问
            column_mapping = {
                'code': 'code',
                'name': 'name',
                'price': 'price',
                'last_close': 'last_close',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'vol': 'vol',
                'amount': 'amount'
            }
            # 确保name列存在
            if 'name' not in df.columns:
                df['name'] = df['code']
            return df
        return pd.DataFrame()
    
    def _get_ext_market_quotes(self, symbols: List[str]) -> pd.DataFrame:
        """获取扩展市场实时行情（港股等）"""
        try:
            from pytdx.exhq import TdxExHq_API
            ext_api = TdxExHq_API()
            
            # 尝试连接扩展市场服务器
            ext_servers = [
                ('61.152.107.141', 7727),
                ('61.152.107.141', 7721),
            ]
            connected = False
            for host, port in ext_servers:
                try:
                    if ext_api.connect(host, port):
                        connected = True
                        break
                except:
                    continue
            
            if not connected:
                print("扩展市场服务器连接失败")
                return pd.DataFrame()
            
            result = []
            for symbol in symbols:
                code = str(symbol).upper().lstrip('0')
                if not code.isdigit():
                    code = symbol
                try:
                    # 港股 market=1
                    data = ext_api.get_instrument_quote(1, code)
                    if data:
                        # 转换数据格式以兼容A股格式
                        for item in data:
                            result.append({
                                'code': symbol,
                                'name': item.get('name', symbol),
                                'price': item.get('price', 0),
                                'last_close': item.get('last_close', item.get('price', 0)),
                                'open': item.get('open', 0),
                                'high': item.get('high', 0),
                                'low': item.get('low', 0),
                                'vol': item.get('vol', 0),
                                'amount': item.get('amount', 0)
                            })
                except Exception as e:
                    print(f"获取港股 {symbol} 行情失败: {e}")
            
            ext_api.disconnect()
            return pd.DataFrame(result) if result else pd.DataFrame()
        except Exception as e:
            print(f"获取扩展市场行情失败: {e}")
            return pd.DataFrame()
    
    def get_stock_list(self, market: str = 'sh') -> pd.DataFrame:
        """
        获取股票列表
        
        Parameters:
            market: 'sh'=上海, 'sz'=深圳
        """
        if not self.connected:
            if not self.connect():
                return pd.DataFrame()
        
        market_code = 1 if market == 'sh' else 0
        
        try:
            count = self.api.get_security_count(market_code)
            data = self.api.get_security_list(market_code, 0)
            
            df = pd.DataFrame(data)
            return df
        except Exception as e:
            print(f"获取股票列表失败: {e}")
            return pd.DataFrame()
    
    def get_transaction_data(self, symbol: str, count: int = 100) -> pd.DataFrame:
        """
        获取分笔成交数据
        
        Parameters:
            symbol: 股票代码
            count: 获取条数
        """
        if not self.connected:
            if not self.connect():
                return pd.DataFrame()
        
        market = self._get_market_code(symbol)
        code = self._clean_symbol(symbol)
        
        try:
            data = self.api.get_transaction_data(market, code, 0, count)
            if data:
                df = pd.DataFrame(data)
                return df
        except Exception as e:
            print(f"获取分笔数据失败: {e}")
        return pd.DataFrame()


# 全局API实例
_stock_api = StockDataAPI()


def get_stock_data(symbol: str, period: str = 'day', count: int = 100) -> pd.DataFrame:
    """
    获取股票数据（简化接口）
    
    Parameters:
        symbol: 股票代码 (如 '600000')
        period: 周期 - '1min', '5min', '15min', '30min', '60min', 'day', 'week', 'month'
        count: 数据条数
    
    Returns:
        DataFrame
    """
    if not _stock_api.connected:
        _stock_api.connect()
    return _stock_api.get_kline(symbol, period, count)


def get_realtime_data(symbols: list) -> pd.DataFrame:
    """
    获取实时行情（简化接口）
    如果通达信连接失败，返回模拟数据
    """
    try:
        if not _stock_api.connected:
            _stock_api.connect()
        
        if _stock_api.connected:
            return _stock_api.get_realtime_quotes(symbols)
    except Exception as e:
        print(f"[!] 通达信实时行情获取失败: {e}")
    
    # 连接失败，返回模拟数据
    print(f"[!] 使用模拟实时数据")
    import numpy as np
    
    data = []
    for symbol in symbols:
        # 基于代码生成固定的模拟价格
        np.random.seed(hash(symbol) % 10000)
        base_price = 50 + (hash(symbol) % 100)
        price = base_price + np.random.randn() * 2
        
        data.append({
            'code': symbol,
            'name': f'股票{symbol}',
            'price': round(price, 2),
            'open': round(price * 0.99, 2),
            'high': round(price * 1.02, 2),
            'low': round(price * 0.98, 2),
            'last_close': round(price * 0.995, 2),
            'vol': int(np.random.randint(100000, 10000000)),
            'amount': int(np.random.randint(1000000, 100000000)),
            'change_pct': round(np.random.randn() * 2, 2)
        })
    
    return pd.DataFrame(data)


if __name__ == '__main__':
    # 测试代码
    print("正在连接通达信服务器...")
    api = StockDataAPI()
    
    if api.connect():
        # 获取上证指数日线
        df = api.get_kline('SH000001', 'day', 10)
        print("\n上证指数日线数据:")
        print(df)
        
        # 获取贵州茅台日线
        df = api.get_kline('600519', 'day', 5)
        print("\n贵州茅台日线数据:")
        print(df)
        
        # 获取实时行情
        quotes = api.get_realtime_quotes(['SH000001', '600519', '000001'])
        print("\n实时行情:")
        print(quotes)
        
        api.disconnect()
    else:
        print("连接失败，请检查网络或通达信服务器状态")
