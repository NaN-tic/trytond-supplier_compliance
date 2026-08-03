# This file is part of the supplier_compliance module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool

from . import compliance, party, product, purchase


def register():
    Pool.register(
        compliance.ScopeType,
        compliance.RequirementType,
        compliance.Scheme,
        compliance.Record,
        compliance.Requirement,
        compliance.Certificate,
        party.Party,
        party.ContactMechanism,
        product.Template,
        purchase.ProductSupplier,
        module='supplier_compliance', type_='model')
