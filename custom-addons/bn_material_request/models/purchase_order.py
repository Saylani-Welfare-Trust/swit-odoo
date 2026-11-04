from odoo import models, fields, api


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    material_request_id = fields.Many2one(
        related='requisition_id.material_request_id',
        string='Source Material Request',
        store=True,
        readonly=True,
        help='Material Request that originally triggered this RFQ, via its Purchase Requisition.'
    )

    # Tag back to EVERY Purchase Request that contributed a line when this RFQ
    # was created as a consolidated RFQ by the Vendor Selection Wizard (one PR
    # line can come from a different Purchase Request than requisition_id,
    # once lines from several PRs for the same product are merged together).
    requisition_ids = fields.Many2many(
        'purchase.requisition', 'purchase_order_requisition_rel', 'order_id', 'requisition_id',
        string='Source Purchase Requests', copy=False,
        help='Every Purchase Request whose line(s) were consolidated into this RFQ '
             'by the Vendor Selection Wizard.')
    requisition_tag_count = fields.Integer(
        string='Source Purchase Requests', compute='_compute_requisition_tag_count')

    @api.depends('requisition_ids')
    def _compute_requisition_tag_count(self):
        for order in self:
            order.requisition_tag_count = len(order.requisition_ids)

    def action_view_tagged_requisitions(self):
        """View every Purchase Request tagged on this consolidated RFQ"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': ('Source Purchase Requests of %s') % self.name,
            'res_model': 'purchase.requisition',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.requisition_ids.ids)],
            'context': {'create': False},
            'target': 'current',
        }


class PurchaseOrderLine(models.Model):
    _name = 'purchase.order.line'
    _inherit = ['purchase.order.line', 'line.change.log.mixin']
    _line_log_parent = 'order_id'
    _line_log_fields = ['product_id', 'name', 'product_qty', 'product_uom', 'price_unit', 'discount', 'taxes_id']

    def _line_log_ignored(self, field_name):
        # Odoo itself already logs a quantity change on a confirmed Purchase Order.
        return field_name == 'product_qty' and self.order_id.state == 'purchase'
