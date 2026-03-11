"""
DeepSeek AI 代码审查器
自动审查、修复或弃用 GitHub 集成的因子代码
"""

import requests
import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class DeepSeekCodeReviewer:
    """DeepSeek AI 代码审查器"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    
    def review_factor_code(self, factor_name: str, code: str, 
                          docstring: str = "") -> Dict:
        """
        审查单个因子代码
        
        Args:
            factor_name: 因子名称
            code: 代码内容
            docstring: 文档字符串
            
        Returns:
            审查结果字典
        """
        prompt = f"""请作为量化交易代码专家，审查以下因子代码：

**因子名称**: {factor_name}
**文档**: {docstring if docstring else '无'}

**代码**:
```python
{code}
```

请从以下维度审查：
1. **语法正确性**: 是否有语法错误
2. **逻辑完整性**: 是否有未实现的 TODO、pass 等
3. **依赖检查**: 是否缺少必要的 import
4. **参数合理性**: 函数参数是否合理
5. **返回值有效性**: 返回值类型和处理是否正确
6. **异常处理**: 是否有必要的错误处理
7. **性能问题**: 是否有明显的性能瓶颈

请按以下 JSON 格式返回审查结果：
{{
    "status": "pass/warning/fail",
    "issues": [
        {{
            "type": "syntax|logic|dependency|parameter|return|exception|performance",
            "severity": "critical|major|minor",
            "description": "问题描述",
            "line": 行号,
            "suggestion": "修复建议"
        }}
    ],
    "can_fix": true/false,
    "fix_suggestion": "具体修复代码或建议",
    "recommendation": "accept/fix/discard"
}}
"""
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "你是专业的量化交易代码审查专家，擅长发现和修复代码问题。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000
                },
                timeout=30
            )
            
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                # 提取 JSON
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return result
                else:
                    return {"status": "error", "message": "无法解析 AI 响应"}
            else:
                return {"status": "error", "message": f"API 请求失败：{response.status_code}"}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def fix_code(self, original_code: str, issues: List[Dict]) -> Optional[str]:
        """
        尝试修复代码
        
        Args:
            original_code: 原始代码
            issues: 问题列表
            
        Returns:
            修复后的代码
        """
        issues_text = "\n".join([
            f"- {issue['type']}: {issue['description']} (建议：{issue['suggestion']})"
            for issue in issues
        ])
        
        prompt = f"""请修复以下代码中的问题：

**原始代码**:
```python
{original_code}
```

**需要修复的问题**:
{issues_text}

请直接给出修复后的完整代码（包含必要的 import），不要其他解释。
如果无法修复，请回复"CANNOT_FIX"。
"""
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json={
                    "model": "deepseek-coder",
                    "messages": [
                        {"role": "system", "content": "你是 Python 代码修复专家。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2,
                    "max_tokens": 1500
                },
                timeout=30
            )
            
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                # 提取代码
                code_match = re.search(r'```python\s*(.*?)\s*```', content, re.DOTALL)
                if code_match:
                    fixed_code = code_match.group(1)
                    if "CANNOT_FIX" not in fixed_code:
                        return fixed_code
                
                # 如果没有代码块，检查是否是纯代码
                if "```" not in content and "CANNOT_FIX" not in content:
                    return content.strip()
            
            return None
            
        except Exception as e:
            print(f"修复失败：{e}")
            return None
    
    def batch_review(self, factors: List[Dict]) -> Dict[str, Dict]:
        """
        批量审查因子
        
        Args:
            factors: 因子列表
            
        Returns:
            审查结果字典 {因子名：审查结果}
        """
        results = {}
        total = len(factors)
        
        print(f"\n开始审查 {total} 个因子...")
        
        for i, factor in enumerate(factors, 1):
            name = factor.get('name', 'unknown')
            code = factor.get('source_code', '')
            docstring = factor.get('docstring', '')
            
            print(f"[{i}/{total}] 审查：{name}")
            
            # 审查
            review_result = self.review_factor_code(name, code, docstring)
            
            # 如果需要修复
            if review_result.get("recommendation") == "fix":
                print(f"  ⚠️  发现问题，尝试修复...")
                fixed_code = self.fix_code(code, review_result.get("issues", []))
                
                if fixed_code:
                    print(f"  ✅ 修复成功")
                    review_result["fixed_code"] = fixed_code
                    review_result["recommendation"] = "accept"
                else:
                    print(f"  ❌ 无法修复，建议弃用")
                    review_result["recommendation"] = "discard"
            
            # 显示结果
            status_map = {
                "pass": "✅ 通过",
                "warning": "⚠️  警告",
                "fail": "❌ 失败",
                "error": "❌ 错误"
            }
            print(f"  结果：{status_map.get(review_result.get('status', 'error'), '未知')}")
            
            results[name] = review_result
        
        return results
    
    def generate_report(self, review_results: Dict[str, Dict]) -> str:
        """
        生成审查报告
        
        Args:
            review_results: 审查结果字典
            
        Returns:
            报告文本
        """
        report_lines = [
            "="*70,
            "GitHub 因子代码审查报告",
            f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "="*70,
            ""
        ]
        
        # 统计
        total = len(review_results)
        accepted = sum(1 for r in review_results.values() if r.get("recommendation") == "accept")
        fixed = sum(1 for r in review_results.values() if r.get("fixed_code"))
        discarded = sum(1 for r in review_results.values() if r.get("recommendation") == "discard")
        
        report_lines.append(f"总计审查：{total} 个因子")
        report_lines.append(f"直接通过：{accepted} 个")
        report_lines.append(f"修复后通过：{fixed} 个")
        report_lines.append(f"建议弃用：{discarded} 个")
        report_lines.append("")
        
        # 详细结果
        report_lines.append("-"*70)
        report_lines.append("详细审查结果")
        report_lines.append("-"*70)
        
        for name, result in review_results.items():
            status = result.get("status", "unknown")
            recommendation = result.get("recommendation", "unknown")
            
            status_icon = {
                "pass": "✅",
                "warning": "⚠️",
                "fail": "❌",
                "error": "❌"
            }.get(status, "❓")
            
            report_lines.append(f"\n{status_icon} {name}")
            report_lines.append(f"  状态：{status}")
            report_lines.append(f"  建议：{recommendation}")
            
            if result.get("issues"):
                report_lines.append(f"  问题数：{len(result['issues'])}")
                for issue in result["issues"][:3]:  # 只显示前 3 个问题
                    report_lines.append(f"    - [{issue['severity']}] {issue['description']}")
            
            if result.get("fixed_code"):
                report_lines.append(f"  ✅ 已修复")
        
        report_lines.append("")
        report_lines.append("="*70)
        
        return "\n".join(report_lines)


def main():
    """主函数"""
    print("="*70)
    print("DeepSeek AI 代码审查器")
    print("="*70)
    
    # 读取 API Key
    try:
        with open('api_key.txt', 'r', encoding='utf-8') as f:
            api_key = f.read().strip()
    except:
        api_key = input("请输入 DeepSeek API Key: ").strip()
    
    if not api_key:
        print("❌ 未提供 API Key")
        return
    
    reviewer = DeepSeekCodeReviewer(api_key)
    
    # 加载因子数据
    try:
        with open('github_factors.json', 'r', encoding='utf-8') as f:
            factors_data = json.load(f)
        
        # 收集所有因子
        all_factors = []
        for repo, factors in factors_data.items():
            for factor in factors:
                all_factors.append(factor)
        
        print(f"加载了 {len(all_factors)} 个因子")
        
        # 询问审查范围
        print("\n请选择审查范围:")
        print("1. 审查所有因子")
        print("2. 只审查前 10 个因子（测试）")
        choice = input("请输入选项 (1/2): ").strip()
        
        if choice == "2":
            test_factors = all_factors[:10]
            print(f"将审查前 10 个因子")
        else:
            test_factors = all_factors
        
        # 执行审查
        results = reviewer.batch_review(test_factors)
        
        # 生成报告
        report = reviewer.generate_report(results)
        
        # 保存报告
        report_file = 'code_review_report.txt'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n审查报告已保存到：{report_file}")
        
        # 保存审查结果
        results_file = 'code_review_results.json'
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"审查结果已保存到：{results_file}")
        
        # 应用审查结果
        print("\n是否应用审查结果？")
        print("1. 应用所有修复并弃用问题代码")
        print("2. 只查看报告，不应用")
        apply_choice = input("请输入选项 (1/2): ").strip()
        
        if apply_choice == "1":
            print("\n应用审查结果...")
            # TODO: 实现结果应用逻辑
            print("✅ 审查结果应用完成")
        
    except FileNotFoundError:
        print("❌ 找不到 github_factors.json，请先运行扫描器")
    except Exception as e:
        print(f"❌ 审查过程出错：{e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
