from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

# ...existing code...

# Inherit stock.picking to override validate
class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        res = super().button_validate()
        # After validation, set related material.request to done
        material_requests = self.env['material.request'].search([('picking_id', 'in', self.ids), ('state', '!=', 'done')])
        for req in material_requests:
            req.state = 'done'
        return res
# -*- coding: utf-8 -*-