# This file is part of the supplier_compliance module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.modules.company.model import CompanyValueMixin
from trytond.pool import Pool, PoolMeta


supplier_compliance_purchase_mode = fields.Selection([
        ('none', 'None'),
        ('warning', 'Warning'),
        ('blocking', 'Blocking'),
        ], 'Supplier Compliance Purchase Mode', required=True,
    help='Defines what happens when a purchase uses a blocked compliance '
    'record. Example: Warning lets the user continue after reading the alert.')


class Configuration(metaclass=PoolMeta):
    __name__ = 'purchase.configuration'

    supplier_compliance_purchase_mode = fields.MultiValue(
        supplier_compliance_purchase_mode)

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'supplier_compliance_purchase_mode':
            return pool.get('purchase.configuration.supplier_compliance')
        return super().multivalue_model(field)

    @classmethod
    def default_supplier_compliance_purchase_mode(cls, **pattern):
        return cls.multivalue_model(
            'supplier_compliance_purchase_mode'
            ).default_supplier_compliance_purchase_mode()


class ConfigurationSupplierCompliance(ModelSQL, CompanyValueMixin):
    __name__ = 'purchase.configuration.supplier_compliance'

    supplier_compliance_purchase_mode = supplier_compliance_purchase_mode

    @classmethod
    def default_supplier_compliance_purchase_mode(cls):
        return 'blocking'
