"""
Loyalty Arbitrage & Frequent Flyer ROI Engine — Interactive Demo (`streamlit_app.py`).

Created by:
- Erik Šauša, Dipl.-Ing. (M.Sc.), B.Sc.
- Master of Science in Telecommunications & Bachelor of Science in Electrical Engineering and Information Technology (TU Wien)
- Maestría en Ciencias en Telecomunicaciones y Licenciatura en Ingeniería Eléctrica y Tecnologías de la Información (TU Wien)

Run locally from the root of `loyalty-arbitrage-engine`:
    pip install streamlit
    streamlit run streamlit_app.py
"""

import inspect
import streamlit as st

from src.core.calculator import (
    apply_transfer_bonus,
    calculate_effective_cpm,
    calculate_required_bank_points,
    estimate_eligible_spend,
    evaluate_eu261_segment,
    haversine_distance,
)
from src.core.ingestion_client import ExternalIngestionClient
from src.core.models import (
    AirportProfile,
    Alliance,
    AwardSweetSpot,
    BankCurrency,
    CabinClass,
    CreditingSimulationResult,
    FlightSegment,
    LoyaltyProgram,
    PartnerEarningRule,
    TransferOptionResult,
    TransferPartnerRule,
)
from src.api import routes as api_routes
from src.db.repository import LoyaltyRepository
from src.db.session import DatabaseSessionManager
from src.serverless import lambda_handler

# ===========================================================================
# Verified, Self-Contained Dataset (Zero Invented Partners or Fake Rules)
# ===========================================================================
MXN_PER_USD = 20.0
EU_EEA_CH_CARRIERS = {"IB", "AF", "KL", "LH", "LX", "OS", "SN", "AY", "SK", "TP", "LO"}

CLEAN_AIRPORTS: dict[str, AirportProfile] = {
    "MEX": AirportProfile("MEX", "Benito Juárez International (AICM)", "Mexico City", "MX", 19.4363, -99.0721, "NORTH_AMERICA", False, 65.0),
    "CUN": AirportProfile("CUN", "Cancún International", "Cancún", "MX", 21.0365, -86.8771, "NORTH_AMERICA", False, 58.0),
    "MAD": AirportProfile("MAD", "Adolfo Suárez Madrid–Barajas", "Madrid", "ES", 40.4983, -3.5676, "EUROPE", True, 42.0),
    "CDG": AirportProfile("CDG", "Charles de Gaulle Airport", "Paris", "FR", 49.0097, 2.5479, "EUROPE", True, 75.0),
    "LHR": AirportProfile("LHR", "Heathrow Airport", "London", "GB", 51.4700, -0.4543, "EUROPE", False, 115.0),
    "BCN": AirportProfile("BCN", "Josep Tarradellas Barcelona–El Prat", "Barcelona", "ES", 41.2974, 2.0833, "EUROPE", True, 38.0),
}

CLEAN_BANKS: dict[str, BankCurrency] = {
    "SANTANDER_MX": BankCurrency("SANTANDER_MX", "Santander México", "Unique Rewards", 0.50),
    "BBVA_MX": BankCurrency("BBVA_MX", "BBVA México", "Puntos BBVA", 0.55),
    "AMEX_MX": BankCurrency("AMEX_MX", "American Express México", "Membership Rewards", 0.75),
}

CLEAN_PROGRAMS: dict[str, LoyaltyProgram] = {
    # SkyTeam (For CDG <-> MEX on Aeroméxico)
    "AM_RW": LoyaltyProgram("AM_RW", "Aeroméxico Rewards", "AM", Alliance.SKYTEAM, "Puntos Aeroméxico", 8.0, True, "Aeroméxico Gold (SkyTeam Elite Plus)", 80000.0),
    "VS_FC": LoyaltyProgram("VS_FC", "Virgin Atlantic Flying Club", "VS", Alliance.SKYTEAM, "Virgin Points", None, True, "Flying Club Gold (SkyTeam Elite Plus)", 1000.0),
    "AF_FB": LoyaltyProgram("AF_FB", "Air France / KLM Flying Blue", "AF", Alliance.SKYTEAM, "Flying Blue Miles", 4.0, True, "Flying Blue Gold (SkyTeam Elite Plus)", 180.0),
    # Oneworld (For MEX <-> MAD on Iberia)
    "IB_PLUS": LoyaltyProgram("IB_PLUS", "Iberia Club (Avios)", "IB", Alliance.ONEWORLD, "Avios", 6.4815, True, "Iberia Oro (Oneworld Sapphire)", 2250.0),
    "BA_EC": LoyaltyProgram("BA_EC", "The British Airways Club (Avios)", "BA", Alliance.ONEWORLD, "Avios", 6.4815, True, "British Airways Silver (Oneworld Sapphire)", 7500.0),
    "AA_ADV": LoyaltyProgram("AA_ADV", "American Airlines AAdvantage", "AA", Alliance.ONEWORLD, "AAdvantage Miles", 5.0, True, "AAdvantage Platinum (Oneworld Sapphire)", 75000.0),
    "AS_ATMOS": LoyaltyProgram("AS_ATMOS", "Alaska Airlines Atmos Rewards", "AS", Alliance.ONEWORLD, "Atmos Points", None, True, "Atmos Gold (Oneworld Sapphire)", 40000.0),
}

# Strictly verified Mexican Credit Card transfer rules:
# - Santander Unique Rewards -> Iberia Club ONLY (1 Unique Point = 1 Avios)
# - BBVA Puntos -> Iberia Club (2.6 Puntos BBVA = 1 Avios, min 130 pts) & Aeroméxico (1.6 Puntos BBVA = 1 Pt AM)
# - Amex México -> Iberia Club (1:1), British Airways (1:1), Flying Blue (1:1), Aeroméxico (1:1)
CLEAN_TRANSFER_RULES: list[TransferPartnerRule] = [
    TransferPartnerRule("SANTANDER_MX", "IB_PLUS", base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("BBVA_MX", "IB_PLUS", base_ratio=50.0 / 130.0, active_bonus_pct=0.0, min_transfer_increment=130),
    TransferPartnerRule("BBVA_MX", "AM_RW",   base_ratio=0.625000, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MX", "IB_PLUS", base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MX", "BA_EC",   base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MX", "AF_FB",   base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MX", "AM_RW",   base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
]

# Tab 2 Award Benchmarks on MEX -> MAD (Iberia 21k/40.5k Avios vs. Flying Blue vs. Aeroméxico)
TAB2_MEX_MAD_BENCHMARKS: list[AwardSweetSpot] = [
    AwardSweetSpot("IB_MEX_MAD_ECON", "IB_PLUS", "IB", Alliance.ONEWORLD, "MEX", "MAD", CabinClass.ECONOMY, 21000, 115.0, 680.0, "LONG_HAUL_SWEET_SPOT", "Iberia Nonstop MEX→MAD Economy (21,000 Avios full, or less with Avios & Money; flexible changes/refunds)"),
    AwardSweetSpot("IB_MEX_MAD_BIZ", "IB_PLUS", "IB", Alliance.ONEWORLD, "MEX", "MAD", CabinClass.BUSINESS, 40500, 195.0, 2450.0, "LONG_HAUL_SWEET_SPOT", "Iberia Nonstop MEX→MAD Lie-Flat Business Class (40,500 Avios Off-Peak)"),
    AwardSweetSpot("BA_MEX_MAD_ECON", "BA_EC", "IB", Alliance.ONEWORLD, "MEX", "MAD", CabinClass.ECONOMY, 21000, 115.0, 680.0, "LONG_HAUL_SWEET_SPOT", "Iberia MEX→MAD Economy booked via British Airways Avios (combines 1:1 with Iberia Club)"),
    AwardSweetSpot("BA_MEX_MAD_BIZ", "BA_EC", "IB", Alliance.ONEWORLD, "MEX", "MAD", CabinClass.BUSINESS, 40500, 195.0, 2450.0, "LONG_HAUL_SWEET_SPOT", "Iberia MEX→MAD Business Class booked via British Airways Avios (combines 1:1 with Iberia Club)"),
    AwardSweetSpot("AF_MEX_MAD_ECON", "AF_FB", "AM", Alliance.SKYTEAM, "MEX", "MAD", CabinClass.ECONOMY, 28000, 140.0, 680.0, "LONG_HAUL_SWEET_SPOT", "Aeroméxico MEX→MAD Economy booked via Air France/KLM Flying Blue"),
    AwardSweetSpot("AF_MEX_MAD_BIZ", "AF_FB", "AM", Alliance.SKYTEAM, "MEX", "MAD", CabinClass.BUSINESS, 70000, 220.0, 2450.0, "LONG_HAUL_SWEET_SPOT", "Aeroméxico MEX→MAD Clase Premier booked via Air France/KLM Flying Blue"),
    AwardSweetSpot("AM_MEX_MAD_ECON", "AM_RW", "AM", Alliance.SKYTEAM, "MEX", "MAD", CabinClass.ECONOMY, 75000, 180.0, 680.0, "LONG_HAUL_SWEET_SPOT", "Aeroméxico MEX→MAD Economy via Aeroméxico Rewards (75,000 pts vs. 21,000 Avios on Iberia)"),
    AwardSweetSpot("AM_MEX_MAD_BIZ", "AM_RW", "AM", Alliance.SKYTEAM, "MEX", "MAD", CabinClass.BUSINESS, 145000, 260.0, 2450.0, "LONG_HAUL_SWEET_SPOT", "Aeroméxico MEX→MAD Clase Premier via Aeroméxico Rewards (145,000 pts vs. 40,500 Avios on Iberia)"),
]

# Tab 3 Immediate Flight Unlock Targets (What Earned Miles From Paid Flights Actually Unlock!)
TAB3_UNLOCK_TARGETS: list[AwardSweetSpot] = [
    # Aeroméxico Rewards: Lowest National Flight in Mexico = 10,000 Puntos AM!
    AwardSweetSpot("AM_NATIONAL_10K", "AM_RW", "AM", Alliance.SKYTEAM, "MEX", "CUN", CabinClass.ECONOMY, 10000, 65.0, 150.0, "SHORT_HAUL_UNLOCK", "Lowest National Flight in Mexico on Aeroméxico (10,000 Puntos AM)"),
    # Virgin Atlantic Flying Club:
    # 1. Off-Peak Promo CUN->LHR Economy = 6,000 VS Points!
    # 2. Off-Peak Promo CUN->LHR Premium Economy (W) = 10,000 VS Points!
    # 3. MEX->Europe on Air France / KLM metal = 15,000 VS Points!
    # 4. MEX->Europe on Aeroméxico metal (SkyTeam distance chart) = 25,000 VS Points
    AwardSweetSpot("VS_CUN_LHR_6K_ECON", "VS_FC", "VS", Alliance.SKYTEAM, "CUN", "LHR", CabinClass.ECONOMY, 6000, 145.0, 620.0, "SHORT_HAUL_UNLOCK", "Off-Peak Promo CUN→LHR (Cancún to Europe!) Economy on Virgin Atlantic (6,000 VS Points)"),
    AwardSweetSpot("VS_CUN_LHR_10K_W", "VS_FC", "VS", Alliance.SKYTEAM, "CUN", "LHR", CabinClass.PREMIUM_ECONOMY, 10000, 245.0, 1050.0, "SHORT_HAUL_UNLOCK", "Off-Peak Promo CUN→LHR (Cancún to Europe!) Premium Economy (W) on Virgin Atlantic (10,000 VS Points)"),
    AwardSweetSpot("VS_AF_KL_15K_ECON", "VS_FC", "AF", Alliance.SKYTEAM, "MEX", "CDG", CabinClass.ECONOMY, 15000, 155.0, 720.0, "SHORT_HAUL_UNLOCK", "MEX→Europe Economy on Air France / KLM metal via Virgin Atlantic (15,000 VS Points)"),
    AwardSweetSpot("VS_AM_25K_ECON", "VS_FC", "AM", Alliance.SKYTEAM, "CDG", "MEX", CabinClass.ECONOMY, 25000, 155.0, 720.0, "SHORT_HAUL_UNLOCK", "MEX↔Europe Economy on Aeroméxico metal via Virgin Atlantic SkyTeam chart (25,000 VS Points)"),
    # Flying Blue:
    AwardSweetSpot("AF_DOMESTIC_7500", "AF_FB", "AM", Alliance.SKYTEAM, "MEX", "CUN", CabinClass.ECONOMY, 7500, 65.0, 150.0, "SHORT_HAUL_UNLOCK", "Domestic Mexico Flight on Aeroméxico via Flying Blue (7,500 Miles)"),
    # Alaska Airlines Atmos Rewards: 4,500-point and 7,000-point Oneworld reward flights!
    AwardSweetSpot("AS_4500_REWARD", "AS_ATMOS", "AA", Alliance.ONEWORLD, "MAD", "BCN", CabinClass.ECONOMY, 4500, 28.0, 140.0, "SHORT_HAUL_UNLOCK", "Oneworld Short-Haul Reward Flight via Alaska Atmos (4,500 Atmos Points)"),
    AwardSweetSpot("AS_7000_REWARD", "AS_ATMOS", "AA", Alliance.ONEWORLD, "MEX", "CUN", CabinClass.ECONOMY, 7000, 45.0, 210.0, "SHORT_HAUL_UNLOCK", "Oneworld Medium-Haul Reward Flight via Alaska Atmos (7,000 Atmos Points)"),
    # Iberia / BA / AA lowest reward flights:
    AwardSweetSpot("IB_4500_SHORTHAUL", "IB_PLUS", "IB", Alliance.ONEWORLD, "MAD", "BCN", CabinClass.ECONOMY, 4500, 28.0, 140.0, "SHORT_HAUL_UNLOCK", "European Short-Haul MAD–BCN Economy on Iberia (4,500 Avios)"),
    AwardSweetSpot("BA_4750_SHORTHAUL", "BA_EC", "IB", Alliance.ONEWORLD, "MAD", "BCN", CabinClass.ECONOMY, 4750, 28.0, 140.0, "SHORT_HAUL_UNLOCK", "European Short-Haul MAD–BCN Economy via British Airways Avios (4,750 Avios)"),
    AwardSweetSpot("AA_7500_SHORTHAUL", "AA_ADV", "AA", Alliance.ONEWORLD, "MEX", "CUN", CabinClass.ECONOMY, 7500, 45.0, 190.0, "SHORT_HAUL_UNLOCK", "Oneworld Short-Haul Reward Flight via AAdvantage (7,500 Miles)"),
]

CLEAN_EARNING_RULES: list[PartnerEarningRule] = [
    # Route 1: Aeroméxico ("AM" — CDG <-> MEX)
    PartnerEarningRule("AM_RW", "AM", "V", CabinClass.ECONOMY,          25.0, 250, "DISTANCE_PCT",  25.0),
    PartnerEarningRule("AM_RW", "AM", "K", CabinClass.ECONOMY,          75.0, 250, "DISTANCE_PCT",  75.0),
    PartnerEarningRule("AM_RW", "AM", "Y", CabinClass.ECONOMY,         100.0, 500, "DISTANCE_PCT", 100.0),
    PartnerEarningRule("AM_RW", "AM", "W", CabinClass.PREMIUM_ECONOMY, 125.0, 500, "DISTANCE_PCT", 125.0),
    PartnerEarningRule("AM_RW", "AM", "I", CabinClass.BUSINESS,        150.0, 500, "DISTANCE_PCT", 150.0),
    PartnerEarningRule("AM_RW", "AM", "J", CabinClass.BUSINESS,        200.0, 1000, "DISTANCE_PCT", 200.0),

    PartnerEarningRule("VS_FC", "AM", "V", CabinClass.ECONOMY,          25.0, 250, "IB_ZONE_FIXED",  25.0, 10.0,  25.0),
    PartnerEarningRule("VS_FC", "AM", "K", CabinClass.ECONOMY,          75.0, 250, "IB_ZONE_FIXED",  75.0, 20.0,  50.0),
    PartnerEarningRule("VS_FC", "AM", "Y", CabinClass.ECONOMY,         150.0, 500, "IB_ZONE_FIXED", 150.0, 30.0,  75.0),
    PartnerEarningRule("VS_FC", "AM", "W", CabinClass.PREMIUM_ECONOMY, 150.0, 500, "IB_ZONE_FIXED", 150.0, 20.0,  50.0),
    PartnerEarningRule("VS_FC", "AM", "I", CabinClass.BUSINESS,        150.0, 500, "IB_ZONE_FIXED", 150.0, 40.0, 200.0),
    PartnerEarningRule("VS_FC", "AM", "J", CabinClass.BUSINESS,        250.0, 1000, "IB_ZONE_FIXED", 250.0, 40.0, 200.0),

    PartnerEarningRule("AF_FB", "AM", "V", CabinClass.ECONOMY,          25.0, 250, "IB_ZONE_FIXED",  25.0,  5.0, 12.0),
    PartnerEarningRule("AF_FB", "AM", "K", CabinClass.ECONOMY,          50.0, 250, "IB_ZONE_FIXED",  50.0,  5.0, 12.0),
    PartnerEarningRule("AF_FB", "AM", "Y", CabinClass.ECONOMY,         100.0, 500, "IB_ZONE_FIXED", 100.0,  5.0, 12.0),
    PartnerEarningRule("AF_FB", "AM", "W", CabinClass.PREMIUM_ECONOMY, 100.0, 500, "IB_ZONE_FIXED", 100.0, 10.0, 24.0),
    PartnerEarningRule("AF_FB", "AM", "I", CabinClass.BUSINESS,        150.0, 500, "IB_ZONE_FIXED", 150.0, 15.0, 36.0),
    PartnerEarningRule("AF_FB", "AM", "J", CabinClass.BUSINESS,        200.0, 1000, "IB_ZONE_FIXED", 200.0, 15.0, 36.0),

    # Route 2: Iberia ("IB" — MEX <-> MAD)
    PartnerEarningRule("IB_PLUS", "IB", "V", CabinClass.ECONOMY,          25.0, 250, "IB_ZONE_FIXED",  25.0,  35.0, 150.0),
    PartnerEarningRule("IB_PLUS", "IB", "K", CabinClass.ECONOMY,          50.0, 250, "IB_ZONE_FIXED",  50.0,  35.0, 150.0),
    PartnerEarningRule("IB_PLUS", "IB", "Y", CabinClass.ECONOMY,         100.0, 500, "IB_ZONE_FIXED", 100.0,  75.0, 300.0),
    PartnerEarningRule("IB_PLUS", "IB", "W", CabinClass.PREMIUM_ECONOMY, 100.0, 500, "IB_ZONE_FIXED", 100.0,  90.0, 350.0),
    PartnerEarningRule("IB_PLUS", "IB", "I", CabinClass.BUSINESS,        125.0, 500, "IB_ZONE_FIXED", 125.0, 125.0, 500.0),
    PartnerEarningRule("IB_PLUS", "IB", "J", CabinClass.BUSINESS,        250.0, 1000, "IB_ZONE_FIXED", 250.0, 175.0, 600.0),

    PartnerEarningRule("BA_EC", "IB", "V", CabinClass.ECONOMY,          25.0, 250, "IB_ZONE_FIXED",  25.0,  10.0,  35.0),
    PartnerEarningRule("BA_EC", "IB", "K", CabinClass.ECONOMY,          50.0, 250, "IB_ZONE_FIXED",  50.0,  10.0,  35.0),
    PartnerEarningRule("BA_EC", "IB", "Y", CabinClass.ECONOMY,         100.0, 500, "IB_ZONE_FIXED", 100.0,  20.0,  70.0),
    PartnerEarningRule("BA_EC", "IB", "W", CabinClass.PREMIUM_ECONOMY, 100.0, 500, "IB_ZONE_FIXED", 100.0,  25.0,  90.0),
    PartnerEarningRule("BA_EC", "IB", "I", CabinClass.BUSINESS,        125.0, 500, "IB_ZONE_FIXED", 125.0,  40.0, 140.0),
    PartnerEarningRule("BA_EC", "IB", "J", CabinClass.BUSINESS,        250.0, 1000, "IB_ZONE_FIXED", 250.0,  40.0, 160.0),

    PartnerEarningRule("AA_ADV", "IB", "V", CabinClass.ECONOMY,          25.0, 250, "DISTANCE_PCT",  25.0),
    PartnerEarningRule("AA_ADV", "IB", "K", CabinClass.ECONOMY,          50.0, 250, "DISTANCE_PCT",  50.0),
    PartnerEarningRule("AA_ADV", "IB", "Y", CabinClass.ECONOMY,         100.0, 500, "DISTANCE_PCT", 100.0),
    PartnerEarningRule("AA_ADV", "IB", "W", CabinClass.PREMIUM_ECONOMY, 100.0, 500, "DISTANCE_PCT", 100.0),
    PartnerEarningRule("AA_ADV", "IB", "I", CabinClass.BUSINESS,        125.0, 500, "DISTANCE_PCT", 125.0),
    PartnerEarningRule("AA_ADV", "IB", "J", CabinClass.BUSINESS,        250.0, 1000, "DISTANCE_PCT", 250.0),

    PartnerEarningRule("AS_ATMOS", "IB", "V", CabinClass.ECONOMY,          25.0, 250, "DISTANCE_PCT",  25.0),
    PartnerEarningRule("AS_ATMOS", "IB", "K", CabinClass.ECONOMY,          50.0, 250, "DISTANCE_PCT",  50.0),
    PartnerEarningRule("AS_ATMOS", "IB", "Y", CabinClass.ECONOMY,         100.0, 500, "DISTANCE_PCT", 100.0),
    PartnerEarningRule("AS_ATMOS", "IB", "W", CabinClass.PREMIUM_ECONOMY, 100.0, 500, "DISTANCE_PCT", 100.0),
    PartnerEarningRule("AS_ATMOS", "IB", "I", CabinClass.BUSINESS,        125.0, 500, "DISTANCE_PCT", 125.0),
    PartnerEarningRule("AS_ATMOS", "IB", "J", CabinClass.BUSINESS,        250.0, 1000, "DISTANCE_PCT", 250.0),
]


def _calculate_segment_spend_and_tax(orig: AirportProfile, total_price_usd: float) -> tuple[float, float, str]:
    """
    Strips strictly the departure airport's mandatory government tax:
    - Departing MEX strips Mexican AICM TUA ($65 USD).
    - Departing CDG strips French airport departure tax ($75 USD).
    - Departing MAD strips Spanish AENA airport departure tax ($42 USD).
    """
    tax_usd = min(round(orig.estimated_gov_departure_tax_usd, 2), round(total_price_usd * 0.35, 2))
    eligible_usd = round(max(0.0, total_price_usd - tax_usd), 2)
    if orig.country_code == "MX":
        tax_label = f"Mexican TUA ({orig.iata_code}: ${tax_usd:.0f} USD)"
    else:
        tax_label = f"EU Airport Departure Tax ({orig.iata_code}: ${tax_usd:.0f} USD)"
    return eligible_usd, tax_usd, tax_label


def _run_mex_mad_transfers(
    cabin: CabinClass,
    bank_filter: str,
    bonus_pct: float,
    cash_fare_usd: float,
    is_es: bool,
) -> list[TransferOptionResult]:
    """Calculates transfer pathways on MEX -> MAD for Santander Unique, BBVA, and Amex México."""
    spots = [s for s in TAB2_MEX_MAD_BENCHMARKS if s.cabin == cabin]
    results: list[TransferOptionResult] = []
    for spot in spots:
        program = CLEAN_PROGRAMS[spot.booking_program_code]
        for rule in CLEAN_TRANSFER_RULES:
            if rule.program_code != spot.booking_program_code:
                continue
            if bank_filter != "ALL_MX" and rule.bank_code != bank_filter:
                continue
            bank = CLEAN_BANKS[rule.bank_code]
            eff_ratio = apply_transfer_bonus(rule.base_ratio, bonus_pct)
            bank_pts = calculate_required_bank_points(
                spot.miles_required_one_way, rule.base_ratio, bonus_pct, rule.min_transfer_increment
            )
            cpp = calculate_effective_cpm(cash_fare_usd, spot.taxes_and_yq_usd, bank_pts)
            net_saved = round(max(0.0, cash_fare_usd - spot.taxes_and_yq_usd), 2)

            if rule.bank_code == "SANTANDER_MX":
                ratio_desc = "1 Unique Point = 1 Avios (Iberia Club Exclusive Partner)" if not is_es else "1 Unique Point = 1 Avios (Socio Exclusivo Iberia Club)"
            elif rule.bank_code == "BBVA_MX" and rule.program_code == "IB_PLUS":
                ratio_desc = "2.6 Puntos BBVA = 1 Avios (min 130 pts)" if not is_es else "2.6 Puntos BBVA = 1 Avios (mín. 130 pts)"
            elif rule.bank_code == "BBVA_MX" and rule.program_code == "AM_RW":
                ratio_desc = "1.6 Puntos BBVA = 1 Punto Aeroméxico" if not is_es else "1.6 Puntos BBVA = 1 Punto Aeroméxico"
            else:
                ratio_desc = "1 : 1 Membership Rewards Transfer" if not is_es else "Transferencia 1 : 1 Membership Rewards"

            if bonus_pct > 0:
                ratio_desc += f" + {bonus_pct:.0f}% promo ({eff_ratio}:1)"

            results.append(
                TransferOptionResult(
                    bank_code=bank.bank_code,
                    bank_currency_name=f"{bank.bank_name} ({bank.currency_name})",
                    booking_program_code=program.program_code,
                    booking_program_name=program.program_name,
                    operating_carrier_iata=spot.operating_carrier_iata,
                    route="MEX-MAD",
                    cabin=cabin,
                    award_miles_required=spot.miles_required_one_way,
                    effective_transfer_ratio=eff_ratio,
                    bank_points_required=bank_pts,
                    taxes_and_yq_usd=spot.taxes_and_yq_usd,
                    cash_fare_benchmark_usd=cash_fare_usd,
                    net_cash_saved_usd=net_saved,
                    effective_cents_per_point=cpp,
                    beats_cashout_baseline=(cpp > bank.baseline_cashout_cents_per_point),
                    notes=f"{spot.description} | {ratio_desc}",
                )
            )
    results.sort(key=lambda r: (r.bank_points_required, r.taxes_and_yq_usd))
    return results


def _run_paid_flight_simulation(
    segments: list[FlightSegment],
    is_es: bool,
) -> list[CreditingSimulationResult]:
    """Simulates paid flight crediting for CDG<->MEX on AM (SkyTeam) or MEX<->MAD on IB (Oneworld)."""
    primary_carrier = segments[0].operating_carrier.upper()
    results: list[CreditingSimulationResult] = []

    for prog_code, program in CLEAN_PROGRAMS.items():
        total_miles = 0
        total_status_pts = 0.0
        total_eligible_spend = 0.0
        total_gov_taxes = 0.0
        used_rev = False
        used_dist = False
        matched_any = False

        for seg in segments:
            orig = CLEAN_AIRPORTS[seg.origin_iata.upper()]
            dest = CLEAN_AIRPORTS[seg.destination_iata.upper()]
            dist_mi, _ = haversine_distance(orig.latitude, orig.longitude, dest.latitude, dest.longitude)

            rule = next(
                (r for r in CLEAN_EARNING_RULES if r.program_code == prog_code and r.operating_carrier == seg.operating_carrier.upper() and r.booking_class == seg.booking_class.upper()),
                None,
            )
            if rule is None:
                continue
            matched_any = True

            eligible_spend, gov_tax, _ = _calculate_segment_spend_and_tax(orig, float(seg.total_ticket_price_usd or 0.0))
            total_eligible_spend += eligible_spend
            total_gov_taxes += gov_tax

            ticketing_carrier = (seg.ticketing_carrier or seg.operating_carrier).upper()
            # Oneworld Transatlantic JV: IB_PLUS, BA_EC, and AA_ADV all credit IB-marketed flights by spend!
            is_revenue_eligible = (
                ticketing_carrier == program.home_carrier_iata
                or (prog_code in {"IB_PLUS", "BA_EC", "AA_ADV"} and ticketing_carrier in {"IB", "BA", "AA"})
            )

            if is_revenue_eligible and eligible_spend > 0 and program.own_ticket_revenue_multiplier is not None:
                if prog_code in {"IB_PLUS", "BA_EC"} and seg.operating_carrier.upper() == "IB":
                    # Official Iberia & British Airways Club rule: 5 base + 2 Spain-Mexico bonus = 7 Avios per €1 EUR
                    eur_spend = eligible_spend / 1.08
                    seg_miles = int(round(eur_spend * 7.0))
                else:
                    seg_miles = int(round(eligible_spend * program.own_ticket_revenue_multiplier))
                used_rev = True
            else:
                raw_miles = dist_mi * (rule.award_miles_pct / 100.0)
                seg_miles = int(round(max(raw_miles, float(rule.min_award_miles)) if rule.award_miles_pct > 0 else 0.0))
                used_dist = True

            total_miles += seg_miles

            if prog_code == "BA_EC" and is_revenue_eligible and eligible_spend > 0:
                gbp_spend = eligible_spend / 1.27
                cabin_bonus = 400.0 if rule.cabin == CabinClass.BUSINESS else (275.0 if rule.cabin == CabinClass.PREMIUM_ECONOMY else 175.0)
                seg_status = round(gbp_spend + cabin_bonus, 1)
            elif prog_code == "AA_ADV" and is_revenue_eligible and eligible_spend > 0:
                seg_status = round(eligible_spend * 5.0, 1)
            elif prog_code == "AM_RW" and is_revenue_eligible and eligible_spend > 0:
                seg_status = round(eligible_spend * 8.0, 1)
            elif rule.status_calc_method == "IB_ZONE_FIXED":
                seg_status = rule.intercontinental_status_points
            else:
                seg_status = round(dist_mi * (rule.status_miles_pct / 100.0), 1)

            total_status_pts += seg_status

        if not matched_any:
            continue

        progress_pct = round(min(100.0, (total_status_pts / program.gold_status_threshold) * 100.0), 1)

        # Evaluate against TAB3_UNLOCK_TARGETS
        unlock_lines: list[str] = []
        progress_lines: list[str] = []
        for bm in TAB3_UNLOCK_TARGETS:
            if bm.booking_program_code != prog_code:
                continue
            if total_miles >= bm.miles_required_one_way:
                count = total_miles // bm.miles_required_one_way
                rem = total_miles % bm.miles_required_one_way
                if is_es:
                    unlock_lines.append(f"✅ ¡Desbloquea {count}x {bm.description} ({bm.miles_required_one_way:,} req. + {rem:,} sobrantes)!")
                else:
                    unlock_lines.append(f"✅ Unlocks {count}x {bm.description} ({bm.miles_required_one_way:,} req. + {rem:,} left)!")
            else:
                pct = round((total_miles / bm.miles_required_one_way) * 100.0, 1)
                if is_es:
                    progress_lines.append(f"❌ 0 vuelos — Solo alcanza {pct}% ({total_miles:,} / {bm.miles_required_one_way:,}) para {bm.description}")
                else:
                    progress_lines.append(f"❌ 0 flights unlocked — Only {pct}% ({total_miles:,} / {bm.miles_required_one_way:,}) toward {bm.description}")

        basis = "REVENUE_BASED (Spend)" if used_rev else "DISTANCE_BASED (Miles × %)"
        results.append(
            CreditingSimulationResult(
                program_code=prog_code,
                program_name=program.program_name,
                alliance=program.alliance,
                is_operating_metal_program=(program.home_carrier_iata == primary_carrier),
                redeemable_miles_earned=total_miles,
                calculation_basis=basis,
                eligible_spend_usd=round(total_eligible_spend, 2),
                estimated_gov_taxes_stripped_usd=round(total_gov_taxes, 2),
                status_points_earned=round(total_status_pts, 1),
                gold_status_threshold=program.gold_status_threshold,
                progress_to_gold_pct=progress_pct,
                own_metal_warning=program.gold_status_tier_name,
                unlocked_short_haul_awards=unlock_lines,
                flagship_sweet_spot_progress=progress_lines,
            )
        )

    results.sort(
        key=lambda r: (len(r.unlocked_short_haul_awards) > 0, r.redeemable_miles_earned, r.progress_to_gold_pct),
        reverse=True,
    )
    return results


# ===========================================================================
# Streamlit Page Setup & Header
# ===========================================================================
st.set_page_config(
    page_title="Loyalty Arbitrage & Frequent Flyer ROI Engine — Erik Šauša",
    page_icon="✈️",
    layout="wide",
)

hdr_left, hdr_right = st.columns([4, 1])
with hdr_right:
    lang = st.selectbox(
        "🌐 Language / Idioma",
        options=["EN", "ES"],
        format_func=lambda x: "🇬🇧 English" if x == "EN" else "🇲🇽 Español",
    )

is_es = lang == "ES"

with hdr_left:
    if not is_es:
        st.title("✈️ Cross-Alliance Loyalty Arbitrage & Frequent Flyer ROI Engine")
        st.markdown(
            "**Created by Erik Šauša, Dipl.-Ing. (M.Sc.), B.Sc.**  \n"
            "*Master of Science in Telecommunications · Bachelor of Science in Electrical Engineering and Information Technology (TU Wien)*  \n"
            "🚧 **Interactive Architecture Demo (Work in Progress):** *Phase 1 Core Math Engine Active · Phase 2 FastAPI / PostgreSQL / AWS Lambda Scaffolded*"
        )
    else:
        st.title("✈️ Motor de Arbitraje de Lealtad Multi-Alianza y ROI de Viajero Frecuente")
        st.markdown(
            "**Creado por Erik Šauša, Dipl.-Ing. (M.Sc.), B.Sc.**  \n"
            "*Maestría en Ciencias en Telecomunicaciones · Licenciatura en Ingeniería Eléctrica y Tecnologías de la Información (TU Wien)*  \n"
            "🚧 **Demo Interactiva de Arquitectura (Proyecto en Desarrollo):** *Fase 1 Motor Matemático Activo · Fase 2 FastAPI / PostgreSQL / AWS Lambda en Scaffolding*"
        )

# ---------------------------------------------------------------------------
# The Two Core Motivations (Why This Engine Exists)
# ---------------------------------------------------------------------------
col_m1, col_m2 = st.columns(2)
with col_m1:
    if not is_es:
        st.info(
            "**1️⃣ Reason #1 — Crediting Paid Flights to 'Own Metal' Is Often Not Optimal:**  \n"
            "• **Aeroméxico (`CDG ↔ MEX`) vs. Virgin Atlantic:** The lowest domestic award flight inside Mexico on **Aeroméxico Rewards** costs **10,000 points**. "
            "If you fly a discounted round-trip from Europe to Mexico (`CDG ↔ MEX`) on Aeroméxico and credit to Aeroméxico's own revenue-based program (`8 pts/$1 USD`), "
            "you often earn **~6,080 points—not even enough for a single 10,000-point national flight in Mexico**! "
            "Crediting that exact same flight to SkyTeam partner **Virgin Atlantic Flying Club** (distance-based) earns **8,572 to 17,145 Virgin Points**, "
            "which immediately unlocks an **Off-Peak Promo flight from Cancún to London (`CUN → LHR` Europe) for just 6,000 Virgin Points in Economy (or 10,000 pts in Premium `W`)**!  \n"
            "• **Iberia (`MEX ↔ MAD`) vs. Alaska Atmos:** Both **Iberia Club** and **British Airways Club** credit Iberia flights by spend (`7 Avios/€`), "
            "so a cheap round-trip earns **~3,500 Avios** (`0` flights unlocked). Crediting that same Iberia flight to **Alaska Airlines Atmos Rewards** (distance-based) "
            "earns **5,634+ points**, immediately unlocking a **4,500-point (or 7,000-point) Oneworld reward flight**!"
        )
    else:
        st.info(
            "**1️⃣ Razón #1 — Acreditar un Vuelo Pagado a la Propia Aerolínea ('Own Metal') Casi Nunca Es Óptimo:**  \n"
            "• **Aeroméxico (`CDG ↔ MEX`) vs. Virgin Atlantic:** El vuelo premio nacional más bajo dentro de México en **Aeroméxico Rewards** cuesta **10,000 puntos**. "
            "Si vuelas redondo de Europa a México (`CDG ↔ MEX`) en tarifa económica de Aeroméxico y acreditas en su propio programa por gasto (`8 pts/$1 USD`), "
            "acumulas **~6,080 puntos—¡ni siquiera te alcanza para un vuelo nacional de 10,000 puntos en México!** "
            "En cambio, si acreditas ese mismo vuelo de Aeroméxico en su socio SkyTeam **Virgin Atlantic Flying Club** (por distancia), ganas **8,572 a 17,145 Virgin Points**, "
            "lo que desbloquea de inmediato un **vuelo promo de Cancún a Londres (`CUN → LHR` Europa) por solo 6,000 Virgin Points en Turista (o 10,000 pts en Premium `W`)**.  \n"
            "• **Iberia (`MEX ↔ MAD`) vs. Alaska Atmos:** Tanto **Iberia Club** como **British Airways Club** acreditan vuelos de Iberia por gasto (`7 Avios/€`), "
            "por lo que un boleto económico redondo da **~3,500 Avios** (`0` vuelos desbloqueados). Acreditarlo en **Alaska Airlines Atmos Rewards** (por distancia) "
            "te da **5,634+ puntos**, ¡desbloqueando ya un **vuelo premio Oneworld de 4,500 o 7,000 puntos**!"
        )

with col_m2:
    if not is_es:
        st.success(
            "**2️⃣ Reason #2 — Cardholders Don't Know the True Value of Their Mexican Bank Points (`Santander Unique`, `BBVA`, `Amex México` → `Iberia Avios`):**  \n"
            "Most cardholders in Mexico redeem **Santander Unique Rewards** or **Puntos BBVA** for low-value store cashback without realizing their true purchasing power in **Iberia Club (Avios)**:  \n"
            "• **Santander Unique Rewards:** Transfers **`1 : 1` (`1 Unique Point = 1 Avios`)** exclusively to **Iberia Club**.  \n"
            "• **BBVA México (`Puntos BBVA`):** Transfers to **Iberia Club** (`2.6 Puntos BBVA = 1 Avios`, min 130 pts) and **Aeroméxico Rewards** (`1.6:1`).  \n"
            "• **American Express México (`Membership Rewards`):** Transfers **`1 : 1`** to **Iberia Club**, **British Airways**, **Flying Blue**, and **Aeroméxico**.  \n"
            "• **21,000 Avios to Europe + Maximum Flexibility:** For just **21,000 Avios** one-way, you can fly nonstop **Mexico City to Madrid (`MEX → MAD`)** paying only with Avios. "
            "You can even choose to pay **fewer Avios** using Iberia's **Avios & Money** slider, and **Avios tickets are far more flexible** than cheap cash tickets (easy date changes or refunds)."
        )
    else:
        st.success(
            "**2️⃣ Razón #2 — La Gente No Conoce el Valor Real de sus Puntos Bancarios en México (`Santander Unique`, `BBVA`, `Amex México` → `Iberia Avios`):**  \n"
            "Muchos tarjetahabientes en México gastan sus puntos en comercios a un valor mínimo sin saber cuánto valen al transferirlos a **Iberia Club (Avios)**:  \n"
            "• **Santander Unique Rewards:** Transfiere **`1 : 1` (`1 Unique Point = 1 Avios`)** exclusivamente a **Iberia Club**.  \n"
            "• **BBVA México (`Puntos BBVA`):** Transfiere a **Iberia Club** (`2.6 Puntos BBVA = 1 Avios`, mín. 130 pts) y a **Aeroméxico Rewards** (`1.6:1`).  \n"
            "• **American Express México (`Membership Rewards`):** Transfiere **`1 : 1`** a **Iberia Club**, **British Airways**, **Flying Blue** y **Aeroméxico**.  \n"
            "• **21,000 Avios a Europa + Máxima Flexibilidad:** Por solo **21,000 Avios** vuelas directo **Ciudad de México a Madrid (`MEX → MAD`)** pagando solo con Avios. "
            "Incluso puedes elegir usar **menos Avios** con **Avios & Money**, y los **boletos con Avios son mucho más flexibles** (permiten cambios y reembolsos)."
        )

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    if not is_es:
        st.markdown("### 👨‍💻 Created By")
        st.markdown(
            """
            **Erik Šauša, Dipl.-Ing. (M.Sc.), B.Sc.**
            - 🎓 **Master of Science in Telecommunications** *(TU Wien)*
            - 🎓 **Bachelor of Science in Electrical Engineering and Information Technology** *(TU Wien)*
            """
        )
        st.divider()
        st.markdown("### 🇲🇽 Verified Demo Scope")
        st.markdown(
            """
            **3 Mexican Cards (Tab 2)**
            - **Santander Unique**: `1 : 1` → Iberia Club *(only)*
            - **Puntos BBVA**: `2.6 : 1` → Iberia (`min 130`) · `1.6 : 1` → Aeroméxico
            - **Amex México**: `1 : 1` → Iberia, BA, Flying Blue, Aeroméxico

            **2 Paid Flight Routes (Tab 3)**
            - **`CDG ↔ MEX` on Aeroméxico (`AM`)**:
              - AM Rewards (`10k` national target) vs. Virgin Atlantic (`6k` Economy / `10k` W `CUN→LHR` promo)
            - **`MEX ↔ MAD` on Iberia (`IB`)**:
              - Iberia & BA (`7 Avios/€` spend) vs. Alaska Atmos (`4.5k` & `7k` distance unlock)
            """
        )
        st.divider()
        st.markdown("### 🚧 Work-in-Progress Status")
        st.markdown(
            """
            - 🟢 `src/core/` *(Live Pure-Python Engine)*
            - 🟢 `tests/` *(Passing Unit Tests)*
            - 🟡 `src/db/` *(PostgreSQL `# TODO`)*
            - 🟡 `src/api/` *(FastAPI `# TODO`)*
            - 🟡 `src/serverless/` *(Lambda `# TODO`)*
            """
        )
    else:
        st.markdown("### 👨‍💻 Creado Por")
        st.markdown(
            """
            **Erik Šauša, Dipl.-Ing. (M.Sc.), B.Sc.**
            - 🎓 **Maestría en Ciencias en Telecomunicaciones** *(TU Wien)*
            - 🎓 **Licenciatura en Ingeniería Eléctrica y Tecnologías de la Información** *(TU Wien)*
            """
        )
        st.divider()
        st.markdown("### 🇲🇽 Alcance Verificado de la Demo")
        st.markdown(
            """
            **3 Tarjetas en México (Pestaña 2)**
            - **Santander Unique**: `1 : 1` → Iberia Club *(exclusivo)*
            - **Puntos BBVA**: `2.6 : 1` → Iberia (`mín 130`) · `1.6 : 1` → Aeroméxico
            - **Amex México**: `1 : 1` → Iberia, BA, Flying Blue, Aeroméxico

            **2 Rutas de Vuelos Pagados (Pestaña 3)**
            - **`CDG ↔ MEX` en Aeroméxico (`AM`)**:
              - AM Rewards (meta `10k` vuelo nacional) vs. Virgin Atlantic (`6k` Turista / `10k` W `CUN→LHR`)
            - **`MEX ↔ MAD` en Iberia (`IB`)**:
              - Iberia y BA (`7 Avios/€` por gasto) vs. Alaska Atmos (`4.5k` y `7k` por distancia)
            """
        )
        st.divider()
        st.markdown("### 🚧 Estado del Proyecto (WIP)")
        st.markdown(
            """
            - 🟢 `src/core/` *(Motor Matemático Activo)*
            - 🟢 `tests/` *(Pruebas Unitarias Activas)*
            - 🟡 `src/db/` *(PostgreSQL `# TODO`)*
            - 🟡 `src/api/` *(FastAPI `# TODO`)*
            - 🟡 `src/serverless/` *(Lambda `# TODO`)*
            """
        )

# ---------------------------------------------------------------------------
# Main Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    [
        "🗺️ 1. How It Works & Architectural Map" if not is_es else "🗺️ 1. Cómo Funciona y Mapa Arquitectónico",
        "💳 2. Mexican Cards → Europe (`Santander 1:1`, `BBVA`, `Amex`)" if not is_es else "💳 2. Tarjetas México → Europa (`Santander 1:1`, `BBVA`, `Amex`)",
        "🛫 3. Flight Crediting (`CDG→MEX` on AM & `MEX→MAD` on IB)" if not is_es else "🛫 3. Acreditación de Vuelos (`CDG→MEX` en AM y `MEX→MAD` en IB)",
        "🛠️ 4. Work-in-Progress Backend (`# TODO` Phase 2)" if not is_es else "🛠️ 4. Backend en Progreso (`# TODO` Fase 2)",
    ]
)

# ===========================================================================
# TAB 1: HOW IT WORKS & ARCHITECTURAL MAP
# ===========================================================================
with tab1:
    st.subheader(
        "System Architecture Map & How the Engine Works"
        if not is_es
        else "Mapa Arquitectónico del Sistema y Cómo Funciona el Motor"
    )

    if not is_es:
        st.markdown(
            """
            <div style="background:#0F172A;color:#F8FAFC;padding:20px 24px;border-radius:12px;border:1px solid #334155;margin-bottom:18px;font-family:sans-serif;">
              <div style="font-size:15px;font-weight:700;color:#38BDF8;margin-bottom:12px;letter-spacing:0.4px;">
                🗺️ ARCHITECTURAL MAP — PHASE 1 (LIVE PURE-PYTHON CORE) → PHASE 2 (WORK-IN-PROGRESS BACKEND SCAFFOLD)
              </div>
              <div style="display:grid;grid-template-columns:1fr 1.35fr 1.35fr;gap:14px;font-size:13px;line-height:1.5;">
                <div style="background:#1E293B;padding:14px;border-radius:8px;border-left:4px solid #94A3B8;">
                  <div style="font-weight:700;color:#E2E8F0;margin-bottom:6px;">1. Verified Inputs</div>
                  • <b>3 Mexican Cards:</b> <code>Santander Unique</code> (1:1 → Iberia only), <code>BBVA</code> (2.6:1 → Iberia, 1.6:1 → AM), <code>Amex México</code> (1:1 → Iberia, BA, AF, AM)<br/>
                  • <b>2 Paid Flight Routes:</b> <code>CDG ↔ MEX</code> on Aeroméxico (SkyTeam) &amp; <code>MEX ↔ MAD</code> on Iberia (Oneworld)
                </div>
                <div style="background:#064E3B;padding:14px;border-radius:8px;border-left:4px solid #10B981;">
                  <div style="font-weight:700;color:#6EE7B7;margin-bottom:6px;">🟢 2. Phase 1: Pure-Python Core (LIVE NOW in <code>src/core/</code>)</div>
                  • <code>seed_data.py</code>: Verified transfer rules, airport departure taxes (<code>CDG</code> $75, <code>MAD</code> $42, <code>MEX</code> TUA $65), and unlock targets (<code>10k</code> AM national, <code>6k/10k</code> VS promo, <code>4.5k/7k</code> Alaska Atmos)<br/>
                  • <code>calculator.py</code>: Haversine Distance, Revenue vs. Distance Crediting, and Static <b>EU261</b> (€600 vs. €0)
                </div>
                <div style="background:#451A03;padding:14px;border-radius:8px;border-left:4px solid #F59E0B;">
                  <div style="font-weight:700;color:#FCD34D;margin-bottom:6px;">🟡 3. Phase 2: Production Backend (WIP <code># TODO</code> Scaffolds)</div>
                  • <code>src/core/ingestion_client.py</code>: Live GDS Tax/YQ Parser &amp; Bank Promo Webhook<br/>
                  • <code>src/db/</code> (<code>session.py</code>, <code>repository.py</code>): Async PostgreSQL 16 (<code>asyncpg</code>)<br/>
                  • <code>src/api/</code> &amp; <code>src/serverless/</code>: FastAPI REST Endpoints + AWS Lambda <code>Mangum</code>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div style="background:#0F172A;color:#F8FAFC;padding:20px 24px;border-radius:12px;border:1px solid #334155;margin-bottom:18px;font-family:sans-serif;">
              <div style="font-size:15px;font-weight:700;color:#38BDF8;margin-bottom:12px;letter-spacing:0.4px;">
                🗺️ MAPA ARQUITECTÓNICO — FASE 1 (MOTOR PYTHON EN VIVO) → FASE 2 (BACKEND EN CONSTRUCCIÓN # TODO)
              </div>
              <div style="display:grid;grid-template-columns:1fr 1.35fr 1.35fr;gap:14px;font-size:13px;line-height:1.5;">
                <div style="background:#1E293B;padding:14px;border-radius:8px;border-left:4px solid #94A3B8;">
                  <div style="font-weight:700;color:#E2E8F0;margin-bottom:6px;">1. Entradas Verificadas</div>
                  • <b>3 Tarjetas en México:</b> <code>Santander Unique</code> (1:1 → exclusivo Iberia), <code>BBVA</code> (2.6:1 → Iberia, 1.6:1 → AM), <code>Amex México</code> (1:1 → Iberia, BA, AF, AM)<br/>
                  • <b>2 Rutas de Vuelos Pagados:</b> <code>CDG ↔ MEX</code> en Aeroméxico (SkyTeam) y <code>MEX ↔ MAD</code> en Iberia (Oneworld)
                </div>
                <div style="background:#064E3B;padding:14px;border-radius:8px;border-left:4px solid #10B981;">
                  <div style="font-weight:700;color:#6EE7B7;margin-bottom:6px;">🟢 2. Fase 1: Motor en Python Puro (ACTIVO AHORA en <code>src/core/</code>)</div>
                  • <code>seed_data.py</code>: Tasas reales, impuestos por aeropuerto de salida (<code>CDG</code> $75, <code>MAD</code> $42, <code>MEX</code> TUA $65) y metas (<code>10k</code> nacional AM, <code>6k/10k</code> promo VS, <code>4.5k/7k</code> Alaska Atmos)<br/>
                  • <code>calculator.py</code>: Distancia Haversine, Gasto vs. Distancia, y Regla <b>EU261</b> (€600 vs. €0)
                </div>
                <div style="background:#451A03;padding:14px;border-radius:8px;border-left:4px solid #F59E0B;">
                  <div style="font-weight:700;color:#FCD34D;margin-bottom:6px;">🟡 3. Fase 2: Backend de Producción (Scaffolds <code># TODO</code> en Progreso)</div>
                  • <code>src/core/ingestion_client.py</code>: Lector GDS de Impuestos/YQ y Bonos Bancarios<br/>
                  • <code>src/db/</code> (<code>session.py</code>, <code>repository.py</code>): PostgreSQL 16 Asíncrono (<code>asyncpg</code>)<br/>
                  • <code>src/api/</code> y <code>src/serverless/</code>: Rutas REST en FastAPI + AWS Lambda <code>Mangum</code>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.graphviz_chart(
        r"""
        digraph LoyaltyArbitrageClean {
            rankdir=LR;
            node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, margin="0.18,0.10"];
            edge [fontname="Helvetica", fontsize=9, color="#475569"];

            subgraph cluster_inputs {
                label="Inputs";
                style="dashed,rounded";
                color="#64748B";
                in_cards  [label="🇲🇽 3 Mexican Credit Cards\n• Santander Unique (1:1 → Iberia Only)\n• BBVA (2.6:1 → Iberia | 1.6:1 → AM)\n• Amex MX (1:1 → Iberia, BA, AF, AM)", fillcolor="#F1F5F9", color="#94A3B8"];
                in_flight [label="🛫 2 Paid Flight Routes\n• CDG ↔ MEX on Aeroméxico (SkyTeam)\n• MEX ↔ MAD on Iberia (Oneworld)", fillcolor="#F1F5F9", color="#94A3B8"];
            }

            subgraph cluster_phase1 {
                label="🟢 PHASE 1: LIVE PURE-PYTHON CORE (src/core/)";
                style="rounded,filled";
                fillcolor="#ECFDF5";
                color="#10B981";
                fontcolor="#065F46";

                calc_cards [label="Bank Transfer Optimizer\n• 21,000 Avios MEX→MAD Economy\n• Avios & Money Flexible Slider\n• 130-pt BBVA / 1,000-pt Rounding", fillcolor="#D1FAE5", color="#059669"];
                calc_flights [label="Flight Crediting & EU261 Engine\n• AM Rewards (<10k national) vs VS (6k/10k W CUN→LHR)\n• IB/BA Spend (7 Avios/€) vs Alaska Atmos (4.5k/7k)\n• Origin Tax Stripper & EU261 (€600 vs €0)", fillcolor="#6EE7B7", color="#047857"];
            }

            subgraph cluster_phase2 {
                label="🟡 PHASE 2: WORK-IN-PROGRESS SCAFFOLD (# TODO)";
                style="rounded,filled";
                fillcolor="#FFFBEB";
                color="#F59E0B";
                fontcolor="#92400E";

                db  [label="src/db/ (PostgreSQL 16 + asyncpg)\n[# TODO] LoyaltyRepository CRUD", fillcolor="#FEF3C7", color="#D97706"];
                api [label="src/api/ & src/serverless/\n[# TODO] FastAPI + AWS Lambda Mangum", fillcolor="#FEF3C7", color="#D97706"];
            }

            in_cards -> calc_cards;
            in_flight -> calc_flights;
            calc_cards -> db [style=dashed, label="Phase 2"];
            calc_flights -> db [style=dashed, label="Phase 2"];
            db -> api [style=dashed, label="Phase 2"];
        }
        """
    )

# ===========================================================================
# TAB 2: MEXICAN CARDS -> EUROPE (SANTANDER UNIQUE 1:1, BBVA, AMEX MEXICO)
# ===========================================================================
with tab2:
    st.subheader(
        "💳 Mexican Credit Card Transfers to Europe (`MEX → MAD`)"
        if not is_es
        else "💳 Transferencia de Puntos Bancarios en México para Volar a Europa (`MEX → MAD`)"
    )
    st.caption(
        "Compares Santander Unique Rewards (1:1 to Iberia Club only), BBVA Puntos (2.6:1 to Iberia vs. 1.6:1 to Aeroméxico), and Amex México (1:1 to Iberia, BA, Flying Blue, Aeroméxico)."
        if not is_es
        else "Compara Santander Unique Rewards (1:1 exclusivo a Iberia Club), Puntos BBVA (2.6:1 a Iberia vs. 1.6:1 a Aeroméxico) y Amex México (1:1 a Iberia, BA, Flying Blue y Aeroméxico)."
    )

    tc1, tc2, tc3, tc4 = st.columns(4)
    with tc1:
        cabin_pick = st.selectbox(
            "1. Select Cabin on MEX → MAD" if not is_es else "1. Selecciona Cabina en MEX → MAD",
            options=[CabinClass.ECONOMY, CabinClass.BUSINESS],
            format_func=lambda c: (
                ("💺 Economy Class (21,000 Avios on Iberia vs. 75,000 on Aeroméxico)" if not is_es else "💺 Turista / Economy (21,000 Avios en Iberia vs. 75,000 en Aeroméxico)")
                if c == CabinClass.ECONOMY
                else ("💺 Business Class (40,500 Avios on Iberia vs. 145,000 on Aeroméxico)" if not is_es else "💺 Clase Ejecutiva / Business (40,500 Avios en Iberia vs. 145,000 en Aeroméxico)")
            ),
        )
    with tc2:
        bank_pick = st.selectbox(
            "2. Filter by Mexican Credit Card" if not is_es else "2. Filtrar por Tarjeta en México",
            options=["ALL_MX", "SANTANDER_MX", "BBVA_MX", "AMEX_MX"],
            format_func=lambda b: {
                "ALL_MX": "🇲🇽 All 3 Mexican Cards (Santander, BBVA, Amex MX)" if not is_es else "🇲🇽 Las 3 Tarjetas en México (Santander, BBVA, Amex MX)",
                "SANTANDER_MX": "🟥 Santander Unique Rewards (1 : 1 → Iberia Club Only)",
                "BBVA_MX": "🟦 BBVA México — Puntos BBVA (2.6 : 1 → Iberia | 1.6 : 1 → Aeroméxico)",
                "AMEX_MX": "🟦 American Express México (1 : 1 → Iberia, BA, Flying Blue, AM)",
            }[b],
        )
    with tc3:
        promo_bonus = st.slider(
            "3. Optional Bank Transfer Bonus (%)" if not is_es else "3. Bono Promocional de Transferencia (%)",
            min_value=0,
            max_value=50,
            value=0,
            step=5,
            help="Starts at 0% base ratios (1:1 Santander, 2.6:1 BBVA, 1:1 Amex). Slide up to test 15%–50% bank transfer promotions.",
        )
    with tc4:
        avios_money_pct = st.slider(
            "4. Iberia 'Avios & Money' (% of Avios Used)" if not is_es else "4. Opción 'Avios & Money' de Iberia (% de Avios)",
            min_value=50,
            max_value=100,
            value=100,
            step=10,
            help="At 100%, you pay all 21,000 Avios. Slide down (50%–90%) to pay even fewer Avios + a small cash co-pay while keeping full Avios ticket flexibility!",
        )

    default_cash_val = 680.0 if cabin_pick == CabinClass.ECONOMY else 2450.0
    pathways = _run_mex_mad_transfers(
        cabin=cabin_pick,
        bank_filter=bank_pick,
        bonus_pct=float(promo_bonus),
        cash_fare_usd=default_cash_val,
        is_es=is_es,
    )

    if pathways:
        winner = pathways[0]
        worst = pathways[-1]
        scaled_avios = int(round(winner.award_miles_required * (avios_money_pct / 100.0)))
        scaled_bank_pts = int(round(winner.bank_points_required * (avios_money_pct / 100.0)))
        extra_copay = round((winner.award_miles_required - scaled_avios) * 0.0135, 0)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric(
            "Iberia Avios Needed (MEX→MAD)" if not is_es else "Avios Requeridos en Iberia (MEX→MAD)",
            f"{scaled_avios:,} Avios",
            "100% Avios (Full)" if avios_money_pct == 100 else f"Avios & Money ({avios_money_pct}% Avios)",
        )
        k2.metric(
            "Santander Unique / Amex MX (1:1)" if not is_es else "Santander Unique / Amex MX (1:1)",
            f"{scaled_bank_pts if winner.bank_code != 'BBVA_MX' else int(round(scaled_avios / (1.0 + promo_bonus / 100.0))):,} pts",
            "1 Unique Point = 1 Avios",
        )
        # Find BBVA -> Iberia row for metric card 3
        bbva_ib_row = next((p for p in pathways if p.bank_code == "BBVA_MX" and p.booking_program_code == "IB_PLUS"), None)
        bbva_am_row = next((p for p in pathways if p.bank_code == "BBVA_MX" and p.booking_program_code == "AM_RW"), None)
        if bbva_ib_row:
            bbva_scaled = int(round(bbva_ib_row.bank_points_required * (avios_money_pct / 100.0)))
            k3.metric(
                "Puntos BBVA → Iberia (2.6:1)" if not is_es else "Puntos BBVA → Iberia (2.6:1)",
                f"{bbva_scaled:,} Puntos BBVA",
                "vs. 120,000 Puntos BBVA on Aeroméxico!" if cabin_pick == CabinClass.ECONOMY else "vs. 232,000 Puntos BBVA on Aeroméxico!",
            )
        else:
            k3.metric("Taxes & TUA", f"${winner.taxes_and_yq_usd:.0f} USD", f"~${winner.taxes_and_yq_usd * MXN_PER_USD:,.0f} MXN")

        k4.metric(
            "Ticket Flexibility" if not is_es else "Flexibilidad del Boleto",
            "Full Avios Flexibility" if not is_es else "Boleto Flexible Avios",
            "Changes / Refunds (~€25)" if not is_es else "Cambios y Reembolso (~€25)",
        )

        if avios_money_pct < 100:
            if not is_es:
                st.info(
                    f"💡 **Iberia 'Avios & Money' Active ({avios_money_pct}% Avios):** Instead of `{winner.award_miles_required:,} Avios`, "
                    f"you only need **`{scaled_avios:,} Avios`** + `${winner.taxes_and_yq_usd + extra_copay:.0f} USD` total cash co-pay, "
                    f"while keeping **full Avios ticket change and refund flexibility**!"
                )
            else:
                st.info(
                    f"💡 **Opción 'Avios & Money' Activa ({avios_money_pct}% Avios):** En lugar de `{winner.award_miles_required:,} Avios`, "
                    f"solo necesitas **`{scaled_avios:,} Avios`** + `${winner.taxes_and_yq_usd + extra_copay:.0f} USD` de copago total, "
                    f"conservando **toda la flexibilidad de cambios y reembolso de los boletos con Avios**."
                )

        rows = []
        for idx, p in enumerate(pathways, start=1):
            val_mxn = p.effective_cents_per_point * (MXN_PER_USD / 100.0)
            if not is_es:
                rows.append(
                    {
                        "Rank": f"#{idx}",
                        "Mexican Credit Card": p.bank_currency_name,
                        "Transfer To Program": f"{p.booking_program_name} ({p.booking_program_code})",
                        "Operating Airline": p.operating_carrier_iata,
                        "Award Miles / Avios Needed": f"{p.award_miles_required:,}",
                        "Effective Ratio": f"{p.effective_transfer_ratio}:1",
                        "Bank Points Required": f"{p.bank_points_required:,} pts",
                        "Taxes & MEX TUA": f"${p.taxes_and_yq_usd:,.0f} USD (${p.taxes_and_yq_usd * MXN_PER_USD:,.0f} MXN)",
                        "Value per Point": f"${val_mxn:.2f} MXN ({p.effective_cents_per_point:.2f}¢ USD)",
                        "Transfer Rule & Flexibility": p.notes,
                    }
                )
            else:
                rows.append(
                    {
                        "Posición": f"#{idx}",
                        "Tarjeta en México": p.bank_currency_name,
                        "Transferir a Programa": f"{p.booking_program_name} ({p.booking_program_code})",
                        "Aerolínea": p.operating_carrier_iata,
                        "Millas / Avios Req.": f"{p.award_miles_required:,}",
                        "Tasa Efectiva": f"{p.effective_transfer_ratio}:1",
                        "Puntos Bancarios Req.": f"{p.bank_points_required:,} pts",
                        "Impuestos y TUA MEX": f"${p.taxes_and_yq_usd:,.0f} USD (${p.taxes_and_yq_usd * MXN_PER_USD:,.0f} MXN)",
                        "Valor por Punto": f"${val_mxn:.2f} MXN ({p.effective_cents_per_point:.2f}¢ USD)",
                        "Regla de Conversión y Flexibilidad": p.notes,
                    }
                )
        st.dataframe(rows, use_container_width=True, hide_index=True)

# ===========================================================================
# TAB 3: PAID FLIGHT CREDITING (STRICTLY CDG->MEX ON AM & MEX->MAD ON IB)
# ===========================================================================
with tab3:
    st.subheader(
        "🛫 Paid Flight Crediting Simulator (`CDG ↔ MEX` on Aeroméxico & `MEX ↔ MAD` on Iberia)"
        if not is_es
        else "🛫 Simulador de Acreditación de Vuelos Pagados (`CDG ↔ MEX` en Aeroméxico y `MEX ↔ MAD` en Iberia)"
    )
    st.caption(
        "Demonstrates why crediting a cheap transatlantic flight to the operating airline ('Own Metal') fails to unlock even a basic short-haul ticket, whereas crediting to the right alliance partner immediately unlocks a reward flight."
        if not is_es
        else "Demuestra por qué acreditar un vuelo trasatlántico económico a la propia aerolínea ('Own Metal') ni siquiera alcanza para el boleto premio más bajo, mientras que acreditarlo al socio correcto de la alianza desbloquea un vuelo premio de inmediato."
    )

    r1, r2, r3 = st.columns(3)
    with r1:
        itinerary_choice = st.selectbox(
            "1. Select Route & Operating Airline" if not is_es else "1. Selecciona Ruta y Aerolínea Operadora",
            options=[
                ("CDG", "MEX", "AM", "🇫🇷➡️🇲🇽 CDG ↔ MEX on Aeroméxico (AM — SkyTeam: AM 10k National vs. Virgin Atlantic 6k/10k W CUN→LHR!)" if not is_es else "🇫🇷➡️🇲🇽 CDG ↔ MEX en Aeroméxico (AM — SkyTeam: Meta 10k Nacional AM vs. Virgin Atlantic 6k/10k W CUN→LHR!)"),
                ("MEX", "MAD", "IB", "🇲🇽➡️🇪🇸 MEX ↔ MAD on Iberia (IB — Oneworld: IB/BA Spend vs. Alaska Atmos 4,500 / 7,000-pt Unlock!)" if not is_es else "🇲🇽➡️🇪🇸 MEX ↔ MAD en Iberia (IB — Oneworld: IB/BA por Gasto vs. Alaska Atmos 4,500 / 7,000 pts!)"),
            ],
            format_func=lambda x: x[3],
        )
    with r2:
        b_class_choice = st.selectbox(
            "2. Select Booking Class" if not is_es else "2. Selecciona Clase Tarifaria",
            options=["K", "Y", "W", "I", "J", "V"],
            format_func=lambda c: {
                "K": ("K — Discounted Economy (75% on Virgin Atlantic / 50% on Alaska Atmos)" if not is_es else "K — Turista Descuento (75% en Virgin Atlantic / 50% en Alaska Atmos)"),
                "Y": ("Y — Standard Economy (150% on Virgin Atlantic / 100% on Alaska Atmos)" if not is_es else "Y — Turista Estándar (150% en Virgin Atlantic / 100% en Alaska Atmos)"),
                "W": ("W — Premium Economy / AM Plus (150% on Virgin Atlantic / 100% on Alaska Atmos)" if not is_es else "W — Premium Economy / AM Plus (150% en Virgin Atlantic / 100% en Alaska Atmos)"),
                "I": ("I — Discounted Business / Clase Premier (150% on Virgin / 125% on Alaska)" if not is_es else "I — Ejecutiva / Clase Premier Descuento (150% en Virgin / 125% en Alaska)"),
                "J": ("J — Full-Fare Business (250% on Virgin Atlantic & Alaska Atmos)" if not is_es else "J — Ejecutiva Flexible (250% en Virgin Atlantic y Alaska Atmos)"),
                "V": ("V — Deep-Discount Economy (25% Distance)" if not is_es else "V — Turista Promo Básica (25% Distancia)"),
            }[c],
            index=0,  # Default to 'K' Discounted Economy!
        )
    with r3:
        trip_type = st.radio(
            "3. Itinerary Type" if not is_es else "3. Tipo de Viaje",
            options=["ROUND_TRIP", "ONE_WAY"],
            format_func=lambda t: ("🔄 Round-Trip (2 Segments)" if not is_es else "🔄 Viaje Redondo (2 Tramos)") if t == "ROUND_TRIP" else ("➡️ One-Way (1 Segment)" if not is_es else "➡️ Sencillo (1 Tramo)"),
            horizontal=True,
        )

    orig_c, dest_c, op_carrier, _ = itinerary_choice
    is_rt = trip_type == "ROUND_TRIP"

    # Default cheap transatlantic Economy fare so the contrast is immediately visible:
    # - On CDG<->MEX (AM): $450/leg all-in ($900 RT) -> strips $75 CDG tax + $65 MEX TUA = $760 eligible spend -> 6,080 AM points (< 10,000 national flight!) vs 8,572 VS Points (unlocks 6,000-pt CUN->LHR!)
    # - On MEX<->MAD (IB): $325/leg all-in ($650 RT) -> strips $65 MEX TUA + $42 MAD tax = $543 eligible spend -> 3,519 Avios on IB & BA (< 4,500 Avios!) vs 5,634 Atmos Points on Alaska (unlocks 4,500-pt flight!)
    default_leg_price = (450.0 if op_carrier == "AM" else 325.0) if b_class_choice in ("V", "K", "Y") else 1400.0

    sp1, sp2 = st.columns([1, 2])
    with sp1:
        seg_all_in_usd = st.slider(
            ("4. All-In Ticket Price per One-Way Leg (USD)" if not is_es else "4. Precio Total con Impuestos por Tramo Sencillo (USD)"),
            min_value=200.0,
            max_value=4000.0,
            value=float(default_leg_price),
            step=25.0,
        )

    ap_orig = CLEAN_AIRPORTS[orig_c]
    ap_dest = CLEAN_AIRPORTS[dest_c]
    elig_leg1, tax_leg1, tax_lbl1 = _calculate_segment_spend_and_tax(ap_orig, float(seg_all_in_usd))
    elig_leg2, tax_leg2, tax_lbl2 = _calculate_segment_spend_and_tax(ap_dest, float(seg_all_in_usd))

    with sp2:
        if is_rt:
            if not is_es:
                st.info(
                    f"🧾 **Accurate Per-Origin Departure Tax Breakdown (`{orig_c} ↔ {dest_c}`):**  \n"
                    f"• **Leg 1 (`{orig_c} → {dest_c}`):** Strips **{tax_lbl1}** → Eligible `Base + YQ`: **${elig_leg1:,.2f} USD**  \n"
                    f"• **Leg 2 (`{dest_c} → {orig_c}`):** Strips **{tax_lbl2}** → Eligible `Base + YQ`: **${elig_leg2:,.2f} USD**"
                )
            else:
                st.info(
                    f"🧾 **Desglose Exacto de Impuestos por Aeropuerto de Salida (`{orig_c} ↔ {dest_c}`):**  \n"
                    f"• **Tramo 1 (`{orig_c} → {dest_c}`):** Descuenta **{tax_lbl1}** → `Base + YQ` Elegible: **${elig_leg1:,.2f} USD**  \n"
                    f"• **Tramo 2 (`{dest_c} → {orig_c}`):** Descuenta **{tax_lbl2}** → `Base + YQ` Elegible: **${elig_leg2:,.2f} USD**"
                )
        else:
            st.info(
                f"🧾 **Departure Tax Stripped (`{orig_c} → {dest_c}`):** Strips **{tax_lbl1}** → Eligible `Base + YQ`: **${elig_leg1:,.2f} USD**"
            )

    built_segments = [
        FlightSegment(orig_c, dest_c, op_carrier, b_class_choice, ticketing_carrier=op_carrier, total_ticket_price_usd=float(seg_all_in_usd))
    ]
    if is_rt:
        built_segments.append(
            FlightSegment(dest_c, orig_c, op_carrier, b_class_choice, ticketing_carrier=op_carrier, total_ticket_price_usd=float(seg_all_in_usd))
        )

    one_way_mi, one_way_km = haversine_distance(ap_orig.latitude, ap_orig.longitude, ap_dest.latitude, ap_dest.longitude)
    mult_legs = 2 if is_rt else 1
    eu_out = evaluate_eu261_segment(ap_orig, ap_dest, op_carrier)
    eu_ret = evaluate_eu261_segment(ap_dest, ap_orig, op_carrier) if is_rt else None

    sim_rankings = _run_paid_flight_simulation(built_segments, is_es=is_es)
    sample_prog = sim_rankings[0]

    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric(
        "Total Great Circle Distance" if not is_es else "Distancia Total Gran Círculo",
        f"{one_way_mi * mult_legs:,.0f} mi",
        f"{one_way_km * mult_legs:,.0f} km ({mult_legs} {'tramos' if is_es and is_rt else ('tramo' if is_es else ('legs' if is_rt else 'leg'))})",
    )
    m_col2.metric(
        "Total Eligible Spend (Base + YQ)" if not is_es else "Gasto Elegible Total (Base + YQ)",
        f"${sample_prog.eligible_spend_usd:,.2f} USD",
        (f"Departure Taxes Stripped: ${sample_prog.estimated_gov_taxes_stripped_usd:,.2f}" if not is_es else f"Impuestos de Salida Descontados: ${sample_prog.estimated_gov_taxes_stripped_usd:,.2f}"),
    )
    m_col3.metric(
        (f"Outbound EU261 ({orig_c}→{dest_c})" if not is_es else f"EU261 Ida ({orig_c}→{dest_c})"),
        (f"€{eu_out['compensation_eur']} Protected" if not is_es else f"€{eu_out['compensation_eur']} Protegido") if eu_out["is_eligible"] else ("€0 (Not Covered)" if not is_es else "€0 (No Cubierto)"),
        ("Departs EU Airport" if ap_orig.is_eu_eea_ch else f"Arrives EU on {op_carrier}"),
    )
    if is_rt and eu_ret:
        m_col4.metric(
            (f"Return EU261 ({dest_c}→{orig_c})" if not is_es else f"EU261 Regreso ({dest_c}→{orig_c})"),
            (f"€{eu_ret['compensation_eur']} Protected" if not is_es else f"€{eu_ret['compensation_eur']} Protegido") if eu_ret["is_eligible"] else ("€0 (Not Covered — Non-EU Carrier)" if not is_es else "€0 (No Cubierto — Aerolínea No-UE)"),
            ("Departs EU Airport" if ap_dest.is_eu_eea_ch else f"Departs {dest_c} on {op_carrier}"),
        )
    else:
        m_col4.metric(
            "Alliance Evaluated" if not is_es else "Alianza Evaluada",
            sample_prog.alliance.value,
            sample_prog.own_metal_warning or "",
        )

    metal_res = next((r for r in sim_rankings if r.is_operating_metal_program), None)
    dist_partners = [r for r in sim_rankings if not r.is_operating_metal_program and "DISTANCE" in r.calculation_basis]
    top_partner = dist_partners[0] if dist_partners else next((r for r in sim_rankings if not r.is_operating_metal_program), None)

    if metal_res and top_partner:
        metal_outcome = (
            "; ".join(metal_res.unlocked_short_haul_awards)
            if metal_res.unlocked_short_haul_awards
            else ("; ".join(metal_res.flagship_sweet_spot_progress))
        )
        partner_outcome = (
            "; ".join(top_partner.unlocked_short_haul_awards)
            if top_partner.unlocked_short_haul_awards
            else ("; ".join(top_partner.flagship_sweet_spot_progress))
        )
        if not is_es:
            st.success(
                f"🔀 **Own Metal (`{metal_res.program_name}`) vs. Smart Alliance Partner (`{top_partner.program_name}`):**  \n"
                f"• **Crediting to Operating Airline ({metal_res.program_name} — `{metal_res.calculation_basis}`):** Earns **{metal_res.redeemable_miles_earned:,}** points "
                f"({metal_res.progress_to_gold_pct}% toward **{metal_res.own_metal_warning}**) → **{metal_outcome}**  \n"
                f"• **Smart Partner Switch ({top_partner.program_name} — `{top_partner.calculation_basis}`):** Earns **{top_partner.redeemable_miles_earned:,}** points "
                f"({top_partner.progress_to_gold_pct}% toward **{top_partner.own_metal_warning}**) → **{partner_outcome}**"
            )
        else:
            st.success(
                f"🔀 **Propia Aerolínea (`{metal_res.program_name}`) vs. Socio Inteligente de Alianza (`{top_partner.program_name}`):**  \n"
                f"• **Propia Aerolínea ({metal_res.program_name} — `{metal_res.calculation_basis}`):** Acumula **{metal_res.redeemable_miles_earned:,}** puntos "
                f"({metal_res.progress_to_gold_pct}% hacia **{metal_res.own_metal_warning}**) → **{metal_outcome}**  \n"
                f"• **Socio Inteligente ({top_partner.program_name} — `{top_partner.calculation_basis}`):** Acumula **{top_partner.redeemable_miles_earned:,}** puntos "
                f"({top_partner.progress_to_gold_pct}% hacia **{top_partner.own_metal_warning}**) → **{partner_outcome}**"
            )

    table_cred = []
    for r in sim_rankings:
        outcome_text = " | ".join(r.unlocked_short_haul_awards if r.unlocked_short_haul_awards else r.flagship_sweet_spot_progress)
        if not is_es:
            table_cred.append(
                {
                    "Loyalty Program": f"{r.program_name} ({r.program_code})",
                    "Alliance": r.alliance.value,
                    "Role": "🏠 Own Metal Default" if r.is_operating_metal_program else "🤝 Alliance Partner",
                    "Calculation Basis": r.calculation_basis,
                    "Points / Miles Earned": f"{r.redeemable_miles_earned:,}",
                    "Alliance Status Tier & Progress": f"{r.progress_to_gold_pct}% toward {r.own_metal_warning} ({r.status_points_earned:,.0f} / {r.gold_status_threshold:,.0f})",
                    "Immediate Reward Flights Unlocked": outcome_text,
                }
            )
        else:
            table_cred.append(
                {
                    "Programa de Lealtad": f"{r.program_name} ({r.program_code})",
                    "Alianza": r.alliance.value,
                    "Rol": "🏠 Propia Aerolínea (Metal)" if r.is_operating_metal_program else "🤝 Socio de Alianza",
                    "Base de Cálculo": r.calculation_basis,
                    "Puntos / Millas Ganados": f"{r.redeemable_miles_earned:,}",
                    "Nivel de Estatus en la Alianza": f"{r.progress_to_gold_pct}% hacia {r.own_metal_warning} ({r.status_points_earned:,.0f} / {r.gold_status_threshold:,.0f})",
                    "Vuelos Premio Desbloqueados": outcome_text,
                }
            )
    st.dataframe(table_cred, use_container_width=True, hide_index=True)

# ===========================================================================
# TAB 4: PHASE 2 WORK-IN-PROGRESS CODE INSPECTOR (# TODO BACKLOG)
# ===========================================================================
with tab4:
    st.subheader(
        "🛠️ Work-in-Progress (WIP) Phase 2 Backend Scaffolding (`src/db/`, `src/api/`, `src/serverless/`)"
        if not is_es
        else "🛠️ Inspector de Backend en Progreso — Fase 2 (`src/db/`, `src/api/`, `src/serverless/`)"
    )
    st.markdown(
        (
            "This project separates the **working Phase 1 pure-Python domain engine (`src/core/`)** from the **Phase 2 production backend backlog (`# TODO`)**. "
            "Select any scaffolded module below to inspect its interface and docstring specification, or click the button to verify it raises `NotImplementedError`."
        )
        if not is_es
        else (
            "Este proyecto separa el **motor matemático de Fase 1 que ya funciona en Python puro (`src/core/`)** del **backlog de ingeniería de Fase 2 (`# TODO`)**. "
            "Selecciona cualquier módulo abajo para inspeccionar su interfaz y especificaciones `# TODO`, o pulsa el botón para verificar que lanza `NotImplementedError`."
        )
    )

    scaffold_choice = st.selectbox(
        "Select Phase 2 `# TODO` Module to Inspect" if not is_es else "Selecciona Módulo `# TODO` de Fase 2 a Inspeccionar",
        options=[
            ("src/db/session.py — DatabaseSessionManager.init_engine (PostgreSQL + asyncpg Pool)", DatabaseSessionManager.init_engine),
            ("src/db/repository.py — LoyaltyRepository.get_active_transfer_rules (SQL Transfer Matrix)", LoyaltyRepository.get_active_transfer_rules),
            ("src/db/repository.py — LoyaltyRepository.get_earning_rules_for_segments (Batch SQL Lookup)", LoyaltyRepository.get_earning_rules_for_segments),
            ("src/db/repository.py — LoyaltyRepository.upsert_transfer_bonus (Promotional Bonus Upsert)", LoyaltyRepository.upsert_transfer_bonus),
            ("src/api/routes.py — post_optimize_transfer (POST /api/v1/optimize-transfer)", api_routes.post_optimize_transfer),
            ("src/api/routes.py — post_simulate_flight_crediting (POST /api/v1/simulate-crediting)", api_routes.post_simulate_flight_crediting),
            ("src/serverless/lambda_handler.py — api_gateway_handler (AWS Lambda + Mangum)", lambda_handler.api_gateway_handler),
            ("src/serverless/lambda_handler.py — scheduled_bonus_refresh_handler (EventBridge 12h Cron)", lambda_handler.scheduled_bonus_refresh_handler),
            ("src/core/ingestion_client.py — ExternalIngestionClient.resolve_exact_ticket_tax_breakdown", ExternalIngestionClient.resolve_exact_ticket_tax_breakdown),
        ],
        format_func=lambda x: x[0],
    )

    _, fn_obj = scaffold_choice
    st.code(inspect.getsource(fn_obj), language="python")

    btn_label = (
        "▶️ Execute Selected Phase 2 Stub (Verify `NotImplementedError`)"
        if not is_es
        else "▶️ Ejecutar Función Stub de Fase 2 (Verificar `NotImplementedError`)"
    )
    if st.button(btn_label):
        try:
            if fn_obj == lambda_handler.api_gateway_handler:
                lambda_handler.api_gateway_handler({}, None)
            elif fn_obj == lambda_handler.scheduled_bonus_refresh_handler:
                lambda_handler.scheduled_bonus_refresh_handler({}, None)
            else:
                raise NotImplementedError("TODO: Implement in Phase 2")
        except NotImplementedError as exc:
            st.warning(f"Confirmed Work-in-Progress Scaffold → Raised `NotImplementedError: {exc}`")