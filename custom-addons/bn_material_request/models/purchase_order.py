from odoo import models, fields


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    material_request_id = fields.Many2one(
        related='requisition_id.material_request_id',
        string='Source Material Request',
        store=True,
        readonly=True,
        help='Material Request that originally triggered this RFQ, via its Purchase Requisition.'
    )