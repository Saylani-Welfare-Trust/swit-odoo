from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # Copied on purpose, so that a backorder keeps the request of its transfer.
    material_request_id = fields.Many2one(
        'material.request', string='Material Request', readonly=True, index=True,
        help='Material Request this internal transfer was created for.')
    requesting_department_id = fields.Many2one(
        related='material_request_id.department_id', string='Requesting Department', store=True)

    @api.model
    def _backfill_material_request(self):
        """Link the transfers that were created before material_request_id existed."""
        # sudo: the Material Request record rule hides requests the user didn't create.
        requests = self.env['material.request'].sudo().search([
            '|', ('picking_id', '!=', False), ('shortage_picking_id', '!=', False),
        ])
        for request in requests:
            pickings = (request.picking_id | request.shortage_picking_id).filtered(
                lambda picking: not picking.material_request_id)
            pickings.material_request_id = request

    def button_validate(self):
        res = super().button_validate()
        self._update_material_request_on_validation()
        return res

    def _update_material_request_on_validation(self):
        """After a delivery is validated, mark the linked Material Request
        as done once all its related pickings (main + shortage) are done."""
        # sudo: the warehouse user validating the picking is usually not the
        # requester, so the Material Request record rule would hide the request.
        MaterialRequest = self.env['material.request'].sudo()

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
