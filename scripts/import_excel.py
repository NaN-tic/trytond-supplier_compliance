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
    matches = Party.find([('name', '=', name)], limit=1)
    if matches:
        return matches[0]
    party = Party(name=name)
    party.save()
    return party


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
        defaults={'name': label, 'product_required': False})


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
    record.state = 'obsolete' if state_text else 'active'


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
    record.save()
    return record


def add_requirement(record, header, value):
    clean_value = normalize(value)
    if not clean_value:
        return
    requirement_type = get_requirement_type(header)
    requirement = record.requirements.new()
    requirement.requirement_type = requirement_type
    requirement.status = 'valid'
    requirement.value = clean_value
    parsed_date = excel_date(value)
    if parsed_date:
        requirement.document_date = parsed_date


def add_certificate(record, cert_name, cert_date):
    cert_name = clean_scheme_name(cert_name)
    if not cert_name:
        return
    certificate = record.certificates.new()
    certificate.scheme = get_scheme(cert_name)
    parsed_date = excel_date(cert_date)
    if parsed_date:
        certificate.issue_date = parsed_date


def import_table(company, sheet_name, rows):
    _, items = extract_table(rows)
    for row in items:
        record = upsert_record(company, row, sheet_name)
        if not record:
            continue
        cert_name = row.get('NOMBRE', row.get('NOMBRE ', ''))
        cert_date = row.get('FECHA', '')
        if not record.certificates:
            add_certificate(record, cert_name, cert_date)
        if not record.requirements:
            for header, value in row.items():
                if header in SKIP_HEADERS:
                    continue
                add_requirement(record, header, value)
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
        record.state = 'active'
        extra = [v for v in values[2:] if v]
        notes = extra + ['Source sheet: Servicios']
        record.notes = '\n'.join(notes)
        record.save()


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: import_excel.py <xlsx_path>')
    set_trytond()
    company = get_company()
    workbook = parse_xlsx(sys.argv[1])
    for sheet_name in ('MP', 'Env. Embalajes', 'MAT. AUX.'):
        import_table(company, sheet_name, workbook[sheet_name])
    import_services(company, workbook['Servicios'])


if __name__ == '__main__':
    main()
