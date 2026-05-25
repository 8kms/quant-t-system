from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ..config import CostConfig, SignalConfig
from .features import DailySnapshot, IntradaySnapshot
from ..io import WatchItem


@dataclass(frozen=True)
class TSignal:
    symbol: str
    name: str
    sector: str
    signal_date: str
    action: str
    score: float
    confidence: str
    trade_ratio: float
    observe_price: float
    target_price: float
    cancel_price: float
    expected_edge_pct: float
    reasons: List[str]
    warnings: List[str]

    @property
    def action_cn(self) -> str:
        mapping = {
            "reverse_t": "反T: 先卖后买回",
            "positive_t": "正T: 先买后卖出底仓",
            "hold": "不做T",
        }
        return mapping.get(self.action, self.action)


class TSignalEngine:
    def __init__(self, costs: CostConfig, config: SignalConfig):
        self.costs = costs
        self.config = config

    def generate(
        self,
        item: WatchItem,
        daily: DailySnapshot,
        intraday: IntradaySnapshot,
        market_return: float = 0.0,
        historical_success_rate: Optional[float] = None,
        breadth_score: float = 0.0,
        breadth_flags: Optional[List[str]] = None,
    ) -> TSignal:
        reverse_score, reverse_reasons, reverse_warnings = self._score_reverse_t(
            daily, intraday, market_return, breadth_score, breadth_flags or []
        )
        positive_score, positive_reasons, positive_warnings = self._score_positive_t(
            daily, intraday, market_return, breadth_score, breadth_flags or []
        )

        if historical_success_rate is not None:
            hist_adj = (historical_success_rate - 0.55) * 30.0
            reverse_score += hist_adj
            positive_score += hist_adj
            reason = f"历史同类场景胜率 {historical_success_rate:.1%}"
            reverse_reasons.append(reason)
            positive_reasons.append(reason)

        if reverse_score >= positive_score:
            action = "reverse_t"
            score = reverse_score
            reasons = reverse_reasons
            warnings = reverse_warnings
            target = intraday.current_price * (1 - self.costs.practical_edge_rate)
            cancel = intraday.current_price * (1 + self.config.reverse_cancel_rate)
        else:
            action = "positive_t"
            score = positive_score
            reasons = positive_reasons
            warnings = positive_warnings
            target = intraday.current_price * (1 + self.costs.practical_edge_rate)
            cancel = min(
                intraday.current_price * (1 - self.config.positive_stop_rate),
                intraday.morning_low * 0.998,
            )

        if score < self.config.min_score_to_trade:
            action = "hold"
            reasons = ["评分低于交易阈值"] + reasons[:3]
            warnings = warnings + ["不做T也是一种仓位决策"]
            target = intraday.current_price
            cancel = intraday.current_price

        return TSignal(
            symbol=item.symbol,
            name=item.name,
            sector=item.sector,
            signal_date=str(intraday.signal_date),
            action=action,
            score=round(max(0.0, min(score, 100.0)), 2),
            confidence=self._confidence(score),
            trade_ratio=self._trade_ratio(score, action),
            observe_price=round(intraday.current_price, 3),
            target_price=round(target, 3),
            cancel_price=round(cancel, 3),
            expected_edge_pct=round(self.costs.practical_edge_rate * 100, 3),
            reasons=reasons[:8],
            warnings=warnings[:6],
        )

    def _score_reverse_t(
        self,
        daily: DailySnapshot,
        intra: IntradaySnapshot,
        market_return: float,
        breadth_score: float = 0.0,
        breadth_flags: Optional[List[str]] = None,
    ) -> tuple[float, List[str], List[str]]:
        score = 45.0
        reasons: List[str] = []
        warnings: List[str] = []

        gap = intra.open_gap
        if 0.006 <= gap <= 0.03:
            add = min(18.0, gap * 700)
            score += add
            reasons.append(f"高开幅度适合反T观察：{gap:.2%}")
        elif gap > 0.03:
            score += 6
            warnings.append("大幅高开可能演变成趋势日，反T不要满仓")
        elif gap < -0.004:
            score -= 12
            warnings.append("低开不是典型反T场景")

        if intra.vwap_distance > 0.003:
            score += min(14.0, intra.vwap_distance * 1600)
            reasons.append(f"当前价高于VWAP {intra.vwap_distance:.2%}")
        if intra.close_position > 0.72:
            score += 8
            reasons.append("早盘价格处在分时区间高位")
        if intra.amount_ratio > 0.035:
            score += min(8.0, intra.amount_ratio * 80)
            reasons.append("早盘成交活跃，具备日内价差空间")
        if daily.ret_5 > 0.05:
            score += 8
            reasons.append(f"近5日涨幅偏高：{daily.ret_5:.2%}")
        if daily.position_20 > 0.82:
            score += 7
            reasons.append("价格处于20日区间上沿附近")
        if daily.upper_shadow_ratio > 0.35:
            score += 5
            reasons.append("昨日K线存在明显上影线")

        if market_return > self.config.strong_market_threshold:
            score -= 12
            warnings.append("市场偏强，反T卖飞概率上升")

        if breadth_score > 0:
            breadth_adj = (breadth_score - 1.5) * 8.0
            score += breadth_adj
            if breadth_flags:
                reasons.extend(breadth_flags[:2])
            if breadth_score >= 2.5:
                warnings.append("市场广度极强，涨停家数多，反T卖飞概率上升")
        elif breadth_score < 0.8 and breadth_score > 0:
            score -= 4
            if breadth_flags:
                warnings.extend(breadth_flags[:1])

        if intra.broke_prev_high and intra.amount_ratio > 0.04 and market_return >= 0:
            score -= 8
            warnings.append("放量突破昨日高点，可能是趋势突破")

        return score, reasons, warnings

    def _score_positive_t(
        self,
        daily: DailySnapshot,
        intra: IntradaySnapshot,
        market_return: float,
        breadth_score: float = 0.0,
        breadth_flags: Optional[List[str]] = None,
    ) -> tuple[float, List[str], List[str]]:
        score = 43.0
        reasons: List[str] = []
        warnings: List[str] = []

        gap = intra.open_gap
        if -0.03 <= gap <= -0.006:
            add = min(18.0, abs(gap) * 700)
            score += add
            reasons.append(f"低开幅度适合正T观察：{gap:.2%}")
        elif gap < -0.03:
            score += 3
            warnings.append("大幅低开可能是真破位，需要等待承接确认")
        elif gap > 0.006:
            score -= 8

        if intra.reclaimed_vwap:
            score += 14
            reasons.append("早盘下探后重新收回VWAP")
        if intra.vwap_distance > 0:
            score += min(8.0, intra.vwap_distance * 900)
            reasons.append("当前价重新站上VWAP")
        if intra.close_position > 0.58 and intra.open_gap < 0:
            score += 7
            reasons.append("低开后价格回到早盘区间上半部")
        if not intra.broke_prev_low and intra.open_gap < 0:
            score += 8
            reasons.append("早盘低点未跌破昨日低点")
        if daily.lower_shadow_ratio > 0.35:
            score += 5
            reasons.append("昨日K线存在下影线支撑")
        if market_return > 0:
            score += min(10.0, market_return * 1200)
            reasons.append(f"市场背景不弱：{market_return:.2%}")

        if breadth_score > 0:
            breadth_adj = (breadth_score - 1.5) * 6.0
            score += breadth_adj
            if breadth_flags and breadth_score < 1.0:
                warnings.extend(breadth_flags[:1])

        if intra.broke_prev_low:
            score -= 16
            warnings.append("早盘低点跌破昨日低点")
        if market_return < self.config.weak_market_threshold:
            score -= 15
            warnings.append("市场偏弱，正T补仓风险较高")
        if daily.ret_20 < -0.12:
            score -= 8
            warnings.append("20日跌幅较深，反弹容易失败")

        return score, reasons, warnings

    def _confidence(self, score: float) -> str:
        if score >= self.config.strong_score:
            return "high"
        if score >= self.config.min_score_to_trade:
            return "medium"
        return "low"

    def _trade_ratio(self, score: float, action: str) -> float:
        if action == "hold":
            return 0.0
        if score >= self.config.strong_score:
            return min(self.config.max_trade_ratio, 0.30)
        if score >= self.config.min_score_to_trade:
            return min(self.config.normal_trade_ratio, 0.20)
        return self.config.small_trade_ratio
