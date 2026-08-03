import unittest
from decimal import Decimal
from datetime import date, timedelta

from proteus import Model
from trytond.exceptions import UserError
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):
        activate_modules(['purchase', 'supplier_compliance'])

        _ = create_company()
        company = get_company()

        Party = Model.get('party.party')
        supplier = Party(name='Supplier')
        supplier.save()

        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        template = ProductTemplate()
        template.name = 'Bread Improver'
        template.default_uom = unit
        template.type = 'goods'
        template.purchasable = True
        template.list_price = Decimal('10')
        product_supplier = template.product_suppliers.new()
        product_supplier.party = supplier
        product_supplier.company = company
        template.save()
        product_supplier, = template.product_suppliers

        ScopeType = Model.get('supplier.compliance.scope.type')
        raw_material_scope = ScopeType(name='Raw Material')
        raw_material_scope.code = 'MP'
        raw_material_scope.product_required = True
        raw_material_scope.save()
        service_scope = ScopeType(name='Service')
        service_scope.code = 'SERV'
        service_scope.save()

        RequirementType = Model.get('supplier.compliance.requirement.type')
        technical_sheet = RequirementType(name='Technical Sheet')
        technical_sheet.code = 'FT'
        technical_sheet.kind = 'document'
        technical_sheet.requires_document = True
        technical_sheet.tracks_expiry = True
        technical_sheet.save()

        Scheme = Model.get('supplier.compliance.scheme')
        scheme = Scheme(name='GRS')
        scheme.code = 'GRS'
        scheme.save()

        Record = Model.get('supplier.compliance.record')
        record = Record()
        record.company = company
        record.party = supplier
        record.product_template = template
        record.product_supplier = product_supplier
        record.scope_type = raw_material_scope
        record.code = 'FT0101'
        record.name = 'Levadura homologada'
        record.state = 'active'
        record.start_date = date(2026, 1, 1)
        record.end_date = date(2026, 12, 31)
        requirement = record.requirements.new()
        requirement.requirement_type = technical_sheet
        requirement.status = 'valid'
        requirement.document_date = date(2026, 1, 15)
        requirement.expiry_date = date.today() - timedelta(days=1)
        requirement.value = 'Rev. 03'
        certificate = record.certificates.new()
        certificate.scheme = scheme
        certificate.certificate_number = 'GRS-001'
        certificate.issue_date = date(2026, 1, 1)
        certificate.expiry_date = date.today() - timedelta(days=1)
        record.save()

        self.assertEqual(record.party.name, 'Supplier')
        self.assertEqual(record.product_template.name, 'Bread Improver')
        self.assertTrue(record.requirements[0].expired)
        self.assertTrue(record.certificates[0].expired)

        service_record = Record()
        service_record.company = company
        service_record.party = supplier
        service_record.scope_type = service_scope
        service_record.name = 'Residus'
        service_record.state = 'draft'
        service_record.save()

        invalid_record = Record()
        invalid_record.company = company
        invalid_record.party = supplier
        invalid_record.scope_type = raw_material_scope
        invalid_record.name = 'Invalid'
        invalid_record.state = 'draft'
        with self.assertRaises(UserError):
            invalid_record.save()
