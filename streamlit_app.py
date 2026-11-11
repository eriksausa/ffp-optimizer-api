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

# Verified Mexican Credit Card transfer rules:
CLEAN_TRANSFER_RULES: list[TransferPartnerRule] = [
    TransferPartnerRule("SANTANDER_MX", "IB_PLUS", base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("BBVA_MX", "IB_PLUS", base_ratio=50.0 / 130.0, active_bonus_pct=0.0, min_transfer_increment=130),
    TransferPartnerRule("BBVA_MX", "AM_RW",   base_ratio=0.625, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MX", "IB_PLUS", base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MX", "BA_EC",   base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MX", "AF_FB",   base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MX", "AM_RW",   base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
]

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

# Separate, carrier-specific booking class menus for SkyTeam (Aeroméxico) vs. Oneworld (Iberia)
SKYTEAM_AM_CLASSES: dict[str, dict[str, str]] = {
    "K": {
        "en": "K / L / Q — Economy Clásica (AM: Spend 8x/$1 | Virgin Atlantic: 75% Distance | Flying Blue: 50%)",
        "es": "K / L / Q — Turista Clásica (AM: Por Gasto 8x/$1 | Virgin Atlantic: 75% Distancia | Flying Blue: 50%)",
    },
    "Y": {
        "en": "Y / B / M — Economy Flexible (AM: Spend 8x/$1 | Virgin Atlantic: 150% Distance | Flying Blue: 100%)",
        "es": "Y / B / M — Turista Flexible (AM: Por Gasto 8x/$1 | Virgin Atlantic: 150% Distancia | Flying Blue: 100%)",
    },
    "W": {
        "en": "W — AM Plus / Premier Light (AM: Spend 8x/$1 | Virgin Atlantic: 150% Distance | Flying Blue: 100%)",
        "es": "W — AM Plus / Premier Light (AM: Por Gasto 8x/$1 | Virgin Atlantic: 150% Distancia | Flying Blue: 100%)",
    },
    "I": {
        "en": "I / D — Clase Premier Discount Business (AM: Spend 8x/$1 | Virgin Atlantic: 150% + 200 TP/leg)",
        "es": "I / D — Clase Premier Descuento (AM: Por Gasto 8x/$1 | Virgin Atlantic: 150% + 200 TP/tramo)",
    },
    "J": {
        "en": "J / C — Clase Premier Full Flex Business (AM: Spend 8x/$1 | Virgin Atlantic: 250% + 200 TP/leg)",
        "es": "J / C — Clase Premier Flexible (AM: Por Gasto 8x/$1 | Virgin Atlantic: 250% + 200 TP/tramo)",
    },
    "V": {
        "en": "V / N / R — Economy Básica Promo (AM: Spend 8x/$1 | Virgin Atlantic: 25% Distance)",
        "es": "V / N / R — Turista Básica Promo (AM: Por Gasto 8x/$1 | Virgin Atlantic: 25% Distancia)",
    },
}

ONEWORLD_IB_CLASSES: dict[str, dict[str, str]] = {
    "K": {
        "en": "K / L / S — Turista Óptima / Discount Economy (IB & BA: Spend 7 Avios/€ | Alaska Atmos: 50% Distance)",
        "es": "K / L / S — Turista Óptima / Descuento (IB y BA: Por Gasto 7 Avios/€ | Alaska Atmos: 50% Distancia)",
    },
    "Y": {
        "en": "Y / B / H — Turista Confort / Flex Economy (IB & BA: Spend 7 Avios/€ | Alaska Atmos: 100% Distance)",
        "es": "Y / B / H — Turista Confort / Flexible (IB y BA: Por Gasto 7 Avios/€ | Alaska Atmos: 100% Distancia)",
    },
    "W": {
        "en": "W / E / T — Turista Premium / Premium Economy (IB & BA: Spend 7 Avios/€ | Alaska Atmos: 100% Distance)",
        "es": "W / E / T — Turista Premium (IB y BA: Por Gasto 7 Avios/€ | Alaska Atmos: 100% Distancia)",
    },
    "I": {
        "en": "I / R — Business Óptima / Discount Business (IB & BA: Spend 7 Avios/€ | Alaska Atmos: 125% Distance)",
        "es": "I / R — Business Óptima / Descuento (IB y BA: Por Gasto 7 Avios/€ | Alaska Atmos: 125% Distancia)",
    },
    "J": {
        "en": "J / C / D — Business Flexible (IB & BA: Spend 7 Avios/€ | Alaska Atmos: 250% Distance)",
        "es": "J / C / D — Business Flexible (IB y BA: Por Gasto 7 Avios/€ | Alaska Atmos: 250% Distancia)",
    },
    "V": {
        "en": "O / Q / N — Turista Básica Deep-Discount (IB & BA: Spend 7 Avios/€ | Alaska Atmos: 25% Distance)",
        "es": "O / Q / N — Turista Básica Promo (IB y BA: Por Gasto 7 Avios/€ | Alaska Atmos: 25% Distancia)",
    },
}

CLEAN_EARNING_RULES: list[PartnerEarningRule] = [
    # Route 1: Aeroméxico ("AM" — CDG <-> MEX, SkyTeam)
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

    # Route 2: Iberia ("IB" — MEX <-> MAD, Oneworld)
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


def _calculate_segment_spend_and_tax(orig: AirportProfile, total_price_usd: float, is_es: bool = False) -> tuple[float, float, str]:
    """Strips strictly the departure airport's mandatory government tax."""
    tax_usd = min(round(orig.estimated_gov_departure_tax_usd, 2), round(total_price_usd * 0.35, 2))
    eligible_usd = round(max(0.0, total_price_usd - tax_usd), 2)
    if orig.country_code == "MX":
        tax_label = f"Mexican TUA ({orig.iata_code}: ${tax_usd:.0f} USD)" if not is_es else f"TUA Mexicana ({orig.iata_code}: ${tax_usd:.0f} USD)"
    else:
        tax_label = f"EU Departure Tax ({orig.iata_code}: ${tax_usd:.0f} USD)" if not is_es else f"Impuesto Salida UE ({orig.iata_code}: ${tax_usd:.0f} USD)"
    return eligible_usd, tax_usd, tax_label


def _format_program_unlock_summary(prog_code: str, total_miles: int, is_es: bool) -> tuple[bool, str, str]:
    """
    Returns `(unlocked_bool, concise_table_cell, detailed_card_explanation)` tailored to each program's
    key benchmark so the output is crystal clear and never cluttered.
    """
    if prog_code == "AM_RW":
        target = 10000
        if total_miles >= target:
            cnt = total_miles // target
            rem = total_miles % target
            short = f"✅ {cnt}x National Flight in Mexico (10,000 pts) + {rem:,} left" if not is_es else f"✅ {cnt}x Vuelo Nacional en México (10,000 pts) + {rem:,} sobrantes"
            detail = f"Unlocks {cnt}x domestic flight in Mexico (10,000 Puntos AM each) with {rem:,} points left over." if not is_es else f"Desbloquea {cnt}x vuelo nacional en México (10,000 Puntos AM) con {rem:,} puntos sobrantes."
            return True, short, detail
        pct = round((total_miles / target) * 100.0, 1)
        shortage = target - total_miles
        short = f"❌ 0 Flights — Only {pct}% of 10,000-pt National Flight (-{shortage:,} pts short)" if not is_es else f"❌ 0 Vuelos — Solo {pct}% de un Vuelo Nacional de 10,000 pts (faltan {shortage:,} pts)"
        detail = f"Does NOT even reach a single 10,000-point domestic flight in Mexico ({total_miles:,} / 10,000 pts = {pct}%)." if not is_es else f"Ni siquiera alcanza para un vuelo nacional de 10,000 puntos dentro de México ({total_miles:,} / 10,000 pts = {pct}%)."
        return False, short, detail

    if prog_code == "VS_FC":
        if total_miles >= 15000:
            cnt_6k = total_miles // 6000
            short = f"✅ Unlocks 15k AF/KL Europe Flight OR 10k W / {cnt_6k}x 6k Promo CUN→LHR!" if not is_es else f"✅ ¡Desbloquea Vuelo 15k AF/KL a Europa O 10k W / {cnt_6k}x 6k CUN→LHR!"
            detail = (
                f"Immediately unlocks: (1) MEX→Europe on Air France/KLM metal (15,000 VS pts), OR (2) Cancún→London (CUN→LHR) in Premium W (10,000 VS pts), OR (3) {cnt_6k}x CUN→LHR Promo Economy flights (6,000 VS pts each)!"
                if not is_es
                else f"Desbloquea de inmediato: (1) MEX→Europa en Air France/KLM (15,000 VS pts), O (2) Cancún→Londres (CUN→LHR) en Premium W (10,000 VS pts), O (3) {cnt_6k}x vuelos CUN→LHR en Turista Promo (6,000 VS pts c/u)."
            )
            return True, short, detail
        if total_miles >= 10000:
            rem_w = total_miles - 10000
            short = f"✅ Unlocks CUN→LHR in Premium (W) (10,000 pts) OR 1x Economy (6,000 pts)!" if not is_es else f"✅ ¡Desbloquea CUN→LHR en Premium (W) (10,000 pts) O Turista (6,000 pts)!"
            detail = (
                f"Immediately unlocks Cancún→London (CUN→LHR) in Premium Economy W (10,000 VS Points + {rem_w:,} left) OR Economy (6,000 VS Points + {total_miles - 6000:,} left)!"
                if not is_es
                else f"Desbloquea de inmediato Cancún→Londres (CUN→LHR) en Premium Economy W (10,000 VS Points + {rem_w:,} sobrantes) O en Turista (6,000 VS Points + {total_miles - 6000:,} sobrantes)."
            )
            return True, short, detail
        if total_miles >= 6000:
            rem = total_miles - 6000
            pct_w = round((total_miles / 10000.0) * 100.0, 1)
            short = f"✅ Unlocks 1x Promo CUN→LHR (Europe) Economy (6,000 pts + {rem:,} left) | {pct_w}% of 10k W" if not is_es else f"✅ ¡Desbloquea 1x Promo CUN→LHR (Europa) Turista (6,000 pts + {rem:,} sobrantes)!"
            detail = (
                f"Immediately unlocks 1x Off-Peak Promo Cancún→London (CUN→LHR) Economy flight to Europe (6,000 VS Points) with {rem:,} points left over (and reaches {pct_w}% of the 10,000-pt Premium W flight)!"
                if not is_es
                else f"¡Desbloquea de inmediato 1x vuelo Promo Cancún→Londres (CUN→LHR) en Turista a Europa (6,000 VS Points) con {rem:,} puntos sobrantes (y alcanza {pct_w}% del vuelo de 10,000 pts en Premium W)!"
            )
            return True, short, detail
        pct = round((total_miles / 6000.0) * 100.0, 1)
        short = f"❌ 0 Flights — {pct}% ({total_miles:,} / 6,000) toward Promo CUN→LHR Economy" if not is_es else f"❌ 0 Vuelos — {pct}% ({total_miles:,} / 6,000) hacia Promo CUN→LHR Turista"
        detail = short
        return False, short, detail

    if prog_code == "AS_ATMOS":
        if total_miles >= 7000:
            cnt_45 = total_miles // 4500
            rem_70 = total_miles - 7000
            short = f"✅ Unlocks 7,000-pt Medium-Haul Flight (+{rem_w if False else rem_70:,} left) OR {cnt_45}x 4,500-pt Flights!" if not is_es else f"✅ ¡Desbloquea Vuelo de 7,000 pts (+{rem_70:,} sobrantes) O {cnt_45}x Vuelos de 4,500 pts!"
            detail = (
                f"Immediately unlocks a 7,000-point Oneworld reward flight (+{rem_70:,} pts left) OR {cnt_45}x 4,500-point short-haul reward flights!"
                if not is_es
                else f"Desbloquea de inmediato un vuelo premio Oneworld de 7,000 puntos (+{rem_70:,} sobrantes) O {cnt_45}x vuelos cortos de 4,500 puntos."
            )
            return True, short, detail
        if total_miles >= 4500:
            rem = total_miles - 4500
            pct_7k = round((total_miles / 7000.0) * 100.0, 1)
            short = f"✅ Unlocks 1x 4,500-pt Reward Flight (+{rem:,} left) | {pct_7k}% toward 7,000-pt Flight" if not is_es else f"✅ ¡Desbloquea 1x Vuelo Premio de 4,500 pts (+{rem:,} sobrantes) | {pct_7k}% de 7,000 pts!"
            detail = (
                f"Immediately unlocks 1x 4,500-point Oneworld reward flight with {rem:,} points left over (and reaches {pct_7k}% of a 7,000-point reward flight)!"
                if not is_es
                else f"¡Desbloquea de inmediato 1x vuelo premio Oneworld de 4,500 puntos con {rem:,} puntos sobrantes (y alcanza {pct_7k}% de un vuelo de 7,000 puntos)!"
            )
            return True, short, detail
        pct = round((total_miles / 4500.0) * 100.0, 1)
        short = f"❌ 0 Flights — {pct}% ({total_miles:,} / 4,500) toward 4,500-pt Reward Flight" if not is_es else f"❌ 0 Vuelos — {pct}% ({total_miles:,} / 4,500) hacia Vuelo de 4,500 pts"
        return False, short, short

    if prog_code in ("IB_PLUS", "BA_EC"):
        target = 4500 if prog_code == "IB_PLUS" else 4750
        if total_miles >= target:
            cnt = total_miles // target
            rem = total_miles % target
            short = f"✅ Unlocks {cnt}x Short-Haul Flight ({target:,} Avios) + {rem:,} left" if not is_es else f"✅ Desbloquea {cnt}x Vuelo Corto ({target:,} Avios) + {rem:,} sobrantes"
            return True, short, short
        pct = round((total_miles / target) * 100.0, 1)
        shortage = target - total_miles
        short = f"❌ 0 Flights — Only {pct}% of {target:,}-Avios Short-Haul (-{shortage:,} Avios short)" if not is_es else f"❌ 0 Vuelos — Solo {pct}% de un Vuelo Corto de {target:,} Avios (faltan {shortage:,} Avios)"
        detail = (
            f"Because {CLEAN_PROGRAMS[prog_code].program_name} credits by spend (7 Avios/€), this cheap ticket only earns {total_miles:,} Avios — {shortage:,} Avios short of a {target:,}-Avios reward flight."
            if not is_es
            else f"Como {CLEAN_PROGRAMS[prog_code].program_name} acredita por gasto (7 Avios/€), este boleto económico solo da {total_miles:,} Avios — faltan {shortage:,} Avios para el vuelo más bajo de {target:,} Avios."
        )
        return False, short, detail

    # AF_FB or AA_ADV (7,500 threshold)
    target = 7500
    if total_miles >= target:
        cnt = total_miles // target
        rem = total_miles % target
        short = f"✅ Unlocks {cnt}x Short-Haul Reward Flight (7,500 mi) + {rem:,} left" if not is_es else f"✅ Desbloquea {cnt}x Vuelo Corto (7,500 mi) + {rem:,} sobrantes"
        return True, short, short
    pct = round((total_miles / target) * 100.0, 1)
    shortage = target - total_miles
    short = f"❌ 0 Flights — Only {pct}% of 7,500-mi Short-Haul (-{shortage:,} short)" if not is_es else f"❌ 0 Vuelos — Solo {pct}% de un Vuelo de 7,500 mi (faltan {shortage:,})"
    return False, short, short


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
                ratio_desc = "1 Unique Point = 1 Avios (Iberia Club Exclusive)" if not is_es else "1 Unique Point = 1 Avios (Exclusivo Iberia Club)"
            elif rule.bank_code == "BBVA_MX" and rule.program_code == "IB_PLUS":
                ratio_desc = "2.6 Puntos BBVA = 1 Avios (min 130 pts)" if not is_es else "2.6 Puntos BBVA = 1 Avios (mín. 130 pts)"
            elif rule.bank_code == "BBVA_MX" and rule.program_code == "AM_RW":
                ratio_desc = "1.6 Puntos BBVA = 1 Punto Aeroméxico" if not is_es else "1.6 Puntos BBVA = 1 Punto Aeroméxico"
            else:
                ratio_desc = "1 : 1 Membership Rewards"

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
) -> list[dict[str, object]]:
    """Simulates paid flight crediting for CDG<->MEX on AM (SkyTeam) or MEX<->MAD on IB (Oneworld)."""
    primary_carrier = segments[0].operating_carrier.upper()
    rows: list[dict[str, object]] = []

    for prog_code, program in CLEAN_PROGRAMS.items():
        total_miles = 0
        total_status_pts = 0.0
        total_eligible_spend = 0.0
        total_gov_taxes = 0.0
        used_rev = False
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

            eligible_spend, gov_tax, _ = _calculate_segment_spend_and_tax(orig, float(seg.total_ticket_price_usd or 0.0), is_es=is_es)
            total_eligible_spend += eligible_spend
            total_gov_taxes += gov_tax

            ticketing_carrier = (seg.ticketing_carrier or seg.operating_carrier).upper()
            is_revenue_eligible = (
                ticketing_carrier == program.home_carrier_iata
                or (prog_code in {"IB_PLUS", "BA_EC", "AA_ADV"} and ticketing_carrier in {"IB", "BA", "AA"})
            )

            if is_revenue_eligible and eligible_spend > 0 and program.own_ticket_revenue_multiplier is not None:
                if prog_code in {"IB_PLUS", "BA_EC"} and seg.operating_carrier.upper() == "IB":
                    eur_spend = eligible_spend / 1.08
                    seg_miles = int(round(eur_spend * 7.0))
                else:
                    seg_miles = int(round(eligible_spend * program.own_ticket_revenue_multiplier))
                used_rev = True
            else:
                raw_miles = dist_mi * (rule.award_miles_pct / 100.0)
                seg_miles = int(round(max(raw_miles, float(rule.min_award_miles)) if rule.award_miles_pct > 0 else 0.0))

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
        unlocked_ok, short_cell, detail_text = _format_program_unlock_summary(prog_code, total_miles, is_es=is_es)
        basis_label = (
            ("Spend-Based (Revenue)" if not is_es else "Por Gasto (Tarifa + YQ)")
            if used_rev
            else ("Distance-Based (Miles × %)" if not is_es else "Por Distancia (Millas × %)")
        )

        rows.append(
            {
                "program_code": prog_code,
                "program_name": program.program_name,
                "currency_name": program.currency_name,
                "alliance": program.alliance.value,
                "is_own_metal": (program.home_carrier_iata == primary_carrier),
                "is_distance_based": not used_rev,
                "basis_label": basis_label,
                "total_miles": total_miles,
                "status_pts": round(total_status_pts, 1),
                "status_threshold": program.gold_status_threshold,
                "progress_pct": progress_pct,
                "status_tier_name": program.gold_status_tier_name,
                "eligible_spend_usd": round(total_eligible_spend, 2),
                "gov_taxes_usd": round(total_gov_taxes, 2),
                "unlocked_ok": unlocked_ok,
                "short_cell": short_cell,
                "detail_text": detail_text,
            }
        )

    rows.sort(key=lambda r: (bool(r["unlocked_ok"]), int(r["total_miles"]), float(r["progress_pct"])), reverse=True)
    return rows


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
            "**1️⃣ Why Built — Crediting Paid Flights to 'Own Metal' Is Often Not Optimal:**  \n"
            "• **Aeroméxico (`CDG ↔ MEX`) vs. Virgin Atlantic:** The lowest domestic award flight inside Mexico on **Aeroméxico Rewards** costs **10,000 points**. "
            "Flying a discounted round-trip from Paris to Mexico (`CDG ↔ MEX`) and crediting to Aeroméxico's own spend-based program (`8 pts/$1 USD`) earns **~6,080 points—not even enough for a single 10,000-point domestic flight in Mexico**! "
            "Crediting that same flight to SkyTeam partner **Virgin Atlantic Flying Club** (distance-based) earns **8,574 to 17,145 Virgin Points**, "
            "immediately unlocking an **Off-Peak Promo flight from Cancún to London (`CUN → LHR` Europe) for just 6,000 Virgin Points in Economy (or 10,000 pts in Premium `W`)**!  \n"
            "• **Iberia (`MEX ↔ MAD`) vs. Alaska Atmos:** Crediting a cheap Iberia round-trip to **Iberia Club** or **British Airways** (spend-based `7 Avios/€`) earns **~3,519 Avios** (`0` flights unlocked). "
            "Crediting it to **Alaska Airlines Atmos Rewards** (distance-based) earns **5,634+ points**, immediately unlocking a **4,500-point (or 7,000-point) Oneworld reward flight**!"
        )
    else:
        st.info(
            "**1️⃣ Razón #1 — Acreditar un Vuelo Pagado a la Propia Aerolínea ('Own Metal') Casi Nunca Es Óptimo:**  \n"
            "• **Aeroméxico (`CDG ↔ MEX`) vs. Virgin Atlantic:** El vuelo premio nacional más bajo dentro de México en **Aeroméxico Rewards** cuesta **10,000 puntos**. "
            "Un vuelo redondo económico de París a México (`CDG ↔ MEX`) acreditado en Aeroméxico por gasto (`8 pts/$1 USD`) da **~6,080 puntos—¡ni siquiera alcanza para un vuelo nacional de 10,000 puntos en México!** "
            "Acreditado en su socio SkyTeam **Virgin Atlantic Flying Club** (por distancia), da **8,574 a 17,145 Virgin Points**, "
            "desbloqueando de inmediato un **vuelo promo de Cancún a Londres (`CUN → LHR` Europa) por solo 6,000 Virgin Points en Turista (o 10,000 pts en Premium `W`)**.  \n"
            "• **Iberia (`MEX ↔ MAD`) vs. Alaska Atmos:** Un boleto económico en Iberia acreditado en **Iberia Club** o **British Airways** (por gasto `7 Avios/€`) da **~3,519 Avios** (`0` vuelos). "
            "Acreditado en **Alaska Airlines Atmos Rewards** (por distancia) da **5,634+ puntos**, ¡desbloqueando ya un **vuelo premio Oneworld de 4,500 o 7,000 puntos**!"
        )

with col_m2:
    if not is_es:
        st.success(
            "**2️⃣ Why Built — Cardholders Don't Know the True Value of Their Mexican Bank Points (`Santander Unique`, `BBVA`, `Amex México` → `Iberia Avios`):**  \n"
            "• **Santander Unique Rewards:** Transfers **`1 : 1` (`1 Unique Point = 1 Avios`)** exclusively to **Iberia Club**.  \n"
            "• **BBVA México (`Puntos BBVA`):** Transfers **`2.6 : 1`** to **Iberia Club** (min 130 pts) and **`1.6 : 1`** to **Aeroméxico Rewards**.  \n"
            "• **American Express México (`Membership Rewards`):** Transfers **`1 : 1`** to **Iberia Club**, **British Airways**, **Flying Blue**, and **Aeroméxico**.  \n"
            "• **21,000 Avios to Europe + Full Flexibility:** For just **21,000 Avios** one-way, you can fly nonstop **Mexico City to Madrid (`MEX → MAD`)** paying only with Avios. "
            "You can even choose to pay **fewer Avios** using Iberia's **Avios & Money** slider, and **Avios tickets are far more flexible** than cheap cash tickets (easy date changes or refunds)."
        )
    else:
        st.success(
            "**2️⃣ Razón #2 — La Gente No Conoce el Valor Real de sus Puntos Bancarios en México (`Santander Unique`, `BBVA`, `Amex México` → `Iberia Avios`):**  \n"
            "• **Santander Unique Rewards:** Transfiere **`1 : 1` (`1 Unique Point = 1 Avios`)** exclusivamente a **Iberia Club**.  \n"
            "• **BBVA México (`Puntos BBVA`):** Transfiere **`2.6 : 1`** a **Iberia Club** (mín. 130 pts) y **`1.6 : 1`** a **Aeroméxico Rewards**.  \n"
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
            - **`CDG ↔ MEX` on Aeroméxico (`AM`, SkyTeam)**:
              - AM Rewards (`10k` national target) vs. Virgin Atlantic (`6k` Economy / `10k` W `CUN→LHR` promo)
            - **`MEX ↔ MAD` on Iberia (`IB`, Oneworld)**:
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
        st.markdown("### 🇲🇽 Alcance Verificado")
        st.markdown(
            """
            **3 Tarjetas en México (Pestaña 2)**
            - **Santander Unique**: `1 : 1` → Iberia Club *(exclusivo)*
            - **Puntos BBVA**: `2.6 : 1` → Iberia (`mín 130`) · `1.6 : 1` → Aeroméxico
            - **Amex México**: `1 : 1` → Iberia, BA, Flying Blue, Aeroméxico

            **2 Rutas de Vuelos Pagados (Pestaña 3)**
            - **`CDG ↔ MEX` en Aeroméxico (`AM`, SkyTeam)**:
              - AM Rewards (meta `10k` vuelo nacional) vs. Virgin Atlantic (`6k` Turista / `10k` W `CUN→LHR`)
            - **`MEX ↔ MAD` en Iberia (`IB`, Oneworld)**:
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
# Main Navigation Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    [
        "🗺️ 1. How It Works & Architectural Map" if not is_es else "🗺️ 1. Cómo Funciona y Mapa Arquitectónico",
        "💳 2. Mexican Cards → Europe (`Santander 1:1`, `BBVA`, `Amex`)" if not is_es else "💳 2. Tarjetas México → Europa (`Santander 1:1`, `BBVA`, `Amex`)",
        "🛫 3. Flight Crediting (`CDG↔MEX` on AM & `MEX↔MAD` on IB)" if not is_es else "🛫 3. Acreditación de Vuelos (`CDG↔MEX` en AM y `MEX↔MAD` en IB)",
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
        bbva_ib_row = next((p for p in pathways if p.bank_code == "BBVA_MX" and p.booking_program_code == "IB_PLUS"), None)
        if bbva_ib_row:
            bbva_scaled = int(round(bbva_ib_row.bank_points_required * (avios_money_pct / 100.0)))
            k3.metric(
                "Puntos BBVA → Iberia (2.6:1)" if not is_es else "Puntos BBVA → Iberia (2.6:1)",
                f"{bbva_scaled:,} Puntos BBVA",
                "vs. 120,000 BBVA on Aeroméxico" if cabin_pick == CabinClass.ECONOMY else "vs. 232,000 BBVA on Aeroméxico",
            )
        else:
            k3.metric("Taxes & TUA", f"${winner.taxes_and_yq_usd:.0f} USD", f"~${winner.taxes_and_yq_usd * MXN_PER_USD:,.0f} MXN")

        k4.metric(
            "Ticket Flexibility" if not is_es else "Flexibilidad del Boleto",
            "Flexible Avios Ticket" if not is_es else "Boleto Flexible Avios",
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
                        "Airline": p.operating_carrier_iata,
                        "Award Miles / Avios": f"{p.award_miles_required:,}",
                        "Ratio": f"{p.effective_transfer_ratio}:1",
                        "Bank Points Required": f"{p.bank_points_required:,} pts",
                        "Taxes & MEX TUA": f"${p.taxes_and_yq_usd:,.0f} USD (${p.taxes_and_yq_usd * MXN_PER_USD:,.0f} MXN)",
                        "Value / Pt": f"${val_mxn:.2f} MXN ({p.effective_cents_per_point:.2f}¢ USD)",
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
                        "Tasa": f"{p.effective_transfer_ratio}:1",
                        "Puntos Bancarios Req.": f"{p.bank_points_required:,} pts",
                        "Impuestos y TUA MEX": f"${p.taxes_and_yq_usd:,.0f} USD (${p.taxes_and_yq_usd * MXN_PER_USD:,.0f} MXN)",
                        "Valor / Pt": f"${val_mxn:.2f} MXN ({p.effective_cents_per_point:.2f}¢ USD)",
                        "Regla de Conversión y Flexibilidad": p.notes,
                    }
                )
        st.dataframe(rows, use_container_width=True, hide_index=True)

# ===========================================================================
# TAB 3: PAID FLIGHT CREDITING (DYNAMIC SKYTEAM vs ONEWORLD CLASS MENUS!)
# ===========================================================================
with tab3:
    st.subheader(
        "🛫 Paid Flight Crediting Simulator (`CDG ↔ MEX` on Aeroméxico & `MEX ↔ MAD` on Iberia)"
        if not is_es
        else "🛫 Simulador de Acreditación de Vuelos Pagados (`CDG ↔ MEX` en Aeroméxico y `MEX ↔ MAD` en Iberia)"
    )

    r1, r2, r3 = st.columns([1.3, 1.5, 0.9])
    with r1:
        itinerary_choice = st.selectbox(
            "1. Select Route & Operating Airline" if not is_es else "1. Selecciona Ruta y Aerolínea Operadora",
            options=[
                ("CDG", "MEX", "AM", "🇫🇷➡️🇲🇽 CDG ↔ MEX — Aeroméxico (SkyTeam)" if not is_es else "🇫🇷➡️🇲🇽 CDG ↔ MEX — Aeroméxico (SkyTeam)"),
                ("MEX", "MAD", "IB", "🇲🇽➡️🇪🇸 MEX ↔ MAD — Iberia (Oneworld)" if not is_es else "🇲🇽➡️🇪🇸 MEX ↔ MAD — Iberia (Oneworld)"),
            ],
            format_func=lambda x: x[3],
        )

    orig_c, dest_c, op_carrier, _ = itinerary_choice
    active_class_dict = SKYTEAM_AM_CLASSES if op_carrier == "AM" else ONEWORLD_IB_CLASSES
    lang_key = "es" if is_es else "en"

    with r2:
        b_class_choice = st.selectbox(
            (f"2. Select {('Aeroméxico (SkyTeam)' if op_carrier == 'AM' else 'Iberia (Oneworld)')} Fare Class" if not is_es else f"2. Selecciona Clase Tarifaria de {('Aeroméxico (SkyTeam)' if op_carrier == 'AM' else 'Iberia (Oneworld)')}"),
            options=list(active_class_dict.keys()),
            format_func=lambda c: active_class_dict[c][lang_key],
            key=f"fare_class_{op_carrier}",  # Separate widget key per carrier so SkyTeam and Oneworld menus never bleed into each other!
        )
    with r3:
        trip_type = st.radio(
            "3. Itinerary Type" if not is_es else "3. Tipo de Viaje",
            options=["ROUND_TRIP", "ONE_WAY"],
            format_func=lambda t: ("🔄 Round-Trip" if not is_es else "🔄 Redondo") if t == "ROUND_TRIP" else ("➡️ One-Way" if not is_es else "➡️ Sencillo"),
            horizontal=True,
        )

    is_rt = trip_type == "ROUND_TRIP"
    default_leg_price = (450.0 if op_carrier == "AM" else 325.0) if b_class_choice in ("V", "K", "Y") else 1400.0

    sp1, sp2 = st.columns([1.1, 1.9])
    with sp1:
        seg_all_in_usd = st.slider(
            ("4. All-In Ticket Price per One-Way Leg (USD)" if not is_es else "4. Precio Total con Impuestos por Tramo Sencillo (USD)"),
            min_value=200.0,
            max_value=4000.0,
            value=float(default_leg_price),
            step=25.0,
            key=f"price_slider_{op_carrier}",
        )

    ap_orig = CLEAN_AIRPORTS[orig_c]
    ap_dest = CLEAN_AIRPORTS[dest_c]
    elig_leg1, tax_leg1, tax_lbl1 = _calculate_segment_spend_and_tax(ap_orig, float(seg_all_in_usd), is_es=is_es)
    elig_leg2, tax_leg2, tax_lbl2 = _calculate_segment_spend_and_tax(ap_dest, float(seg_all_in_usd), is_es=is_es)

    with sp2:
        if is_rt:
            st.markdown(
                f"""
                <div style="background:#F8FAFC;border:1px solid #CBD5E1;border-left:4px solid #0284C7;border-radius:8px;padding:10px 14px;font-size:13.5px;color:#0F172A;">
                  <b>🧾 {"Per-Origin Departure Tax Breakdown" if not is_es else "Desglose de Impuestos por Aeropuerto de Salida"} (<code>{orig_c} ↔ {dest_c}</code>):</b><br/>
                  • <b>Leg 1 (<code>{orig_c} → {dest_c}</code>):</b> -{tax_lbl1} → <b>${elig_leg1:,.2f} USD</b> {"eligible Base + YQ" if not is_es else "Base + YQ elegible"}<br/>
                  • <b>Leg 2 (<code>{dest_c} → {orig_c}</code>):</b> -{tax_lbl2} → <b>${elig_leg2:,.2f} USD</b> {"eligible Base + YQ" if not is_es else "Base + YQ elegible"}
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div style="background:#F8FAFC;border:1px solid #CBD5E1;border-left:4px solid #0284C7;border-radius:8px;padding:12px 14px;font-size:13.5px;color:#0F172A;">
                  <b>🧾 {"Departure Tax Breakdown" if not is_es else "Desglose de Impuesto de Salida"} (<code>{orig_c} → {dest_c}</code>):</b><br/>
                  • -{tax_lbl1} → <b>${elig_leg1:,.2f} USD</b> {"eligible Base + YQ" if not is_es else "Base + YQ elegible"}
                </div>
                """,
                unsafe_allow_html=True,
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

    sim_rows = _run_paid_flight_simulation(built_segments, is_es=is_es)
    sample_row = sim_rows[0]

    # 4 Clean Metric Cards (Compact text so values never truncate with '...')
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric(
        "Total Great Circle Distance" if not is_es else "Distancia Total Gran Círculo",
        f"{one_way_mi * mult_legs:,.0f} mi",
        f"{one_way_km * mult_legs:,.0f} km ({mult_legs} {'tramos' if is_es and is_rt else ('tramo' if is_es else ('legs' if is_rt else 'leg'))})",
    )
    m_col2.metric(
        "Eligible Spend (Base + YQ)" if not is_es else "Gasto Elegible (Base + YQ)",
        f"${sample_row['eligible_spend_usd']:,.2f} USD",
        f"-${sample_row['gov_taxes_usd']:,.2f} USD taxes stripped" if not is_es else f"-${sample_row['gov_taxes_usd']:,.2f} USD impuestos desc.",
    )
    m_col3.metric(
        f"EU261 Leg 1 ({orig_c}→{dest_c})",
        (f"€{eu_out['compensation_eur']} Protected" if not is_es else f"€{eu_out['compensation_eur']} Protegido") if eu_out["is_eligible"] else ("€0 Not Covered" if not is_es else "€0 No Cubierto"),
        ("Departs EU Airport" if ap_orig.is_eu_eea_ch else f"EU Carrier ({op_carrier}) into EU"),
    )
    if is_rt and eu_ret:
        m_col4.metric(
            f"EU261 Leg 2 ({dest_c}→{orig_c})",
            (f"€{eu_ret['compensation_eur']} Protected" if not is_es else f"€{eu_ret['compensation_eur']} Protegido") if eu_ret["is_eligible"] else ("€0 Not Covered" if not is_es else "€0 No Cubierto"),
            ("Departs EU Airport" if ap_dest.is_eu_eea_ch else f"Non-EU Origin & Carrier ({op_carrier})" if not is_es else f"Origen y Aerolínea No-UE ({op_carrier})"),
        )
    else:
        m_col4.metric(
            "Alliance" if not is_es else "Alianza",
            str(sample_row["alliance"]),
            str(sample_row["status_tier_name"]),
        )

    # -----------------------------------------------------------------------
    # Clean Side-by-Side Visual Verdict Cards (Own Metal vs. Smart Partner)
    # -----------------------------------------------------------------------
    metal_row = next((r for r in sim_rows if r["is_own_metal"]), None)
    dist_partner_rows = [r for r in sim_rows if not r["is_own_metal"] and r["is_distance_based"]]
    partner_row = dist_partner_rows[0] if dist_partner_rows else next((r for r in sim_rows if not r["is_own_metal"]), None)

    if metal_row and partner_row:
        card_left, card_right = st.columns(2)
        with card_left:
            m_bg = "#FEF2F2" if not metal_row["unlocked_ok"] else "#F0FDF4"
            m_border = "#EF4444" if not metal_row["unlocked_ok"] else "#22C55E"
            m_title_color = "#991B1B" if not metal_row["unlocked_ok"] else "#166534"
            st.markdown(
                f"""
                <div style="background:{m_bg};border:1px solid {m_border};border-left:6px solid {m_border};border-radius:10px;padding:16px 18px;margin:8px 0;">
                  <div style="font-size:12px;font-weight:700;text-transform:uppercase;color:{m_title_color};letter-spacing:0.5px;">
                    🏠 {"Crediting to Operating Airline (Own Metal Default)" if not is_es else "Acreditar a la Propia Aerolínea (Opción por Defecto)"}
                  </div>
                  <div style="font-size:19px;font-weight:800;color:#0F172A;margin-top:4px;">
                    {metal_row['program_name']} <span style="font-size:13px;font-weight:500;color:#475569;">({metal_row['basis_label']})</span>
                  </div>
                  <div style="font-size:24px;font-weight:800;color:{m_title_color};margin:8px 0;">
                    {metal_row['total_miles']:,} {metal_row['currency_name']}
                  </div>
                  <div style="font-size:13.5px;color:#1E293B;margin-bottom:6px;">
                    <b>{"Status Progress" if not is_es else "Progreso de Estatus"}:</b> {metal_row['progress_pct']}% → <code>{metal_row['status_tier_name']}</code>
                  </div>
                  <div style="font-size:13.5px;font-weight:600;color:{m_title_color};">
                    {metal_row['detail_text']}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with card_right:
            p_bg = "#ECFDF5" if partner_row["unlocked_ok"] else "#FFFBEB"
            p_border = "#10B981" if partner_row["unlocked_ok"] else "#F59E0B"
            p_title_color = "#065F46" if partner_row["unlocked_ok"] else "#92400E"
            st.markdown(
                f"""
                <div style="background:{p_bg};border:1px solid {p_border};border-left:6px solid {p_border};border-radius:10px;padding:16px 18px;margin:8px 0;">
                  <div style="font-size:12px;font-weight:700;text-transform:uppercase;color:{p_title_color};letter-spacing:0.5px;">
                    🚀 {"Smart Alliance Partner Switch (Distance-Based)" if not is_es else "Cambio Inteligente a Socio de Alianza (Por Distancia)"}
                  </div>
                  <div style="font-size:19px;font-weight:800;color:#0F172A;margin-top:4px;">
                    {partner_row['program_name']} <span style="font-size:13px;font-weight:500;color:#475569;">({partner_row['basis_label']})</span>
                  </div>
                  <div style="font-size:24px;font-weight:800;color:{p_title_color};margin:8px 0;">
                    {partner_row['total_miles']:,} {partner_row['currency_name']}
                  </div>
                  <div style="font-size:13.5px;color:#1E293B;margin-bottom:6px;">
                    <b>{"Status Progress" if not is_es else "Progreso de Estatus"}:</b> {partner_row['progress_pct']}% → <code>{partner_row['status_tier_name']}</code>
                  </div>
                  <div style="font-size:13.5px;font-weight:600;color:{p_title_color};">
                    {partner_row['detail_text']}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Clean, Scannable Comparison Table
    table_cred = []
    for r in sim_rows:
        if not is_es:
            table_cred.append(
                {
                    "Loyalty Program": f"{r['program_name']} ({r['program_code']})",
                    "Alliance": r["alliance"],
                    "Strategy Role": "🏠 Own Metal" if r["is_own_metal"] else "🤝 Alliance Partner",
                    "Calculation Rule": r["basis_label"],
                    "Points / Miles Earned": f"{r['total_miles']:,}",
                    "Alliance Status Progress": f"{r['progress_pct']}% ({r['status_pts']:,.0f} / {r['status_threshold']:,.0f} → {r['status_tier_name']})",
                    "Reward Flight Verdict": r["short_cell"],
                }
            )
        else:
            table_cred.append(
                {
                    "Programa de Lealtad": f"{r['program_name']} ({r['program_code']})",
                    "Alianza": r["alliance"],
                    "Rol": "🏠 Propia Aerolínea" if r["is_own_metal"] else "🤝 Socio de Alianza",
                    "Regla de Cálculo": r["basis_label"],
                    "Puntos / Millas Ganados": f"{r['total_miles']:,}",
                    "Progreso de Estatus": f"{r['progress_pct']}% ({r['status_pts']:,.0f} / {r['status_threshold']:,.0f} → {r['status_tier_name']})",
                    "Veredicto de Vuelos Premio": r["short_cell"],
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