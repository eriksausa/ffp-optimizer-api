# Loyalty Arbitrage Engine (`loyalty-arbitrage-engine`)

A modular Python backend and domain calculation engine that solves two interconnected airline loyalty optimization problems:

1. **Credit Card Point Transfer & Partner Award Arbitrage**: Evaluates transferable bank currencies (**American Express Membership Rewards**, **Chase Ultimate Rewards**, **Citi ThankYou Points**, **Capital One Venture Miles**), active promotional transfer bonuses, and cross-alliance partner award charts (**Star Alliance**, **Oneworld**, **SkyTeam**) to identify the lowest-point pathway to book a target flight and cabin.
2. **Paid Flight Crediting & Status ROI ("Default to the Metal" vs. "Smart Alliance Switch")**: Simulates crediting paid flight segments across competing alliance programs, stripping mandatory government departure taxes (e.g., Mexico's TUA or UK APD) while retaining eligible Base Fare + Carrier-Imposed Surcharges (`YQ`/`YR`), calculating normalized percentage progress toward Alliance Gold/Sapphire/Elite Plus, unlocking tangible award benchmarks, and checking static **EU261** route protection (€250 / €400 / €600).

## Repository Architecture

```text
loyalty-arbitrage-engine/
├── README.md                  # System architecture, math/routing overview, and active development roadmap
├── requirements.txt           # Core dependencies + pinned stack (fastapi, sqlalchemy, pydantic, mangum, pytest)
├── .gitignore                 # Standard Python/env ignores
├── src/
│   ├── __init__.py
│   ├── core/                  # WORKING NOW: Pure Python domain logic (zero external API dependencies)
│   │   ├── __init__.py
│   │   ├── models.py          # Frozen dataclasses & Enums for Programs, Alliances, TransferRatios, and Routes
│   │   ├── calculator.py      # Working CPM, transfer bonus math, tax stripping, EU261, and arbitrage logic
│   │   ├── seed_data.py       # Static dataset of alliances (Star Alliance, SkyTeam, Oneworld) & bank transfer partners
│   │   └── ingestion_client.py# Skeleton interface for live tax breakdown & promotional bonus feeds (# TODO)
│   ├── db/                    # SCAFFOLD / TODO: PostgreSQL persistence layer
│   │   ├── __init__.py
│   │   ├── session.py         # Skeleton for SQLAlchemy AsyncEngine & connection pooling (# TODO: wire PostgreSQL URI)
│   │   └── repository.py      # Skeleton CRUD repository for transfer matrices and partner award charts (# TODO)
│   ├── api/                   # SCAFFOLD / TODO: FastAPI REST layer
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI app factory and healthcheck + # TODO: mount routers and middleware
│   │   └── routes.py          # Endpoint skeletons (POST /optimize-transfer, POST /simulate-crediting, GET /alliances)
│   └── serverless/            # SCAFFOLD / TODO: AWS Lambda deployment layer
│       ├── __init__.py
│       └── lambda_handler.py  # AWS Lambda entry point skeleton using Mangum + scheduled rate-refresh stubs (# TODO)
└── tests/
    ├── __init__.py
    └── test_calculator.py     # Working unit tests for core math + # TODO stubs for API/DB integration tests
```

## Core Math & Routing Overview (`src/core/`)

### 1. Transfer Bonus & Minimum Increment Rounding
When transferring credit card points to an airline partner with a base ratio $R_{\text{base}}$ and promotional bonus $B_{\%}$:

$$R_{\text{eff}} = R_{\text{base}} \times \left(1 + \frac{B_{\%}}{100}\right)$$

$$P_{\text{bank}} = \left\lceil \frac{M_{\text{award}}}{R_{\text{eff}} \times I_{\text{min}}} \right\rceil \times I_{\text{min}}$$

where $I_{\text{min}}$ is the bank's required transfer increment (typically $1,000$ points).

### 2. Realized Cents-Per-Point (CPP) vs. Cash-Out Baseline
Instead of assigning arbitrary static valuations to loyalty currencies, the engine calculates realized purchasing power against the target route's cash benchmark $C_{\text{cash}}$ and mandatory award co-pay ($T_{\text{gov}} + YQ$):

$$\text{CPP}_{\text{realized}} = \frac{\max(0,\; C_{\text{cash}} - (T_{\text{gov}} + YQ)) \times 100}{P_{\text{bank}}}$$

### 3. Revenue Spend Separation (Base Fare + `YQ` vs. Government Taxes)
Revenue-based programs (**United MileagePlus**, **Lufthansa Miles & More**, **Iberia Plus**, **Aeroméxico Rewards**) award miles on **Base Fare + Carrier-Imposed Surcharges (`YQ`/`YR`)**, while excluding mandatory government airport taxes. When only an all-in ticket price is supplied, `estimate_eligible_spend` automatically strips airport-specific departure taxes using `AirportProfile.estimated_gov_departure_tax_usd`.

## Running the Core Engine & Tests Locally

Because `src/core/` uses only the Python 3.11+ standard library, you can run the core unit tests immediately with either `pytest` or standard `unittest`:

```bash
python3 -m unittest discover -s tests -v
# or with pytest installed:
pytest -v
```

## Active Development Roadmap (Phase 2 Backlog)

1. **PostgreSQL 16 Async Persistence (`src/db/session.py` & `src/db/repository.py`)**:
   - Wire `create_async_engine` (`postgresql+asyncpg://`) with environment-aware connection pooling (`NullPool` for AWS Lambda vs. `AsyncAdaptedQueuePool` for containers).
   - Implement `LoyaltyRepository` batch queries (`get_active_transfer_rules`, `get_award_sweet_spots_by_route`, `get_earning_rules_for_segments`, and `upsert_transfer_bonus`).
2. **FastAPI REST Layer (`src/api/main.py` & `src/api/routes.py`)**:
   - Implement `create_app()` with CORS, lifespan hooks, and RFC 7807 Problem Details exception handlers.
   - Wire `POST /api/v1/optimize-transfer`, `POST /api/v1/simulate-crediting`, and `GET /api/v1/alliances`.
3. **AWS Lambda Serverless & Scheduled Ingestion (`src/serverless/lambda_handler.py` & `src/core/ingestion_client.py`)**:
   - Wrap the FastAPI app with `Mangum` in `api_gateway_handler`.
   - Implement `scheduled_bonus_refresh_handler` for Amazon EventBridge 12-hour promotional transfer bonus syncs.
4. **Multi-Segment ECJ EU261 Connecting Itinerary Rules**:
   - Extend `evaluate_eu261_segment` to evaluate single-PNR connecting itineraries across EU hubs under European Court of Justice case law.
