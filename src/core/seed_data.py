"""
Verified Reference Dataset (`src/core/seed_data.py`).

Focused strictly on two real-world Mexican loyalty arbitrage cases:
1. Paid Flight Crediting (`CDG <-> MEX` on Aeroméxico & `MEX <-> MAD` on Iberia):
   - Aeroméxico (`CDG <-> MEX`, SkyTeam): Crediting a cheap round-trip Europe flight to Aeroméxico Rewards
     (`AM_RW`, revenue-based 8 pts/$1 USD) doesn't even earn enough for a 10,000-point domestic flight in Mexico,
     whereas crediting that exact same flight to Virgin Atlantic Flying Club (`VS_FC`, distance-based) earns
     enough Virgin Points to immediately unlock a 6,000-point Economy (or 10,000-pt Premium W) promo flight
     from Cancún to London (`CUN -> LHR`)!
   - Iberia (`MEX <-> MAD`, Oneworld): Crediting a cheap Iberia ticket to Iberia Club (`IB_PLUS`) or
     The British Airways Club (`BA_EC`) is spend-based (leaving you under 4,500 Avios on cheap fares),
     whereas crediting to Alaska Airlines Atmos Rewards (`AS_ATMOS`, distance-based) earns 5,634+ points,
     immediately unlocking a 4,500-point or 7,000-point Oneworld reward flight!
2. Mexican Credit Card Point Transfers (`Santander Unique 1:1`, `BBVA 2.6:1 / 1.6:1`, `Amex México 1:1`):
   - Santander Unique Rewards (`SANTANDER_MX`): 1 Unique Point = 1 Avios in Iberia Club (`IB_PLUS` only).
   - BBVA México (`BBVA_MX` — Puntos BBVA): 2.6 Puntos BBVA = 1 Avios in Iberia Club (`IB_PLUS`, min 130 pts)
     and 1.6 Puntos BBVA = 1 Punto Aeroméxico Rewards (`AM_RW`, min 1,000 pts).
   - American Express México (`AMEX_MX` — Membership Rewards): 1:1 to Iberia Club (`IB_PLUS`),
     The British Airways Club (`BA_EC`), Air France/KLM Flying Blue (`AF_FB`), and Aeroméxico Rewards (`AM_RW`).
"""

from src.core.models import (
    AirportProfile,
    Alliance,
    AwardSweetSpot,
    BankCurrency,
    CabinClass,
    LoyaltyProgram,
    PartnerEarningRule,
    TransferPartnerRule,
)

AIRPORTS: dict[str, AirportProfile] = {
    "MEX": AirportProfile(
        iata_code="MEX",
        name="Benito Juárez International (AICM)",
        city="Mexico City",
        country_code="MX",
        latitude=19.4363,
        longitude=-99.0721,
        region_zone="NORTH_AMERICA",
        is_eu_eea_ch=False,
        estimated_gov_departure_tax_usd=65.0,  # Mexican AICM TUA (~$65 USD)
    ),
    "CUN": AirportProfile(
        iata_code="CUN",
        name="Cancún International",
        city="Cancún",
        country_code="MX",
        latitude=21.0365,
        longitude=-86.8771,
        region_zone="NORTH_AMERICA",
        is_eu_eea_ch=False,
        estimated_gov_departure_tax_usd=58.0,  # Mexican CUN TUA (~$58 USD)
    ),
    "MAD": AirportProfile(
        iata_code="MAD",
        name="Adolfo Suárez Madrid–Barajas",
        city="Madrid",
        country_code="ES",
        latitude=40.4983,
        longitude=-3.5676,
        region_zone="EUROPE",
        is_eu_eea_ch=True,
        estimated_gov_departure_tax_usd=42.0,  # Spanish AENA departure tax (~$42 USD)
    ),
    "CDG": AirportProfile(
        iata_code="CDG",
        name="Charles de Gaulle Airport",
        city="Paris",
        country_code="FR",
        latitude=49.0097,
        longitude=2.5479,
        region_zone="EUROPE",
        is_eu_eea_ch=True,
        estimated_gov_departure_tax_usd=75.0,  # French civil aviation & solidarity tax (~$75 USD)
    ),
    "LHR": AirportProfile(
        iata_code="LHR",
        name="Heathrow Airport",
        city="London",
        country_code="GB",
        latitude=51.4700,
        longitude=-0.4543,
        region_zone="EUROPE",
        is_eu_eea_ch=False,
        estimated_gov_departure_tax_usd=115.0,
    ),
    "BCN": AirportProfile(
        iata_code="BCN",
        name="Josep Tarradellas Barcelona–El Prat",
        city="Barcelona",
        country_code="ES",
        latitude=41.2974,
        longitude=2.0833,
        region_zone="EUROPE",
        is_eu_eea_ch=True,
        estimated_gov_departure_tax_usd=38.0,
    ),
}

BANK_CURRENCIES: dict[str, BankCurrency] = {
    "SANTANDER_MX": BankCurrency("SANTANDER_MX", "Santander México", "Unique Rewards", 0.50),
    "BBVA_MX": BankCurrency("BBVA_MX", "BBVA México", "Puntos BBVA", 0.55),
    "AMEX_MX": BankCurrency("AMEX_MX", "American Express México", "Membership Rewards", 0.75),
}

LOYALTY_PROGRAMS: dict[str, LoyaltyProgram] = {
    # --- SKYTEAM (For CDG <-> MEX on Aeroméxico) ---
    "AM_RW": LoyaltyProgram(
        program_code="AM_RW",
        program_name="Aeroméxico Rewards",
        home_carrier_iata="AM",
        alliance=Alliance.SKYTEAM,
        currency_name="Puntos Aeroméxico Rewards",
        own_ticket_revenue_multiplier=8.0,  # 8 Puntos per $1 USD (Base Fare + YQ)
        counts_yq_surcharge=True,
        gold_status_tier_name="Aeroméxico Gold (SkyTeam Elite Plus)",
        gold_status_threshold=80000.0,
    ),
    "VS_FC": LoyaltyProgram(
        program_code="VS_FC",
        program_name="Virgin Atlantic Flying Club",
        home_carrier_iata="VS",
        alliance=Alliance.SKYTEAM,
        currency_name="Virgin Points",
        own_ticket_revenue_multiplier=None,  # Distance-based on partner Aeroméxico flights
        counts_yq_surcharge=True,
        gold_status_tier_name="Flying Club Gold (SkyTeam Elite Plus)",
        gold_status_threshold=1000.0,  # 1,000 Tier Points for Gold (SkyTeam Elite Plus)
    ),
    "AF_FB": LoyaltyProgram(
        program_code="AF_FB",
        program_name="Air France / KLM Flying Blue",
        home_carrier_iata="AF",
        alliance=Alliance.SKYTEAM,
        currency_name="Flying Blue Miles",
        own_ticket_revenue_multiplier=4.0,
        counts_yq_surcharge=True,
        gold_status_tier_name="Flying Blue Gold (SkyTeam Elite Plus)",
        gold_status_threshold=180.0,
    ),
    # --- ONEWORLD (For MEX <-> MAD on Iberia) ---
    "IB_PLUS": LoyaltyProgram(
        program_code="IB_PLUS",
        program_name="Iberia Club (Avios)",
        home_carrier_iata="IB",
        alliance=Alliance.ONEWORLD,
        currency_name="Avios",
        own_ticket_revenue_multiplier=6.4815,  # 7 Avios per €1 EUR on Spain-Mexico (5 base + 2 bonus)
        counts_yq_surcharge=True,
        gold_status_tier_name="Iberia Oro (Oneworld Sapphire)",
        gold_status_threshold=2250.0,
    ),
    "BA_EC": LoyaltyProgram(
        program_code="BA_EC",
        program_name="The British Airways Club (Avios)",
        home_carrier_iata="BA",
        alliance=Alliance.ONEWORLD,
        currency_name="Avios",
        own_ticket_revenue_multiplier=6.4815,  # Also 7 Avios per €1 EUR on IB-marketed Spain-Mexico flights!
        counts_yq_surcharge=True,
        gold_status_tier_name="British Airways Silver (Oneworld Sapphire)",
        gold_status_threshold=7500.0,  # Spend-based Tier Points threshold for Silver
    ),
    "AA_ADV": LoyaltyProgram(
        program_code="AA_ADV",
        program_name="American Airlines AAdvantage",
        home_carrier_iata="AA",
        alliance=Alliance.ONEWORLD,
        currency_name="AAdvantage Miles",
        own_ticket_revenue_multiplier=5.0,  # Spend-based (5x per $1 USD) on IB-marketed flights!
        counts_yq_surcharge=True,
        gold_status_tier_name="AAdvantage Platinum (Oneworld Sapphire)",
        gold_status_threshold=75000.0,
    ),
    "AS_ATMOS": LoyaltyProgram(
        program_code="AS_ATMOS",
        program_name="Alaska Airlines Atmos Rewards",
        home_carrier_iata="AS",
        alliance=Alliance.ONEWORLD,
        currency_name="Atmos Points",
        own_ticket_revenue_multiplier=None,  # Distance-based on partner Iberia flights!
        counts_yq_surcharge=True,
        gold_status_tier_name="Atmos Gold (Oneworld Sapphire)",
        gold_status_threshold=40000.0,
    ),
}

# Strictly verified Mexican Credit Card transfer rules (Zero invented partners!)
TRANSFER_PARTNER_RULES: list[TransferPartnerRule] = [
    # 1. Santander Unique Rewards: ONLY transfers to Iberia Club at 1:1 (1 Unique Point = 1 Avios)
    TransferPartnerRule("SANTANDER_MX", "IB_PLUS", base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),

    # 2. BBVA México (Puntos BBVA):
    #    - Iberia Club: 2.6 Puntos BBVA = 1 Avios (base_ratio = 1 / 2.6 = 0.384615), min 130 Puntos BBVA (= 50 Avios)
    #    - Aeroméxico Rewards: 1.6 Puntos BBVA = 1 Punto Aeroméxico (base_ratio = 0.625), min 1,000 Puntos BBVA
    TransferPartnerRule("BBVA_MX", "IB_PLUS", base_ratio=50.0 / 130.0, active_bonus_pct=0.0, min_transfer_increment=130),
    TransferPartnerRule("BBVA_MX", "AM_RW",   base_ratio=0.625000, active_bonus_pct=0.0, min_transfer_increment=1000),

    # 3. American Express México (Membership Rewards):
    #    - 1:1 to Iberia Club, The British Airways Club, Air France/KLM Flying Blue, and Aeroméxico Rewards
    TransferPartnerRule("AMEX_MX", "IB_PLUS", base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MX", "BA_EC",   base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MX", "AF_FB",   base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MX", "AM_RW",   base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
]

AWARD_SWEET_SPOTS: list[AwardSweetSpot] = [
    # =========================================================================
    # 1. Tab 2 Benchmarks: MEX -> MAD (Transferring Santander, BBVA, Amex MX)
    # =========================================================================
    AwardSweetSpot(
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
        description="MEX-MAD Nonstop Economy on Iberia (21,000 Avios full, or less with Avios & Money; flexible changes/refunds)",
    ),
    AwardSweetSpot(
        benchmark_code="IB_MEX_MAD_BIZ",
        booking_program_code="IB_PLUS",
        operating_carrier_iata="IB",
        alliance=Alliance.ONEWORLD,
        origin_iata="MEX",
        destination_iata="MAD",
        cabin=CabinClass.BUSINESS,
        miles_required_one_way=40500,
        taxes_and_yq_usd=195.0,
        typical_cash_fare_one_way_usd=2450.0,
        category="LONG_HAUL_SWEET_SPOT",
        description="MEX-MAD Nonstop Lie-Flat Business Class on Iberia (40,500 Avios Off-Peak)",
    ),
    AwardSweetSpot(
        benchmark_code="BA_MEX_MAD_ECON",
        booking_program_code="BA_EC",
        operating_carrier_iata="IB",
        alliance=Alliance.ONEWORLD,
        origin_iata="MEX",
        destination_iata="MAD",
        cabin=CabinClass.ECONOMY,
        miles_required_one_way=21000,
        taxes_and_yq_usd=115.0,
        typical_cash_fare_one_way_usd=680.0,
        category="LONG_HAUL_SWEET_SPOT",
        description="MEX-MAD Iberia Economy via British Airways Avios (combines 1:1 with Iberia Club)",
    ),
    AwardSweetSpot(
        benchmark_code="BA_MEX_MAD_BIZ",
        booking_program_code="BA_EC",
        operating_carrier_iata="IB",
        alliance=Alliance.ONEWORLD,
        origin_iata="MEX",
        destination_iata="MAD",
        cabin=CabinClass.BUSINESS,
        miles_required_one_way=40500,
        taxes_and_yq_usd=195.0,
        typical_cash_fare_one_way_usd=2450.0,
        category="LONG_HAUL_SWEET_SPOT",
        description="MEX-MAD Iberia Business Class via British Airways Avios (combines 1:1 with Iberia Club)",
    ),
    AwardSweetSpot(
        benchmark_code="AF_MEX_MAD_ECON",
        booking_program_code="AF_FB",
        operating_carrier_iata="AM",
        alliance=Alliance.SKYTEAM,
        origin_iata="MEX",
        destination_iata="MAD",
        cabin=CabinClass.ECONOMY,
        miles_required_one_way=28000,
        taxes_and_yq_usd=140.0,
        typical_cash_fare_one_way_usd=680.0,
        category="LONG_HAUL_SWEET_SPOT",
        description="MEX-MAD Economy booked via Air France/KLM Flying Blue",
    ),
    AwardSweetSpot(
        benchmark_code="AF_MEX_MAD_BIZ",
        booking_program_code="AF_FB",
        operating_carrier_iata="AM",
        alliance=Alliance.SKYTEAM,
        origin_iata="MEX",
        destination_iata="MAD",
        cabin=CabinClass.BUSINESS,
        miles_required_one_way=70000,
        taxes_and_yq_usd=220.0,
        typical_cash_fare_one_way_usd=2450.0,
        category="LONG_HAUL_SWEET_SPOT",
        description="MEX-MAD Business Class booked via Air France/KLM Flying Blue",
    ),
    AwardSweetSpot(
        benchmark_code="AM_MEX_MAD_ECON",
        booking_program_code="AM_RW",
        operating_carrier_iata="AM",
        alliance=Alliance.SKYTEAM,
        origin_iata="MEX",
        destination_iata="MAD",
        cabin=CabinClass.ECONOMY,
        miles_required_one_way=75000,
        taxes_and_yq_usd=180.0,
        typical_cash_fare_one_way_usd=680.0,
        category="LONG_HAUL_SWEET_SPOT",
        description="MEX-MAD Economy via Aeroméxico Rewards (45,000+ pts vs. 21,000 Avios on Iberia)",
    ),
    AwardSweetSpot(
        benchmark_code="AM_MEX_MAD_BIZ",
        booking_program_code="AM_RW",
        operating_carrier_iata="AM",
        alliance=Alliance.SKYTEAM,
        origin_iata="MEX",
        destination_iata="MAD",
        cabin=CabinClass.BUSINESS,
        miles_required_one_way=145000,
        taxes_and_yq_usd=260.0,
        typical_cash_fare_one_way_usd=2450.0,
        category="LONG_HAUL_SWEET_SPOT",
        description="MEX-MAD Clase Premier via Aeroméxico Rewards (95,000+ pts vs. 40,500 Avios on Iberia)",
    ),

    # =========================================================================
    # 2. Tab 3 Immediate Flight Unlock Benchmarks (What Earned Flight Miles Unlock!)
    # =========================================================================
    # A. Aeroméxico Rewards: Lowest domestic national flight in Mexico = 10,000 points!
    AwardSweetSpot(
        benchmark_code="AM_NATIONAL_MEXICO_ECON",
        booking_program_code="AM_RW",
        operating_carrier_iata="AM",
        alliance=Alliance.SKYTEAM,
        origin_iata="MEX",
        destination_iata="CUN",
        cabin=CabinClass.ECONOMY,
        miles_required_one_way=10000,
        taxes_and_yq_usd=65.0,
        typical_cash_fare_one_way_usd=150.0,
        category="SHORT_HAUL_UNLOCK",
        description="Lowest National Flight in Mexico on Aeroméxico (10,000 Puntos AM)",
    ),
    # B. Virgin Atlantic Flying Club:
    #    - 6,000 VS Points: Off-Peak Promo / Saver CUN -> LHR (Cancún to Europe!) in Economy
    #    - 10,000 VS Points: Off-Peak Promo / Saver CUN -> LHR in Premium Economy (W)!
    #    - 15,000 VS Points: MEX -> Europe on Air France / KLM metal
    AwardSweetSpot(
        benchmark_code="VS_CUN_LHR_PROMO_ECON",
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
        description="Off-Peak Promo CUN->LHR (Cancún to Europe!) Economy on Virgin Atlantic (6,000 VS Points)",
    ),
    AwardSweetSpot(
        benchmark_code="VS_CUN_LHR_PROMO_PREM_W",
        booking_program_code="VS_FC",
        operating_carrier_iata="VS",
        alliance=Alliance.SKYTEAM,
        origin_iata="CUN",
        destination_iata="LHR",
        cabin=CabinClass.PREMIUM_ECONOMY,
        miles_required_one_way=10000,
        taxes_and_yq_usd=245.0,
        typical_cash_fare_one_way_usd=1050.0,
        category="SHORT_HAUL_UNLOCK",
        description="Off-Peak Promo CUN->LHR (Cancún to Europe!) Premium Economy (W) on Virgin Atlantic (10,000 VS Points)",
    ),
    AwardSweetSpot(
        benchmark_code="VS_MEX_EU_AF_KL_ECON",
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
        description="MEX->Europe Economy on Air France / KLM metal via Virgin Atlantic (15,000 VS Points)",
    ),
    # C. Air France / KLM Flying Blue: Domestic/Short-haul SkyTeam partner flight = 7,500 miles
    AwardSweetSpot(
        benchmark_code="AF_SHORT_HAUL_PARTNER",
        booking_program_code="AF_FB",
        operating_carrier_iata="AM",
        alliance=Alliance.SKYTEAM,
        origin_iata="MEX",
        destination_iata="CUN",
        cabin=CabinClass.ECONOMY,
        miles_required_one_way=7500,
        taxes_and_yq_usd=65.0,
        typical_cash_fare_one_way_usd=150.0,
        category="SHORT_HAUL_UNLOCK",
        description="Domestic Mexico Flight on Aeroméxico via Flying Blue (7,500 Miles)",
    ),
    # D. Alaska Airlines Atmos Rewards: 4,500-point and 7,000-point Oneworld reward flights!
    AwardSweetSpot(
        benchmark_code="AS_4500_REWARD_FLIGHT",
        booking_program_code="AS_ATMOS",
        operating_carrier_iata="AA",
        alliance=Alliance.ONEWORLD,
        origin_iata="MAD",
        destination_iata="BCN",
        cabin=CabinClass.ECONOMY,
        miles_required_one_way=4500,
        taxes_and_yq_usd=28.0,
        typical_cash_fare_one_way_usd=140.0,
        category="SHORT_HAUL_UNLOCK",
        description="Oneworld Short-Haul Reward Flight via Alaska Atmos (4,500 Atmos Points)",
    ),
    AwardSweetSpot(
        benchmark_code="AS_7000_REWARD_FLIGHT",
        booking_program_code="AS_ATMOS",
        operating_carrier_iata="AA",
        alliance=Alliance.ONEWORLD,
        origin_iata="MEX",
        destination_iata="CUN",
        cabin=CabinClass.ECONOMY,
        miles_required_one_way=7000,
        taxes_and_yq_usd=45.0,
        typical_cash_fare_one_way_usd=210.0,
        category="SHORT_HAUL_UNLOCK",
        description="Oneworld Medium-Haul Reward Flight via Alaska Atmos (7,000 Atmos Points)",
    ),
    # E. Iberia Club / British Airways / AAdvantage short-haul unlock targets:
    AwardSweetSpot(
        benchmark_code="IB_MAD_BCN_SHORTHAUL",
        booking_program_code="IB_PLUS",
        operating_carrier_iata="IB",
        alliance=Alliance.ONEWORLD,
        origin_iata="MAD",
        destination_iata="BCN",
        cabin=CabinClass.ECONOMY,
        miles_required_one_way=4500,
        taxes_and_yq_usd=28.0,
        typical_cash_fare_one_way_usd=140.0,
        category="SHORT_HAUL_UNLOCK",
        description="European Short-Haul MAD-BCN Economy on Iberia (4,500 Avios)",
    ),
    AwardSweetSpot(
        benchmark_code="BA_MAD_BCN_SHORTHAUL",
        booking_program_code="BA_EC",
        operating_carrier_iata="IB",
        alliance=Alliance.ONEWORLD,
        origin_iata="MAD",
        destination_iata="BCN",
        cabin=CabinClass.ECONOMY,
        miles_required_one_way=4750,
        taxes_and_yq_usd=28.0,
        typical_cash_fare_one_way_usd=140.0,
        category="SHORT_HAUL_UNLOCK",
        description="European Short-Haul MAD-BCN Economy via British Airways Avios (4,750 Avios)",
    ),
    AwardSweetSpot(
        benchmark_code="AA_SHORT_HAUL_REWARD",
        booking_program_code="AA_ADV",
        operating_carrier_iata="AA",
        alliance=Alliance.ONEWORLD,
        origin_iata="MEX",
        destination_iata="CUN",
        cabin=CabinClass.ECONOMY,
        miles_required_one_way=7500,
        taxes_and_yq_usd=45.0,
        typical_cash_fare_one_way_usd=190.0,
        category="SHORT_HAUL_UNLOCK",
        description="Oneworld Short-Haul Economy via AAdvantage (7,500 Miles)",
    ),
]

PARTNER_EARNING_RULES: list[PartnerEarningRule] = [
    # =========================================================================
    # ROUTE 1: Operating Carrier = Aeroméxico ("AM" — SkyTeam, CDG <-> MEX)
    # =========================================================================
    PartnerEarningRule("AM_RW", "AM", "V", CabinClass.ECONOMY,          25.0, 250, "DISTANCE_PCT",  25.0),
    PartnerEarningRule("AM_RW", "AM", "K", CabinClass.ECONOMY,          75.0, 250, "DISTANCE_PCT",  75.0),
    PartnerEarningRule("AM_RW", "AM", "Y", CabinClass.ECONOMY,         100.0, 500, "DISTANCE_PCT", 100.0),
    PartnerEarningRule("AM_RW", "AM", "W", CabinClass.PREMIUM_ECONOMY, 125.0, 500, "DISTANCE_PCT", 125.0),
    PartnerEarningRule("AM_RW", "AM", "I", CabinClass.BUSINESS,        150.0, 500, "DISTANCE_PCT", 150.0),
    PartnerEarningRule("AM_RW", "AM", "J", CabinClass.BUSINESS,        200.0, 1000, "DISTANCE_PCT", 200.0),

    # Virgin Atlantic Flying Club ("VS_FC") on Aeroméxico ("AM")
    PartnerEarningRule("VS_FC", "AM", "V", CabinClass.ECONOMY,          25.0, 250, "IB_ZONE_FIXED",  25.0, 10.0,  25.0),
    PartnerEarningRule("VS_FC", "AM", "K", CabinClass.ECONOMY,          75.0, 250, "IB_ZONE_FIXED",  75.0, 20.0,  50.0),
    PartnerEarningRule("VS_FC", "AM", "Y", CabinClass.ECONOMY,         150.0, 500, "IB_ZONE_FIXED", 150.0, 30.0,  75.0),
    PartnerEarningRule("VS_FC", "AM", "W", CabinClass.PREMIUM_ECONOMY, 150.0, 500, "IB_ZONE_FIXED", 150.0, 20.0,  50.0),
    PartnerEarningRule("VS_FC", "AM", "I", CabinClass.BUSINESS,        150.0, 500, "IB_ZONE_FIXED", 150.0, 40.0, 200.0),
    PartnerEarningRule("VS_FC", "AM", "J", CabinClass.BUSINESS,        250.0, 1000, "IB_ZONE_FIXED", 250.0, 40.0, 200.0),

    # Air France / KLM Flying Blue ("AF_FB") on Aeroméxico ("AM")
    PartnerEarningRule("AF_FB", "AM", "V", CabinClass.ECONOMY,          25.0, 250, "IB_ZONE_FIXED",  25.0,  5.0, 12.0),
    PartnerEarningRule("AF_FB", "AM", "K", CabinClass.ECONOMY,          50.0, 250, "IB_ZONE_FIXED",  50.0,  5.0, 12.0),
    PartnerEarningRule("AF_FB", "AM", "Y", CabinClass.ECONOMY,         100.0, 500, "IB_ZONE_FIXED", 100.0,  5.0, 12.0),
    PartnerEarningRule("AF_FB", "AM", "W", CabinClass.PREMIUM_ECONOMY, 100.0, 500, "IB_ZONE_FIXED", 100.0, 10.0, 24.0),
    PartnerEarningRule("AF_FB", "AM", "I", CabinClass.BUSINESS,        150.0, 500, "IB_ZONE_FIXED", 150.0, 15.0, 36.0),
    PartnerEarningRule("AF_FB", "AM", "J", CabinClass.BUSINESS,        200.0, 1000, "IB_ZONE_FIXED", 200.0, 15.0, 36.0),

    # =========================================================================
    # ROUTE 2: Operating Carrier = Iberia ("IB" — Oneworld, MEX <-> MAD)
    # =========================================================================
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