from odoo import models, fields


class MicrofinanceGuarantor(models.Model):
    _inherit = 'microfinance.guarantor'


    welfare_id = fields.Many2one('welfare', string="Welfare")