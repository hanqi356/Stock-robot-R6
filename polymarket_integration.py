# -*- coding: utf-8 -*-
"""
Polymarket 预测市场数据接入模块
提供实时市场数据获取功能
"""

import requests
import json
from datetime import datetime
from typing import List, Dict, Optional


class PolymarketClient:
    """Polymarket API客户端"""
    
    GAMMA_API_URL = "https://gamma-api.polymarket.com"
    CLOB_API_URL = "https://clob.polymarket.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_active_markets(self, limit: int = 20, order_by: str = "volume24hr") -> List[Dict]:
        """获取活跃市场列表
        
        Args:
            limit: 返回市场数量
            order_by: 排序字段 (volume24hr, liquidity, createdAt)
            
        Returns:
            市场列表
        """
        try:
            params = {
                "active": "true",
                "closed": "false",
                "limit": limit,
                "order": order_by,
                "ascending": "false"
            }
            
            response = self.session.get(
                f"{self.GAMMA_API_URL}/markets",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            markets = response.json()
            return self._format_markets(markets)
            
        except Exception as e:
            print(f"获取Polymarket市场数据失败: {str(e)}")
            return []
    
    def get_market_by_id(self, market_id: str) -> Optional[Dict]:
        """获取特定市场详情
        
        Args:
            market_id: 市场ID
            
        Returns:
            市场详情
        """
        try:
            response = self.session.get(
                f"{self.GAMMA_API_URL}/markets/{market_id}",
                timeout=10
            )
            response.raise_for_status()
            
            market = response.json()
            return self._format_market(market)
            
        except Exception as e:
            print(f"获取市场详情失败: {str(e)}")
            return None
    
    def search_markets(self, query: str, limit: int = 10) -> List[Dict]:
        """搜索市场
        
        Args:
            query: 搜索关键词
            limit: 返回数量
            
        Returns:
            搜索结果
        """
        try:
            params = {
                "active": "true",
                "archived": "false",
                "closed": "false",
                "limit": limit,
                "offset": 0,
                "sort": "volume24hr",
                "order": "desc"
            }
            
            response = self.session.get(
                f"{self.GAMMA_API_URL}/markets",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            markets = response.json()
            # 本地过滤
            filtered = [m for m in markets if query.lower() in m.get('question', '').lower()]
            return self._format_markets(filtered[:limit])
            
        except Exception as e:
            print(f"搜索市场失败: {str(e)}")
            return []
    
    def get_trending_markets(self, limit: int = 10) -> List[Dict]:
        """获取热门市场（按24小时交易量排序）
        
        Args:
            limit: 返回数量
            
        Returns:
            热门市场列表
        """
        return self.get_active_markets(limit=limit, order_by="volume24hr")
    
    def get_market_orderbook(self, token_id: str) -> Optional[Dict]:
        """获取市场订单簿
        
        Args:
            token_id: 代币ID
            
        Returns:
            订单簿数据
        """
        try:
            response = self.session.get(
                f"{self.CLOB_API_URL}/book/{token_id}",
                timeout=10
            )
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            print(f"获取订单簿失败: {str(e)}")
            return None
    
    def _format_markets(self, markets: List[Dict]) -> List[Dict]:
        """格式化市场数据"""
        return [self._format_market(m) for m in markets if self._format_market(m)]
    
    def _format_market(self, market: Dict) -> Optional[Dict]:
        """格式化单个市场数据"""
        try:
            # 获取最佳价格
            outcomes = market.get('outcomes', [])
            prices = []
            for outcome in outcomes:
                price = outcome.get('price', 0)
                if price:
                    prices.append(price)
            
            best_price = max(prices) if prices else 0
            
            return {
                'id': market.get('id'),
                'question': market.get('question', 'Unknown'),
                'description': market.get('description', '')[:200] + '...' if len(market.get('description', '')) > 200 else market.get('description', ''),
                'category': market.get('category', 'Other'),
                'volume_24h': market.get('volume24hr', 0),
                'total_volume': market.get('volume', 0),
                'liquidity': market.get('liquidity', 0),
                'best_price': best_price,
                'outcomes': [o.get('name', 'Unknown') for o in outcomes],
                'end_date': market.get('endDate', 'Unknown'),
                'created_at': market.get('createdAt'),
                'icon': market.get('icon', ''),
                'active': market.get('active', False)
            }
            
        except Exception as e:
            print(f"格式化市场数据失败: {str(e)}")
            return None
    
    def get_market_summary(self) -> Dict:
        """获取市场摘要统计"""
        try:
            markets = self.get_active_markets(limit=100)
            
            if not markets:
                return {'error': '无法获取市场数据'}
            
            total_volume = sum(m['volume_24h'] for m in markets)
            total_liquidity = sum(m['liquidity'] for m in markets)
            
            # 按类别分组
            categories = {}
            for m in markets:
                cat = m['category']
                if cat not in categories:
                    categories[cat] = {'count': 0, 'volume': 0}
                categories[cat]['count'] += 1
                categories[cat]['volume'] += m['volume_24h']
            
            return {
                'total_markets': len(markets),
                'total_volume_24h': total_volume,
                'total_liquidity': total_liquidity,
                'top_markets': markets[:5],
                'categories': categories
            }
            
        except Exception as e:
            return {'error': str(e)}


# 便捷函数
def get_polymarket_client() -> PolymarketClient:
    """获取Polymarket客户端实例"""
    return PolymarketClient()


def get_hot_markets(limit: int = 10) -> List[Dict]:
    """获取热门市场"""
    client = PolymarketClient()
    return client.get_trending_markets(limit)


def format_market_for_display(market: Dict) -> str:
    """格式化市场信息用于显示"""
    return f"""
市场: {market.get('question', 'Unknown')}
类别: {market.get('category', 'Other')}
24h交易量: ${market.get('volume_24h', 0):,.2f}
最佳价格: {market.get('best_price', 0):.4f}
选项: {', '.join(market.get('outcomes', []))}
结束时间: {market.get('end_date', 'Unknown')}
"""


if __name__ == "__main__":
    # 测试
    client = PolymarketClient()
    markets = client.get_trending_markets(5)
    
    print("=== Polymarket 热门市场 ===")
    for market in markets:
        print(format_market_for_display(market))
        print("-" * 50)
