"""
AI股票分析模块
提供智能股票分析、买卖点建议、风险评估
"""

import json
import requests
from typing import Dict, List, Optional
from datetime import datetime


class BailianAIAnalyzer:
    """
    AI 分析器（支持阿里云百炼和 DeepSeek）
    
    功能：
    1. 股票趋势分析
    2. 买卖点建议
    3. 风险评估
    4. 技术指标解读
    
    支持的模型：
    - 阿里云百炼：qwen-max, qwen-plus, qwen-turbo, qwen-long
    - DeepSeek: deepseek-chat, deepseek-coder
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek-chat"):
        self.api_key = api_key
        self.model = model
        
        # 根据模型选择 API 端点
        if model.startswith("deepseek"):
            self.api_url = "https://api.deepseek.com/v1/chat/completions"
        else:
            # 阿里云百炼
            self.api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        
    def set_api_key(self, api_key: str):
        """设置API密钥"""
        self.api_key = api_key
        
    def analyze_stock(self, symbol: str, stock_data: Dict) -> Dict:
        """
        分析单只股票
        
        Args:
            symbol: 股票代码
            stock_data: 股票数据字典
            
        Returns:
            分析结果字典
        """
        if not self.api_key:
            return {
                'success': False,
                'error': '未设置API密钥',
                'suggestion': '请在设置中配置API密钥'
            }
        
        # 构建提示词
        prompt = self._build_analysis_prompt(symbol, stock_data)
        
        try:
            response = self._call_api(prompt)
            analysis = self._parse_response(response)
            return {
                'success': True,
                'symbol': symbol,
                'analysis': analysis,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'symbol': symbol
            }
    
    def analyze_portfolio(self, positions: List[Dict]) -> Dict:
        """
        分析整个持仓组合
        
        Args:
            positions: 持仓列表
            
        Returns:
            组合分析结果
        """
        if not self.api_key:
            return {
                'success': False,
                'error': '未设置API密钥'
            }
        
        prompt = self._build_portfolio_prompt(positions)
        
        try:
            response = self._call_api(prompt)
            analysis = self._parse_response(response)
            return {
                'success': True,
                'analysis': analysis,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_trading_advice(self, symbol: str, market_data: Dict, 
                          technical_indicators: Dict) -> Dict:
        """
        获取交易建议
        
        Args:
            symbol: 股票代码
            market_data: 市场数据
            technical_indicators: 技术指标数据
            
        Returns:
            交易建议
        """
        if not self.api_key:
            return {
                'success': False,
                'error': '未设置API密钥'
            }
        
        prompt = self._build_trading_prompt(symbol, market_data, technical_indicators)
        
        try:
            response = self._call_api(prompt)
            advice = self._parse_response(response)
            return {
                'success': True,
                'symbol': symbol,
                'advice': advice,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _build_analysis_prompt(self, symbol: str, stock_data: Dict) -> str:
        """构建股票分析提示词"""
        prompt = f"""请作为专业股票分析师，分析以下股票：

股票代码：{symbol}
当前价格：{stock_data.get('price', 'N/A')}
涨跌幅：{stock_data.get('change_pct', 'N/A')}%
成交量：{stock_data.get('volume', 'N/A')}

技术指标：
- MACD：{stock_data.get('macd', 'N/A')}
- MA5：{stock_data.get('ma5', 'N/A')}
- MA20：{stock_data.get('ma20', 'N/A')}
- RSI：{stock_data.get('rsi', 'N/A')}

请提供：
1. 趋势分析（ bullish/bearish/neutral ）
2. 关键支撑位和阻力位
3. 短期（1-3天）和中期（1-2周）展望
4. 风险提示
5. 操作建议（买入/卖出/持有）

请以JSON格式返回结果。"""
        return prompt
    
    def _build_portfolio_prompt(self, positions: List[Dict]) -> str:
        """构建组合分析提示词"""
        positions_str = "\n".join([
            f"- {p['代码']}: {p['股数']}股, 成本{p['成本价']}, 现价{p['现价']}, 盈亏{p['盈亏率']}%"
            for p in positions
        ])
        
        prompt = f"""请分析以下股票投资组合：

持仓情况：
{positions_str}

请提供：
1. 组合整体风险评估
2. 行业分布分析
3. 集中度风险
4. 优化建议
5. 调仓建议

请以JSON格式返回结果。"""
        return prompt
    
    def _build_trading_prompt(self, symbol: str, market_data: Dict, 
                             technical_indicators: Dict) -> str:
        """构建交易建议提示词"""
        prompt = f"""请基于以下数据提供交易建议：

股票：{symbol}
当前价格：{market_data.get('price', 'N/A')}
今日开盘：{market_data.get('open', 'N/A')}
今日最高：{market_data.get('high', 'N/A')}
今日最低：{market_data.get('low', 'N/A')}

技术指标：
{json.dumps(technical_indicators, ensure_ascii=False, indent=2)}

请提供：
1. 建议操作（强烈买入/买入/持有/卖出/强烈卖出）
2. 建议买入/卖出价格区间
3. 止损位设置
4. 目标价位
5. 操作建议理由

请以JSON格式返回结果。"""
        return prompt
    
    def _call_api(self, prompt: str) -> str:
        """调用 AI API（支持阿里云百炼和 DeepSeek）"""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
            
        # 根据模型构建不同的请求格式
        if self.model.startswith("deepseek"):
            # DeepSeek API (OpenAI 兼容格式)
            payload = {
                'model': self.model,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': 2000,
                'temperature': 0.7
            }
        else:
            # 阿里云百炼 API
            payload = {
                'model': self.model,
                'input': {
                    'messages': [
                        {'role': 'user', 'content': prompt}
                    ]
                },
                'parameters': {
                    'result_format': 'text',
                    'max_tokens': 2000,
                    'temperature': 0.7
                }
            }
            
        response = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=60
        )
            
        if response.status_code == 200:
            result = response.json()
            # 解析不同格式的响应
            if self.model.startswith("deepseek"):
                return result['choices'][0]['message']['content']
            else:
                return result['output']['text']
        else:
            raise Exception(f"API 调用失败：{response.status_code} - {response.text}")
    
    def _parse_response(self, response: str) -> Dict:
        """解析API响应"""
        try:
            # 尝试解析JSON
            return json.loads(response)
        except:
            # 如果不是JSON，返回文本
            return {'text': response}


# 便捷函数
def create_analyzer(api_key: Optional[str] = None) -> BailianAIAnalyzer:
    """创建AI分析器实例"""
    return BailianAIAnalyzer(api_key)


if __name__ == '__main__':
    # 测试
    print("AI分析模块")
    print("="*50)
    print("使用说明：")
    print("1. 获取API密钥")
    print("2. 创建分析器: analyzer = BailianAIAnalyzer(api_key='your_key')")
    print("3. 分析股票: result = analyzer.analyze_stock('000001', stock_data)")
