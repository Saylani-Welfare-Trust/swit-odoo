from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Welfare API: donee checks and applications of Welfare / Medical Equipment
    welfare_url = fields.Char('Welfare URL', tracking=True)
    odoo_auth_key = fields.Char('Odoo Auth Key')
    search_endpoint = fields.Char('Search Endpoint', tracking=True)
    create_application_endpoint = fields.Char('Create Application Endpoint', tracking=True)
    check_donee_endpoint = fields.Char('Check Donee Endpoint', tracking=True)
    create_donee_endpoint = fields.Char('Create Donee Endpoint', tracking=True)
    mark_application_endpoint = fields.Char('Mark Application Endpoint', tracking=True)
    # donee found by CNIC / mobile: link the portal donee to its Odoo partner
    update_donee_mapping_endpoint = fields.Char('Update Donee Mapping Endpoint', tracking=True)
