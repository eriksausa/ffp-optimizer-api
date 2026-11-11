"""
Pure-Python Calculation & Arbitrage Engine (`src/core/calculator.py`).

Implements:
1. Credit card transfer bonus & effective Cents-Per-Mile (CPM) arbitrage math for
   Santander Unique Rewards (1:1 to Iberia), BBVA México (2.6:1 to Iberia, 1.6:1 to Aeroméxico),
   and American Express México (1:1 to Iberia, British Airways, Flying Blue, Aeroméxico).
2. Geodesic Haversine distance (`mi` & `km`), per-origin airport departure tax stripping
   (Mexican TUA applied strictly when departing `MEX`/`CUN`; European airport tax when departing `CDG`/`MAD`),
   and static EU261 bands (€250, €400, €600).
3. Multi-program flight crediting simulation for `CDG <-> MEX` on Aeroméxico (SkyTeam)
   and `MEX <-> MAD` on Iberia (Oneworld).
"""

import math
from typing import Optional

from src.core.models import (
    AirportProfile,
    AwardSweetSpot,
    CabinClass,
    CreditingSimulationResult,
    FlightSegment,
    TransferOptionResult,
)
from src.core.seed_data import (
    AIRPORTS,
    AWARD_SWEET_SPOTS,
    BANK_CURRENCIES,
    LOYALTY_PROGRAMS,
    PARTNER_EARNING_RULES,
    TRANSFER_PARTNER_RULES,
)

EARTH_RADIUS_KM = 6371.0088
KM_TO_MILES = 0.6213711922
EU_EEA_CH_CARRIERS = {"IB", "AF", "KL", "LH", "LX", "OS", "SN", "AY", "SK", "TP", "LO"}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    """
    Computes Great Circle distance between two latitude/longitude pairs.
    Returns `(distance_miles, distance_km)` rounded to 2 decimal places.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    dist_km = EARTH_RADIUS_KM * c
    dist_mi = dist_km * KM_TO_MILES
    return round(dist_mi, 2), round(dist_km, 2)


def apply_transfer_bonus(base_ratio: float, bonus_pct: float) -> float:
    """
    Calculates the effective transfer multiplier from bank points to airline miles.
    Example: base_ratio=1.0 with bonus_pct=20.0 -> 1.20 airline miles per 1 bank point.
    """
    if base_ratio <= 0:
        raise ValueError("base_ratio must be strictly positive.")
    if bonus_pct < 0:
        raise ValueError("bonus_pct cannot be negative.")
    return round(base_ratio * (1.0 + (bonus_pct / 100.0)), 4)


def calculate_required_bank_points(
    award_miles_needed: int,
    base_ratio: float,
    bonus_pct: float = 0.0,
    min_increment: int = 1000,
) -> int:
    """
    Computes how many credit card points must be transferred to reach `award_miles_needed`,
    rounding up to the bank's required transfer increment (1,000 pts for Santander/Amex, 130 pts for BBVA->Avios).
    """
    if award_miles_needed <= 0:
        return 0
    effective_ratio = base_ratio * (1.0 + (bonus_pct / 100.0))
    raw_points = round(award_miles_needed / effective_ratio, 6)
    if min_increment <= 1:
        return math.ceil(raw_points)
    return int(math.ceil(raw_points / min_increment) * min_increment)


def calculate_effective_cpm(
    cash_fare_usd: float,
    taxes_and_yq_usd: float,
    points_or_miles_used: int,
) -> float:
    """
    Computes realized Cents-Per-Point (CPP in USD cents) on a specific redemption:
        ((cash_fare_usd - taxes_and_yq_usd) * 100) / points_or_miles_used
    """
    if points_or_miles_used <= 0:
        raise ValueError("points_or_miles_used must be strictly positive.")
    net_value_usd = max(0.0, cash_fare_usd - taxes_and_yq_usd)
    return round((net_value_usd * 100.0) / points_or_miles_used, 2)


def find_best_transfer_pathways(
    origin_iata: str,
    destination_iata: str,
    cabin: CabinClass = CabinClass.ECONOMY,
    bank_code_filter: Optional[str] = None,
    override_bonus_pct: Optional[float] = None,
    override_cash_fare_usd: Optional[float] = None,
) -> list[TransferOptionResult]:
    """
    Evaluates all seeded `AwardSweetSpot` benchmarks for `(origin_iata, destination_iata, cabin)`
    and joins them against verified `TRANSFER_PARTNER_RULES` (Santander Unique, BBVA, Amex México).
    """
    orig = origin_iata.upper()
    dest = destination_iata.upper()

    matching_awards: list[AwardSweetSpot] = [
        spot
        for spot in AWARD_SWEET_SPOTS
        if spot.origin_iata == orig and spot.destination_iata == dest and spot.cabin == cabin
    ]

    results: list[TransferOptionResult] = []
    for spot in matching_awards:
        program = LOYALTY_PROGRAMS[spot.booking_program_code]
        cash_benchmark = (
            float(override_cash_fare_usd)
            if override_cash_fare_usd is not None and override_cash_fare_usd > 0
            else spot.typical_cash_fare_one_way_usd
        )

        for rule in TRANSFER_PARTNER_RULES:
            if rule.program_code != spot.booking_program_code:
                continue
            if bank_code_filter and rule.bank_code != bank_code_filter.upper():
                continue

            bank = BANK_CURRENCIES[rule.bank_code]
            effective_bonus = (
                float(override_bonus_pct)
                if override_bonus_pct is not None
                else rule.active_bonus_pct
            )
            eff_ratio = apply_transfer_bonus(rule.base_ratio, effective_bonus)
            bank_pts = calculate_required_bank_points(
                spot.miles_required_one_way,
                rule.base_ratio,
                effective_bonus,
                rule.min_transfer_increment,
            )
            cpp = calculate_effective_cpm(
                cash_benchmark,
                spot.taxes_and_yq_usd,
                bank_pts,
            )
            net_saved = round(max(0.0, cash_benchmark - spot.taxes_and_yq_usd), 2)

            if rule.base_ratio < 0.45:
                base_str = f"2.6 Puntos BBVA = 1 Avios (min {rule.min_transfer_increment} pts)"
            elif rule.base_ratio == 0.625:
                base_str = "1.6 Puntos BBVA = 1 Punto Aeroméxico"
            else:
                base_str = "1 : 1 Transfer Ratio"

            bonus_label = (
                f"{base_str} + {effective_bonus:.0f}% bonus ({eff_ratio}:1)."
                if effective_bonus > 0
                else f"{base_str}."
            )

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
                    cash_fare_benchmark_usd=cash_benchmark,
                    net_cash_saved_usd=net_saved,
                    effective_cents_per_point=cpp,
                    beats_cashout_baseline=(cpp > bank.baseline_cashout_cents_per_point),
                    notes=f"{spot.description} | {bonus_label}",
                )
            )

    results.sort(key=lambda r: (r.bank_points_required, r.taxes_and_yq_usd))
    return results


def estimate_eligible_spend(
    origin_airport: AirportProfile,
    dest_airport: AirportProfile,
    base_fare_usd: Optional[float],
    yq_surcharge_usd: float,
    total_ticket_price_usd: Optional[float],
    counts_yq_surcharge: bool,
) -> tuple[float, float]:
    """
    Separates eligible loyalty spend (Base Fare + carrier-imposed YQ/YR) from the
    departure airport's mandatory government tax:
    - Departing MEX/CUN strips Mexican TUA (~$65 / ~$58 USD).
    - Departing CDG strips French airport departure tax (~$75 USD).
    - Departing MAD strips Spanish AENA departure tax (~$42 USD).
    Returns `(eligible_spend_usd, estimated_gov_taxes_stripped_usd)`.
    """
    if base_fare_usd is not None:
        eligible_yq = yq_surcharge_usd if counts_yq_surcharge else 0.0
        eligible = round(base_fare_usd + eligible_yq, 2)
        gov_taxes = (
            round(max(0.0, total_ticket_price_usd - base_fare_usd - yq_surcharge_usd), 2)
            if total_ticket_price_usd is not None
            else round(origin_airport.estimated_gov_departure_tax_usd, 2)
        )
        return eligible, gov_taxes

    if total_ticket_price_usd is not None and total_ticket_price_usd > 0:
        # Strip strictly the departure airport's mandatory government tax
        est_gov_tax = min(
            round(origin_airport.estimated_gov_departure_tax_usd, 2),
            round(total_ticket_price_usd * 0.35, 2),
        )
        eligible = round(max(0.0, total_ticket_price_usd - est_gov_tax), 2)
        if not counts_yq_surcharge and yq_surcharge_usd > 0:
            eligible = round(max(0.0, eligible - yq_surcharge_usd), 2)
        return eligible, est_gov_tax

    return 0.0, 0.0


def evaluate_eu261_segment(
    origin_airport: AirportProfile,
    dest_airport: AirportProfile,
    operating_carrier: str,
) -> dict[str, object]:
    """
    Calculates static single-segment EU261 protection and compensation (€250, €400, or €600):
    - Departs an EU/EEA/CH airport (e.g. CDG->MEX on AM, or MAD->MEX on IB) -> Covered (€600).
    - Arrives into an EU/EEA/CH airport from outside the EU on an EU carrier (e.g. MEX->MAD on IB) -> Covered (€600).
    - Arrives into an EU/EEA/CH airport from outside the EU on a non-EU carrier (e.g. MEX->CDG on AM) -> Not Covered (€0).
    """
    _, dist_km = haversine_distance(
        origin_airport.latitude,
        origin_airport.longitude,
        dest_airport.latitude,
        dest_airport.longitude,
    )
    carrier = operating_carrier.upper()
    is_eligible = origin_airport.is_eu_eea_ch or (
        dest_airport.is_eu_eea_ch and carrier in EU_EEA_CH_CARRIERS
    )

    if dist_km <= 1500.0:
        comp_eur = 250 if is_eligible else 0
    elif dist_km <= 3500.0 or (origin_airport.is_eu_eea_ch and dest_airport.is_eu_eea_ch):
        comp_eur = 400 if is_eligible else 0
    else:
        comp_eur = 600 if is_eligible else 0

    return {
        "route": f"{origin_airport.iata_code}-{dest_airport.iata_code}",
        "operating_carrier": carrier,
        "distance_km": dist_km,
        "is_eligible": is_eligible,
        "compensation_eur": comp_eur,
    }


def simulate_flight_crediting(segments: list[FlightSegment]) -> list[CreditingSimulationResult]:
    """
    Simulates crediting paid flight segments across all programs in the operating airline's alliance:
    - For `CDG <-> MEX` on Aeroméxico (`AM`, SkyTeam): Compares `AM_RW`, `VS_FC`, and `AF_FB`.
    - For `MEX <-> MAD` on Iberia (`IB`, Oneworld): Compares `IB_PLUS`, `BA_EC`, `AA_ADV`, and `AS_ATMOS`.
    """
    if not segments:
        raise ValueError("At least one FlightSegment is required.")

    primary_carrier = segments[0].operating_carrier.upper()
    results: list[CreditingSimulationResult] = []

    for prog_code, program in LOYALTY_PROGRAMS.items():
        total_miles = 0
        total_status_pts = 0.0
        total_eligible_spend = 0.0
        total_gov_taxes = 0.0
        used_rev = False
        used_dist = False
        matched_any_rule = False

        for seg in segments:
            orig = AIRPORTS[seg.origin_iata.upper()]
            dest = AIRPORTS[seg.destination_iata.upper()]
            dist_mi, _ = haversine_distance(orig.latitude, orig.longitude, dest.latitude, dest.longitude)
            is_intercontinental = orig.region_zone != dest.region_zone

            rule = next(
                (
                    r
                    for r in PARTNER_EARNING_RULES
                    if r.program_code == prog_code
                    and r.operating_carrier == seg.operating_carrier.upper()
                    and r.booking_class == seg.booking_class.upper()
                ),
                None,
            )
            if rule is None:
                continue

            matched_any_rule = True
            eligible_spend, gov_tax = estimate_eligible_spend(
                orig,
                dest,
                seg.base_fare_usd,
                seg.yq_surcharge_usd,
                seg.total_ticket_price_usd,
                program.counts_yq_surcharge,
            )
            total_eligible_spend += eligible_spend
            total_gov_taxes += gov_tax

            ticketing_carrier = (seg.ticketing_carrier or seg.operating_carrier).upper()
            # Oneworld Transatlantic JV: IB_PLUS, BA_EC, and AA_ADV all credit IB-marketed flights by spend!
            oneworld_jv_group = {"IB", "BA", "AA"}
            is_revenue_eligible = (
                ticketing_carrier == program.home_carrier_iata
                or (prog_code in {"IB_PLUS", "BA_EC", "AA_ADV"} and ticketing_carrier in oneworld_jv_group)
            )

            if is_revenue_eligible and eligible_spend > 0 and program.own_ticket_revenue_multiplier is not None:
                if prog_code in {"IB_PLUS", "BA_EC"} and seg.operating_carrier.upper() == "IB":
                    # Official IB & BA Club rule: 5 base Avios/€ + 2 additional Avios/€ on Spain<->Mexico (= 7 Avios/€)
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
                # 2025/2026 British Airways Club spend-based Tier Points (1 TP per £1 GBP + sector cabin bonus)
                gbp_spend = eligible_spend / 1.27
                cabin_bonus = 400.0 if rule.cabin == CabinClass.BUSINESS else (275.0 if rule.cabin == CabinClass.PREMIUM_ECONOMY else 175.0)
                seg_status = round(gbp_spend + cabin_bonus, 1)
            elif prog_code == "AA_ADV" and is_revenue_eligible and eligible_spend > 0:
                # AAdvantage on IB: 5 Loyalty Points per $1 USD eligible spend
                seg_status = round(eligible_spend * 5.0, 1)
            elif prog_code == "AM_RW" and is_revenue_eligible and eligible_spend > 0:
                # Aeromexico Rewards: 8 Qualifying Points per $1 USD eligible spend
                seg_status = round(eligible_spend * 8.0, 1)
            elif rule.status_calc_method == "IB_ZONE_FIXED":
                seg_status = (
                    rule.intercontinental_status_points
                    if is_intercontinental
                    else rule.continental_status_points
                )
            else:
                seg_status = round(dist_mi * (rule.status_miles_pct / 100.0), 1)

            total_status_pts += seg_status

        if not matched_any_rule:
            continue

        progress_pct = round(min(100.0, (total_status_pts / program.gold_status_threshold) * 100.0), 1)

        short_unlocks: list[str] = []
        long_progress: list[str] = []
        for bm in AWARD_SWEET_SPOTS:
            if bm.booking_program_code != prog_code:
                continue
            if bm.category == "SHORT_HAUL_UNLOCK":
                if total_miles >= bm.miles_required_one_way:
                    count = total_miles // bm.miles_required_one_way
                    rem = total_miles % bm.miles_required_one_way
                    short_unlocks.append(f"✅ Unlocks {count}x {bm.description} ({bm.miles_required_one_way:,} req. + {rem:,} left)")
                else:
                    pct = round((total_miles / bm.miles_required_one_way) * 100.0, 1)
                    short_unlocks.append(f"❌ 0 flights unlocked — Only {pct}% ({total_miles:,} / {bm.miles_required_one_way:,}) toward {bm.description}")

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
                own_metal_warning=program.gold_status_tier_name,
                unlocked_short_haul_awards=short_unlocks,
                flagship_sweet_spot_progress=long_progress,
            )
        )

    results.sort(
        key=lambda r: (any(s.startswith("✅") for s in r.unlocked_short_haul_awards), r.redeemable_miles_earned, r.progress_to_gold_pct),
        reverse=True,
    )
    return results