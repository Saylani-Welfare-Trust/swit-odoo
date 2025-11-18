from odoo import models, fields


class MicrofinanceFamily(models.Model):
    _inherit = 'microfinance.family'


    welfare_id = fields.Many2one('welfare', string="Welfare")