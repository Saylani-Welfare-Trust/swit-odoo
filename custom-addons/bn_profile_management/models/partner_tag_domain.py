# -*- coding: utf-8 -*-
from odoo import api, fields, models

# Contact tags of bn_profile_management, by short name
TAGS = {
    'vendor': 'bn_profile_management.vendor_partner_category',
    'donor': 'bn_profile_management.donor_partner_category',
    'donee': 'bn_profile_management.donee_partner_category',
    'individual': 'bn_profile_management.individual_partner_category',
    'institute': 'bn_profile_management.coorporate_institute_partner_category',
    'welfare': 'bn_profile_management.welfare_partner_category',
    'microfinance': 'bn_profile_management.microfinance_partner_category',
    'medical': 'bn_profile_management.medical_partner_category',
    'patient': 'bn_profile_management.medical_patient_partner_category',
    'student': 'bn_profile_management.student_partner_category',
    'db_donor': 'bn_profile_management.donation_box_donor_partner_category',
}


def tag_domain(*tags, registered=False, any_of=False):
    """Domain (as a callable for a Many2one ``domain=``) of the contacts with
    ALL the given tags (any of them with ``any_of``), registered ones only with
    ``registered``. By tag id, so a renamed tag keeps working."""
    def domain(model):
        return model.env['res.partner']._tag_domain(*tags, registered=registered, any_of=any_of)
    return domain


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _tag_domain(self, *tags, registered=False, any_of=False):
        ids = []
        for tag in tags:
            category = self.env.ref(TAGS[tag], raise_if_not_found=False)
            ids.append(category.id if category else 0)
        if any_of:
            domain = [('category_id', 'in', ids)]
        else:
            domain = [('category_id', 'in', [tag_id]) for tag_id in ids]
        if registered:
            domain.append(('state', '=', 'register'))
        return domain
