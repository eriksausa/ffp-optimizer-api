"""
External Award Availability & Schedule Ingestion Skeleton (`src/core/ingestion_client.py`).

Isolates future external partner API integrations (ATPCO fare filing feeds, GDS tax breakdown
lookups, and bank promotional transfer bonus webhooks) away from the deterministic `src/core`
calculation engine so offline tests never depend on external network availability.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LiveTaxQuote:
    """Structured breakdown of base fare, YQ/YR carrier surcharges, and government taxes."""

    origin_iata: str
    destination_iata: str
    marketing_carrier: str
    base_fare_usd: float
    yq_yr_surcharge_usd: float
    gov_taxes_usd: float
    raw_tax_codes: dict[str, float]


class ExternalIngestionClient:
    """
    Interface for pulling real-time promotional transfer bonuses and e-ticket tax breakdowns.

    Engineering Trade-offs:
    - Phase 1 uses static deterministic tax profiles in `src/core/seed_data.py` to guarantee
      sub-millisecond latency and zero external API fragility.
    - Phase 2 will implement async HTTP fetching with exponential backoff and Redis/PostgreSQL
      caching (`TTL = 24h` for promotional bank bonuses, `TTL = 6h` for route YQ surcharges).
    """

    def __init__(self, api_key: str | None = None, timeout_seconds: float = 5.0) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def fetch_active_bank_transfer_bonuses(self) -> list[dict[str, Any]]:
        """
        Fetches currently active time-limited credit card transfer bonuses (e.g., 30% Chase -> Avios).

        # TODO (Phase 2 - Ingestion):
        # 1. Authenticate against partner loyalty feed using `self.api_key`.
        # 2. Validate incoming JSON payload against TransferPartnerRule schema constraints.
        # 3. Filter out expired promotional windows where `promo_end_utc < now()`.
        # 4. Return normalized list of active transfer bonus overrides for repository upsert.
        """
        raise NotImplementedError("TODO: Implement in Phase 2")

    def resolve_exact_ticket_tax_breakdown(
        self,
        origin_iata: str,
        destination_iata: str,
        carrier_iata: str,
        booking_class: str,
        total_fare_usd: float,
    ) -> LiveTaxQuote:
        """
        Queries itemized GDS/ITA tax tables to split an all-in ticket price into
        eligible `base_fare_usd` + `yq_yr_surcharge_usd` vs. non-earning government taxes.

        # TODO (Phase 2 - Ingestion):
        # 1. Query cached route surcharge table in PostgreSQL first (cache-aside pattern).
        # 2. On cache miss, parse itemized tax codes (separating YQ/YR from MX/XT/US/APD).
        # 3. Persist updated route surcharge record and return `LiveTaxQuote`.
        """
        raise NotImplementedError("TODO: Implement in Phase 2")
