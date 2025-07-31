"""Bet models and enumerations."""

from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class BetType(Enum):
    """Type of bet."""
    BACK = "BACK"
    LAY = "LAY"


class BetStatus(Enum):
    """Status of a bet."""
    PENDING = "PENDING"
    MATCHED = "MATCHED"
    UNMATCHED = "UNMATCHED"
    CANCELLED = "CANCELLED"
    SETTLED = "SETTLED"
    VOIDED = "VOIDED"


class Bookmaker(Enum):
    """Supported bookmakers."""
    BETFAIR = "BETFAIR"
    PADDYPOWER = "PADDYPOWER"
    WILLIAMHILL = "WILLIAMHILL"
    BET365 = "BET365"
    BETMGM = "BETMGM"
    LADBROKES = "LADBROKES"
    
    @property
    def display_name(self) -> str:
        """Get display name for bookmaker."""
        names = {
            self.BETFAIR: "Betfair Exchange",
            self.PADDYPOWER: "Paddy Power",
            self.WILLIAMHILL: "William Hill",
            self.BET365: "Bet365",
            self.BETMGM: "BetMGM",
            self.LADBROKES: "Ladbrokes"
        }
        return names.get(self, self.value)
    
    @property
    def is_exchange(self) -> bool:
        """Check if bookmaker is an exchange."""
        return self == self.BETFAIR


@dataclass
class Bet:
    """Individual bet record."""
    bet_id: str
    bookmaker: Bookmaker
    market_id: str
    market_name: str
    selection_id: str
    selection_name: str
    bet_type: BetType
    odds: float
    stake: float
    status: BetStatus
    placed_at: datetime
    matched_at: Optional[datetime] = None
    settled_at: Optional[datetime] = None
    profit_loss: Optional[float] = None
    commission: float = 0.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def potential_profit(self) -> float:
        """Calculate potential profit."""
        if self.bet_type == BetType.BACK:
            return (self.stake * self.odds) - self.stake
        else:  # LAY
            return self.stake
    
    @property
    def liability(self) -> float:
        """Calculate liability (for lay bets)."""
        if self.bet_type == BetType.LAY:
            return self.stake * (self.odds - 1)
        return self.stake
    
    @property
    def net_profit(self) -> float:
        """Calculate net profit after commission."""
        if self.profit_loss is not None:
            return self.profit_loss - (self.profit_loss * self.commission)
        return 0.0


@dataclass
class BookmakerAccount:
    """Bookmaker account information."""
    bookmaker: Bookmaker
    username: str
    balance: float
    available_balance: float
    exposure: float
    currency: str = "GBP"
    commission_rate: float = 0.05  # Default 5% for Betfair
    is_active: bool = True
    last_updated: Optional[datetime] = None
    
    @property
    def total_funds(self) -> float:
        """Calculate total funds including exposure."""
        return self.balance + self.exposure