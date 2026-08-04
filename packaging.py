# This file is part of the supplier_compliance module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from datetime import timedelta
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.model import DeactivableMixin, ModelSQL, ModelView, fields, \
    sequence_ordered
from trytond.pool import Pool
from trytond.transaction import Transaction


class PackagingFamily(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'supplier.compliance.packaging.family'
    _rec_name = 'name'

    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='CASCADE',
        help='Empresa a la que pertenece la familia de envases. '
        'Ejemplo: "Valero Forn Tradicional, S. L.".')
    party = fields.Many2One('party.party', 'Supplier', required=True,
        ondelete='CASCADE',
        help='Proveedor al que se asocia la familia de envases. '
        'Ejemplo: "DISCERMA DEL VALLES S.L.".')
    name = fields.Char('Name', required=True, translate=True,
        help='Nombre identificativo de la familia. '
        'Ejemplo: "Bosses Pages".')
    code = fields.Char('Code',
        help='Código interno para agrupar referencias similares. '
        'Ejemplo: "BOLSAS-PAGES".')
    material = fields.Char('Material',
        help='Material principal compartido por la familia. '
        'Ejemplo: "Papel + PE".')
    notes = fields.Text('Notes',
        help='Observaciones generales de la familia. '
        'Ejemplo: "Aplica la misma declaración de conformidad".')
    records = fields.One2Many('supplier.compliance.record', 'packaging_family',
        'Records',
        help='Registros de homologación que usan esta familia de envases.')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')


class PackagingSpecification(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.packaging.specification'

    record = fields.Many2One('supplier.compliance.record', 'Record',
        required=True, ondelete='CASCADE',
        help='Registro de homologación al que pertenece esta especificación.')
    kind = fields.Selection([
            ('bag', 'Bag'),
            ('box', 'Box'),
            ('film', 'Film'),
            ('tray', 'Tray'),
            ('other', 'Other'),
            ], 'Packaging Type', required=True,
        help='Tipo principal de envase o embalaje. '
        'Ejemplo: "Bag".')
    primary_material = fields.Char('Primary Material', required=True,
        help='Material principal del envase. Ejemplo: "Kraft".')
    additional_materials = fields.Text('Additional Materials',
        help='Materiales adicionales o multicapa. '
        'Ejemplo: "Ventana PE transparente".')
    food_contact = fields.Boolean('Food Contact',
        help='Marca si el material entra en contacto directo o potencial con '
        'el alimento.')
    contact_type = fields.Selection([
            ('direct', 'Direct'),
            ('indirect', 'Indirect'),
            ('none', 'No Contact'),
            ], 'Contact Type',
        help='Tipo de contacto con el alimento. '
        'Ejemplo: "Direct" para una bolsa de pan.')
    authorized_foods = fields.Char('Authorized Foods',
        help='Alimentos para los que está autorizado el uso. '
        'Ejemplo: "Pan y bollería".')
    use_conditions = fields.Text('Use Conditions',
        help='Condiciones de uso o limitaciones. '
        'Ejemplo: "Temperatura ambiente, uso monodosis".')
    recycled = fields.Boolean('Recycled',
        help='Indica si el envase incluye material reciclado.')
    recycled_percentage = fields.Numeric('Recycled Percentage',
        digits=(5, 2),
        help='Porcentaje de material reciclado. Ejemplo: 30.00.')
    dimensions = fields.Char('Dimensions',
        help='Medidas del envase. Ejemplo: "40x31+4 cm".')
    grammage = fields.Char('Grammage',
        help='Gramaje o peso por superficie/material. Ejemplo: "70 g/m2".')
    notes = fields.Text('Notes',
        help='Observaciones técnicas adicionales. '
        'Ejemplo: "Bolsa pan payés Carrefour".')

    @staticmethod
    def default_kind():
        return 'other'

    @staticmethod
    def default_contact_type():
        return 'none'


class PackagingCompliance(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.packaging.compliance'

    record = fields.Many2One('supplier.compliance.record', 'Record',
        required=True, ondelete='CASCADE',
        help='Registro de homologación al que pertenece esta conformidad de '
        'envase.')
    reference = fields.Char('Reference',
        help='Referencia o número de la declaración de conformidad. '
        'Ejemplo: "DOC-CE-2026-014".')
    versions = fields.One2Many('supplier.compliance.packaging.compliance.version',
        'compliance', 'Versions',
        help='Histórico de versiones de la declaración o certificado.')
    current_version = fields.Function(fields.Many2One(
            'supplier.compliance.packaging.compliance.version',
            'Current Version',
            help='Versión actualmente vigente de la conformidad.'),
        'get_current_version')
    issue_date = fields.Date('Issue Date',
        help='Fecha de emisión del documento vigente. Ejemplo: 2026-03-15.')
    review_date = fields.Date('Review Date',
        help='Fecha de revisión del documento, si el proveedor la indica. '
        'Ejemplo: 2027-03-15.')
    expiry_date = fields.Date('Expiry Date',
        help='Fecha de caducidad del documento vigente. '
        'Ejemplo: 2027-03-15.')
    expiry_notice_days = fields.Integer('Expiry Notice Days',
        help='Días de antelación para pedir actualización antes de que '
        'caduque. Ejemplo: 45.')
    covered_materials = fields.Text('Covered Materials',
        help='Materiales o referencias cubiertas por la conformidad. '
        'Ejemplo: "Papel kraft y ventana PE".')
    authorized_foods = fields.Char('Authorized Foods',
        help='Tipos de alimento autorizados por la declaración. '
        'Ejemplo: "Productos de panadería".')
    restrictions = fields.Text('Restrictions',
        help='Restricciones de uso del documento. '
        'Ejemplo: "No apto para alimentos grasos".')
    declared_regulation = fields.Char('Declared Regulation',
        help='Normativa declarada por el proveedor. '
        'Ejemplo: "Reg. (CE) 1935/2004".')
    status = fields.Selection([
            ('pending', 'Pending'),
            ('valid', 'Valid'),
            ('expired', 'Expired'),
            ('rejected', 'Rejected'),
            ('superseded', 'Superseded'),
            ], 'Status', required=True,
        help='Estado actual del documento de conformidad. '
        'Ejemplo: "Valid".')
    notes = fields.Text('Notes',
        help='Observaciones de revisión o cobertura del documento.')
    expired = fields.Function(fields.Boolean('Expired',
            help='Indica si la conformidad vigente ya ha caducado.'),
        'on_change_with_expired')
    request_update = fields.Function(fields.Boolean('Request Update',
            help='Se activa cuando la conformidad entra en el plazo de aviso '
            'para solicitar una nueva versión.'),
        'on_change_with_request_update', searcher='search_request_update')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'new_version': {},
                })

    @staticmethod
    def default_status():
        return 'pending'

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

    @fields.depends('expiry_date')
    def on_change_with_expired(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        return bool(self.expiry_date and self.expiry_date < today)

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
        Version = Pool().get('supplier.compliance.packaging.compliance.version')
        ids = list({
                version.compliance.id
                for version in Version.search([('current', '=', True)])
                if version.on_change_with_request_update()
                })
        domain = [('id', 'in', ids or [-1])]
        if value:
            return domain
        return [('id', 'not in', ids or [-1])]

    @classmethod
    def validate(cls, compliances):
        super().validate(compliances)
        for compliance in compliances:
            compliance.check_unique()
            compliance.check_dates()

    def check_unique(self):
        duplicates = self.search([
                ('record', '=', self.record.id),
                ('reference', '=', self.reference),
                ('id', '!=', self.id),
                ], limit=1)
        if duplicates:
            raise UserError(gettext(
                'supplier_compliance.msg_packaging_compliance_duplicate',
                compliance=self.rec_name))

    def check_dates(self):
        if (self.issue_date and self.expiry_date
                and self.expiry_date < self.issue_date):
            raise UserError(gettext(
                'supplier_compliance.msg_packaging_compliance_invalid_dates',
                compliance=self.rec_name))

    @classmethod
    @ModelView.button
    def new_version(cls, compliances):
        Version = Pool().get('supplier.compliance.packaging.compliance.version')
        for compliance in compliances:
            current_version = compliance._get_current_version()
            if current_version:
                Version.write([current_version], {'current': False})
                Version.copy([current_version], default={
                        'current': True,
                        'issue_date': None,
                        'review_date': None,
                        'expiry_date': None,
                        'attachments': None,
                        })
            else:
                Version.create([{
                            'compliance': compliance.id,
                            'current': True,
                            'status': 'pending',
                            }])


class PackagingComplianceVersion(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.packaging.compliance.version'

    compliance = fields.Many2One('supplier.compliance.packaging.compliance',
        'Compliance', required=True, ondelete='CASCADE',
        help='Conformidad principal a la que pertenece esta versión.')
    current = fields.Boolean('Current',
        help='Marca esta versión como la versión vigente del documento.')
    issue_date = fields.Date('Issue Date',
        help='Fecha de emisión de esta versión. Ejemplo: 2026-03-15.')
    review_date = fields.Date('Review Date',
        help='Fecha de revisión de esta versión.')
    expiry_date = fields.Date('Expiry Date',
        help='Fecha de caducidad de esta versión.')
    covered_materials = fields.Text('Covered Materials',
        help='Materiales cubiertos en esta versión concreta.')
    authorized_foods = fields.Char('Authorized Foods',
        help='Alimentos autorizados en esta versión. '
        'Ejemplo: "Pan y bollería".')
    restrictions = fields.Text('Restrictions',
        help='Limitaciones o exclusiones de esta versión.')
    declared_regulation = fields.Char('Declared Regulation',
        help='Normativa citada en esta versión del documento.')
    status = fields.Selection([
            ('pending', 'Pending'),
            ('valid', 'Valid'),
            ('expired', 'Expired'),
            ('rejected', 'Rejected'),
            ('superseded', 'Superseded'),
            ], 'Status', required=True,
        help='Estado documental de esta versión. '
        'Ejemplo: "Superseded".')
    notes = fields.Text('Notes',
        help='Observaciones de esta versión. '
        'Ejemplo: "Sustituida por revisión 04".')
    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments',
        help='Archivos adjuntos de esta versión, como PDF firmado o ensayo '
        'relacionado.')
    expired = fields.Function(fields.Boolean('Expired',
            help='Indica si esta versión ya ha caducado.'),
        'on_change_with_expired')
    request_update = fields.Function(fields.Boolean('Request Update',
            help='Indica si esta versión entra en el periodo de aviso previo '
            'a la caducidad.'),
        'on_change_with_request_update')

    @staticmethod
    def default_status():
        return 'pending'

    @fields.depends('expiry_date')
    def on_change_with_expired(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        return bool(self.expiry_date and self.expiry_date < today)

    @fields.depends('expiry_date', '_parent_compliance.expiry_notice_days')
    def on_change_with_request_update(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        notice_days = 0
        if self.compliance:
            notice_days = self.compliance.expiry_notice_days or 0
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
                'supplier_compliance.msg_packaging_compliance_invalid_dates',
                compliance=self.rec_name))

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
        compliances = []
        for version in versions:
            if version.compliance and version.compliance not in compliances:
                compliances.append(version.compliance)
        super().delete(versions)
        cls._refresh_compliances(compliances)

    @classmethod
    def _sync_current(cls, versions):
        compliances = []
        to_write = []
        for version in versions:
            if version.compliance and version.compliance not in compliances:
                compliances.append(version.compliance)
            if not version.current:
                continue
            siblings = cls.search([
                    ('compliance', '=', version.compliance.id),
                    ('id', '!=', version.id),
                    ('current', '=', True),
                    ])
            if siblings:
                to_write.extend(siblings)
        if to_write:
            super().write(to_write, {'current': False})
            for version in to_write:
                if (version.compliance
                        and version.compliance not in compliances):
                    compliances.append(version.compliance)
        cls._refresh_compliances(compliances)

    @classmethod
    def _refresh_compliances(cls, compliances):
        Compliance = Pool().get('supplier.compliance.packaging.compliance')
        for compliance in compliances:
            current = compliance._get_current_version()
            values = {
                'issue_date': None,
                'review_date': None,
                'expiry_date': None,
                'covered_materials': None,
                'authorized_foods': None,
                'restrictions': None,
                'declared_regulation': None,
                'status': 'pending',
                'notes': None,
                }
            if current:
                values.update({
                        'issue_date': current.issue_date,
                        'review_date': current.review_date,
                        'expiry_date': current.expiry_date,
                        'covered_materials': current.covered_materials,
                        'authorized_foods': current.authorized_foods,
                        'restrictions': current.restrictions,
                        'declared_regulation': current.declared_regulation,
                        'status': current.status,
                        'notes': current.notes,
                        })
            Compliance.write([compliance], values)


class PackagingMigrationTest(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.packaging.migration_test'

    record = fields.Many2One('supplier.compliance.record', 'Record',
        required=True, ondelete='CASCADE',
        help='Registro de homologación al que pertenece este ensayo de '
        'migración.')
    versions = fields.One2Many(
        'supplier.compliance.packaging.migration_test.version',
        'migration_test', 'Versions',
        help='Histórico de versiones del ensayo de migración.')
    current_version = fields.Function(fields.Many2One(
            'supplier.compliance.packaging.migration_test.version',
            'Current Version',
            help='Versión vigente del ensayo de migración.'),
        'get_current_version')
    laboratory = fields.Char('Laboratory',
        help='Laboratorio que realizó el ensayo. Ejemplo: "Ainia".')
    report_number = fields.Char('Report Number',
        help='Número del informe de ensayo. Ejemplo: "MIG-2026-55".')
    test_date = fields.Date('Test Date',
        help='Fecha de realización del ensayo. Ejemplo: 2026-02-01.')
    migration_type = fields.Selection([
            ('global_migration', 'Global Migration'),
            ('specific_migration', 'Specific Migration'),
            ('heavy_metals', 'Heavy Metals'),
            ('printing_inks', 'Printing Inks'),
            ('other', 'Other'),
            ], 'Migration Type', required=True,
        help='Tipo de ensayo realizado. Ejemplo: "Global Migration".')
    food_simulant = fields.Char('Food Simulant',
        help='Simulante alimentario usado en el ensayo. '
        'Ejemplo: "Simulante A".')
    duration = fields.Char('Duration',
        help='Duración del ensayo. Ejemplo: "10 días".')
    temperature = fields.Char('Temperature',
        help='Temperatura aplicada en el ensayo. Ejemplo: "40 C".')
    result = fields.Char('Result',
        help='Resultado principal del ensayo. Ejemplo: "2 mg/dm2".')
    limit_value = fields.Char('Limit Value',
        help='Límite normativo comparado. Ejemplo: "10 mg/dm2".')
    conform = fields.Boolean('Conform',
        help='Marca si el ensayo cumple el límite aplicable.')
    next_review_date = fields.Date('Next Review Date',
        help='Fecha prevista para repetir o revisar el ensayo. '
        'Ejemplo: 2027-02-01.')
    review_notice_days = fields.Integer('Review Notice Days',
        help='Días de antelación para avisar antes de la próxima revisión. '
        'Ejemplo: 60.')
    notes = fields.Text('Notes',
        help='Observaciones del ensayo o del criterio de revisión.')
    due = fields.Function(fields.Boolean('Due',
            help='Indica si la próxima revisión ya está vencida.'),
        'on_change_with_due')
    request_update = fields.Function(fields.Boolean('Request Update',
            help='Se activa cuando la próxima revisión entra en el plazo de '
            'aviso configurado.'),
        'on_change_with_request_update', searcher='search_request_update')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'new_version': {},
                })

    @staticmethod
    def default_migration_type():
        return 'other'

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

    @fields.depends('next_review_date')
    def on_change_with_due(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        return bool(self.next_review_date and self.next_review_date < today)

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
        Version = Pool().get(
            'supplier.compliance.packaging.migration_test.version')
        ids = list({
                version.migration_test.id
                for version in Version.search([('current', '=', True)])
                if version.on_change_with_request_update()
                })
        domain = [('id', 'in', ids or [-1])]
        if value:
            return domain
        return [('id', 'not in', ids or [-1])]

    @classmethod
    def validate(cls, tests):
        super().validate(tests)
        for test in tests:
            test.check_unique()

    def check_unique(self):
        duplicates = self.search([
                ('record', '=', self.record.id),
                ('migration_type', '=', self.migration_type),
                ('id', '!=', self.id),
                ], limit=1)
        if duplicates:
            raise UserError(gettext(
                'supplier_compliance.msg_packaging_migration_test_duplicate',
                test=self.rec_name))

    @classmethod
    @ModelView.button
    def new_version(cls, tests):
        Version = Pool().get(
            'supplier.compliance.packaging.migration_test.version')
        for test in tests:
            current_version = test._get_current_version()
            if current_version:
                Version.write([current_version], {'current': False})
                Version.copy([current_version], default={
                        'current': True,
                        'test_date': None,
                        'next_review_date': None,
                        'attachments': None,
                        })
            else:
                Version.create([{
                            'migration_test': test.id,
                            'current': True,
                            'migration_type': test.migration_type,
                            }])


class PackagingMigrationTestVersion(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.packaging.migration_test.version'

    migration_test = fields.Many2One(
        'supplier.compliance.packaging.migration_test', 'Migration Test',
        required=True, ondelete='CASCADE',
        help='Ensayo principal al que pertenece esta versión.')
    current = fields.Boolean('Current',
        help='Marca esta versión como la vigente para el ensayo.')
    laboratory = fields.Char('Laboratory',
        help='Laboratorio de esta versión. Ejemplo: "SGS".')
    report_number = fields.Char('Report Number',
        help='Número del informe en esta versión. Ejemplo: "SGS-MIG-11".')
    test_date = fields.Date('Test Date',
        help='Fecha del ensayo en esta versión.')
    migration_type = fields.Selection([
            ('global_migration', 'Global Migration'),
            ('specific_migration', 'Specific Migration'),
            ('heavy_metals', 'Heavy Metals'),
            ('printing_inks', 'Printing Inks'),
            ('other', 'Other'),
            ], 'Migration Type', required=True,
        help='Tipo de ensayo registrado en esta versión.')
    food_simulant = fields.Char('Food Simulant',
        help='Simulante usado en esta versión. Ejemplo: "B".')
    duration = fields.Char('Duration',
        help='Duración declarada en esta versión. Ejemplo: "2 h".')
    temperature = fields.Char('Temperature',
        help='Temperatura declarada en esta versión. Ejemplo: "70 C".')
    result = fields.Char('Result',
        help='Resultado de esta versión. Ejemplo: "Conforme".')
    limit_value = fields.Char('Limit Value',
        help='Límite aplicado en esta versión. Ejemplo: "<= 10 mg/dm2".')
    conform = fields.Boolean('Conform',
        help='Marca si esta versión cumple con el límite definido.')
    next_review_date = fields.Date('Next Review Date',
        help='Fecha prevista para revisar o repetir esta versión del ensayo.')
    notes = fields.Text('Notes',
        help='Notas de esta versión del ensayo.')
    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments',
        help='Adjuntos asociados a esta versión, como informe PDF o hoja de '
        'resultados.')
    due = fields.Function(fields.Boolean('Due',
            help='Indica si esta versión ya ha superado su fecha de revisión.'),
        'on_change_with_due')
    request_update = fields.Function(fields.Boolean('Request Update',
            help='Indica si esta versión entra en el plazo de aviso previo a '
            'la revisión.'),
        'on_change_with_request_update')

    @staticmethod
    def default_migration_type():
        return 'other'

    @fields.depends('next_review_date')
    def on_change_with_due(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        return bool(self.next_review_date and self.next_review_date < today)

    @fields.depends('next_review_date',
        '_parent_migration_test.review_notice_days')
    def on_change_with_request_update(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        notice_days = 0
        if self.migration_test:
            notice_days = self.migration_test.review_notice_days or 0
        if not self.next_review_date or not notice_days:
            return False
        if self.next_review_date < today:
            return False
        return self.next_review_date <= today + timedelta(days=notice_days)

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
        tests = []
        for version in versions:
            if version.migration_test and version.migration_test not in tests:
                tests.append(version.migration_test)
        super().delete(versions)
        cls._refresh_tests(tests)

    @classmethod
    def _sync_current(cls, versions):
        tests = []
        to_write = []
        for version in versions:
            if version.migration_test and version.migration_test not in tests:
                tests.append(version.migration_test)
            if not version.current:
                continue
            siblings = cls.search([
                    ('migration_test', '=', version.migration_test.id),
                    ('id', '!=', version.id),
                    ('current', '=', True),
                    ])
            if siblings:
                to_write.extend(siblings)
        if to_write:
            super().write(to_write, {'current': False})
            for version in to_write:
                if version.migration_test and version.migration_test not in tests:
                    tests.append(version.migration_test)
        cls._refresh_tests(tests)

    @classmethod
    def _refresh_tests(cls, tests):
        MigrationTest = Pool().get(
            'supplier.compliance.packaging.migration_test')
        for test in tests:
            current = test._get_current_version()
            values = {
                'laboratory': None,
                'report_number': None,
                'test_date': None,
                'migration_type': test.migration_type or 'other',
                'food_simulant': None,
                'duration': None,
                'temperature': None,
                'result': None,
                'limit_value': None,
                'conform': False,
                'next_review_date': None,
                'notes': None,
                }
            if current:
                values.update({
                        'laboratory': current.laboratory,
                        'report_number': current.report_number,
                        'test_date': current.test_date,
                        'migration_type': current.migration_type,
                        'food_simulant': current.food_simulant,
                        'duration': current.duration,
                        'temperature': current.temperature,
                        'result': current.result,
                        'limit_value': current.limit_value,
                        'conform': current.conform,
                        'next_review_date': current.next_review_date,
                        'notes': current.notes,
                        })
            MigrationTest.write([test], values)
