"""
Domain models for the Loyalty Arbitrage Engine (`src/core/models.py`).

Uses Python's built-in `@dataclass(frozen=True)` and `Enum` so the core calculation engine
runs out-of-the-box with zero third-party runtime dependencies, while mapping 1-to-1
to Pydantic v2 schemas and SQLAlchemy 2.0 ORM models in Phase 2.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Alliance(str, Enum):
    """Global airline alliances plus non-aligned partners."""

    STAR_ALLIANCE = "STAR_ALLIANCE"
    ONEWORLD = "ONEWORLD"
    SKYTEAM = "SKYTEAM"
    NON_ALIGNED = "NON_ALIGNED"


class CabinClass(str, Enum):
    """Standardized cabin buckets used across earning and redemption charts."""

    ECONOMY = "ECONOMY"
    PREMIUM_ECONOMY = "PREMIUM_ECONOMY"
    BUSINESS = "BUSINESS"
    FIRST = "FIRST"


@dataclass(frozen=True)
class AirportProfile:
    """
    Reference metadata for an airport, including coordinates for Haversine great-circle
    calculations, Miles & More regional zones, EU261 jurisdiction, and estimated government taxes.
    """

    iata_code: str
    name: str
    city: str
    country_code: str
    latitude: float
    longitude: float
    region_zone: str
    is_eu_eea_ch: bool
    estimated_gov_departure_tax_usd: float = 25.0


@dataclass(frozen=True)
class BankCurrency:
    """Transferable credit card points ecosystem (e.g., Amex MR, Chase UR, Citi TYP, Capital One)."""

    bank_code: str
    bank_name: str
    currency_name: str
    baseline_cashout_cents_per_point: float


@dataclass(frozen=True)
class LoyaltyProgram:
    """Frequent Flyer Program configuration for both flight crediting and award redemptions."""

    program_code: str
    program_name: str
    home_carrier_iata: str
    alliance: Alliance
    currency_name: str
    own_ticket_revenue_multiplier: Optional[float]
    counts_yq_surcharge: bool
    gold_status_tier_name: str
    gold_status_threshold: float
    own_metal_min_share_pct: float = 0.0
    own_metal_min_segments: int = 0


@dataclass(frozen=True)
class TransferPartnerRule:
    """
    Defines how a bank point currency transfers to an airline loyalty program.
    Example: 1,000 Chase UR -> 1,000 Iberia Avios (base_ratio = 1.0) with an optional
    promotional bonus (e.g., 30% bonus -> active_bonus_pct = 30.0).
    """

    bank_code: str
    program_code: str
    base_ratio: float = 1.0
    active_bonus_pct: float = 0.0
    min_transfer_increment: int = 1000
    estimated_transfer_hours: int = 0


@dataclass(frozen=True)
class PartnerEarningRule:
    """Defines how a paid flight segment earns redeemable miles and status points in a loyalty program."""

    program_code: str
    operating_carrier: str
    booking_class: str
    cabin: CabinClass
    award_miles_pct: float
    min_award_miles: int
    status_calc_method: str  # "DISTANCE_PCT", "MM_ZONE_FIXED", "UA_PQP_PARTNER", "IB_ZONE_FIXED"
    status_miles_pct: float = 100.0
    continental_status_points: float = 0.0
    intercontinental_status_points: float = 0.0


@dataclass(frozen=True)
class AwardSweetSpot:
    """
    Represents a bookable partner or own-metal award flight benchmark on a specific corridor.
    Enables cross-alliance and intra-alliance arbitrage comparisons (e.g., booking Lufthansa metal
    via Air Canada Aeroplan or Turkish Miles&Smiles vs. Miles & More; or Iberia vs. Aeroméxico on MEX-MAD).
    """

    benchmark_code: str
    booking_program_code: str
    operating_carrier_iata: str
    alliance: Alliance
    origin_iata: str
    destination_iata: str
    cabin: CabinClass
    miles_required_one_way: int
    taxes_and_yq_usd: float
    typical_cash_fare_one_way_usd: float
    category: str  # "SHORT_HAUL_UNLOCK" or "LONG_HAUL_SWEET_SPOT"
    description: str


@dataclass(frozen=True)
class FlightSegment:
    """Input flight segment for calculating earned miles, status progress, and EU261 protection."""

    origin_iata: str
    destination_iata: str
    operating_carrier: str
    booking_class: str
    ticketing_carrier: Optional[str] = None
    base_fare_usd: Optional[float] = None
    yq_surcharge_usd: float = 0.0
    total_ticket_price_usd: Optional[float] = None


@dataclass(frozen=True)
class TransferOptionResult:
    """Output record ranking a specific Bank -> Airline Program -> Partner Award arbitrage pathway."""

    bank_code: str
    bank_currency_name: str
    booking_program_code: str
    booking_program_name: str
    operating_carrier_iata: str
    route: str
    cabin: CabinClass
    award_miles_required: int
    effective_transfer_ratio: float
    bank_points_required: int
    taxes_and_yq_usd: float
    cash_fare_benchmark_usd: float
    net_cash_saved_usd: float
    effective_cents_per_point: float
    beats_cashout_baseline: bool
    notes: str = ""


@dataclass(frozen=True)
class CreditingSimulationResult:
    """Output record comparing flight crediting across competing alliance loyalty programs."""

    program_code: str
    program_name: str
    alliance: Alliance
    is_operating_metal_program: bool
    redeemable_miles_earned: int
    calculation_basis: str
    eligible_spend_usd: float
    estimated_gov_taxes_stripped_usd: float
    status_points_earned: float
    gold_status_threshold: float
    progress_to_gold_pct: float
    own_metal_warning: Optional[str]
    unlocked_short_haul_awards: list[str] = field(default_factory=list)
    flagship_sweet_spot_progress: list[str] = field(default_factory=list)
