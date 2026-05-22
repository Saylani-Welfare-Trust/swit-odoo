from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'


    web_no_meat_distribution_location = fields.Char('Web No-Meat Distribution Location', tracking=True)