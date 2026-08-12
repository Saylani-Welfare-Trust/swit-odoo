from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        res = super().button_validate()
        self._update_material_request_on_validation()
        return res

    def _update_material_request_on_validation(self):
        """After a delivery is validated, mark the linked Material Request
        as done once all its related pickings (main + shortage) are done."""
        MaterialRequest = self.env['material.request']

        related_mrs = MaterialRequest.search([
            ('state', '=', 'pending'),
            '|',
            ('picking_id', 'in', self.ids),
            ('shortage_picking_id', 'in', self.ids),
        ])

        for mr in related_mrs:
            pickings = (mr.picking_id | mr.shortage_picking_id).filtered(lambda p: p)
            if pickings and all(p.state == 'done' for p in pickings):
                mr.state = 'done'