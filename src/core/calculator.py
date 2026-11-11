"""
Pure-Python Calculation & Arbitrage Engine (`src/core/calculator.py`).

Implements:
1. Credit card transfer bonus & effective Cents-Per-Mile (CPM) arbitrage math.
2. Cross-alliance partner award discovery (with optional live bonus & cash fare overrides).
3. Geodesic Haversine distance (`mi` & `km`), government departure tax stripping, and static EU261 bands.
4. Multi-program flight crediting simulation ("Default to the Metal" vs. "Smart Alliance Switch"),
   explicitly preserving 0%-earning fare-class traps (e.g., Lufthansa 'P' class on Turkish Miles&Smiles)
   so users see the warning rather than having the row silently dropped.
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
EU_EEA_CH_CARRIERS = {"LH", "LX", "OS", "SN", "IB", "AF", "KL", "AY", "SK", "TP", "LO"}
UA_PREFERRED_PARTNERS = {"LH", "LX", "OS", "SN", "AC", "NH"}


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
    Example: base_ratio=1.0 with bonus_pct=30.0 -> 1.30 airline miles per 1 bank point.
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
    rounding up to the bank's required transfer increment (typically 1,000 points).
    """
    if award_miles_needed <= 0:
        return 0
    effective_ratio = apply_transfer_bonus(base_ratio, bonus_pct)
    raw_points = award_miles_needed / effective_ratio
    if min_increment <= 1:
        return math.ceil(raw_points)
    return int(math.ceil(raw_points / min_increment) * min_increment)


def calculate_effective_cpm(
    cash_fare_usd: float,
    taxes_and_yq_usd: float,
    points_or_miles_used: int,
) -> float:
    """
    Computes the realized Cents-Per-Mile / Cents-Per-Point (CPM/CPP) on a specific redemption:
        ((cash_fare_usd - taxes_and_yq_usd) * 100) / points_or_miles_used
    """
    if points_or_miles_used <= 0:
        raise ValueError("points_or_miles_used must be strictly positive.")
    net_value_usd = max(0.0, cash_fare_usd - taxes_and_yq_usd)
    return round((net_value_usd * 100.0) / points_or_miles_used, 2)


def find_best_transfer_pathways(
    origin_iata: str,
    destination_iata: str,
    cabin: CabinClass = CabinClass.BUSINESS,
    bank_code_filter: Optional[str] = None,
    override_bonus_pct: Optional[float] = None,
    override_cash_fare_usd: Optional[float] = None,
) -> list[TransferOptionResult]:
    """
    Evaluates all seeded `AwardSweetSpot` benchmarks for `(origin_iata, destination_iata, cabin)`
    and joins them against `TRANSFER_PARTNER_RULES` to rank which bank point transfer requires
    the fewest credit card points and yields the highest net cash savings.
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

            bonus_label = (
                f"Includes {effective_bonus:.0f}% transfer bonus ({eff_ratio}:1)."
                if effective_bonus > 0
                else f"Standard transfer ratio ({eff_ratio}:1)."
            )

            results.append(
                TransferOptionResult(
                    bank_code=bank.bank_code,
                    bank_currency_name=f"{bank.bank_name} {bank.currency_name}",
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
    Separates eligible loyalty spend (Base Fare + carrier-imposed YQ/YR) from mandatory
    government/airport departure taxes (such as Mexico's TUA or UK APD).
    Returns `(eligible_spend_usd, estimated_gov_taxes_stripped_usd)`.
    """
    if base_fare_usd is not None:
        eligible_yq = yq_surcharge_usd if counts_yq_surcharge else 0.0
        eligible = round(base_fare_usd + eligible_yq, 2)
        gov_taxes = (
            round(max(0.0, total_ticket_price_usd - base_fare_usd - yq_surcharge_usd), 2)
            if total_ticket_price_usd is not None
            else round(origin_airport.estimated_gov_departure_tax_usd + (dest_airport.estimated_gov_departure_tax_usd * 0.35), 2)
        )
        return eligible, gov_taxes

    if total_ticket_price_usd is not None and total_ticket_price_usd > 0:
        est_gov_tax = round(
            origin_airport.estimated_gov_departure_tax_usd
            + (dest_airport.estimated_gov_departure_tax_usd * 0.35),
            2,
        )
        est_gov_tax = min(est_gov_tax, round(total_ticket_price_usd * 0.35, 2))
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
    Calculates static single-segment EU261 protection and compensation (€250, €400, or €600).
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
    Simulates crediting a list of paid flight segments across all loyalty programs in the
    operating carrier's alliance, comparing 'Default to the Metal' against partner
    'Smart Alliance Switch' programs.
    """
    if not segments:
        raise ValueError("At least one FlightSegment is required.")

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
        zero_earning_trap_classes: list[str] = []

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
            if rule.award_miles_pct == 0.0 and rule.status_miles_pct == 0.0:
                zero_earning_trap_classes.append(f"{seg.operating_carrier.upper()} '{seg.booking_class.upper()}'")

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
            is_own_ticket = ticketing_carrier == program.home_carrier_iata

            if is_own_ticket and eligible_spend > 0 and program.own_ticket_revenue_multiplier is not None:
                seg_miles = int(round(eligible_spend * program.own_ticket_revenue_multiplier))
                used_rev = True
            else:
                raw_miles = dist_mi * (rule.award_miles_pct / 100.0)
                seg_miles = int(round(max(raw_miles, float(rule.min_award_miles)) if rule.award_miles_pct > 0 else 0.0))
                used_dist = True

            total_miles += seg_miles

            if rule.status_calc_method in ("MM_ZONE_FIXED", "IB_ZONE_FIXED"):
                seg_status = (
                    rule.intercontinental_status_points
                    if is_intercontinental
                    else rule.continental_status_points
                )
            elif rule.status_calc_method == "UA_PQP_PARTNER":
                if is_own_ticket and eligible_spend > 0:
                    seg_status = eligible_spend
                else:
                    divisor = 5.0 if seg.operating_carrier.upper() in UA_PREFERRED_PARTNERS else 6.0
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
        warning: Optional[str] = None
        if zero_earning_trap_classes:
            trap_str = ", ".join(sorted(set(zero_earning_trap_classes)))
            warning = f"⚠️ 0% Earning Trap: {trap_str} earns 0 miles and 0 status points in {program.program_name}!"
        elif program.own_metal_min_share_pct > 0 and total_status_pts > 0:
            share = (own_metal_status_pts / total_status_pts) * 100.0
            if share < program.own_metal_min_share_pct:
                warning = f"Requires {program.own_metal_min_share_pct:.0f}% status points on {program.home_carrier_iata} Group metal (currently {share:.1f}%)."
        elif program.own_metal_min_segments > 0 and own_metal_segs < program.own_metal_min_segments:
            warning = f"Requires {program.own_metal_min_segments} annual segments on {program.home_carrier_iata} metal (this itinerary has {own_metal_segs})."

        short_unlocks: list[str] = []
        long_progress: list[str] = []
        for bm in AWARD_SWEET_SPOTS:
            if bm.booking_program_code != prog_code:
                continue
            if bm.category == "SHORT_HAUL_UNLOCK" and total_miles >= bm.miles_required_one_way:
                count = total_miles // bm.miles_required_one_way
                rem = total_miles % bm.miles_required_one_way
                short_unlocks.append(f"Unlocks {count}x {bm.description} ({bm.miles_required_one_way:,} + {rem:,} left)")
            elif bm.category == "LONG_HAUL_SWEET_SPOT":
                pct = round(min(100.0, (total_miles / bm.miles_required_one_way) * 100.0), 1)
                long_progress.append(f"{pct}% toward {bm.description} ({bm.miles_required_one_way:,} required)")

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

    results.sort(key=lambda r: (r.progress_to_gold_pct, r.redeemable_miles_earned), reverse=True)
    return results