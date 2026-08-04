#!/usr/bin/env python3
# This file is part of the supplier_compliance module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from __future__ import annotations

import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path
import re
import unicodedata

from proteus import Model
from proteus.config import set_trytond


NS = {
    'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'rel': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'pkgrel': 'http://schemas.openxmlformats.org/package/2006/relationships',
}

SCOPE_LABELS = {
    'MP': 'Raw Material',
    'ENVASE': 'Packaging',
    'EMBALAJE': 'Packaging',
    'MAT. AUXILIAR': 'Auxiliary Material',
    'SERVICIO': 'Service',
}

SKIP_HEADERS = {
    'CODIGO', 'PROVEEDOR', 'ARTICULO', 'TIPO',
    'OBSERVACIONES', 'OBSERVACIONES ',
    'CONTACTO ALERTAS/CRISIS',
    'CORREO ELECTRONICO DE CONTACTO',
    'CORREO ELECTRONICO',
    'NOMBRE ', 'NOMBRE', 'FECHA',
    'BAJA', 'ESTADO/FECHA',
    '',
}

FOOD_HEADERS = {
    'RGS',
    'C. AUSENCIA OGM',
    'C. AUSENCIA IRADIACIÓN',
    'DECLARACIÓN ALERGENOS',
    'PRESENCIA ALERGENOS',
    'ANALITICA CONTAMINANTES',
    'ORIGEN INGREDIENTES',
}

PACKAGING_HEADERS = {
    'DECLARACIÓN / CERTIFICADO DE CONFORMIDAD',
    'CERTIFICADO DE CONFORMIDAD',
    'CERTIFICADO ENVASES APTOS',
    'ESTUDIOS MIGRACIÓN',
    'ESTUDIOS DE MIGRACIÓN',
}

ALLERGEN_CODES = {
    'GL': 'Gluten',
    'CR': 'Crustaceans',
    'H': 'Egg',
    'HU': 'Egg',
    'OU': 'Egg',
    'P': 'Fish',
    'CA': 'Peanuts',
    'SO': 'Soy',
    'L': 'Milk',
    'FC': 'Nuts',
    'AP': 'Celery',
    'MO': 'Mustard',
    'MOST': 'Mustard',
    'SE': 'Sesame',
    'SU': 'Sulphites',
    'AL': 'Lupin',
    'ALT': 'Lupin',
    'ML': 'Molluscs',
}

COUNTRY_CODES = {
    'ESPANA': 'ES',
    'ESPAÑA': 'ES',
    'EGIPTO': 'EG',
    'EGYPTO': 'EG',
    'RUSIA': 'RU',
    'RUSSIA': 'RU',
    'INDIA': 'IN',
    'BULGARIA': 'BG',
    'FRANCIA': 'FR',
    'FRANCE': 'FR',
    'BELGICA': 'BE',
    'BELGICA ': 'BE',
    'BELGIUM': 'BE',
}


def excel_date(value):
    if value in (None, ''):
        return None
    if isinstance(value, date):
        return value
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return date(1899, 12, 30) + timedelta(days=int(value))


def normalize(text):
    return ' '.join((text or '').replace('\n', ' ').split()).strip()


def normalize_key(text):
    text = unicodedata.normalize('NFKD', normalize(text))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return text.upper()


def compact_key(text):
    return re.sub(r'[^A-Z0-9]+', '', normalize_key(text))


def party_name_key(text):
    text = normalize_key(text)
    text = re.sub(r'\b(SA|S A|SL|S L|SCP|S C P|SLU|S L U|SAU|S A U)\b', '',
        text)
    return re.sub(r'[^A-Z0-9]+', '', text)


def split_lines(text):
    return [line.strip() for line in (text or '').splitlines() if line.strip()]


def extract_emails(text):
    return re.findall(r'[\w.+-]+@[\w.-]+\.\w+', text or '')


def extract_phones(text):
    phones = []
    for raw in re.findall(r'[\d+][\d\s/.-]{5,}', text or ''):
        cleaned = ' '.join(raw.replace('/', ' ').split()).strip(' .-')
        if cleaned:
            phones.append(cleaned)
    return phones


def find_date_in_text(value):
    if value in (None, ''):
        return None
    parsed = excel_date(value)
    if parsed:
        return parsed
    text = normalize(value)
    match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', text)
    if not match:
        return None
    day, month, year = map(int, match.groups())
    if year < 100:
        year += 2000
    try:
        return date(year, month, day)
    except ValueError:
        return None


def split_tokens(value):
    text = normalize_key(value)
    text = re.sub(r'([A-Z]{2,4})Y([A-Z]{2,4})', r'\1,\2', text)
    text = re.sub(r'([A-Z]{2,4})Y\s+([A-Z]{2,4})', r'\1,\2', text)
    text = text.replace(' Y ', ',')
    text = text.replace('.', ',')
    text = text.replace(';', ',')
    text = text.replace('(', ',').replace(')', ',')
    return [token.strip() for token in text.split(',') if token.strip()]


def get_allergen_type(code):
    name = ALLERGEN_CODES.get(code, code.title())
    return get_or_create(
        'supplier.compliance.food.allergen.type', 'code', code,
        defaults={'name': name})


def get_country(value):
    Country = Model.get('country.country')
    key = normalize_key(value)
    if not key:
        return None
    code = COUNTRY_CODES.get(key, key[:2] if len(key) == 2 else None)
    if code:
        matches = Country.find([('code', '=', code)], limit=1)
        if matches:
            return matches[0]
    for field in ('name',):
        matches = Country.find([(field, '=', normalize(value))], limit=1)
        if matches:
            return matches[0]
    return None


def get_packaging_family(company, party, scope_code, family_hint=None):
    family_hint = normalize(family_hint)
    if family_hint:
        family_name = '%s - %s' % (party.name, family_hint)
    else:
        family_name = '%s %s' % (party.name, SCOPE_LABELS.get(scope_code, scope_code))
    Family = Model.get('supplier.compliance.packaging.family')
    matches = Family.find([
            ('company', '=', company.id),
            ('party', '=', party.id),
            ('name', '=', family_name),
            ], limit=1)
    if matches:
        return matches[0]
    family = Family()
    family.company = company
    family.party = party
    family.name = family_name
    family.code = '%s-%s' % (party.id, scope_code[:10])
    family.save()
    return family


def append_record_note(record, text):
    text = normalize(text)
    if not text:
        return
    existing = split_lines(record.notes)
    if text not in existing:
        existing.append(text)
        record.notes = '\n'.join(existing)


def clean_scheme_name(value):
    value = normalize(value)
    if not value:
        return ''
    if value.upper().startswith('SI '):
        value = value[3:]
    return value.strip()


def parse_xlsx(path):
    path = Path(path)
    with zipfile.ZipFile(path) as zf:
        shared = []
        if 'xl/sharedStrings.xml' in zf.namelist():
            root = ET.fromstring(zf.read('xl/sharedStrings.xml'))
            for si in root.findall('main:si', NS):
                shared.append(''.join(t.text or '' for t in si.iterfind('.//main:t', NS)))

        wb = ET.fromstring(zf.read('xl/workbook.xml'))
        rels = ET.fromstring(zf.read('xl/_rels/workbook.xml.rels'))
        rel_map = {
            rel.attrib['Id']: rel.attrib['Target']
            for rel in rels.findall('pkgrel:Relationship', NS)
        }

        result = {}
        for sheet in wb.findall('main:sheets/main:sheet', NS):
            title = sheet.attrib['name']
            rid = sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
            target = 'xl/' + rel_map[rid]
            ws = ET.fromstring(zf.read(target))
            rows = []
            for row in ws.findall('main:sheetData/main:row', NS):
                values = {}
                for cell in row.findall('main:c', NS):
                    ref = cell.attrib.get('r', '')
                    col = ''.join(ch for ch in ref if ch.isalpha())
                    ctype = cell.attrib.get('t')
                    value_node = cell.find('main:v', NS)
                    if ctype == 's' and value_node is not None:
                        value = shared[int(value_node.text)]
                    elif ctype == 'inlineStr':
                        value = ''.join(t.text or '' for t in cell.iterfind('.//main:t', NS))
                    elif value_node is not None:
                        value = value_node.text
                    else:
                        value = ''
                    values[col] = value
                rows.append(values)
            result[title] = rows
        return result


def row_as_list(row):
    if not row:
        return []
    cols = sorted(row.keys(), key=lambda c: (len(c), c))
    return [row.get(col, '') for col in cols]


def extract_table(rows):
    header_row = None
    for row in rows:
        values = row_as_list(row)
        if any(normalize(v) == 'CODIGO' for v in values):
            header_row = row
            break
    if not header_row:
        return [], []
    columns = sorted(header_row.keys(), key=lambda c: (len(c), c))
    headers = [normalize(header_row.get(col, '')) for col in columns]
    start = rows.index(header_row) + 1
    items = []
    for row in rows[start:]:
        item = {header: row.get(col, '') for header, col in zip(headers, columns)}
        if not any(normalize(v) for v in item.values()):
            continue
        items.append(item)
    return headers, items


def get_or_create(model_name, key_field, value, defaults=None):
    defaults = defaults or {}
    ModelCls = Model.get(model_name)
    matches = ModelCls.find([(key_field, '=', value)], limit=1)
    if matches:
        return matches[0]
    record = ModelCls()
    setattr(record, key_field, value)
    for field, field_value in defaults.items():
        setattr(record, field, field_value)
    record.save()
    return record


def get_company():
    Company = Model.get('company.company')
    company, = Company.find([], limit=1)
    return company


def get_party(name):
    Party = Model.get('party.party')
    ProductSupplier = Model.get('purchase.product_supplier')
    normalized = normalize(name)
    candidates = []
    for domain in [
            [('name', '=', normalized)],
            [('name', 'ilike', normalized)],
            [('name', 'ilike', normalized + '%')],
            ]:
        for party in Party.find(domain):
            if party.id not in {p.id for p in candidates}:
                candidates.append(party)
    key = party_name_key(normalized)
    if key:
        for party in Party.find([]):
            if party_name_key(party.name) == key:
                if party.id not in {p.id for p in candidates}:
                    candidates.append(party)
    if candidates:
        supplier_parties = [
            party for party in candidates
            if ProductSupplier.find([('party', '=', party.id)], limit=1)
            ]
        if len(supplier_parties) == 1:
            return supplier_parties[0]
        if len(candidates) == 1:
            return candidates[0]
    party = Party(name=normalized)
    party.save()
    return party


def get_product_supplier(company, party, code=None, article=None):
    ProductSupplier = Model.get('purchase.product_supplier')
    product_suppliers = ProductSupplier.find([
            ('party', '=', party.id),
            ('company', '=', company.id),
            ])
    normalized_article = normalize(article)
    compact_article = compact_key(article)
    if code:
        code_matches = [ps for ps in product_suppliers
            if normalize(ps.code) == code]
        if len(code_matches) == 1:
            return code_matches[0]
    if normalized_article:
        article_matches = []
        for product_supplier in product_suppliers:
            candidate_names = [
                normalize(product_supplier.name),
                normalize(product_supplier.template.name),
                normalize(product_supplier.rec_name),
                ]
            if product_supplier.product:
                candidate_names.append(normalize(product_supplier.product.name))
            if normalized_article in candidate_names:
                article_matches.append(product_supplier)
        if len(article_matches) == 1:
            return article_matches[0]
    if compact_article:
        compact_matches = []
        for product_supplier in product_suppliers:
            candidate_values = [
                product_supplier.name,
                product_supplier.template.name,
                product_supplier.template.code,
                ]
            if product_supplier.product:
                candidate_values.extend([
                        product_supplier.product.name,
                        product_supplier.product.code,
                        ])
            if compact_article in {compact_key(v) for v in candidate_values}:
                compact_matches.append(product_supplier)
        if len(compact_matches) == 1:
            return compact_matches[0]
    return None


def get_contact_mechanism(party, type_, value, name=None):
    ContactMechanism = Model.get('party.contact_mechanism')
    normalized = normalize(value)
    compare_value = normalized.lower() if type_ == 'email' else normalized
    for mechanism in party.contact_mechanisms:
        mechanism_value = normalize(mechanism.value)
        if mechanism.type == 'email':
            mechanism_value = mechanism_value.lower()
        if mechanism.type == type_ and mechanism_value == compare_value:
            if name and not mechanism.name:
                mechanism.name = name
                mechanism.save()
            return mechanism
    mechanism = ContactMechanism()
    mechanism.party = party
    mechanism.type = type_
    mechanism.value = normalized
    if name:
        mechanism.name = name
    mechanism.save()
    return mechanism


def assign_alert_mechanisms(record, contact_text, email_text):
    contact_lines = split_lines(contact_text)
    email_lines = split_lines(email_text)

    contact_name = None
    for line in contact_lines:
        if not extract_emails(line) and not extract_phones(line):
            contact_name = normalize(line)
            break

    email_name = contact_name
    for line in email_lines:
        if not extract_emails(line) and not extract_phones(line):
            email_name = normalize(line)
            break

    phones = extract_phones(contact_text)
    if phones:
        mechanism = get_contact_mechanism(
            record.party, 'phone', phones[0], name=contact_name)
        mechanism.supplier_compliance_alert = True
        mechanism.supplier_compliance_crisis = True
        mechanism.save()

    emails = extract_emails(email_text or contact_text)
    if emails:
        mechanism = get_contact_mechanism(
            record.party, 'email', emails[0], name=email_name)
        mechanism.supplier_compliance_alert = True
        mechanism.supplier_compliance_crisis = True
        mechanism.save()


def get_scope(scope_code):
    label = SCOPE_LABELS.get(scope_code, scope_code.title())
    return get_or_create(
        'supplier.compliance.scope.type', 'code', scope_code,
        defaults={'name': label, 'product_required': scope_code == 'MP'})


def get_requirement_type(header):
    return get_or_create(
        'supplier.compliance.requirement.type', 'name', header,
        defaults={'code': header[:20], 'kind': 'document'})


def get_scheme(name):
    return get_or_create(
        'supplier.compliance.scheme', 'name', name,
        defaults={'code': name[:20]})


def set_record_state(record, row):
    state_text = normalize(row.get('BAJA') or row.get('ESTADO/FECHA'))
    record.state = 'withdrawn' if state_text else 'approved'
    if state_text and not record.withdrawal_date:
        record.withdrawal_date = date.today()


def upsert_record(company, row, source_sheet):
    supplier_name = normalize(row.get('PROVEEDOR'))
    article = normalize(row.get('ARTICULO'))
    if not supplier_name or not article:
        return None

    scope_code = normalize(row.get('TIPO')) or source_sheet
    party = get_party(supplier_name)
    code = normalize(row.get('CODIGO'))
    Record = Model.get('supplier.compliance.record')
    domain = [('party', '=', party.id), ('name', '=', article)]
    if code:
        domain = [('party', '=', party.id), ('code', '=', code)]
    matches = Record.find(domain, limit=1)
    record = matches[0] if matches else Record()
    record.company = company
    record.party = party
    record.scope_type = get_scope(scope_code)
    record.code = code
    record.name = article
    record.external_article_name = article
    product_supplier = get_product_supplier(
        company, party, code=code, article=article)
    if product_supplier:
        record.product_supplier = product_supplier
        record.product_template = product_supplier.template
    assign_alert_mechanisms(
        record,
        row.get('CONTACTO ALERTAS/CRISIS'),
        row.get('CORREO ELECTRONICO DE CONTACTO') or row.get('CORREO ELECTRONICO'))

    notes = []
    for key in ('OBSERVACIONES', 'OBSERVACIONES '):
        text = normalize(row.get(key))
        if text:
            notes.append(text)
    notes.append(f'Source sheet: {source_sheet}')
    record.notes = '\n'.join(notes)
    set_record_state(record, row)
    if scope_code in {'ENVASE', 'EMBALAJE'}:
        family_hint = (
            normalize(row.get('OBSERVACIONES'))
            or normalize(row.get('OBSERVACIONES '))
            or normalize(row.get('ARTICULO')))
        record.packaging_family = get_packaging_family(
            company, party, scope_code, family_hint=family_hint)
    record.save()
    return record


def clear_one2many(lines):
    for line in list(lines):
        lines.remove(line)


def parse_registrations(value):
    text = normalize(value)
    if not text:
        return []
    return list(dict.fromkeys(re.findall(r'[A-Z]?\d[\d./-]*[A-Z/]?', text)))


def add_food_health_registrations(record, value):
    Registration = Model.get('supplier.compliance.food.health_registration')
    for registration_number in parse_registrations(value):
        matches = Registration.find([
                ('record', '=', record.id),
                ('registration_number', '=', registration_number),
                ], limit=1)
        registration = matches[0] if matches else Registration()
        if not matches:
            registration.record = record
            registration.registration_number = registration_number
        version = registration.versions.new()
        version.current = True
        version.state = 'valid'
        registration.save()


def add_food_requirement(record, header, value):
    clean_value = normalize(value)
    if not clean_value:
        return
    requirement_type = get_requirement_type(header)
    Requirement = Model.get('supplier.compliance.requirement')
    matches = Requirement.find([
            ('record', '=', record.id),
            ('requirement_type', '=', requirement_type.id),
            ], limit=1)
    requirement = matches[0] if matches else Requirement()
    if not matches:
        requirement.record = record
        requirement.requirement_type = requirement_type
        requirement.save()
    version = requirement.versions.new()
    version.current = True
    version.status = 'valid'
    version.value = clean_value
    version.document_date = find_date_in_text(value)
    requirement.save()


def add_food_allergens(record, value):
    text = normalize_key(value)
    if not text or text in {'NO', 'N/A'}:
        return
    if text == 'SI':
        append_record_note(record, 'Food allergen declaration indicates presence without detail.')
        return
    trace_text = ''
    if 'T:' in text:
        contains_text, trace_text = text.split('T:', 1)
    elif ' T ' in text:
        contains_text, trace_text = text.split(' T ', 1)
    else:
        contains_text = text
    for code in split_tokens(contains_text):
        if code in {'SI', 'NO'}:
            continue
        allergen = record.food_allergens.new()
        allergen.allergen = get_allergen_type(code)
        allergen.status = 'contains'
        allergen.source = 'Excel import'
    for code in split_tokens(trace_text):
        allergen = record.food_allergens.new()
        allergen.allergen = get_allergen_type(code)
        allergen.status = 'may_contain'
        allergen.source = 'Excel import'


def add_food_origins(record, value):
    text = normalize(value)
    if not text:
        return
    normalized = normalize_key(text)
    if normalized.startswith('NO'):
        return
    if normalized.startswith('SI'):
        text = normalize(text[2:])
    text = text.strip('() ')
    Origin = Model.get('supplier.compliance.food.origin')
    for country in split_tokens(text):
        if country == 'SI':
            continue
        country_record = get_country(country)
        if not country_record:
            append_record_note(record, 'Unresolved country: %s' % country)
            continue
        matches = Origin.find([
                ('record', '=', record.id),
                ('ingredient', '=', 'General'),
                ], limit=1)
        origin = matches[0] if matches else Origin()
        if not matches:
            origin.record = record
            origin.ingredient = 'General'
        version = origin.versions.new()
        version.current = True
        version.country = country_record
        origin.save()


def add_food_analysis(record, value):
    text = normalize(value)
    if not text:
        return
    Analysis = Model.get('supplier.compliance.food.analysis')
    matches = Analysis.find([
            ('record', '=', record.id),
            ('analysis_type', '=', 'Contaminants'),
            ], limit=1)
    analysis = matches[0] if matches else Analysis()
    if not matches:
        analysis.record = record
        analysis.analysis_type = 'Contaminants'
    version = analysis.versions.new()
    version.current = True
    version.result = text
    version.report_date = find_date_in_text(value)
    version.conform = normalize_key(text).startswith('SI')
    analysis.save()


def detect_packaging_kind(article):
    text = normalize_key(article)
    if 'BOSSA' in text or 'BOLSA' in text:
        return 'bag'
    if 'CAJA' in text or 'CAPSA' in text:
        return 'box'
    if 'FILM' in text:
        return 'film'
    if 'BANDEJA' in text:
        return 'tray'
    return 'other'


def detect_packaging_material(article):
    text = normalize(article)
    for material in ('kraft', 'PE', 'PP', 'PET', 'paper', 'carton'):
        if material.lower() in text.lower():
            return material.upper() if material.isupper() else material.title()
    return ''


def detect_packaging_dimensions(article):
    match = re.search(r'(\d+\s*[xX]\s*\d+(?:\s*\+\s*\d+)?)', article or '')
    if match:
        return normalize(match.group(1))
    return ''


def add_packaging_specification(record, row):
    specification = record.packaging_specifications.new()
    specification.kind = detect_packaging_kind(record.name)
    specification.primary_material = (
        detect_packaging_material(record.name)
        or SCOPE_LABELS.get(normalize(row.get('TIPO')), 'Packaging'))
    specification.food_contact = True
    specification.contact_type = 'direct'
    specification.dimensions = detect_packaging_dimensions(record.name)
    specification.notes = normalize(row.get('OBSERVACIONES'))


def add_packaging_compliance(record, header, value):
    text = normalize(value)
    if not text:
        return
    Compliance = Model.get('supplier.compliance.packaging.compliance')
    matches = Compliance.find([
            ('record', '=', record.id),
            ('reference', '=', header),
            ], limit=1)
    compliance = matches[0] if matches else Compliance()
    if not matches:
        compliance.record = record
        compliance.reference = header
    version = compliance.versions.new()
    version.current = True
    version.issue_date = find_date_in_text(value)
    version.status = 'valid' if normalize_key(text).startswith('SI') else 'pending'
    version.notes = text
    compliance.save()


def add_packaging_migration_test(record, value):
    text = normalize(value)
    if not text:
        return
    MigrationTest = Model.get('supplier.compliance.packaging.migration_test')
    matches = MigrationTest.find([
            ('record', '=', record.id),
            ('migration_type', '=', 'global_migration'),
            ], limit=1)
    test = matches[0] if matches else MigrationTest()
    if not matches:
        test.record = record
        test.migration_type = 'global_migration'
    version = test.versions.new()
    version.current = True
    version.migration_type = 'global_migration'
    version.test_date = find_date_in_text(value)
    version.conform = normalize_key(text).startswith('SI')
    version.notes = text
    test.save()


def add_unlabelled_notes(record, row):
    used_headers = {
        normalize_key(header) for header in row.keys() if normalize(header)
    }
    notes = []
    for header, value in row.items():
        if normalize(header):
            continue
        clean_value = normalize(value)
        if not clean_value:
            continue
        if normalize_key(clean_value) in used_headers:
            continue
        notes.append(clean_value)
    for note in notes:
        append_record_note(record, note)


def load_structured_data(record, row, source_sheet):
    clear_one2many(record.requirements)
    clear_one2many(record.certificates)
    clear_one2many(record.food_health_registrations)
    clear_one2many(record.food_allergens)
    clear_one2many(record.food_origins)
    clear_one2many(record.food_analyses)
    clear_one2many(record.packaging_specifications)
    clear_one2many(record.packaging_compliances)
    clear_one2many(record.packaging_migration_tests)

    is_packaging_sheet = source_sheet == 'Env. Embalajes'

    cert_name = row.get('NOMBRE', row.get('NOMBRE ', ''))
    cert_date = row.get('FECHA', '')
    add_certificate(record, cert_name, cert_date)

    for header, value in row.items():
        if header in SKIP_HEADERS or not normalize(value):
            continue
        if header == 'RGS':
            add_food_health_registrations(record, value)
            continue
        if header in {'C. AUSENCIA OGM', 'C. AUSENCIA IRADIACIÓN',
                'DECLARACIÓN ALERGENOS'}:
            add_food_requirement(record, header, value)
            continue
        if header == 'PRESENCIA ALERGENOS':
            add_food_allergens(record, value)
            continue
        if header == 'ANALITICA CONTAMINANTES':
            add_food_analysis(record, value)
            continue
        if header == 'ORIGEN INGREDIENTES':
            add_food_origins(record, value)
            continue
        if (is_packaging_sheet and header in {
                    'DECLARACIÓN / CERTIFICADO DE CONFORMIDAD',
                    'CERTIFICADO DE CONFORMIDAD',
                    'CERTIFICADO ENVASES APTOS'}):
            add_packaging_compliance(record, header, value)
            continue
        if is_packaging_sheet and header in {
                'ESTUDIOS MIGRACIÓN', 'ESTUDIOS DE MIGRACIÓN'}:
            add_packaging_migration_test(record, value)
            continue
        add_requirement(record, header, value)

    if is_packaging_sheet:
        add_packaging_specification(record, row)
        add_unlabelled_notes(record, row)


def add_requirement(record, header, value):
    clean_value = normalize(value)
    if not clean_value:
        return
    requirement_type = get_requirement_type(header)
    Requirement = Model.get('supplier.compliance.requirement')
    matches = Requirement.find([
            ('record', '=', record.id),
            ('requirement_type', '=', requirement_type.id),
            ], limit=1)
    requirement = matches[0] if matches else Requirement()
    if not matches:
        requirement.record = record
        requirement.requirement_type = requirement_type
        requirement.save()
    version = requirement.versions.new()
    version.current = True
    version.status = 'valid'
    version.value = clean_value
    parsed_date = excel_date(value)
    if parsed_date:
        version.document_date = parsed_date
    requirement.save()


def add_certificate(record, cert_name, cert_date):
    cert_name = clean_scheme_name(cert_name)
    if not cert_name:
        return
    scheme = get_scheme(cert_name)
    Certificate = Model.get('supplier.compliance.certificate')
    matches = Certificate.find([
            ('record', '=', record.id),
            ('scheme', '=', scheme.id),
            ], limit=1)
    certificate = matches[0] if matches else Certificate()
    if not matches:
        certificate.record = record
        certificate.scheme = scheme
        certificate.save()
    version = certificate.versions.new()
    version.current = True
    parsed_date = excel_date(cert_date)
    if parsed_date:
        version.issue_date = parsed_date
    certificate.save()


def import_table(company, sheet_name, rows):
    _, items = extract_table(rows)
    for row in items:
        record = upsert_record(company, row, sheet_name)
        if not record:
            continue
        load_structured_data(record, row, sheet_name)
        record.save()


def import_services(company, rows):
    for row in rows:
        values = [normalize(v) for v in row_as_list(row)]
        if len(values) < 2 or not values[0] or not values[1]:
            continue
        supplier_name = values[0]
        service_name = values[1]
        party = get_party(supplier_name)
        Record = Model.get('supplier.compliance.record')
        matches = Record.find([
                ('party', '=', party.id),
                ('name', '=', service_name),
                ], limit=1)
        record = matches[0] if matches else Record()
        record.company = company
        record.party = party
        record.scope_type = get_scope('SERVICIO')
        record.name = service_name
        record.external_article_name = service_name
        record.state = 'approved'
        extra = [v for v in values[2:] if v]
        notes = extra + ['Source sheet: Servicios']
        record.notes = '\n'.join(notes)
        record.save()


def reset_data():
    for model_name in [
            'supplier.compliance.record',
            'supplier.compliance.packaging.family',
            ]:
        ModelCls = Model.get(model_name)
        records = ModelCls.find([])
        if records:
            ModelCls.delete(records)

    ContactMechanism = Model.get('party.contact_mechanism')
    mechanisms = ContactMechanism.find([
            ['OR',
                ('supplier_compliance_alert', '=', True),
                ('supplier_compliance_crisis', '=', True),
                ],
            ])
    for mechanism in mechanisms:
        mechanism.supplier_compliance_alert = False
        mechanism.supplier_compliance_crisis = False
        mechanism.save()


def main():
    reset = False
    args = sys.argv[1:]
    if '--reset' in args:
        reset = True
        args.remove('--reset')
    if len(args) != 1:
        raise SystemExit('usage: import_excel.py [--reset] <xlsx_path>')
    set_trytond()
    if reset:
        reset_data()
    company = get_company()
    workbook = parse_xlsx(args[0])
    for sheet_name in ('MP', 'Env. Embalajes', 'MAT. AUX.'):
        import_table(company, sheet_name, workbook[sheet_name])
    import_services(company, workbook['Servicios'])


if __name__ == '__main__':
    main()
