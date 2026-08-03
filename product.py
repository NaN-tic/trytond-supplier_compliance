# This file is part of the supplier_compliance module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    compliance_records = fields.One2Many('supplier.compliance.record',
        'product_template', 'Compliance Records')
