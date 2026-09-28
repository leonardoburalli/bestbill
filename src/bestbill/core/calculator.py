"""Pure cost engine: compare offers against a consumption profile."""

from __future__ import annotations

from datetime import date
from typing import Literal

from bestbill.arera import policy
from bestbill.core.bands import aggregate_to_structure, split_month_to_bands
from bestbill.core.models import (
    Assumptions,
    Comparison,
    ConsumptionProfile,
    CustomerType,
    Discount,
    Flat,
    Historical,
    Offer,
    OfferResult,
    PriceType,
    PunSeries,
    Residency,
    Scaled,
    Scenario,
)

_ITALIAN_MONTHS = {
    1: "gen",
    2: "feb",
    3: "mar",
    4: "apr",
    5: "mag",
    6: "giu",
    7: "lug",
    8: "ago",
    9: "set",
    10: "ott",
    11: "nov",
    12: "dic",
}


def _italian_month_year(d: date) -> str:
    return f"{_ITALIAN_MONTHS[d.month]} {d.year}"


def round_eur(value: float, ndigits: int = 2) -> float:
    """Round a euro amount for presentation only. Full precision is kept in
    the results returned by :func:`compare`.
    """
    return round(value, ndigits)


def _resolve_pun_month(pun: PunSeries, month: date) -> tuple[float, bool] | None:
    """Resolve the PUN value to use for a consumption month: the same
    calendar month if published, else the latest published month <= it (or
    the latest overall). Returns ``(value, substituted)`` or ``None`` if the
    PUN series has no data at all.
    """
    exact = pun.get(month)
    if exact is not None:
        return exact, False

    candidates = [m for m in pun.values if m <= month]
    if candidates:
        latest = max(candidates)
        return pun.values[latest], True

    latest_overall = pun.latest_month
    if latest_overall is None:
        return None
    return pun.values[latest_overall], True


def _resolve_pun_series(
    pun: PunSeries, profile: ConsumptionProfile
) -> tuple[dict[date, float], list[date]] | None:
    """Resolve a raw (pre-scenario) PUN value for every month in the
    profile. Returns ``(month -> value, substituted months)`` or ``None`` if
    the PUN series is empty.
    """
    if pun.is_empty:
        return None
    resolved: dict[date, float] = {}
    substituted: list[date] = []
    for month in profile.months:
        result = _resolve_pun_month(pun, month.month)
        if result is None:
            return None
        value, was_substituted = result
        resolved[month.month] = value
        if was_substituted:
            substituted.append(month.month)
    return resolved, substituted


def _apply_scenario(
    pun_months: dict[date, float], scenario: Scenario
) -> dict[date, float]:
    if isinstance(scenario, Historical):
        return dict(pun_months)
    if isinstance(scenario, Scaled):
        return {m: v * scenario.factor for m, v in pun_months.items()}
    if isinstance(scenario, Flat):
        return dict.fromkeys(pun_months, scenario.value)
    raise ValueError(f"unsupported scenario: {scenario!r}")


def _scenario_statement(
    period_start: date, period_end: date, scenario: Scenario
) -> str:
    period = f"{_italian_month_year(period_start)} – {_italian_month_year(period_end)}"
    if isinstance(scenario, Historical):
        return (
            "Stima nell'ipotesi che nei prossimi 12 mesi i tuoi consumi e il PUN "
            f"siano identici a quelli di {period}. Non è una previsione."
        )
    if isinstance(scenario, Scaled):
        pct = round((scenario.factor - 1) * 100)
        sign = "+" if pct >= 0 else ""
        return (
            "Stima nell'ipotesi che nei prossimi 12 mesi i tuoi consumi siano "
            f"identici a quelli di {period}, con un PUN storico modificato "
            f"({sign}{pct}%). Non è una previsione."
        )
    if isinstance(scenario, Flat):
        return (
            "Stima nell'ipotesi che nei prossimi 12 mesi i tuoi consumi siano "
            f"identici a quelli di {period}, con un PUN costante di "
            f"{scenario.value:.3f} €/kWh. Non è una previsione."
        )
    raise ValueError(f"unsupported scenario: {scenario!r}")


def _is_eligible(
    offer: Offer,
    total_kwh: float,
    today: date,
    residency: Literal["resident", "non_resident"],
    istat_comune: str | None,
) -> str | None:
    """Return a reason string if the offer must be excluded, else None."""
    if offer.customer is not CustomerType.DOMESTIC:
        return "offerta non domestica"
    if offer.residency is Residency.RESIDENTS and residency != "resident":
        return "offerta riservata ai residenti"
    if offer.residency is Residency.NON_RESIDENTS and residency != "non_resident":
        return "offerta riservata ai non residenti"
    if offer.geo is not None:
        if istat_comune is None:
            return "zona non specificata"
        if not offer.geo.matches(istat_comune):
            return "offerta non disponibile nel comune indicato"
    if offer.valid_from is not None and today < offer.valid_from:
        return "non ancora attivabile (valid_from nel futuro)"
    if offer.valid_to is not None and today > offer.valid_to:
        return "offerta scaduta (valid_to nel passato)"
    if offer.consumption_min_kwh is not None and total_kwh < offer.consumption_min_kwh:
        return "consumo annuo sotto la soglia minima dell'offerta"
    if offer.consumption_max_kwh is not None and total_kwh > offer.consumption_max_kwh:
        return "consumo annuo sopra la soglia massima dell'offerta"
    return None


def _energy_multiplier(offer: Offer) -> float:
    return 1.0 + policy.LOSSES if offer.losses_applied_to_energy else 1.0


def _priced_discounts(offer: Offer) -> list[Discount]:
    return [
        d
        for d in offer.discounts
        if policy.discount_is_priced(d.validity, d.conditional)
    ]


def _conditional_discounts(offer: Offer) -> list[Discount]:
    return [
        d
        for d in offer.discounts
        if not policy.discount_is_priced(d.validity, d.conditional)
    ]


def _offer_cost(
    offer: Offer,
    monthly_band_kwh: list[dict[str, float]],
    pun_by_month: dict[date, float] | None,
    months: list[date],
    total_kwh: float,
    committed_power_kw: float,
) -> float:
    multiplier = _energy_multiplier(offer)
    energy_cost = 0.0
    if offer.price_type is PriceType.FIXED:
        for band_kwh in monthly_band_kwh:
            for band, kwh in band_kwh.items():
                price = offer.energy_price_eur_kwh[band]
                spread = offer.spread_eur_kwh[band]
                energy_cost += kwh * (
                    (price + spread) * multiplier + offer.per_kwh_extras_eur
                )
    else:
        assert pun_by_month is not None
        for month, band_kwh in zip(months, monthly_band_kwh, strict=True):
            pun_value = pun_by_month[month]
            for band, kwh in band_kwh.items():
                spread = offer.spread_eur_kwh[band]
                energy_cost += kwh * (
                    (pun_value + spread) * multiplier + offer.per_kwh_extras_eur
                )

    fees = offer.fixed_fee_eur_year + offer.power_fee_eur_kw_year * committed_power_kw
    gross = energy_cost + fees
    discount_total = sum(
        policy.discount_annual_value_eur(d, total_kwh, energy_cost)
        for d in _priced_discounts(offer)
    )
    return gross - discount_total


def _break_even_pun(
    offer: Offer,
    monthly_band_kwh: list[dict[str, float]],
    total_kwh: float,
    best_fixed_cost: float | None,
    committed_power_kw: float,
) -> float | None:
    """Flat average PUN at which this variable offer costs the same as the
    cheapest eligible fixed offer.
    """
    if best_fixed_cost is None or total_kwh <= 0:
        return None
    multiplier = _energy_multiplier(offer)
    rest = offer.fixed_fee_eur_year + offer.power_fee_eur_kw_year * committed_power_kw
    spread_energy_cost = 0.0
    for band_kwh in monthly_band_kwh:
        for band, kwh in band_kwh.items():
            spread = offer.spread_eur_kwh[band]
            spread_energy_cost += kwh * spread * multiplier
            rest += kwh * offer.per_kwh_extras_eur
    rest += spread_energy_cost
    # Discounts are priced against the realised energy cost; approximate it
    # here with the spread-only energy cost (the PUN part cancels out at
    # equilibrium for EUR/EUR_KWH discounts, and percent discounts are an
    # approximation either way -- see policy.py for the percent caveat).
    discount_total = sum(
        policy.discount_annual_value_eur(d, total_kwh, spread_energy_cost)
        for d in _priced_discounts(offer)
    )
    rest -= discount_total
    return (best_fixed_cost - rest) / (total_kwh * multiplier)


def estimate_annual_cost(
    offer: Offer,
    profile: ConsumptionProfile,
    pun: PunSeries,
    committed_power_kw: float = 3.0,
) -> float | None:
    """Price a single offer against a consumption profile, ignoring
    eligibility (valid_from/to, consumption range, residency, geo). Used by
    ``catalog/build.py`` for the pricing-sanity gate, where eligibility is
    irrelevant (the reference customer isn't tied to a real address).
    Returns ``None`` if the offer is variable and no PUN data is available.
    """
    total_kwh = profile.total_kwh
    months = [m.month for m in profile.months]
    monthly_bands_f123 = [split_month_to_bands(m) for m in profile.months]
    band_kwh = [
        aggregate_to_structure(monthly, offer.band_structure)
        for monthly in monthly_bands_f123
    ]

    pun_by_month = None
    if offer.price_type is PriceType.VARIABLE:
        resolved = _resolve_pun_series(pun, profile)
        if resolved is None:
            return None
        pun_by_month = resolved[0]

    return _offer_cost(
        offer, band_kwh, pun_by_month, months, total_kwh, committed_power_kw
    )


def compare(
    offers: list[Offer],
    profile: ConsumptionProfile,
    pun: PunSeries,
    scenario: Scenario | None = None,
    today: date | None = None,
    residency: Literal["resident", "non_resident"] = "resident",
    istat_comune: str | None = None,
    committed_power_kw: float = 3.0,
) -> Comparison:
    """Compare offers against a 12-month consumption profile.

    ``residency``/``istat_comune`` filter offers restricted to residents or
    to a geographic zone (ARERA ZoneOfferta); ``istat_comune`` is the
    user's 6-digit ISTAT comune code -- geo-restricted offers are excluded
    when it isn't given. ``committed_power_kw`` prices offers with a
    €/kW/year power fee. See PLAN.md §5 for the backtest / perfect-foresight
    assumptions.
    """
    scenario = scenario if scenario is not None else Historical()
    today = today if today is not None else date.today()
    total_kwh = profile.total_kwh

    band_split_source: Literal["user", "standard"] = (
        "user" if all(m.bands is not None for m in profile.months) else "standard"
    )

    months = [m.month for m in profile.months]
    monthly_bands_f123 = [split_month_to_bands(m) for m in profile.months]

    resolved = _resolve_pun_series(pun, profile)
    pun_months_used: dict[date, float] = {}
    substituted_months: list[date] = []
    if resolved is not None:
        raw_pun_months, substituted_months = resolved
        pun_months_used = _apply_scenario(raw_pun_months, scenario)

    excluded: list[tuple[str, str]] = []
    eligible: list[Offer] = []
    for offer in offers:
        reason = _is_eligible(offer, total_kwh, today, residency, istat_comune)
        if reason is not None:
            excluded.append((offer.id, reason))
            continue
        if offer.price_type is PriceType.VARIABLE and resolved is None:
            excluded.append((offer.id, "PUN non disponibile per il periodo richiesto"))
            continue
        eligible.append(offer)

    offer_band_kwh: dict[str, list[dict[str, float]]] = {
        offer.id: [
            aggregate_to_structure(monthly, offer.band_structure)
            for monthly in monthly_bands_f123
        ]
        for offer in eligible
    }

    costs: dict[str, float] = {
        offer.id: _offer_cost(
            offer,
            offer_band_kwh[offer.id],
            pun_months_used if offer.price_type is PriceType.VARIABLE else None,
            months,
            total_kwh,
            committed_power_kw,
        )
        for offer in eligible
    }

    fixed_costs = [costs[o.id] for o in eligible if o.price_type is PriceType.FIXED]
    best_fixed_cost = min(fixed_costs) if fixed_costs else None

    ordered = sorted(eligible, key=lambda o: (costs[o.id], o.supplier, o.name))
    best_cost = costs[ordered[0].id] if ordered else 0.0

    results: list[OfferResult] = []
    for rank, offer in enumerate(ordered, start=1):
        cost = costs[offer.id]
        break_even = None
        if offer.price_type is PriceType.VARIABLE:
            break_even = _break_even_pun(
                offer,
                offer_band_kwh[offer.id],
                total_kwh,
                best_fixed_cost,
                committed_power_kw,
            )
        results.append(
            OfferResult(
                offer_id=offer.id,
                supplier=offer.supplier,
                name=offer.name,
                price_type=offer.price_type,
                cost_eur=cost,
                delta_vs_best_eur=cost - best_cost,
                eur_per_kwh_effective=cost / total_kwh if total_kwh > 0 else 0.0,
                rank=rank,
                break_even_pun_eur_kwh=break_even,
                one_off_fee_eur=offer.one_off_fee_eur,
                conditional_discounts=_conditional_discounts(offer),
            )
        )

    assumptions = Assumptions(
        period_start=profile.period_start,
        period_end=profile.period_end,
        pun_months_used=pun_months_used,
        substituted_pun_months=substituted_months,
        band_split_source=band_split_source,
        scenario=scenario,
        statement=_scenario_statement(
            profile.period_start, profile.period_end, scenario
        ),
        committed_power_kw=committed_power_kw,
        residency=residency,
        istat_comune=istat_comune,
    )

    return Comparison(results=results, assumptions=assumptions, excluded=excluded)
