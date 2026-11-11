"""
Cross-Alliance Loyalty Arbitrage & Frequent Flyer ROI Engine — Interactive Demo (`streamlit_app.py`).

Author:
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
from src.core.seed_data import (
    AIRPORTS,
    AWARD_SWEET_SPOTS,
    BANK_CURRENCIES,
    LOYALTY_PROGRAMS,
    PARTNER_EARNING_RULES,
    TRANSFER_PARTNER_RULES,
)
from src.api import routes as api_routes
from src.db.repository import LoyaltyRepository
from src.db.session import DatabaseSessionManager
from src.serverless import lambda_handler

# ---------------------------------------------------------------------------
# Self-Contained Seed Data Synchronization (Guarantees 100% Working Combinations)
# ---------------------------------------------------------------------------
MXN_PER_USD = 20.0
MEXICAN_BANK_CODES = {"BBVA_MX", "SANTANDER_MX", "AMEX_MX"}
US_BANK_CODES = {"CHASE_UR", "AMEX_MR", "CITI_TYP", "CAP_ONE"}

AIRPORTS.update({
    "MEX": AirportProfile("MEX", "Benito Juárez International (AICM)", "Mexico City", "MX", 19.4363, -99.0721, "NORTH_AMERICA", False, 65.0),
    "CUN": AirportProfile("CUN", "Cancún International", "Cancún", "MX", 21.0365, -86.8771, "NORTH_AMERICA", False, 58.0),
    "VIE": AirportProfile("VIE", "Vienna International Airport", "Vienna", "AT", 48.1103, 16.5697, "EUROPE", True, 54.0),
    "LHR": AirportProfile("LHR", "Heathrow Airport", "London", "GB", 51.4700, -0.4543, "EUROPE", False, 115.0),
})

BANK_CURRENCIES.update({
    "BBVA_MX": BankCurrency("BBVA_MX", "BBVA México", "Puntos BBVA", 0.55),
    "SANTANDER_MX": BankCurrency("SANTANDER_MX", "Santander México", "Unique Rewards", 0.50),
    "AMEX_MX": BankCurrency("AMEX_MX", "American Express México", "Membership Rewards MX", 0.75),
})

LOYALTY_PROGRAMS.update({
    "IB_PLUS": LoyaltyProgram("IB_PLUS", "Iberia Club (Avios)", "IB", Alliance.ONEWORLD, "Avios", 5.0, True, "Iberia Oro (Oneworld Sapphire)", 2250.0),
    "BA_EC": LoyaltyProgram("BA_EC", "The British Airways Club (Avios)", "BA", Alliance.ONEWORLD, "Avios", 6.4815, True, "Silver (Oneworld Sapphire)", 7500.0),
    "AS_ATMOS": LoyaltyProgram("AS_ATMOS", "Alaska Airlines Atmos Rewards", "AS", Alliance.ONEWORLD, "Atmos Points", None, True, "Atmos Gold (Oneworld Sapphire)", 40000.0),
    "AA_ADV": LoyaltyProgram("AA_ADV", "American Airlines AAdvantage", "AA", Alliance.ONEWORLD, "AAdvantage Miles", 5.0, True, "Platinum (Oneworld Sapphire)", 75000.0),
    "AM_RW": LoyaltyProgram("AM_RW", "Aeroméxico Rewards (Club Premier)", "AM", Alliance.SKYTEAM, "Puntos Aeroméxico Rewards", 8.0, True, "Gold (SkyTeam Elite Plus)", 80000.0),
    "VS_FC": LoyaltyProgram("VS_FC", "Virgin Atlantic Flying Club", "VS", Alliance.SKYTEAM, "Virgin Points", None, True, "Flying Club Gold (SkyTeam Elite Plus)", 1000.0),
    "AF_FB": LoyaltyProgram("AF_FB", "Air France / KLM Flying Blue", "AF", Alliance.SKYTEAM, "Flying Blue Miles", 4.0, True, "Gold (SkyTeam Elite Plus)", 180.0),
})

_EXTRA_TRANSFER_RULES = [
    TransferPartnerRule("BBVA_MX", "IB_PLUS", base_ratio=0.3846, active_bonus_pct=20.0, min_transfer_increment=130),
    TransferPartnerRule("BBVA_MX", "BA_EC",   base_ratio=0.3846, active_bonus_pct=20.0, min_transfer_increment=130),
    TransferPartnerRule("BBVA_MX", "AM_RW",   base_ratio=0.6250, active_bonus_pct=25.0, min_transfer_increment=1000),
    TransferPartnerRule("BBVA_MX", "VS_FC",   base_ratio=0.3846, active_bonus_pct=0.0,  min_transfer_increment=130),
    TransferPartnerRule("BBVA_MX", "AF_FB",   base_ratio=0.3846, active_bonus_pct=0.0,  min_transfer_increment=130),
    TransferPartnerRule("BBVA_MX", "AC_AP",   base_ratio=0.3846, active_bonus_pct=0.0,  min_transfer_increment=130),
    TransferPartnerRule("BBVA_MX", "TK_MS",   base_ratio=0.3846, active_bonus_pct=0.0,  min_transfer_increment=130),
    TransferPartnerRule("SANTANDER_MX", "IB_PLUS", base_ratio=0.50, active_bonus_pct=25.0, min_transfer_increment=1000),
    TransferPartnerRule("SANTANDER_MX", "BA_EC",   base_ratio=0.50, active_bonus_pct=25.0, min_transfer_increment=1000),
    TransferPartnerRule("SANTANDER_MX", "AM_RW",   base_ratio=1.00, active_bonus_pct=15.0, min_transfer_increment=1000),
    TransferPartnerRule("SANTANDER_MX", "VS_FC",   base_ratio=0.50, active_bonus_pct=0.0,  min_transfer_increment=1000),
    TransferPartnerRule("SANTANDER_MX", "AC_AP",   base_ratio=0.50, active_bonus_pct=0.0,  min_transfer_increment=1000),
    TransferPartnerRule("SANTANDER_MX", "AF_FB",   base_ratio=0.50, active_bonus_pct=0.0,  min_transfer_increment=1000),
    TransferPartnerRule("SANTANDER_MX", "TK_MS",   base_ratio=0.50, active_bonus_pct=0.0,  min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MX", "IB_PLUS", base_ratio=1.0, active_bonus_pct=20.0, min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MX", "BA_EC",   base_ratio=1.0, active_bonus_pct=20.0, min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MX", "VS_FC",   base_ratio=1.0, active_bonus_pct=30.0, min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MX", "AC_AP",   base_ratio=1.0, active_bonus_pct=15.0, min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MX", "AF_FB",   base_ratio=1.0, active_bonus_pct=25.0, min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MX", "AM_RW",   base_ratio=1.6, active_bonus_pct=20.0, min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MX", "TK_MS",   base_ratio=1.0, active_bonus_pct=0.0,  min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MX", "UA_MP",   base_ratio=1.0, active_bonus_pct=0.0,  min_transfer_increment=1000),
]
_existing_tr = {(r.bank_code, r.program_code) for r in TRANSFER_PARTNER_RULES}
for _r in _EXTRA_TRANSFER_RULES:
    if (_r.bank_code, _r.program_code) not in _existing_tr:
        TRANSFER_PARTNER_RULES.append(_r)

# Update IB_MEX_MAD_ECON to 21,000 Avios and add Virgin Atlantic 6,000-pt CUN-LHR Economy sweet spot
for _idx, _spot in enumerate(AWARD_SWEET_SPOTS):
    if _spot.benchmark_code == "IB_MEX_MAD_ECON":
        AWARD_SWEET_SPOTS[_idx] = AwardSweetSpot(
            benchmark_code="IB_MEX_MAD_ECON",
            booking_program_code="IB_PLUS",
            operating_carrier_iata="IB",
            alliance=Alliance.ONEWORLD,
            origin_iata="MEX",
            destination_iata="MAD",
            cabin=CabinClass.ECONOMY,
            miles_required_one_way=21000,
            taxes_and_yq_usd=115.0,
            typical_cash_fare_one_way_usd=680.0,
            category="LONG_HAUL_SWEET_SPOT",
            description="MEX-MAD Economy to Europe on Iberia (21,000 Avios full, or even less with Avios & Money; flexible changes/refunds vs 75,000 AM points)",
        )

_EXTRA_SWEET_SPOTS = [
    AwardSweetSpot(
        benchmark_code="AS_SHORT_HAUL_US_ECON",
        booking_program_code="AS_ATMOS",
        operating_carrier_iata="AA",
        alliance=Alliance.ONEWORLD,
        origin_iata="MEX",
        destination_iata="IAH",
        cabin=CabinClass.ECONOMY,
        miles_required_one_way=4500,
        taxes_and_yq_usd=65.0,
        typical_cash_fare_one_way_usd=190.0,
        category="SHORT_HAUL_UNLOCK",
        description="Oneworld Short-Haul (<700 mi) Economy via Alaska Atmos Rewards (4,500 pts)",
    ),
    AwardSweetSpot(
        benchmark_code="VS_CUN_LHR_ECON",
        booking_program_code="VS_FC",
        operating_carrier_iata="VS",
        alliance=Alliance.SKYTEAM,
        origin_iata="CUN",
        destination_iata="LHR",
        cabin=CabinClass.ECONOMY,
        miles_required_one_way=6000,
        taxes_and_yq_usd=145.0,
        typical_cash_fare_one_way_usd=620.0,
        category="SHORT_HAUL_UNLOCK",
        description="[Chart 1: VS Own-Metal Saver] CUN-LHR Economy for 6,000 VS Points (or 10,500 pts in Premium W!)",
    ),
    AwardSweetSpot(
        benchmark_code="VS_MEX_CDG_AF_KL_BIZ",
        booking_program_code="VS_FC",
        operating_carrier_iata="AF",
        alliance=Alliance.SKYTEAM,
        origin_iata="MEX",
        destination_iata="CDG",
        cabin=CabinClass.BUSINESS,
        miles_required_one_way=48500,
        taxes_and_yq_usd=265.0,
        typical_cash_fare_one_way_usd=2450.0,
        category="LONG_HAUL_SWEET_SPOT",
        description="[Chart 2: AF/KL JV Zone Chart] MEX-CDG/AMS Business Class on Air France/KLM (48,500 VS Points)",
    ),
    AwardSweetSpot(
        benchmark_code="VS_MEX_CDG_AF_KL_ECON",
        booking_program_code="VS_FC",
        operating_carrier_iata="AF",
        alliance=Alliance.SKYTEAM,
        origin_iata="MEX",
        destination_iata="CDG",
        cabin=CabinClass.ECONOMY,
        miles_required_one_way=15000,
        taxes_and_yq_usd=155.0,
        typical_cash_fare_one_way_usd=720.0,
        category="SHORT_HAUL_UNLOCK",
        description="[Chart 2: AF/KL JV Zone Chart] MEX-CDG/AMS Economy on Air France or KLM metal for 15,000 VS Points!",
    ),
    AwardSweetSpot(
        benchmark_code="VS_CUN_LHR_BIZ",
        booking_program_code="VS_FC",
        operating_carrier_iata="VS",
        alliance=Alliance.SKYTEAM,
        origin_iata="CUN",
        destination_iata="LHR",
        cabin=CabinClass.BUSINESS,
        miles_required_one_way=29000,
        taxes_and_yq_usd=290.0,
        typical_cash_fare_one_way_usd=2100.0,
        category="LONG_HAUL_SWEET_SPOT",
        description="Cancún to Europe (CUN-LHR) Upper Class (Business) on Virgin Atlantic (29,000 Virgin Points)",
    ),
    AwardSweetSpot(
        benchmark_code="VS_MEX_MAD_PARTNER_ECON",
        booking_program_code="VS_FC",
        operating_carrier_iata="AM",
        alliance=Alliance.SKYTEAM,
        origin_iata="MEX",
        destination_iata="MAD",
        cabin=CabinClass.ECONOMY,
        miles_required_one_way=25000,
        taxes_and_yq_usd=155.0,
        typical_cash_fare_one_way_usd=680.0,
        category="LONG_HAUL_SWEET_SPOT",
        description="[Chart 3: SkyTeam Distance Chart] MEX-MAD Economy on AM/UX metal (25,000 VS Points)",
    ),
]
_existing_bm = {b.benchmark_code for b in AWARD_SWEET_SPOTS}
for _b in _EXTRA_SWEET_SPOTS:
    if _b.benchmark_code not in _existing_bm:
        AWARD_SWEET_SPOTS.append(_b)

_EXTRA_EARNING_RULES = [
    PartnerEarningRule("AS_ATMOS", "IB", "K", CabinClass.ECONOMY,   50.0, 250, "DISTANCE_PCT",  50.0),
    PartnerEarningRule("AS_ATMOS", "IB", "Y", CabinClass.ECONOMY,  100.0, 500, "DISTANCE_PCT", 100.0),
    PartnerEarningRule("AS_ATMOS", "IB", "P", CabinClass.BUSINESS, 125.0, 500, "DISTANCE_PCT", 125.0),
    PartnerEarningRule("AS_ATMOS", "IB", "I", CabinClass.BUSINESS, 125.0, 500, "DISTANCE_PCT", 125.0),
    PartnerEarningRule("AS_ATMOS", "IB", "J", CabinClass.BUSINESS, 250.0, 1000, "DISTANCE_PCT", 250.0),
    PartnerEarningRule("VS_FC", "AM", "K", CabinClass.ECONOMY,   55.0, 250, "IB_ZONE_FIXED",  55.0, 10.0,  25.0),
    PartnerEarningRule("VS_FC", "AM", "Y", CabinClass.ECONOMY,  100.0, 500, "IB_ZONE_FIXED", 100.0, 20.0,  50.0),
    PartnerEarningRule("VS_FC", "AM", "P", CabinClass.BUSINESS, 125.0, 500, "IB_ZONE_FIXED", 125.0, 40.0, 100.0),
    PartnerEarningRule("VS_FC", "AM", "I", CabinClass.BUSINESS, 150.0, 500, "IB_ZONE_FIXED", 150.0, 40.0, 100.0),
    PartnerEarningRule("VS_FC", "AM", "J", CabinClass.BUSINESS, 200.0, 1000, "IB_ZONE_FIXED", 200.0, 40.0, 200.0),
]
_existing_er = {(e.program_code, e.operating_carrier, e.booking_class) for e in PARTNER_EARNING_RULES}
for _e in _EXTRA_EARNING_RULES:
    if (_e.program_code, _e.operating_carrier, _e.booking_class) not in _existing_er:
        PARTNER_EARNING_RULES.append(_e)


def _run_transfer_pathways(
    origin_iata: str,
    destination_iata: str,
    cabin: CabinClass,
    bank_selector: str = "ALL_MX",
    override_bonus_pct: float | None = None,
    override_cash_fare_usd: float | None = None,
    is_es: bool = False,
) -> list[TransferOptionResult]:
    """Evaluates transfer pathways filtered by Mexican bank ecosystem, single bank, or US comparison."""
    orig = origin_iata.upper()
    dest = destination_iata.upper()
    matching = [s for s in AWARD_SWEET_SPOTS if s.origin_iata == orig and s.destination_iata == dest and s.cabin == cabin]
    results: list[TransferOptionResult] = []
    for spot in matching:
        program = LOYALTY_PROGRAMS[spot.booking_program_code]
        cash_bm = float(override_cash_fare_usd) if (override_cash_fare_usd is not None and override_cash_fare_usd > 0) else spot.typical_cash_fare_one_way_usd
        for rule in TRANSFER_PARTNER_RULES:
            if rule.program_code != spot.booking_program_code:
                continue
            if bank_selector == "ALL_MX" and rule.bank_code not in MEXICAN_BANK_CODES:
                continue
            elif bank_selector == "ALL_US" and rule.bank_code not in US_BANK_CODES:
                continue
            elif bank_selector not in ("ALL_MX", "ALL_US", "ALL_GLOBAL") and rule.bank_code != bank_selector:
                continue

            bank = BANK_CURRENCIES[rule.bank_code]
            eff_bonus = float(override_bonus_pct) if override_bonus_pct is not None else rule.active_bonus_pct
            eff_ratio = apply_transfer_bonus(rule.base_ratio, eff_bonus)
            bank_pts = calculate_required_bank_points(spot.miles_required_one_way, rule.base_ratio, eff_bonus, rule.min_transfer_increment)
            cpp = calculate_effective_cpm(cash_bm, spot.taxes_and_yq_usd, bank_pts)
            net_saved = round(max(0.0, cash_bm - spot.taxes_and_yq_usd), 2)

            if rule.base_ratio < 0.45:
                ratio_str = f"2.6:1 base (min {rule.min_transfer_increment} pts)"
            elif rule.base_ratio == 0.50:
                ratio_str = "2:1 base (2 Unique Pts = 1 Avios)"
            elif rule.base_ratio == 0.625:
                ratio_str = "1.6:1 base (1.6 Puntos BBVA = 1 Pt AM)"
            elif rule.base_ratio > 1.0:
                ratio_str = f"1:{rule.base_ratio} base"
            else:
                ratio_str = "1:1 base"

            if is_es:
                bonus_label = f"{ratio_str} + {eff_bonus:.0f}% bono ({eff_ratio}:1 ef.)." if eff_bonus > 0 else f"{ratio_str} ({eff_ratio}:1 ef.)."
            else:
                bonus_label = f"{ratio_str} + {eff_bonus:.0f}% promo ({eff_ratio}:1 eff)." if eff_bonus > 0 else f"{ratio_str} ({eff_ratio}:1 eff)."

            results.append(
                TransferOptionResult(
                    bank_code=bank.bank_code,
                    bank_currency_name=f"{bank.bank_name} ({bank.currency_name})",
                    booking_program_code=program.program_code,
                    booking_program_name=program.program_name,
                    operating_carrier_iata=spot.operating_carrier_iata,
                    route=f"{orig}-{dest}",
                    cabin=cabin,
                    award_miles_required=spot.miles_required_one_way,
                    effective_transfer_ratio=eff_ratio,
                    bank_points_required=bank_pts,
                    taxes_and_yq_usd=spot.taxes_and_yq_usd,
                    cash_fare_benchmark_usd=cash_bm,
                    net_cash_saved_usd=net_saved,
                    effective_cents_per_point=cpp,
                    beats_cashout_baseline=(cpp > bank.baseline_cashout_cents_per_point),
                    notes=f"{spot.description} | {bonus_label}",
                )
            )
    results.sort(key=lambda r: (r.bank_points_required, r.taxes_and_yq_usd))
    return results


def _run_flight_crediting(segments: list[FlightSegment], is_es: bool = False) -> list[CreditingSimulationResult]:
    """Simulates flight crediting across alliance partners while preserving 0%-earning fare-class traps."""
    primary_carrier = segments[0].operating_carrier.upper()
    results: list[CreditingSimulationResult] = []
    for prog_code, program in LOYALTY_PROGRAMS.items():
        total_miles = 0
        total_status_pts = 0.0
        own_metal_status_pts = 0.0
        own_metal_segs = 0
        total_eligible_spend = 0.0
        total_gov_taxes = 0.0
        used_rev = False
        used_dist = False
        matched_any_rule = False
        zero_trap_classes: list[str] = []

        for seg in segments:
            orig = AIRPORTS[seg.origin_iata.upper()]
            dest = AIRPORTS[seg.destination_iata.upper()]
            dist_mi, _ = haversine_distance(orig.latitude, orig.longitude, dest.latitude, dest.longitude)
            is_intercontinental = orig.region_zone != dest.region_zone
            rule = next(
                (r for r in PARTNER_EARNING_RULES if r.program_code == prog_code and r.operating_carrier == seg.operating_carrier.upper() and r.booking_class == seg.booking_class.upper()),
                None,
            )
            if rule is None:
                continue
            matched_any_rule = True
            if rule.award_miles_pct == 0.0 and rule.status_miles_pct == 0.0:
                zero_trap_classes.append(f"{seg.operating_carrier.upper()} '{seg.booking_class.upper()}'")

            eligible_spend, gov_tax = estimate_eligible_spend(
                orig, dest, seg.base_fare_usd, seg.yq_surcharge_usd, seg.total_ticket_price_usd, program.counts_yq_surcharge
            )
            if seg.base_fare_usd is not None and seg.total_ticket_price_usd is None:
                gov_tax = round(orig.estimated_gov_departure_tax_usd + (dest.estimated_gov_departure_tax_usd * 0.35), 2)
            total_eligible_spend += eligible_spend
            total_gov_taxes += gov_tax

            ticketing_carrier = (seg.ticketing_carrier or seg.operating_carrier).upper()
            oneworld_jv_revenue_group = {"IB", "BA", "AA"}
            is_revenue_eligible_ticket = (
                ticketing_carrier == program.home_carrier_iata
                or (prog_code in {"IB_PLUS", "BA_EC", "AA_ADV"} and ticketing_carrier in oneworld_jv_revenue_group)
            )

            if is_revenue_eligible_ticket and eligible_spend > 0 and program.own_ticket_revenue_multiplier is not None:
                if prog_code in {"IB_PLUS", "BA_EC"} and seg.operating_carrier.upper() == "IB":
                    # Official Iberia & British Airways Club rule on IB-marketed & operated flights:
                    # 5 base Avios/€ + 2 bonus Avios/€ between Spain and Mexico/LatAm (= 7 Avios/€)
                    # or +1 bonus Avios/€ on MAD-BCN Air Shuttle (= 6 Avios/€)
                    eur_spend = eligible_spend / 1.08
                    pair_set = {orig.iata_code, dest.iata_code}
                    if "MAD" in pair_set and ("MEX" in pair_set or "CUN" in pair_set):
                        avios_per_eur = 7.0
                    elif pair_set == {"MAD", "BCN"}:
                        avios_per_eur = 6.0
                    else:
                        avios_per_eur = 5.0
                    seg_miles = int(round(eur_spend * avios_per_eur))
                else:
                    seg_miles = int(round(eligible_spend * program.own_ticket_revenue_multiplier))
                used_rev = True
            else:
                raw_miles = dist_mi * (rule.award_miles_pct / 100.0)
                seg_miles = int(round(max(raw_miles, float(rule.min_award_miles)) if rule.award_miles_pct > 0 else 0.0))
                used_dist = True
            total_miles += seg_miles

            if prog_code == "BA_EC" and is_revenue_eligible_ticket and eligible_spend > 0:
                gbp_spend = eligible_spend / 1.27
                cabin_sector_bonus = 400.0 if rule.cabin == CabinClass.BUSINESS else 175.0
                seg_status = round(gbp_spend + (cabin_sector_bonus if is_intercontinental else 75.0), 1)
            elif prog_code == "AA_ADV" and is_revenue_eligible_ticket and eligible_spend > 0:
                seg_status = round(eligible_spend * 5.0, 1)
            elif rule.status_calc_method in ("MM_ZONE_FIXED", "IB_ZONE_FIXED"):
                seg_status = rule.intercontinental_status_points if is_intercontinental else rule.continental_status_points
            elif rule.status_calc_method == "UA_PQP_PARTNER":
                if is_revenue_eligible_ticket and eligible_spend > 0:
                    seg_status = eligible_spend
                else:
                    divisor = 5.0 if seg.operating_carrier.upper() in {"LH", "LX", "OS", "SN", "AC", "NH"} else 6.0
                    seg_status = round(min(seg_miles / divisor, 1500.0), 1)
            else:
                seg_status = round(dist_mi * (rule.status_miles_pct / 100.0), 1)

            total_status_pts += seg_status
            if seg.operating_carrier.upper() == program.home_carrier_iata:
                own_metal_status_pts += seg_status
                own_metal_segs += 1

        if not matched_any_rule:
            continue

        progress_pct = round(min(100.0, (total_status_pts / program.gold_status_threshold) * 100.0), 1)
        warning: str | None = None
        if zero_trap_classes:
            trap_str = ", ".join(sorted(set(zero_trap_classes)))
            warning = (
                f"⚠️ Trampa de 0%: ¡{trap_str} acumula 0 millas y 0 puntos de estatus en {program.program_name}!"
                if is_es
                else f"⚠️ 0% Earning Trap: {trap_str} earns 0 miles and 0 status points in {program.program_name}!"
            )
        elif program.own_metal_min_share_pct > 0 and total_status_pts > 0:
            share = (own_metal_status_pts / total_status_pts) * 100.0
            if share < program.own_metal_min_share_pct:
                warning = (
                    f"Requiere {program.own_metal_min_share_pct:.0f}% de puntos en aerolíneas del grupo {program.home_carrier_iata} (actual: {share:.1f}%)."
                    if is_es
                    else f"Requires {program.own_metal_min_share_pct:.0f}% status points on {program.home_carrier_iata} Group metal (currently {share:.1f}%)."
                )
        elif program.own_metal_min_segments > 0 and own_metal_segs < program.own_metal_min_segments:
            warning = (
                f"Requiere {program.own_metal_min_segments} segmentos anuales operados por {program.home_carrier_iata} (este itinerario tiene {own_metal_segs})."
                if is_es
                else f"Requires {program.own_metal_min_segments} annual segments on {program.home_carrier_iata} metal (this itinerary has {own_metal_segs})."
            )

        short_unlocks: list[str] = []
        long_progress: list[str] = []
        for bm in AWARD_SWEET_SPOTS:
            if bm.booking_program_code != prog_code:
                continue
            if bm.category == "SHORT_HAUL_UNLOCK" and total_miles >= bm.miles_required_one_way:
                count = total_miles // bm.miles_required_one_way
                rem = total_miles % bm.miles_required_one_way
                if is_es:
                    short_unlocks.append(f"¡Desbloquea {count}x {bm.description} ({bm.miles_required_one_way:,} req. + {rem:,} sobrantes)!")
                else:
                    short_unlocks.append(f"Unlocks {count}x {bm.description} ({bm.miles_required_one_way:,} req. + {rem:,} left)!")
            elif bm.category == "LONG_HAUL_SWEET_SPOT":
                pct = round(min(100.0, (total_miles / bm.miles_required_one_way) * 100.0), 1)
                if is_es:
                    long_progress.append(f"{pct}% hacia {bm.description} ({bm.miles_required_one_way:,} req.)")
                else:
                    long_progress.append(f"{pct}% toward {bm.description} ({bm.miles_required_one_way:,} req.)")

        basis = "HYBRID" if (used_rev and used_dist) else ("REVENUE_BASED" if used_rev else "DISTANCE_AND_ZONE_BASED")
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
                own_metal_warning=warning,
                unlocked_short_haul_awards=short_unlocks,
                flagship_sweet_spot_progress=long_progress,
            )
        )
    # Sort primarily by whether a tangible flight is immediately unlocked, then by redeemable miles and status progress
    results.sort(
        key=lambda r: (len(r.unlocked_short_haul_awards) > 0, r.progress_to_gold_pct, r.redeemable_miles_earned),
        reverse=True,
    )
    return results


st.set_page_config(
    page_title="Loyalty Arbitrage & Frequent Flyer ROI Engine — Erik Šauša, Dipl.-Ing.",
    page_icon="✈️",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Top Header & Language Toggle
# ---------------------------------------------------------------------------
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
# The Two Core Motivations Banner (Why This Engine Exists)
# ---------------------------------------------------------------------------
col_m1, col_m2 = st.columns(2)
with col_m1:
    if not is_es:
        st.info(
            "**1️⃣ Why Built — Crediting to 'Own Metal' Is Often Not Optimal (Aeroméxico vs. Virgin Atlantic):**  \n"
            "Most travelers automatically credit a paid flight to the airline they are flying on. That is frequently a costly mistake.  \n"
            "• **Real-World Example:** If you fly **Aeroméxico (`AM`) round-trip to Europe (`MEX–MAD–MEX`)** and credit to **Aeroméxico Rewards**, "
            "you earn nowhere near the **75,000 points** required for an Economy award to Europe.  \n"
            "• **The Partner Arbitrage:** If you instead credit that exact same Aeroméxico flight to SkyTeam partner **Virgin Atlantic Flying Club (`VS_FC`)**, "
            "a single round-trip to Europe earns **5,630 to 16,800+ Virgin Points**—and Virgin Atlantic prices **Cancún to Europe (`CUN–LHR` London) Economy at just 6,000 Virgin Points**! "
            "One round-trip on Aeroméxico credited to Virgin Atlantic unlocks a **6,000-pt Economy** or **10,500-pt Premium (`W`)** Saver flight on Virgin metal (`CUN–LHR`), or a **15,000-pt Economy flight to Europe on Air France/KLM metal (`MEX–CDG/AMS`)**!"
        )
    else:
        st.info(
            "**1️⃣ Primera Razón — Acreditar a la Propia Aerolínea ('Own Metal') Casi Nunca Es Óptimo (Aeroméxico vs. Virgin Atlantic):**  \n"
            "La mayoría de los viajeros acreditan sus vuelos pagados al programa de la misma aerolínea en la que vuelan, perdiendo oportunidades enormes dentro de la misma alianza.  \n"
            "• **Ejemplo Real:** Si vuelas redondo a Europa con **Aeroméxico (`MEX–MAD–MEX`)** y acreditas en **Aeroméxico Rewards**, "
            "quedas muy lejos de los **75,000 puntos** que pide Aeroméxico para un vuelo sencillo en Turista a Europa.  \n"
            "• **El Arbitraje de Alianza:** Si acreditas ese mismo vuelo de Aeroméxico en su socio SkyTeam **Virgin Atlantic Flying Club (`VS_FC`)**, "
            "un solo viaje redondo a Europa te da entre **5,630 y 16,800+ Virgin Points**—¡y con eso desbloqueas un vuelo Saver de **6,000 pts en Turista** o **10,500 pts en Premium (`W`)** en Virgin Atlantic (`CUN–LHR`), o un vuelo de **15,000 pts de México a Europa en metal de Air France/KLM (`MEX–CDG/AMS`)**!"
        )

with col_m2:
    if not is_es:
        st.success(
            "**2️⃣ Why Built — Cardholders Don't Know the True Value of Their Bank Points (BBVA & Santander → Iberia Avios):**  \n"
            "Millions of cardholders in Mexico spend **Puntos BBVA** or **Santander Unique Rewards** at cash-register terminals for tiny cashback discounts (~$0.07–$0.10 MXN/pt) without realizing how far those points go when transferred to airline partners.  \n"
            "• **Real-World Example:** Both **BBVA México** and **Santander Unique Rewards** (as well as **American Express México**) transfer directly to **Iberia Club (Avios)**.  \n"
            "• **21,000 Avios to Europe + Full Flexibility:** For just **21,000 Avios** one-way, you can fly nonstop from **Mexico City to Madrid (`MEX–MAD`)** paying only with Avios (+ airport taxes). "
            "Even better, Iberia's **Avios & Money** slider lets you choose to pay **even fewer Avios** (e.g., 9,000 Avios + cash co-pay), and **Avios tickets are vastly more flexible** than cheap cash fares (allowing date changes or full Avios refunds for a minimal ~€25 fee)."
        )
    else:
        st.success(
            "**2️⃣ Segunda Razón — La Gente Desconoce el Valor Real de sus Puntos Bancarios (BBVA y Santander → Iberia Avios):**  \n"
            "En México, la mayoría gasta sus **Puntos BBVA** o **Santander Unique Rewards** en comercios a un valor mínimo (~$0.07–$0.10 MXN por punto) sin saber que pueden transferirlos a programas de aerolíneas.  \n"
            "• **Ejemplo Real:** Tanto **BBVA México** como **Santander Unique Rewards** (y **American Express México**) transfieren directamente a **Iberia Club (Avios)**.  \n"
            "• **21,000 Avios a Europa + Máxima Flexibilidad:** Con solo **21,000 Avios** puedes volar directo de **Ciudad de México a Madrid (`MEX–MAD`)** pagando únicamente con Avios (+ impuestos). "
            "Además, el esquema **Avios & Money** te permite elegir pagar con **incluso menos Avios** (ej. 9,000 Avios + efectivo), y los **boletos emitidos con Avios son mucho más flexibles** que las tarifas económicas en efectivo (permiten cambios o reembolso de Avios por una penalización mínima de ~€25)."
        )

# ---------------------------------------------------------------------------
# Sidebar: Author Credentials, Mexican Bank Reference & WIP Status
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
        st.markdown("### 🇲🇽 Key Mexican Rules Seeded")
        st.markdown(
            """
            - **Aeroméxico → Virgin Atlantic (`VS_FC`)**:
              - 1x `MEX–MAD–MEX` round-trip on `AM` earns **5,630–16,800+ VS Points**
              - Unlocks **`CUN–LHR` (Europe) for 6,000 VS Points!**
            - **BBVA (`BBVA_MX`) → Iberia Avios**:
              - `2.6 Puntos BBVA = 1 Avios` (min `130` pts) + `20%` promo
            - **Santander (`SANTANDER_MX`) → Iberia Avios**:
              - `2 Unique Points = 1 Avios` + `25%` promo
            - **Amex México (`AMEX_MX`) → Avios / VS**:
              - `1 : 1` to Iberia Avios (+20%) & Virgin Atlantic (+30%)
            """
        )
        st.divider()
        st.markdown("### 🚧 Demo & WIP Status")
        st.markdown(
            """
            **Phase 1 — Live Engine (`src/core/`)**
            - 🟢 `models.py` *(Domain Dataclasses)*
            - 🟢 `seed_data.py` *(MX Banks & Alliances)*
            - 🟢 `calculator.py` *(Arbitrage & EU261)*
            - 🟢 `test_calculator.py` *(Unit Tests)*

            **Phase 2 — In Progress (`# TODO`)**
            - 🟡 `ingestion_client.py` *(Live TUA/YQ & Promos)*
            - 🟡 `db/session.py` & `repository.py` *(PostgreSQL)*
            - 🟡 `api/main.py` & `routes.py` *(FastAPI REST)*
            - 🟡 `serverless/lambda_handler.py` *(AWS Lambda)*
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
        st.markdown("### 🇲🇽 Reglas Clave en México")
        st.markdown(
            """
            - **Aeroméxico → Virgin Atlantic (`VS_FC`)**:
              - 1 vuelo redondo `MEX–MAD–MEX` en `AM` da **5,630–16,800+ VS Points**
              - ¡Desbloquea **Cancún–Europa (`CUN–LHR`) por 6,000 VS Points**!
            - **BBVA (`BBVA_MX`) → Iberia Avios**:
              - `2.6 Puntos BBVA = 1 Avios` (mín `130` pts) + `20%` bono
            - **Santander (`SANTANDER_MX`) → Iberia Avios**:
              - `2 Unique Points = 1 Avios` + `25%` bono
            - **Amex México (`AMEX_MX`) → Avios / VS**:
              - `1 : 1` a Iberia Avios (+20%) y Virgin Atlantic (+30%)
            """
        )
        st.divider()
        st.markdown("### 🚧 Estado del Proyecto (WIP)")
        st.markdown(
            """
            **Fase 1 — Motor Activo (`src/core/`)**
            - 🟢 `models.py` *(Modelos de Dominio)*
            - 🟢 `seed_data.py` *(Bancos MX y Alianzas)*
            - 🟢 `calculator.py` *(Arbitraje y EU261)*
            - 🟢 `test_calculator.py` *(Pruebas Unitarias)*

            **Fase 2 — En Construcción (`# TODO`)**
            - 🟡 `ingestion_client.py` *(TUA/YQ y Bonos en Vivo)*
            - 🟡 `db/session.py` y `repository.py` *(PostgreSQL)*
            - 🟡 `api/main.py` y `routes.py` *(FastAPI REST)*
            - 🟡 `serverless/lambda_handler.py` *(AWS Lambda)*
            """
        )

# ---------------------------------------------------------------------------
# Main Navigation Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    [
        "🗺️ 1. Motivation, How It Works & Architecture Map" if not is_es else "🗺️ 1. Motivación, Cómo Funciona y Mapa Arquitectónico",
        "💳 2. Bank Point Arbitrage (BBVA, Santander, Amex → Avios/VS)" if not is_es else "💳 2. Arbitraje Bancario (BBVA, Santander, Amex → Avios/VS)",
        "🛫 3. Flight Crediting (Aeroméxico → Virgin 6k Unlock & EU261)" if not is_es else "🛫 3. Acreditación de Vuelos (Aeroméxico → Virgin 6k y EU261)",
        "🛠️ 4. Work-in-Progress Backend Inspector (`# TODO` Phase 2)" if not is_es else "🛠️ 4. Inspector de Backend en Progreso (`# TODO` Fase 2)",
    ]
)

# ===========================================================================
# TAB 1: MOTIVATION, HOW IT WORKS & ARCHITECTURAL MAP
# ===========================================================================
with tab1:
    st.subheader(
        "How the Engine Works & Architectural Map"
        if not is_es
        else "Cómo Funciona el Motor y Mapa de Arquitectura del Sistema"
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
                  <div style="font-weight:700;color:#E2E8F0;margin-bottom:6px;">1. Traveler Inputs (Paid Flights &amp; Bank Points)</div>
                  • <b>Mexican Credit Cards:</b> <code>BBVA México</code> (2.6:1 to Avios), <code>Santander Unique</code> (2:1 to Avios), <code>Amex México</code> (1:1 to Avios / Virgin Atlantic)<br/>
                  • <b>Flight Segments:</b> Operating Airline (<code>AM</code>, <code>IB</code>, <code>LH</code>, <code>UA</code>), Booking Class (<code>J, I, P, Y, K</code>) &amp; Ticket Price
                </div>
                <div style="background:#064E3B;padding:14px;border-radius:8px;border-left:4px solid #10B981;">
                  <div style="font-weight:700;color:#6EE7B7;margin-bottom:6px;">🟢 2. Phase 1: Pure-Python Core (LIVE NOW in <code>src/core/</code>)</div>
                  • <code>seed_data.py</code>: 10 Alliance Programs (including <b>Virgin Atlantic 6,000-pt CUN–Europe</b> &amp; <b>Iberia 21,000-Avios MEX–MAD</b>)<br/>
                  • <code>calculator.py</code>: Haversine Distance, Mexican <b>TUA Tax Stripper</b> ($65 USD at MEX / $58 at CUN), Asymmetric Transfer Math, 0% Fare-Class Trap Detector &amp; <b>EU261</b> (€250/€400/€600)
                </div>
                <div style="background:#451A03;padding:14px;border-radius:8px;border-left:4px solid #F59E0B;">
                  <div style="font-weight:700;color:#FCD34D;margin-bottom:6px;">🟡 3. Phase 2: Production Backend (WIP <code># TODO</code> Scaffolds)</div>
                  • <code>src/core/ingestion_client.py</code>: Live GDS Tax/YQ Parser &amp; Bank Promo Webhook<br/>
                  • <code>src/db/</code> (<code>session.py</code>, <code>repository.py</code>): Async PostgreSQL 16 (<code>asyncpg</code>) Batch Lookup &amp; Upsert<br/>
                  • <code>src/api/</code> &amp; <code>src/serverless/</code>: FastAPI REST Endpoints + AWS Lambda <code>Mangum</code> &amp; EventBridge 12h Cron
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
                  <div style="font-weight:700;color:#E2E8F0;margin-bottom:6px;">1. Entradas del Viajero (Vuelos y Puntos Bancarios)</div>
                  • <b>Tarjetas en México:</b> <code>BBVA México</code> (2.6:1 a Avios), <code>Santander Unique</code> (2:1 a Avios), <code>Amex México</code> (1:1 a Avios / Virgin Atlantic)<br/>
                  • <b>Segmentos de Vuelo:</b> Aerolínea Operadora (<code>AM</code>, <code>IB</code>, <code>LH</code>, <code>UA</code>), Clase Tarifaria (<code>J, I, P, Y, K</code>) y Precio
                </div>
                <div style="background:#064E3B;padding:14px;border-radius:8px;border-left:4px solid #10B981;">
                  <div style="font-weight:700;color:#6EE7B7;margin-bottom:6px;">🟢 2. Fase 1: Motor Dominio en Python (ACTIVO AHORA en <code>src/core/</code>)</div>
                  • <code>seed_data.py</code>: 10 Programas de Lealtad (incluyendo <b>Virgin Atlantic 6,000 pts CUN–Europa</b> e <b>Iberia 21,000 Avios MEX–MAD</b>)<br/>
                  • <code>calculator.py</code>: Distancia Haversine, Desglose de <b>TUA Mexicana</b> ($65 USD en MEX / $58 en CUN), Conversión Asimétrica, Detector de Trampas de 0% y <b>EU261</b> (€250/€400/€600)
                </div>
                <div style="background:#451A03;padding:14px;border-radius:8px;border-left:4px solid #F59E0B;">
                  <div style="font-weight:700;color:#FCD34D;margin-bottom:6px;">🟡 3. Fase 2: Backend de Producción (Scaffolds <code># TODO</code> en Progreso)</div>
                  • <code>src/core/ingestion_client.py</code>: Lector GDS de Impuestos/YQ y Webhook de Bonos Bancarios<br/>
                  • <code>src/db/</code> (<code>session.py</code>, <code>repository.py</code>): PostgreSQL 16 Asíncrono (<code>asyncpg</code>)<br/>
                  • <code>src/api/</code> y <code>src/serverless/</code>: Rutas REST en FastAPI + AWS Lambda <code>Mangum</code> y EventBridge
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.graphviz_chart(
        r"""
        digraph LoyaltyArbitrageArchitectureMX {
            rankdir=LR;
            node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, margin="0.18,0.10"];
            edge [fontname="Helvetica", fontsize=9, color="#475569"];

            subgraph cluster_inputs {
                label="Inputs";
                style="dashed,rounded";
                color="#64748B";
                fontcolor="#334155";
                in_cards  [label="🇲🇽 Bank Points (BBVA, Santander, Amex)\n• 21,000 Avios MEX-MAD (Flexible + Avios & Money)\n• 6,000 Virgin Points CUN-LHR (Europe)", fillcolor="#F1F5F9", color="#94A3B8"];
                in_flight [label="🛫 Paid Flight Segments\n• e.g. Aeroméxico MEX-MAD-MEX\n• Credited to AM Rewards vs. Virgin Atlantic", fillcolor="#F1F5F9", color="#94A3B8"];
            }

            subgraph cluster_phase1 {
                label="🟢 PHASE 1: LIVE PURE-PYTHON CORE (src/core/ — Active in Demo)";
                style="rounded,filled";
                fillcolor="#ECFDF5";
                color="#10B981";
                fontcolor="#065F46";

                seed [label="src/core/seed_data.py\n• 13 Airports & MEX/CUN TUA\n• 10 Programs (VS, IB, AM, LH, UA...)\n• MX & US Bank Transfer Rules", fillcolor="#D1FAE5", color="#059669"];
                geo  [label="Geodesic, TUA & EU261 Math\n• Haversine Great Circle (mi/km)\n• Strips MEX/CUN TUA Taxes\n• Static EU261 (€250/€400/€600)", fillcolor="#A7F3D0", color="#059669"];
                calc [label="src/core/calculator.py\n• Bank Ratio & Increment Rounding\n• Own Metal vs Partner Arbitrage\n• Immediate Flight Unlocks (6k VS / 21k IB)", fillcolor="#6EE7B7", color="#047857"];
            }

            subgraph cluster_phase2 {
                label="🟡 PHASE 2: WORK-IN-PROGRESS BACKEND (src/db, src/api, src/serverless — # TODO)";
                style="rounded,filled";
                fillcolor="#FFFBEB";
                color="#F59E0B";
                fontcolor="#92400E";

                ingest [label="src/core/ingestion_client.py\n[# TODO] Live GDS Tax & YQ\n+ Bank Promo Bonus Webhook", fillcolor="#FEF3C7", color="#D97706"];
                db     [label="src/db/ (session & repository)\n[# TODO] PostgreSQL 16 + asyncpg\nBatch SQL Lookup & Upsert", fillcolor="#FEF3C7", color="#D97706"];
                api    [label="src/api/ (main & routes)\n[# TODO] FastAPI REST Endpoints\nPOST /optimize-transfer\nPOST /simulate-crediting", fillcolor="#FEF3C7", color="#D97706"];
                lambda [label="src/serverless/lambda_handler.py\n[# TODO] AWS Lambda + Mangum\n+ EventBridge 12h Cron Sync", fillcolor="#FEF3C7", color="#D97706"];
            }

            in_cards -> calc;
            in_flight -> geo;
            seed -> geo;
            seed -> calc;
            geo -> calc;
            ingest -> db [style=dashed, label="Phase 2"];
            db -> calc [style=dashed, label="Phase 2"];
            calc -> api [style=dashed, label="Phase 2"];
            api -> lambda [style=dashed, label="Phase 2"];
        }
        """
    )

    st.markdown(
        "#### 📊 Reference Table: Why Strategy #1 (Virgin Atlantic) & Strategy #2 (Iberia Avios) Beat Standard Defaults"
        if not is_es
        else "#### 📊 Tabla Comparativa: Por Qué la Estrategia #1 (Virgin Atlantic) y #2 (Iberia Avios) Superan lo Tradicional"
    )
    if not is_es:
        comp_rows = [
            {
                "Scenario": "1. Paid Aeroméxico Round-Trip to Europe (MEX–MAD–MEX)",
                "Standard Default ('Own Metal' / Cashback)": "Credit to Aeroméxico Rewards → Earns ~11,260–22,000 AM points (requires 75,000 pts for 1 Europe Economy ticket = 0 flights unlocked)",
                "Smart Arbitrage Strategy in This Engine": "Credit to Virgin Atlantic Flying Club (SkyTeam partner) → Earns 5,630–16,890 Virgin Points → Immediately unlocks 1x to 2x Cancún–London (CUN–LHR) Economy flights (only 6,000 VS Points each!)",
            },
            {
                "Scenario": "2. Using BBVA Puntos / Santander Unique Rewards / Amex MX",
                "Standard Default ('Own Metal' / Cashback)": "Spend points at store terminals for ~0.5¢ USD ($0.10 MXN/pt) or transfer to Aeroméxico (75,000 pts Economy / 145,000 pts Business to Madrid)",
                "Smart Arbitrage Strategy in This Engine": "Transfer to Iberia Club (Avios) → Fly nonstop MEX–MAD to Europe for just 21,000 Avios in Economy (or 40,500 Avios in Business), use 'Avios & Money' to pay even fewer Avios, and keep full ticket change/refund flexibility!",
            },
        ]
    else:
        comp_rows = [
            {
                "Escenario": "1. Vuelo Pagado Redondo a Europa en Aeroméxico (MEX–MAD–MEX)",
                "Opción Tradicional ('Own Metal' / Cashback)": "Acreditar en Aeroméxico Rewards → Acumula ~11,260–22,000 puntos AM (pide 75,000 pts para 1 boleto Turista a Europa = 0 vuelos desbloqueados)",
                "Estrategia de Arbitraje en Este Motor": "Acreditar en Virgin Atlantic Flying Club (socio SkyTeam) → Acumula 5,630–16,890 Virgin Points → ¡Desbloquea de inmediato 1 a 2 vuelos Cancún–Londres (CUN–LHR) en Turista (solo 6,000 VS Points c/u)!",
            },
            {
                "Escenario": "2. Uso de Puntos BBVA / Santander Unique Rewards / Amex MX",
                "Opción Tradicional ('Own Metal' / Cashback)": "Pagar en comercios a ~$0.10 MXN/punto o transferir a Aeroméxico (75,000 pts en Turista / 145,000 pts en Clase Premier a Madrid)",
                "Estrategia de Arbitraje en Este Motor": "Transferir a Iberia Club (Avios) → Volar directo MEX–MAD a Europa por solo 21,000 Avios en Turista (o 40,500 Avios en Business), usar 'Avios & Money' para requerir aún menos Avios, y tener boletos flexibles reembolsables.",
            },
        ]
    st.dataframe(comp_rows, use_container_width=True, hide_index=True)

# ===========================================================================
# TAB 2: BANK POINT ARBITRAGE (BBVA, SANTANDER, AMEX -> IBERIA 21K & VIRGIN 6K)
# ===========================================================================
with tab2:
    st.subheader(
        "💳 Mexican Credit Card Point Transfer Simulator (BBVA, Santander Unique, Amex México)"
        if not is_es
        else "💳 Simulador de Transferencia de Puntos Bancarios (BBVA, Santander Unique, Amex México)"
    )
    st.caption(
        "Test how BBVA Puntos, Santander Unique Rewards, and Amex México unlock 21,000-Avios flights to Madrid (with Avios & Money flexibility) and 6,000-point Virgin Atlantic flights from Cancún to Europe."
        if not is_es
        else "Compara cómo Puntos BBVA, Santander Unique Rewards y Amex México desbloquean vuelos a Madrid por 21,000 Avios (con flexibilidad Avios & Money) y vuelos de Cancún a Europa por 6,000 puntos en Virgin Atlantic."
    )

    tc1, tc2, tc3, tc4 = st.columns(4)
    with tc1:
        corridor = st.selectbox(
            "1. Select Target Route" if not is_es else "1. Selecciona Ruta Objetivo",
            options=[
                ("MEX", "MAD", "🇲🇽➡️🇪🇸 MEX → MAD (21,000 Avios on Iberia vs. 75,000 on Aeroméxico)" if not is_es else "🇲🇽➡️🇪🇸 MEX → MAD (21,000 Avios en Iberia vs. 75,000 en Aeroméxico)"),
                ("CUN", "LHR", "🇲🇽➡️🇬🇧 CUN → LHR (6k Economy / 10.5k Premium W on Virgin Metal!)" if not is_es else "🇲🇽➡️🇬🇧 CUN → LHR (¡6k Turista / 10.5k Premium W en Virgin Atlantic!)"),
                ("MEX", "CDG", "🇲🇽➡️🇫🇷 MEX → CDG/AMS (15,000 Virgin Points on Air France / KLM Metal!)" if not is_es else "🇲🇽➡️🇫🇷 MEX → CDG/AMS (¡15,000 Virgin Points en Air France / KLM!)"),
                ("MEX", "FRA", "🇲🇽➡️🇩🇪 MEX → FRA (CDMX to Frankfurt — Star Alliance)" if not is_es else "🇲🇽➡️🇩🇪 MEX → FRA (CDMX a Frankfurt — Star Alliance)"),
                ("MEX", "CUN", "🇲🇽➡️🇲🇽 MEX → CUN (Domestic Mexico — 7,500 Flying Blue vs 12k AM)" if not is_es else "🇲🇽➡️🇲🇽 MEX → CUN (Nacional — 7,500 Flying Blue vs 12k AM)"),
                ("MAD", "BCN", "🇪🇸➡️🇪🇸 MAD → BCN (4,500 Avios Intra-Europe Hop)" if not is_es else "🇪🇸➡️🇪🇸 MAD → BCN (4,500 Avios Vuelo Corto en Europa)"),
            ],
            format_func=lambda x: x[2],
        )
    with tc2:
        cabin_pick = st.selectbox(
            "2. Select Cabin Class" if not is_es else "2. Selecciona Cabina",
            options=[CabinClass.ECONOMY, CabinClass.BUSINESS],
            format_func=lambda c: (
                ("💺 Economy Class (21k Avios MEX-MAD / 6k VS CUN-LHR)" if not is_es else "💺 Turista / Economy (21k Avios MEX-MAD / 6k VS CUN-LHR)")
                if c == CabinClass.ECONOMY
                else ("💺 Business / Upper Class (40.5k Avios MEX-MAD / 29k VS CUN-LHR)" if not is_es else "💺 Clase Ejecutiva / Business (40.5k Avios MEX-MAD / 29k VS CUN-LHR)")
            ),
        )
    with tc3:
        bank_pick = st.selectbox(
            "3. Select Bank Ecosystem" if not is_es else "3. Selecciona Banco",
            options=[
                "ALL_MX",
                "BBVA_MX",
                "SANTANDER_MX",
                "AMEX_MX",
                "ALL_US",
            ],
            format_func=lambda b: {
                "ALL_MX": "🇲🇽 All Mexican Cards (BBVA, Santander, Amex MX)" if not is_es else "🇲🇽 Todas las Tarjetas en México (BBVA, Santander, Amex MX)",
                "BBVA_MX": "🇲🇽 BBVA México (Puntos BBVA — 2.6:1 Avios / 1.6:1 AM)",
                "SANTANDER_MX": "🇲🇽 Santander México (Unique Rewards — 2:1 Avios / 1:1 AM)",
                "AMEX_MX": "🇲🇽 American Express México (Membership Rewards — 1:1 Avios/VS)",
                "ALL_US": "🇺🇸 US Cards (Optional Benchmark: Chase, Amex US, Citi, CapOne)" if not is_es else "🇺🇸 Tarjetas EE.UU. (Comparativa Opcional: Chase, Amex, Citi)",
            }[b],
        )
    with tc4:
        bonus_mode = st.selectbox(
            "4. Promotional Transfer Bonus" if not is_es else "4. Bono Promocional de Transferencia",
            options=["SEEDED_DEFAULT", "CUSTOM_SLIDER"],
            format_func=lambda m: (
                ("Active Bank Promos (20% BBVA, 25% Santander, 20–30% Amex)" if not is_es else "Bonos Bancarios Activos (20% BBVA, 25% Santander, 20–30% Amex)")
                if m == "SEEDED_DEFAULT"
                else ("Custom Bonus % Slider Override" if not is_es else "Ajustar Bono % Manualmente con el Control Deslizante")
            ),
        )

    orig_i, dest_i, _ = corridor
    default_cash = next(
        (s.typical_cash_fare_one_way_usd for s in AWARD_SWEET_SPOTS if s.origin_iata == orig_i and s.destination_iata == dest_i and s.cabin == cabin_pick),
        680.0,
    )

    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        custom_bonus_pct = st.slider(
            "Transfer Bonus Override (%)" if not is_es else "Bono de Transferencia (%)",
            min_value=0,
            max_value=100,
            value=25 if bonus_mode == "CUSTOM_SLIDER" else 0,
            step=5,
        )
    with sc2:
        custom_cash_fare = st.slider(
            ("Comparable One-Way Flexible Cash Ticket (USD)" if not is_es else "Precio Comparable Boleto Flexible Sencillo (USD)"),
            min_value=100.0,
            max_value=5000.0,
            value=float(default_cash),
            step=50.0,
        )
    with sc3:
        avios_money_pct = st.slider(
            ("Iberia 'Avios & Money' Slider (% of Avios Used)" if not is_es else "Descuento 'Avios & Money' de Iberia (% de Avios a Usar)"),
            min_value=50,
            max_value=100,
            value=100,
            step=10,
            help=(
                "Iberia Club lets you pay 100% of the award in Avios (e.g. 21,000 Avios) OR choose 50%–90% Avios + a small cash co-pay while keeping full Avios ticket flexibility!"
                if not is_es
                else "Iberia Club te permite pagar el 100% en Avios (ej. 21,000 Avios) O elegir usar entre 50% y 90% de los Avios + una diferencia en efectivo, manteniendo la flexibilidad total del boleto Avios."
            ),
        )

    pathways = _run_transfer_pathways(
        orig_i,
        dest_i,
        cabin=cabin_pick,
        bank_selector=bank_pick,
        override_bonus_pct=float(custom_bonus_pct) if bonus_mode == "CUSTOM_SLIDER" else None,
        override_cash_fare_usd=float(custom_cash_fare),
        is_es=is_es,
    )

    if pathways:
        winner = pathways[0]
        worst = pathways[-1]
        pts_saved = worst.bank_points_required - winner.bank_points_required
        net_saved_mxn = winner.net_cash_saved_usd * MXN_PER_USD
        mxn_per_pt = winner.effective_cents_per_point * (MXN_PER_USD / 100.0)

        # Calculate Avios & Money option if winner is IB_PLUS or BA_EC
        discounted_miles = int(round(winner.award_miles_required * (avios_money_pct / 100.0)))
        extra_copay_usd = round((winner.award_miles_required - discounted_miles) * 0.0135, 2)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric(
            "Lowest Bank Points Needed" if not is_es else "Menor Cantidad de Puntos Bancarios",
            f"{winner.bank_points_required:,} pts",
            winner.bank_currency_name,
        )
        k2.metric(
            "Target Airline Program" if not is_es else "Programa de Aerolínea Óptimo",
            winner.booking_program_name,
            f"Flies {winner.operating_carrier_iata} ({winner.award_miles_required:,} mi/Avios)",
        )
        k3.metric(
            "Net Cash Saved vs. Ticket" if not is_es else "Ahorro Neto vs. Efectivo",
            f"${winner.net_cash_saved_usd:,.0f} USD",
            f"~${net_saved_mxn:,.0f} MXN",
        )
        k4.metric(
            "Realized Value per Point" if not is_es else "Valor Real por Punto",
            f"${mxn_per_pt:.2f} MXN / pt",
            f"{winner.effective_cents_per_point:.2f} ¢ USD / pt",
        )

        if avios_money_pct < 100 and winner.booking_program_code in ("IB_PLUS", "BA_EC"):
            scaled_bank_pts = int(round(winner.bank_points_required * (avios_money_pct / 100.0)))
            if not is_es:
                st.info(
                    f"💡 **Iberia 'Avios & Money' Option ({avios_money_pct}% Avios Selected):** Instead of `{winner.award_miles_required:,} Avios`, "
                    f"you can book this exact flight for just **`{discounted_miles:,} Avios` (~`{scaled_bank_pts:,}` bank points)** "
                    f"+ `${winner.taxes_and_yq_usd + extra_copay_usd:,.0f} USD` total cash co-pay, while keeping **full Avios change/refund flexibility**!"
                )
            else:
                st.info(
                    f"💡 **Opción 'Avios & Money' de Iberia ({avios_money_pct}% Avios Seleccionado):** En lugar de `{winner.award_miles_required:,} Avios`, "
                    f"puedes emitir este mismo boleto con solo **`{discounted_miles:,} Avios` (~`{scaled_bank_pts:,}` puntos bancarios)** "
                    f"+ `${winner.taxes_and_yq_usd + extra_copay_usd:,.0f} USD` de copago total, conservando la **flexibilidad total de cambios y reembolso de Avios**."
                )

        rows = []
        for idx, p in enumerate(pathways, start=1):
            val_mxn = p.effective_cents_per_point * (MXN_PER_USD / 100.0)
            if not is_es:
                rows.append(
                    {
                        "Rank": f"#{idx}",
                        "Bank Card Program": p.bank_currency_name,
                        "Transfer To Airline": f"{p.booking_program_name} ({p.booking_program_code})",
                        "Carrier": p.operating_carrier_iata,
                        "Award Miles / Avios": f"{p.award_miles_required:,}",
                        "Effective Ratio": f"{p.effective_transfer_ratio}:1",
                        "Bank Points Required": f"{p.bank_points_required:,} pts",
                        "Taxes & TUA": f"${p.taxes_and_yq_usd:,.0f} USD (${p.taxes_and_yq_usd * MXN_PER_USD:,.0f} MXN)",
                        "Value per Point": f"${val_mxn:.2f} MXN ({p.effective_cents_per_point:.2f}¢ USD)",
                        "Flexibility & Arbitrage Notes": p.notes,
                    }
                )
            else:
                rows.append(
                    {
                        "Posición": f"#{idx}",
                        "Tarjeta / Banco": p.bank_currency_name,
                        "Transferir a Aerolínea": f"{p.booking_program_name} ({p.booking_program_code})",
                        "Operador": p.operating_carrier_iata,
                        "Millas / Avios Req.": f"{p.award_miles_required:,}",
                        "Tasa Efectiva": f"{p.effective_transfer_ratio}:1",
                        "Puntos Bancarios Req.": f"{p.bank_points_required:,} pts",
                        "Impuestos y TUA": f"${p.taxes_and_yq_usd:,.0f} USD (${p.taxes_and_yq_usd * MXN_PER_USD:,.0f} MXN)",
                        "Valor por Punto": f"${val_mxn:.2f} MXN ({p.effective_cents_per_point:.2f}¢ USD)",
                        "Notas de Flexibilidad y Arbitraje": p.notes,
                    }
                )
        st.dataframe(rows, use_container_width=True, hide_index=True)

# ===========================================================================
# TAB 3: PAID FLIGHT CREDITING (AEROMEXICO -> VIRGIN ATLANTIC 6K UNLOCK & EU261)
# ===========================================================================
with tab3:
    st.subheader(
        "🛫 Paid Flight Crediting Simulator ('Default to the Metal' vs. 'Smart Alliance Switch')"
        if not is_es
        else "🛫 Simulador de Acreditación de Vuelos Pagados ('Propia Aerolínea' vs. 'Socio de Alianza')"
    )
    st.caption(
        "Defaults to the flagship example: flying Aeroméxico round-trip to Europe (`MEX ↔ MAD`) and comparing Aeroméxico Rewards vs. Virgin Atlantic Flying Club (where 6,000 Virgin Points unlocks Cancún → Europe!)."
        if not is_es
        else "Inicia con el ejemplo clave: volar redondo a Europa con Aeroméxico (`MEX ↔ MAD`) comparando Aeroméxico Rewards contra Virgin Atlantic Flying Club (¡donde 6,000 Virgin Points desbloquean Cancún → Europa!)."
    )

    r1, r2, r3, r4 = st.columns(4)
    with r1:
        itinerary_choice = st.selectbox(
            "1. Select Paid Flight Route & Operating Airline" if not is_es else "1. Selecciona Vuelo Pagado y Aerolínea Operadora",
            options=[
                ("MEX", "MAD", "AM", "🇲🇽➡️🇪🇸 MEX ↔ MAD on Aeroméxico (AM — Unlocks 6k Virgin Atlantic!)" if not is_es else "🇲🇽➡️🇪🇸 MEX ↔ MAD en Aeroméxico (AM — ¡Desbloquea 6k en Virgin Atlantic!)"),
                ("MEX", "MAD", "IB", "🇲🇽➡️🇪🇸 MEX ↔ MAD on Iberia (IB — Oneworld: Iberia vs. BA vs. AA)" if not is_es else "🇲🇽➡️🇪🇸 MEX ↔ MAD en Iberia (IB — Oneworld: Iberia vs. BA vs. AA)"),
                ("MEX", "FRA", "LH", "🇲🇽➡️🇩🇪 MEX ↔ FRA on Lufthansa (LH — Star Alliance: Turkish vs. LH)" if not is_es else "🇲🇽➡️🇩🇪 MEX ↔ FRA en Lufthansa (LH — Star Alliance: Turkish vs. LH)"),
                ("MEX", "EWR", "UA", "🇲🇽➡️🇺🇸 MEX ↔ EWR on United Airlines (UA — Star Alliance)" if not is_es else "🇲🇽➡️🇺🇸 MEX ↔ EWR en United Airlines (UA — Star Alliance)"),
                ("FRA", "VIE", "LH", "🇩🇪➡️🇦🇹 FRA ↔ VIE on Lufthansa (LH — Intra-EU Short-Haul)" if not is_es else "🇩🇪➡️🇦🇹 FRA ↔ VIE en Lufthansa (LH — Vuelo Corto Intra-UE)"),
            ],
            format_func=lambda x: x[3],
        )
    with r2:
        b_class_choice = st.selectbox(
            "2. Select Booking Class" if not is_es else "2. Selecciona Clase Tarifaria",
            options=["K", "Y", "I", "P", "J"],
            format_func=lambda c: {
                "K": ("K — Discounted Economy (55% Distance — Unlocks 6,000-pt VS Europe Flight on AM Round-Trip!)" if not is_es else "K — Turista Descuento (55% Distancia — ¡Desbloquea el vuelo de 6,000 pts en VS a Europa!)"),
                "Y": ("Y — Standard / Flex Economy (100% Distance — Unlocks 1x–2x 6k VS Europe Flights!)" if not is_es else "Y — Turista Estándar / Flex (100% Distancia — ¡Desbloquea 1x–2x vuelos de 6k en VS!)"),
                "I": ("I — Discounted Business (125%–150% Distance — Unlocks 2x 6k VS Flights!)" if not is_es else "I — Ejecutiva Descuento (125%–150% Distancia — ¡Desbloquea 2x vuelos de 6k en VS!)"),
                "P": ("P — Deep-Discount Business (125% on VS, 0% Trap on Turkish when flying LH!)" if not is_es else "P — Ejecutiva Promo (125% en VS, ¡Trampa de 0% en Turkish volando LH!)"),
                "J": ("J — Full-Fare Business (200%–250% Distance — Unlocks 3x 6k VS Flights!)" if not is_es else "J — Ejecutiva Flexible (200%–250% Distancia — ¡Desbloquea 3x vuelos de 6k en VS!)"),
            }[c],
            index=1,  # Default to 'Y' Economy so users immediately see an Economy round-trip on AM unlocking 6,000 VS Points!
        )
    with r3:
        ticket_stock_mode = st.selectbox(
            "3. Ticket Stock (Revenue vs. Distance)" if not is_es else "3. Emisión del Boleto (Gasto vs. Distancia)",
            options=["OWN_TICKET_STOCK", "PARTNER_DISTANCE_ONLY"],
            format_func=lambda m: (
                ("Operating Airline Ticket (Revenue on Home Program, Distance on Partners)" if not is_es else "Boleto de la Aerolínea Operadora (Por Gasto en su Programa, por Distancia en Socios)")
                if m == "OWN_TICKET_STOCK"
                else ("Partner / Agency Ticket (Distance × Class % Across All Programs)" if not is_es else "Boleto de Socio / Agencia (Distancia × % Clase en Todos los Programas)")
            ),
        )
    with r4:
        trip_type = st.radio(
            "4. Itinerary Direction" if not is_es else "4. Tipo de Viaje",
            options=["ROUND_TRIP", "ONE_WAY"],
            format_func=lambda t: ("🔄 Round-Trip (2 Segments)" if not is_es else "🔄 Viaje Redondo (2 Segmentos)") if t == "ROUND_TRIP" else ("➡️ One-Way (1 Segment)" if not is_es else "➡️ Sencillo (1 Segmento)"),
            horizontal=True,
        )

    orig_c, dest_c, op_carrier, _ = itinerary_choice
    is_rt = trip_type == "ROUND_TRIP"

    sp1, sp2, sp3 = st.columns(3)
    with sp1:
        spend_mode = st.selectbox(
            "5. Fare & Mexican TUA Input Mode" if not is_es else "5. Modo de Precio e Impuesto TUA",
            options=["ALL_IN_AUTO_STRIP", "EXACT_BASE_AND_YQ"],
            format_func=lambda m: (
                ("All-In Price (Auto-Strip MEX TUA & Airport Gov Taxes)" if not is_es else "Precio Total con Impuestos (Descontar TUA Automáticamente)")
                if m == "ALL_IN_AUTO_STRIP"
                else ("Exact Base Fare + YQ Surcharge Breakdown" if not is_es else "Tarifa Base Exacta + Cargo por Combustible YQ")
            ),
        )
    with sp2:
        if spend_mode == "ALL_IN_AUTO_STRIP":
            seg_all_in_usd = st.slider(
                ("All-In Ticket Price per One-Way Segment (USD)" if not is_es else "Precio Total por Segmento Sencillo (USD)"),
                min_value=150.0,
                max_value=5000.0,
                value=550.0 if b_class_choice in ("K", "Y") else 1800.0,
                step=50.0,
            )
            seg_base_usd = None
            seg_yq_usd = 0.0
        else:
            seg_base_usd = st.slider(
                ("Exact Base Fare per One-Way Segment (USD)" if not is_es else "Tarifa Base Exacta por Segmento Sencillo (USD)"),
                min_value=100.0,
                max_value=4000.0,
                value=400.0 if b_class_choice in ("K", "Y") else 1350.0,
                step=50.0,
            )
            seg_all_in_usd = None
    with sp3:
        if spend_mode == "EXACT_BASE_AND_YQ":
            seg_yq_usd = st.slider(
                ("Carrier Surcharge (YQ/YR) per Segment (USD)" if not is_es else "Cargo de Aerolínea (YQ/YR) por Segmento (USD)"),
                min_value=0.0,
                max_value=1000.0,
                value=90.0 if b_class_choice in ("K", "Y") else 280.0,
                step=20.0,
            )
        else:
            orig_ap_preview = AIRPORTS[orig_c]
            dest_ap_preview = AIRPORTS[dest_c]
            _, est_tax_preview = estimate_eligible_spend(
                orig_ap_preview, dest_ap_preview, None, 0.0, float(seg_all_in_usd), True
            )
            if not is_es:
                st.info(
                    f"🧾 **Mexican TUA & Gov Tax Stripper (`{orig_c} → {dest_c}`):** Strips **~${est_tax_preview:.2f} USD "
                    f"(~${est_tax_preview * MXN_PER_USD:,.0f} MXN)** in mandatory government taxes per leg (`{orig_c}` TUA/tax "
                    f"${orig_ap_preview.estimated_gov_departure_tax_usd:.0f} USD + `{dest_c}` duty) so only eligible `Base Fare + YQ` earns revenue miles."
                )
            else:
                st.info(
                    f"🧾 **Desglose Automático de TUA (`{orig_c} → {dest_c}`):** Descuenta **~${est_tax_preview:.2f} USD "
                    f"(~${est_tax_preview * MXN_PER_USD:,.0f} MXN)** de impuestos gubernamentales por tramo (`{orig_c}` TUA "
                    f"${orig_ap_preview.estimated_gov_departure_tax_usd:.0f} USD + tasas de `{dest_c}`) para calcular millas solo sobre `Tarifa Base + YQ`."
                )

    ticketing_code = op_carrier if ticket_stock_mode == "OWN_TICKET_STOCK" else "XX"

    built_segments = [
        FlightSegment(
            origin_iata=orig_c,
            destination_iata=dest_c,
            operating_carrier=op_carrier,
            booking_class=b_class_choice,
            ticketing_carrier=ticketing_code,
            base_fare_usd=seg_base_usd,
            yq_surcharge_usd=seg_yq_usd,
            total_ticket_price_usd=seg_all_in_usd,
        )
    ]
    if is_rt:
        built_segments.append(
            FlightSegment(
                origin_iata=dest_c,
                destination_iata=orig_c,
                operating_carrier=op_carrier,
                booking_class=b_class_choice,
                ticketing_carrier=ticketing_code,
                base_fare_usd=seg_base_usd,
                yq_surcharge_usd=seg_yq_usd,
                total_ticket_price_usd=seg_all_in_usd,
            )
        )

    ap_orig = AIRPORTS[orig_c]
    ap_dest = AIRPORTS[dest_c]
    one_way_mi, one_way_km = haversine_distance(ap_orig.latitude, ap_orig.longitude, ap_dest.latitude, ap_dest.longitude)
    mult_legs = 2 if is_rt else 1
    eu_out = evaluate_eu261_segment(ap_orig, ap_dest, op_carrier)
    eu_ret = evaluate_eu261_segment(ap_dest, ap_orig, op_carrier) if is_rt else None

    sim_rankings = _run_flight_crediting(built_segments, is_es=is_es)
    sample_prog = sim_rankings[0]

    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric(
        "Total Great Circle Distance" if not is_es else "Distancia Total Gran Círculo",
        f"{one_way_mi * mult_legs:,.0f} mi",
        f"{one_way_km * mult_legs:,.0f} km ({mult_legs} {'tramos' if is_es and is_rt else ('tramo' if is_es else ('legs' if is_rt else 'leg'))})",
    )
    m_col2.metric(
        "Eligible Spend (Base + YQ)" if not is_es else "Gasto Elegible (Base + YQ)",
        f"${sample_prog.eligible_spend_usd:,.2f} USD",
        (f"TUA & Taxes Stripped: ${sample_prog.estimated_gov_taxes_stripped_usd:,.2f}" if not is_es else f"TUA e Impuestos Descontados: ${sample_prog.estimated_gov_taxes_stripped_usd:,.2f}"),
    )
    m_col3.metric(
        (f"Outbound EU261 ({orig_c}→{dest_c})" if not is_es else f"EU261 Ida ({orig_c}→{dest_c})"),
        (f"€{eu_out['compensation_eur']} Protected" if not is_es else f"€{eu_out['compensation_eur']} Protegido") if eu_out["is_eligible"] else ("€0 (Not Covered)" if not is_es else "€0 (No Cubierto)"),
        f"{eu_out['distance_km']:,.0f} km ({op_carrier})",
    )
    if is_rt and eu_ret:
        m_col4.metric(
            (f"Return EU261 ({dest_c}→{orig_c})" if not is_es else f"EU261 Regreso ({dest_c}→{orig_c})"),
            (f"€{eu_ret['compensation_eur']} Protected" if not is_es else f"€{eu_ret['compensation_eur']} Protegido") if eu_ret["is_eligible"] else ("€0 (Not Covered)" if not is_es else "€0 (No Cubierto)"),
            f"{eu_ret['distance_km']:,.0f} km ({op_carrier})",
        )
    else:
        m_col4.metric(
            "Booking Class" if not is_es else "Clase Tarifaria",
            f"Class '{b_class_choice}'" if not is_es else f"Clase '{b_class_choice}'",
            f"Carrier: {op_carrier}" if not is_es else f"Aerolínea: {op_carrier}",
        )

    metal_res = next((r for r in sim_rankings if r.is_operating_metal_program), None)
    # Prefer a distance-based partner for the "Smart Alliance Switch" comparison when own-metal is revenue-based
    partner_res_list = [r for r in sim_rankings if not r.is_operating_metal_program]
    dist_partners = [r for r in partner_res_list if r.calculation_basis == "DISTANCE_AND_ZONE_BASED" and r.redeemable_miles_earned > 0]
    top_partner = dist_partners[0] if dist_partners else (partner_res_list[0] if partner_res_list else None)

    if metal_res and top_partner:
        miles_delta = top_partner.redeemable_miles_earned - metal_res.redeemable_miles_earned
        status_delta = round(top_partner.progress_to_gold_pct - metal_res.progress_to_gold_pct, 1)
        if not is_es:
            st.success(
                f"🔀 **Own Metal (`{metal_res.program_name}`) vs. Distance-Based Alliance Partner (`{top_partner.program_name}`):**  \n"
                f"• **Crediting to Operating Airline ({metal_res.program_name} — `{metal_res.calculation_basis}`):** Earns **{metal_res.redeemable_miles_earned:,}** points "
                f"(on `IB` Spain–Mexico flights, both **Iberia Club** and **British Airways Club** credit by spend at **7 Avios per €1 EUR** = 5 base + 2 LatAm bonus) "
                f"and reaches **{metal_res.progress_to_gold_pct}%** toward Gold/Sapphire status.  \n"
                f"• **Smart Partner Switch ({top_partner.program_name} — `{top_partner.calculation_basis}`):** Earns **{top_partner.redeemable_miles_earned:,}** points ({miles_delta:+,} vs. metal), "
                f"reaches **{top_partner.progress_to_gold_pct}%** toward Gold/Sapphire ({status_delta:+.1f}% status difference), and unlocks: "
                f"**{'; '.join(top_partner.unlocked_short_haul_awards) if top_partner.unlocked_short_haul_awards else 'progress toward long-haul sweet spots'}**."
            )
        else:
            st.success(
                f"🔀 **Propia Aerolínea (`{metal_res.program_name}`) vs. Socio de Alianza por Distancia (`{top_partner.program_name}`):**  \n"
                f"• **Propia Aerolínea ({metal_res.program_name} — `{metal_res.calculation_basis}`):** Acumula **{metal_res.redeemable_miles_earned:,}** puntos "
                f"(en vuelos `IB` España–México, tanto **Iberia Club** como **British Airways Club** acreditan por gasto a razón de **7 Avios por cada €1 EUR** = 5 base + 2 bono LatAm) "
                f"y alcanza **{metal_res.progress_to_gold_pct}%** hacia estatus Oro/Sapphire.  \n"
                f"• **Socio por Distancia ({top_partner.program_name} — `{top_partner.calculation_basis}`):** Acumula **{top_partner.redeemable_miles_earned:,}** puntos ({miles_delta:+,} vs. propia aerolínea), "
                f"alcanza **{top_partner.progress_to_gold_pct}%** hacia estatus Oro/Sapphire ({status_delta:+.1f}% dif. en estatus), y desbloquea: "
                f"**{'; '.join(top_partner.unlocked_short_haul_awards) if top_partner.unlocked_short_haul_awards else 'progreso hacia vuelos de largo radio'}**."
            )

    trap_prog = next((r for r in sim_rankings if r.own_metal_warning and ("0%" in r.own_metal_warning)), None)
    if trap_prog:
        st.error(trap_prog.own_metal_warning)

    table_cred = []
    for r in sim_rankings:
        unlocks_str = " | ".join(r.unlocked_short_haul_awards + r.flagship_sweet_spot_progress) or "—"
        if not is_es:
            table_cred.append(
                {
                    "Loyalty Program": f"{r.program_name} ({r.program_code})",
                    "Alliance": r.alliance.value,
                    "Strategy Role": "🏠 Own Metal Default" if r.is_operating_metal_program else "🤝 Smart Alliance Partner",
                    "Calc Basis": r.calculation_basis,
                    "Redeemable Miles / Points": f"{r.redeemable_miles_earned:,}",
                    "Status Progress": f"{r.progress_to_gold_pct}% ({r.status_points_earned:,.0f} / {r.gold_status_threshold:,.0f})",
                    "Own-Metal / Fare Trap Check": r.own_metal_warning or "✅ No Restriction",
                    "Tangible Flights Unlocked & Sweet Spot Progress": unlocks_str,
                }
            )
        else:
            table_cred.append(
                {
                    "Programa de Lealtad": f"{r.program_name} ({r.program_code})",
                    "Alianza": r.alliance.value,
                    "Rol Estratégico": "🏠 Propia Aerolínea (Metal)" if r.is_operating_metal_program else "🤝 Socio de Alianza",
                    "Base de Cálculo": r.calculation_basis,
                    "Millas / Puntos Acumulados": f"{r.redeemable_miles_earned:,}",
                    "Progreso a Estatus Oro": f"{r.progress_to_gold_pct}% ({r.status_points_earned:,.0f} / {r.gold_status_threshold:,.0f})",
                    "Restricciones / Trampas": r.own_metal_warning or "✅ Sin Restricción",
                    "Vuelos Desbloqueados y Progreso": unlocks_str,
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