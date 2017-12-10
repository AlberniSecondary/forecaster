""" Tests for Canada-specific Tax subclasses. """

import unittest
from decimal import Decimal
import context  # pylint: disable=unused-import
from forecaster.person import Person
from forecaster.canada.tax import TaxCanada
from forecaster.canada.accounts import RRSP, TaxableAccount, Money
from forecaster.canada import constants
# pylint: disable=wildcard-import,unused-wildcard-import
from tests.test_helper import *


class TestTax(unittest.TestCase):
    """ Tests CanadianResidentTax """

    def setUp(self):
        self.initial_year = 2000
        # Build 100 years of inflation adjustments with steadily growing
        # adjustment factors. First, pick a nice number (ideally a power
        # of 2 to avoid float precision issues); inflation_adjustment
        # will grow by adding the inverse (1/n) of this number annually
        growth_factor = 32
        year_range = range(self.initial_year, self.initial_year + 100)
        self.inflation_adjustments = {
            year: 1 + (year - self.initial_year) / growth_factor
            for year in year_range
        }
        # For convenience, store the year where inflation has doubled
        # the nominal value of money
        self.double_year = self.initial_year + growth_factor
        # Build some brackets with nice round numbers:
        self.tax_brackets = {
            self.initial_year: {
                Money(0): Decimal('0.1'),
                Money('100'): Decimal('0.2'),
                Money('10000'): Decimal('0.3')
            }
        }
        # For convenience in testing, build an accum dict that
        # corresponds to the tax brackets above.
        self.accum = {
            self.initial_year: {
                Money(0): Money('0'),
                Money('100'): Money('10'),
                Money('10000'): Money('1990')
            }
        }
        self.personal_deduction = {
            self.initial_year: Money('100')
        }
        self.credit_rate = {
            self.initial_year: Decimal('0.1')
        }

    def test_init(self):
        """ Test TaxCanada.__init__ """
        tax = TaxCanada(self.inflation_adjustments, province='BC')
        # Test federal tax:
        # There's some type-conversion going on, so test the Decimal-
        # valued `amount` of the Tax's tax bracket's keys against the
        # Decimal key object of the Constants tax brackets.
        for year in constants.TAX_BRACKETS['Federal']:
            self.assertEqual(
                tax.federal_tax.tax_brackets(year),
                {
                    Money(bracket): value
                    for bracket, value in
                    constants.TAX_BRACKETS['Federal'][year].items()
                }
            )
            self.assertEqual(
                tax.federal_tax.personal_deduction(year),
                constants.TAX_PERSONAL_DEDUCTION['Federal'][year])
            self.assertEqual(
                tax.federal_tax.credit_rate(year),
                constants.TAX_CREDIT_RATE['Federal'][year])
        self.assertTrue(callable(tax.federal_tax.inflation_adjust))

        # Test provincial tax:
        for year in constants.TAX_BRACKETS['BC']:
            self.assertEqual(
                tax.provincial_tax.tax_brackets(year),
                {
                    Money(bracket): value
                    for bracket, value in
                    constants.TAX_BRACKETS['BC'][year].items()
                }
            )
            self.assertEqual(
                tax.provincial_tax.personal_deduction(year),
                constants.TAX_PERSONAL_DEDUCTION['BC'][year])
            self.assertEqual(
                tax.provincial_tax.credit_rate(year),
                constants.TAX_CREDIT_RATE['BC'][year])
        self.assertTrue(callable(tax.provincial_tax.inflation_adjust))

        # Omit optional argument and try again:
        tax = TaxCanada(self.inflation_adjustments)
        for year in constants.TAX_BRACKETS['BC']:
            self.assertEqual(
                tax.provincial_tax.tax_brackets(year),
                {
                    Money(bracket): value
                    for bracket, value in
                    constants.TAX_BRACKETS['BC'][year].items()
                }
            )
            self.assertEqual(
                tax.provincial_tax.personal_deduction(year),
                constants.TAX_PERSONAL_DEDUCTION['BC'][year])
            self.assertEqual(
                tax.provincial_tax.credit_rate(year),
                constants.TAX_CREDIT_RATE['BC'][year])
        self.assertTrue(callable(tax.provincial_tax.inflation_adjust))

    def test_call(self):
        """ Test TaxCanada.__call__ """
        tax = TaxCanada(self.inflation_adjustments)
        # Test a call on Money:
        taxable_income = Money(100000)
        self.assertEqual(
            tax(taxable_income, self.initial_year),
            tax.federal_tax(taxable_income, self.initial_year) +
            tax.provincial_tax(taxable_income, self.initial_year)
        )

        # Test a call on one Person:
        person1 = Person(
            self.initial_year, "Tester 1", self.initial_year - 20,
            retirement_date=self.initial_year + 45, gross_income=100000)
        _ = TaxableAccount(
            owner=person1,
            acb=0, balance=Money(1000000), rate=Decimal('0.05'),
            transactions={'start': -Money(1000000)}, nper=1)
        # NOTE: by using an RRSP here, a pension income tax credit will
        # be applied by TaxCanadaJurisdiction. Be aware of this if you
        # want to test this output against a generic Tax object with
        # Canadian brackets.
        _ = RRSP(
            person1,
            inflation_adjust=self.inflation_adjustments,
            contribution_room=0,
            balance=Money(500000), rate=Decimal('0.05'),
            transactions={'start': -Money(500000)}, nper=1)
        self.assertEqual(
            tax(person1, self.initial_year),
            tax.federal_tax(person1, self.initial_year) +
            tax.provincial_tax(person1, self.initial_year)
        )

        # Should get the same result for a single-person set:
        self.assertEqual(
            tax({person1}, self.initial_year),
            tax(person1, self.initial_year)
        )

        # Finally, test tax treatment of multiple people:
        person2 = Person(
            self.initial_year, "Tester 2", self.initial_year - 18,
            retirement_date=self.initial_year + 47, gross_income=50000)
        _ = TaxableAccount(
            owner=person2,
            acb=0, balance=Money(10000), rate=Decimal('0.05'),
            transactions={'start': -Money(10000)}, nper=1)
        # Make sure that we're getting the correct result for person2:
        self.assertEqual(
            tax(person2, self.initial_year),
            tax.federal_tax(person2, self.initial_year) +
            tax.provincial_tax(person2, self.initial_year)
        )
        # Now confirm that the Tax object works with both people.
        self.assertEqual(
            tax({person1, person2}, self.initial_year),
            tax.federal_tax({person1, person2}, self.initial_year) +
            tax.provincial_tax({person1, person2}, self.initial_year)
        )

if __name__ == '__main__':
    unittest.main()