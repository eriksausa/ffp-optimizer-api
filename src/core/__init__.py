"""
Pure-Python Domain Core (`src.core`).

Contains deterministic data structures, geodesic/tax-stripping calculations,
credit card transfer bonus math, and cross-alliance award arbitrage algorithms.
Designed with zero external network or database dependencies for fast local execution.
"""

from src.core.models import (
    AirportProfile,
    Alliance,
    AwardSweetSpot,
    BankCurrency,
    CabinClass,
    FlightSegment,
    LoyaltyProgram,
    TransferOptionResult,
    TransferPartnerRule,
)
from src.core.calculator import (
    apply_transfer_bonus,
    calculate_effective_cpm,
    estimate_eligible_spend,
    evaluate_eu261_segment,
    find_best_transfer_pathways,
    haversine_distance,
    simulate_flight_crediting,
)

__all__ = [
    "AirportProfile",
    "Alliance",
    "AwardSweetSpot",
    "BankCurrency",
    "CabinClass",
    "FlightSegment",
    "LoyaltyProgram",
    "TransferOptionResult",
    "TransferPartnerRule",
    "apply_transfer_bonus",
    "calculate_effective_cpm",
    "estimate_eligible_spend",
    "evaluate_eu261_segment",
    "find_best_transfer_pathways",
    "haversine_distance",
    "simulate_flight_crediting",
]
