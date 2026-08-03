# This file is part of the supplier_compliance module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.model import DeactivableMixin, ModelSQL, ModelView, fields, \
    sequence_ordered
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, If
from trytond.transaction import Transaction


class ScopeType(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'supplier.compliance.scope.type'
    _rec_name = 'name'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code')
    product_required = fields.Boolean('Product Required')
    description = fields.Text('Description')


class RequirementType(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'supplier.compliance.requirement.type'
    _rec_name = 'name'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code')
    kind = fields.Selection([
            ('document', 'Document'),
            ('declaration', 'Declaration'),
            ('analysis', 'Analysis'),
            ('certificate', 'Certificate'),
            ('other', 'Other'),
            ], 'Kind', required=True)
    requires_document = fields.Boolean('Requires Document')
    tracks_expiry = fields.Boolean('Tracks Expiry Date')
    description = fields.Text('Description')

    @staticmethod
    def default_kind():
        return 'document'


class Scheme(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'supplier.compliance.scheme'
    _rec_name = 'name'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code')
    description = fields.Text('Description')


class Record(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'supplier.compliance.record'

    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='CASCADE')
    party = fields.Many2One('party.party', 'Supplier', required=True,
        ondelete='CASCADE')
    product_template = fields.Many2One('product.template', 'Product',
        ondelete='CASCADE')
    product_supplier = fields.Many2One('purchase.product_supplier',
        'Supplier Product',
        domain=[
            If(Bool(Eval('party')), ('party', '=', Eval('party')), ()),
            If(Bool(Eval('product_template')),
                ('template', '=', Eval('product_template')), ()),
            If(Bool(Eval('company')), ('company', '=', Eval('company')), ()),
            ],
        depends=['party', 'product_template', 'company'])
    scope_type = fields.Many2One('supplier.compliance.scope.type',
        'Scope Type', required=True, ondelete='RESTRICT')
    code = fields.Char('Code')
    name = fields.Char('Name', required=True, translate=True)
    external_article_name = fields.Char('External Article Name')
    state = fields.Selection([
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('obsolete', 'Obsolete'),
            ], 'State', required=True)
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    contact_mechanisms = fields.Function(fields.One2Many(
            'party.contact_mechanism', None, 'Contacts',
            domain=[
                ('party', '=', Eval('party', -1)),
                ['OR',
                    ('supplier_compliance_alert', '=', True),
                    ('supplier_compliance_crisis', '=', True),
                    ],
                ],
            context={
                'related_party': Eval('party', -1),
                },
            depends=['party']),
        'get_contact_mechanisms', setter='set_contact_mechanisms')
    notes = fields.Text('Notes')
    requirements = fields.One2Many('supplier.compliance.requirement', 'record',
        'Requirements')
    certificates = fields.One2Many('supplier.compliance.certificate', 'record',
        'Certificates')
    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments')
    expired = fields.Function(fields.Boolean('Expired'), 'on_change_with_expired')
    needs_review = fields.Function(fields.Boolean('Needs Review'),
        'get_needs_review', searcher='search_needs_review')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_state():
        return 'draft'

    @fields.depends('end_date')
    def on_change_with_expired(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        return bool(self.end_date and self.end_date < today)

    def get_needs_review(self, name):
        return (self.on_change_with_expired()
            or any(r.on_change_with_expired() for r in self.requirements)
            or any(c.on_change_with_expired() for c in self.certificates))

    @classmethod
    def search_needs_review(cls, name, clause):
        _, operator, value = clause
        if operator not in ('=', '!='):
            raise NotImplementedError(
                'Operator %s not supported for %s' % (operator, name))
        if operator == '!=':
            value = not value
        Date = Pool().get('ir.date')
        today = Date.today()
        expired_domain = ['OR',
            ('end_date', '<', today),
            ('requirements.expiry_date', '<', today),
            ('certificates.expiry_date', '<', today),
            ]
        if value:
            return expired_domain
        return ['NOT', expired_domain]

    def get_contact_mechanisms(self, name):
        if not self.party:
            return []
        return [m.id for m in self.party.contact_mechanisms
            if m.supplier_compliance_alert or m.supplier_compliance_crisis]

    @classmethod
    def set_contact_mechanisms(cls, records, name, value):
        Party = Pool().get('party.party')
        for record in records:
            if not record.party:
                continue
            Party.write([record.party], {
                    'contact_mechanisms': value,
                    })

    @fields.depends('product_supplier')
    def on_change_product_supplier(self):
        if not self.product_supplier:
            return
        self.party = self.product_supplier.party
        self.product_template = self.product_supplier.template
        if not self.code:
            self.code = self.product_supplier.code
        if not self.external_article_name:
            self.external_article_name = self.product_supplier.name
        if not self.name:
            self.name = self.product_supplier.rec_name

    @classmethod
    def validate(cls, records):
        super().validate(records)
        for record in records:
            record.check_dates()
            record.check_scope()
            record.check_product_supplier()

    def check_dates(self):
        if (self.start_date and self.end_date
                and self.end_date < self.start_date):
            raise UserError(gettext(
                'supplier_compliance.msg_record_invalid_dates',
                record=self.rec_name))

    def check_scope(self):
        if (self.scope_type and self.scope_type.product_required
                and not self.product_template):
            raise UserError(gettext(
                'supplier_compliance.msg_scope_requires_product',
                scope=self.scope_type.rec_name,
                record=self.rec_name))

    def check_product_supplier(self):
        if not self.product_supplier:
            return
        if self.party and self.product_supplier.party != self.party:
            raise UserError(gettext(
                'supplier_compliance.msg_product_supplier_mismatch',
                record=self.rec_name))
        if (self.product_template
                and self.product_supplier.template != self.product_template):
            raise UserError(gettext(
                'supplier_compliance.msg_product_supplier_mismatch',
                record=self.rec_name))


class Requirement(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.requirement'

    record = fields.Many2One('supplier.compliance.record', 'Record',
        required=True, ondelete='CASCADE')
    requirement_type = fields.Many2One('supplier.compliance.requirement.type',
        'Requirement Type', required=True, ondelete='RESTRICT')
    status = fields.Selection([
            ('missing', 'Missing'),
            ('pending', 'Pending'),
            ('valid', 'Valid'),
            ('expired', 'Expired'),
            ('not_applicable', 'Not Applicable'),
            ], 'Status', required=True)
    document_date = fields.Date('Document Date')
    expiry_date = fields.Date('Expiry Date')
    value = fields.Char('Value')
    notes = fields.Text('Notes')
    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments')
    expired = fields.Function(fields.Boolean('Expired'), 'on_change_with_expired')

    @staticmethod
    def default_status():
        return 'missing'

    @fields.depends('expiry_date')
    def on_change_with_expired(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        return bool(self.expiry_date and self.expiry_date < today)

    @classmethod
    def validate(cls, requirements):
        super().validate(requirements)
        for requirement in requirements:
            requirement.check_dates()

    def check_dates(self):
        if (self.document_date and self.expiry_date
                and self.expiry_date < self.document_date):
            raise UserError(gettext(
                'supplier_compliance.msg_requirement_invalid_dates',
                requirement=self.rec_name))


class Certificate(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.certificate'

    record = fields.Many2One('supplier.compliance.record', 'Record',
        required=True, ondelete='CASCADE')
    scheme = fields.Many2One('supplier.compliance.scheme', 'Scheme',
        required=True, ondelete='RESTRICT')
    certificate_number = fields.Char('Certificate Number')
    issuer = fields.Char('Issuer')
    issue_date = fields.Date('Issue Date')
    expiry_date = fields.Date('Expiry Date')
    scope_text = fields.Text('Scope')
    notes = fields.Text('Notes')
    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments')
    expired = fields.Function(fields.Boolean('Expired'), 'on_change_with_expired')

    @fields.depends('expiry_date')
    def on_change_with_expired(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        return bool(self.expiry_date and self.expiry_date < today)

    @classmethod
    def validate(cls, certificates):
        super().validate(certificates)
        for certificate in certificates:
            certificate.check_dates()

    def check_dates(self):
        if (self.issue_date and self.expiry_date
                and self.expiry_date < self.issue_date):
            raise UserError(gettext(
                'supplier_compliance.msg_certificate_invalid_dates',
                certificate=self.rec_name))
