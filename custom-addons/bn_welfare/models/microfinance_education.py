from odoo import models, fields


class MicrofinanceEducation(models.Model):
    _inherit = 'microfinance.education'


    welfare_id = fields.Many2one('welfare', string="Welfare")