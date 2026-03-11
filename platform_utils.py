# -*- coding: utf-8 -*-
"""
跨平台工具模块
提供Windows、macOS、Linux的兼容性支持
"""

import sys
import os
import platform
from pathlib import Path
from typing import Optional, Dict, List


class PlatformInfo:
    """平台信息类"""
    
    @staticmethod
    def get_platform() -> str:
        """获取当前平台"""
        if sys.platform == 'win32':
            return 'windows'
        elif sys.platform == 'darwin':
            return 'macos'
        elif sys.platform.startswith('linux'):
            return 'linux'
        else:
            return 'unknown'
    
    @staticmethod
    def is_windows() -> bool:
        """是否为Windows"""
        return sys.platform == 'win32'
    
    @staticmethod
    def is_macos() -> bool:
        """是否为macOS"""
        return sys.platform == 'darwin'
    
    @staticmethod
    def is_linux() -> bool:
        """是否为Linux"""
        return sys.platform.startswith('linux')
    
    @staticmethod
    def get_home_dir() -> Path:
        """获取用户主目录"""
        return Path.home()
    
    @staticmethod
    def get_config_dir() -> Path:
        """获取配置目录"""
        plat = PlatformInfo.get_platform()
        home = PlatformInfo.get_home_dir()
        
        if plat == 'windows':
            # Windows: %APPDATA%\StockRobot 或 %USERPROFILE%\.stockrobot
            app_data = os.environ.get('APPDATA')
            if app_data:
                return Path(app_data) / 'StockRobot'
            return home / '.stockrobot'
        elif plat == 'macos':
            # macOS: ~/Library/Application Support/StockRobot
            return home / 'Library' / 'Application Support' / 'StockRobot'
        else:
            # Linux: ~/.config/stockrobot 或 ~/.stockrobot
            xdg_config = os.environ.get('XDG_CONFIG_HOME')
            if xdg_config:
                return Path(xdg_config) / 'stockrobot'
            return home / '.config' / 'stockrobot'
    
    @staticmethod
    def get_data_dir() -> Path:
        """获取数据目录"""
        plat = PlatformInfo.get_platform()
        home = PlatformInfo.get_home_dir()
        
        if plat == 'windows':
            # Windows: %LOCALAPPDATA%\StockRobot\Data
            local_app_data = os.environ.get('LOCALAPPDATA')
            if local_app_data:
                return Path(local_app_data) / 'StockRobot' / 'Data'
            return home / '.stockrobot' / 'data'
        elif plat == 'macos':
            # macOS: ~/Library/Application Support/StockRobot/Data
            return home / 'Library' / 'Application Support' / 'StockRobot' / 'Data'
        else:
            # Linux: ~/.local/share/stockrobot
            xdg_data = os.environ.get('XDG_DATA_HOME')
            if xdg_data:
                return Path(xdg_data) / 'stockrobot'
            return home / '.local' / 'share' / 'stockrobot'
    
    @staticmethod
    def ensure_dirs():
        """确保必要的目录存在"""
        dirs = [
            PlatformInfo.get_config_dir(),
            PlatformInfo.get_data_dir(),
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)


class UnicodeHelper:
    """Unicode编码辅助类"""
    
    @staticmethod
    def setup_stdout():
        """设置标准输出编码（解决Windows GBK问题）"""
        if sys.platform == 'win32':
            # Windows: 尝试设置UTF-8编码
            try:
                import io
                sys.stdout = io.TextIOWrapper(
                    sys.stdout.buffer, 
                    encoding='utf-8', 
                    errors='replace'
                )
                sys.stderr = io.TextIOWrapper(
                    sys.stderr.buffer,
                    encoding='utf-8',
                    errors='replace'
                )
            except Exception:
                pass
        
        # 设置环境变量
        os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    @staticmethod
    def safe_print(text: str):
        """安全打印（处理编码错误）"""
        try:
            print(text)
        except UnicodeEncodeError:
            # 如果打印失败，尝试替换无法编码的字符
            print(text.encode('utf-8', errors='replace').decode('utf-8'))


class PathHelper:
    """路径辅助类"""
    
    @staticmethod
    def get_project_root() -> Path:
        """获取项目根目录"""
        # 获取当前文件所在目录
        current_file = Path(__file__).resolve()
        return current_file.parent
    
    @staticmethod
    def get_chan_path() -> Optional[Path]:
        """获取chan.py路径（跨平台）"""
        root = PathHelper.get_project_root()
        chan_path = root / 'chan.py-main'
        
        if chan_path.exists():
            return chan_path
        
        # 尝试其他可能的位置
        alt_paths = [
            root.parent / 'chan.py-main',
            Path('/usr/local/share/chan.py-main'),  # Linux/macOS系统目录
            PlatformInfo.get_data_dir().parent / 'chan.py-main',
        ]
        
        for p in alt_paths:
            if p.exists():
                return p
        
        return None
    
    @staticmethod
    def normalize_path(path: str) -> str:
        """标准化路径（跨平台）"""
        return str(Path(path).resolve())
    
    @staticmethod
    def join_path(*parts) -> str:
        """跨平台路径拼接"""
        return str(Path(*parts))


class BrokerPlatformHelper:
    """券商客户端跨平台支持"""
    
    # 各平台支持的券商客户端路径
    BROKER_PATHS = {
        'windows': {
            'ths': [  # 同花顺
                r'C:\Users\{username}\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\同花顺\同花顺.lnk',
                r'C:\Program Files (x86)\同花顺\hexin.exe',
                r'C:\Program Files\同花顺\hexin.exe',
            ],
            'ht': [  # 华泰
                r'C:\Users\{username}\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\华泰证券\涨乐财富通.lnk',
                r'C:\Program Files (x86)\华泰证券\涨乐财富通\zgjzyj.exe',
            ],
            'gj': [  # 国泰君安
                r'C:\Program Files (x86)\国泰君安\君弘\Junhong.exe',
            ],
            'zht': [  # 招商
                r'C:\Program Files (x86)\招商证券\智远一户通\ZYZH.exe',
            ],
        },
        'macos': {
            'ths': [  # 同花顺 Mac版
                '/Applications/同花顺.app/Contents/MacOS/同花顺',
                '/Applications/THS.app/Contents/MacOS/THS',
            ],
            'ht': [  # 华泰 Mac版
                '/Applications/涨乐财富通.app/Contents/MacOS/涨乐财富通',
            ],
            'gj': [  # 国泰君安 Mac版
                '/Applications/君弘.app/Contents/MacOS/君弘',
            ],
        },
        'linux': {
            # Linux通常使用网页版或Wine运行Windows客户端
            'ths': [
                '/usr/local/bin/ths',
                '/opt/ths/hexin.exe',  # Wine
            ],
        }
    }
    
    @staticmethod
    def find_broker_exe(broker_type: str) -> Optional[str]:
        """查找券商客户端可执行文件"""
        plat = PlatformInfo.get_platform()
        paths = BrokerPlatformHelper.BROKER_PATHS.get(plat, {}).get(broker_type, [])
        
        # 替换用户名变量
        username = os.environ.get('USERNAME') or os.environ.get('USER') or ''
        paths = [p.format(username=username) for p in paths]
        
        for path in paths:
            if os.path.exists(path):
                return path
        
        return None
    
    @staticmethod
    def is_broker_supported(broker_type: str) -> bool:
        """检查券商是否在当前平台支持"""
        plat = PlatformInfo.get_platform()
        return broker_type in BrokerPlatformHelper.BROKER_PATHS.get(plat, {})
    
    @staticmethod
    def get_supported_brokers() -> List[str]:
        """获取当前平台支持的券商列表"""
        plat = PlatformInfo.get_platform()
        return list(BrokerPlatformHelper.BROKER_PATHS.get(plat, {}).keys())


class EnvironmentSetup:
    """环境设置类"""
    
    @staticmethod
    def setup_all():
        """设置所有环境"""
        # 设置编码
        UnicodeHelper.setup_stdout()
        
        # 确保目录存在
        PlatformInfo.ensure_dirs()
        
        # 添加chan.py到路径
        chan_path = PathHelper.get_chan_path()
        if chan_path and str(chan_path) not in sys.path:
            sys.path.insert(0, str(chan_path))
    
    @staticmethod
    def get_platform_summary() -> Dict:
        """获取平台摘要信息"""
        return {
            'platform': PlatformInfo.get_platform(),
            'python_version': sys.version,
            'system': platform.system(),
            'release': platform.release(),
            'machine': platform.machine(),
            'config_dir': str(PlatformInfo.get_config_dir()),
            'data_dir': str(PlatformInfo.get_data_dir()),
            'project_root': str(PathHelper.get_project_root()),
            'supported_brokers': BrokerPlatformHelper.get_supported_brokers(),
        }


# 便捷函数
def get_platform() -> str:
    """获取当前平台"""
    return PlatformInfo.get_platform()


def is_windows() -> bool:
    """是否为Windows"""
    return PlatformInfo.is_windows()


def is_macos() -> bool:
    """是否为macOS"""
    return PlatformInfo.is_macos()


def is_linux() -> bool:
    """是否为Linux"""
    return PlatformInfo.is_linux()


def setup_environment():
    """设置环境"""
    EnvironmentSetup.setup_all()


# 测试代码
if __name__ == '__main__':
    print("=" * 60)
    print("跨平台工具测试")
    print("=" * 60)
    
    # 设置环境
    setup_environment()
    
    # 显示平台信息
    print("\n平台信息:")
    info = EnvironmentSetup.get_platform_summary()
    for key, value in info.items():
        if isinstance(value, list):
            print(f"  {key}: {', '.join(value)}")
        else:
            print(f"  {key}: {value}")
    
    # 测试路径
    print("\n路径测试:")
    print(f"  配置目录: {PlatformInfo.get_config_dir()}")
    print(f"  数据目录: {PlatformInfo.get_data_dir()}")
    print(f"  项目根目录: {PathHelper.get_project_root()}")
    print(f"  chan.py路径: {PathHelper.get_chan_path()}")
    
    # 测试券商查找
    print("\n券商客户端查找测试:")
    for broker in ['ths', 'ht', 'gj']:
        path = BrokerPlatformHelper.find_broker_exe(broker)
        status = f"找到: {path}" if path else "未找到"
        print(f"  {broker}: {status}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
