import unittest
from datetime import date
from decimal import Decimal

from proteus import Model
from proteus.config import get_config
from trytond.model.exceptions import AccessError, DomainValidationError
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class TestManualTemplate(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):
        activate_modules(['purchase', 'supplier_compliance'])
        create_company()
        company = get_company()
        Party = Model.get('party.party')
        supplier = Party(name='Manual Template Supplier')
        supplier.save()
        Scope = Model.get('supplier.compliance.scope.type')
        scope = Scope(name='Materials')
        scope.save()
        other_scope = Scope(name='Services')
        other_scope.save()
        Category = Model.get('product.category')
        category = Category(name='Ingredients')
        category.save()
        other_category = Category(name='Other Materials')
        other_category.save()
        RequirementType = Model.get('supplier.compliance.requirement.type')
        automatic_requirement = RequirementType(name='Technical Sheet')
        automatic_requirement.save()
        manual_requirement = RequirementType(name='Supplier Declaration')
        manual_requirement.save()
        Scheme = Model.get('supplier.compliance.scheme')
        scheme = Scheme(name='Test Scheme')
        scheme.save()
        Template = Model.get('supplier.compliance.template')
        automatic = Template(company=company, scope_type=scope,
            name='Automatic', product_category=category)
        automatic.requirements.new(requirement_type=automatic_requirement)
        automatic.save()
        manual = Template(company=company, scope_type=scope,
            name='Manual', product_category=other_category)
        manual.requirements.new(requirement_type=manual_requirement)
        manual.certificates.new(scheme=scheme)
        manual.food_analyses.new(analysis_type='Contaminants',
            review_notice_days=20)
        manual.packaging_compliances.new(reference='DECLARATION',
            expiry_notice_days=30)
        manual.packaging_migration_tests.new(migration_type='global_migration',
            review_notice_days=40)
        manual.save()
        Product = Model.get('product.template')
        Uom = Model.get('product.uom')
        unit, = Uom.find([('name', '=', 'Unit')])
        product = Product(name='Ingredient', default_uom=unit,
            type='goods', purchasable=True, list_price=Decimal('1'))
        product.categories.append(category)
        product.product_suppliers.new(party=supplier, company=company)
        product.save()

        Record = Model.get('supplier.compliance.record')
        record = Record(company=company, party=supplier, scope_type=scope,
            product_template=product, name='Ingredient Approval')
        self.assertIsNone(record.compliance_template)
        self.assertEqual([r.requirement_type.id for r in record.requirements],
            [automatic_requirement.id])
        existing = record.requirements[0]
        version = existing.versions.new(version='Received revision',
            document_date=date.today(), status='valid', current=True)
        version.attachments.new(name='Original declaration', type='data',
            data=b'original supplier document')
        record.save()
        existing_id = record.requirements[0].id

        # A manual choice overrides the category and preserves received data.
        record.compliance_template = manual
        record.save()
        record.reload()
        self.assertEqual(record.compliance_template.id, manual.id)
        self.assertEqual({r.requirement_type.id for r in record.requirements},
            {automatic_requirement.id, manual_requirement.id})
        existing, = [r for r in record.requirements if r.id == existing_id]
        self.assertEqual(existing.status, 'valid')
        self.assertEqual(existing.versions[0].attachments[0].data,
            b'original supplier document')
        self.assertEqual(len(record.certificates), 1)
        self.assertEqual(record.food_analyses[0].review_notice_days, 20)
        self.assertEqual(record.packaging_compliances[0].expiry_notice_days, 30)
        self.assertEqual(
            record.packaging_migration_tests[0].review_notice_days, 40)
        record.name = 'Renamed approval'
        record.code = 'MANUAL'
        record.save()
        record.reload()
        self.assertEqual(record.compliance_template.id, manual.id)
        self.assertEqual(len(record.requirements), 2)
        self.assertEqual(len(record.packaging_compliances), 1)

        # Manual templates also work without an internal product.
        service_supplier = Party(name='Supplier Without Products')
        service_supplier.save()
        no_product = Record(company=company, party=service_supplier,
            scope_type=scope, name='Manual Without Product')
        no_product.compliance_template = manual
        no_product.save()
        self.assertIsNone(no_product.product_template)
        self.assertEqual([r.requirement_type.id
                for r in no_product.requirements], [manual_requirement.id])
        # Selecting a product keeps the manual choice, even in another category.
        no_product.party = supplier
        no_product.product_template = product
        self.assertEqual(no_product.compliance_template.id, manual.id)
        self.assertEqual([r.requirement_type.id
                for r in no_product.requirements], [manual_requirement.id])
        no_product.compliance_template = None
        self.assertEqual({r.requirement_type.id
                for r in no_product.requirements},
            {manual_requirement.id, automatic_requirement.id})
        no_product.save()
        no_product.compliance_template = manual
        no_product.scope_type = other_scope
        self.assertIsNone(no_product.compliance_template)
        self.assertEqual(len(no_product.requirements), 2)
        no_product.save()

        # The server also rejects incompatible assignments made without UI.
        with self.assertRaises(DomainValidationError):
            Record.write([no_product.id], {'compliance_template': manual.id},
                get_config().context)
        Company = Model.get('company.company')
        other_party = Party(name='Other Company')
        other_party.save()
        other_company = Company(party=other_party, currency=company.currency)
        other_company.save()
        company_change = Record(company=company, scope_type=scope,
            name='Company Change')
        company_change.compliance_template = manual
        company_change.company = other_company
        self.assertIsNone(company_change.compliance_template)
        self.assertEqual(len(company_change.requirements), 1)

        # Operational users can select and read templates without editing them.
        User = Model.get('res.user')
        Group = Model.get('res.group')
        user = User(name='Quality User', login='manual_template_quality')
        group, = Group.find([('name', '=', 'Technical Sheets User')])
        user.groups.append(group)
        user.companies.append(company)
        user.company = company
        user.save()
        config = get_config()
        admin = config.user
        config.user = user.id
        try:
            User = Model.get('res.user')
            with config.set_context(User.get_preferences(True, {})):
                Template = Model.get('supplier.compliance.template')
                Record = Model.get('supplier.compliance.record')
                selected, = Template.find([('id', '=', manual.id)])
                operational = Record(record.id)
                operational.compliance_template = None
                operational.compliance_template = selected
                operational.save()
                operational.reload()
                self.assertEqual(operational.compliance_template.id, manual.id)
                self.assertEqual(len(operational.requirements), 2)
                selected.name = 'Unauthorized change'
                with self.assertRaises(AccessError):
                    selected.save()
        finally:
            config.user = admin
