""" A module with free methods and extensions to third-party classes.

Used throughout the application, without any dependency on any other
modules.
"""

import collections
from decimal import Decimal


class Timing(dict):
    """ A dict of {timing: weight} pairs.

    This is really just a vanilla dict with a convenient init method.
    It divides the interval [0,1] into a number of equal-length periods
    equal to `frequency` and, within each period, assigns a timing at
    `when`. The timings are equally-weighted.

    Examples:
        Timing()
        # {0.5: 1}
        Timing(when=1, frequency=4)
        # {0.25: 0.25, 0.5: 0.25, 0.75: 0.25, 1: 0.25}
        Timing(when=0, frequency=4)
        # {0: 0.25, 0.25: 0.25, 0.5: 0.25, 0.75: 0.25}
        Timing(when=0.5, frequency=2)
        # {0.25: 0.5, 0.75: 0.5}

    Args:
        when (Number, str): When transactions occur in each period (e.g.
            'start', 'end', 0.5). Uses the same syntax as
            `forecaster.utility.when_conv`. Optional.
        frequency (str, int): The number of periods (and thus the number
            of transactions). Uses the same syntax as
            `forecaster.utility.frequency_conv`. Optional.
    """
    def __init__(self, when=0.5, frequency=1):
        """ Initializes a Timing dict. """
        # Get an empty dict:
        super().__init__()
        # If we call Timing(input) with dict-type `input`, copy the
        # input without further processing:
        if isinstance(when, dict):
            self.update(when)
            return
        # Otherwise, assume inputs are scalar and build out multiple
        # timings accordingly.
        # Arguments might be str-valued; process to make them numeric:
        when = when_conv(when)
        frequency = frequency_conv(frequency)
        # Each transaction has equal weight:
        weight = 1 / frequency
        # Build the dict:
        for time in range(frequency):
            self[(time + when) / frequency] = weight


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

# String codes describing frequencies (e.g. annual, bimonthly)
# mapped to ints giving the number of such periods in a year:
FREQUENCY_MAPPING = {
    'C': None,
    'D': 365,
    'W': 52,
    'BW': 26,
    'SM': 24,
    'M': 12,
    'BM': 6,
    'Q': 4,
    'SA': 2,
    'A': 1
}

def frequency_conv(nper):
    """ Number of periods in a year given a compounding frequency.

    Args:
        nper (str, int): A code (str) indicating a compounding
            frequency (e.g. 'W', 'M'), an int, or None

    Returns:
        An int indicating the number of compounding periods in a
            year or None if compounding is continuous.

    Raises:
        ValueError: str nper must have a known value.
        ValueError: nper must be greater than 0.
        TypeError: nper cannot be losslessly converted to int.
    """
    # nper can be None, so return gracefully.
    if nper is None:
        return None

    # Try to parse a string based on known compounding frequencies
    if isinstance(nper, str):
        if nper not in FREQUENCY_MAPPING:
            raise ValueError('Account: str nper must have a known value')
        return FREQUENCY_MAPPING[nper]
    else:  # Attempt to cast to int
        if not nper == int(nper):
            raise TypeError(
                'Account: nper is not losslessly convertible to int')
        if nper <= 0:
            raise ValueError('Account: nper must be greater than 0')
        return int(nper)

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
        following year.

        Returns `None` if `vals` is empty.
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
    base_year = nearest_year(vals, target_year)

    # If one of the above searches worked, return an inflation-adjusted
    # value (or dict/list of values, depending on what the values of
    # `vals` are)
    if base_year != target_year:
        val = vals[base_year]
        if isinstance(val, dict):
            return {
                k: val[k] * inflation_adjust(target_year, base_year)
                for k in val
            }
        elif isinstance(val, collections.abc.Iterable):
            return type(val)(
                v * inflation_adjust(target_year, base_year) for v in val
            )
        else:
            return val * inflation_adjust(target_year, base_year)
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
        `inflation_adjust(val, this_year, target_year)`.

        The method returns a Money object (assuming Money-typed `val`
        input).

        Finds a nominal value in `target_year` with the same real
        value as `val`, a nominal value in `this_year`.
    """
    # Use a default value
    if inflation_adjust is None:
        # Assume real values if no inflation-adjustment method is
        # given - i.e. always return val without adjustment.
        # pylint: disable=W0613,E0102
        def inflation_adjust_func(target_year=None, base_year=None):
            """ No inflation adjustment; returns 1 every year. """
            return Decimal(1)
    elif isinstance(inflation_adjust, dict):
        # If a dict of {year: Decimal} values has been passed in,
        # convert that to a suitable method.
        # If inflation_adjust has a default value, preserve it:
        if isinstance(inflation_adjust, collections.defaultdict):
            inflation_dict = collections.defaultdict(
                inflation_adjust.default_factory)
        else:
            inflation_dict = {}
        # Then type-convert all the elements of inflation_adjust:
        inflation_dict.update({
            int(key): Decimal(inflation_adjust[key])
            for key in inflation_adjust
        })

        # It's slightly more efficient to find the smallest key in
        # inflation_adjust outside of the function.
        default_base = min(inflation_dict.keys())

        def inflation_adjust_func(target_year, base_year=None):
            """ Inflation adjustment from """
            if base_year is None:
                base_year = default_base
            return Decimal(
                inflation_dict[target_year] /
                inflation_dict[base_year]
            )
    elif not callable(inflation_adjust):
        # If it's not a dict and not callable, then we don't know
        # what to do with it. Raise an error.
        raise TypeError('RegisteredAccount: inflation_adjust must be ' +
                        'callable.')
    else:
        # inflation_adjust is callable, so just use that!
        inflation_adjust_func = inflation_adjust

    return inflation_adjust_func
