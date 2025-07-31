"""Market data models."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class MarketStatus(Enum):
    """Market status enumeration."""
    INACTIVE = "INACTIVE"
    OPEN = "OPEN"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class RunnerStatus(Enum):
    """Runner status enumeration."""
    ACTIVE = "ACTIVE"
    WINNER = "WINNER"
    LOSER = "LOSER"
    REMOVED = "REMOVED"
    PLACED = "PLACED"


@dataclass
class PriceSize:
    """Price and size information."""
    price: float
    size: float
    
    @property
    def implied_probability(self) -> float:
        """Calculate implied probability from decimal odds."""
        return 1.0 / self.price if self.price > 0 else 0.0


@dataclass
class Runner:
    """Runner (selection) in a market."""
    selection_id: int
    runner_name: str
    status: RunnerStatus
    handicap: float = 0.0
    back_prices: List[PriceSize] = field(default_factory=list)
    lay_prices: List[PriceSize] = field(default_factory=list)
    total_matched: float = 0.0
    last_price_traded: Optional[float] = None
    
    @property
    def best_back_price(self) -> Optional[float]:
        """Get best available back price."""
        return self.back_prices[0].price if self.back_prices else None
    
    @property
    def best_lay_price(self) -> Optional[float]:
        """Get best available lay price."""
        return self.lay_prices[0].price if self.lay_prices else None
    
    @property
    def best_back_size(self) -> Optional[float]:
        """Get size available at best back price."""
        return self.back_prices[0].size if self.back_prices else None
    
    @property
    def best_lay_size(self) -> Optional[float]:
        """Get size available at best lay price."""
        return self.lay_prices[0].size if self.lay_prices else None
    
    @property
    def spread(self) -> Optional[float]:
        """Calculate spread between best back and lay prices."""
        if self.best_back_price and self.best_lay_price:
            return self.best_lay_price - self.best_back_price
        return None
    
    @property
    def spread_percentage(self) -> Optional[float]:
        """Calculate spread as percentage of mid price."""
        if self.best_back_price and self.best_lay_price:
            mid_price = (self.best_back_price + self.best_lay_price) / 2
            return (self.spread / mid_price) * 100
        return None


@dataclass
class MarketBook:
    """Market book containing current prices and status."""
    market_id: str
    status: MarketStatus
    inplay: bool
    total_matched: float
    total_available: float
    runners: List[Runner]
    publish_time: datetime
    version: int
    complete: bool = True
    
    def get_runner(self, selection_id: int) -> Optional[Runner]:
        """Get runner by selection ID."""
        for runner in self.runners:
            if runner.selection_id == selection_id:
                return runner
        return None
    
    @property
    def is_active(self) -> bool:
        """Check if market is active and tradeable."""
        return self.status == MarketStatus.OPEN and not self.inplay


@dataclass
class Market:
    """Market information and metadata."""
    market_id: str
    market_name: str
    market_type: str
    event_id: str
    event_name: str
    event_type_id: str
    competition_id: Optional[str]
    competition_name: Optional[str]
    market_start_time: datetime
    total_matched: float = 0.0
    runners: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def is_match_odds(self) -> bool:
        """Check if this is a match odds market."""
        return self.market_type == "MATCH_ODDS"
    
    @property
    def is_over_under(self) -> bool:
        """Check if this is an over/under market."""
        return "OVER_UNDER" in self.market_type
    
    @property
    def runner_count(self) -> int:
        """Get number of runners in market."""
        return len(self.runners)