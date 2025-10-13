from odoo import models, fields


class POSConfig(models.Model):
    _inherit = 'pos.config'


    user_ids = fields.Many2many('res.users', string="User")