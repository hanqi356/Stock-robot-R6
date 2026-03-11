"""
GitHub 因子自动下载与集成工具
下载因子代码并集成到现有系统
"""

import os
import re
import json
from typing import Dict, List, Optional
from datetime import datetime
import shutil


class GitHubFactorIntegrator:
    """GitHub 因子集成器"""
    
    def __init__(self, target_dir: str = '.'):
        self.target_dir = target_dir
        self.factors_file = 'github_factors.json'
        self.backup_dir = 'backup_factors'
        
    def load_factors_data(self) -> Optional[Dict]:
        """加载因子数据"""
        if not os.path.exists(self.factors_file):
            print(f"因子文件不存在：{self.factors_file}")
            return None
        
        with open(self.factors_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def create_backup(self):
        """备份现有的因子模块"""
        if not os.path.exists('panda_factor_integration.py'):
            return
        
        os.makedirs(self.backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(self.backup_dir, f'panda_factor_integration_{timestamp}.py')
        shutil.copy2('panda_factor_integration.py', backup_file)
        print(f"已备份现有因子模块：{backup_file}")
    
    def parse_factor_code(self, code: str, func_name: str) -> Optional[Dict]:
        """
        解析因子代码
        
        Args:
            code: 完整代码
            func_name: 函数名
            
        Returns:
            因子信息字典
        """
        # 查找函数定义
        pattern = rf'def\s+{func_name}\s*\(([^)]*)\):'
        match = re.search(pattern, code)
        
        if not match:
            return None
        
        params = [p.strip() for p in match.group(1).split(',')]
        
        # 提取函数体
        start_pos = match.end()
        lines = code[start_pos:].split('\n')
        
        func_body_lines = []
        indent_level = 0
        for line in lines:
            stripped = line.lstrip()
            if stripped and not stripped.startswith('#'):
                current_indent = len(line) - len(stripped)
                if current_indent <= indent_level and func_body_lines:
                    break
            func_body_lines.append(line)
        
        return {
            'name': func_name,
            'params': params,
            'body': '\n'.join(func_body_lines),
            'source_code': match.group(0) + '\n' + '\n'.join(func_body_lines)
        }
    
    def generate_factor_wrapper(self, factor_info: Dict, repo: str) -> str:
        """
        生成因子包装代码
        
        Args:
            factor_info: 因子信息
            repo: 来源仓库
            
        Returns:
            包装代码字符串
        """
        wrapper = f"""
    @staticmethod
    def {factor_info['name']}_github({', '.join(factor_info['params'])}):
        '''
        从 {repo} 导入的因子
        '''
        try:
            # TODO: 需要实现具体逻辑
            # 这里是占位符，实际使用时需要替换为真实代码
            pass
        except Exception as e:
            print(f"因子 {{factor_info['name']}} 计算失败：{{e}}")
            return None
"""
        return wrapper
    
    def integrate_to_calculator(self, new_factors: List[Dict]):
        """
        集成新因子到 FactorCalculator
        
        Args:
            new_factors: 新因子列表
        """
        calculator_file = 'panda_factor_integration.py'
        
        if not os.path.exists(calculator_file):
            print(f"找不到因子计算器文件：{calculator_file}")
            return
        
        # 读取现有代码
        with open(calculator_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 找到 FactorCalculator 类
        class_pattern = r'(class FactorCalculator:.*?)(\n\nclass|\Z)'
        match = re.search(class_pattern, content, re.DOTALL)
        
        if not match:
            print("找不到 FactorCalculator 类")
            return
        
        class_start = match.start()
        class_end = match.end(1)
        
        # 在类末尾添加新方法
        insert_pos = class_end
        
        # 生成新方法代码
        new_methods = []
        for factor in new_factors:
            method_code = f"""
    @staticmethod
    def {factor['name']}(df):
        '''
        {factor.get('docstring', 'GitHub 因子')}
        来源：{factor.get('repo', 'Unknown')}
        '''
        # TODO: 实现因子计算逻辑
        # 这是一个占位符，需要根据实际情况实现
        if 'close' in df.columns:
            result = pd.Series(index=df.index)
            return result
        return None
"""
            new_methods.append(method_code)
        
        # 插入新方法
        if new_methods:
            new_content = (
                content[:insert_pos] + 
                '\n'.join(new_methods) + 
                content[insert_pos:]
            )
            
            # 写回文件
            with open(calculator_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"已添加 {len(new_methods)} 个新因子到 FactorCalculator")
    
    def update_calculate_factors_method(self, new_factor_names: List[str]):
        """
        更新 calculate_factors 方法，调用新因子
        
        Args:
            new_factor_names: 新因子名称列表
        """
        calculator_file = 'panda_factor_integration.py'
        
        with open(calculator_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 找到 calculate_factors 方法中的 factors 赋值部分
        pattern = r"(factors\['[\w_]+'] = .+?\n)"
        matches = list(re.finditer(pattern, content))
        
        if matches:
            # 在最后一个因子后面添加新因子
            last_match = matches[-1]
            insert_pos = last_match.end()
            
            # 生成调用代码
            new_calls = []
            for name in new_factor_names[:5]:  # 限制添加 5 个调用
                call_code = f"\n        # GitHub 因子\n        factors['{name}'] = self.calculator.{name}(df)"
                new_calls.append(call_code)
            
            if new_calls:
                new_content = (
                    content[:insert_pos] + 
                    ''.join(new_calls) + 
                    content[insert_pos:]
                )
                
                with open(calculator_file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                print(f"已在 calculate_factors 中添加 {len(new_calls)} 个因子调用")
    
    def create_github_factors_module(self, factors_data: Dict):
        """
        创建独立的 GitHub 因子模块
        
        Args:
            factors_data: 因子数据
        """
        module_content = '''# -*- coding: utf-8 -*-
"""
GitHub 因子库集成模块
自动从 GitHub 仓库收集和集成量化因子
"""

import pandas as pd
import numpy as np
from typing import Dict, List


class GitHubFactors:
    """GitHub 因子集合"""
    
    def __init__(self):
        pass
    
'''
        
        # 为每个仓库创建方法
        count = 0
        for repo, factors in factors_data.items():
            module_content += f'\n    # ===== Factors from {repo} =====\n'
            
            for factor in factors[:5]:  # 每个仓库选 5 个因子
                method_code = f'''
    @staticmethod
    def {factor['name']}(df):
        """
        {factor.get('docstring', 'GitHub 因子')}
        
        Source: {repo}
        File: {factor.get('file', 'Unknown')}
        """
        # TODO: 实现具体逻辑
        # 建议参考原仓库的实现
        if 'close' not in df.columns:
            return None
        
        # 示例实现（需要根据实际代码修改）
        close = df['close']
        result = pd.Series(index=df.index)
        return result

'''
                module_content += method_code
                count += 1
        
        # 保存文件
        with open('github_factors.py', 'w', encoding='utf-8') as f:
            f.write(module_content)
        
        print(f"已创建 GitHub 因子模块：github_factors.py (包含 {count} 个因子)")
    
    def run_integration(self):
        """运行集成流程"""
        print("="*70)
        print("GitHub 因子自动集成工具")
        print("="*70)
        
        # 1. 加载因子数据
        print("\n[1/5] 加载因子数据...")
        factors_data = self.load_factors_data()
        
        if not factors_data:
            print("请先运行 github_factor_scanner.py 生成因子数据")
            return False
        
        total_factors = sum(len(f) for f in factors_data.values())
        print(f"加载了 {total_factors} 个因子")
        
        # 2. AI 代码审查（新增）
        print("\n[2/5] DeepSeek AI 代码审查...")
        review_choice = input("是否使用 DeepSeek AI 审查代码？(y/n): ").strip().lower()
        
        if review_choice == 'y':
            try:
                # 读取 API Key
                try:
                    with open('api_key.txt', 'r', encoding='utf-8') as f:
                        api_key = f.read().strip()
                except:
                    api_key = input("请输入 DeepSeek API Key: ").strip()
                
                if api_key:
                    from deepseek_code_reviewer import DeepSeekCodeReviewer
                    reviewer = DeepSeekCodeReviewer(api_key)
                    
                    # 收集所有因子
                    all_factors = []
                    for repo, factors in factors_data.items():
                        for factor in factors:
                            factor['repo'] = repo
                            all_factors.append(factor)
                    
                    # 批量审查（限制前 20 个）
                    test_factors = all_factors[:20]
                    review_results = reviewer.batch_review(test_factors)
                    
                    # 生成报告
                    report = reviewer.generate_report(review_results)
                    with open('code_review_report.txt', 'w', encoding='utf-8') as f:
                        f.write(report)
                    
                    # 应用审查结果
                    accepted_count = 0
                    discarded_count = 0
                    fixed_count = 0
                    
                    for name, result in review_results.items():
                        if result.get('recommendation') == 'accept':
                            accepted_count += 1
                            if result.get('fixed_code'):
                                # 更新因子代码
                                for factor in all_factors:
                                    if factor['name'] == name:
                                        factor['source_code'] = result['fixed_code']
                                        fixed_count += 1
                        elif result.get('recommendation') == 'discard':
                            discarded_count += 1
                            # 从数据中移除
                            factors_data = self._remove_factor(factors_data, name)
                    
                    print(f"\n审查完成:")
                    print(f"  ✅ 通过：{accepted_count} 个")
                    print(f"  🔧 修复：{fixed_count} 个")
                    print(f"  ❌ 弃用：{discarded_count} 个")
                    print(f"\n审查报告已保存到：code_review_report.txt")
                else:
                    print("⚠️  未提供 API Key，跳过 AI 审查")
                    
            except Exception as e:
                print(f"⚠️  AI 审查失败：{e}，将继续执行...")
        else:
            print("⚠️  跳过 AI 审查")
        
        # 3. 备份现有模块
        print("\n[3/5] 备份现有模块...")
        self.create_backup()
        
        # 4. 创建独立模块
        print("\n[4/5] 创建 GitHub 因子模块...")
        self.create_github_factors_module(factors_data)
        
        # 5. 集成到现有系统（可选）
        print("\n[5/5] 是否集成到 panda_factor_integration.py?")
        choice = input("警告：这会修改现有文件。是否继续？(y/n): ").strip().lower()
        
        if choice == 'y':
            # 收集所有因子
            all_factors = []
            for repo, factors in factors_data.items():
                for factor in factors:
                    factor['repo'] = repo
                    all_factors.append(factor)
            
            # 只集成前 10 个因子作为测试
            sample_factors = all_factors[:10]
            self.integrate_to_calculator(sample_factors)
            
            print("\n✅ 集成完成！")
            print("\n下一步:")
            print("1. 检查 github_factors.py 查看新增因子")
            print("2. 手动实现因子的具体计算逻辑")
            print("3. 测试新因子的计算结果")
        else:
            print("\n⚠️  已取消集成到现有系统")
            print("可以手动复制 github_factors.py 中的代码")
        
        return True
    
    def _remove_factor(self, factors_data: Dict, factor_name: str) -> Dict:
        """从数据中移除指定的因子"""
        for repo, factors in factors_data.items():
            factors_data[repo] = [f for f in factors if f.get('name') != factor_name]
        return factors_data


def main():
    """主函数"""
    integrator = GitHubFactorIntegrator()
    success = integrator.run_integration()
    return success


if __name__ == '__main__':
    main()
