"""
Deterministic local reference dataset (`src/core/seed_data.py`).

Provides offline seed data for:
- Global airport profiles (coordinates, regional zones, EU261 status, and departure tax estimates).
- Major transferable bank currencies (Amex Membership Rewards, Chase Ultimate Rewards, Citi ThankYou, Capital One).
- Loyalty programs across Star Alliance (Lufthansa, United, Turkish, Aeroplan), Oneworld (Iberia, British Airways),
  and SkyTeam (Aeroméxico, Air France/KLM Flying Blue).
- Bank-to-airline transfer ratios (including promotional transfer bonuses).
- Cross-alliance award sweet spots and partner earning charts.
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
    "MEX": AirportProfile("MEX", "Benito Juárez International", "Mexico City", "MX", 19.4363, -99.0721, "NORTH_AMERICA", False, 65.0),
    "FRA": AirportProfile("FRA", "Frankfurt Airport", "Frankfurt", "DE", 50.0379, 8.5622, "EUROPE", True, 88.0),
    "MUC": AirportProfile("MUC", "Munich Airport", "Munich", "DE", 48.3538, 11.7861, "EUROPE", True, 82.0),
    "MAD": AirportProfile("MAD", "Adolfo Suárez Madrid–Barajas", "Madrid", "ES", 40.4983, -3.5676, "EUROPE", True, 42.0),
    "BCN": AirportProfile("BCN", "Josep Tarradellas Barcelona–El Prat", "Barcelona", "ES", 41.2974, 2.0833, "EUROPE", True, 38.0),
    "EWR": AirportProfile("EWR", "Newark Liberty International", "Newark", "US", 40.6895, -74.1745, "NORTH_AMERICA", False, 28.0),
    "IAH": AirportProfile("IAH", "George Bush Intercontinental", "Houston", "US", 29.9902, -95.3368, "NORTH_AMERICA", False, 28.0),
    "IST": AirportProfile("IST", "Istanbul Airport", "Istanbul", "TR", 41.2753, 28.7519, "EUROPE", False, 45.0),
    "YYZ": AirportProfile("YYZ", "Toronto Pearson International", "Toronto", "CA", 43.6777, -79.6248, "NORTH_AMERICA", False, 52.0),
    "LHR": AirportProfile("LHR", "Heathrow Airport", "London", "GB", 51.4700, -0.4543, "EUROPE", False, 115.0),
    "CDG": AirportProfile("CDG", "Charles de Gaulle Airport", "Paris", "FR", 49.0097, 2.5479, "EUROPE", True, 75.0),
}

BANK_CURRENCIES: dict[str, BankCurrency] = {
    "AMEX_MR": BankCurrency("AMEX_MR", "American Express", "Membership Rewards", 1.0),
    "CHASE_UR": BankCurrency("CHASE_UR", "Chase", "Ultimate Rewards", 1.25),
    "CITI_TYP": BankCurrency("CITI_TYP", "Citi", "ThankYou Points", 1.0),
    "CAP_ONE": BankCurrency("CAP_ONE", "Capital One", "Venture Miles", 1.0),
}

LOYALTY_PROGRAMS: dict[str, LoyaltyProgram] = {
    "LH_MM": LoyaltyProgram(
        program_code="LH_MM",
        program_name="Lufthansa Miles & More",
        home_carrier_iata="LH",
        alliance=Alliance.STAR_ALLIANCE,
        currency_name="Miles & More Miles",
        own_ticket_revenue_multiplier=4.0,
        counts_yq_surcharge=True,
        gold_status_tier_name="Senator (Star Alliance Gold)",
        gold_status_threshold=2000.0,
        own_metal_min_share_pct=50.0,
    ),
    "UA_MP": LoyaltyProgram(
        program_code="UA_MP",
        program_name="United MileagePlus",
        home_carrier_iata="UA",
        alliance=Alliance.STAR_ALLIANCE,
        currency_name="MileagePlus Miles",
        own_ticket_revenue_multiplier=5.0,
        counts_yq_surcharge=True,
        gold_status_tier_name="Premier Gold (Star Alliance Gold)",
        gold_status_threshold=10000.0,
        own_metal_min_segments=4,
    ),
    "TK_MS": LoyaltyProgram(
        program_code="TK_MS",
        program_name="Turkish Airlines Miles&Smiles",
        home_carrier_iata="TK",
        alliance=Alliance.STAR_ALLIANCE,
        currency_name="Miles&Smiles Miles",
        own_ticket_revenue_multiplier=None,
        counts_yq_surcharge=True,
        gold_status_tier_name="Elite (Star Alliance Gold)",
        gold_status_threshold=40000.0,
    ),
    "AC_AP": LoyaltyProgram(
        program_code="AC_AP",
        program_name="Air Canada Aeroplan",
        home_carrier_iata="AC",
        alliance=Alliance.STAR_ALLIANCE,
        currency_name="Aeroplan Points",
        own_ticket_revenue_multiplier=None,
        counts_yq_surcharge=True,
        gold_status_tier_name="Aeroplan 50K (Star Alliance Gold)",
        gold_status_threshold=50000.0,
    ),
    "IB_PLUS": LoyaltyProgram(
        program_code="IB_PLUS",
        program_name="Iberia Plus",
        home_carrier_iata="IB",
        alliance=Alliance.ONEWORLD,
        currency_name="Avios",
        own_ticket_revenue_multiplier=5.0,
        counts_yq_surcharge=True,
        gold_status_tier_name="Iberia Oro (Oneworld Sapphire)",
        gold_status_threshold=2250.0,
    ),
    "AM_RW": LoyaltyProgram(
        program_code="AM_RW",
        program_name="Aeroméxico Rewards",
        home_carrier_iata="AM",
        alliance=Alliance.SKYTEAM,
        currency_name="Aeroméxico Points",
        own_ticket_revenue_multiplier=8.0,
        counts_yq_surcharge=True,
        gold_status_tier_name="Gold (SkyTeam Elite Plus)",
        gold_status_threshold=80000.0,
    ),
}

TRANSFER_PARTNER_RULES: list[TransferPartnerRule] = [
    # Chase Ultimate Rewards
    TransferPartnerRule("CHASE_UR", "IB_PLUS", base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("CHASE_UR", "UA_MP", base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("CHASE_UR", "AC_AP", base_ratio=1.0, active_bonus_pct=20.0, min_transfer_increment=1000),
    # American Express Membership Rewards
    TransferPartnerRule("AMEX_MR", "IB_PLUS", base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MR", "AC_AP", base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("AMEX_MR", "AM_RW", base_ratio=1.6, active_bonus_pct=20.0, min_transfer_increment=1000),
    # Citi ThankYou Points
    TransferPartnerRule("CITI_TYP", "TK_MS", base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("CITI_TYP", "AM_RW", base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
    # Capital One Venture Miles
    TransferPartnerRule("CAP_ONE", "TK_MS", base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("CAP_ONE", "AC_AP", base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
    TransferPartnerRule("CAP_ONE", "IB_PLUS", base_ratio=1.0, active_bonus_pct=0.0, min_transfer_increment=1000),
]

AWARD_SWEET_SPOTS: list[AwardSweetSpot] = [
    # MEX-MAD corridor: Iberia Plus (Oneworld) vs Aeromexico Rewards (SkyTeam)
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
        description="Off-Peak European short-haul MAD-BCN Economy on Iberia",
    ),
    AwardSweetSpot(
        benchmark_code="IB_MEX_MAD_ECON",
        booking_program_code="IB_PLUS",
        operating_carrier_iata="IB",
        alliance=Alliance.ONEWORLD,
        origin_iata="MEX",
        destination_iata="MAD",
        cabin=CabinClass.ECONOMY,
        miles_required_one_way=20000,
        taxes_and_yq_usd=115.0,
        typical_cash_fare_one_way_usd=680.0,
        category="LONG_HAUL_SWEET_SPOT",
        description="Off-Peak MEX-MAD Economy on Iberia (20,000 Avios vs 75,000 AM points)",
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
        description="Off-Peak MEX-MAD Lie-Flat Business Class on Iberia",
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
        description="MEX-MAD Clase Premier Business Class on Aeroméxico",
    ),
    # Star Alliance MEX-FRA corridor: Aeroplan vs Turkish vs United vs Miles & More
    AwardSweetSpot(
        benchmark_code="AC_SHORT_HAUL_NA",
        booking_program_code="AC_AP",
        operating_carrier_iata="AC",
        alliance=Alliance.STAR_ALLIANCE,
        origin_iata="YYZ",
        destination_iata="EWR",
        cabin=CabinClass.ECONOMY,
        miles_required_one_way=6000,
        taxes_and_yq_usd=45.0,
        typical_cash_fare_one_way_usd=210.0,
        category="SHORT_HAUL_UNLOCK",
        description="Short-Haul North America (<500 mi) Economy via Air Canada Aeroplan",
    ),
    AwardSweetSpot(
        benchmark_code="AC_MEX_FRA_LH_BIZ",
        booking_program_code="AC_AP",
        operating_carrier_iata="LH",
        alliance=Alliance.STAR_ALLIANCE,
        origin_iata="MEX",
        destination_iata="FRA",
        cabin=CabinClass.BUSINESS,
        miles_required_one_way=70000,
        taxes_and_yq_usd=75.0,
        typical_cash_fare_one_way_usd=2850.0,
        category="LONG_HAUL_SWEET_SPOT",
        description="Lufthansa Business Class MEX-FRA booked via Aeroplan (eliminates ~$500 LH YQ surcharge)",
    ),
    AwardSweetSpot(
        benchmark_code="TK_MEX_FRA_LH_BIZ",
        booking_program_code="TK_MS",
        operating_carrier_iata="LH",
        alliance=Alliance.STAR_ALLIANCE,
        origin_iata="MEX",
        destination_iata="FRA",
        cabin=CabinClass.BUSINESS,
        miles_required_one_way=65000,
        taxes_and_yq_usd=290.0,
        typical_cash_fare_one_way_usd=2850.0,
        category="LONG_HAUL_SWEET_SPOT",
        description="Lufthansa Business Class MEX-FRA booked via Turkish Miles&Smiles partner chart",
    ),
    AwardSweetSpot(
        benchmark_code="UA_MEX_FRA_LH_BIZ",
        booking_program_code="UA_MP",
        operating_carrier_iata="LH",
        alliance=Alliance.STAR_ALLIANCE,
        origin_iata="MEX",
        destination_iata="FRA",
        cabin=CabinClass.BUSINESS,
        miles_required_one_way=88000,
        taxes_and_yq_usd=45.0,
        typical_cash_fare_one_way_usd=2850.0,
        category="LONG_HAUL_SWEET_SPOT",
        description="Lufthansa Business Class MEX-FRA booked via United MileagePlus (zero YQ)",
    ),
]

PARTNER_EARNING_RULES: list[PartnerEarningRule] = [
    # Lufthansa operating ("LH") credited across Star Alliance programs
    PartnerEarningRule("LH_MM", "LH", "K", CabinClass.ECONOMY, 50.0, 250, "MM_ZONE_FIXED", 50.0, 20.0, 60.0),
    PartnerEarningRule("LH_MM", "LH", "P", CabinClass.BUSINESS, 100.0, 500, "MM_ZONE_FIXED", 100.0, 40.0, 200.0),
    PartnerEarningRule("LH_MM", "LH", "I", CabinClass.BUSINESS, 125.0, 500, "MM_ZONE_FIXED", 125.0, 40.0, 200.0),
    PartnerEarningRule("UA_MP", "LH", "K", CabinClass.ECONOMY, 50.0, 250, "UA_PQP_PARTNER", 50.0),
    PartnerEarningRule("UA_MP", "LH", "P", CabinClass.BUSINESS, 100.0, 500, "UA_PQP_PARTNER", 100.0),
    PartnerEarningRule("UA_MP", "LH", "I", CabinClass.BUSINESS, 125.0, 500, "UA_PQP_PARTNER", 125.0),
    # Note: LH discounted Business 'P' earns 0% in Turkish Miles&Smiles, whereas 'I' earns 125%!
    PartnerEarningRule("TK_MS", "LH", "K", CabinClass.ECONOMY, 50.0, 250, "DISTANCE_PCT", 50.0),
    PartnerEarningRule("TK_MS", "LH", "P", CabinClass.BUSINESS, 0.0, 0, "DISTANCE_PCT", 0.0),
    PartnerEarningRule("TK_MS", "LH", "I", CabinClass.BUSINESS, 125.0, 500, "DISTANCE_PCT", 125.0),
    PartnerEarningRule("AC_AP", "LH", "K", CabinClass.ECONOMY, 50.0, 250, "DISTANCE_PCT", 50.0),
    PartnerEarningRule("AC_AP", "LH", "P", CabinClass.BUSINESS, 100.0, 500, "DISTANCE_PCT", 100.0),
    PartnerEarningRule("AC_AP", "LH", "I", CabinClass.BUSINESS, 125.0, 500, "DISTANCE_PCT", 125.0),
    # Iberia ("IB") & Aeromexico ("AM")
    PartnerEarningRule("IB_PLUS", "IB", "I", CabinClass.BUSINESS, 125.0, 500, "IB_ZONE_FIXED", 125.0, 125.0, 500.0),
    PartnerEarningRule("AM_RW", "AM", "I", CabinClass.BUSINESS, 150.0, 500, "DISTANCE_PCT", 150.0),
]
