# -*- coding: utf-8 -*-
from odoo import fields, models


class ProfileManagementPage(models.Model):
    """Catalog of the notebook pages available on the Profile Management form.

    Each row's `technical_name` must match the `name=` attribute of a
    <page> element in the master Profile Management form
    (profile_management_view_form / base.view_partner_form). Any module
    that adds a new page to that form should also add a matching row here
    (a simple data record) so admins can pick it per tag - the page's
    *content* is still owned and filled in by whichever module inherits
    the form, this catalog only lets admins choose who sees it.
    """
    _name = 'profile.management.page'
    _description = 'Profile Management Page'
    _order = 'sequence, id'

    name = fields.Char('Label', required=True, translate=True)
    technical_name = fields.Char(
        'Technical Name', required=True,
        help="Must exactly match the name= attribute of the matching <page> "
             "element in the Profile Management form.")
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)

    _sql_constraints = [
        ('technical_name_uniq', 'unique(technical_name)',
         'A page with this technical name already exists.'),
    ]
