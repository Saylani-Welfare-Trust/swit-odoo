from odoo import models, fields


class QurbaniOrder(models.Model):
    _inherit = 'qurbani.order'


    description = fields.Html('Description')