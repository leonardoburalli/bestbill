"""THE single place for uncertain ARERA pricing rules.

Every rule here is verified against the AU "Regole per il calcolo della
spesa annua stimata" v4.0 and the user-approved ``docs/pricing-policy.md``
(2026-09-28). Parsers (:mod:`bestbill.arera.placet`,
:mod:`bestbill.arera.mlibero`) call into this module instead of
hard-coding pricing decisions, so a single review can adjust every rule
without touching parser code.

Scope: commodity/retailer-dependent cost only, before VAT. Network
charges, system charges, excise duties and VAT are never priced here.

Verified rules (see ``docs/pricing-policy.md``):
- **Network losses (LOSSES)**: fixed offers (both ARERA sources) get NO
  losses. Mercato libero variable offers apply losses to the index only,
  not the spread. PLACET variable offers apply losses to (PINGM + alpha)
  together. See ``bestbill.core.models.LossesMode`` and ``losses_mode()``
  below.
- **IDX_PREZZO_ENERGIA**: 12 and 01 are both treated as the monthly PUN
  index (01 is *inferred* to behave like 12 in the sample data -- flagged
  here in case a future spec revision distinguishes them). Other codes
  (05 Maggior Tutela, 08, ...) are excluded.
- **Maggior Tutela**: closed to new customers; any offer referencing it
  (IDX_PREZZO_ENERGIA 05, TIPO_DISPACCIAMENTO 02/10, Sconto TIPOLOGIA 04)
  is excluded with reason "riferita a Maggior Tutela".
- **Dispatching**: priced per offer from the ARERA parameters files
  (``bestbill.arera.parameters``); see ``dispatching_component_v2()``.
- **Discounts**: IVA_SCONTO 02 amounts are converted to pre-VAT with
  ``VAT_DOMESTIC`` (flat 10% household VAT) at parse time.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bestbill.arera.codes import (
    Macroarea,
    ScontoValidita,
    TipologiaFasce,
    UnitaMisura,
)
from bestbill.arera.parameters import Parameters
from bestbill.core.models import (
    ConsumptionTier,
    Discount,
    DiscountUnit,
    DiscountValidity,
    LossesMode,
    OfferSource,
    PriceType,
)

#: mercato libero DETTAGLIOOFFERTA/DURATA values meaning "no fixed term".
#: -1 is indeterminata; 99 is treated the same for now.
#: pending confirmation against ARERA spec
OPEN_ENDED_DURATA = frozenset({-1, 99})

#: PLACET conditions are fixed for 12 months by ARERA regulation (the PLACET
#: CSV has no duration column).
PLACET_DURATION_MONTHS = 12


def parse_durata(value: str | None) -> tuple[int | None, bool]:
    """Map a raw DURATA text to ``(duration_months, open_ended)``.

    Missing/invalid/non-positive (other than open-ended codes) -> unknown
    ``(None, False)``.
    """
    if value is None:
        return None, False
    try:
        n = int(value.strip())
    except ValueError:
        return None, False
    if n in OPEN_ENDED_DURATA:
        return None, True
    if n < 1:
        return None, False
    return n, False


#: Network losses applied at low voltage, art. 13.2 methodology, verified
#: against AU "Regole per il calcolo della spesa annua stimata" v4.0 (see
#: docs/arera-data.md "Methodology points" and ``losses_mode()`` below for
#: which offers/components it applies to).
LOSSES = 0.10

#: Flat household VAT rate, used ONLY to convert Sconto/IVA_SCONTO == "02"
#: (post-VAT) discount amounts back to pre-VAT at parse time. Never used
#: to add VAT to the cost estimate itself (see docs/pricing-policy.md).
VAT_DOMESTIC = 0.10

#: ARERA reference domestic customer ("cliente tipo").
REFERENCE_CONSUMPTION_KWH = 2700.0
REFERENCE_POWER_KW = 3.0

#: Plausibility gate for the pricing sanity check in catalog/validate.py.
PLAUSIBLE_MIN_EUR = 100.0
PLAUSIBLE_MAX_EUR = 5000.0

#: Sanity gate on the day-to-day change in included-offer counts.
COUNT_CHANGE_TOLERANCE = 0.30

#: Tolerance for the Cdisp + mean(cpty) ≈ cdispd sanity invariant.
DISPATCHING_IDENTITY_TOLERANCE = 1e-6

#: Reason string used for every Maggior Tutela exclusion (IDX 05,
#: TIPO_DISPACCIAMENTO 02/10, Sconto TIPOLOGIA 04).
MAGGIOR_TUTELA_REASON = "riferita a Maggior Tutela"

#: RiferimentiPrezzoEnergia/COEFFICIENTE: a multiplier on the index
#: (PERC_IDX × PUN), used from 01/04/2026 when more than one index is
#: transmitted for an offer. Every domestic offer observed in the real
#: catalogue carries a single index with COEFFICIENTE "1" (a no-op); we
#: only accept that no-op case and exclude anything else rather than
#: guess at combining multiple indices.
SUPPORTED_COEFFICIENTE = "1"

#: IDX_PREZZO_ENERGIA codes we can price: 12 (PUN GME mensile) and 01,
#: both treated as the monthly PUN (see module docstring).
SUPPORTED_IDX_CODES = frozenset({"01", "12"})

#: TIPOLOGIA_FASCE codes we can price.
SUPPORTED_TIPOLOGIA_FASCE = frozenset(
    {TipologiaFasce.MONO, TipologiaFasce.F1F2F3, TipologiaFasce.F1F23}
)

#: TIPO_DISPACCIAMENTO code meaning a €/year fixed fee rather than €/kWh.
_DISPBT_FIXED_FEE_CODE = "13"


def losses_mode(source: OfferSource, price_type: PriceType) -> LossesMode:
    """How network losses apply to this offer's energy terms. Verified
    against AU "Regole per il calcolo della spesa annua stimata" v4.0:
    fixed offers (either source) get no losses; mercato libero variable
    offers apply losses to the index only; PLACET variable offers apply
    losses to (index + spread) together.
    """
    if price_type is PriceType.FIXED:
        return LossesMode.NONE
    if source is OfferSource.MLIBERO:
        return LossesMode.INDEX_ONLY
    if source is OfferSource.PLACET:
        return LossesMode.INDEX_AND_SPREAD
    raise ValueError(f"unsupported source for losses_mode: {source!r}")


def idx_is_supported(idx_code: str) -> bool:
    return idx_code in SUPPORTED_IDX_CODES


def idx_is_maggior_tutela(idx_code: str) -> bool:
    return idx_code == "05"


def tipologia_fasce_is_supported(code: str) -> bool:
    return code in SUPPORTED_TIPOLOGIA_FASCE


class ComponentRole:
    """Where a ComponenteImpresa price ends up in the normalised Offer."""

    FIXED_FEE = "fixed_fee"
    ENERGY_PRICE = "energy_price"
    SPREAD = "spread"
    PER_KWH_EXTRAS = "per_kwh_extras"
    ONE_OFF = "one_off"
    POWER_FEE = "power_fee"


def classify_component(
    macroarea: str, unita_misura: str, price_type: PriceType
) -> tuple[str, None] | tuple[None, str]:
    """Classify a ComponenteImpresa price into a :class:`ComponentRole`, or
    return an exclusion reason if the MACROAREA/UNITA_MISURA combination is
    not supported. Per docs/pricing-policy.md:

    - MACROAREA 01 (quota fissa commerciale), UM 01 (€/year) -> fixed fee,
      UM 05 (€) -> one-off (added to the 12-month total).
    - MACROAREA 02 (quota variabile commerciale/energia), UM 03 (€/kWh) ->
      per-kWh extras.
    - MACROAREA 04 (spread) / 06 (renewable energy price), UM 03 (€/kWh)
      -> energy price (fixed offers) or spread (variable offers).
    - MACROAREA 05 (one-off), UM 05 (€) -> one-off.
    - MACROAREA 06, UM 01 (€/year) -> fixed fee (like 01).
    - UM 02 (€/kW/year) -> power fee, regardless of MACROAREA.
    - Any other combination is excluded and counted. ComponentiRegolate
      (CRPPE/CRPCV) are ignored by the caller before reaching here.
    """
    if unita_misura == UnitaMisura.EUR_KW_ANNO:
        return ComponentRole.POWER_FEE, None
    if (
        macroarea
        in (Macroarea.QUOTA_FISSA_COMMERCIALE, Macroarea.PREZZO_ENERGIA_RINNOVABILE)
        and unita_misura == UnitaMisura.EUR_ANNO
    ):
        return ComponentRole.FIXED_FEE, None
    if (
        macroarea in (Macroarea.QUOTA_FISSA_COMMERCIALE, Macroarea.ONE_OFF)
        and unita_misura == UnitaMisura.EUR_UNA_TANTUM
    ):
        return ComponentRole.ONE_OFF, None
    if (
        macroarea
        in (
            Macroarea.QUOTA_VENDITA_ENERGIA_SPREAD,
            Macroarea.PREZZO_ENERGIA_RINNOVABILE,
        )
        and unita_misura == UnitaMisura.EUR_KWH
    ):
        if price_type is PriceType.VARIABLE:
            return ComponentRole.SPREAD, None
        return ComponentRole.ENERGY_PRICE, None
    if (
        macroarea == Macroarea.QUOTA_VARIABILE_COMMERCIALE_ENERGIA
        and unita_misura == UnitaMisura.EUR_KWH
    ):
        return ComponentRole.PER_KWH_EXTRAS, None
    return None, (
        f"combinazione MACROAREA/UNITA_MISURA non supportata: "
        f"{macroarea!r}/{unita_misura!r}"
    )


def dispatching_component(
    tipo_dispacciamento: str, valore_disp: float | None
) -> tuple[str, float] | None:
    """Legacy helper kept for the unit tests that exercise it directly
    (see ``dispatching_component_v2`` for the parameters-driven pricing
    used by the parsers).
    """
    if valore_disp is None:
        return None
    if tipo_dispacciamento == _DISPBT_FIXED_FEE_CODE:
        return ComponentRole.FIXED_FEE, valore_disp
    return ComponentRole.PER_KWH_EXTRAS, valore_disp


#: TIPO_DISPACCIAMENTO codes 03..08 map 1:1 to a parameter name, applied
#: as €/kWh with losses (docs/pricing-policy.md dispatching table).
_DISPBT_PARAM_BY_CODE = {
    "03": "msd",
    "04": "modeol",
    "05": "uniess",
    "06": "terna",
    "07": "capprod",
    "08": "interr",
}

#: The six components that sum to Cdisp (TIPO_DISPACCIAMENTO == "01").
_CDISP_COMPONENTS = ("msd", "modeol", "uniess", "terna", "capprod", "interr")

#: The three Capacity Market monthly parameters averaged for code "09".
_CPTY_MRKT_PARAMS = ("cpty_mrkt_1", "cpty_mrkt_2", "cpty_mrkt_3")


@dataclass(frozen=True)
class DispatchingResult:
    """One TIPO_DISPACCIAMENTO row's contribution to an offer, already
    converted to the right unit. ``eur_kwh`` already includes losses where
    the dispatching table calls for them; the caller (parsers) must NOT
    apply losses again.
    """

    eur_kwh: float = 0.0
    eur_year: float = 0.0
    breakdown: dict[str, float] = field(default_factory=dict)
    approximate: bool = False


def dispatching_component_v2(
    tipo_dispacciamento: str,
    valore_disp: float | None,
    params: Parameters,
) -> tuple[DispatchingResult, None] | tuple[None, str]:
    """Classify+price one Dispacciamento row per docs/pricing-policy.md's
    dispatching table. Returns ``(result, None)`` or ``(None, reason)`` if
    the offer must be excluded (Maggior Tutela, a code reserved for
    non-domestic offers, a missing parameter, or an unknown code).

    This importer only ever prices domestic offers (TIPO_CLIENTE == "01"
    is excluded before dispatching is parsed -- see
    ``bestbill.arera.mlibero``/``bestbill.arera.placet``), so codes 11/12
    (rst/rstg, non-domestic only) always exclude the offer here; there is
    no non-domestic pricing branch to keep in sync.
    """
    code = tipo_dispacciamento
    factor = 1.0 + LOSSES

    if code in ("02", "10"):
        return None, MAGGIOR_TUTELA_REASON

    if code in ("11", "12"):
        return None, (
            f"TIPO_DISPACCIAMENTO {code!r} riservato a offerte non domestiche"
        )

    if code == "01":
        breakdown: dict[str, float] = {}
        for name in _CDISP_COMPONENTS:
            value = params.get(name)
            if value is None:
                return None, f"parametro {name!r} mancante"
            breakdown[name] = value
        cdisp = sum(breakdown.values())
        return DispatchingResult(eur_kwh=cdisp * factor, breakdown=breakdown), None

    if code in _DISPBT_PARAM_BY_CODE:
        name = _DISPBT_PARAM_BY_CODE[code]
        value = params.get(name)
        if value is None:
            return None, f"parametro {name!r} mancante"
        return (
            DispatchingResult(eur_kwh=value * factor, breakdown={name: value}),
            None,
        )

    if code == "09":
        breakdown = {}
        for name in _CPTY_MRKT_PARAMS:
            value = params.get(name)
            if value is None:
                return None, f"parametro {name!r} mancante"
            breakdown[name] = value
        mean_value = sum(breakdown.values()) / len(breakdown)
        return (
            DispatchingResult(
                eur_kwh=mean_value,
                breakdown={**breakdown, "mean": mean_value},
                approximate=True,
            ),
            None,
        )

    if code == _DISPBT_FIXED_FEE_CODE:  # "13"
        value = params.get("dispbt_d")
        if value is None:
            return None, "parametro 'dispbt_d' mancante"
        return DispatchingResult(eur_year=value, breakdown={"dispbt_d": value}), None

    if code == "14":
        value = params.get("cdispd")
        if value is None:
            return None, "parametro 'cdispd' mancante"
        return DispatchingResult(eur_kwh=value, breakdown={"cdispd": value}), None

    if code == "99":
        if valore_disp is None:
            return None, "VALORE_DISP mancante per TIPO_DISPACCIAMENTO 99"
        return (
            DispatchingResult(
                eur_kwh=valore_disp, breakdown={"valore_disp": valore_disp}
            ),
            None,
        )

    return None, f"TIPO_DISPACCIAMENTO non supportato: {code!r}"


def combine_dispatching(results: list[DispatchingResult]) -> DispatchingResult:
    """Combine several dispatching rows declared on one offer. They're
    additive by construction (no overlap, docs/pricing-policy.md).
    """
    eur_kwh = sum(r.eur_kwh for r in results)
    eur_year = sum(r.eur_year for r in results)
    breakdown: dict[str, float] = {}
    for r in results:
        breakdown.update(r.breakdown)
    approximate = any(r.approximate for r in results)
    return DispatchingResult(
        eur_kwh=eur_kwh, eur_year=eur_year, breakdown=breakdown, approximate=approximate
    )


def placet_domestic_dispatching(
    params: Parameters,
) -> tuple[DispatchingResult, None] | tuple[None, str]:
    """PLACET domestic dispatching (fixed and variable alike):
    ``dispbt_d`` €/year + ``cdispd`` €/kWh, no losses (ignore csed and
    cpstgd -- Servizio a Tutele Graduali only).
    """
    dispbt_d = params.get("dispbt_d")
    cdispd = params.get("cdispd")
    if dispbt_d is None:
        return None, "parametro 'dispbt_d' mancante"
    if cdispd is None:
        return None, "parametro 'cdispd' mancante"
    return (
        DispatchingResult(
            eur_kwh=cdispd,
            eur_year=dispbt_d,
            breakdown={"dispbt_d": dispbt_d, "cdispd": cdispd},
        ),
        None,
    )


def dispatching_identity_diff(params: Parameters) -> float | None:
    """``Cdisp + mean(cpty_mrkt_1..3) - cdispd``, or ``None`` if any
    required parameter is missing. Logged (and warned on, if over
    ``DISPATCHING_IDENTITY_TOLERANCE``) in the catalogue manifest.
    """
    cdisp_parts = [params.get(name) for name in _CDISP_COMPONENTS]
    cpty_parts = [params.get(name) for name in _CPTY_MRKT_PARAMS]
    cdispd = params.get("cdispd")
    if any(v is None for v in (*cdisp_parts, *cpty_parts, cdispd)):
        return None
    cdisp = sum(v for v in cdisp_parts if v is not None)
    mean_cpty = sum(v for v in cpty_parts if v is not None) / len(cpty_parts)
    assert cdispd is not None
    return cdisp + mean_cpty - cdispd


def discount_is_priced(validity: DiscountValidity, conditional: bool) -> bool:
    """Only unconditional discounts valid on entry or within the first 12
    months are priced into the annual estimate; beyond-12-months and
    conditional discounts are display-only.
    """
    if conditional:
        return False
    return validity in (DiscountValidity.ON_ENTRY, DiscountValidity.WITHIN_12_MONTHS)


def sconto_validita_to_model(code: str) -> DiscountValidity:
    return {
        ScontoValidita.ALLINGRESSO: DiscountValidity.ON_ENTRY,
        ScontoValidita.ENTRO_12_MESI: DiscountValidity.WITHIN_12_MONTHS,
        ScontoValidita.OLTRE_12_MESI: DiscountValidity.BEYOND_12_MONTHS,
    }[ScontoValidita(code)]


_UNITA_TO_DISCOUNT_UNIT = {
    UnitaMisura.EUR_ANNO: DiscountUnit.EUR_YEAR,
    UnitaMisura.EUR_KW_ANNO: DiscountUnit.EUR_KW_YEAR,
    UnitaMisura.EUR_KWH: DiscountUnit.EUR_KWH,
    UnitaMisura.EUR_SMC: DiscountUnit.EUR_SMC,
    UnitaMisura.EUR_UNA_TANTUM: DiscountUnit.EUR_ONE_OFF,
    UnitaMisura.PERCENTO: DiscountUnit.PERCENT,
}


def unita_misura_to_discount_unit(code: str) -> DiscountUnit:
    return _UNITA_TO_DISCOUNT_UNIT[UnitaMisura(code)]


def discount_nominal_to_pre_vat(amount: float, iva_sconto_code: str | None) -> float:
    """Convert a Sconto/PrezziSconto amount to pre-VAT: IVA_SCONTO "02"
    (post-VAT) amounts are divided by ``1 + VAT_DOMESTIC``; IVA_SCONTO
    "01" (already pre-VAT) amounts are returned unchanged. This is the
    ONLY place VAT_DOMESTIC is used (docs/pricing-policy.md §6).
    """
    if iva_sconto_code == "02":
        return amount / (1.0 + VAT_DOMESTIC)
    return amount


def discount_kwh_base(
    discount: Discount,
    total_kwh: float,
    monthly_kwh: list[float] | None,
) -> float:
    """The kWh amount a per-kWh (``EUR_KWH``) discount actually applies
    to: ``total_kwh`` restricted to the discount's consumption band
    (``consumption_from_kwh``/``consumption_to_kwh``, ARERA PrezziSconto
    VALIDO_DA/VALIDO_FINO) and/or to its first ``duration_months`` months
    (ARERA Sconto/PeriodoValidita/DURATA), if set. ``monthly_kwh`` is the
    12-month profile's total kWh per month, in chronological order (the
    engine's "next 12 months" assumption -- see
    ``bestbill.core.calculator``); required only when ``duration_months``
    is set.
    """
    kwh = total_kwh
    if discount.duration_months is not None and monthly_kwh is not None:
        months = min(discount.duration_months, len(monthly_kwh))
        kwh = sum(monthly_kwh[:months])
    lower = discount.consumption_from_kwh or 0.0
    upper = (
        discount.consumption_to_kwh
        if discount.consumption_to_kwh is not None
        else float("inf")
    )
    return max(0.0, min(kwh, upper) - lower)


def discount_annual_value_eur(
    discount: Discount,
    total_kwh: float,
    energy_base_eur: float,
    monthly_kwh: list[float] | None = None,
) -> float:
    """The annual euro value of a priced discount (0 if it isn't priced).

    ``energy_base_eur`` is the base a percent discount (UNITA_MISURA 06)
    applies to: for a fixed offer this is the energy-price part only
    (Σ MACROAREA 04/06); for a variable offer it's PUN×1.10 + spread,
    summed over the year (docs/pricing-policy.md §6). ``monthly_kwh`` is
    only used for ``EUR_KWH`` discounts with a ``duration_months``
    restriction -- see ``discount_kwh_base``.
    """
    if not discount_is_priced(discount.validity, discount.conditional):
        return 0.0
    if discount.unit in (DiscountUnit.EUR_YEAR, DiscountUnit.EUR_ONE_OFF):
        return discount.amount
    if discount.unit is DiscountUnit.EUR_KWH:
        return discount.amount * discount_kwh_base(discount, total_kwh, monthly_kwh)
    if discount.unit is DiscountUnit.PERCENT:
        return energy_base_eur * discount.amount / 100.0
    # EUR_KW_YEAR / EUR_SMC discounts are not meaningful for an EE-only
    # estimate; keep them display-only rather than guess.
    return 0.0


def tiered_annual_value_eur(tiers: list[ConsumptionTier], kwh: float) -> float:
    """Marginal (tax-bracket-style) sum of ``price_i × overlap(kwh, tier_i)``
    over every tier -- see ``ConsumptionTier``.
    """
    total = 0.0
    for tier in tiers:
        upper = tier.to_kwh if tier.to_kwh is not None else float("inf")
        overlap = max(0.0, min(kwh, upper) - tier.from_kwh)
        total += overlap * tier.price_eur_kwh
    return total


def band_value_eur(
    flat_price: float,
    tiers: list[ConsumptionTier] | None,
    kwh: float,
) -> float:
    """A band's annual €: the flat price times ``kwh`` PLUS the marginal
    value of any consumption tiers layered on top (both can coexist --
    e.g. a flat base rate plus a tiered surcharge above a threshold; see
    the 000670* sample offers in docs/arera-data.md).
    """
    value = flat_price * kwh
    if tiers:
        value += tiered_annual_value_eur(tiers, kwh)
    return value


#: Reason for consumption-tiered (CONSUMO_DA/CONSUMO_A) prices this
#: importer can't price unambiguously: overlapping tiers, or tiers on a
#: component role other than energy price/spread (per-kWh extras aren't
#: banded in the model, and fixed fees/power fees/one-off fees aren't
#: kWh-scaled at all -- see docs/arera-data.md).
UNSUPPORTED_TIERED_PRICE_REASON = "prezzi a scaglioni non supportati"


def build_consumption_tiers(
    rows: list[tuple[float, float | None, float]],
) -> tuple[list[ConsumptionTier], None] | tuple[None, str]:
    """Build a validated, sorted marginal tier schedule from raw
    ``(CONSUMO_DA, CONSUMO_A, PREZZO)`` rows on one ComponenteImpresa
    band. Tiers must not overlap (``None``/very large ``CONSUMO_A``
    sentinels mean unbounded); overlapping or otherwise inconsistent rows
    return ``UNSUPPORTED_TIERED_PRICE_REASON`` rather than guess.
    """
    ordered = sorted(rows, key=lambda r: r[0])
    tiers: list[ConsumptionTier] = []
    previous_to = 0.0
    for from_kwh, to_kwh, price in ordered:
        if from_kwh < previous_to:
            return None, UNSUPPORTED_TIERED_PRICE_REASON
        try:
            tiers.append(
                ConsumptionTier(from_kwh=from_kwh, to_kwh=to_kwh, price_eur_kwh=price)
            )
        except ValueError:
            return None, UNSUPPORTED_TIERED_PRICE_REASON
        previous_to = to_kwh if to_kwh is not None else float("inf")
    return tiers, None
