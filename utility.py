""" A module with free methods and extensions to third-party classes.

Used throughout the application, without any dependency on any other
modules.
"""

import collections
from decimal import Decimal
from moneyed import Money as PyMoney


class Money(PyMoney):
    """ Extends py-moneyed to support Decimal-like functions. """

    default_currency = 'CAD'

    def __init__(self, amount=Decimal('0.0'), currency=None):
        """ Initializes with application-level default currency.

        Also allows for initializing from another Money object.
        """
        if isinstance(amount, Money):
            super().__init__(amount.amount, amount.currency)
        elif currency is None:
            super().__init__(amount, self.default_currency)
        else:
            super().__init__(amount, currency)

    def __round__(self, ndigits=None):
        """ Rounds to ndigits """
        return Money(round(self.amount, ndigits), self.currency)

    def __hash__(self):
        """ Allows for use in sets and as dict keys. """
        # Equality of Money objects is based on amount and currency.
        return hash(self.amount) + hash(self.currency)

    def __eq__(self, other):
        """ Extends == operator to allow comparison with Decimal.

        This allows for comparison to 0 (or other Decimal-convertible
        values), but not with other Money objects in different
        currencies.
        """
        # NOTE: If the other object is also a Money object, this
        # won't fall back to Decimal, because Decimal doesn't know how
        # to compare itself to Money. This is good, because otherwise
        # we'd be comparing face values of different currencies,
        # yielding incorrect behaviour like JPY1 == USD1.
        return super().__eq__(other) or self.amount == other

    def __lt__(self, other):
        """ Extends < operator to allow comparison with 0 """
        if other == 0:
            return self.amount < 0
        else:
            return super().__lt__(other)

    def __gt__(self, other):
        """ Extends > operator to allow comparison with 0 """
        if other == 0:
            return self.amount > 0
        else:
            return super().__gt__(other)


def when_conv(when):
    """ Converts various types of `when` inputs to Decimal.

    The Decimal value is in [0,1], where 0 is the start of the period
    and 1 is the end.

    NOTE: `numpy` defines its `when` argument such that 'end' = 0 and
    'start' = 1. If you're using that package, consider whether any
    conversions are necessary.

    Args:
        `when` (float, Decimal, str): The timing of the transaction.
            Must be in the range [0,1] or in ('start', 'end').

    Raises:
        decimal.InvalidOperation: `when` must be convertible to
            type Decimal
        ValueError: `when` must be in [0,1]

    Returns:
        A Decimal in [0,1]
    """
    # Attempt to convert strings 'start' and 'end' first
    if isinstance(when, str):
        if when == 'end':
            when = 1
        elif when == 'start':
            when = 0

    # Decimal can take a variety of input types (including str), so
    # rather than throw an error on non-start/end input strings, try
    # to cast to Decimal and throw a decimal.InvalidOperation error.
    when = Decimal(when)

    if when > 1 or when < 0:
        raise ValueError("When: 'when' must be in [0,1]")

    return when


def nearest_year(vals, year):
    """ Finds the nearest (past) year to `year` in `vals`.

    This is a companion method to `inflation_adjust()`. It's meant to be
    used when you want to pull a value out of an incomplete dict without
    inflation-adjusting it (e.g. when you want to grab the most recent
    percentage rate from a dict of `{year: Decimal}` pairs.)

    If `year` is in `vals`, then this method returns `year`.
    If not, then this method tries to find the last year
    before `year` that is in `vals`. If that doesn't work, then this
    method tries to find the first year in `vals` following `year`.

    Returns:
        A year in `vals` is near to `year`, preferring
        the nearest preceding year (if it exists) over the nearest
        following year. Returns `None` if `vals` is empty.
    """
    if vals == {}:
        return None

    # If the year is explicitly represented, no need to inflation-adjust
    if year in vals:
        return year

    # Look for the most recent year prior to `year` that's in vals
    key = max((k for k in vals if k < year), default=None)

    # If that didn't work, look for the closest following year.
    if key is None:
        key = min((k for k in vals if k > year), default=None)

    return key


def extend_inflation_adjusted(vals, inflation_adjust, target_year):
    """ Fills in partial time-series with inflation-adjusted values.

    This method is targeted at inflation-adjusting input data (e.g.
    as found in the Constants module), which tends to be incomplete
    and can represent non-sequential years. New years are often entered
    when something changes (i.e. when values change in real terms), so
    this method prefers to infer inflation-adjusted values based on the
    most recent *past* years when possible (since future years might
    not be comparable).

    If `target_year` is in `vals`, then this method returns the value
    for `target_year` in `vals` without further inflation-adjusting
    (as that value is already in nominal terms).

    If `target_year` is not in `vals`, then this method attempts to
    interpolate an inflation-adjusted value based on the last year in
    `vals` before `target_year` or, if no such year exists, based on the
    first year in `vals` after `target_year`.

    If the values of `vals` are dicts or other iterable, this method
    returns a dict or other iterable with values that have each been
    inflation-adjusted.

    Args:
        vals (dict): A dict of `{year: val}` pairs, where `val` is a
            scalar, list, or dict. This dict may be incomplete, in the
            sense that some years may not be represented.
            If `val` is non-scalar, an object of the same type is
            returned with each of its values inflation-adjusted.
        inflation_adjust: A method of the form
            `inflation_adjust(val, this_year, target_year)` that finds a
            nominal value in `target_year` with the same real value as
            nominal value `val` in `this_year`.
        year (int): The year for which an adjusted value is to be
            generated.
    """
    # If the year is explicitly represented, no need to inflation-adjust
    if target_year in vals:
        return vals[target_year]

    # Look for the most recent year prior to `year`
    this_year = nearest_year(vals, target_year)

    # TODO: Update following to use the method instead.
    # If one of the above searches worked, return an inflation-adjusted
    # value (or dict/list of values, depending on what the values of
    # `vals` are)
    if this_year != target_year:
        val = vals[this_year]
        if isinstance(val, dict):
            return {
                k: inflation_adjust(val[k], this_year, target_year)
                for k in val
            }
        elif isinstance(val, collections.Iterable):
            return type(val)(
                inflation_adjust(v, this_year, target_year) for v in val
            )
        else:
            return inflation_adjust(val, this_year, target_year)
    # If none of the above searches for a year worked, raise an error.
    else:
        raise ValueError('inflation_adjust: No year is in both vals and ' +
                         'inflation_adjustment')


def build_inflation_adjust(inflation_adjust=None):
    """ Generates an inflation_adjust method.

    If inflation_adjust is not provided, all values are assumed to be in
    real terms, the returned method will return its argument `val`
    without inflation adjustment.

    Args:
        inflation_adjust: May be a dict of {year: inflation_adjustment}
            pairs, where `inflation_adjustment` is a Decimal that
            indicates a cumulative year-over-year inflation factor.
            Or may be a method (returned as-is). Optional.

    Returns:
        A method with the following form:
        `inflation_adjust(val, this_year, target_year)`. The method
        returns a Money object (assuming Money-typed `val` input).
        Finds a nominal value in `target_year` with the same real
        value as `val`, a nominal value in `this_year`.
    """
    # Use a default value
    if inflation_adjust is None:
        # Assume real values if no inflation-adjustment method is
        # given - i.e. always return val without adjustment.
        def inflation_adjust(val, this_year, target_year):
            return val
    elif isinstance(inflation_adjust, dict):
        # If a dict of {year: Decimal} values has been passed in,
        # convert that to a suitable method:
        inflation_adjustments = {
            int(k): Decimal(inflation_adjust[k])
            for k in inflation_adjust
        }

        def inflation_adjust(val, this_year, target_year):
            return val * (
                inflation_adjustments[target_year] /
                inflation_adjustments[this_year]
            )
    elif not callable(inflation_adjust):
        # If it's not a dict and not callable, then we don't know
        # what to do with it. Raise an error.
        raise TypeError('RegisteredAccount: inflation_adjust must be ' +
                        'callable.')

    return inflation_adjust