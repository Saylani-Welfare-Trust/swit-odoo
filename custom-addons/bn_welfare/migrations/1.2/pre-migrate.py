# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

NEW_MODULE = 'bn_sadqa_e_jariya'

# Models moved to bn_sadqa_e_jariya with all their fields
MODELS = (
    'welfare.institution.fetch.log',
    'welfare.committee.member',
    'welfare.inquiry.report',
    'welfare.madrasa',
    'welfare.masjid',
    'welfare.teacher',
)

# Fields moved to bn_sadqa_e_jariya on models that stay in bn_welfare
FIELDS = (
    ('welfare', 'institution_category'),
    ('welfare', 'subcategory'),
    ('welfare', 'committee_member_ids'),
    ('welfare', 'teacher_ids'),
    ('welfare', 'inquiry_report_ids'),
    ('welfare', 'masjid_id'),
    ('welfare', 'madrasa_id'),
    ('welfare.fields.wizard', 'institution_category'),
    ('welfare.fields.wizard', 'subcategory'),
    ('welfare.fields.wizard', 'committee_members_html'),
)

# Groups keep their users, access rules keep working even before bn_sadqa_e_jariya is installed
XMLIDS = (
    'group_fetch_institution',
    'group_institutional_disbursement',
    'access_welfare_institution_fetch_log',
    'access_welfare_committee_member',
    'access_welfare_inquiry_report',
    'access_welfare_madrasa',
    'access_welfare_masjid',
    'access_welfare_teacher',
)

NOT_TAKEN = f"NOT EXISTS (SELECT 1 FROM ir_model_data o WHERE o.module = '{NEW_MODULE}' AND o.name = d.name)"


def migrate(cr, version):
    """
    Institution disbursement code moved from bn_welfare to bn_sadqa_e_jariya.
    Hand the external ids of the moved models, fields and groups over to
    bn_sadqa_e_jariya first: otherwise updating bn_welfare deletes what it no
    longer defines, dropping welfare.institution_category / subcategory and the
    groups' users. Tables and columns are kept, bn_sadqa_e_jariya picks them up.
    Idempotent — ids already handed over are not matched again.
    """
    if not version:
        return  # fresh install, nothing to migrate

    params = {'new': NEW_MODULE, 'models': MODELS, 'fields': FIELDS, 'xmlids': XMLIDS}

    cr.execute(f"""
        UPDATE ir_model_data d SET module = %(new)s
          FROM ir_model m
         WHERE d.module = 'bn_welfare' AND d.model = 'ir.model' AND d.res_id = m.id
           AND m.model IN %(models)s AND {NOT_TAKEN}
    """, params)
    _logger.info("bn_welfare: %s models handed over to %s", cr.rowcount, NEW_MODULE)

    cr.execute(f"""
        UPDATE ir_model_data d SET module = %(new)s
          FROM ir_model_fields f
         WHERE d.module = 'bn_welfare' AND d.model = 'ir.model.fields' AND d.res_id = f.id
           AND (f.model IN %(models)s OR (f.model, f.name) IN %(fields)s) AND {NOT_TAKEN}
    """, params)
    _logger.info("bn_welfare: %s fields handed over to %s", cr.rowcount, NEW_MODULE)

    cr.execute(f"""
        UPDATE ir_model_data d SET module = %(new)s
          FROM ir_model_fields_selection s
          JOIN ir_model_fields f ON f.id = s.field_id
         WHERE d.module = 'bn_welfare' AND d.model = 'ir.model.fields.selection' AND d.res_id = s.id
           AND (f.model IN %(models)s OR (f.model, f.name) IN %(fields)s) AND {NOT_TAKEN}
    """, params)
    _logger.info("bn_welfare: %s selection values handed over to %s", cr.rowcount, NEW_MODULE)

    cr.execute(f"""
        UPDATE ir_model_data d SET module = %(new)s
         WHERE d.module = 'bn_welfare' AND d.name IN %(xmlids)s AND {NOT_TAKEN}
    """, params)
    _logger.info("bn_welfare: %s groups / access rules handed over to %s", cr.rowcount, NEW_MODULE)
