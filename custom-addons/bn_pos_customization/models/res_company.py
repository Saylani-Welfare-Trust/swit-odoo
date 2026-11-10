from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    # logo printed on the donation receipts (DN)
    dn_name = fields.Char('DN Name', tracking=True)
    dn_image = fields.Binary('DN Image')
