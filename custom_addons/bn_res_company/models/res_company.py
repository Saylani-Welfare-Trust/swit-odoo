from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'


    dn_name = fields.Char('DN Name', tracking=True)

    dn_image = fields.Binary('DN Image')

    url = fields.Char('URL', tracking=True)
    client_id = fields.Char('Client ID', tracking=True)
    client_secret = fields.Char('Client Secret', tracking=True)