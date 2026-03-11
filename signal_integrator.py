"""
统一信号整合器
整合缠论、背离、因子分析等多个模块，输出标准化买卖信号
"""

import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime


class SignalIntegrator:
    """统一信号整合器"""
    
    def __init__(self):
        # 信号权重配置
        self.signal_weights = {
            'chan_divergence': 0.35,      # 缠论背离
            'factor_analysis': 0.25,      # 因子分析
            'ai_analysis': 0.25,          # AI 分析
            'technical_indicators': 0.15  # 技术指标
        }
        
        # 信号映射（统一为标准动作）
        self.signal_map = {
            # 强烈买入信号
            'STRONG_BUY': 1.0,
            'BUY': 0.6,
            'HOLD': 0.0,
            'SELL': -0.6,
            'STRONG_SELL': -1.0
        }
    
    def integrate_signals(self, signals: Dict) -> Dict:
        """
        整合多个信号源
        
        Args:
            signals: 信号字典，格式如：
                {
                    'chan_divergence': {'signal': 'BUY', 'confidence': 60},
                    'factor_analysis': {'score': 75},
                    'ai_analysis': {'recommendation': 'BUY'},
                    ...
                }
        
        Returns:
            统一信号结果
        """
        final_score = 0.0
        total_weight = 0.0
        reasons = []
        
        # 1. 缠论背离信号（权重 35%）
        if 'chan_divergence' in signals and signals['chan_divergence']:
            cd_signal = signals['chan_divergence']
            score = self._normalize_signal(cd_signal.get('signal', 'HOLD'))
            weight = self.signal_weights['chan_divergence'] * (cd_signal.get('confidence', 50) / 100)
            final_score += score * weight
            total_weight += weight
            
            if cd_signal.get('reason'):
                reasons.extend([f"[缠论] {r}" for r in cd_signal['reason']])
        
        # 2. 因子分析信号（权重 25%）
        if 'factor_analysis' in signals and signals['factor_analysis']:
            fa_signal = signals['factor_analysis']
            score = (fa_signal.get('score', 50) - 50) / 50  # 归一化到 [-1, 1]
            weight = self.signal_weights['factor_analysis']
            final_score += score * weight
            total_weight += weight
            
            if fa_signal.get('comment'):
                reasons.append(f"[因子] {fa_signal['comment']}")
        
        # 3. AI 分析信号（权重 25%）
        if 'ai_analysis' in signals and signals['ai_analysis']:
            ai_signal = signals['ai_analysis']
            ai_rec = ai_signal.get('recommendation', 'HOLD')
            score = self._normalize_signal(ai_rec)
            weight = self.signal_weights['ai_analysis']
            final_score += score * weight
            total_weight += weight
            
            if ai_signal.get('analysis'):
                reasons.append(f"[AI] {ai_signal['analysis']}")
        
        # 4. 技术指标信号（权重 15%）
        if 'technical_indicators' in signals and signals['technical_indicators']:
            ti_signal = signals['technical_indicators']
            score = ti_signal.get('score', 0) / 100  # 假设技术指标给的是 0-100 分
            score = score * 2 - 1  # 转换到 [-1, 1]
            weight = self.signal_weights['technical_indicators']
            final_score += score * weight
            total_weight += weight
            
            if ti_signal.get('indicators'):
                reasons.append(f"[技术] {ti_signal['indicators']}")
        
        # 生成最终信号
        final_signal, action = self._score_to_signal(final_score / total_weight if total_weight > 0 else 0)
        
        return {
            'final_signal': final_signal,
            'action': action,
            'score': round(final_score, 4),
            'confidence': int(abs(final_score) * 100),
            'reasons': reasons,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'breakdown': {
                'chan_divergence': signals.get('chan_divergence', {}),
                'factor_analysis': signals.get('factor_analysis', {}),
                'ai_analysis': signals.get('ai_analysis', {}),
                'technical_indicators': signals.get('technical_indicators', {})
            }
        }
    
    def _normalize_signal(self, signal: str) -> float:
        """将不同信号标准化为 [-1, 1]"""
        return self.signal_map.get(signal.upper(), 0.0)
    
    def _score_to_signal(self, score: float) -> tuple:
        """将分数转换为标准信号"""
        if score >= 0.8:
            return "STRONG_BUY", 1
        elif score >= 0.4:
            return "BUY", 1
        elif score >= -0.2:
            return "HOLD", 0
        elif score >= -0.6:
            return "SELL", -1
        else:
            return "STRONG_SELL", -1
    
    def create_trading_decision(self, integrator_result: Dict, 
                                position_size: float = 0.2,
                                stop_loss: float = 0.05,
                                take_profit: float = 0.10) -> Dict:
        """
        根据整合信号生成交易决策
        
        Args:
            integrator_result: 整合器输出结果
            position_size: 仓位比例（默认 20%）
            stop_loss: 止损比例（默认 5%）
            take_profit: 止盈比例（默认 10%）
        
        Returns:
            交易决策字典
        """
        action = integrator_result['action']
        confidence = integrator_result['confidence']
        
        # 根据置信度调整仓位
        actual_position = position_size * (confidence / 100)
        
        decision = {
            'should_trade': action != 0,  # 是否应该交易
            'direction': 'buy' if action > 0 else ('sell' if action < 0 else 'hold'),
            'position': round(actual_position, 2) if action != 0 else 0,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'reasoning': integrator_result['reasons'],
            'risk_level': self._assess_risk(confidence, action)
        }
        
        return decision
    
    def _assess_risk(self, confidence: int, action: int) -> str:
        """评估风险等级"""
        if abs(action) == 0:
            return "LOW"  # 持有观望，风险低
        elif confidence >= 80:
            return "MEDIUM"  # 高置信度，中等风险
        elif confidence >= 60:
            return "MEDIUM_HIGH"  # 中等置信度，中高风险
        else:
            return "HIGH"  # 低置信度，高风险


def quick_test():
    """快速测试"""
    print("="*70)
    print("统一信号整合器测试")
    print("="*70)
    
    integrator = SignalIntegrator()
    
    # 模拟多模块信号
    test_signals = {
        'chan_divergence': {
            'signal': 'BUY',
            'confidence': 60,
            'reason': ['缠论底背驰']
        },
        'factor_analysis': {
            'score': 75,
            'comment': '估值合理，成长性良好'
        },
        'ai_analysis': {
            'recommendation': 'BUY',
            'analysis': '技术面和基本面共振'
        },
        'technical_indicators': {
            'score': 70,
            'indicators': 'MACD 金叉，均线多头'
        }
    }
    
    # 整合信号
    result = integrator.integrate_signals(test_signals)
    
    print("\n整合结果:")
    print(f"  最终信号：{result['final_signal']}")
    print(f"  动作：{result['action']} (-1 卖出/0 持有/1 买入)")
    print(f"  综合得分：{result['score']}")
    print(f"  置信度：{result['confidence']}%")
    
    print("\n分析依据:")
    for reason in result['reasons']:
        print(f"  - {reason}")
    
    # 生成交易决策
    decision = integrator.create_trading_decision(
        result,
        position_size=0.3,  # 30% 仓位
        stop_loss=0.05,     # 5% 止损
        take_profit=0.15    # 15% 止盈
    )
    
    print("\n交易决策:")
    print(f"  是否交易：{'是' if decision['should_trade'] else '否'}")
    print(f"  方向：{decision['direction']}")
    print(f"  建议仓位：{decision['position']*100:.1f}%")
    print(f"  止损位：{decision['stop_loss']*100:.1f}%")
    print(f"  止盈位：{decision['take_profit']*100:.1f}%")
    print(f"  风险等级：{decision['risk_level']}")
    
    print("\n" + "="*70)


if __name__ == '__main__':
    quick_test()
