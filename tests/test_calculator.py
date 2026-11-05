"""
Unit and Integration Test Suite (`tests/test_calculator.py`).

Contains:
- Working, deterministic unit tests for the Phase 1 pure-Python `src.core` engine
  (transfer bonus math, effective CPM, cross-alliance award arbitrage, tax stripping,
  EU261 static bands, and multi-program flight crediting).
- `# TODO` test stubs for Phase 2 FastAPI endpoints, PostgreSQL repository queries,
  and AWS Lambda event handlers.
"""

import unittest

try:
    import pytest
except ImportError:  # Allows running via standard library  before installing pytest
    class _PytestStub:
        class mark:
            @staticmethod
            def skip(reason: str = ""):
                return unittest.skip(reason)
    pytest = _PytestStub()  # type: ignore[assignment]

from src.core.calculator import (
    apply_transfer_bonus,
    calculate_effective_cpm,
    calculate_required_bank_points,
    estimate_eligible_spend,
    evaluate_eu261_segment,
    find_best_transfer_pathways,
    haversine_distance,
    simulate_flight_crediting,
)
from src.core.models import CabinClass, FlightSegment
from src.core.seed_data import AIRPORTS


class TestCoreLoyaltyArbitrageEngine(unittest.TestCase):
    """Working unit tests for `src.core` (runs offline with zero external dependencies)."""

    def test_transfer_bonus_and_cpm_math(self) -> None:
        """Verifies bank transfer bonus multiplier, 1,000-point rounding, and effective CPP."""
        # 30% Chase -> Iberia Avios bonus turns 1.0 base ratio into 1.30
        eff_ratio = apply_transfer_bonus(base_ratio=1.0, bonus_pct=30.0)
        self.assertEqual(eff_ratio, 1.3)

        # 40,500 Avios for MEX-MAD Business Class with a 30% bonus requires 31,154 raw -> 32,000 Chase UR points
        pts_needed = calculate_required_bank_points(
            award_miles_needed=40500,
            base_ratio=1.0,
            bonus_pct=30.0,
            min_increment=1000,
        )
        self.assertEqual(pts_needed, 32000)

        # $2,450 cash fare - $195 taxes = $2,255 net value across 32,000 bank points -> 7.05 cents/point
        cpp = calculate_effective_cpm(
            cash_fare_usd=2450.0,
            taxes_and_yq_usd=195.0,
            points_or_miles_used=pts_needed,
        )
        self.assertEqual(cpp, 7.05)

    def test_cross_alliance_transfer_arbitrage_mex_mad_and_mex_fra(self) -> None:
        """
        Verifies that the engine identifies:
        1. Chase UR -> Iberia Plus (with 30% bonus = 32,000 pts) as the #1 pathway for MEX-MAD Business,
           beating Amex MR -> Aeroméxico Rewards (76,000 pts).
        2. Chase UR -> Air Canada Aeroplan (with 20% bonus = 59,000 pts) as the #1 pathway for MEX-FRA Business.
        """
        mex_mad_options = find_best_transfer_pathways("MEX", "MAD", cabin=CabinClass.BUSINESS)
        self.assertGreaterEqual(len(mex_mad_options), 4)

        best_mex_mad = mex_mad_options[0]
        self.assertEqual(best_mex_mad.bank_code, "CHASE_UR")
        self.assertEqual(best_mex_mad.booking_program_code, "IB_PLUS")
        self.assertEqual(best_mex_mad.bank_points_required, 32000)
        self.assertTrue(best_mex_mad.beats_cashout_baseline)

        mex_fra_options = find_best_transfer_pathways("MEX", "FRA", cabin=CabinClass.BUSINESS)
        self.assertGreaterEqual(len(mex_fra_options), 3)
        best_mex_fra = mex_fra_options[0]
        self.assertEqual(best_mex_fra.bank_code, "CHASE_UR")
        self.assertEqual(best_mex_fra.booking_program_code, "AC_AP")
        self.assertEqual(best_mex_fra.bank_points_required, 59000)

    def test_flight_crediting_tax_stripping_and_eu261(self) -> None:
        """
        Verifies paid flight crediting simulation on MEX-FRA-MEX in Business Class ('I'),
        automatic government tax stripping, and static €600 EU261 protection on Lufthansa metal.
        """
        mex = AIRPORTS["MEX"]
        fra = AIRPORTS["FRA"]
        dist_mi, dist_km = haversine_distance(mex.latitude, mex.longitude, fra.latitude, fra.longitude)
        self.assertTrue(5900.0 <= dist_mi <= 5970.0)
        self.assertTrue(9500.0 <= dist_km <= 9600.0)

        # Strip estimated gov taxes from a $2,000 all-in MEX->FRA ticket
        eligible_usd, gov_tax_usd = estimate_eligible_spend(
            mex, fra, base_fare_usd=None, yq_surcharge_usd=0.0, total_ticket_price_usd=2000.0, counts_yq_surcharge=True
        )
        self.assertGreater(gov_tax_usd, 80.0)
        self.assertEqual(eligible_usd, round(2000.0 - gov_tax_usd, 2))

        # EU261: MEX->FRA on LH (EU carrier arriving in EU > 3,500 km) -> €600
        eu261_lh = evaluate_eu261_segment(mex, fra, "LH")
        self.assertTrue(eu261_lh["is_eligible"])
        self.assertEqual(eu261_lh["compensation_eur"], 600)

        # Simulate round-trip MEX-FRA-MEX on LH in 'I' class
        itinerary = [
            FlightSegment("MEX", "FRA", "LH", "I", ticketing_carrier="LH", total_ticket_price_usd=2200.0),
            FlightSegment("FRA", "MEX", "LH", "I", ticketing_carrier="LH", total_ticket_price_usd=2200.0),
        ]
        rankings = simulate_flight_crediting(itinerary)
        self.assertEqual(len(rankings), 4)  # LH_MM, UA_MP, TK_MS, AC_AP

        # Turkish Miles&Smiles has no own-metal restriction and 40k Gold threshold -> 14,840 status miles = 37.1% Gold!
        tk_res = next(r for r in rankings if r.program_code == "TK_MS")
        lh_res = next(r for r in rankings if r.program_code == "LH_MM")
        self.assertGreater(tk_res.progress_to_gold_pct, lh_res.progress_to_gold_pct)
        self.assertIsNone(tk_res.own_metal_warning)


# =============================================================================
# Phase 2 Integration Test Stubs (# TODO for Terminal Coding Session)
# =============================================================================

@pytest.mark.skip(reason="TODO Phase 2: Implement after wiring FastAPI routes in src/api/routes.py")
def test_api_post_optimize_transfer_endpoint() -> None:
    """
    # TODO (Phase 2 - API Integration Test):
    # 1. Instantiate FastAPI `TestClient(create_app())` with overridden `get_db_session`.
    # 2. POST `{"origin_iata": "MEX", "destination_iata": "MAD", "cabin": "BUSINESS"}` to `/api/v1/optimize-transfer`.
    # 3. Assert HTTP 200 and verify `CHASE_UR -> IB_PLUS` is returned first.
    """
    raise NotImplementedError("TODO: Implement in Phase 2")


@pytest.mark.skip(reason="TODO Phase 2: Implement after wiring PostgreSQL repository in src/db/repository.py")
def test_repository_upsert_promotional_transfer_bonus() -> None:
    """
    # TODO (Phase 2 - Database Repository Test):
    # 1. Seed isolated test transaction with base `TransferPartnerRule` records.
    # 2. Call `await repo.upsert_transfer_bonus("AMEX_MR", "IB_PLUS", 25.0, "2026-12-31T23:59:59Z")`.
    # 3. Verify `get_active_transfer_rules` reflects the updated 1.25:1 effective transfer ratio.
    """
    raise NotImplementedError("TODO: Implement in Phase 2")
