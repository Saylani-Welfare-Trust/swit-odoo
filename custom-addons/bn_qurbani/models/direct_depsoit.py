from odoo import models, fields

class DirectDeposit(models.Model):
    _inherit = 'direct.deposit'


    qurbani_order_id = fields.Many2one('qurbani.order', string="Qurbani Order")