# -*- coding: utf-8 -*-
"""
多券商交易接口工厂
支持：东莞证券、华泰证券、国泰君安、招商证券等
基于 easytrader 的统一封装
支持Windows、macOS、Linux
"""

import json
import os
import sys
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# 跨平台支持
try:
    from platform_utils import PlatformInfo, BrokerPlatformHelper
except ImportError:
    # 备用定义
    class PlatformInfo:
        @staticmethod
        def get_platform():
            if sys.platform == 'win32':
                return 'windows'
            elif sys.platform == 'darwin':
                return 'macos'
            else:
                return 'linux'
    
    class BrokerPlatformHelper:
        @staticmethod
        def get_supported_brokers():
            return ['ths', 'ht'] if sys.platform == 'win32' else []

# 条件导入 easytrader（仅Windows支持）
try:
    import easytrader
    EASYTRADER_AVAILABLE = True
except ImportError:
    easytrader = None
    EASYTRADER_AVAILABLE = False


@dataclass
class BrokerConfig:
    """券商配置"""
    name: str  # 券商名称
    code: str  # 券商代码
    type: str  # 客户端类型: 'ths'(同花顺)/'ht'(华泰)/'gj'(国君)/'zht'(招商)
    exe_path: Optional[str] = None  # 客户端路径
    auto_login: bool = False  # 是否自动登录
    account: Optional[str] = None  # 资金账号
    password: Optional[str] = None  # 密码（加密存储）


class BaseBrokerTrader(ABC):
    """券商交易接口基类"""
    
    def __init__(self, config: BrokerConfig):
        self.config = config
        self.user = None
        self.connected = False
        self.account_info: Dict = {}
        self.positions: List[Dict] = []
        self.trades: List[Dict] = []
        
    @abstractmethod
    def connect(self) -> bool:
        """连接券商客户端"""
        pass
    
    @abstractmethod
    def disconnect(self):
        """断开连接"""
        pass
    
    @abstractmethod
    def get_account_info(self) -> Dict:
        """获取账户信息"""
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Dict]:
        """获取持仓"""
        pass
    
    @abstractmethod
    def buy(self, symbol: str, price: float, shares: int) -> Tuple[bool, str]:
        """买入"""
        pass
    
    @abstractmethod
    def sell(self, symbol: str, price: float, shares: int) -> Tuple[bool, str]:
        """卖出"""
        pass
    
    def get_name(self) -> str:
        """获取券商名称"""
        return self.config.name


class EasytraderBrokerTrader(BaseBrokerTrader):
    """
    基于 easytrader 的通用券商交易接口
    支持所有 easytrader 支持的券商
    注意：easytrader 仅支持 Windows
    """
    
    def __init__(self, config: BrokerConfig):
        super().__init__(config)
        if not EASYTRADER_AVAILABLE:
            raise RuntimeError("easytrader 未安装，无法使用实盘交易功能")
    
    def connect(self) -> bool:
        """连接券商客户端"""
        if not EASYTRADER_AVAILABLE:
            print(f"{self.config.name} 连接失败: easytrader 未安装")
            return False
        
        # 检查平台
        if PlatformInfo.get_platform() != 'windows':
            print(f"{self.config.name} 连接失败: easytrader 仅支持 Windows 平台")
            return False
        
        try:
            # 使用 easytrader 创建交易对象
            self.user = easytrader.use(self.config.type)
            
            if self.config.exe_path and os.path.exists(self.config.exe_path):
                # 指定路径连接
                self.user.connect(self.config.exe_path)
            else:
                # 尝试自动查找客户端
                auto_path = BrokerPlatformHelper.find_broker_exe(self.config.type)
                if auto_path:
                    self.user.connect(auto_path)
                else:
                    # 自动连接已启动的客户端
                    self.user.connect()
            
            self.connected = True
            print(f"{self.config.name} 连接成功")
            return True
            
        except Exception as e:
            print(f"{self.config.name} 连接失败: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """断开连接"""
        self.connected = False
        self.user = None
        print(f"{self.config.name} 已断开")
    
    def get_account_info(self) -> Dict:
        """获取账户信息"""
        if not self.connected or not self.user:
            return {'error': '未连接'}
        
        try:
            balance = self.user.balance
            return {
                '券商': self.config.name,
                '资金余额': balance.get('资金余额', 0),
                '可用资金': balance.get('可用金额', 0),
                '冻结资金': balance.get('冻结金额', 0),
                '总资产': balance.get('总资产', 0),
                '市值': balance.get('股票市值', 0),
                '更新时间': datetime.now().strftime('%H:%M:%S')
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_positions(self) -> List[Dict]:
        """获取持仓列表"""
        if not self.connected or not self.user:
            return []
        
        try:
            positions = self.user.position
            result = []
            for p in positions:
                result.append({
                    '代码': p.get('证券代码', ''),
                    '名称': p.get('证券名称', ''),
                    '股数': p.get('股票余额', 0),
                    '可用': p.get('可用余额', 0),
                    '成本价': p.get('成本价', 0),
                    '现价': p.get('市价', 0),
                    '市值': p.get('市值', 0),
                    '盈亏': p.get('盈亏', 0),
                    '盈亏率': p.get('盈亏比例(%)', 0)
                })
            return result
        except Exception as e:
            print(f"获取持仓失败: {e}")
            return []
    
    def buy(self, symbol: str, price: float, shares: int) -> Tuple[bool, str]:
        """买入股票"""
        if not self.connected:
            return False, "未连接"
        
        if shares % 100 != 0:
            return False, "买入股数必须是100的整数倍"
        
        try:
            # 格式化股票代码
            symbol = str(symbol).strip()
            if symbol.isdigit() and len(symbol) <= 6:
                symbol = symbol.zfill(6)
            
            result = self.user.buy(symbol, price, shares)
            
            if result:
                return True, str(result)
            else:
                return False, "买入失败"
                
        except Exception as e:
            return False, f"买入异常: {e}"
    
    def sell(self, symbol: str, price: float, shares: int) -> Tuple[bool, str]:
        """卖出股票"""
        if not self.connected:
            return False, "未连接"
        
        try:
            # 格式化股票代码
            symbol = str(symbol).strip()
            if symbol.isdigit() and len(symbol) <= 6:
                symbol = symbol.zfill(6)
            
            result = self.user.sell(symbol, price, shares)
            
            if result:
                return True, str(result)
            else:
                return False, "卖出失败"
                
        except Exception as e:
            return False, f"卖出异常: {e}"
    
    def get_today_trades(self) -> List[Dict]:
        """获取今日成交"""
        if not self.connected:
            return []
        try:
            return self.user.today_trades
        except:
            return []
    
    def get_entrusts(self) -> List[Dict]:
        """获取委托列表"""
        if not self.connected:
            return []
        try:
            return self.user.entrust
        except:
            return []


class BrokerFactory:
    """券商工厂类 - 管理所有支持的券商"""
    
    # 预定义的券商配置（根据平台过滤）
    _ALL_BROKERS = {
        'dongguan': BrokerConfig(name='东莞证券', code='dongguan', type='ths', exe_path=None),
        'huatai': BrokerConfig(name='华泰证券', code='huatai', type='ht', exe_path=None),
        'guojun': BrokerConfig(name='国泰君安', code='guojun', type='gj', exe_path=None),
        'zhaoshang': BrokerConfig(name='招商证券', code='zhaoshang', type='zht', exe_path=None),
        'guoxin': BrokerConfig(name='国信证券', code='guoxin', type='ths', exe_path=None),
        'guangfa': BrokerConfig(name='广发证券', code='guangfa', type='ths', exe_path=None),
        'zhongxin': BrokerConfig(name='中信证券', code='zhongxin', type='ths', exe_path=None),
        'xingye': BrokerConfig(name='兴业证券', code='xingye', type='ths', exe_path=None),
    }
    
    @property
    def SUPPORTED_BROKERS(self) -> Dict[str, BrokerConfig]:
        """获取当前平台支持的券商"""
        plat = PlatformInfo.get_platform()
        
        if plat != 'windows':
            # 非Windows平台：easytrader 不支持
            print(f"警告：当前平台 {plat} 不支持 easytrader 实盘交易")
            print("模拟交易功能仍然可用")
            return {}
        
        return self._ALL_BROKERS
    
    def __init__(self):
        # 使用跨平台配置目录
        try:
            from platform_utils import PlatformInfo
            config_dir = PlatformInfo.get_config_dir()
            config_dir.mkdir(parents=True, exist_ok=True)
            self.config_file = str(config_dir / 'broker_config.json')
        except ImportError:
            self.config_file = 'broker_config.json'
        
        self.user_configs: Dict[str, BrokerConfig] = {}
        self.current_trader: Optional[BaseBrokerTrader] = None
        self.load_user_configs()
    
    def get_supported_brokers(self) -> List[Dict]:
        """获取支持的券商列表"""
        return [
            {
                'code': code,
                'name': config.name,
                'type': config.type
            }
            for code, config in self.SUPPORTED_BROKERS.items()
        ]
    
    def create_trader(self, broker_code: str, 
                      exe_path: Optional[str] = None) -> Optional[BaseBrokerTrader]:
        """
        创建券商交易接口
        
        Args:
            broker_code: 券商代码
            exe_path: 客户端路径（可选）
        
        Returns:
            交易接口实例
        """
        if broker_code not in self.SUPPORTED_BROKERS:
            print(f"不支持的券商: {broker_code}")
            return None
        
        config = self.SUPPORTED_BROKERS[broker_code]
        
        # 使用用户自定义路径
        if exe_path:
            config.exe_path = exe_path
        elif broker_code in self.user_configs:
            config.exe_path = self.user_configs[broker_code].exe_path
        
        # 创建交易接口
        trader = EasytraderBrokerTrader(config)
        self.current_trader = trader
        return trader
    
    def save_user_config(self, broker_code: str, exe_path: str):
        """保存用户券商配置"""
        if broker_code in self.SUPPORTED_BROKERS:
            config = self.SUPPORTED_BROKERS[broker_code]
            config.exe_path = exe_path
            self.user_configs[broker_code] = config
            self._save_configs()
    
    def load_user_configs(self):
        """加载用户配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for code, config_data in data.items():
                        if code in self.SUPPORTED_BROKERS:
                            self.SUPPORTED_BROKERS[code].exe_path = config_data.get('exe_path')
                            self.user_configs[code] = self.SUPPORTED_BROKERS[code]
            except Exception as e:
                print(f"加载券商配置失败: {e}")
    
    def _save_configs(self):
        """保存配置到文件"""
        data = {
            code: {
                'exe_path': config.exe_path,
                'name': config.name
            }
            for code, config in self.user_configs.items()
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存券商配置失败: {e}")
    
    def get_current_trader(self) -> Optional[BaseBrokerTrader]:
        """获取当前交易接口"""
        return self.current_trader


# 全局工厂实例
_broker_factory: Optional[BrokerFactory] = None


def get_broker_factory() -> BrokerFactory:
    """获取券商工厂单例"""
    global _broker_factory
    if _broker_factory is None:
        _broker_factory = BrokerFactory()
    return _broker_factory


def create_broker_trader(broker_code: str, exe_path: Optional[str] = None) -> Optional[BaseBrokerTrader]:
    """便捷函数：创建券商交易接口"""
    factory = get_broker_factory()
    return factory.create_trader(broker_code, exe_path)


def get_supported_brokers() -> List[Dict]:
    """便捷函数：获取支持的券商列表"""
    return get_broker_factory().get_supported_brokers()


# 测试代码
if __name__ == '__main__':
    print("=" * 60)
    print("多券商交易接口测试")
    print("=" * 60)
    
    # 显示支持的券商
    print("\n支持的券商列表:")
    brokers = get_supported_brokers()
    for b in brokers:
        print(f"  [{b['code']}] {b['name']} (类型: {b['type']})")
    
    # 测试创建交易接口
    print("\n测试创建东莞证券交易接口...")
    trader = create_broker_trader('dongguan')
    if trader:
        print(f"  成功创建: {trader.get_name()}")
    
    print("\n测试创建华泰证券交易接口...")
    trader = create_broker_trader('huatai')
    if trader:
        print(f"  成功创建: {trader.get_name()}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
