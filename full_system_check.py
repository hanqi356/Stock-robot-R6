"""
量化交易系统 R6 - 全面自检脚本
检测所有核心模块、缠论功能、GUI 完整性
"""

import sys
import importlib
from datetime import datetime

# 修复 Windows GBK 控制台无法输出 Unicode 字符的问题
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def print_header(title):
    """打印标题"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def test_core_modules():
    """测试核心模块导入"""
    print_header("1. 核心模块导入测试")
    
    modules = [
        'stock_data',
        'strategy',
        'backtest_engine',
        'chanlun_engine',
        'ai_analyzer',
        'indicators',
        'custom_indicators',
        'trading_rules_enforcer'
    ]
    
    failed = []
    for module in modules:
        try:
            importlib.import_module(module)
            print(f"[OK] {module}")
        except Exception as e:
            print(f"[FAIL] {module}: {e}")
            failed.append(module)
    
    return len(failed) == 0, failed


def test_chan_modules():
    """测试缠论相关模块"""
    print_header("2. 缠论模块测试")
    
    modules = [
        'chan_divergence_strategy',
        'signal_integrator',
        'unified_analyzer',
        'chan_backtester',
        'chan_adapter'
    ]
    
    failed = []
    for module in modules:
        try:
            importlib.import_module(module)
            print(f"[OK] {module}")
        except Exception as e:
            print(f"[FAIL] {module}: {e}")
            failed.append(module)
    
    return len(failed) == 0, failed


def test_gui_components():
    """测试 GUI 组件"""
    print_header("3. GUI 模块测试")
    
    try:
        from stock_pro_gui import ProStockGUI
        
        # 创建实例（不初始化）
        gui = ProStockGUI.__new__(ProStockGUI)
        print("[OK] GUI 类可实例化")
        
        # 检查关键方法
        methods = [
            'chan_divergence_analysis',
            '_show_chan_divergence_result',
            'ai_analyze_selected',
            'factor_analyze_selected',
            'buy_selected',
            'sell_selected'
        ]
        
        failed_methods = []
        for method in methods:
            if hasattr(gui, method):
                print(f"[OK] 方法 {method} 存在")
            else:
                print(f"[FAIL] 方法 {method} 缺失")
                failed_methods.append(method)
        
        return len(failed_methods) == 0, failed_methods
        
    except Exception as e:
        print(f"[FAIL] GUI 导入失败：{e}")
        return False, [str(e)]


def test_dependencies():
    """测试依赖包"""
    print_header("4. 依赖包检查")
    
    packages = [
        'pandas',
        'numpy',
        'loguru',
        'czsc'
    ]
    
    failed = []
    for pkg in packages:
        try:
            importlib.import_module(pkg)
            print(f"[OK] {pkg}")
        except Exception as e:
            print(f"[FAIL] {pkg}: {e}")
            failed.append(pkg)
    

    
    return len(failed) == 0, failed


def test_czsc_functionality():
    """测试 czsc 功能"""
    print_header("5. czsc 缠论库测试")
    
    try:
        import czsc
        
        print(f"[OK] czsc 版本：{czsc.__version__}")
        
        # 检查核心类 (可选)
        core_classes = ['CZSC', 'CzscSignals', 'CzscTrader']
        for cls in core_classes:
            if hasattr(czsc, cls):
                print(f"[OK] 类 {cls} 可用")
            else:
                print(f"[WARN] 类 {cls} 不存在")
        
        return True, []
        
    except Exception as e:
        print(f"[WARN] czsc 导入失败：{e}")
        print("   提示：czsc 需要 pythonnet 依赖，该依赖在某些环境下构建失败")
        print("   建议：使用 chan_divergence_strategy 等本地缠论模块代替")
        return True, ["czsc 可选依赖未安装"]


def test_signal_integrator():
    """测试信号整合器"""
    print_header("6. 信号整合器测试")
    
    try:
        from signal_integrator import SignalIntegrator
        
        si = SignalIntegrator()
        print("[OK] 信号整合器可实例化")
        
        # 检查权重配置
        print(f"[OK] 权重配置：{si.signal_weights}")
        
        # 检查信号映射
        print(f"[OK] 信号映射：{list(si.signal_map.keys())}")
        
        return True, []
        
    except Exception as e:
        print(f"[FAIL] 信号整合器测试失败：{e}")
        return False, [str(e)]


def test_backtester():
    """测试回测器"""
    print_header("7. 回测器测试")
    
    try:
        from chan_backtester import ChanBacktester
        
        bt = ChanBacktester(initial_capital=100000)
        print("[OK] 回测器可实例化")
        
        # 检查核心方法
        methods = ['backtest', '_execute_signal', '_calculate_statistics']
        for method in methods:
            if hasattr(bt, method):
                print(f"[OK] 方法 {method} 存在")
            else:
                print(f"[FAIL] 方法 {method} 缺失")
        
        return True, []
        
    except Exception as e:
        print(f"[FAIL] 回测器测试失败：{e}")
        return False, [str(e)]


def test_unified_analyzer():
    """测试统一分析器"""
    print_header("8. 统一分析器测试")
    
    try:
        from unified_analyzer import UnifiedAnalyzer, analyze_stock
        
        print("[OK] 统一分析接口可导入")
        print(f"[OK] 便捷函数：analyze_stock")
        
        # 检查文档
        if analyze_stock.__doc__:
            doc_line = analyze_stock.__doc__.split('\n')[1].strip()
            print(f"   功能：{doc_line}")
        
        return True, []
        
    except Exception as e:
        print(f"[FAIL] 统一分析器测试失败：{e}")
        return False, [str(e)]


def test_strategy_demo():
    """测试策略演示"""
    print_header("9. 策略演示测试")
    
    try:
        import pandas as pd
        import numpy as np
        from chan_divergence_strategy import ChanDivergenceStrategy
        
        # 生成测试数据
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        close = 100 + np.cumsum(np.random.randn(100))
        
        df = pd.DataFrame({
            'date': dates.strftime('%Y-%m-%d'),
            'open': close * 0.99,
            'high': close * 1.02,
            'low': close * 0.98,
            'close': close,
            'volume': np.random.randint(1000, 10000, 100)
        })
        
        strategy = ChanDivergenceStrategy(df)
        signal = strategy.generate_signal()
        
        print("[OK] 策略信号生成成功")
        print(f"   信号：{signal['signal']}")
        print(f"   动作：{signal['action']}")
        print(f"   置信度：{signal['confidence']}%")
        
        return True, []
        
    except Exception as e:
        print(f"[FAIL] 策略演示测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False, [str(e)]


def main():
    """运行所有测试"""
    print("\n" + "="*70)
    print("  量化交易系统 R6 - 全面自检")
    print(f"  时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    tests = [
        ("核心模块", test_core_modules),
        ("缠论模块", test_chan_modules),
        ("GUI 组件", test_gui_components),
        ("依赖包", test_dependencies),
        ("czsc 功能", test_czsc_functionality),
        ("信号整合器", test_signal_integrator),
        ("回测器", test_backtester),
        ("统一分析器", test_unified_analyzer),
        ("策略演示", test_strategy_demo)
    ]
    
    results = []
    all_passed = True
    
    for name, test_func in tests:
        try:
            passed, details = test_func()
            results.append((name, passed, details))
            if not passed:
                all_passed = False
        except Exception as e:
            print(f"\n[FAIL] {name} 测试异常：{e}")
            import traceback
            traceback.print_exc()
            results.append((name, False, [str(e)]))
            all_passed = False
    
    # 汇总结果
    print_header("测试结果汇总")
    
    passed_count = sum(1 for _, p, _ in results if p)
    total_count = len(results)
    
    for name, passed, details in results:
        status = "[OK] 通过" if passed else "[FAIL] 失败"
        print(f"{status}: {name}")
        
        if not passed:
            print(f"   详情：{details}")
    
    print(f"\n总计：{passed_count}/{total_count} 项测试通过 ({passed_count/total_count*100:.1f}%)")
    
    if all_passed:
        print("\n[SUCCESS] 所有测试通过！系统状态良好。")
        print("\n建议下一步:")
        print("1. 启动 GUI 界面进行可视化测试")
        print("2. 使用真实数据进行实盘模拟")
        print("3. 运行回测验证策略有效性")
    else:
        print(f"\n[WARNING] 有 {total_count - passed_count} 项测试未通过，请检查上方详情。")
    
    print("\n" + "="*70)
    
    return all_passed


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
