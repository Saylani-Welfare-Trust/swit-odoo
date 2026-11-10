from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """The "Medical" donee tag becomes "Medical Equipment"; "Medical" now tags POS patients.

    The tag is a noupdate record, so the new name in the data file only reaches new databases.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    tag = env.ref('bn_profile_management.medical_partner_category', raise_if_not_found=False)
    if not tag:
        return

    tag.name = 'Medical Equipment'

    # Stored fields computed from the tag names, but depending on category_id only
    Partner = env['res.partner']
    partners = Partner.with_context(active_test=False).search([('category_id', 'in', tag.ids)])
    for field_name in ('categories', 'donee_required_fields'):
        if field_name in Partner._fields:
            env.add_to_compute(Partner._fields[field_name], partners)
    env.flush_all()
