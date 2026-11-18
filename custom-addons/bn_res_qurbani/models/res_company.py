from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'


    web_no_meat_distribution_location_id = fields.Many2one('stock.location', string="Web No-Meat Distribution Location", tracking=True)