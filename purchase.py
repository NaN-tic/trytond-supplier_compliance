# This file is part of the supplier_compliance module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta


class ProductSupplier(metaclass=PoolMeta):
    __name__ = 'purchase.product_supplier'

    compliance_records = fields.One2Many('supplier.compliance.record',
        'product_supplier', 'Compliance Records')
