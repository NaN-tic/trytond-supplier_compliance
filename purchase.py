# This file is part of the supplier_compliance module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.exceptions import UserError, UserWarning
from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import Pool, PoolMeta


class ProductSupplier(metaclass=PoolMeta):
    __name__ = 'purchase.product_supplier'

    compliance_records = fields.One2Many('supplier.compliance.record',
        'product_supplier', 'Compliance Records',
        help='Compliance records linked to this supplier product. Example: '
        'the homologation file for supplier code 946.')


class Purchase(metaclass=PoolMeta):
    __name__ = 'purchase.purchase'

    def check_for_quotation(self):
        super().check_for_quotation()
        mode = self.get_supplier_compliance_purchase_mode()
        for line in self.lines:
            line.check_supplier_compliance(mode=mode)

    def get_supplier_compliance_purchase_mode(self):
        Configuration = Pool().get('purchase.configuration')
        config = Configuration(1)
        return config.get_multivalue(
            'supplier_compliance_purchase_mode',
            company=self.company.id if self.company else None)


class Line(metaclass=PoolMeta):
    __name__ = 'purchase.line'

    def check_supplier_compliance(self, mode='blocking'):
        Record = Pool().get('supplier.compliance.record')
        Warning = Pool().get('res.user.warning')
        if (self.type != 'line'
                or not self.purchase
                or not self.purchase.party
                or not self.product
                or mode == 'none'):
            return
        record = Record.get_purchase_blocking_record(
            self.purchase.company, self.purchase.party, self.product,
            product_supplier=self.product_supplier)
        if not record:
            return
        replacement = (
            record.replacement_record.rec_name
            if record.replacement_record else '-')
        message = gettext(
            'supplier_compliance.msg_purchase_line_blocked_by_compliance',
            record=record.rec_name,
            state=record.state,
            replacement=replacement)
        if mode == 'warning':
            key = Warning.format('supplier_compliance_purchase', [self.purchase])
            if Warning.check(key):
                raise UserWarning(key, message)
        elif mode == 'blocking':
            raise UserError(gettext(
                'supplier_compliance.msg_purchase_line_blocked_by_compliance',
                record=record.rec_name,
                state=record.state,
                replacement=replacement))
