# This file is part of the supplier_compliance module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    compliance_records = fields.One2Many('supplier.compliance.record', 'party',
        'Compliance Records',
        help='Compliance records linked to this supplier. Example: one record '
        'for each approved raw material.')


class ContactMechanism(metaclass=PoolMeta):
    __name__ = 'party.contact_mechanism'

    supplier_compliance_alert = fields.Boolean('Compliance Alert',
        help='Use this contact for compliance alerts. Example: the quality '
        'email that receives document expiry notices.')
    supplier_compliance_crisis = fields.Boolean('Compliance Crisis',
        help='Use this contact for crisis communication. Example: the 24/7 '
        'food safety contact of the supplier.')

    @classmethod
    def usages(cls, _fields=None):
        _fields = set(_fields or [])
        _fields.update({
                'supplier_compliance_alert',
                'supplier_compliance_crisis',
                })
        return super().usages(_fields)
