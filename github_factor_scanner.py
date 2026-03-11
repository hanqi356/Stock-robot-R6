"""
GitHub 因子库自动扫描器
扫描 GitHub 上的量化因子库并自动集成
"""

import requests
import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import os


class GitHubFactorScanner:
    """GitHub 因子库扫描器"""
    
    def __init__(self):
        self.github_api = "https://api.github.com"
        self.session = requests.Session()
        
        # 热门量化因子仓库列表
        self.factor_repos = [
            'microsoft/qlib',
            'QuantLib/QuantLib',
            'polarsource/polars',
            'pydata/xarray',
            'quantopian/alphalens',
            'quantopian/pyfolio',
            'empyrical/empyrical',
            'ranaroussi/yfinance',
            'akfamily/akshare',
            'shidenggui/easyquotation',
            'refraction-ray/xalpha',
            'cosname/cosx.org',
        ]
        
        # 因子关键词
        self.factor_keywords = [
            'factor',
            'alpha',
            'momentum',
            'volatility',
            'rsi',
            'macd',
            'bollinger',
            'quant',
            'technical',
            'indicator'
        ]
    
    def search_repositories(self, query: str, limit: int = 10) -> List[Dict]:
        """
        搜索 GitHub 仓库
        
        Args:
            query: 搜索关键词
            limit: 返回数量限制
            
        Returns:
            仓库列表
        """
        url = f"{self.github_api}/search/repositories"
        params = {
            'q': query,
            'sort': 'stars',
            'order': 'desc',
            'per_page': min(limit, 100)
        }
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get('items', [])
        except Exception as e:
            print(f"搜索失败：{e}")
            return []
    
    def get_repo_contents(self, owner: str, repo: str, path: str = "") -> List[Dict]:
        """
        获取仓库文件列表
        
        Args:
            owner: 仓库所有者
            repo: 仓库名
            path: 路径
            
        Returns:
            文件列表
        """
        url = f"{self.github_api}/repos/{owner}/{repo}/contents/{path}"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取内容失败：{e}")
            return []
    
    def download_file(self, owner: str, repo: str, path: str) -> Optional[str]:
        """
        下载文件内容
        
        Args:
            owner: 仓库所有者
            repo: 仓库名
            path: 文件路径
            
        Returns:
            文件内容
        """
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{path}"
        
        try:
            response = self.session.get(url)
            if response.status_code == 200:
                return response.text
            else:
                # 尝试 master 分支
                url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/{path}"
                response = self.session.get(url)
                if response.status_code == 200:
                    return response.text
        except Exception as e:
            print(f"下载失败：{e}")
        
        return None
    
    def extract_factors_from_code(self, code: str) -> List[Dict]:
        """
        从代码中提取因子定义
        
        Args:
            code: Python 代码
            
        Returns:
            因子列表
        """
        factors = []
        
        # 匹配函数定义
        func_pattern = r'def\s+(\w+_?(?:factor|alpha|indicator|signal))\s*\([^)]*\):'
        matches = re.finditer(func_pattern, code, re.IGNORECASE)
        
        for match in matches:
            func_name = match.group(1)
            start_line = code[:match.start()].count('\n') + 1
            
            # 提取函数文档字符串
            docstring_match = re.search(r'("""|\'\'\')(.*?)\1', code[match.end():match.end()+500], re.DOTALL)
            docstring = docstring_match.group(2) if docstring_match else ""
            
            factors.append({
                'name': func_name,
                'line': start_line,
                'docstring': docstring.strip() if docstring else "",
                'source': 'github'
            })
        
        return factors
    
    def scan_repository(self, owner: str, repo: str) -> List[Dict]:
        """
        扫描单个仓库的因子
        
        Args:
            owner: 仓库所有者
            repo: 仓库名
            
        Returns:
            因子列表
        """
        print(f"\n正在扫描：{owner}/{repo}")
        factors = []
        
        # 获取根目录
        contents = self.get_repo_contents(owner, repo)
        
        # 递归扫描 Python 文件
        python_files = self._find_python_files(owner, repo, contents, max_depth=3)
        
        for file_info in python_files:
            code = self.download_file(owner, repo, file_info['path'])
            if code:
                file_factors = self.extract_factors_from_code(code)
                for factor in file_factors:
                    factor['file'] = file_info['path']
                    factor['repo'] = f"{owner}/{repo}"
                    factors.append(factor)
        
        print(f"  发现 {len(factors)} 个因子")
        return factors
    
    def _find_python_files(self, owner: str, repo: str, contents: List[Dict], 
                          depth: int = 0, max_depth: int = 3) -> List[Dict]:
        """
        递归查找 Python 文件
        
        Args:
            owner: 仓库所有者
            repo: 仓库名
            contents: 文件列表
            depth: 当前深度
            max_depth: 最大深度
            
        Returns:
            Python 文件列表
        """
        python_files = []
        
        if depth > max_depth:
            return python_files
        
        for item in contents:
            if item['type'] == 'file' and item['name'].endswith('.py'):
                # 跳过测试和示例文件
                if not any(keyword in item['path'].lower() for keyword in ['test', 'example', 'demo']):
                    python_files.append(item)
            elif item['type'] == 'dir' and not item['name'].startswith('.'):
                # 递归扫描子目录
                sub_contents = self.get_repo_contents(owner, repo, item['path'])
                python_files.extend(
                    self._find_python_files(owner, repo, sub_contents, depth + 1, max_depth)
                )
        
        return python_files
    
    def scan_all_repos(self) -> Dict[str, List[Dict]]:
        """
        扫描所有预定义仓库
        
        Returns:
            按仓库分类的因子字典
        """
        all_factors = {}
        
        for repo_full in self.factor_repos:
            try:
                owner, repo = repo_full.split('/')
                factors = self.scan_repository(owner, repo)
                if factors:
                    all_factors[repo_full] = factors
            except Exception as e:
                print(f"扫描 {repo_full} 失败：{e}")
        
        return all_factors
    
    def search_factor_repos(self, keywords: List[str] = None) -> List[Dict]:
        """
        搜索包含因子的仓库
        
        Args:
            keywords: 关键词列表
            
        Returns:
            相关仓库列表
        """
        if keywords is None:
            keywords = self.factor_keywords
        
        all_repos = []
        seen_repos = set()
        
        for keyword in keywords:
            repos = self.search_repositories(f"{keyword} quant factor", limit=5)
            for repo in repos:
                repo_key = f"{repo['full_name']}"
                if repo_key not in seen_repos:
                    seen_repos.add(repo_key)
                    all_repos.append(repo)
        
        return all_repos
    
    def save_factors_to_file(self, factors_data: Dict[str, List[Dict]], 
                            output_file: str = 'github_factors.json'):
        """
        保存因子数据到文件
        
        Args:
            factors_data: 因子数据
            output_file: 输出文件名
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(factors_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n因子数据已保存到：{output_file}")
    
    def generate_integration_code(self, factors_data: Dict[str, List[Dict]]) -> str:
        """
        生成集成代码
        
        Args:
            factors_data: 因子数据
            
        Returns:
            Python 代码字符串
        """
        code_lines = [
            "# -*- coding: utf-8 -*-",
            '"""',
            'GitHub 因子库自动集成模块',
            f'生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
            '"""',
            '',
            'import pandas as pd',
            'import numpy as np',
            '',
            '',
            'class GitHubFactorsIntegration:',
            '    """GitHub 因子集成类"""',
            '',
            '    def __init__(self):',
            '        self.factors = {}',
            '',
        ]
        
        # 为每个仓库生成集成代码
        for repo, factors in factors_data.items():
            code_lines.append(f'    # Factors from {repo}')
            for factor in factors[:10]:  # 限制每个仓库 10 个因子
                func_name = factor['name']
                code_lines.append(f'    def {func_name}(self, df):')
                code_lines.append(f'        """{factor["docstring"][:50]}..."""')
                code_lines.append(f'        # TODO: Implement factor logic')
                code_lines.append(f'        return pd.Series(index=df.index)')
                code_lines.append('')
        
        return '\n'.join(code_lines)


def main():
    """主函数"""
    print("="*70)
    print("GitHub 因子库自动扫描器")
    print("="*70)
    
    scanner = GitHubFactorScanner()
    
    # 选项 1: 扫描预定义仓库
    print("\n[模式 1] 扫描预定义的量化因子仓库...")
    factors_data = scanner.scan_all_repos()
    
    # 选项 2: 搜索相关仓库
    print("\n[模式 2] 搜索 GitHub 上的因子仓库...")
    related_repos = scanner.search_factor_repos()
    print(f"发现 {len(related_repos)} 个相关仓库")
    
    # 保存结果
    if factors_data:
        total_factors = sum(len(factors) for factors in factors_data.values())
        print(f"\n总计发现 {total_factors} 个因子")
        
        # 保存到 JSON
        scanner.save_factors_to_file(factors_data)
        
        # 生成集成代码
        integration_code = scanner.generate_integration_code(factors_data)
        with open('github_factors_auto.py', 'w', encoding='utf-8') as f:
            f.write(integration_code)
        print(f"集成代码已保存到：github_factors_auto.py")
    else:
        print("\n未发现因子")


if __name__ == '__main__':
    main()
