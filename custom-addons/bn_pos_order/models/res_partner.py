from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    
    pos_order_line_ids = fields.One2many('pos.order', 'partner_id', string="POS Orders")