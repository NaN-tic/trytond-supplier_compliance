import unittest
from decimal import Decimal
from datetime import date, timedelta

from proteus import Model
from trytond.exceptions import UserError, UserWarning
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
        today = date.today()

        _ = create_company()
        company = get_company()
        PurchaseConfiguration = Model.get('purchase.configuration')
        configuration = PurchaseConfiguration(1)

        Country = Model.get('country.country')
        egypt = Country(name='Egypt', code='EG')
        egypt.save()

        Party = Model.get('party.party')
        supplier = Party(name='Supplier')
        supplier.addresses.new()
        supplier.save()

        Category = Model.get('product.category')
        ingredient_category = Category(name='Ingredients')
        ingredient_category.save()

        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        template = ProductTemplate()
        template.name = 'Bread Improver'
        template.default_uom = unit
        template.type = 'goods'
        template.purchasable = True
        template.list_price = Decimal('10')
        template.categories.append(ingredient_category)
        product_supplier = template.product_suppliers.new()
        product_supplier.party = supplier
        product_supplier.company = company
        product_supplier.code = 'FT0101'
        template.save()
        product_supplier, = template.product_suppliers

        extra_template = ProductTemplate()
        extra_template.name = 'Other Ingredient'
        extra_template.default_uom = unit
        extra_template.type = 'goods'
        extra_template.purchasable = True
        extra_template.list_price = Decimal('11')
        extra_supplier = extra_template.product_suppliers.new()
        extra_supplier.party = supplier
        extra_supplier.company = company
        extra_supplier.code = 'OTR001'
        extra_template.save()

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
        technical_sheet.expiry_notice_days = 10
        technical_sheet.save()

        Scheme = Model.get('supplier.compliance.scheme')
        scheme = Scheme(name='GRS')
        scheme.code = 'GRS'
        scheme.expiry_notice_days = 15
        scheme.save()

        ComplianceTemplate = Model.get('supplier.compliance.template')
        compliance_template = ComplianceTemplate()
        compliance_template.company = company
        compliance_template.name = 'Raw Material Ingredients'
        compliance_template.scope_type = raw_material_scope
        compliance_template.product_category = ingredient_category
        template_requirement = compliance_template.requirements.new()
        template_requirement.requirement_type = technical_sheet
        template_certificate = compliance_template.certificates.new()
        template_certificate.scheme = scheme
        template_analysis = compliance_template.food_analyses.new()
        template_analysis.analysis_type = 'Contaminants'
        template_analysis.review_notice_days = 45
        template_packaging_compliance = (
            compliance_template.packaging_compliances.new())
        template_packaging_compliance.reference = 'DOC-001'
        template_packaging_compliance.declared_regulation = '1935/2004'
        template_packaging_compliance.expiry_notice_days = 90
        template_migration_test = (
            compliance_template.packaging_migration_tests.new())
        template_migration_test.migration_type = 'global_migration'
        template_migration_test.review_notice_days = 60
        compliance_template.save()

        FoodAllergenType = Model.get('supplier.compliance.food.allergen.type')
        gluten = FoodAllergenType(name='Gluten')
        gluten.code = 'GL'
        gluten.save()

        PackagingFamily = Model.get('supplier.compliance.packaging.family')
        family = PackagingFamily()
        family.company = company
        family.party = supplier
        family.name = 'Paper Bags'
        family.code = 'BAG'
        family.material = 'Paper / PE'
        family.save()

        Record = Model.get('supplier.compliance.record')
        RecordStateHistory = Model.get(
            'supplier.compliance.record.state.history')
        templated_record = Record()
        templated_record.company = company
        templated_record.party = supplier
        templated_record.scope_type = raw_material_scope
        templated_record.product_template = template
        self.assertEqual(len(templated_record.requirements), 1)
        self.assertEqual(len(templated_record.certificates), 1)
        self.assertEqual(
            templated_record.requirements[0].requirement_type.id,
            technical_sheet.id)
        self.assertEqual(
            templated_record.certificates[0].scheme.id,
            scheme.id)
        self.assertEqual(len(templated_record.food_analyses), 1)
        self.assertEqual(
            templated_record.food_analyses[0].analysis_type,
            'Contaminants')
        self.assertEqual(len(templated_record.packaging_compliances), 1)
        self.assertEqual(
            templated_record.packaging_compliances[0].reference,
            'DOC-001')
        self.assertEqual(len(templated_record.packaging_migration_tests), 1)
        self.assertEqual(
            templated_record.packaging_migration_tests[0].migration_type,
            'global_migration')

        record = Record()
        record.company = company
        record.party = supplier
        record.product_template = template
        record.product_supplier = product_supplier
        record.packaging_family = family
        record.scope_type = raw_material_scope
        record.code = 'FT0101'
        record.name = 'Levadura homologada'
        record.state = 'approved'
        record.start_date = today - timedelta(days=60)
        record.end_date = today + timedelta(days=365)
        health_registration = record.food_health_registrations.new()
        health_registration.registration_number = '31.002872/B'
        health_registration.country = 'ES'
        health_registration.activity = 'Food handling'
        health_registration.start_date = today - timedelta(days=120)
        health_registration.expiry_date = today + timedelta(days=180)
        health_registration.expiry_notice_days = 30
        health_registration.state = 'valid'
        allergen = record.food_allergens.new()
        allergen.allergen = gluten
        allergen.status = 'contains'
        allergen.source = 'Supplier declaration'
        allergen.declaration_date = today - timedelta(days=10)
        origin = record.food_origins.new()
        origin.ingredient = 'Yeast'
        origin.country = egypt
        origin.percentage = Decimal('100')
        origin.document_confirmed = True
        analysis, = record.food_analyses
        analysis.laboratory = 'Lab'
        analysis.report_number = 'LAB-001'
        analysis.sample_date = today - timedelta(days=20)
        analysis.report_date = today - timedelta(days=15)
        analysis.next_analysis_date = today + timedelta(days=30)
        analysis.review_notice_days = 45
        analysis.conform = True
        specification = record.packaging_specifications.new()
        specification.kind = 'bag'
        specification.primary_material = 'Kraft'
        specification.food_contact = True
        specification.contact_type = 'direct'
        specification.recycled = False
        compliance, = record.packaging_compliances
        compliance.declared_regulation = '1935/2004'
        compliance.issue_date = today - timedelta(days=20)
        compliance.expiry_date = today + timedelta(days=60)
        compliance.expiry_notice_days = 90
        compliance.status = 'valid'
        migration_test, = record.packaging_migration_tests
        migration_test.laboratory = 'Lab'
        migration_test.report_number = 'MIG-001'
        migration_test.test_date = today - timedelta(days=12)
        migration_test.next_review_date = today + timedelta(days=45)
        migration_test.review_notice_days = 60
        migration_test.conform = True
        record.save()
        record.reload()
        Requirement = Model.get('supplier.compliance.requirement')
        requirement, = record.requirements
        requirement, = Requirement.find([('id', '=', requirement.id)])
        requirement_version = requirement.versions.new()
        requirement_version.current = True
        requirement_version.status = 'valid'
        requirement_version.document_date = today - timedelta(days=30)
        requirement_version.expiry_date = today + timedelta(days=5)
        requirement_version.value = 'Rev. 03'
        requirement.save()
        Certificate = Model.get('supplier.compliance.certificate')
        certificate, = record.certificates
        certificate, = Certificate.find([('id', '=', certificate.id)])
        certificate_version = certificate.versions.new()
        certificate_version.current = True
        certificate_version.certificate_number = 'GRS-001'
        certificate_version.issue_date = today - timedelta(days=90)
        certificate_version.expiry_date = today + timedelta(days=7)
        certificate.save()
        FoodHealthRegistration = Model.get(
            'supplier.compliance.food.health_registration')
        health_registration, = record.food_health_registrations
        health_registration, = FoodHealthRegistration.find([
                ('id', '=', health_registration.id)])
        health_registration_version = health_registration.versions.new()
        health_registration_version.current = True
        health_registration_version.country = 'ES'
        health_registration_version.activity = 'Food handling'
        health_registration_version.start_date = today - timedelta(days=120)
        health_registration_version.expiry_date = today + timedelta(days=180)
        health_registration_version.state = 'valid'
        health_registration.save()
        FoodOrigin = Model.get('supplier.compliance.food.origin')
        origin, = record.food_origins
        origin, = FoodOrigin.find([('id', '=', origin.id)])
        origin_version = origin.versions.new()
        origin_version.current = True
        origin_version.country = egypt
        origin_version.percentage = Decimal('100')
        origin_version.document_confirmed = True
        origin.save()
        PackagingCompliance = Model.get('supplier.compliance.packaging.compliance')
        compliance, = record.packaging_compliances
        compliance, = PackagingCompliance.find([('id', '=', compliance.id)])
        compliance_version = compliance.versions.new()
        compliance_version.current = True
        compliance_version.declared_regulation = '1935/2004'
        compliance_version.issue_date = today - timedelta(days=20)
        compliance_version.expiry_date = today + timedelta(days=60)
        compliance_version.status = 'valid'
        compliance.save()
        FoodAnalysis = Model.get('supplier.compliance.food.analysis')
        analysis, = record.food_analyses
        analysis, = FoodAnalysis.find([('id', '=', analysis.id)])
        analysis_version = analysis.versions.new()
        analysis_version.current = True
        analysis_version.laboratory = 'Lab'
        analysis_version.report_number = 'LAB-001'
        analysis_version.sample_date = today - timedelta(days=20)
        analysis_version.report_date = today - timedelta(days=15)
        analysis_version.next_analysis_date = today + timedelta(days=30)
        analysis_version.conform = True
        analysis.save()
        PackagingMigrationTest = Model.get(
            'supplier.compliance.packaging.migration_test')
        migration_test, = record.packaging_migration_tests
        migration_test, = PackagingMigrationTest.find([
                ('id', '=', migration_test.id)])
        migration_version = migration_test.versions.new()
        migration_version.current = True
        migration_version.migration_type = 'global_migration'
        migration_version.laboratory = 'Lab'
        migration_version.report_number = 'MIG-001'
        migration_version.test_date = today - timedelta(days=12)
        migration_version.next_review_date = today + timedelta(days=45)
        migration_version.conform = True
        migration_test.save()
        record.reload()

        self.assertEqual(record.party.name, 'Supplier')
        self.assertEqual(record.product_template.name, 'Bread Improver')
        self.assertEqual(record.packaging_family.name, 'Paper Bags')
        self.assertTrue(record.requirements[0].request_update)
        self.assertTrue(record.certificates[0].request_update)
        self.assertFalse(record.food_health_registrations[0].request_update)
        self.assertEqual(record.food_allergens[0].allergen.name, 'Gluten')
        self.assertEqual(record.food_origins[0].country.code, 'EG')
        self.assertEqual(len(record.food_origins[0].versions), 1)
        self.assertTrue(record.food_analyses[0].request_update)
        self.assertFalse(record.food_analyses[0].due)
        self.assertEqual(len(record.food_health_registrations[0].versions), 1)
        self.assertEqual(len(record.food_analyses[0].versions), 1)
        self.assertEqual(len(record.packaging_compliances[0].versions), 1)
        self.assertEqual(record.packaging_specifications[0].primary_material,
            'Kraft')
        self.assertTrue(record.packaging_compliances[0].request_update)
        self.assertFalse(record.packaging_compliances[0].expired)
        self.assertTrue(record.packaging_migration_tests[0].request_update)
        self.assertFalse(record.packaging_migration_tests[0].due)
        self.assertEqual(len(record.packaging_migration_tests[0].versions), 1)
        self.assertTrue(record.request_update)
        self.assertFalse(record.expired_documents)
        self.assertFalse(record.purchase_blocked)
        self.assertEqual(record.existing_stock, 0)
        self.assertEqual(Record.find([('request_update', '=', True)]), [record])
        state_history = RecordStateHistory.find([('record', '=', record.id)])
        self.assertEqual(len(state_history), 1)
        self.assertEqual(state_history[0].from_state, '')
        self.assertEqual(state_history[0].to_state, 'approved')

        update_record = Record()
        update_record.company = company
        update_record.party = supplier
        update_record.product_template = template
        update_record.scope_type = raw_material_scope
        update_record.name = 'Update Record'
        update_record.state = 'approved'
        update_health_registration = update_record.food_health_registrations.new()
        update_health_registration.registration_number = '26.07609/B'
        update_health_registration.expiry_notice_days = 20
        update_health_registration.state = 'valid'
        update_analysis = update_record.food_analyses.new()
        update_analysis.analysis_type = 'Microbiology'
        update_analysis.review_notice_days = 20
        update_migration_test = update_record.packaging_migration_tests.new()
        update_migration_test.migration_type = 'specific_migration'
        update_migration_test.review_notice_days = 20
        update_record.save()
        update_record.reload()
        update_health_registration, = update_record.food_health_registrations
        update_health_registration, = FoodHealthRegistration.find([
                ('id', '=', update_health_registration.id)])
        update_health_version = update_health_registration.versions.new()
        update_health_version.current = True
        update_health_version.country = 'ES'
        update_health_version.activity = 'Food handling'
        update_health_version.start_date = today - timedelta(days=10)
        update_health_version.expiry_date = today + timedelta(days=10)
        update_health_version.state = 'valid'
        update_health_registration.save()
        update_analysis = [
            a for a in update_record.food_analyses
            if a.analysis_type == 'Microbiology'][0]
        update_analysis, = FoodAnalysis.find([('id', '=', update_analysis.id)])
        update_analysis_version = update_analysis.versions.new()
        update_analysis_version.current = True
        update_analysis_version.laboratory = 'Lab'
        update_analysis_version.report_number = 'LAB-002'
        update_analysis_version.sample_date = today - timedelta(days=10)
        update_analysis_version.report_date = today - timedelta(days=8)
        update_analysis_version.next_analysis_date = today + timedelta(days=10)
        update_analysis_version.conform = True
        update_analysis.save()
        update_migration_test = [
            t for t in update_record.packaging_migration_tests
            if t.migration_type == 'specific_migration'][0]
        update_migration_test, = PackagingMigrationTest.find([
                ('id', '=', update_migration_test.id)])
        update_migration_version = update_migration_test.versions.new()
        update_migration_version.current = True
        update_migration_version.migration_type = 'specific_migration'
        update_migration_version.laboratory = 'Lab'
        update_migration_version.report_number = 'MIG-002'
        update_migration_version.test_date = today - timedelta(days=5)
        update_migration_version.next_review_date = today + timedelta(days=10)
        update_migration_version.conform = True
        update_migration_test.save()
        update_record.reload()
        self.assertTrue(update_record.food_health_registrations[0].request_update)
        self.assertTrue(any(
                analysis.request_update
                for analysis in update_record.food_analyses))
        self.assertTrue(any(
                test.request_update
                for test in update_record.packaging_migration_tests))
        self.assertTrue(update_record.request_update)
        self.assertEqual(set(Record.find([('request_update', '=', True)])),
            {record, update_record})

        Purchase = Model.get('purchase.purchase')
        purchase = Purchase()
        purchase.party = supplier
        purchase.invoice_method = 'order'
        purchase_line = purchase.lines.new()
        purchase_line.product = template.products[0]
        purchase_line.quantity = 2.0
        purchase_line.unit_price = Decimal('10')
        purchase.save()

        record.reload()
        self.assertEqual(record.affected_open_purchases, 1)
        self.assertEqual(record.draft_purchases, 1)
        self.assertEqual(record.pending_receipt_purchases, 0)
        self.assertEqual(record.past_purchases, 0)
        record.replacement_record = update_record
        record.save()
        record.click('set_state_withdrawn')
        record.reload()
        self.assertTrue(record.purchase_blocked)
        self.assertIsNotNone(record.withdrawal_date)
        state_history = RecordStateHistory.find([('record', '=', record.id)])
        self.assertEqual(len(state_history), 2)
        self.assertIn(
            ('approved', 'withdrawn'),
            {(line.from_state, line.to_state) for line in state_history})
        with self.assertRaises(UserError):
            purchase.click('quote')

        configuration.supplier_compliance_purchase_mode = 'none'
        configuration.save()
        purchase.click('quote')
        self.assertEqual(purchase.state, 'quotation')

        warning_purchase = Purchase()
        warning_purchase.party = supplier
        warning_purchase.invoice_method = 'order'
        warning_line = warning_purchase.lines.new()
        warning_line.product = template.products[0]
        warning_line.quantity = 1.0
        warning_line.unit_price = Decimal('8')
        warning_purchase.save()
        configuration.supplier_compliance_purchase_mode = 'warning'
        configuration.save()
        with self.assertRaises(UserWarning):
            warning_purchase.click('quote')

        Record.click([record], 'create_template')
        compliance_template.reload()
        self.assertEqual(len(compliance_template.food_analyses), 1)
        self.assertEqual(len(compliance_template.packaging_compliances), 1)
        self.assertEqual(len(compliance_template.packaging_migration_tests), 1)

        expired_record = Record()
        expired_record.company = company
        expired_record.party = supplier
        expired_record.product_template = template
        expired_record.scope_type = raw_material_scope
        expired_record.name = 'Expired Record'
        expired_record.state = 'approved'
        expired_record.save()
        expired_record.reload()
        expired_requirement, = expired_record.requirements
        expired_requirement, = Requirement.find([('id', '=', expired_requirement.id)])
        expired_requirement_version = expired_requirement.versions.new()
        expired_requirement_version.current = True
        expired_requirement_version.status = 'valid'
        expired_requirement_version.expiry_date = today - timedelta(days=1)
        expired_requirement.save()
        expired_record.reload()
        self.assertTrue(expired_record.expired_documents)
        self.assertEqual(Record.find([('expired_documents', '=', True)]),
            [expired_record])

        auto_record = Record()
        auto_record.company = company
        auto_record.party = supplier
        auto_record.product_template = template
        self.assertEqual(auto_record.product_supplier.id, product_supplier.id)

        global_template = ProductTemplate()
        global_template.name = 'Global Supplier Product'
        global_template.default_uom = unit
        global_template.type = 'goods'
        global_template.purchasable = True
        global_template.list_price = Decimal('12')
        global_product_supplier = global_template.product_suppliers.new()
        global_product_supplier.party = supplier
        global_template.save()
        global_product_supplier, = global_template.product_suppliers

        global_record = Record()
        global_record.company = company
        global_record.party = supplier
        global_record.product_template = global_template
        self.assertEqual(
            global_record.product_supplier.id, global_product_supplier.id)

        requirement_version.current = False
        requirement_version.version = 'Rev. 03'
        old_requirement = requirement.versions.new()
        old_requirement.current = False
        old_requirement.version = 'Rev. 02'
        old_requirement.status = 'expired'
        old_requirement.document_date = today - timedelta(days=400)
        old_requirement.expiry_date = today - timedelta(days=200)
        old_requirement.value = 'Historic'
        new_requirement = requirement.versions.new()
        new_requirement.current = True
        new_requirement.version = 'Rev. 04'
        new_requirement.status = 'valid'
        new_requirement.document_date = today
        new_requirement.expiry_date = today + timedelta(days=30)
        new_requirement.value = 'Current'
        requirement.save()
        record.reload()
        current_requirements = [
            r for r in record.requirements
            if r.requirement_type.id == technical_sheet.id]
        self.assertEqual(len(current_requirements), 1)
        self.assertEqual(len(current_requirements[0].versions), 3)

        Requirement.click([current_requirements[0]], 'new_version')
        record.reload()
        current_requirement = [
            r for r in record.requirements
            if r.requirement_type.id == technical_sheet.id][0]
        self.assertEqual(len(current_requirement.versions), 4)
        pending_versions = [
            v for v in current_requirement.versions if v.status == 'pending']
        self.assertEqual(len(pending_versions), 1)
        self.assertIsNone(pending_versions[0].document_date)
        self.assertIsNone(pending_versions[0].expiry_date)

        FoodHealthRegistration.click([record.food_health_registrations[0]],
            'new_version')
        PackagingCompliance.click([record.packaging_compliances[0]],
            'new_version')
        FoodOrigin.click([record.food_origins[0]], 'new_version')
        FoodAnalysis.click([record.food_analyses[0]], 'new_version')
        PackagingMigrationTest.click([record.packaging_migration_tests[0]],
            'new_version')
        record.reload()
        self.assertEqual(len(record.food_health_registrations[0].versions), 2)
        self.assertEqual(len(record.food_origins[0].versions), 2)
        self.assertEqual(len(record.food_analyses[0].versions), 2)
        self.assertEqual(len(record.packaging_compliances[0].versions), 2)
        self.assertEqual(len(record.packaging_migration_tests[0].versions), 2)

        service_record = Record()
        service_record.company = company
        service_record.party = supplier
        service_record.scope_type = service_scope
        service_record.name = 'Residus'
        service_record.state = 'draft'
        service_record.save()

        other_supplier = Party(name='Other Supplier')
        other_supplier.save()

        invalid_record = Record()
        invalid_record.company = company
        invalid_record.party = other_supplier
        invalid_record.scope_type = raw_material_scope
        invalid_record.name = 'Invalid'
        invalid_record.state = 'draft'
        with self.assertRaises(UserError):
            invalid_record.save()
