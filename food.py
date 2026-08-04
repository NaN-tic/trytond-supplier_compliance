# This file is part of the supplier_compliance module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from datetime import timedelta
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.model import DeactivableMixin, ModelSQL, ModelView, fields, \
    sequence_ordered
from trytond.pool import Pool


class FoodAllergenType(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'supplier.compliance.food.allergen.type'
    _rec_name = 'name'

    name = fields.Char('Name', required=True, translate=True,
        help='Nombre del alérgeno para clasificar declaraciones del proveedor. '
        'Ejemplo: "Gluten".')
    code = fields.Char('Code',
        help='Código corto interno para identificar el alérgeno. '
        'Ejemplo: "GL".')
    description = fields.Text('Description',
        help='Descripción opcional del alérgeno o de su criterio de uso. '
        'Ejemplo: "Incluye trigo, cebada y centeno".')


class FoodHealthRegistration(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.food.health_registration'

    record = fields.Many2One('supplier.compliance.record', 'Record',
        required=True, ondelete='CASCADE',
        help='Registro de homologación al que pertenece este registro '
        'sanitario. Ejemplo: APLIENA / Raw Material.')
    registration_number = fields.Char('Registration Number', required=True,
        help='Número del registro sanitario o autorización oficial. '
        'Ejemplo: "31.002872/B".')
    versions = fields.One2Many('supplier.compliance.food.health_registration.version',
        'registration', 'Versions',
        help='Histórico de versiones del registro sanitario para conservar '
        'renovaciones, caducidades y adjuntos.')
    current_version = fields.Function(fields.Many2One(
            'supplier.compliance.food.health_registration.version',
            'Current Version',
            help='Versión actualmente vigente del registro sanitario.'),
        'get_current_version')
    country = fields.Char('Country',
        help='País del registro sanitario vigente. Ejemplo: "España".')
    issuing_authority = fields.Char('Issuing Authority',
        help='Organismo que emite o valida el registro. '
        'Ejemplo: "Generalitat de Catalunya".')
    activity = fields.Char('Activity',
        help='Actividad autorizada por el registro. '
        'Ejemplo: "Fabricación de ingredientes alimentarios".')
    start_date = fields.Date('Start Date',
        help='Fecha de inicio de vigencia del registro. '
        'Ejemplo: 2026-01-01.')
    expiry_date = fields.Date('Expiry Date',
        help='Fecha en la que caduca el registro actual. '
        'Ejemplo: 2027-01-01.')
    expiry_notice_days = fields.Integer('Expiry Notice Days',
        help='Días de antelación para marcar que debe pedirse renovación '
        'antes de la caducidad. Ejemplo: 30.')
    state = fields.Selection([
            ('draft', 'Draft'),
            ('valid', 'Valid'),
            ('expired', 'Expired'),
            ('obsolete', 'Obsolete'),
            ], 'State', required=True,
        help='Situación actual del registro sanitario. '
        'Ejemplo: "Valid" cuando el documento vigente está en regla.')
    expired = fields.Function(fields.Boolean('Expired',
            help='Indica si la fecha de caducidad ya ha pasado.'),
        'on_change_with_expired')
    request_update = fields.Function(fields.Boolean('Request Update',
            help='Se activa cuando el registro entra en el plazo de aviso '
            'para solicitar una renovación. Ejemplo: registro que caduca en '
            '15 días.'),
        'on_change_with_request_update', searcher='search_request_update')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'new_version': {},
                })

    @staticmethod
    def default_state():
        return 'draft'

    def get_current_version(self, name):
        current_version = self._get_current_version()
        return current_version.id if current_version else None

    def _get_current_version(self):
        versions = list(self.versions or [])
        current_versions = [v for v in versions if v.current]
        if current_versions:
            return current_versions[0]
        if versions:
            return versions[-1]
        return None

    @staticmethod
    def default_versions():
        return ()

    @fields.depends('expiry_date')
    def on_change_with_expired(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        return bool(self.expiry_date and self.expiry_date < today)

    @fields.depends('expiry_date', 'expiry_notice_days')
    def on_change_with_request_update(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        notice_days = self.expiry_notice_days or 0
        if not self.expiry_date or not notice_days:
            return False
        if self.expiry_date < today:
            return False
        return self.expiry_date <= today + timedelta(days=notice_days)

    @classmethod
    def search_request_update(cls, name, clause):
        _, operator, value = clause
        if operator not in ('=', '!='):
            raise NotImplementedError(
                'Operator %s not supported for %s' % (operator, name))
        if operator == '!=':
            value = not value
        Version = Pool().get('supplier.compliance.food.health_registration.version')
        ids = list({
                version.registration.id
                for version in Version.search([('current', '=', True)])
                if version.on_change_with_request_update()
                })
        domain = [('id', 'in', ids or [-1])]
        if value:
            return domain
        return [('id', 'not in', ids or [-1])]

    @classmethod
    def validate(cls, registrations):
        super().validate(registrations)
        for registration in registrations:
            registration.check_unique()
            registration.check_dates()

    def check_unique(self):
        duplicates = self.search([
                ('record', '=', self.record.id),
                ('registration_number', '=', self.registration_number),
                ('id', '!=', self.id),
                ], limit=1)
        if duplicates:
            raise UserError(gettext(
                'supplier_compliance.msg_food_health_registration_duplicate',
                registration=self.rec_name))

    def check_dates(self):
        if (self.start_date and self.expiry_date
                and self.expiry_date < self.start_date):
            raise UserError(gettext(
                'supplier_compliance.msg_food_health_registration_invalid_dates',
                registration=self.rec_name))

    @classmethod
    @ModelView.button
    def new_version(cls, registrations):
        Version = Pool().get('supplier.compliance.food.health_registration.version')
        for registration in registrations:
            current_version = registration._get_current_version()
            if current_version:
                Version.write([current_version], {'current': False})
                Version.copy([current_version], default={
                        'current': True,
                        'start_date': None,
                        'expiry_date': None,
                        'attachments': None,
                        })
            else:
                Version.create([{
                            'registration': registration.id,
                            'current': True,
                            'state': 'draft',
                            }])


class FoodHealthRegistrationVersion(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.food.health_registration.version'

    registration = fields.Many2One('supplier.compliance.food.health_registration',
        'Registration', required=True, ondelete='CASCADE',
        help='Registro sanitario principal al que pertenece esta versión.')
    current = fields.Boolean('Current',
        help='Marca esta versión como la actualmente vigente. Solo debería '
        'haber una versión actual por registro.')
    country = fields.Char('Country',
        help='País informado en esta versión del registro. '
        'Ejemplo: "España".')
    issuing_authority = fields.Char('Issuing Authority',
        help='Autoridad emisora en esta versión. '
        'Ejemplo: "AESAN".')
    activity = fields.Char('Activity',
        help='Actividad cubierta en esta versión. '
        'Ejemplo: "Envasado de alimentos".')
    start_date = fields.Date('Start Date',
        help='Fecha inicial de vigencia de esta versión. '
        'Ejemplo: 2026-01-01.')
    expiry_date = fields.Date('Expiry Date',
        help='Fecha de caducidad de esta versión. Ejemplo: 2027-01-01.')
    state = fields.Selection([
            ('draft', 'Draft'),
            ('valid', 'Valid'),
            ('expired', 'Expired'),
            ('obsolete', 'Obsolete'),
            ], 'State', required=True,
        help='Estado documental de esta versión. '
        'Ejemplo: "Obsolete" para una versión sustituida.')
    notes = fields.Text('Notes',
        help='Observaciones de revisión o contexto de la versión. '
        'Ejemplo: "Renovado tras auditoría 2026".')
    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments',
        help='Adjuntos que justifican esta versión, como PDF del registro o '
        'correo de renovación.')
    expired = fields.Function(fields.Boolean('Expired',
            help='Indica si esta versión ya ha caducado.'),
        'on_change_with_expired')
    request_update = fields.Function(fields.Boolean('Request Update',
            help='Indica si esta versión entra en el plazo de revisión '
            'definido en el registro principal.'),
        'on_change_with_request_update')

    @staticmethod
    def default_state():
        return 'draft'

    @fields.depends('expiry_date')
    def on_change_with_expired(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        return bool(self.expiry_date and self.expiry_date < today)

    @fields.depends('registration', 'expiry_date',
        '_parent_registration.expiry_notice_days')
    def on_change_with_request_update(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        notice_days = 0
        if self.registration:
            notice_days = self.registration.expiry_notice_days or 0
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
        if (self.start_date and self.expiry_date
                and self.expiry_date < self.start_date):
            raise UserError(gettext(
                'supplier_compliance.msg_food_health_registration_invalid_dates',
                registration=self.rec_name))

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
        registrations = []
        for version in versions:
            if version.registration and version.registration not in registrations:
                registrations.append(version.registration)
        super().delete(versions)
        cls._refresh_registrations(registrations)

    @classmethod
    def _sync_current(cls, versions):
        registrations = []
        to_write = []
        for version in versions:
            if version.registration and version.registration not in registrations:
                registrations.append(version.registration)
            if not version.current:
                continue
            siblings = cls.search([
                    ('registration', '=', version.registration.id),
                    ('id', '!=', version.id),
                    ('current', '=', True),
                    ])
            if siblings:
                to_write.extend(siblings)
        if to_write:
            super().write(to_write, {'current': False})
            for version in to_write:
                if (version.registration
                        and version.registration not in registrations):
                    registrations.append(version.registration)
        cls._refresh_registrations(registrations)

    @classmethod
    def _refresh_registrations(cls, registrations):
        Registration = Pool().get('supplier.compliance.food.health_registration')
        for registration in registrations:
            current = registration._get_current_version()
            values = {
                'country': None,
                'issuing_authority': None,
                'activity': None,
                'start_date': None,
                'expiry_date': None,
                'state': 'draft',
                }
            if current:
                values.update({
                        'country': current.country,
                        'issuing_authority': current.issuing_authority,
                        'activity': current.activity,
                        'start_date': current.start_date,
                        'expiry_date': current.expiry_date,
                        'state': current.state,
                        })
            Registration.write([registration], values)


class FoodAllergen(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.food.allergen'

    record = fields.Many2One('supplier.compliance.record', 'Record',
        required=True, ondelete='CASCADE',
        help='Registro de homologación al que pertenece esta declaración de '
        'alérgeno.')
    allergen = fields.Many2One('supplier.compliance.food.allergen.type',
        'Allergen', required=True, ondelete='RESTRICT',
        help='Alérgeno declarado por el proveedor. Ejemplo: "Gluten".')
    status = fields.Selection([
            ('contains', 'Contains'),
            ('may_contain', 'May Contain'),
            ('cross_contamination', 'Cross Contamination'),
            ('absent', 'Absent'),
            ('unknown', 'Unknown'),
            ], 'Status', required=True,
        help='Resultado de la declaración del proveedor. '
        'Ejemplo: "May Contain" para trazas.')
    source = fields.Char('Source',
        help='Origen de la información declarada. '
        'Ejemplo: "Ficha técnica rev. 3".')
    declaration_date = fields.Date('Declaration Date',
        help='Fecha de la declaración del alérgeno. Ejemplo: 2026-07-15.')
    notes = fields.Text('Notes',
        help='Detalles adicionales o texto original del proveedor. '
        'Ejemplo: "GL T: SO, SE y L".')

    @staticmethod
    def default_status():
        return 'unknown'


class FoodOrigin(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.food.origin'

    record = fields.Many2One('supplier.compliance.record', 'Record',
        required=True, ondelete='CASCADE',
        help='Registro de homologación al que pertenece este origen.')
    ingredient = fields.Char('Ingredient', required=True,
        help='Ingrediente o componente cuyo origen se controla. '
        'Ejemplo: "Semilla de lino".')
    versions = fields.One2Many('supplier.compliance.food.origin.version',
        'origin', 'Versions',
        help='Histórico de países y condiciones de origen de este ingrediente.')
    current_version = fields.Function(fields.Many2One(
            'supplier.compliance.food.origin.version', 'Current Version',
            help='Versión vigente del origen del ingrediente.'),
        'get_current_version')
    country = fields.Function(fields.Many2One('country.country', 'Country',
            ondelete='RESTRICT',
            help='País de origen vigente. Ejemplo: "España".'),
        'get_country', setter='set_country', searcher='search_country')
    country_ref = fields.Many2One('country.country', 'Country',
        ondelete='RESTRICT',
        help='Valor almacenado del país de origen actual.')
    percentage = fields.Numeric('Percentage', digits=(5, 2),
        help='Porcentaje aproximado del ingrediente procedente de este origen. '
        'Ejemplo: 100.00.')
    start_date = fields.Date('Start Date',
        help='Fecha desde la que aplica este origen. Ejemplo: 2026-01-01.')
    end_date = fields.Date('End Date',
        help='Fecha fin de validez de este origen, si dejó de aplicar. '
        'Ejemplo: 2026-06-30.')
    document_confirmed = fields.Boolean('Document Confirmed',
        help='Marca si el origen está confirmado con documentación del '
        'proveedor. Ejemplo: certificado de origen adjunto.')
    notes = fields.Text('Notes',
        help='Observaciones del origen o texto recibido del proveedor. '
        'Ejemplo: "RUSIA, INDIA y BULGARIA".')

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
        versions = list(self.versions or [])
        current_versions = [v for v in versions if v.current]
        if current_versions:
            return current_versions[0]
        if versions:
            return versions[-1]
        return None

    @staticmethod
    def default_versions():
        return ()

    def get_country(self, name):
        return self.country_ref.id if self.country_ref else None

    @classmethod
    def set_country(cls, origins, name, value):
        cls.write(origins, {
                'country_ref': value,
                })

    @classmethod
    def search_country(cls, name, clause):
        return [('country_ref',) + tuple(clause[1:])]

    @classmethod
    def validate(cls, origins):
        super().validate(origins)
        for origin in origins:
            origin.check_unique()
            origin.check_country()
            origin.check_dates()

    def check_unique(self):
        duplicates = self.search([
                ('record', '=', self.record.id),
                ('ingredient', '=', self.ingredient),
                ('id', '!=', self.id),
                ], limit=1)
        if duplicates:
            raise UserError(gettext(
                'supplier_compliance.msg_food_origin_duplicate',
                origin=self.rec_name))

    def check_country(self):
        if not self.versions:
            return
        if not self.country_ref:
            raise UserError(gettext(
                'supplier_compliance.msg_food_origin_missing_country',
                origin=self.rec_name))

    def check_dates(self):
        if (self.start_date and self.end_date
                and self.end_date < self.start_date):
            raise UserError(gettext(
                'supplier_compliance.msg_food_origin_invalid_dates',
                origin=self.rec_name))

    @classmethod
    @ModelView.button
    def new_version(cls, origins):
        Version = Pool().get('supplier.compliance.food.origin.version')
        for origin in origins:
            current_version = origin._get_current_version()
            if current_version:
                Version.write([current_version], {'current': False})
                Version.copy([current_version], default={
                        'current': True,
                        'start_date': None,
                        'end_date': None,
                        })
            else:
                Version.create([{
                            'origin': origin.id,
                            'current': True,
                            }])


class FoodOriginVersion(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.food.origin.version'

    origin = fields.Many2One('supplier.compliance.food.origin', 'Origin',
        required=True, ondelete='CASCADE',
        help='Origen principal al que pertenece esta versión.')
    current = fields.Boolean('Current',
        help='Marca esta versión como la versión vigente del origen.')
    country = fields.Function(fields.Many2One('country.country', 'Country',
            ondelete='RESTRICT',
            help='País declarado en esta versión del origen.'),
        'get_country', setter='set_country', searcher='search_country')
    country_ref = fields.Many2One('country.country', 'Country',
        ondelete='RESTRICT',
        help='Valor almacenado del país para esta versión.')
    percentage = fields.Numeric('Percentage', digits=(5, 2),
        help='Porcentaje que aplica en esta versión. Ejemplo: 40.00.')
    start_date = fields.Date('Start Date',
        help='Fecha de inicio de esta versión de origen.')
    end_date = fields.Date('End Date',
        help='Fecha de fin de esta versión de origen.')
    document_confirmed = fields.Boolean('Document Confirmed',
        help='Indica si esta versión está confirmada documentalmente.')
    notes = fields.Text('Notes',
        help='Notas o aclaraciones de esta versión. '
        'Ejemplo: "Cambio temporal por escasez".')

    def get_country(self, name):
        return self.country_ref.id if self.country_ref else None

    @classmethod
    def set_country(cls, origins, name, value):
        cls.write(origins, {
                'country_ref': value,
                })

    @classmethod
    def search_country(cls, name, clause):
        return [('country_ref',) + tuple(clause[1:])]

    @classmethod
    def validate(cls, versions):
        super().validate(versions)
        for version in versions:
            version.check_country()
            version.check_dates()

    def check_country(self):
        if not self.country_ref:
            raise UserError(gettext(
                'supplier_compliance.msg_food_origin_missing_country',
                origin=self.rec_name))

    def check_dates(self):
        if (self.start_date and self.end_date
                and self.end_date < self.start_date):
            raise UserError(gettext(
                'supplier_compliance.msg_food_origin_invalid_dates',
                origin=self.rec_name))

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
        origins = []
        for version in versions:
            if version.origin and version.origin not in origins:
                origins.append(version.origin)
        super().delete(versions)
        cls._refresh_origins(origins)

    @classmethod
    def _sync_current(cls, versions):
        origins = []
        to_write = []
        for version in versions:
            if version.origin and version.origin not in origins:
                origins.append(version.origin)
            if not version.current:
                continue
            siblings = cls.search([
                    ('origin', '=', version.origin.id),
                    ('id', '!=', version.id),
                    ('current', '=', True),
                    ])
            if siblings:
                to_write.extend(siblings)
        if to_write:
            super().write(to_write, {'current': False})
            for version in to_write:
                if version.origin and version.origin not in origins:
                    origins.append(version.origin)
        cls._refresh_origins(origins)

    @classmethod
    def _refresh_origins(cls, origins):
        Origin = Pool().get('supplier.compliance.food.origin')
        for origin in origins:
            current = origin._get_current_version()
            values = {
                'country_ref': None,
                'percentage': None,
                'start_date': None,
                'end_date': None,
                'document_confirmed': False,
                'notes': None,
                }
            if current:
                values.update({
                        'country_ref': current.country_ref.id
                        if current.country_ref else None,
                        'percentage': current.percentage,
                        'start_date': current.start_date,
                        'end_date': current.end_date,
                        'document_confirmed': current.document_confirmed,
                        'notes': current.notes,
                        })
            Origin.write([origin], values)


class FoodAnalysis(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.food.analysis'

    record = fields.Many2One('supplier.compliance.record', 'Record',
        required=True, ondelete='CASCADE',
        help='Registro de homologación al que pertenece esta analítica.')
    analysis_type = fields.Char('Analysis Type', required=True,
        help='Tipo de análisis realizado o exigido. '
        'Ejemplo: "Contaminants".')
    versions = fields.One2Many('supplier.compliance.food.analysis.version',
        'analysis', 'Versions',
        help='Histórico de informes y renovaciones de esta analítica.')
    current_version = fields.Function(fields.Many2One(
            'supplier.compliance.food.analysis.version', 'Current Version',
            help='Versión vigente del análisis.'),
        'get_current_version')
    laboratory = fields.Char('Laboratory',
        help='Laboratorio que emite el informe. Ejemplo: "Eurofins".')
    report_number = fields.Char('Report Number',
        help='Número del informe analítico. Ejemplo: "LAB-2026-00125".')
    sample_date = fields.Date('Sample Date',
        help='Fecha de toma de muestra. Ejemplo: 2026-07-10.')
    report_date = fields.Date('Report Date',
        help='Fecha del informe emitido por el laboratorio. '
        'Ejemplo: 2026-07-15.')
    result = fields.Char('Result',
        help='Resumen del resultado o valor principal. '
        'Ejemplo: "Conforme" o "< 0.01 mg/kg".')
    conform = fields.Boolean('Conform',
        help='Marca si el resultado cumple el criterio definido.')
    next_analysis_date = fields.Date('Next Analysis Date',
        help='Fecha prevista para solicitar una nueva analítica. '
        'Ejemplo: 2027-07-15.')
    review_notice_days = fields.Integer('Review Notice Days',
        help='Días de antelación para avisar que debe pedirse una nueva '
        'analítica. Ejemplo: 30.')
    notes = fields.Text('Notes',
        help='Observaciones de control o peticiones futuras. '
        'Ejemplo: "Pedir analítica 2027 en junio".')
    due = fields.Function(fields.Boolean('Due',
            help='Indica si la fecha prevista de análisis ya ha vencido.'),
        'on_change_with_due')
    request_update = fields.Function(fields.Boolean('Request Update',
            help='Se activa cuando la próxima analítica entra en el plazo de '
            'aviso configurado.'),
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
        versions = list(self.versions or [])
        current_versions = [v for v in versions if v.current]
        if current_versions:
            return current_versions[0]
        if versions:
            return versions[-1]
        return None

    @staticmethod
    def default_versions():
        return ()

    @fields.depends('next_analysis_date')
    def on_change_with_due(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        return bool(self.next_analysis_date and self.next_analysis_date < today)

    @fields.depends('next_analysis_date', 'review_notice_days')
    def on_change_with_request_update(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        notice_days = self.review_notice_days or 0
        if not self.next_analysis_date or not notice_days:
            return False
        if self.next_analysis_date < today:
            return False
        return self.next_analysis_date <= today + timedelta(days=notice_days)

    @classmethod
    def search_request_update(cls, name, clause):
        _, operator, value = clause
        if operator not in ('=', '!='):
            raise NotImplementedError(
                'Operator %s not supported for %s' % (operator, name))
        if operator == '!=':
            value = not value
        Version = Pool().get('supplier.compliance.food.analysis.version')
        ids = list({
                version.analysis.id
                for version in Version.search([('current', '=', True)])
                if version.on_change_with_request_update()
                })
        domain = [('id', 'in', ids or [-1])]
        if value:
            return domain
        return [('id', 'not in', ids or [-1])]

    @classmethod
    def validate(cls, analyses):
        super().validate(analyses)
        for analysis in analyses:
            analysis.check_unique()
            analysis.check_dates()

    def check_unique(self):
        duplicates = self.search([
                ('record', '=', self.record.id),
                ('analysis_type', '=', self.analysis_type),
                ('id', '!=', self.id),
                ], limit=1)
        if duplicates:
            raise UserError(gettext(
                'supplier_compliance.msg_food_analysis_duplicate',
                analysis=self.rec_name))

    def check_dates(self):
        if (self.sample_date and self.report_date
                and self.report_date < self.sample_date):
            raise UserError(gettext(
                'supplier_compliance.msg_food_analysis_invalid_dates',
                analysis=self.rec_name))

    @classmethod
    @ModelView.button
    def new_version(cls, analyses):
        Version = Pool().get('supplier.compliance.food.analysis.version')
        for analysis in analyses:
            current_version = analysis._get_current_version()
            if current_version:
                Version.write([current_version], {'current': False})
                Version.copy([current_version], default={
                        'current': True,
                        'sample_date': None,
                        'report_date': None,
                        'next_analysis_date': None,
                        'attachments': None,
                        })
            else:
                Version.create([{
                            'analysis': analysis.id,
                            'current': True,
                            }])


class FoodAnalysisVersion(sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'supplier.compliance.food.analysis.version'

    analysis = fields.Many2One('supplier.compliance.food.analysis', 'Analysis',
        required=True, ondelete='CASCADE',
        help='Analítica principal a la que pertenece esta versión.')
    current = fields.Boolean('Current',
        help='Marca esta versión como la vigente para este tipo de análisis.')
    laboratory = fields.Char('Laboratory',
        help='Laboratorio de esta versión del informe. '
        'Ejemplo: "SGS".')
    report_number = fields.Char('Report Number',
        help='Número del informe en esta versión. '
        'Ejemplo: "SGS-24-9988".')
    sample_date = fields.Date('Sample Date',
        help='Fecha de toma de muestra de esta versión.')
    report_date = fields.Date('Report Date',
        help='Fecha del informe de esta versión.')
    result = fields.Char('Result',
        help='Resultado declarado en esta versión. '
        'Ejemplo: "Conforme".')
    conform = fields.Boolean('Conform',
        help='Marca si esta versión cumple el criterio esperado.')
    next_analysis_date = fields.Date('Next Analysis Date',
        help='Próxima fecha prevista de revisión o repetición del análisis.')
    notes = fields.Text('Notes',
        help='Notas de esta versión del informe.')
    attachments = fields.One2Many('ir.attachment', 'resource', 'Attachments',
        help='Adjuntos de esta versión, como PDF del laboratorio o hojas de '
        'resultado.')
    due = fields.Function(fields.Boolean('Due',
            help='Indica si esta versión ya está fuera de plazo de revisión.'),
        'on_change_with_due')
    request_update = fields.Function(fields.Boolean('Request Update',
            help='Indica si esta versión entra en el plazo de aviso para '
            'pedir un nuevo análisis.'),
        'on_change_with_request_update')

    @fields.depends('next_analysis_date')
    def on_change_with_due(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        return bool(self.next_analysis_date and self.next_analysis_date < today)

    @fields.depends('analysis', 'next_analysis_date',
        '_parent_analysis.review_notice_days')
    def on_change_with_request_update(self, name=None):
        Date = Pool().get('ir.date')
        today = Date.today()
        notice_days = 0
        if self.analysis:
            notice_days = self.analysis.review_notice_days or 0
        if not self.next_analysis_date or not notice_days:
            return False
        if self.next_analysis_date < today:
            return False
        return self.next_analysis_date <= today + timedelta(days=notice_days)

    @classmethod
    def validate(cls, versions):
        super().validate(versions)
        for version in versions:
            version.check_dates()

    def check_dates(self):
        if (self.sample_date and self.report_date
                and self.report_date < self.sample_date):
            raise UserError(gettext(
                'supplier_compliance.msg_food_analysis_invalid_dates',
                analysis=self.rec_name))

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
        analyses = []
        for version in versions:
            if version.analysis and version.analysis not in analyses:
                analyses.append(version.analysis)
        super().delete(versions)
        cls._refresh_analyses(analyses)

    @classmethod
    def _sync_current(cls, versions):
        analyses = []
        to_write = []
        for version in versions:
            if version.analysis and version.analysis not in analyses:
                analyses.append(version.analysis)
            if not version.current:
                continue
            siblings = cls.search([
                    ('analysis', '=', version.analysis.id),
                    ('id', '!=', version.id),
                    ('current', '=', True),
                    ])
            if siblings:
                to_write.extend(siblings)
        if to_write:
            super().write(to_write, {'current': False})
            for version in to_write:
                if version.analysis and version.analysis not in analyses:
                    analyses.append(version.analysis)
        cls._refresh_analyses(analyses)

    @classmethod
    def _refresh_analyses(cls, analyses):
        Analysis = Pool().get('supplier.compliance.food.analysis')
        for analysis in analyses:
            current = analysis._get_current_version()
            values = {
                'laboratory': None,
                'report_number': None,
                'sample_date': None,
                'report_date': None,
                'result': None,
                'conform': False,
                'next_analysis_date': None,
                'notes': None,
                }
            if current:
                values.update({
                        'laboratory': current.laboratory,
                        'report_number': current.report_number,
                        'sample_date': current.sample_date,
                        'report_date': current.report_date,
                        'result': current.result,
                        'conform': current.conform,
                        'next_analysis_date': current.next_analysis_date,
                        'notes': current.notes,
                        })
            Analysis.write([analysis], values)
