"""Models for arbitrage opportunities and value bets."""

from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .market import Market, Runner


class OpportunityType(Enum):
    """Type of betting opportunity."""
    ARBITRAGE = "ARBITRAGE"
    VALUE_BET = "VALUE_BET"
    SURE_BET = "SURE_BET"


@dataclass
class ArbitrageLeg:
    """Single leg of an arbitrage bet."""
    market_id: str
    market_name: str
    selection_id: int
    selection_name: str
    bet_type: str  # BACK or LAY
    odds: float
    stake: float
    potential_profit: float
    implied_probability: float
    
    @property
    def potential_return(self) -> float:
        """Calculate potential return including stake."""
        if self.bet_type == "BACK":
            return self.stake * self.odds
        else:  # LAY
            return self.stake


@dataclass
class ArbitrageOpportunity:
    """Arbitrage opportunity across markets or selections."""
    opportunity_id: str
    opportunity_type: OpportunityType
    created_at: datetime
    expires_at: Optional[datetime]
    total_stake: float
    guaranteed_profit: float
    profit_percentage: float
    legs: List[ArbitrageLeg]
    market_ids: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Extract market IDs from legs."""
        self.market_ids = list(set(leg.market_id for leg in self.legs))
    
    @property
    def is_valid(self) -> bool:
        """Check if opportunity is still valid."""
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return self.profit_percentage > 0
    
    @property
    def roi(self) -> float:
        """Calculate return on investment."""
        return (self.guaranteed_profit / self.total_stake) * 100 if self.total_stake > 0 else 0
    
    def calculate_stakes(self, total_investment: float) -> Dict[str, float]:
        """Calculate optimal stakes for given total investment."""
        stakes = {}
        for leg in self.legs:
            stake_proportion = leg.stake / self.total_stake
            stakes[f"{leg.market_id}_{leg.selection_id}"] = total_investment * stake_proportion
        return stakes


@dataclass
class ValueBet:
    """Value betting opportunity."""
    bet_id: str
    market_id: str
    market_name: str
    selection_id: int
    selection_name: str
    bet_type: str  # BACK or LAY
    current_odds: float
    true_odds: float
    true_probability: float
    edge_percentage: float
    recommended_stake: float
    kelly_fraction: float
    expected_value: float
    confidence: float
    created_at: datetime
    expires_at: Optional[datetime]
    
    @property
    def is_positive_ev(self) -> bool:
        """Check if bet has positive expected value."""
        return self.expected_value > 0
    
    @property
    def implied_probability(self) -> float:
        """Calculate implied probability from current odds."""
        return 1.0 / self.current_odds if self.current_odds > 0 else 0
    
    @property
    def probability_difference(self) -> float:
        """Calculate difference between true and implied probability."""
        return self.true_probability - self.implied_probability
    
    def calculate_kelly_stake(self, bankroll: float, max_fraction: float = 0.25) -> float:
        """Calculate Kelly criterion stake with maximum fraction limit."""
        kelly_stake = bankroll * min(self.kelly_fraction, max_fraction)
        return min(kelly_stake, self.recommended_stake)
    
    def calculate_expected_profit(self, stake: float) -> float:
        """Calculate expected profit for given stake."""
        if self.bet_type == "BACK":
            win_amount = stake * (self.current_odds - 1)
            return (win_amount * self.true_probability) - (stake * (1 - self.true_probability))
        else:  # LAY
            liability = stake * (self.current_odds - 1)
            return (stake * (1 - self.true_probability)) - (liability * self.true_probability)


@dataclass
class ArbitrageResult:
    """Result of arbitrage calculation."""
    is_arbitrage: bool
    profit_percentage: float
    total_implied_probability: float
    optimal_stakes: Dict[str, float]
    guaranteed_profit: float
    required_capital: float
    
    @property
    def roi(self) -> float:
        """Calculate return on investment."""
        return (self.guaranteed_profit / self.required_capital * 100) if self.required_capital > 0 else 0