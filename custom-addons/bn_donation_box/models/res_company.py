from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'


    donation_box_product = fields.Char('Donation Box', tracking=True)