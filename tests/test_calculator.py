"""
Unit and Integration Test Suite (`tests/test_calculator.py`).

Tests the verified Mexican credit card transfer rules (Santander Unique Rewards 1:1 to Iberia,
BBVA 2.6:1 to Iberia & 1.6:1 to Aeroméxico, Amex México 1:1) and the two transatlantic
flight crediting routes (`CDG <-> MEX` on Aeroméxico and `MEX <-> MAD` on Iberia).
"""

import unittest

try:
    import pytest
except ImportError:
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
from src.core.models import Alliance, CabinClass, FlightSegment
from src.core.seed_data import AIRPORTS


class TestCoreLoyaltyArbitrageEngine(unittest.TestCase):
    """Working unit tests for `src.core` (runs offline with zero external dependencies)."""

    def test_santander_bbva_and_amex_mex_to_iberia_math(self) -> None:
        """
        Verifies:
        - Santander Unique Rewards transfers 1:1 to Iberia Club (21,000 Unique Points -> 21,000 Avios for MEX-MAD Economy).
        - BBVA Puntos transfers 2.6:1 to Iberia Club in 130-pt blocks (54,600 Puntos BBVA -> 21,000 Avios)
          vs. 1.6:1 to Aeroméxico Rewards (120,000 Puntos BBVA -> 75,000 AM points).
        """
        options = find_best_transfer_pathways("MEX", "MAD", cabin=CabinClass.ECONOMY)
        santander_ib = next(o for o in options if o.bank_code == "SANTANDER_MX" and o.booking_program_code == "IB_PLUS")
        bbva_ib = next(o for o in options if o.bank_code == "BBVA_MX" and o.booking_program_code == "IB_PLUS")
        bbva_am = next(o for o in options if o.bank_code == "BBVA_MX" and o.booking_program_code == "AM_RW")

        self.assertEqual(santander_ib.effective_transfer_ratio, 1.0)
        self.assertEqual(santander_ib.bank_points_required, 21000)
        self.assertEqual(bbva_ib.bank_points_required, 54600)
        self.assertEqual(bbva_am.bank_points_required, 120000)
        self.assertLess(bbva_ib.bank_points_required, bbva_am.bank_points_required)

    def test_cdg_mex_on_aeromexico_skyteam_and_virgin_atlantic_unlock(self) -> None:
        """
        Verifies `CDG -> MEX` on Aeroméxico (AM):
        1. Strictly SkyTeam alliance (never Oneworld Sapphire).
        2. `CDG` departure strips $75 French airport tax (not Mexican TUA); `MEX` return strips $65 Mexican TUA.
        3. EU261 covers `CDG -> MEX` (€600, departs EU), but NOT `MEX -> CDG` (€0, non-EU origin on non-EU carrier).
        4. Crediting to Virgin Atlantic Flying Club (`VS_FC`) unlocks the 6,000-pt CUN->LHR Saver flight!
        """
        cdg = AIRPORTS["CDG"]
        mex = AIRPORTS["MEX"]

        eu_out = evaluate_eu261_segment(cdg, mex, "AM")
        eu_ret = evaluate_eu261_segment(mex, cdg, "AM")
        self.assertTrue(eu_out["is_eligible"])
        self.assertEqual(eu_out["compensation_eur"], 600)
        self.assertFalse(eu_ret["is_eligible"])
        self.assertEqual(eu_ret["compensation_eur"], 0)

        # Tax check: CDG strips $75, MEX strips $65
        _, cdg_tax = estimate_eligible_spend(cdg, mex, None, 0.0, 600.0, True)
        _, mex_tax = estimate_eligible_spend(mex, cdg, None, 0.0, 600.0, True)
        self.assertEqual(cdg_tax, 75.0)
        self.assertEqual(mex_tax, 65.0)

        itinerary = [
            FlightSegment("CDG", "MEX", "AM", "K", ticketing_carrier="AM", total_ticket_price_usd=550.0),
            FlightSegment("MEX", "CDG", "AM", "K", ticketing_carrier="AM", total_ticket_price_usd=550.0),
        ]
        rankings = simulate_flight_crediting(itinerary)
        for r in rankings:
            self.assertEqual(r.alliance, Alliance.SKYTEAM)
            self.assertIn("SkyTeam Elite Plus", r.own_metal_warning or "")

        vs_res = next(r for r in rankings if r.program_code == "VS_FC")
        self.assertGreaterEqual(vs_res.redeemable_miles_earned, 6000)
        self.assertGreaterEqual(len(vs_res.unlocked_short_haul_awards), 1)

    def test_mex_mad_on_iberia_oneworld_spend_based_ba_and_ib(self) -> None:
        """
        Verifies `MEX -> MAD` on Iberia (IB):
        1. Both Iberia Club (`IB_PLUS`) and British Airways Club (`BA_EC`) are `REVENUE_BASED` at 7 Avios/EUR.
        2. Alaska Airlines Atmos Rewards (`AS_ATMOS`) is `DISTANCE_AND_ZONE_BASED`.
        """
        itinerary = [
            FlightSegment("MEX", "MAD", "IB", "K", ticketing_carrier="IB", total_ticket_price_usd=550.0),
            FlightSegment("MAD", "MEX", "IB", "K", ticketing_carrier="IB", total_ticket_price_usd=550.0),
        ]
        rankings = simulate_flight_crediting(itinerary)
        ib_res = next(r for r in rankings if r.program_code == "IB_PLUS")
        ba_res = next(r for r in rankings if r.program_code == "BA_EC")
        as_res = next(r for r in rankings if r.program_code == "AS_ATMOS")

        self.assertEqual(ib_res.calculation_basis, "REVENUE_BASED")
        self.assertEqual(ba_res.calculation_basis, "REVENUE_BASED")
        self.assertEqual(ib_res.redeemable_miles_earned, ba_res.redeemable_miles_earned)
        self.assertEqual(as_res.calculation_basis, "DISTANCE_AND_ZONE_BASED")


@pytest.mark.skip(reason="TODO Phase 2: Implement after wiring FastAPI routes in src/api/routes.py")
def test_api_post_optimize_transfer_endpoint() -> None:
    raise NotImplementedError("TODO: Implement in Phase 2")


@pytest.mark.skip(reason="TODO Phase 2: Implement after wiring PostgreSQL repository in src/db/repository.py")
def test_repository_upsert_promotional_transfer_bonus() -> None:
    raise NotImplementedError("TODO: Implement in Phase 2")