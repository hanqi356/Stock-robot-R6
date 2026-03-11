"""
快速验证脚本 - 检查安装是否成功
"""

import sys
import importlib

# 修复 Windows GBK 控制台无法输出 Unicode 字符的问题
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def print_header(title):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def check_module(module_name, display_name=None):
    """检查模块是否安装"""
    if display_name is None:
        display_name = module_name
    
    try:
        importlib.import_module(module_name)
        print(f"[OK] {display_name}")
        return True
    except ImportError as e:
        print(f"[FAIL] {display_name}: {e}")
        return False
    except Exception as e:
        print(f"[WARN] {display_name}: {e}")
        return False

def main():
    """主函数"""
    print_header("量化交易系统 R6 - 安装验证")
    
    # 检查 Python 版本
    print(f"\nPython 版本：{sys.version}")
    print(f"Python 路径：{sys.executable}")
    
    # 核心库检查
    print_header("1. 核心基础库")
    core_modules = [
        ('numpy', 'NumPy'),
        ('pandas', 'Pandas'),
        ('matplotlib', 'Matplotlib'),
        ('PIL', 'Pillow'),
    ]
    
    core_passed = 0
    for module, name in core_modules:
        if check_module(module, name):
            core_passed += 1
    
    print(f"\n核心库：{core_passed}/{len(core_modules)} 通过")
    
    # GUI 相关检查
    print_header("2. GUI 组件")
    gui_modules = [
        ('tkinter', 'Tkinter'),
        ('tkinter.ttk', 'Tkinter TTK'),
    ]
    
    gui_passed = 0
    for module, name in gui_modules:
        if check_module(module, name):
            gui_passed += 1
    
    print(f"\nGUI 组件：{gui_passed}/{len(gui_modules)} 通过")
    
    # 数据接口检查
    print_header("3. 数据接口")
    data_modules = [
        ('pytdx', '通达信接口'),
        ('akshare', 'AKShare'),
    ]
    
    data_passed = 0
    for module, name in data_modules:
        if check_module(module, name):
            data_passed += 1
    
    print(f"\n数据接口：{data_passed}/{len(data_modules)} 通过")
    
    # 分析工具检查
    print_header("4. 分析工具")
    analysis_modules = [
        ('sqlalchemy', 'SQLAlchemy'),
        ('requests', 'Requests'),
        ('bs4', 'BeautifulSoup4'),
        ('yaml', 'PyYAML'),
    ]
    
    analysis_passed = 0
    for module, name in analysis_modules:
        if check_module(module, name):
            analysis_passed += 1
    
    print(f"\n分析工具：{analysis_passed}/{len(analysis_modules)} 通过")
    
    # AI 相关检查
    print_header("5. AI 模型接口（可选）")
    ai_modules = [
        ('openai', 'OpenAI'),
        ('google.generativeai', 'Google Gemini'),
        ('anthropic', 'Anthropic Claude'),
    ]
    
    ai_passed = 0
    for module, name in ai_modules:
        if check_module(module, name):
            ai_passed += 1
    
    print(f"\nAI 接口：{ai_passed}/{len(ai_modules)} 通过 (可选功能)")
    
    # 缠论相关检查
    print_header("6. 缠论分析（可选）")
    chan_modules = [
        ('loguru', 'Loguru'),
        ('pyarrow', 'PyArrow'),
        ('talib', 'TA-Lib'),
        ('parse', 'Parse'),
        ('pyecharts', 'PyECharts'),
        ('lightweight_charts', 'Lightweight Charts'),
        ('seaborn', 'Seaborn'),
        ('statsmodels', 'Statsmodels'),
        ('plotly', 'Plotly'),
    ]
    
    chan_passed = 0
    for module, name in chan_modules:
        if check_module(module, name):
            chan_passed += 1
    
    print(f"\n缠论工具：{chan_passed}/{len(chan_modules)} 通过 (可选功能)")
    
    # czsc 缠论库检查
    print("\n检查 czsc 缠论库...")
    try:
        import czsc
        print(f"[OK] czsc 缠论库 v{czsc.__version__}")
        chan_passed += 1
    except ImportError:
        print("[INFO] czsc 缠论库未安装（可选功能，可跳过）")
    
    # 总体评估
    print_header("验证结果汇总")
    
    total_core = core_passed + gui_passed + data_passed + analysis_passed
    total_optional = ai_passed + chan_passed
    total_core_count = len(core_modules) + len(gui_modules) + len(data_modules) + len(analysis_modules)
    
    print(f"\n核心功能：{total_core}/{total_core_count} 通过")
    print(f"可选功能：{total_optional}/{len(ai_modules) + len(chan_modules) + 1} 通过")
    
    # 判断是否满足最低要求
    if core_passed == len(core_modules) and gui_passed == len(gui_modules):
        print("\n[SUCCESS] 系统已正确安装，可以正常使用！")
        
        if data_passed < len(data_modules):
            print("\n[提示] 部分数据接口未安装，可能影响数据获取功能")
        
        print("\n下一步:")
        print("1. 双击 启动专业版.bat 启动程序")
        print("2. 等待 GUI 界面加载")
        print("3. 开始使用各项功能")
        
    else:
        print("\n[WARNING] 部分核心组件缺失，建议重新运行 一键安装并运行.bat 安装")
        print("\n缺失的组件:")
        if core_passed < len(core_modules):
            print("  - 核心基础库")
        if gui_passed < len(gui_modules):
            print("  - GUI 组件")
    
    print("\n" + "=" * 60)
    print("验证完成！")
    print("=" * 60)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] 验证过程出错：{e}")
        import traceback
        traceback.print_exc()
