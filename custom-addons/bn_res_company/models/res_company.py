from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'


    dn_name = fields.Char('DN Name', tracking=True)

    dn_image = fields.Binary('DN Image')

    # Online Donation
    url = fields.Char('URL', tracking=True)
    client_id = fields.Char('Client ID', tracking=True)
    client_secret = fields.Char('Client Secret', tracking=True)

    # Welfare
    # welfare_url = fields.Char('Welfare URL', tracking=True)
    # odoo_auth_key = fields.Char('Odoo Auth Key', tracking=True)
    
    # search_endpoint = fields.Char('Search Endpoint', tracking=True)
    # check_donee_endpoint = fields.Char('Check Donee Endpoint', tracking=True)
    # create_donee_endpoint = fields.Char('Create Donee Endpoint', tracking=True)
    # mark_application_endpoint = fields.Char('Mark Application Endpoint', tracking=True)