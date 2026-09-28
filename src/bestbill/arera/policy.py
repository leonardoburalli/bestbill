"""THE single place for uncertain ARERA pricing rules.

Every rule here is provisional until verified against the AU "Regole per il
calcolo della spesa annua stimata" v4.0 PDF (see docs/arera-data.md). Parsers
(:mod:`bestbill.arera.placet`, :mod:`bestbill.arera.mlibero`) call into this
module instead of hard-coding pricing decisions, so a single review can
adjust every rule without touching parser code.

Open questions for the pricing-semantics review (flag in the PR):
- Network losses (LOSSES): applied to (index + spread) for variable offers
  and to the energy price for fixed offers, for both PLACET and mercato
  libero. Verify per source/price_type combination.
- Percent-unit discounts (``DiscountUnit.PERCENT``): the sample data has at
  least one PREZZO of ``100`` under UNITA_MISURA ``06`` (%), which looks
  like a data-quality issue rather than a "100% discount" -- verify the
  intended semantics before trusting this branch in production.
- Dispatching regulated-value codes (01, 02, 14, ...) are ignored unless a
  VALORE_DISP is present, on the assumption that ARERA-regulated values are
  identical across suppliers and therefore don't change the ranking (same
  rationale as network/system charges in PLAN.md §5). If VALORE_DISP is
  absent for those codes, no charge is priced for that dispatching row.
- MACROAREA 02 ("quota variabile commerciale/energia"): the task brief's
  provisional default routes it to per_kwh_extras, but at least one real
  fixed offer names its MACROAREA 02 component "Sales Price" / "Prezzo
  Energia" and it is clearly meant to be the energy price (with no other
  energy-price component on that offer, it is currently excluded as
  "prezzi energia incompleti"). Kept as per_kwh_extras per the brief
  pending the PDF review; flagged here so the reviewer can decide whether
  MACROAREA 02 should route like 04/06 instead (see docs/arera-data.md
  "Observed findings").
"""

from __future__ import annotations

from bestbill.arera.codes import (
    Macroarea,
    ScontoValidita,
    TipologiaFasce,
    UnitaMisura,
)
from bestbill.core.models import (
    Discount,
    DiscountUnit,
    DiscountValidity,
    OfferSource,
    PriceType,
)

#: Network losses applied at low voltage, art. 13.2 methodology (see
#: docs/arera-data.md "Methodology points"). Provisional: applied to energy
#: terms only (index/price + spread), never to fees or extras.
LOSSES = 0.10

#: ARERA reference domestic customer ("cliente tipo").
REFERENCE_CONSUMPTION_KWH = 2700.0
REFERENCE_POWER_KW = 3.0

#: Plausibility gate for the pricing sanity check in catalog/validate.py.
PLAUSIBLE_MIN_EUR = 100.0
PLAUSIBLE_MAX_EUR = 5000.0

#: Sanity gate on the day-to-day change in included-offer counts.
COUNT_CHANGE_TOLERANCE = 0.30

#: IDX_PREZZO_ENERGIA codes we can price (PUN monthly).
SUPPORTED_IDX_CODES = frozenset({"12"})

#: TIPOLOGIA_FASCE codes we can price.
SUPPORTED_TIPOLOGIA_FASCE = frozenset(
    {TipologiaFasce.MONO, TipologiaFasce.F1F2F3, TipologiaFasce.F1F23}
)

#: TIPO_DISPACCIAMENTO code meaning a €/year fixed fee rather than €/kWh.
_DISPBT_FIXED_FEE_CODE = "13"


def losses_applied_to_energy(source: OfferSource, price_type: PriceType) -> bool:
    """Whether the engine should multiply this offer's energy terms by
    (1 + LOSSES). Provisional default: yes, for every ARERA source and
    price type (see module docstring). Custom (legacy Excel) offers never
    call this function and keep their historical, loss-free pricing.
    """
    del source, price_type  # provisional: same for every combination today
    return True


def idx_is_supported(idx_code: str) -> bool:
    return idx_code in SUPPORTED_IDX_CODES


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
    not supported.
    """
    if unita_misura == UnitaMisura.EUR_KW_ANNO:
        return ComponentRole.POWER_FEE, None
    if (
        macroarea == Macroarea.QUOTA_FISSA_COMMERCIALE
        and unita_misura == UnitaMisura.EUR_ANNO
    ):
        return ComponentRole.FIXED_FEE, None
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
    if macroarea == Macroarea.ONE_OFF and unita_misura == UnitaMisura.EUR_UNA_TANTUM:
        return ComponentRole.ONE_OFF, None
    return None, (
        f"combinazione MACROAREA/UNITA_MISURA non supportata: "
        f"{macroarea!r}/{unita_misura!r}"
    )


def dispatching_component(
    tipo_dispacciamento: str, valore_disp: float | None
) -> tuple[str, float] | None:
    """Classify a Dispacciamento row. Returns ``(role, amount)`` to add to
    the offer, or ``None`` if it should be ignored (a regulated-value code
    with no VALORE_DISP given -- see module docstring).
    """
    if valore_disp is None:
        return None
    if tipo_dispacciamento == _DISPBT_FIXED_FEE_CODE:
        return ComponentRole.FIXED_FEE, valore_disp
    return ComponentRole.PER_KWH_EXTRAS, valore_disp


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


def discount_annual_value_eur(
    discount: Discount, total_kwh: float, energy_cost_eur: float
) -> float:
    """The annual euro value of a priced discount (0 if it isn't priced).
    See the module docstring for the percent-unit caveat.
    """
    if not discount_is_priced(discount.validity, discount.conditional):
        return 0.0
    if discount.unit in (DiscountUnit.EUR_YEAR, DiscountUnit.EUR_ONE_OFF):
        return discount.amount
    if discount.unit is DiscountUnit.EUR_KWH:
        return discount.amount * total_kwh
    if discount.unit is DiscountUnit.PERCENT:
        return energy_cost_eur * discount.amount / 100.0
    # EUR_KW_YEAR / EUR_SMC discounts are not meaningful for an EE-only
    # estimate; keep them display-only rather than guess.
    return 0.0
