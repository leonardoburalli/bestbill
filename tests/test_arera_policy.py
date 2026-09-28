import pytest

from bestbill.arera import policy
from bestbill.core.models import Discount, DiscountUnit, DiscountValidity, PriceType


def test_classify_component_fixed_fee():
    role, reason = policy.classify_component("01", "01", PriceType.FIXED)
    assert role == policy.ComponentRole.FIXED_FEE
    assert reason is None


def test_classify_component_energy_price_for_fixed():
    role, reason = policy.classify_component("04", "03", PriceType.FIXED)
    assert role == policy.ComponentRole.ENERGY_PRICE


def test_classify_component_spread_for_variable():
    role, reason = policy.classify_component("04", "03", PriceType.VARIABLE)
    assert role == policy.ComponentRole.SPREAD


def test_classify_component_macroarea_06_same_as_04():
    fixed_role, _ = policy.classify_component("06", "03", PriceType.FIXED)
    variable_role, _ = policy.classify_component("06", "03", PriceType.VARIABLE)
    assert fixed_role == policy.ComponentRole.ENERGY_PRICE
    assert variable_role == policy.ComponentRole.SPREAD


def test_classify_component_extras():
    role, _ = policy.classify_component("02", "03", PriceType.FIXED)
    assert role == policy.ComponentRole.PER_KWH_EXTRAS


def test_classify_component_one_off():
    role, _ = policy.classify_component("05", "05", PriceType.FIXED)
    assert role == policy.ComponentRole.ONE_OFF


def test_classify_component_macroarea_01_one_off():
    role, _ = policy.classify_component("01", "05", PriceType.FIXED)
    assert role == policy.ComponentRole.ONE_OFF


def test_classify_component_macroarea_06_fixed_fee():
    role, _ = policy.classify_component("06", "01", PriceType.FIXED)
    assert role == policy.ComponentRole.FIXED_FEE


def test_classify_component_power_fee_regardless_of_macroarea():
    role, _ = policy.classify_component("04", "02", PriceType.FIXED)
    assert role == policy.ComponentRole.POWER_FEE


def test_classify_component_unsupported_combo_excluded():
    role, reason = policy.classify_component("99", "03", PriceType.FIXED)
    assert role is None
    assert "non supportata" in reason


def test_dispatching_ignored_without_value():
    assert policy.dispatching_component("01", None) is None


def test_dispatching_included_with_value():
    role, amount = policy.dispatching_component("99", 0.011)
    assert role == policy.ComponentRole.PER_KWH_EXTRAS
    assert amount == 0.011


def test_dispatching_code_13_is_fixed_fee():
    role, amount = policy.dispatching_component("13", 25.0)
    assert role == policy.ComponentRole.FIXED_FEE
    assert amount == 25.0


def test_idx_support():
    assert policy.idx_is_supported("12")
    assert policy.idx_is_supported("01")
    assert not policy.idx_is_supported("08")
    assert not policy.idx_is_supported("05")


def test_tipologia_fasce_support():
    assert policy.tipologia_fasce_is_supported("01")
    assert policy.tipologia_fasce_is_supported("03")
    assert policy.tipologia_fasce_is_supported("91")
    assert not policy.tipologia_fasce_is_supported("07")


def test_discount_priced_unconditional_on_entry_or_within_12():
    assert policy.discount_is_priced(DiscountValidity.ON_ENTRY, conditional=False)
    assert policy.discount_is_priced(
        DiscountValidity.WITHIN_12_MONTHS, conditional=False
    )


def test_discount_not_priced_beyond_12_months():
    assert not policy.discount_is_priced(
        DiscountValidity.BEYOND_12_MONTHS, conditional=False
    )


def test_discount_not_priced_if_conditional():
    assert not policy.discount_is_priced(DiscountValidity.ON_ENTRY, conditional=True)


def test_discount_annual_value_eur_year():
    d = Discount(
        name="x",
        validity=DiscountValidity.ON_ENTRY,
        conditional=False,
        amount=50.0,
        unit=DiscountUnit.EUR_YEAR,
    )
    assert (
        policy.discount_annual_value_eur(d, total_kwh=1000, energy_base_eur=200) == 50.0
    )


def test_discount_annual_value_eur_kwh():
    d = Discount(
        name="x",
        validity=DiscountValidity.WITHIN_12_MONTHS,
        conditional=False,
        amount=0.01,
        unit=DiscountUnit.EUR_KWH,
    )
    assert (
        policy.discount_annual_value_eur(d, total_kwh=1000, energy_base_eur=200) == 10.0
    )


def test_discount_annual_value_percent():
    d = Discount(
        name="x",
        validity=DiscountValidity.ON_ENTRY,
        conditional=False,
        amount=10.0,
        unit=DiscountUnit.PERCENT,
    )
    assert (
        policy.discount_annual_value_eur(d, total_kwh=1000, energy_base_eur=200) == 20.0
    )


def test_discount_annual_value_zero_when_not_priced():
    d = Discount(
        name="x",
        validity=DiscountValidity.BEYOND_12_MONTHS,
        conditional=False,
        amount=999.0,
        unit=DiscountUnit.EUR_YEAR,
    )
    assert (
        policy.discount_annual_value_eur(d, total_kwh=1000, energy_base_eur=200) == 0.0
    )


def test_losses_mode_fixed_offers_never_get_losses():
    from bestbill.core.models import LossesMode, OfferSource

    assert policy.losses_mode(OfferSource.PLACET, PriceType.FIXED) is LossesMode.NONE
    assert policy.losses_mode(OfferSource.MLIBERO, PriceType.FIXED) is LossesMode.NONE


def test_losses_mode_mlibero_variable_is_index_only():
    from bestbill.core.models import LossesMode, OfferSource

    assert (
        policy.losses_mode(OfferSource.MLIBERO, PriceType.VARIABLE)
        is LossesMode.INDEX_ONLY
    )


def test_losses_mode_placet_variable_is_index_and_spread():
    from bestbill.core.models import LossesMode, OfferSource

    assert (
        policy.losses_mode(OfferSource.PLACET, PriceType.VARIABLE)
        is LossesMode.INDEX_AND_SPREAD
    )


def test_idx_maggior_tutela():
    assert policy.idx_is_maggior_tutela("05")
    assert not policy.idx_is_maggior_tutela("12")


def test_discount_nominal_to_pre_vat_converts_post_vat():
    assert policy.discount_nominal_to_pre_vat(11.0, "02") == pytest.approx(10.0)


def test_discount_nominal_to_pre_vat_keeps_pre_vat_unchanged():
    assert policy.discount_nominal_to_pre_vat(10.0, "01") == 10.0
    assert policy.discount_nominal_to_pre_vat(10.0, None) == 10.0
