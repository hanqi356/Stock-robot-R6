# -*- coding: utf-8 -*-
"""
智能监控管理器
自动扫描、策略筛选、动态添加/移除监控股票
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Callable, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import json
import os
from enum import Enum

from stock_scanner import StockScanner, scan_watch_list
from chan_stock_picker import ChanStockPicker, ChanPickResult
from stock_data import get_stock_data


class SignalType(Enum):
    """信号类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    EXPIRED = "expired"


@dataclass
class WatchItem:
    """监控项"""
    code: str
    name: str = ""
    added_time: datetime = field(default_factory=datetime.now)
    last_update: datetime = field(default_factory=datetime.now)
    score: int = 0
    signal_type: str = "hold"
    signal_description: str = ""
    consecutive_count: int = 0  # 连续符合策略次数
    expired: bool = False
    
    def to_dict(self) -> Dict:
        return {
            'code': self.code,
            'name': self.name,
            'added_time': self.added_time.isoformat(),
            'last_update': self.last_update.isoformat(),
            'score': self.score,
            'signal_type': self.signal_type,
            'signal_description': self.signal_description,
            'consecutive_count': self.consecutive_count,
            'expired': self.expired
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'WatchItem':
        item = cls(
            code=data['code'],
            name=data.get('name', ''),
            score=data.get('score', 0),
            signal_type=data.get('signal_type', 'hold'),
            signal_description=data.get('signal_description', ''),
            consecutive_count=data.get('consecutive_count', 0),
            expired=data.get('expired', False)
        )
        item.added_time = datetime.fromisoformat(data['added_time'])
        item.last_update = datetime.fromisoformat(data['last_update'])
        return item


@dataclass
class SmartWatchConfig:
    """智能监控配置"""
    # 添加条件
    min_score_to_add: int = 60          # 最低评分才添加
    consecutive_required: int = 2       # 连续几次符合才添加
    max_watch_count: int = 50           # 最大监控数量
    
    # 移除条件
    expire_days: int = 7                # 信号过期天数
    min_score_to_keep: int = 40         # 低于此分数移除
    max_consecutive_fail: int = 3       # 连续几次不符合就移除
    
    # 扫描设置
    scan_interval_seconds: int = 60     # 扫描间隔
    auto_add_enabled: bool = True       # 自动添加
    auto_remove_enabled: bool = True    # 自动移除
    
    # 策略权重
    use_tdx_scanner: bool = True        # 使用通达信扫描
    use_chan_picker: bool = True        # 使用缠论选股
    tdx_weight: float = 0.4             # 通达信权重
    chan_weight: float = 0.6            # 缠论权重


class SmartWatchManager:
    """
    智能监控管理器
    
    功能：
    1. 自动扫描全市场或指定股票池
    2. 根据策略筛选符合条件的股票
    3. 自动添加到监控列表
    4. 自动移除过期或不符合条件的股票
    """
    
    def __init__(self, config: SmartWatchConfig = None):
        self.config = config or SmartWatchConfig()
        self.watch_items: Dict[str, WatchItem] = {}
        self.tdx_scanner = StockScanner(score_threshold=self.config.min_score_to_add)
        self.chan_picker = ChanStockPicker(min_score=self.config.min_score_to_add)
        
        # 候选池（用于自动添加）
        self.candidate_pool: Set[str] = set()
        self.candidate_scores: Dict[str, Dict] = {}
        
        # 回调函数
        self.on_add_callback: Optional[Callable[[str], None]] = None
        self.on_remove_callback: Optional[Callable[[str], None]] = None
        self.on_update_callback: Optional[Callable[[List[WatchItem]], None]] = None
        
        # 运行状态
        self.running = False
        self.scan_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        
        # 加载历史数据
        self._load_state()
    
    def set_callbacks(self, 
                     on_add: Optional[Callable[[str], None]] = None,
                     on_remove: Optional[Callable[[str], None]] = None,
                     on_update: Optional[Callable[[List[WatchItem]], None]] = None):
        """设置回调函数"""
        self.on_add_callback = on_add
        self.on_remove_callback = on_remove
        self.on_update_callback = on_update
    
    def add_manual(self, code: str, name: str = "") -> bool:
        """手动添加监控"""
        with self.lock:
            if code in self.watch_items:
                return False
            
            if len(self.watch_items) >= self.config.max_watch_count:
                return False
            
            item = WatchItem(code=code, name=name or code)
            self.watch_items[code] = item
            self._save_state()
            
            if self.on_add_callback:
                self.on_add_callback(code)
            
            return True
    
    def remove_manual(self, code: str) -> bool:
        """手动移除监控"""
        with self.lock:
            if code not in self.watch_items:
                return False
            
            del self.watch_items[code]
            self._save_state()
            
            if self.on_remove_callback:
                self.on_remove_callback(code)
            
            return True
    
    def get_watch_list(self) -> List[str]:
        """获取当前监控列表"""
        with self.lock:
            return list(self.watch_items.keys())
    
    def get_watch_items(self) -> List[WatchItem]:
        """获取所有监控项"""
        with self.lock:
            return list(self.watch_items.values())
    
    def get_item(self, code: str) -> Optional[WatchItem]:
        """获取单个监控项"""
        with self.lock:
            return self.watch_items.get(code)
    
    def scan_and_update(self, stock_pool: List[str] = None) -> Dict:
        """
        扫描并更新监控列表
        
        Args:
            stock_pool: 扫描的股票池，None则扫描当前监控列表
        
        Returns:
            扫描结果统计
        """
        if stock_pool is None:
            stock_pool = list(self.watch_items.keys())
        
        results = {
            'scanned': len(stock_pool),
            'added': [],
            'removed': [],
            'updated': [],
            'candidates': []
        }
        
        # 1. 扫描所有股票
        scan_results = self._scan_stocks(stock_pool)
        
        with self.lock:
            # 2. 更新现有监控项
            for code, scan_data in scan_results.items():
                if code in self.watch_items:
                    updated = self._update_existing_item(code, scan_data)
                    if updated:
                        results['updated'].append(code)
                else:
                    # 3. 检查是否满足添加条件
                    if self.config.auto_add_enabled:
                        should_add = self._check_add_condition(code, scan_data)
                        if should_add and len(self.watch_items) < self.config.max_watch_count:
                            self._add_new_item(code, scan_data)
                            results['added'].append(code)
                        else:
                            # 记录候选
                            results['candidates'].append({
                                'code': code,
                                'score': scan_data.get('score', 0),
                                'reason': 'score_not_met' if scan_data.get('score', 0) < self.config.min_score_to_add else 'consecutive_not_met'
                            })
            
            # 4. 清理过期项
            if self.config.auto_remove_enabled:
                removed = self._cleanup_expired()
                results['removed'].extend(removed)
            
            self._save_state()
        
        # 5. 触发更新回调
        if self.on_update_callback:
            self.on_update_callback(self.get_watch_items())
        
        return results
    
    def _scan_stocks(self, stock_codes: List[str]) -> Dict[str, Dict]:
        """扫描股票，返回代码到数据的映射"""
        results = {}
        
        def fetch_data(code):
            try:
                return get_stock_data(code, count=100)
            except Exception as e:
                print(f"获取 {code} 数据失败: {e}")
                return None
        
        # 通达信扫描
        if self.config.use_tdx_scanner:
            for code in stock_codes:
                df = fetch_data(code)
                if df is not None and not df.empty:
                    try:
                        result = self.tdx_scanner.scan_stock(code, df)
                        if code not in results:
                            results[code] = {}
                        results[code]['tdx'] = result
                    except Exception as e:
                        print(f"通达信扫描 {code} 失败: {e}")
        
        # 缠论扫描
        if self.config.use_chan_picker:
            for code in stock_codes:
                df = fetch_data(code)
                if df is not None and not df.empty:
                    try:
                        chan_result = self.chan_picker.pick_single(code, df)
                        if code not in results:
                            results[code] = {}
                        results[code]['chan'] = chan_result
                    except Exception as e:
                        print(f"缠论扫描 {code} 失败: {e}")
        
        # 合并评分
        for code in results:
            results[code] = self._merge_scores(results[code])
        
        return results
    
    def _merge_scores(self, data: Dict) -> Dict:
        """合并两种策略的评分"""
        tdx_data = data.get('tdx', {})
        chan_data = data.get('chan')
        
        tdx_score = tdx_data.get('score', 0) if isinstance(tdx_data, dict) else 0
        chan_score = chan_data.score if chan_data else 0
        
        # 加权平均
        if self.config.use_tdx_scanner and self.config.use_chan_picker:
            final_score = (tdx_score * self.config.tdx_weight + 
                          chan_score * self.config.chan_weight)
        elif self.config.use_chan_picker:
            final_score = chan_score
        else:
            final_score = tdx_score
        
        # 确定信号类型
        signal_type = 'hold'
        signal_desc = ''
        
        if chan_data:
            signal_type = chan_data.signal_type
            signal_desc = chan_data.description
        elif tdx_data.get('is_candidate', False):
            signal_type = 'buy'
            signal_desc = f"通达信评分 {tdx_score}"
        
        return {
            'score': int(final_score),
            'tdx_score': tdx_score,
            'chan_score': chan_score,
            'signal_type': signal_type,
            'signal_description': signal_desc,
            'is_candidate': final_score >= self.config.min_score_to_add
        }
    
    def _update_existing_item(self, code: str, scan_data: Dict) -> bool:
        """更新现有监控项，返回是否有更新"""
        item = self.watch_items[code]
        item.last_update = datetime.now()
        
        old_score = item.score
        old_signal = item.signal_type
        
        item.score = scan_data.get('score', 0)
        item.signal_type = scan_data.get('signal_type', 'hold')
        item.signal_description = scan_data.get('signal_description', '')
        
        # 检查是否连续符合
        if scan_data.get('is_candidate', False):
            item.consecutive_count += 1
        else:
            item.consecutive_count = 0
        
        # 检查是否有实质变化
        return (old_score != item.score or 
                old_signal != item.signal_type)
    
    def _check_add_condition(self, code: str, scan_data: Dict) -> bool:
        """检查是否满足添加条件"""
        # 评分条件
        if scan_data.get('score', 0) < self.config.min_score_to_add:
            return False
        
        # 连续次数条件
        if code not in self.candidate_scores:
            self.candidate_scores[code] = {'count': 0, 'last_score': 0}
        
        candidate_info = self.candidate_scores[code]
        
        if scan_data.get('is_candidate', False):
            candidate_info['count'] += 1
            candidate_info['last_score'] = scan_data.get('score', 0)
        else:
            candidate_info['count'] = 0
        
        return candidate_info['count'] >= self.config.consecutive_required
    
    def _add_new_item(self, code: str, scan_data: Dict):
        """添加新监控项"""
        item = WatchItem(
            code=code,
            score=scan_data.get('score', 0),
            signal_type=scan_data.get('signal_type', 'hold'),
            signal_description=scan_data.get('signal_description', ''),
            consecutive_count=1
        )
        self.watch_items[code] = item
        
        if self.on_add_callback:
            self.on_add_callback(code)
    
    def _cleanup_expired(self) -> List[str]:
        """清理过期项，返回被移除的代码列表"""
        to_remove = []
        now = datetime.now()
        
        for code, item in self.watch_items.items():
            # 检查过期天数
            days_since_update = (now - item.last_update).days
            if days_since_update >= self.config.expire_days:
                item.expired = True
            
            # 检查分数条件
            if item.score < self.config.min_score_to_keep:
                item.consecutive_count -= 1
            
            # 检查连续失败次数
            if item.consecutive_count <= -self.config.max_consecutive_fail:
                to_remove.append(code)
            elif item.expired:
                to_remove.append(code)
        
        # 执行移除
        for code in to_remove:
            del self.watch_items[code]
            if code in self.candidate_scores:
                del self.candidate_scores[code]
            if self.on_remove_callback:
                self.on_remove_callback(code)
        
        return to_remove
    
    def start_auto_scan(self, stock_pool: List[str] = None):
        """启动自动扫描线程"""
        if self.running:
            return
        
        self.running = True
        
        def scan_loop():
            while self.running:
                try:
                    results = self.scan_and_update(stock_pool)
                    print(f"[SmartWatch] 扫描完成: {results}")
                except Exception as e:
                    print(f"[SmartWatch] 扫描异常: {e}")
                
                # 等待下次扫描
                for _ in range(self.config.scan_interval_seconds):
                    if not self.running:
                        break
                    threading.Event().wait(1)
        
        self.scan_thread = threading.Thread(target=scan_loop, daemon=True)
        self.scan_thread.start()
        print("[SmartWatch] 自动扫描已启动")
    
    def stop_auto_scan(self):
        """停止自动扫描"""
        self.running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=5)
        print("[SmartWatch] 自动扫描已停止")
    
    def _save_state(self):
        """保存状态到文件"""
        try:
            data = {
                'config': {
                    'min_score_to_add': self.config.min_score_to_add,
                    'consecutive_required': self.config.consecutive_required,
                    'max_watch_count': self.config.max_watch_count,
                    'expire_days': self.config.expire_days,
                    'min_score_to_keep': self.config.min_score_to_keep,
                    'max_consecutive_fail': self.config.max_consecutive_fail,
                    'scan_interval_seconds': self.config.scan_interval_seconds,
                    'auto_add_enabled': self.config.auto_add_enabled,
                    'auto_remove_enabled': self.config.auto_remove_enabled,
                },
                'watch_items': {code: item.to_dict() for code, item in self.watch_items.items()},
                'candidate_scores': self.candidate_scores
            }
            
            with open('smart_watch_state.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SmartWatch] 保存状态失败: {e}")
    
    def _load_state(self):
        """从文件加载状态"""
        try:
            if not os.path.exists('smart_watch_state.json'):
                return
            
            with open('smart_watch_state.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 加载监控项
            for code, item_data in data.get('watch_items', {}).items():
                self.watch_items[code] = WatchItem.from_dict(item_data)
            
            # 加载候选分数
            self.candidate_scores = data.get('candidate_scores', {})
            
            print(f"[SmartWatch] 已加载 {len(self.watch_items)} 个监控项")
        except Exception as e:
            print(f"[SmartWatch] 加载状态失败: {e}")
    
    def get_summary(self) -> Dict:
        """获取监控摘要"""
        with self.lock:
            buy_signals = sum(1 for item in self.watch_items.values() if item.signal_type == 'buy')
            sell_signals = sum(1 for item in self.watch_items.values() if item.signal_type == 'sell')
            expired = sum(1 for item in self.watch_items.values() if item.expired)
            
            return {
                'total': len(self.watch_items),
                'buy_signals': buy_signals,
                'sell_signals': sell_signals,
                'expired': expired,
                'candidates': len(self.candidate_scores),
                'max_allowed': self.config.max_watch_count
            }


# 便捷函数
def create_smart_watch_manager(
    min_score: int = 60,
    max_count: int = 50,
    auto_add: bool = True,
    auto_remove: bool = True
) -> SmartWatchManager:
    """创建智能监控管理器便捷函数"""
    config = SmartWatchConfig(
        min_score_to_add=min_score,
        max_watch_count=max_count,
        auto_add_enabled=auto_add,
        auto_remove_enabled=auto_remove
    )
    return SmartWatchManager(config)


if __name__ == '__main__':
    # 测试
    print("=" * 60)
    print("智能监控管理器测试")
    print("=" * 60)
    
    # 创建管理器
    manager = create_smart_watch_manager(min_score=50, max_count=10)
    
    # 手动添加几个测试股票
    test_codes = ['000001', '600519', '000858']
    for code in test_codes:
        manager.add_manual(code)
    
    print(f"\n初始监控列表: {manager.get_watch_list()}")
    
    # 执行一次扫描
    print("\n执行扫描...")
    results = manager.scan_and_update()
    
    print(f"扫描结果:")
    print(f"  扫描数量: {results['scanned']}")
    print(f"  新增: {results['added']}")
    print(f"  移除: {results['removed']}")
    print(f"  更新: {results['updated']}")
    print(f"  候选: {len(results['candidates'])}")
    
    # 显示摘要
    summary = manager.get_summary()
    print(f"\n监控摘要: {summary}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
