"""Pure cost engine: compare offers against a consumption profile."""

from __future__ import annotations

from datetime import date
from typing import Literal

from bestbill.arera import policy
from bestbill.core.bands import aggregate_to_structure, split_month_to_bands
from bestbill.core.models import (
    Assumptions,
    BreakEvenStatus,
    Comparison,
    ComuneRef,
    ConsumptionProfile,
    CostBreakdown,
    CustomerType,
    Discount,
    Flat,
    Historical,
    LossesMode,
    Offer,
    OfferResult,
    PriceType,
    PunSeries,
    Residency,
    Scaled,
    Scenario,
)
from bestbill.geo import resolve_comune

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
    base = (
        "Non include costi di rete, oneri di sistema e imposte: sono uguali "
        "per ogni fornitore e non dipendono dalla scelta dell'offerta."
    )
    if isinstance(scenario, Historical):
        return (
            "Stima nell'ipotesi che nei prossimi 12 mesi i tuoi consumi e il PUN "
            f"siano identici a quelli di {period}. Non è una previsione. {base}"
        )
    if isinstance(scenario, Scaled):
        pct = round((scenario.factor - 1) * 100)
        sign = "+" if pct >= 0 else ""
        return (
            "Stima nell'ipotesi che nei prossimi 12 mesi i tuoi consumi siano "
            f"identici a quelli di {period}, con un PUN storico modificato "
            f"({sign}{pct}%). Non è una previsione. {base}"
        )
    if isinstance(scenario, Flat):
        return (
            "Stima nell'ipotesi che nei prossimi 12 mesi i tuoi consumi siano "
            f"identici a quelli di {period}, con un PUN costante di "
            f"{scenario.value:.3f} €/kWh. Non è una previsione. {base}"
        )
    raise ValueError(f"unsupported scenario: {scenario!r}")


def _is_eligible(
    offer: Offer,
    total_kwh: float,
    today: date,
    residency: Literal["resident", "non_resident"],
    comune: ComuneRef | None,
) -> str | None:
    """Return a reason string if the offer must be excluded, else None."""
    if offer.customer is not CustomerType.DOMESTIC:
        return "offerta non domestica"
    if offer.residency is Residency.RESIDENTS and residency != "resident":
        return "offerta riservata ai residenti"
    if offer.residency is Residency.NON_RESIDENTS and residency != "non_resident":
        return "offerta riservata ai non residenti"
    if offer.geo is not None:
        if comune is None:
            return "zona non specificata"
        if not offer.geo.matches(comune):
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


def _loss_multipliers(offer: Offer) -> tuple[float, float]:
    """Return ``(index_multiplier, spread_multiplier)`` for this offer's
    ``losses_mode`` (see ``bestbill.core.models.LossesMode`` and
    ``bestbill.arera.policy``, verified against AU "Regole per il calcolo
    della spesa annua stimata" v4.0):

    - NONE: no losses anywhere (1.0, 1.0) -- fixed offers of both ARERA
      sources, and every custom/legacy offer.
    - INDEX_ONLY: losses on the index only, not the spread -- mercato
      libero variable offers.
    - INDEX_AND_SPREAD: losses on (index + spread) together -- PLACET
      variable offers (PINGM + alpha).
    """
    factor = 1.0 + policy.LOSSES
    if offer.losses_mode is LossesMode.NONE:
        return 1.0, 1.0
    if offer.losses_mode is LossesMode.INDEX_ONLY:
        return factor, 1.0
    if offer.losses_mode is LossesMode.INDEX_AND_SPREAD:
        return factor, factor
    raise ValueError(f"unsupported losses_mode: {offer.losses_mode!r}")


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


def _annual_band_kwh(monthly_band_kwh: list[dict[str, float]]) -> dict[str, float]:
    """Sum each band's kWh across all 12 months -- the dimension consumption
    tiers (ARERA CONSUMO_DA/CONSUMO_A) are evaluated against."""
    totals: dict[str, float] = {}
    for band_kwh in monthly_band_kwh:
        for band, kwh in band_kwh.items():
            totals[band] = totals.get(band, 0.0) + kwh
    return totals


def _energy_cost(
    offer: Offer,
    monthly_band_kwh: list[dict[str, float]],
    pun_by_month: dict[date, float] | None,
    months: list[date],
) -> float:
    """Σ price/PUN × kWh (+ spread), with losses applied per
    ``offer.losses_mode``. This is the "energy" breakdown bucket and the
    base for percent-unit discounts (docs/pricing-policy.md §6-7).

    Flat prices/spreads are per-month; consumption-tiered prices
    (``energy_price_tiers_eur_kwh``/``spread_tiers_eur_kwh``) are
    evaluated once against each band's own annual kWh -- see
    ``bestbill.arera.policy.band_value_eur``. The spread is a scalar
    (doesn't vary by month), so summing per month or computing it once
    against the annual band total is equivalent; only the PUN index term
    must stay monthly.
    """
    index_multiplier, spread_multiplier = _loss_multipliers(offer)
    annual_band_kwh = _annual_band_kwh(monthly_band_kwh)
    energy_cost = 0.0
    if offer.price_type is PriceType.FIXED:
        for band, kwh in annual_band_kwh.items():
            price_value = policy.band_value_eur(
                offer.energy_price_eur_kwh[band],
                offer.energy_price_tiers_eur_kwh.get(band),
                kwh,
            )
            spread_value = policy.band_value_eur(
                offer.spread_eur_kwh[band],
                offer.spread_tiers_eur_kwh.get(band),
                kwh,
            )
            energy_cost += (
                price_value * index_multiplier + spread_value * spread_multiplier
            )
    else:
        assert pun_by_month is not None
        for month, band_kwh in zip(months, monthly_band_kwh, strict=True):
            pun_value = pun_by_month[month]
            for kwh in band_kwh.values():
                energy_cost += kwh * pun_value * index_multiplier
        for band, kwh in annual_band_kwh.items():
            spread_value = policy.band_value_eur(
                offer.spread_eur_kwh[band],
                offer.spread_tiers_eur_kwh.get(band),
                kwh,
            )
            energy_cost += spread_value * spread_multiplier
    return energy_cost


def _offer_breakdown(
    offer: Offer,
    monthly_band_kwh: list[dict[str, float]],
    pun_by_month: dict[date, float] | None,
    months: list[date],
    total_kwh: float,
    committed_power_kw: float,
) -> CostBreakdown:
    energy = _energy_cost(offer, monthly_band_kwh, pun_by_month, months)
    fixed_fees = offer.fixed_fee_eur_year + offer.dispatching_eur_year
    per_kwh_extras = total_kwh * offer.per_kwh_extras_eur
    power_fee = offer.power_fee_eur_kw_year * committed_power_kw
    dispatching = total_kwh * offer.dispatching_eur_kwh
    one_off = offer.one_off_fee_eur
    monthly_kwh = [sum(band_kwh.values()) for band_kwh in monthly_band_kwh]
    discounts = sum(
        policy.discount_annual_value_eur(d, total_kwh, energy, monthly_kwh)
        for d in _priced_discounts(offer)
    )
    total = (
        energy
        + fixed_fees
        + per_kwh_extras
        + power_fee
        + dispatching
        + one_off
        - discounts
    )
    return CostBreakdown(
        energy=energy,
        fixed_fees=fixed_fees,
        per_kwh_extras=per_kwh_extras,
        power_fee=power_fee,
        dispatching=dispatching,
        one_off=one_off,
        discounts=discounts,
        total=total,
    )


def _break_even_pun(
    offer: Offer,
    monthly_band_kwh: list[dict[str, float]],
    total_kwh: float,
    best_fixed_cost: float | None,
    committed_power_kw: float,
) -> tuple[float | None, BreakEvenStatus | None]:
    """Break-even PUN at which this variable offer costs the same as the
    cheapest eligible fixed offer, including dispatching, one-off fees and
    priced discounts (docs/pricing-policy.md §7).

    The variable offer's annual cost is linear in the flat average PUN
    ``P``: ``cost_var(P) = k*P + rest`` with ``k = total_kwh *
    index_multiplier``. Since ``k > 0`` whenever there's consumption to
    price (``total_kwh > 0`` is required by the caller, and
    ``index_multiplier`` is always positive -- 1.0 or ``1 + LOSSES``),
    ``cost_var(P) < best_fixed_cost`` exactly for ``P < break_even``.
    Returns ``(break_even_pun, status)``:

    - ``(P*, CHEAPER_BELOW)``: the normal case, ``P* > 0`` -- cheaper
      below that PUN, more expensive above it.
    - ``(None, NEVER_CHEAPER)``: ``P* <= 0`` -- the variable offer costs
      at least as much as the best fixed offer at every PUN >= 0, so
      there's no informative break-even point to show.
    - ``(None, ALWAYS_CHEAPER)``: defensive branch for ``k <= 0`` (not
      reachable given the caller's ``total_kwh > 0`` gate and the always-
      positive loss multiplier, kept for completeness/safety).
    - ``(None, None)``: no eligible fixed offer to break even against, or
      no consumption at all.
    """
    if best_fixed_cost is None or total_kwh <= 0:
        return None, None
    index_multiplier, spread_multiplier = _loss_multipliers(offer)
    rest = (
        offer.fixed_fee_eur_year
        + offer.dispatching_eur_year
        + offer.power_fee_eur_kw_year * committed_power_kw
        + offer.one_off_fee_eur
        + total_kwh * offer.per_kwh_extras_eur
        + total_kwh * offer.dispatching_eur_kwh
    )
    annual_band_kwh = _annual_band_kwh(monthly_band_kwh)
    spread_energy_cost = (
        sum(
            policy.band_value_eur(
                offer.spread_eur_kwh[band], offer.spread_tiers_eur_kwh.get(band), kwh
            )
            for band, kwh in annual_band_kwh.items()
        )
        * spread_multiplier
    )
    rest += spread_energy_cost
    # Discounts are priced against the realised energy cost; approximate it
    # here with the spread-only energy cost (the PUN part cancels out at
    # equilibrium for EUR/EUR_KWH discounts, and percent discounts are an
    # approximation either way -- see policy.py for the percent caveat).
    monthly_kwh = [sum(band_kwh.values()) for band_kwh in monthly_band_kwh]
    discount_total = sum(
        policy.discount_annual_value_eur(d, total_kwh, spread_energy_cost, monthly_kwh)
        for d in _priced_discounts(offer)
    )
    rest -= discount_total

    k = total_kwh * index_multiplier
    if k <= 0:
        # Defensive: can't happen given the total_kwh > 0 gate above and an
        # always-positive index_multiplier, but never divide by <= 0.
        if best_fixed_cost - rest > 0:
            return None, BreakEvenStatus.ALWAYS_CHEAPER
        return None, BreakEvenStatus.NEVER_CHEAPER

    break_even = (best_fixed_cost - rest) / k
    if break_even <= 0:
        return None, BreakEvenStatus.NEVER_CHEAPER
    return break_even, BreakEvenStatus.CHEAPER_BELOW


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

    breakdown = _offer_breakdown(
        offer, band_kwh, pun_by_month, months, total_kwh, committed_power_kw
    )
    return breakdown.total


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

    Scope: this prices the **commodity/supplier cost only** -- energy
    price/spread (with network losses applied where flagged), supplier
    fixed fees, supplier-set €/kWh extras (e.g. MACROAREA 02 pass-through),
    dispatching (TIPO_DISPACCIAMENTO, precomputed on the offer), power
    fees, one-off fees and unconditional discounts. It never adds network
    charges, system charges, excise duties or VAT: those are set by
    regulation and are identical for every supplier, so they don't change
    the ranking (PLAN.md §5). Every ``cost_eur`` in the result is this
    supplier cost, not the full electricity bill; see
    ``Assumptions.cost_label``.

    ``residency``/``istat_comune`` filter offers restricted to residents or
    to a geographic zone (ARERA ZoneOfferta); ``istat_comune`` is the
    user's 6-digit ISTAT comune code (resolved to its provincia and
    regione via ``bestbill.geo``) -- geo-restricted offers are excluded
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

    comune = resolve_comune(istat_comune) if istat_comune is not None else None

    excluded: list[tuple[str, str]] = []
    eligible: list[Offer] = []
    for offer in offers:
        reason = _is_eligible(offer, total_kwh, today, residency, comune)
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

    breakdowns: dict[str, CostBreakdown] = {
        offer.id: _offer_breakdown(
            offer,
            offer_band_kwh[offer.id],
            pun_months_used if offer.price_type is PriceType.VARIABLE else None,
            months,
            total_kwh,
            committed_power_kw,
        )
        for offer in eligible
    }
    costs: dict[str, float] = {
        offer_id: breakdown.total for offer_id, breakdown in breakdowns.items()
    }

    fixed_costs = [costs[o.id] for o in eligible if o.price_type is PriceType.FIXED]
    best_fixed_cost = min(fixed_costs) if fixed_costs else None

    ordered = sorted(eligible, key=lambda o: (costs[o.id], o.supplier, o.name))
    best_cost = costs[ordered[0].id] if ordered else 0.0

    results: list[OfferResult] = []
    for rank, offer in enumerate(ordered, start=1):
        cost = costs[offer.id]
        break_even = None
        break_even_status = None
        if offer.price_type is PriceType.VARIABLE:
            break_even, break_even_status = _break_even_pun(
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
                break_even_status=break_even_status,
                one_off_fee_eur=offer.one_off_fee_eur,
                conditional_discounts=_conditional_discounts(offer),
                breakdown=breakdowns[offer.id],
                dispatching_is_standard_estimate=offer.dispatching_is_standard_estimate,
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
