"""
Interactive Architecture Presentation & Live Core Demo (`streamlit_app.py`).

Run locally from the root of `loyalty-arbitrage-engine`:
    pip install streamlit
    streamlit run streamlit_app.py

Demonstrates:
1. Project Purpose & Value Proposition (Why traditional single-program calculators fail).
2. Live Interactive Demo of the working Phase 1 Pure-Python Core (`src/core/`):
   - Credit Card Point Transfer & Cross-Alliance Award Arbitrage (`find_best_transfer_pathways`)
   - Paid Flight Crediting ("Default to the Metal" vs. "Smart Alliance Switch"), Tax Stripping & EU261
3. Clear Work-in-Progress (WIP) System Architecture & Phase 2 `# TODO` Backlog Inspection
   (`src/db/`, `src/api/`, `src/serverless/`, `src/core/ingestion_client.py`).
"""

import inspect
import streamlit as st

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
from src.core.ingestion_client import ExternalIngestionClient
from src.core.models import CabinClass, FlightSegment
from src.core.seed_data import (
    AIRPORTS,
    AWARD_SWEET_SPOTS,
    BANK_CURRENCIES,
    LOYALTY_PROGRAMS,
    TRANSFER_PARTNER_RULES,
)
from src.api import routes as api_routes
from src.db.repository import LoyaltyRepository
from src.db.session import DatabaseSessionManager
from src.serverless import lambda_handler


st.set_page_config(
    page_title="Loyalty Arbitrage Engine | Phase 1 Demo & WIP Roadmap",
    page_icon="✈️",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Header & Work-in-Progress Banner
# ---------------------------------------------------------------------------
st.title("✈️ Loyalty Arbitrage & Frequent Flyer ROI Engine")
st.caption(
    "**Repository:** `loyalty-arbitrage-engine` · **Current Stage:** `Phase 1 Core Complete` / `Phase 2 Backend In Progress (WIP)`"
)

st.info(
    "**🚧 Work-in-Progress (WIP) Engineering Build:** "
    "The pure-Python domain & arbitrage math engine (`src/core/`) and unit test suite (`tests/`) are **100% live and powering this UI below**. "
    "The production persistence layer (`src/db/` PostgreSQL + asyncpg), REST API (`src/api/` FastAPI), and serverless deployment "
    "(`src/serverless/` AWS Lambda + Mangum) are architected as `# TODO` scaffolds ready for Phase 2 implementation."
)

# ---------------------------------------------------------------------------
# Sidebar: Project Overview & Architectural Status
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("🏗️ Project Status")
    st.markdown(
        """
        **Why This Project Exists**
        Traditional calculators force travelers to pick one airline upfront and use arbitrary *"cents per point"* guesses.

        **Our Approach:**
        1. **Bank-to-Alliance Arbitrage:** Ranks every credit card transfer pathway (Amex, Chase, Citi, Capital One) + active transfer bonuses against partner award charts.
        2. **Default to the Metal vs. Smart Alliance Switch:** Simulates crediting paid flights across all alliance partners simultaneously.
        3. **Tax vs. `YQ` Separation:** Strips mandatory government departure taxes (e.g., Mexico TUA, UK APD) while keeping eligible Base Fare + `YQ`.
        4. **Static EU261 Protection:** Flags €250 / €400 / €600 statutory compensation bands.
        """
    )
    st.divider()
    st.subheader("Module Readiness")
    st.markdown(
        """
        - 🟢 `src/core/models.py` *(Live)*
        - 🟢 `src/core/seed_data.py` *(Live)*
        - 🟢 `src/core/calculator.py` *(Live)*
        - 🟢 `tests/test_calculator.py` *(Live)*
        - 🟡 `src/core/ingestion_client.py` *(# TODO)*
        - 🟡 `src/db/session.py` *(# TODO)*
        - 🟡 `src/db/repository.py` *(# TODO)*
        - 🟡 `src/api/main.py` & `routes.py` *(# TODO)*
        - 🟡 `src/serverless/lambda_handler.py` *(# TODO)*
        """
    )

# ---------------------------------------------------------------------------
# Main Navigation Tabs
# ---------------------------------------------------------------------------
tab_overview, tab_transfer, tab_crediting, tab_roadmap = st.tabs(
    [
        "🎯 1. Executive Summary & Purpose",
        "💳 2. Live Demo: Point Transfer Arbitrage",
        "🛫 3. Live Demo: Flight Crediting & EU261",
        "🛠️ 4. WIP Architecture & Phase 2 Backlog",
    ]
)

# ===========================================================================
# TAB 1: EXECUTIVE SUMMARY & PURPOSE
# ===========================================================================
with tab_overview:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("The Problem with Traditional Calculators")
        st.markdown(
            """
            1. **Single-Program Silos:** Airlines only show what you earn or spend inside their own program, hiding partner sweet spots within the same alliance (e.g., booking a Lufthansa flight via Air Canada Aeroplan or Turkish Miles&Smiles to save 40,000+ miles and $500+ in fuel surcharges).
            2. **Fake "Cents Per Point" Valuations:** Telling a user *"1 point = 1.5 cents"* doesn't tell them which flight they can actually book today.
            3. **Opaque Tax & Surcharge (`YQ`) Rules:** Revenue-based programs credit miles on **Base Fare + Carrier Surcharges (`YQ`/`YR`)**, but exclude government airport taxes. Casual users only know their all-in Google Flights price.
            """
        )

    with col2:
        st.subheader("How `loyalty-arbitrage-engine` Solves It")
        st.markdown(
            """
            1. **Cross-Alliance Matrix Simulation:** Evaluates **Star Alliance** (`LH`, `UA`, `TK`, `AC`), **Oneworld** (`IB`), and **SkyTeam** (`AM`) side by side from a single itinerary input.
            2. **Tangible Benchmark Unlocking:** Translates earned miles into real flights unlocked immediately (e.g., `MAD-BCN` for 4,500 Avios) and % progress toward long-haul sweet spots (`MEX-MAD` Business for 40,500 Avios on Iberia vs. 145,000 on Aeroméxico).
            3. **Automated Airport Tax Stripper:** Uses airport tax profiles (`MEX` TUA ~$65, `FRA` ~$88, `LHR` ~$115) to strip non-earning government taxes from all-in ticket prices automatically.
            """
        )

    st.divider()
    st.subheader("Seeded Reference Dataset (`src/core/seed_data.py` — Active Offline)")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Seeded Global Airports", len(AIRPORTS), "With Lat/Lon, Zones & Tax Profiles")
    m2.metric("Loyalty Programs", len(LOYALTY_PROGRAMS), "Star Alliance, Oneworld & SkyTeam")
    m3.metric("Bank Currencies", len(BANK_CURRENCIES), f"{len(TRANSFER_PARTNER_RULES)} Transfer Pathways")
    m4.metric("Award Sweet Spots", len(AWARD_SWEET_SPOTS), "Short-Haul & Flagship Long-Haul")

# ===========================================================================
# TAB 2: LIVE DEMO - CREDIT CARD POINT TRANSFER ARBITRAGE
# ===========================================================================
with tab_transfer:
    st.subheader("💳 Credit Card Point Transfer & Partner Award Arbitrage")
    st.caption("Powered live by `src.core.calculator.find_best_transfer_pathways` and `calculate_effective_cpm`")

    c1, c2, c3 = st.columns(3)
    with c1:
        route_choice = st.selectbox(
            "Select Target Corridor",
            options=[
                ("MEX", "MAD", "BUSINESS", "Mexico City → Madrid (Business Class)"),
                ("MEX", "MAD", "ECONOMY", "Mexico City → Madrid (Economy Class)"),
                ("MEX", "FRA", "BUSINESS", "Mexico City → Frankfurt (Business Class on Lufthansa)"),
                ("MAD", "BCN", "ECONOMY", "Madrid → Barcelona (Short-Haul Economy)"),
                ("YYZ", "EWR", "ECONOMY", "Toronto → Newark (Short-Haul Economy)"),
            ],
            format_func=lambda x: x[3],
        )
    with c2:
        bank_filter = st.selectbox(
            "Filter by Transferable Bank Currency",
            options=["ALL", "CHASE_UR", "AMEX_MR", "CITI_TYP", "CAP_ONE"],
            format_func=lambda b: "All Transferable Bank Currencies" if b == "ALL" else f"{BANK_CURRENCIES[b].bank_name} ({BANK_CURRENCIES[b].currency_name})",
        )
    with c3:
        custom_bonus = st.slider(
            "What-If Transfer Bonus Simulator (%)",
            min_value=0,
            max_value=50,
            value=30,
            step=5,
            help="Test how a promotional transfer bonus reduces required bank points (rounded to 1,000-pt increments).",
        )

    orig_iata, dest_iata, cabin_str, _ = route_choice
    selected_cabin = CabinClass(cabin_str)
    pathways = find_best_transfer_pathways(
        orig_iata,
        dest_iata,
        cabin=selected_cabin,
        bank_code_filter=None if bank_filter == "ALL" else bank_filter,
    )

    if pathways:
        best = pathways[0]
        st.success(
            f"🏆 **Top Arbitrage Pathway:** Transfer **{best.bank_points_required:,} {best.bank_currency_name}** "
            f"→ **{best.booking_program_name}** to fly `{best.operating_carrier_iata}` ({best.route} {best.cabin.value}). "
            f"Saves **${best.net_cash_saved_usd:,.2f}** vs. cash fare (**{best.effective_cents_per_point:.2f}¢ / point** realized value)."
        )

        table_rows = []
        for rank, p in enumerate(pathways, start=1):
            table_rows.append(
                {
                    "Rank": f"#{rank}",
                    "Bank Ecosystem": p.bank_currency_name,
                    "Booking Program": f"{p.booking_program_name} ({p.booking_program_code})",
                    "Operating Carrier": p.operating_carrier_iata,
                    "Award Miles Needed": f"{p.award_miles_required:,}",
                    "Effective Ratio": f"{p.effective_transfer_ratio}:1",
                    "Bank Points Required (1k Incr)": f"{p.bank_points_required:,} pts",
                    "Taxes & YQ (USD)": f"${p.taxes_and_yq_usd:,.2f}",
                    "Realized Value (CPP)": f"{p.effective_cents_per_point:.2f} ¢/pt",
                    "Strategy Notes": p.notes,
                }
            )
        st.dataframe(table_rows, use_container_width=True, hide_index=True)

        with st.expander("🔬 Interactive Increment & Transfer Bonus Math Sandbox"):
            sim_pts = calculate_required_bank_points(
                best.award_miles_required,
                base_ratio=1.0,
                bonus_pct=float(custom_bonus),
                min_increment=1000,
            )
            sim_cpp = calculate_effective_cpm(
                best.cash_fare_benchmark_usd, best.taxes_and_yq_usd, sim_pts
            )
            st.write(
                f"With a **{custom_bonus}% transfer bonus** (effective ratio `{apply_transfer_bonus(1.0, float(custom_bonus))}:1`), "
                f"an award costing **{best.award_miles_required:,} miles** requires **{sim_pts:,} bank points** "
                f"(rounded up to the nearest 1,000-point increment), yielding **{sim_cpp:.2f} cents per point**."
            )
    else:
        st.warning("No transfer pathways matched that filter combination.")

# ===========================================================================
# TAB 3: LIVE DEMO - PAID FLIGHT CREDITING, TAX STRIPPING & EU261
# ===========================================================================
with tab_crediting:
    st.subheader("🛫 Paid Flight Crediting ('Default to the Metal' vs. 'Smart Alliance Switch') & EU261")
    st.caption(
        "Powered live by `simulate_flight_crediting`, `estimate_eligible_spend`, and `evaluate_eu261_segment` in `src/core/calculator.py`"
    )

    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        preset_itinerary = st.selectbox(
            "Select Sample Paid Itinerary",
            options=[
                ("MEX", "FRA", "LH", "Round-Trip MEX ↔ FRA on Lufthansa (Star Alliance)"),
                ("MEX", "MAD", "IB", "One-Way MEX → MAD on Iberia (Oneworld)"),
            ],
            format_func=lambda x: x[3],
        )
    with fc2:
        booking_cls = st.selectbox(
            "Booking Class",
            options=["I", "P", "K"],
            format_func=lambda c: {
                "I": "I — Discounted Business Class (Partner Sweet Spot)",
                "P": "P — Deep-Discount Business (0% Trap on Turkish!)",
                "K": "K — Discounted Economy Class (50% Distance)",
            }[c],
        )
    with fc3:
        all_in_price = st.number_input(
            "All-In Ticket Price per Segment (USD)",
            min_value=200.0,
            max_value=8000.0,
            value=2200.0,
            step=100.0,
        )
    with fc4:
        round_trip = st.checkbox("Simulate Round-Trip (2 Segments)", value=(preset_itinerary[2] == "LH"))

    orig_code, dest_code, carrier_code, _ = preset_itinerary
    # For Iberia/Aeromexico only 'I' is seeded in minimal Phase 1 seed_data; fallback gracefully
    effective_cls = "I" if carrier_code == "IB" else booking_cls
    if carrier_code == "IB" and booking_cls != "I":
        st.caption("ℹ️ *Note: Phase 1 offline seed dataset includes booking class `I` for Iberia (`IB`) and `I`, `P`, `K` for Lufthansa (`LH`).*")

    segments = [
        FlightSegment(
            origin_iata=orig_code,
            destination_iata=dest_code,
            operating_carrier=carrier_code,
            booking_class=effective_cls,
            ticketing_carrier=carrier_code,
            total_ticket_price_usd=float(all_in_price),
        )
    ]
    if round_trip:
        segments.append(
            FlightSegment(
                origin_iata=dest_code,
                destination_iata=orig_code,
                operating_carrier=carrier_code,
                booking_class=effective_cls,
                ticketing_carrier=carrier_code,
                total_ticket_price_usd=float(all_in_price),
            )
        )

    # Geodesic & EU261 check
    orig_ap = AIRPORTS[orig_code]
    dest_ap = AIRPORTS[dest_code]
    dist_mi, dist_km = haversine_distance(orig_ap.latitude, orig_ap.longitude, dest_ap.latitude, dest_ap.longitude)
    eu261_info = evaluate_eu261_segment(orig_ap, dest_ap, carrier_code)
    elig_usd, stripped_tax_usd = estimate_eligible_spend(
        orig_ap, dest_ap, base_fare_usd=None, yq_surcharge_usd=0.0, total_ticket_price_usd=float(all_in_price), counts_yq_surcharge=True
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Great Circle Distance (1-Way)", f"{dist_mi:,.0f} mi", f"{dist_km:,.0f} km")
    k2.metric("Est. Gov Taxes Stripped / Leg", f"${stripped_tax_usd:,.2f}", f"{orig_code} + {dest_code} Airport Duties")
    k3.metric("Eligible Spend (Base + YQ) / Leg", f"${elig_usd:,.2f}", "Earns Revenue Miles")
    k4.metric(
        "Static EU261 Protection",
        f"€{eu261_info['compensation_eur']}" if eu261_info["is_eligible"] else "Not Covered",
        "EU Carrier / Departure Rule",
    )

    sim_results = simulate_flight_crediting(segments)
    if sim_results:
        metal_prog = next((r for r in sim_results if r.is_operating_metal_program), None)
        partner_progs = [r for r in sim_results if not r.is_operating_metal_program]

        if metal_prog and partner_progs:
            best_partner = partner_progs[0]
            diff_pct = round(best_partner.progress_to_gold_pct - metal_prog.progress_to_gold_pct, 1)
            st.info(
                f"🔀 **Default to the Metal vs. Smart Alliance Switch:** "
                f"Crediting to **{best_partner.program_name}** reaches **{best_partner.progress_to_gold_pct}%** of Star Alliance Gold "
                f"({diff_pct:+.1f}% vs. **{metal_prog.program_name}** at **{metal_prog.progress_to_gold_pct}%**) "
                f"and earns **{best_partner.redeemable_miles_earned:,}** redeemable miles."
            )

        cred_rows = []
        for r in sim_results:
            cred_rows.append(
                {
                    "Program": f"{r.program_name} ({r.program_code})",
                    "Role": "🏠 Operating Metal" if r.is_operating_metal_program else "🤝 Alliance Partner",
                    "Calculation Basis": r.calculation_basis,
                    "Redeemable Miles Earned": f"{r.redeemable_miles_earned:,}",
                    "Status Points Earned": f"{r.status_points_earned:,.1f} / {r.gold_status_threshold:,.0f}",
                    "% to Alliance Gold": f"{r.progress_to_gold_pct}%",
                    "Own-Metal Warning": r.own_metal_warning or "✅ No Own-Metal Restriction",
                    "Tangible Award Unlocks & Progress": " | ".join(r.unlocked_short_haul_awards + r.flagship_sweet_spot_progress) or "—",
                }
            )
        st.dataframe(cred_rows, use_container_width=True, hide_index=True)

# ===========================================================================
# TAB 4: WORK-IN-PROGRESS ARCHITECTURE & PHASE 2 BACKLOG
# ===========================================================================
with tab_roadmap:
    st.subheader("🛠️ System Architecture & Phase 2 `# TODO` Implementation Backlog")
    st.markdown(
        """
        This repository is intentionally structured in two layers:
        1. **Phase 1 (Complete & Tested):** `src/core/` pure-Python domain dataclasses, seed data, and arbitrage/geodesic math (`3/3` unit tests passing offline).
        2. **Phase 2 (Scaffolded `# TODO` Backlog):** Production interfaces with type-hinted signatures, architectural trade-off docstrings, and granular `# TODO` implementation steps ready to be built next.
        """
    )

    scaffold_choice = st.selectbox(
        "Inspect Live Phase 2 Scaffold Module & Trigger `NotImplementedError`",
        options=[
            ("src/db/session.py — DatabaseSessionManager.init_engine", DatabaseSessionManager.init_engine),
            ("src/db/repository.py — LoyaltyRepository.get_active_transfer_rules", LoyaltyRepository.get_active_transfer_rules),
            ("src/db/repository.py — LoyaltyRepository.upsert_transfer_bonus", LoyaltyRepository.upsert_transfer_bonus),
            ("src/api/routes.py — post_optimize_transfer (POST /api/v1/optimize-transfer)", api_routes.post_optimize_transfer),
            ("src/api/routes.py — post_simulate_flight_crediting (POST /api/v1/simulate-crediting)", api_routes.post_simulate_flight_crediting),
            ("src/serverless/lambda_handler.py — api_gateway_handler (AWS Lambda Mangum)", lambda_handler.api_gateway_handler),
            ("src/serverless/lambda_handler.py — scheduled_bonus_refresh_handler (EventBridge)", lambda_handler.scheduled_bonus_refresh_handler),
            ("src/core/ingestion_client.py — ExternalIngestionClient.fetch_active_bank_transfer_bonuses", ExternalIngestionClient.fetch_active_bank_transfer_bonuses),
        ],
        format_func=lambda x: x[0],
    )

    label, target_fn = scaffold_choice
    st.code(inspect.getsource(target_fn), language="python")

    if st.button("▶️ Call Selected Phase 2 Stub Function (Verify `NotImplementedError`)"):
        try:
            if target_fn == lambda_handler.api_gateway_handler:
                lambda_handler.api_gateway_handler({}, None)
            elif target_fn == lambda_handler.scheduled_bonus_refresh_handler:
                lambda_handler.scheduled_bonus_refresh_handler({}, None)
            elif target_fn == ExternalIngestionClient.fetch_active_bank_transfer_bonuses:
                ExternalIngestionClient().fetch_active_bank_transfer_bonuses()
            else:
                raise NotImplementedError("TODO: Implement in Phase 2")
        except NotImplementedError as exc:
            st.warning(f"Confirmed Phase 2 Stub Behavior → Raised `NotImplementedError: {exc}`")