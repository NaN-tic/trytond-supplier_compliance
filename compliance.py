# This file is part of the supplier_compliance module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from datetime import datetime, timedelta

from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.model import DeactivableMixin, ModelSQL, ModelView, fields, \
    sequence_ordered
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, If, PYSONEncoder
from trytond.transaction import Transaction, without_check_access


RECORD_STATES = [
    ('draft', 'Draft'),
    ('pending_documents', 'Pending Documents'),
    ('approved', 'Approved'),
    ('conditional', 'Conditional'),
    ('suspended', 'Suspended'),
    ('expired', 'Expired'),
    ('withdrawn', 'Withdrawn'),
    ('rejected', 'Rejected'),
    ]
RECORD_STATES_WITH_EMPTY = [('', '')] + RECORD_STATES


class ScopeType(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'supplier.compliance.scope.type'
    _rec_name = 'name'

    name = fields.Char('Name', required=True, translate=True,
        help='Scope type name shown to users. Example: Raw Material or '
        'Packaging.')
    code = fields.Char('Code',
        help='Short code used in imports and filters. Example: MP or ENVASE.')
    product_required = fields.Boolean('Product Required',
        help='Enable this when the compliance record must be linked to a '
        'product. Example: raw materials usually require a product.')
    description = fields.Text('Description',
        help='Internal explanation of when to use this scope type. Example: '
        'used for food contact packaging suppliers.')


class RequirementType(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'supplier.compliance.requirement.type'
    _rec_name = 'name'

    name = fields.Char('Name', required=True, translate=True,
        help='Requirement type name. Example: Technical Sheet or Non GMO '
        'Declaration.')
    code = fields.Char('Code',
        help='Short identifier for the requirement type. Example: FT or OGM.')
    kind = fields.Selection([
            ('document', 'Document'),
            ('declaration', 'Declaration'),
            ('analysis', 'Analysis'),
            ('certificate', 'Certificate'),
            ('other', 'Other'),
            ], 'Kind', required=True,
        help='Functional group of the requirement. Example: use Document for '
        'a technical sheet and Declaration for allergen statements.')
    requires_document = fields.Boolean('Requires Document',
        help='Mark this when an attachment is expected. Example: a signed PDF '
        'for the questionnaire.')
    tracks_expiry = fields.Boolean('Tracks Expiry Date',
        help='Enable this when the requirement can expire. Example: annual '
        'supplier questionnaire.')
    expiry_notice_days = fields.Integer('Expiry Notice Days',
        help='Days in advance to request an update. Example: 30 sends the '
        'warning one month before expiry.')
    description = fields.Text('Description',
        help='Internal guidance for this requirement type. Example: applies '
        'only to food suppliers.')

    @staticmethod
    def default_kind():
        return 'document'


class Scheme(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'supplier.compliance.scheme'
    _rec_name = 'name'

    name = fields.Char('Name', required=True, translate=True,
        help='Certification scheme name. Example: IFS, GRS or FSC.')
    code = fields.Char('Code',
        help='Short code for the scheme. Example: IFS.')
    expiry_notice_days = fields.Integer('Expiry Notice Days',
        help='Days before certificate expiry to request renewal. Example: 45.')
    description = fields.Text('Description',
        help='Internal notes about the scheme. Example: requested only for '
        'recycled content suppliers.')


class ComplianceTemplate(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'supplier.compliance.template'
    _rec_name = 'name'

    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='CASCADE',
        help='Company that owns this template. Example: Valero Forn '
        'Tradicional, S. L.')
    name = fields.Char('Name', required=True, translate=True,
        help='Template name. Example: Raw Material Ingredients.')
    scope_type = fields.Many2One('supplier.compliance.scope.type',
        'Scope Type', required=True, ondelete='RESTRICT',
        help='Scope where the template applies. Example: Raw Material.')
    product_category = fields.Many2One('product.category', 'Product Category',
        ondelete='RESTRICT',
        help='Optional product category to narrow the template. Example: '
        'Ingredients.')
    requirements = fields.One2Many('supplier.compliance.template.requirement',
        'template', 'Requirements',
        help='Requirement types created automatically from this template. '
        'Example: Technical Sheet and Allergen Declaration.')
    certificates = fields.One2Many('supplier.compliance.template.certificate',
        'template', 'Certificates',
        help='Certificates created automatically from this template. Example: '
        'IFS.')
    food_analyses = fields.One2Many(
        'supplier.compliance.template.food.analysis', 'template',
        'Food Analyses',
        help='Food analyses created automatically from this template. '
        'Example: Contaminants.')
    packaging_compliances = fields.One2Many(
        'supplier.compliance.template.packaging.compliance', 'template',
        'Packaging Compliances',
        help='Packaging declarations created automatically from this '
        'template. Example: food contact declaration.')
    packaging_migration_tests = fields.One2Many(
        'supplier.compliance.template.packaging.migration_test', 'template',
        'Packaging Migration Tests',
        help='Migration tests created automatically from this template. '
        'Example: global migration.')
    notes = fields.Text('Notes',
        help='Optional notes about the template. Example: use for all cereal '
        'mixes from external suppliers.')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def validate(cls, templates):
        super().validate(templates)
        for template in templates:
            template.check_unique()

    def check_unique(self):
        domain = [
            ('company', '=', self.company.id),
            ('scope_type', '=', self.scope_type.id),
            ('id', '!=', self.id),
            ]
        if self.product_category:
            domain.append(('product_category', '=', self.product_category.id))
        else:
            domain.append(('product_category', '=', None))
        duplicates = self.search(domain, limit=1)
        if duplicates:
            raise UserError(gettext(
                'supplier_compliance.msg_compliance_template_duplicate',
                template=self.rec_name))

    def get_category_depth(self):
        depth = 0
        category = self.product_category
        while category and category.parent:
            depth += 1
            category = category.parent
        return depth

    @classmethod
    def get_matching_template(cls, company, scope_type, product_template):
        if not company or not scope_type or not product_template:
            return None
        templates = cls.search([
                ('company', '=', company.id),
                ('scope_type', '=', scope_type.id),
                ('active', '=', True),
                ])
        if not templates:
            return None
        category_ids = {c.id for c in product_template.categories_all}
        matches = []
        for template in templates:
            if (template.product_category
                    and template.product_category.id not in category_ids):
                continue
            matches.append((
                    template.product_category is None,
                    -template.get_category_depth(),
                    template.id,
                    template,
                    ))
        if not matches:
            return None
        matches.sort()
        return matches[0][3]

    def apply_to_record(self, record):
        Requirement = Pool().get('supplier.compliance.requirement')
        Certificate = Pool().get('supplier.compliance.certificate')
        FoodAnalysis = Pool().get('supplier.compliance.food.analysis')
        PackagingCompliance = Pool().get(
            'supplier.compliance.packaging.compliance')
        PackagingMigrationTest = Pool().get(
            'supplier.compliance.packaging.migration_test')
        requirements = list(record.requirements or ())
        existing_requirement_types = {
            requirement.requirement_type.id
            for requirement in requirements
            if requirement.requirement_type
            }
        for line in self.requirements:
            if line.requirement_type.id in existing_requirement_types:
                continue
            requirement = Requirement()
            requirement.sequence = line.sequence
            requirement.requirement_type = line.requirement_type
            requirement.status = 'missing'
            requirements.append(requirement)
            existing_requirement_types.add(line.requirement_type.id)
        record.requirements = tuple(requirements)

        certificates = list(record.certificates or ())
        existing_schemes = {
            certificate.scheme.id
            for certificate in certificates
            if certificate.scheme
            }
        for line in self.certificates:
            if line.scheme.id in existing_schemes:
                continue
            certificate = Certificate()
            certificate.sequence = line.sequence
            certificate.scheme = line.scheme
            certificates.append(certificate)
            existing_schemes.add(line.scheme.id)
        record.certificates = tuple(certificates)

        analyses = list(record.food_analyses or ())
        existing_analysis_types = {
            analysis.analysis_type
            for analysis in analyses
            if analysis.analysis_type
            }
        for line in self.food_analyses:
            if line.analysis_type in existing_analysis_types:
                continue
            analysis = FoodAnalysis()
            analysis.sequence = line.sequence
            analysis.analysis_type = line.analysis_type
            analysis.review_notice_days = line.review_notice_days
            analyses.append(analysis)
            existing_analysis_types.add(line.analysis_type)
        record.food_analyses = tuple(analyses)

        compliances = list(record.packaging_compliances or ())
        existing_compliance_refs = {
            compliance.reference
            for compliance in compliances
            }
        for line in self.packaging_compliances:
            if line.reference and line.reference in existing_compliance_refs:
                continue
            compliance = PackagingCompliance()
            compliance.sequence = line.sequence
            compliance.reference = line.reference
            compliance.declared_regulation = line.declared_regulation
            compliance.expiry_notice_days = line.expiry_notice_days
            compliance.status = 'pending'
            compliances.append(compliance)
            if line.reference:
                existing_compliance_refs.add(line.reference)
        record.packaging_compliances = tuple(compliances)

        migration_tests = list(record.packaging_migration_tests or ())
        existing_migration_types = {
            test.migration_type
            for test in migration_tests
            if test.migration_type
            }
        for line in self.packaging_migration_tests:
            if line.migration_type in existing_migration_types:
                continue
            migration_test = PackagingMigrationTest()
            migration_test.sequence = line.sequence
            migration_test.migration_type = line.migration_type
            migration_test.review_notice_days = line.review_notice_days
            migration_tests.append(migration_test)
            existing_migration_types.add(line.migration_type)
        record.packaging_migration_tests = tuple(migration_tests)

    @classmethod
    def get_template_category(cls, product_template):
        if not product_template:
            return None
        categories = list(product_template.categories or ())
        if not categories:
            categories = list(product_template.categories_all or ())
        if not categories:
            return None
        categories.sort(key=lambda c: cls._get_category_depth(c), reverse=True)
        return categories[0]

    @staticmethod
    def _get_category_depth(category):
        depth = 0
        while category and category.parent:
            depth += 1
            category = category.parent
        return depth

    @classmethod
    def create_from_record(cls, record):
        RequirementLine = Pool().get('supplier.compliance.template.requirement')
        CertificateLine = Pool().get('supplier.compliance.template.certificate')
        FoodAnalysisLine = Pool().get(
            'supplier.compliance.template.food.analysis')
        PackagingComplianceLine = Pool().get(
            'supplier.compliance.template.packaging.compliance')
        MigrationTestLine = Pool().get(
            'supplier.compliance.template.packaging.migration_test')
        category = cls.get_template_category(record.product_template)
        domain = [
            ('company', '=', record.company.id),
            ('scope_type', '=', record.scope_type.id),
            ]
        if category:
            domain.append(('product_category', '=', category.id))
        else:
            domain.append(('product_category', '=', None))
        templates = cls.search(domain, limit=1)
        if templates:
            template, = templates
        else:
            template, = cls.create([{
                        'company': record.company.id,
                        'scope_type': record.scope_type.id,
                        'product_category': category.id if category else None,
                        'name': record.name or record.rec_name,
                        }])

        existing_requirement_types = {
            line.requirement_type.id for line in template.requirements
            if line.requirement_type
            }
        to_create = []
        for requirement in record.requirements:
            if (not requirement.requirement_type
                    or requirement.requirement_type.id
                    in existing_requirement_types):
                continue
            to_create.append({
                    'template': template.id,
                    'sequence': requirement.sequence,
                    'requirement_type': requirement.requirement_type.id,
                    })
            existing_requirement_types.add(requirement.requirement_type.id)
        if to_create:
            RequirementLine.create(to_create)

        existing_schemes = {
            line.scheme.id for line in template.certificates
            if line.scheme
            }
        to_create = []
        for certificate in record.certificates:
            if (not certificate.scheme
                    or certificate.scheme.id in existing_schemes):
                continue
            to_create.append({
                    'template': template.id,
                    'sequence': certificate.sequence,
                    'scheme': certificate.scheme.id,
                    })
            existing_schemes.add(certificate.scheme.id)
        if to_create:
            CertificateLine.create(to_create)

        existing_analysis_types = {
            line.analysis_type for line in template.food_analyses
            if line.analysis_type
            }
        to_create = []
        for analysis in record.food_analyses:
            if (not analysis.analysis_type
                    or analysis.analysis_type in existing_analysis_types):
                continue
            to_create.append({
                    'template': template.id,
                    'sequence': analysis.sequence,
                    'analysis_type': analysis.analysis_type,
                    'review_notice_days': analysis.review_notice_days,
                    })
            existing_analysis_types.add(analysis.analysis_type)
        if to_create:
            FoodAnalysisLine.create(to_create)

        existing_packaging_refs = {
            line.reference for line in template.packaging_compliances
            if line.reference
            }
        to_create = []
        for compliance in record.packaging_compliances:
            if compliance.reference and compliance.reference in existing_packaging_refs:
                continue
            to_create.append({
                    'template': template.id,
                    'sequence': compliance.sequence,
                    'reference': compliance.reference,
                    'declared_regulation': compliance.declared_regulation,
                    'expiry_notice_days': compliance.expiry_notice_days,
                    })
            if compliance.reference:
                existing_packaging_refs.add(compliance.reference)
        if to_create:
            PackagingComplianceLine.create(to_create)

        existing_migration_types = {
            line.migration_type for line in template.packaging_migration_tests
            if line.migration_type
            }
        to_create = []
        for migration_test in record.packaging_migration_tests:
            if (not migration_test.migration_type
                    or migration_test.migration_type
                    in existing_migration_types):
                continue
            to_create.append({
                    'template': template.id,
                    'sequence': migration_test.sequence,
                    'migration_type': migration_test.migration_type,
                    'review_notice_days': migration_test.review_notice_days,
                    })
            existing_migration_types.add(migration_test.migration_type)
        if to_create:
            MigrationTestLine.create(to_create)
        return template


class ComplianceTemplateRequirement(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.template.requirement'

    template = fields.Many2One('supplier.compliance.template', 'Template',
        required=True, ondelete='CASCADE',
        help='Template that owns this requirement line.')
    requirement_type = fields.Many2One('supplier.compliance.requirement.type',
        'Requirement Type', required=True, ondelete='RESTRICT',
        help='Requirement created by the template. Example: Technical Sheet.')

    @classmethod
    def validate(cls, lines):
        super().validate(lines)
        for line in lines:
            line.check_unique()

    def check_unique(self):
        duplicates = self.search([
                ('template', '=', self.template.id),
                ('requirement_type', '=', self.requirement_type.id),
                ('id', '!=', self.id),
                ], limit=1)
        if duplicates:
            raise UserError(gettext(
                'supplier_compliance.msg_compliance_template_requirement_duplicate',
                template=self.template.rec_name,
                requirement_type=self.requirement_type.rec_name))


class ComplianceTemplateCertificate(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.template.certificate'

    template = fields.Many2One('supplier.compliance.template', 'Template',
        required=True, ondelete='CASCADE',
        help='Template that owns this certificate line.')
    scheme = fields.Many2One('supplier.compliance.scheme', 'Scheme',
        required=True, ondelete='RESTRICT',
        help='Certification scheme created by the template. Example: IFS.')

    @classmethod
    def validate(cls, lines):
        super().validate(lines)
        for line in lines:
            line.check_unique()

    def check_unique(self):
        duplicates = self.search([
                ('template', '=', self.template.id),
                ('scheme', '=', self.scheme.id),
                ('id', '!=', self.id),
                ], limit=1)
        if duplicates:
            raise UserError(gettext(
                'supplier_compliance.msg_compliance_template_certificate_duplicate',
                template=self.template.rec_name,
                scheme=self.scheme.rec_name))


class ComplianceTemplateFoodAnalysis(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.template.food.analysis'

    template = fields.Many2One('supplier.compliance.template', 'Template',
        required=True, ondelete='CASCADE',
        help='Template that owns this analysis line.')
    analysis_type = fields.Char('Analysis Type', required=True,
        help='Analysis name created by the template. Example: Contaminants.')
    review_notice_days = fields.Integer('Review Notice Days',
        help='Days before next review to request a new analysis. Example: 20.')

    @classmethod
    def validate(cls, lines):
        super().validate(lines)
        for line in lines:
            line.check_unique()

    def check_unique(self):
        duplicates = self.search([
                ('template', '=', self.template.id),
                ('analysis_type', '=', self.analysis_type),
                ('id', '!=', self.id),
                ], limit=1)
        if duplicates:
            raise UserError(gettext(
                'supplier_compliance.msg_compliance_template_food_analysis_duplicate',
                template=self.template.rec_name,
                analysis_type=self.analysis_type))


class ComplianceTemplatePackagingCompliance(
        sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.template.packaging.compliance'

    template = fields.Many2One('supplier.compliance.template', 'Template',
        required=True, ondelete='CASCADE',
        help='Template that owns this packaging compliance line.')
    reference = fields.Char('Reference',
        help='Optional reference prefilled on the record. Example: DOC-001.')
    declared_regulation = fields.Char('Declared Regulation',
        help='Regulation expected on the declaration. Example: 1935/2004.')
    expiry_notice_days = fields.Integer('Expiry Notice Days',
        help='Days before expiry to request a new declaration. Example: 90.')


class ComplianceTemplatePackagingMigrationTest(
        sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.template.packaging.migration_test'

    template = fields.Many2One('supplier.compliance.template', 'Template',
        required=True, ondelete='CASCADE',
        help='Template that owns this migration test line.')
    migration_type = fields.Selection([
            ('global_migration', 'Global Migration'),
            ('specific_migration', 'Specific Migration'),
            ('heavy_metals', 'Heavy Metals'),
            ('printing_inks', 'Printing Inks'),
            ('other', 'Other'),
            ], 'Migration Type', required=True,
        help='Migration test expected on the record. Example: Global '
        'Migration.')
    review_notice_days = fields.Integer('Review Notice Days',
        help='Days before next review to request a new test. Example: 60.')

    @classmethod
    def validate(cls, lines):
        super().validate(lines)
        for line in lines:
            line.check_unique()

    def check_unique(self):
        duplicates = self.search([
                ('template', '=', self.template.id),
                ('migration_type', '=', self.migration_type),
                ('id', '!=', self.id),
                ], limit=1)
        if duplicates:
            raise UserError(gettext(
                'supplier_compliance.msg_compliance_template_packaging_migration_test_duplicate',
                template=self.template.rec_name,
                migration_type=self.rec_name))


class Record(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'supplier.compliance.record'
    _purchase_allowed_states = {'approved', 'conditional'}

    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='CASCADE',
        help='Company that owns the compliance record. Example: Valero Forn '
        'Tradicional, S. L.')
    party = fields.Many2One('party.party', 'Supplier', required=True,
        ondelete='CASCADE',
        help='Approved supplier for this record. Example: APLIENA S.A.')
    product_template = fields.Many2One('product.template', 'Product',
        domain=[
            If(Bool(Eval('party')),
                ('product_suppliers.party', '=', Eval('party')),
                ()),
            If(Bool(Eval('company')),
                ['OR',
                    ('product_suppliers.company', '=', Eval('company')),
                    ('product_suppliers.company', '=', None),
                    ],
                ()),
            ],
        depends=['party', 'company'],
        ondelete='CASCADE',
        help='Internal product affected by this compliance record. Example: '
        'the template [MX0118] Mix Atrian Vitamina 50%.')
    product_supplier = fields.Many2One('purchase.product_supplier',
        'Supplier Product',
        domain=[
            If(Bool(Eval('party')), ('party', '=', Eval('party')), ()),
            If(Bool(Eval('product_template')),
                ('template', '=', Eval('product_template')), ()),
            If(Bool(Eval('company')),
                ['OR',
                    ('company', '=', Eval('company')),
                    ('company', '=', None),
                    ],
                ()),
            ],
        depends=['party', 'product_template', 'company'],
        help='Supplier product card linked to the record. Example: supplier '
        'code 946 for APLIENA.')
    scope_type = fields.Many2One('supplier.compliance.scope.type',
        'Scope Type', required=True, ondelete='RESTRICT',
        help='Business scope of the record. Example: Raw Material or '
        'Packaging.')
    code = fields.Char('Code',
        help='Internal or supplier code used to identify the article. '
        'Example: FT0101 or 946.')
    name = fields.Char('Name', required=True, translate=True,
        help='Name of the approved item. Example: Semillas Atrian vitamina.')
    external_article_name = fields.Char('External Article Name',
        help='Supplier article name when it differs from the internal name. '
        'Example: Mix Atrian Vitamina 50%.')
    state = fields.Selection(RECORD_STATES, 'State', required=True,
        help='Operational state of the record. Example: Approved for active '
        'use or Withdrawn when purchases must stop.')
    start_date = fields.Date('Start Date',
        help='Date from which the approval is valid. Example: the day the '
        'supplier was homologated.')
    end_date = fields.Date('End Date',
        help='Optional end date for the whole approval. Example: a temporary '
        'trial material valid until month end.')
    withdrawal_date = fields.Date('Withdrawal Date',
        help='Date on which the item was withdrawn. Example: 2026-08-04.')
    withdrawal_reason = fields.Text('Withdrawal Reason',
        help='Why the item was withdrawn. Example: missing updated technical '
        'sheet.')
    replacement_record = fields.Many2One('supplier.compliance.record',
        'Replacement Article',
        domain=[
            ('id', '!=', Eval('id', -1)),
            If(Bool(Eval('company')), ('company', '=', Eval('company')), ()),
            If(Bool(Eval('scope_type')),
                ('scope_type', '=', Eval('scope_type')), ()),
            ('active', '=', True),
            ('state', 'in', ['approved', 'conditional']),
            ],
        depends=['id', 'company', 'scope_type'],
        help='Approved replacement record to use in new purchases. Example: '
        'new version of the same flour mix.')
    authorized_by = fields.Many2One('res.user', 'Authorized By',
        help='User that approved the withdrawal or special decision. Example: '
        'quality manager.')
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
            depends=['party'],
            help='Alert or crisis contacts copied from the supplier. Example: '
            'quality email and emergency phone.'),
        'get_contact_mechanisms', setter='set_contact_mechanisms')
    notes = fields.Text('Notes',
        help='Free notes about the approval. Example: source sheet, pending '
        'actions or line restrictions.')
    state_history = fields.One2Many(
        'supplier.compliance.record.state.history', 'record', 'State History',
        help='Chronological log of state changes for this compliance record. '
        'Example: Draft to Approved on the homologation date.')
    requirements = fields.One2Many('supplier.compliance.requirement', 'record',
        'Requirements',
        help='Document and declaration requirements for this record. Example: '
        'technical sheet, OGM declaration and questionnaire.')
    certificates = fields.One2Many('supplier.compliance.certificate', 'record',
        'Certificates',
        help='Certificates linked to this record. Example: IFS or GRS.')
    food_health_registrations = fields.One2Many(
        'supplier.compliance.food.health_registration', 'record',
        'Food Health Registrations',
        help='Food registrations or sanitary registrations of the supplier. '
        'Example: RGS 31.002872/B.')
    food_allergens = fields.One2Many('supplier.compliance.food.allergen',
        'record', 'Food Allergens',
        help='Normalized allergen declaration for the item. Example: Gluten '
        'contains, Sesame may contain.')
    food_origins = fields.One2Many('supplier.compliance.food.origin', 'record',
        'Food Origins',
        help='Ingredient origins declared by the supplier. Example: Egypt '
        '100 percent for yeast.')
    food_analyses = fields.One2Many('supplier.compliance.food.analysis',
        'record', 'Food Analyses',
        help='Analyses requested for food control. Example: contaminants or '
        'microbiology.')
    packaging_family = fields.Many2One(
        'supplier.compliance.packaging.family', 'Packaging Family',
        domain=[
            If(Bool(Eval('party')), ('party', '=', Eval('party')), ()),
            If(Bool(Eval('company')),
                ['OR',
                    ('company', '=', Eval('company')),
                    ('company', '=', None),
                    ],
                ()),
            ],
        depends=['party', 'company'],
        help='Optional packaging family that groups several items under the '
        'same supplier. Example: paper bags family.')
    packaging_specifications = fields.One2Many(
        'supplier.compliance.packaging.specification', 'record',
        'Packaging Specifications',
        help='Technical packaging specifications. Example: kraft bag, direct '
        'food contact.')
    packaging_compliances = fields.One2Many(
        'supplier.compliance.packaging.compliance', 'record',
        'Packaging Compliances',
        help='Declarations of conformity for packaging. Example: EU '
        '1935/2004 statement.')
    packaging_migration_tests = fields.One2Many(
        'supplier.compliance.packaging.migration_test', 'record',
        'Packaging Migration Tests',
        help='Migration studies linked to the record. Example: global '
        'migration report.')
    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments',
        help='Files attached directly to the record. Example: general supplier '
        'PDFs or audit notes.')
    expired = fields.Function(fields.Boolean('Expired',
            help='Checked when the record end date is already in the past.'),
        'on_change_with_expired')
    needs_review = fields.Function(fields.Boolean('Needs Review',
            help='Checked when any linked document needs review or update.'),
        'get_needs_review', searcher='search_needs_review')
    expired_documents = fields.Function(fields.Boolean('Expired Documents',
            help='Checked when any linked document or analysis is expired.'),
        'get_expired_documents', searcher='search_expired_documents')
    request_update = fields.Function(fields.Boolean('Request Update',
            help='Checked when some linked document is within its warning '
            'window.'),
        'get_request_update', searcher='search_request_update')
    purchase_blocked = fields.Function(fields.Boolean('Purchase Blocked',
            help='Checked when the record can not be used in new purchases.'),
        'on_change_with_purchase_blocked')
    affected_open_purchases = fields.Function(
        fields.Integer('Affected Open Purchases',
            help='Number of open purchases currently using this item. '
            'Example: 5.'),
        'get_affected_open_purchases')
    draft_purchases = fields.Function(
        fields.Integer('Draft Purchases',
            help='Number of draft or quotation purchases for this item.'),
        'get_draft_purchases')
    pending_receipt_purchases = fields.Function(
        fields.Integer('Pending Receipt Purchases',
            help='Number of confirmed or processing purchases still waiting '
            'for receipt.'),
        'get_pending_receipt_purchases')
    past_purchases = fields.Function(
        fields.Integer('Past Purchases',
            help='Number of historical purchases already received or '
            'completed.'),
        'get_past_purchases')
    existing_stock = fields.Function(fields.Float('Existing Stock',
            help='Current stock of the linked internal product. Example: '
            '120 kg.'),
        'get_existing_stock')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'set_state_draft': {
                    'depends': ['state'],
                    'invisible': Eval('state') == 'draft',
                    },
                'set_state_pending_documents': {
                    'depends': ['state'],
                    'invisible': Eval('state') == 'pending_documents',
                    },
                'set_state_approved': {
                    'depends': ['state'],
                    'invisible': Eval('state') == 'approved',
                    },
                'set_state_conditional': {
                    'depends': ['state'],
                    'invisible': Eval('state') == 'conditional',
                    },
                'set_state_suspended': {
                    'depends': ['state'],
                    'invisible': Eval('state') == 'suspended',
                    },
                'set_state_expired': {
                    'depends': ['state'],
                    'invisible': Eval('state') == 'expired',
                    },
                'set_state_withdrawn': {
                    'depends': ['state'],
                    'invisible': Eval('state') == 'withdrawn',
                    },
                'set_state_rejected': {
                    'depends': ['state'],
                    'invisible': Eval('state') == 'rejected',
                    },
                'create_template': {},
                'open_affected_open_purchases': {},
                'open_draft_purchases': {},
                'open_pending_receipt_purchases': {},
                'open_past_purchases': {},
                })

    @classmethod
    def __register__(cls, module_name):
        table = cls.__table__()
        cursor = Transaction().connection.cursor()
        super().__register__(module_name)
        cursor.execute(*table.update(
                columns=[table.state],
                values=['approved'],
                where=table.state == 'active'))
        cursor.execute(*table.update(
                columns=[table.state],
                values=['withdrawn'],
                where=table.state == 'obsolete'))

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_authorized_by():
        user = Transaction().user
        if user and user > 0:
            return user

    @fields.depends('state', 'withdrawal_date')
    def on_change_state(self):
        self._apply_withdrawal_defaults()

    def _apply_withdrawal_defaults(self):
        if self.state == 'withdrawn' and not getattr(
                self, 'withdrawal_date', None):
            Date = Pool().get('ir.date')
            self.withdrawal_date = Date.today()
        if self.state == 'withdrawn' and not getattr(
                self, 'authorized_by', None):
            user = Transaction().user
            if user and user > 0:
                self.authorized_by = user

    @fields.depends('end_date')
    def on_change_with_expired(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        return bool(self.end_date and self.end_date < today)

    @fields.depends('state', 'active')
    def on_change_with_purchase_blocked(self, name=None):
        return (not self.active
            or self.state not in self._purchase_allowed_states)

    @classmethod
    def create(cls, vlist):
        records = super().create(vlist)
        cls._apply_state_side_effects(records)
        cls._create_state_history(records, {
                record.id: (None, record.state)
                for record in records if record.state
                })
        return records

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        records = []
        previous_states = {}
        for record_group, _values in zip(actions, actions):
            for record in record_group:
                records.append(record)
                previous_states[record.id] = record.state
        super().write(*args)
        cls._apply_state_side_effects(records)
        transitions = {}
        for record in records:
            previous_state = previous_states.get(record.id)
            if previous_state != record.state:
                transitions[record.id] = (previous_state, record.state)
        cls._create_state_history(records, transitions)

    @classmethod
    def _apply_state_side_effects(cls, records):
        Date = Pool().get('ir.date')
        updates = []
        for record in records:
            values = {}
            if record.state == 'withdrawn' and not record.withdrawal_date:
                values['withdrawal_date'] = Date.today()
            if record.state == 'withdrawn' and not record.authorized_by:
                user = Transaction().user
                if user and user > 0:
                    values['authorized_by'] = user
            if values:
                updates.append((record, values))
        for record, values in updates:
            super().write([record], values)

    @classmethod
    def _create_state_history(cls, records, transitions):
        History = Pool().get('supplier.compliance.record.state.history')
        if not transitions:
            return
        user = Transaction().user
        changed_at = datetime.now()
        histories = []
        for record in records:
            if record.id not in transitions:
                continue
            from_state, to_state = transitions[record.id]
            histories.append({
                    'record': record.id,
                    'from_state': from_state or '',
                    'to_state': to_state,
                    'changed_at': changed_at,
                    'changed_by': user if user and user > 0 else None,
                    })
        if histories:
            with without_check_access():
                History.create(histories)

    @classmethod
    def _set_state(cls, records, state):
        values = {'state': state}
        if state == 'withdrawn':
            Date = Pool().get('ir.date')
            user = Transaction().user
            values['withdrawal_date'] = Date.today()
            if user and user > 0:
                values['authorized_by'] = user
        cls.write(records, values)

    @classmethod
    @ModelView.button
    def set_state_draft(cls, records):
        cls._set_state(records, 'draft')

    @classmethod
    @ModelView.button
    def set_state_pending_documents(cls, records):
        cls._set_state(records, 'pending_documents')

    @classmethod
    @ModelView.button
    def set_state_approved(cls, records):
        cls._set_state(records, 'approved')

    @classmethod
    @ModelView.button
    def set_state_conditional(cls, records):
        cls._set_state(records, 'conditional')

    @classmethod
    @ModelView.button
    def set_state_suspended(cls, records):
        cls._set_state(records, 'suspended')

    @classmethod
    @ModelView.button
    def set_state_expired(cls, records):
        cls._set_state(records, 'expired')

    @classmethod
    @ModelView.button
    def set_state_withdrawn(cls, records):
        cls._set_state(records, 'withdrawn')

    @classmethod
    @ModelView.button
    def set_state_rejected(cls, records):
        cls._set_state(records, 'rejected')

    def get_needs_review(self, name):
        return self.get_expired_documents(name)

    def get_expired_documents(self, name):
        return (self.on_change_with_expired()
            or any(r.on_change_with_expired() for r in self.requirements)
            or any(c.on_change_with_expired() for c in self.certificates)
            or any(r.on_change_with_expired()
                for r in self.food_health_registrations)
            or any(a.on_change_with_due() for a in self.food_analyses)
            or any(c.on_change_with_expired()
                for c in self.packaging_compliances)
            or any(t.on_change_with_due()
                for t in self.packaging_migration_tests))

    @classmethod
    def search_needs_review(cls, name, clause):
        return cls.search_expired_documents(name, clause)

    @classmethod
    def search_expired_documents(cls, name, clause):
        _, operator, value = clause
        if operator not in ('=', '!='):
            raise NotImplementedError(
                'Operator %s not supported for %s' % (operator, name))
        if operator == '!=':
            value = not value
        Date = Pool().get('ir.date')
        Requirement = Pool().get('supplier.compliance.requirement')
        Certificate = Pool().get('supplier.compliance.certificate')
        today = Date.today()
        expired_ids = set(record.id for record in cls.search([
                    ('end_date', '<', today),
                    ]))
        expired_ids.update(
            requirement.record.id for requirement in Requirement.search([])
            if requirement.on_change_with_expired())
        expired_ids.update(
            certificate.record.id for certificate in Certificate.search([])
            if certificate.on_change_with_expired())
        expired_ids.update(record.id for record in cls.search([
                    ['OR',
                        ('food_health_registrations.expiry_date', '<', today),
                        ('food_analyses.next_analysis_date', '<', today),
                        ('packaging_compliances.expiry_date', '<', today),
                        ('packaging_migration_tests.next_review_date', '<', today),
                        ],
                    ]))
        if value:
            return [('id', 'in', list(expired_ids) or [-1])]
        return [('id', 'not in', list(expired_ids) or [-1])]

    def get_request_update(self, name):
        return (any(r.on_change_with_request_update() for r in self.requirements)
            or any(c.on_change_with_request_update()
                for c in self.certificates)
            or any(r.on_change_with_request_update()
                for r in self.food_health_registrations)
            or any(a.on_change_with_request_update()
                for a in self.food_analyses)
            or any(c.on_change_with_request_update()
                for c in self.packaging_compliances)
            or any(t.on_change_with_request_update()
                for t in self.packaging_migration_tests))

    @classmethod
    def search_request_update(cls, name, clause):
        _, operator, value = clause
        if operator not in ('=', '!='):
            raise NotImplementedError(
                'Operator %s not supported for %s' % (operator, name))
        if operator == '!=':
            value = not value
        Requirement = Pool().get('supplier.compliance.requirement')
        Certificate = Pool().get('supplier.compliance.certificate')
        Registration = Pool().get('supplier.compliance.food.health_registration')
        Analysis = Pool().get('supplier.compliance.food.analysis')
        PackagingCompliance = Pool().get(
            'supplier.compliance.packaging.compliance')
        MigrationTest = Pool().get(
            'supplier.compliance.packaging.migration_test')
        req_ids = [r.record.id for r in Requirement.search([
                    ('request_update', '=', True),
                    ])]
        cert_ids = [c.record.id for c in Certificate.search([
                    ('request_update', '=', True),
                    ])]
        registration_ids = [r.record.id for r in Registration.search([
                    ('request_update', '=', True),
                    ])]
        analysis_ids = [a.record.id for a in Analysis.search([
                    ('request_update', '=', True),
                    ])]
        packaging_compliance_ids = [
            c.record.id for c in PackagingCompliance.search([
                    ('request_update', '=', True),
                    ])]
        migration_test_ids = [t.record.id for t in MigrationTest.search([
                    ('request_update', '=', True),
                    ])]
        ids = list(set(
                req_ids + cert_ids + registration_ids + analysis_ids
                + packaging_compliance_ids + migration_test_ids))
        domain = [('id', 'in', ids or [-1])]
        if value:
            return domain
        return [('id', 'not in', ids or [-1])]

    def get_affected_open_purchases(self, name):
        return self._count_purchases([
                ('purchase.state', 'in', ['draft', 'quotation', 'confirmed',
                        'processing']),
                ])

    def get_draft_purchases(self, name):
        return self._count_purchases([
                ('purchase.state', 'in', ['draft', 'quotation']),
                ])

    def get_pending_receipt_purchases(self, name):
        return self._count_purchases([
                ('purchase.state', 'in', ['confirmed', 'processing']),
                ('purchase.shipment_state', '!=', 'received'),
                ])

    def get_past_purchases(self, name):
        return self._count_purchases([
                ['OR',
                    ('purchase.state', '=', 'done'),
                    ['AND',
                        ('purchase.state', '=', 'processing'),
                        ('purchase.shipment_state', '=', 'received'),
                        ],
                    ],
                ])

    def get_existing_stock(self, name):
        if not self.product_template:
            return 0
        context = {}
        if self.company:
            context['company'] = self.company.id
        with Transaction().set_context(context):
            return self.product_template.quantity or 0

    def _get_purchase_line_domain(self):
        domain = [('type', '=', 'line')]
        if self.company:
            domain.append(('purchase.company', '=', self.company.id))
        if self.product_supplier:
            domain.append(('product_supplier', '=', self.product_supplier.id))
        elif self.party and self.product_template:
            domain.extend([
                    ('supplier', '=', self.party.id),
                    ('product.template', '=', self.product_template.id),
                    ])
        else:
            return None
        return domain

    def _count_purchases(self, extra_domain):
        PurchaseLine = Pool().get('purchase.line')
        domain = self._get_purchase_line_domain()
        if domain is None:
            return 0
        domain.extend(extra_domain)
        lines = PurchaseLine.search(domain)
        return len({line.purchase.id for line in lines})

    @classmethod
    def _open_purchase_action(cls, records, extra_domain, suffix):
        PurchaseLine = Pool().get('purchase.line')
        if not records:
            return {}
        record, = records
        domain = record._get_purchase_line_domain()
        if domain is None:
            return {}
        domain.extend(extra_domain)
        purchase_ids = list({
                line.purchase.id for line in PurchaseLine.search(domain)
                })
        return {
            'name': suffix,
            'pyson_domain': PYSONEncoder().encode([
                ('id', 'in', purchase_ids or [-1]),
                ]),
            }

    @classmethod
    def get_purchase_record(cls, company, party, product, product_supplier=None):
        if not party or not product:
            return None
        domain = [
            ('party', '=', party.id),
            ('product_template', '=', product.template.id),
            ('active', '=', True),
            ]
        if company:
            domain.append(('company', '=', company.id))
        records = list(cls.search(domain))
        if not records:
            return None
        if product_supplier:
            exact = [r for r in records if r.product_supplier == product_supplier]
            if exact:
                return exact[0]
        if len(records) == 1:
            return records[0]
        return None

    @classmethod
    def get_purchase_blocking_record(
            cls, company, party, product, product_supplier=None):
        record = cls.get_purchase_record(
            company, party, product, product_supplier=product_supplier)
        if record and record.on_change_with_purchase_blocked():
            return record
        return None

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

    @fields.depends('product_supplier', 'scope_type', 'requirements',
        'certificates', 'food_analyses', 'packaging_compliances',
        'packaging_migration_tests')
    def on_change_product_supplier(self):
        if not self.product_supplier:
            return
        self.party = self.product_supplier.party
        self.product_template = self.product_supplier.template
        if not getattr(self, 'code', None):
            self.code = self.product_supplier.code
        if not getattr(self, 'external_article_name', None):
            self.external_article_name = self.product_supplier.name
        if not getattr(self, 'name', None):
            self.name = self.product_supplier.rec_name
        self._apply_compliance_template()

    @fields.depends('party', 'product_template', 'company', 'product_supplier',
        'scope_type', 'requirements', 'certificates', 'food_analyses',
        'packaging_compliances', 'packaging_migration_tests')
    def on_change_party(self):
        self._sync_product_supplier()

    @fields.depends('party', 'product_template', 'company', 'product_supplier',
        'scope_type', 'requirements', 'certificates', 'food_analyses',
        'packaging_compliances', 'packaging_migration_tests')
    def on_change_product_template(self):
        if not getattr(self, 'product_template', None):
            self.product_supplier = None
            self._apply_compliance_template()
            return
        self._sync_product_supplier()

    @fields.depends('party', 'product_template', 'company', 'product_supplier',
        'scope_type', 'requirements', 'certificates', 'food_analyses',
        'packaging_compliances', 'packaging_migration_tests')
    def on_change_code(self):
        self._sync_product_supplier()

    @fields.depends('party', 'product_template', 'company', 'product_supplier',
        'scope_type', 'requirements', 'certificates', 'food_analyses',
        'packaging_compliances', 'packaging_migration_tests')
    def on_change_name(self):
        self._sync_product_supplier()

    @fields.depends('party', 'product_template', 'company', 'product_supplier',
        'scope_type', 'requirements', 'certificates', 'food_analyses',
        'packaging_compliances', 'packaging_migration_tests')
    def on_change_external_article_name(self):
        self._sync_product_supplier()

    @fields.depends('party', 'product_template', 'company', 'product_supplier',
        'scope_type', 'requirements', 'certificates', 'food_analyses',
        'packaging_compliances', 'packaging_migration_tests')
    def on_change_scope_type(self):
        self._apply_compliance_template()

    @fields.depends('party', 'product_template', 'company', 'product_supplier',
        'scope_type', 'requirements', 'certificates', 'food_analyses',
        'packaging_compliances', 'packaging_migration_tests')
    def _sync_product_supplier(self):
        ProductSupplier = Pool().get('purchase.product_supplier')
        if not self.party:
            self.product_supplier = None
            self._apply_compliance_template()
            return
        domain = [
            ('party', '=', self.party.id),
            ]
        if self.company:
            domain.append([
                    'OR',
                    ('company', '=', self.company.id),
                    ('company', '=', None),
                    ])
        if self.product_template:
            domain.append(('template', '=', self.product_template.id))
        suppliers = list(ProductSupplier.search(domain))
        if not self.product_template:
            suppliers = self._filter_product_suppliers(suppliers)
        if len(suppliers) == 1:
            self.product_supplier, = suppliers
            if not self.product_template:
                self.product_template = self.product_supplier.template
            if not getattr(self, 'code', None):
                self.code = self.product_supplier.code
            if not getattr(self, 'external_article_name', None):
                self.external_article_name = self.product_supplier.name
            if not getattr(self, 'name', None):
                self.name = self.product_supplier.rec_name
        elif self.product_supplier and self.product_supplier not in suppliers:
            self.product_supplier = None
        self._apply_compliance_template()

    def _filter_product_suppliers(self, suppliers):
        normalized_code = self._normalize_match_value(
            getattr(self, 'code', None))
        if normalized_code:
            code_matches = [supplier for supplier in suppliers
                if self._normalize_match_value(supplier.code) == normalized_code]
            if code_matches:
                suppliers = code_matches
        normalized_names = {
            self._normalize_match_value(getattr(self, 'name', None)),
            self._normalize_match_value(
                getattr(self, 'external_article_name', None)),
            }
        normalized_names.discard('')
        if normalized_names and len(suppliers) > 1:
            name_matches = []
            for supplier in suppliers:
                candidate_names = {
                    self._normalize_match_value(supplier.name),
                    self._normalize_match_value(supplier.template.name),
                    }
                if supplier.product:
                    candidate_names.add(
                        self._normalize_match_value(supplier.product.name))
                if candidate_names & normalized_names:
                    name_matches.append(supplier)
            if name_matches:
                suppliers = name_matches
        return suppliers

    @staticmethod
    def _normalize_match_value(value):
        return ' '.join((value or '').split()).strip().casefold()

    def _apply_compliance_template(self):
        Template = Pool().get('supplier.compliance.template')
        template = Template.get_matching_template(
            getattr(self, 'company', None),
            getattr(self, 'scope_type', None),
            getattr(self, 'product_template', None))
        if template:
            template.apply_to_record(self)

    @classmethod
    @ModelView.button_action('supplier_compliance.act_compliance_template_form')
    def create_template(cls, records):
        Template = Pool().get('supplier.compliance.template')
        if not records:
            return {}
        template = Template.create_from_record(records[0])
        return {
            'res_id': [template.id],
            }

    @classmethod
    @ModelView.button_action('purchase.act_purchase_form')
    def open_affected_open_purchases(cls, records):
        return cls._open_purchase_action(
            records,
            [('purchase.state', 'in', ['draft', 'quotation', 'confirmed',
                    'processing'])],
            'Affected Open Purchases')

    @classmethod
    @ModelView.button_action('purchase.act_purchase_form')
    def open_draft_purchases(cls, records):
        return cls._open_purchase_action(
            records,
            [('purchase.state', 'in', ['draft', 'quotation'])],
            'Draft Purchases')

    @classmethod
    @ModelView.button_action('purchase.act_purchase_form')
    def open_pending_receipt_purchases(cls, records):
        return cls._open_purchase_action(
            records,
            [
                ('purchase.state', 'in', ['confirmed', 'processing']),
                ('purchase.shipment_state', '!=', 'received'),
                ],
            'Pending Receipt Purchases')

    @classmethod
    @ModelView.button_action('purchase.act_purchase_form')
    def open_past_purchases(cls, records):
        return cls._open_purchase_action(
            records,
            [[
                    'OR',
                    ('purchase.state', '=', 'done'),
                    ['AND',
                        ('purchase.state', '=', 'processing'),
                        ('purchase.shipment_state', '=', 'received'),
                        ],
                    ]],
            'Past Purchases')

    @classmethod
    def validate(cls, records):
        super().validate(records)
        for record in records:
            record.check_dates()
            record.check_scope()
            record.check_product_supplier()
            record.check_withdrawal()

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

    def check_withdrawal(self):
        if self.state == 'withdrawn' and not self.withdrawal_date:
            raise UserError(gettext(
                'supplier_compliance.msg_record_missing_withdrawal_date',
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


class RecordStateHistory(ModelSQL, ModelView):
    __name__ = 'supplier.compliance.record.state.history'
    _rec_name = 'to_state'
    _order = [('changed_at', 'DESC'), ('id', 'DESC')]

    record = fields.Many2One('supplier.compliance.record', 'Record',
        required=True, ondelete='CASCADE',
        help='Compliance record whose state changed.')
    from_state = fields.Selection(RECORD_STATES_WITH_EMPTY, 'From State',
        help='Previous state before the transition. Example: Draft.')
    to_state = fields.Selection(RECORD_STATES, 'To State', required=True,
        help='New state after the transition. Example: Approved.')
    changed_at = fields.DateTime('Changed At', required=True,
        help='Date and time when the transition was recorded.')
    changed_by = fields.Many2One('res.user', 'Changed By',
        help='User who triggered the state change. Example: quality manager.')

    @staticmethod
    def default_changed_at():
        return datetime.now()


class Requirement(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.requirement'

    record = fields.Many2One('supplier.compliance.record', 'Record',
        required=True, ondelete='CASCADE',
        help='Compliance record that owns this requirement.')
    requirement_type = fields.Many2One('supplier.compliance.requirement.type',
        'Requirement Type', required=True, ondelete='RESTRICT',
        help='Requirement requested for the record. Example: Technical Sheet.')
    versions = fields.One2Many('supplier.compliance.requirement.version',
        'requirement', 'Versions',
        help='History of received versions for this requirement.')
    current_version = fields.Function(fields.Many2One(
            'supplier.compliance.requirement.version', 'Current Version',
            help='Current version used to compute the visible status.'),
        'get_current_version')
    status = fields.Selection([
            ('missing', 'Missing'),
            ('pending', 'Pending'),
            ('valid', 'Valid'),
            ('expired', 'Expired'),
            ('not_applicable', 'Not Applicable'),
            ], 'Status', required=True,
        help='Current status of the requirement. Example: Valid or Pending.')
    version = fields.Char('Version',
        help='Current revision label. Example: Rev. 03.')
    document_date = fields.Date('Document Date',
        help='Date shown on the current document. Example: 2026-07-15.')
    expiry_date = fields.Date('Expiry Date',
        help='Expiry date of the current document when applicable.')
    value = fields.Char('Value',
        help='Free text or reference captured from the document. Example: '
        '45217 or Si en FT.')
    expired = fields.Function(fields.Boolean('Expired',
            help='Checked when the current version expiry date is already '
            'past.'),
        'on_change_with_expired')
    request_update = fields.Function(fields.Boolean('Request Update',
            help='Checked when the current version is inside its warning '
            'window.'),
        'on_change_with_request_update', searcher='search_request_update')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'new_version': {},
                })

    def get_current_version(self, name):
        current_version = self._get_current_version()
        return current_version.id if current_version else None

    def _get_current_version(self):
        current_versions = [v for v in self.versions if v.current]
        if current_versions:
            return current_versions[0]
        if self.versions:
            return self.versions[-1]
        return None

    @staticmethod
    def default_status():
        return 'missing'

    @fields.depends('current_version')
    def on_change_with_expired(self, name=None):
        current_version = self._get_current_version()
        return bool(current_version and current_version.expired)

    @fields.depends('current_version')
    def on_change_with_request_update(self, name=None):
        current_version = self._get_current_version()
        return bool(current_version and current_version.request_update)

    @classmethod
    def search_request_update(cls, name, clause):
        _, operator, value = clause
        if operator not in ('=', '!='):
            raise NotImplementedError(
                'Operator %s not supported for %s' % (operator, name))
        if operator == '!=':
            value = not value
        Version = Pool().get('supplier.compliance.requirement.version')
        ids = list({
                version.requirement.id
                for version in Version.search([('current', '=', True)])
                if version.on_change_with_request_update()
                })
        domain = [('id', 'in', ids or [-1])]
        if value:
            return domain
        return [('id', 'not in', ids or [-1])]

    @classmethod
    def validate(cls, requirements):
        super().validate(requirements)
        for requirement in requirements:
            requirement.check_unique()

    def check_unique(self):
        duplicates = self.search([
                ('record', '=', self.record.id),
                ('requirement_type', '=', self.requirement_type.id),
                ('id', '!=', self.id),
                ], limit=1)
        if duplicates:
            raise UserError(gettext(
                'supplier_compliance.msg_requirement_duplicate',
                requirement=self.rec_name))

    @classmethod
    @ModelView.button
    def new_version(cls, requirements):
        Version = Pool().get('supplier.compliance.requirement.version')
        for requirement in requirements:
            current_version = requirement._get_current_version()
            if current_version:
                Version.write([current_version], {'current': False})
                Version.copy([current_version], default={
                        'current': True,
                        'version': None,
                        'status': 'pending',
                        'document_date': None,
                        'expiry_date': None,
                        'attachments': None,
                        })
            else:
                Version.create([{
                            'requirement': requirement.id,
                            'current': True,
                            'status': 'pending',
                            }])


class RequirementVersion(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.requirement.version'

    requirement = fields.Many2One('supplier.compliance.requirement',
        'Requirement', required=True, ondelete='CASCADE',
        help='Parent requirement of this version line.')
    current = fields.Boolean('Current',
        help='Enable this for the active version. Example: only the latest '
        'approved revision should be current.')
    status = fields.Selection([
            ('missing', 'Missing'),
            ('pending', 'Pending'),
            ('valid', 'Valid'),
            ('expired', 'Expired'),
            ('not_applicable', 'Not Applicable'),
            ], 'Status', required=True,
        help='Status of this version. Example: Pending while waiting for the '
        'new signed file.')
    version = fields.Char('Version',
        help='Revision of this version line. Example: Rev. 04.')
    document_date = fields.Date('Document Date',
        help='Date printed on this version of the document.')
    expiry_date = fields.Date('Expiry Date',
        help='Expiry date of this version when the document expires.')
    value = fields.Char('Value',
        help='Captured value of this version. Example: certificate number or '
        'free text response.')
    notes = fields.Text('Notes',
        help='Comments about this specific version. Example: received by email '
        'without signature.')
    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments',
        help='Files for this version. Example: scanned PDF of the updated '
        'technical sheet.')
    expired = fields.Function(fields.Boolean('Expired',
            help='Checked when this version expiry date is already past.'),
        'on_change_with_expired')
    request_update = fields.Function(fields.Boolean('Request Update',
            help='Checked when this version should be renewed soon.'),
        'on_change_with_request_update')

    @staticmethod
    def default_status():
        return 'missing'

    @fields.depends('expiry_date')
    def on_change_with_expired(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        return bool(self.expiry_date and self.expiry_date < today)

    @fields.depends('expiry_date', '_parent_requirement.requirement_type')
    def on_change_with_request_update(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        notice_days = 0
        if self.requirement and self.requirement.requirement_type:
            notice_days = self.requirement.requirement_type.expiry_notice_days or 0
        if not self.expiry_date or not notice_days:
            return False
        if self.expiry_date < today:
            return False
        return self.expiry_date <= today + timedelta(days=notice_days)

    @classmethod
    def validate(cls, versions):
        super().validate(versions)
        for version in versions:
            version.check_dates()

    def check_dates(self):
        if (self.document_date and self.expiry_date
                and self.expiry_date < self.document_date):
            raise UserError(gettext(
                'supplier_compliance.msg_requirement_invalid_dates',
                requirement=self.rec_name))

    @classmethod
    def create(cls, vlist):
        versions = super().create(vlist)
        cls._sync_current(versions)
        return versions

    @classmethod
    def write(cls, *args):
        super().write(*args)
        versions = []
        actions = iter(args)
        for version_group, _values in zip(actions, actions):
            versions.extend(version_group)
        cls._sync_current(versions)

    @classmethod
    def delete(cls, versions):
        requirements = []
        for version in versions:
            if version.requirement and version.requirement not in requirements:
                requirements.append(version.requirement)
        super().delete(versions)
        cls._refresh_requirements(requirements)

    @classmethod
    def _sync_current(cls, versions):
        requirements = []
        to_write = []
        for version in versions:
            if version.requirement and version.requirement not in requirements:
                requirements.append(version.requirement)
            if not version.current:
                continue
            siblings = cls.search([
                    ('requirement', '=', version.requirement.id),
                    ('id', '!=', version.id),
                    ('current', '=', True),
                    ])
            if siblings:
                to_write.extend(siblings)
        if to_write:
            super().write(to_write, {'current': False})
            for version in to_write:
                if (version.requirement
                        and version.requirement not in requirements):
                    requirements.append(version.requirement)
        cls._refresh_requirements(requirements)

    @classmethod
    def _refresh_requirements(cls, requirements):
        Requirement = Pool().get('supplier.compliance.requirement')
        for requirement in requirements:
            current = requirement._get_current_version()
            values = {
                'status': 'missing',
                'version': None,
                'document_date': None,
                'expiry_date': None,
                'value': None,
                }
            if current:
                values.update({
                        'status': current.status,
                        'version': current.version,
                        'document_date': current.document_date,
                        'expiry_date': current.expiry_date,
                        'value': current.value,
                        })
            Requirement.write([requirement], values)


class Certificate(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.certificate'

    record = fields.Many2One('supplier.compliance.record', 'Record',
        required=True, ondelete='CASCADE',
        help='Compliance record that owns this certificate.')
    scheme = fields.Many2One('supplier.compliance.scheme', 'Scheme',
        required=True, ondelete='RESTRICT',
        help='Certificate scheme. Example: IFS or FSC.')
    versions = fields.One2Many('supplier.compliance.certificate.version',
        'certificate', 'Versions',
        help='History of versions of this certificate.')
    current_version = fields.Function(fields.Many2One(
            'supplier.compliance.certificate.version', 'Current Version',
            help='Current certificate version used in the header fields.'),
        'get_current_version')
    version = fields.Char('Version',
        help='Current certificate revision. Example: 2026 issue.')
    certificate_number = fields.Char('Certificate Number',
        help='Current certificate number. Example: IFS-2026-001.')
    issuer = fields.Char('Issuer',
        help='Certification body. Example: SGS.')
    issue_date = fields.Date('Issue Date',
        help='Issue date of the current certificate.')
    expiry_date = fields.Date('Expiry Date',
        help='Expiry date of the current certificate.')
    scope_text = fields.Text('Scope',
        help='Declared scope of the certificate. Example: production of bread '
        'improvers.')
    expired = fields.Function(fields.Boolean('Expired',
            help='Checked when the current certificate has expired.'),
        'on_change_with_expired')
    request_update = fields.Function(fields.Boolean('Request Update',
            help='Checked when the certificate is close to expiry.'),
        'on_change_with_request_update', searcher='search_request_update')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'new_version': {},
                })

    def get_current_version(self, name):
        current_version = self._get_current_version()
        return current_version.id if current_version else None

    def _get_current_version(self):
        current_versions = [v for v in self.versions if v.current]
        if current_versions:
            return current_versions[0]
        if self.versions:
            return self.versions[-1]
        return None

    @fields.depends('current_version')
    def on_change_with_expired(self, name=None):
        current_version = self._get_current_version()
        return bool(current_version and current_version.expired)

    @fields.depends('current_version')
    def on_change_with_request_update(self, name=None):
        current_version = self._get_current_version()
        return bool(current_version and current_version.request_update)

    @classmethod
    def search_request_update(cls, name, clause):
        _, operator, value = clause
        if operator not in ('=', '!='):
            raise NotImplementedError(
                'Operator %s not supported for %s' % (operator, name))
        if operator == '!=':
            value = not value
        Version = Pool().get('supplier.compliance.certificate.version')
        ids = list({
                version.certificate.id
                for version in Version.search([('current', '=', True)])
                if version.on_change_with_request_update()
                })
        domain = [('id', 'in', ids or [-1])]
        if value:
            return domain
        return [('id', 'not in', ids or [-1])]

    @classmethod
    def validate(cls, certificates):
        super().validate(certificates)
        for certificate in certificates:
            certificate.check_unique()

    def check_unique(self):
        duplicates = self.search([
                ('record', '=', self.record.id),
                ('scheme', '=', self.scheme.id),
                ('id', '!=', self.id),
                ], limit=1)
        if duplicates:
            raise UserError(gettext(
                'supplier_compliance.msg_certificate_duplicate',
                certificate=self.rec_name))

    @classmethod
    @ModelView.button
    def new_version(cls, certificates):
        Version = Pool().get('supplier.compliance.certificate.version')
        for certificate in certificates:
            current_version = certificate._get_current_version()
            if current_version:
                Version.write([current_version], {'current': False})
                Version.copy([current_version], default={
                        'current': True,
                        'version': None,
                        'issue_date': None,
                        'expiry_date': None,
                        'attachments': None,
                        })
            else:
                Version.create([{
                            'certificate': certificate.id,
                            'current': True,
                            }])


class CertificateVersion(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.certificate.version'

    certificate = fields.Many2One('supplier.compliance.certificate',
        'Certificate', required=True, ondelete='CASCADE',
        help='Parent certificate of this version line.')
    current = fields.Boolean('Current',
        help='Enable this on the active certificate version.')
    version = fields.Char('Version',
        help='Version label of this certificate line. Example: Rev. B.')
    certificate_number = fields.Char('Certificate Number',
        help='Certificate number of this version.')
    issuer = fields.Char('Issuer',
        help='Issuer of this version. Example: Bureau Veritas.')
    issue_date = fields.Date('Issue Date',
        help='Issue date of this certificate version.')
    expiry_date = fields.Date('Expiry Date',
        help='Expiry date of this certificate version.')
    scope_text = fields.Text('Scope',
        help='Scope declared in this version.')
    notes = fields.Text('Notes',
        help='Comments about this version. Example: superseded by customer '
        'audit request.')
    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments',
        help='Files attached to this certificate version.')
    expired = fields.Function(fields.Boolean('Expired',
            help='Checked when this certificate version has expired.'),
        'on_change_with_expired')
    request_update = fields.Function(fields.Boolean('Request Update',
            help='Checked when this version is close to expiry.'),
        'on_change_with_request_update')

    @fields.depends('expiry_date')
    def on_change_with_expired(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        return bool(self.expiry_date and self.expiry_date < today)

    @fields.depends('expiry_date', '_parent_certificate.scheme')
    def on_change_with_request_update(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        notice_days = 0
        if self.certificate and self.certificate.scheme:
            notice_days = self.certificate.scheme.expiry_notice_days or 0
        if not self.expiry_date or not notice_days:
            return False
        if self.expiry_date < today:
            return False
        return self.expiry_date <= today + timedelta(days=notice_days)

    @classmethod
    def validate(cls, versions):
        super().validate(versions)
        for version in versions:
            version.check_dates()

    def check_dates(self):
        if (self.issue_date and self.expiry_date
                and self.expiry_date < self.issue_date):
            raise UserError(gettext(
                'supplier_compliance.msg_certificate_invalid_dates',
                certificate=self.rec_name))

    @classmethod
    def create(cls, vlist):
        versions = super().create(vlist)
        cls._sync_current(versions)
        return versions

    @classmethod
    def write(cls, *args):
        super().write(*args)
        versions = []
        actions = iter(args)
        for version_group, _values in zip(actions, actions):
            versions.extend(version_group)
        cls._sync_current(versions)

    @classmethod
    def delete(cls, versions):
        certificates = []
        for version in versions:
            if version.certificate and version.certificate not in certificates:
                certificates.append(version.certificate)
        super().delete(versions)
        cls._refresh_certificates(certificates)

    @classmethod
    def _sync_current(cls, versions):
        certificates = []
        to_write = []
        for version in versions:
            if version.certificate and version.certificate not in certificates:
                certificates.append(version.certificate)
            if not version.current:
                continue
            siblings = cls.search([
                    ('certificate', '=', version.certificate.id),
                    ('id', '!=', version.id),
                    ('current', '=', True),
                    ])
            if siblings:
                to_write.extend(siblings)
        if to_write:
            super().write(to_write, {'current': False})
            for version in to_write:
                if (version.certificate
                        and version.certificate not in certificates):
                    certificates.append(version.certificate)
        cls._refresh_certificates(certificates)

    @classmethod
    def _refresh_certificates(cls, certificates):
        Certificate = Pool().get('supplier.compliance.certificate')
        for certificate in certificates:
            current = certificate._get_current_version()
            values = {
                'version': None,
                'certificate_number': None,
                'issuer': None,
                'issue_date': None,
                'expiry_date': None,
                'scope_text': None,
                }
            if current:
                values.update({
                        'version': current.version,
                        'certificate_number': current.certificate_number,
                        'issuer': current.issuer,
                        'issue_date': current.issue_date,
                        'expiry_date': current.expiry_date,
                        'scope_text': current.scope_text,
                        })
            Certificate.write([certificate], values)
