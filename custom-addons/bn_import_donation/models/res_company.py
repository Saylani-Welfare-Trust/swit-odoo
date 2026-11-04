from odoo import models, fields

SECRET_GROUP = 'bn_import_donation.import_donation_admin_group,base.group_system'


class ResCompany(models.Model):
    _inherit = 'res.company'


    url = fields.Char('Donation API URL', tracking=True, help="Base URL of the website donation API, e.g. https://example.org")
    client_id = fields.Char('Donation API Client ID', groups=SECRET_GROUP)
    client_secret = fields.Char('Donation API Client Secret', groups=SECRET_GROUP)
