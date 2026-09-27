"""Money arithmetic. Pure, no database, no I/O.

These are the tests that matter most in the project, because a rounding error
here is not a display glitch - it is a customer charged the wrong amount and an
invoice that does not reconcile. They are deliberately exhaustive over the small
numbers where rounding actually misbehaves, because the large numbers are the
ones people test and the off-by-one-paise is the one that reaches a customer.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.services.pricing import (
    add_tax_exclusive,
    allocate_tax_across_lines,
    extract_tax_from_inclusive,
    format_rate_bps,
    quote_shipping,
    rate_to_bps,
    rupees_to_minor,
    split_tax,
    spread_discount,
)


class TestConversion:
    @pytest.mark.parametrize(
        ("rupees", "expected"),
        [
            (99.00, 9900),
            (4999.00, 499900),
            (0.1, 10),
            (1, 100),
            (0, 0),
            (123.45, 12345),
            (0.07, 7),
            # 8.115 * 100 is 811.4999999999999 in binary floating point. Parsed as
            # a decimal literal it is exactly 811.5, which rounds half-up to 812.
            # This is the exact case that makes the Decimal(str(x)) conversion
            # non-optional.
            (8.115, 812),
            (1.005, 101),
            (2.675, 268),
        ],
    )
    def test_rupees_to_minor(self, rupees: float, expected: int) -> None:
        assert rupees_to_minor(rupees) == expected

    def test_rupees_to_minor_accepts_strings_exactly(self) -> None:
        assert rupees_to_minor("99.00") == 9900
        assert rupees_to_minor("0.1") == 10
        assert rupees_to_minor(Decimal("8.115")) == 812

    def test_conversion_never_uses_float_arithmetic(self) -> None:
        """Prove the float path would have been wrong, so the test has teeth."""
        # 1.005 is 1.00499999999999989... in binary, so the float product is
        # 100.49999999999999 and rounds to 100. Parsed as the decimal literal a
        # human typed, it is exactly 100.5 and rounds half-up to 101.
        assert round(1.005 * 100) == 100
        assert rupees_to_minor(1.005) == 101
        assert rupees_to_minor(1.005) != round(1.005 * 100)

    def test_negative_amounts_are_representable(self) -> None:
        """Refunds and credit notes need negatives; the display must keep the sign."""
        from app.schemas.common import format_minor

        assert format_minor(-500) == "-Rs.5"
        assert format_minor(0) == "Rs.0"

    @pytest.mark.parametrize(
        ("rate", "bps"),
        [(0.18, 1800), (0.05, 500), (0.12, 1200), (0.0, 0), (1.0, 10000), (0.28, 2800)],
    )
    def test_rate_to_bps(self, rate: float, bps: int) -> None:
        assert rate_to_bps(rate) == bps

    def test_rate_rejects_negative(self) -> None:
        from app.core.errors import ValidationError

        with pytest.raises(ValidationError):
            rate_to_bps(-0.18)

    @pytest.mark.parametrize(
        ("bps", "text"), [(1800, "18"), (1200, "12"), (500, "5"), (1850, "18.5"), (0, "0")]
    )
    def test_format_rate_bps(self, bps: int, text: str) -> None:
        assert format_rate_bps(bps) == text


class TestInclusiveTax:
    """GST inside the price. The Indian retail default, and the easy one to get wrong."""

    def test_worked_example(self) -> None:
        # 152542 paise of tax-inclusive goods at 18%.
        # 152542 * 1800 / 11800 = 23269.11...  ->  23269
        assert extract_tax_from_inclusive(152542, 1800) == 23269

    def test_net_plus_tax_equals_gross(self) -> None:
        """The property that actually matters on an invoice."""
        for gross in range(0, 60000, 977):  # prime-ish steps so it is not all round
            tax = extract_tax_from_inclusive(gross, 1800)
            net = gross - tax
            assert 0 <= tax <= gross, "tax can never exceed the gross it sits inside"
            assert net >= 0

    def test_zero_and_negative_inputs(self) -> None:
        assert extract_tax_from_inclusive(0, 1800) == 0
        assert extract_tax_from_inclusive(1000, 0) == 0

    def test_tax_is_monotonic(self) -> None:
        previous = -1
        for gross in range(0, 200000, 1000):
            current = extract_tax_from_inclusive(gross, 1800)
            assert current >= previous, "a bigger price cannot produce less tax"
            previous = current

    def test_inclusive_is_never_confused_with_exclusive(self) -> None:
        """The two modes must never return the same number by accident.

        This is the double-charge guard: if these ever converge, the
        `tax_inclusive` flag on an order stops meaning anything.
        """
        for base in (10000, 55555, 152542, 999999):
            inclusive = extract_tax_from_inclusive(base, 1800)
            exclusive = add_tax_exclusive(base, 1800)
            assert inclusive < exclusive, (
                f"base={base}: inclusive extraction ({inclusive}) must be less than "
                f"an on-top addition ({exclusive})"
            )


class TestExclusiveTax:
    def test_worked_example(self) -> None:
        assert add_tax_exclusive(100000, 1800) == 18000

    def test_rounds_half_up(self) -> None:
        # All values in paise. 100 paise at 18% is exactly 18.
        assert add_tax_exclusive(100, 1800) == 18
        # 1 paise at 18% is 0.18 -> 0, and must not become 1.
        assert add_tax_exclusive(1, 1800) == 0
        # 3 paise at 18% is 0.54 -> 1.
        assert add_tax_exclusive(3, 1800) == 1
        # 8 paise at 18% is 1.44 -> 1.
        assert add_tax_exclusive(8, 1800) == 1
        # 14 paise at 18% is 2.52 -> 3.
        assert add_tax_exclusive(14, 1800) == 3

    def test_zero_inputs(self) -> None:
        assert add_tax_exclusive(0, 1800) == 0
        assert add_tax_exclusive(1000, 0) == 0


class TestTaxSplit:
    @pytest.mark.parametrize("total", [1, 2, 3, 7, 99, 101, 47943, 47944, 47945, 999999])
    def test_halves_always_re_sum_to_the_total(self, total: int) -> None:
        """A GST invoice whose halves do not add to the printed total is rejected."""
        igst, cgst, sgst = split_tax(total, "INTRA_STATE")
        assert igst == 0
        assert cgst + sgst == total, f"{cgst} + {sgst} != {total}"

    @pytest.mark.parametrize("total", [1, 2, 3, 7, 99, 101, 47943, 47944, 47945])
    def test_inter_state_is_all_igst(self, total: int) -> None:
        igst, cgst, sgst = split_tax(total, "INTER_STATE")
        assert (igst, cgst, sgst) == (total, 0, 0)

    def test_zero(self) -> None:
        assert split_tax(0, "INTRA_STATE") == (0, 0, 0)
        assert split_tax(-5, "INTRA_STATE") == (0, 0, 0)


class TestDiscountDistribution:
    @pytest.mark.parametrize("discount", [1, 2, 3, 7, 99, 100, 333, 10001, 99999])
    @pytest.mark.parametrize(
        "line_totals",
        [[100], [1, 1, 1], [100, 200, 333], [0, 0, 500], [12345], [7, 7, 7, 7, 7], [1, 99999]],
    )
    def test_distribution_conserves_every_paisa(
        self, discount: int, line_totals: list[int]
    ) -> None:
        """A refund computed from a line's share must reconcile with the order."""
        parts = spread_discount(discount, line_totals)
        assert sum(parts) == discount, (
            f"discount {discount} over {line_totals} produced {parts}, "
            f"which sums to {sum(parts)}"
        )
        assert all(p >= 0 for p in parts), "no line may be credited a negative discount"

    def test_no_discount_is_all_zeroes(self) -> None:
        assert spread_discount(0, [100, 200]) == [0, 0]
        assert spread_discount(-5, [100, 200]) == [0, 0]

    def test_empty_lines(self) -> None:
        assert spread_discount(100, []) == []

    def test_discount_larger_than_goods_is_clamped_upstream(self) -> None:
        # spread_discount assumes the caller clamped. Document that by showing
        # the total is preserved even when it exceeds the goods, which is why
        # compute_totals clamps first.
        parts = spread_discount(500, [100, 200])
        assert sum(parts) == 500


class TestLineTaxAllocation:
    def _totals(self, tax_total: int = 18000, subtotal: int = 100000):
        from app.services.pricing import Totals

        return Totals(
            subtotal=subtotal,
            discount_total=0,
            shipping_total=0,
            tax_total=tax_total,
            total=subtotal,
            taxable_amount=subtotal,
            tax_rate_bps=1800,
            tax_inclusive=True,
            tax_split_mode="INTRA_STATE",
            igst=0,
            cgst=tax_total // 2,
            sgst=tax_total - tax_total // 2,
            item_count=2,
        )

    def test_two_lines_split_proportionally(self) -> None:
        parts = allocate_tax_across_lines([50000, 50000], self._totals())
        assert parts == [9000, 9000]
        assert sum(parts) == 18000

    def test_the_whole_tax_is_not_given_to_every_line(self) -> None:
        """Regression: the single-line version handed the full tax to each line,
        so a two-line invoice printed double the GST."""
        parts = allocate_tax_across_lines([50000, 50000], self._totals())
        assert all(p < 18000 for p in parts), (
            f"each line got the entire order tax: {parts}"
        )
        assert sum(parts) == 18000

    def test_uneven_split_conserves_the_total(self) -> None:
        totals = self._totals(tax_total=47943)  # deliberately odd
        parts = allocate_tax_across_lines([33333, 33333, 33334], totals)
        assert sum(parts) == 47943
        assert all(p >= 0 for p in parts)

    def test_zero_order_allocates_nothing(self) -> None:
        assert allocate_tax_across_lines([0, 0], self._totals(tax_total=0)) == [0, 0]
        assert allocate_tax_across_lines([], self._totals()) == []


class TestShippingQuote:
    def test_flat_rate_applied_below_the_threshold(self) -> None:
        from app.core.config import Settings

        settings = Settings(shipping_flat_rate=99.00, shipping_free_above=4999.00)
        quote = quote_shipping(settings=settings, subtotal_after_discount=100000)
        assert quote.total == 9900
        assert quote.free_applied is False

    def test_free_above_the_threshold(self) -> None:
        from app.core.config import Settings

        settings = Settings(shipping_flat_rate=99.00, shipping_free_above=4999.00)
        quote = quote_shipping(settings=settings, subtotal_after_discount=499900)
        assert quote.total == 0
        assert quote.free_applied is True

    def test_exactly_at_the_threshold_is_free(self) -> None:
        from app.core.config import Settings

        settings = Settings(shipping_flat_rate=99.00, shipping_free_above=4999.00)
        quote = quote_shipping(settings=settings, subtotal_after_discount=499900)
        assert quote.total == 0, "hitting the threshold exactly should ship free"

    def test_zero_threshold_never_ships_free(self) -> None:
        from app.core.config import Settings

        settings = Settings(shipping_flat_rate=99.00, shipping_free_above=0)
        quote = quote_shipping(settings=settings, subtotal_after_discount=10_000_000)
        assert quote.total == 9900
        assert quote.free_applied is False

    def test_zero_flat_rate_means_pickup_only(self) -> None:
        from app.core.config import Settings

        settings = Settings(shipping_flat_rate=0, shipping_free_above=0)
        quote = quote_shipping(settings=settings, subtotal_after_discount=100000)
        assert quote.total == 0
