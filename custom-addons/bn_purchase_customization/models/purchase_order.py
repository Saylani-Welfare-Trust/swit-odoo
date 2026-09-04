from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'


    comparative_count = fields.Integer('Comparative Count', compute="_set_comparative_count")


    def _set_comparative_count(self):
        for rec in self:
            rec.comparative_count = 0

            if rec.requisition_id:
                rec.comparative_count = len(rec.requisition_id.purchase_ids.filtered(lambda p: p.id != rec.id))

    def action_open_comparative_analysis(self):
        purchase_ids = self.requisition_id.purchase_ids.filtered(lambda p: p.id != self.id)

        # raise ValidationError(str(purchase_ids))

        return {
            'type': 'ir.actions.act_window',
            'name': 'Request for Quotations',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', purchase_ids.ids)],
            'context': {
                'create': 0
            }
        }
        
class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    on_hand_qty = fields.Float(
        string='On Hand',
        compute='_compute_on_hand_qty'
    )

    last_purchase_amount = fields.Float(
        string="Last Purchase Amount",
        compute='_compute_last_purchase_amount'
    )


    @api.depends('product_id')
    def _compute_on_hand_qty(self):
        for line in self:
            line.on_hand_qty = line.product_id.qty_available if line.product_id else 0.0

    @api.depends('product_id')
    def _compute_last_purchase_amount(self):
        for line in self:
            line.last_purchase_amount = 0.0

            if not line.product_id:
                continue

            domain = [
                ('state', '=', 'purchase'),
                ('order_line.product_id', '=', line.product_id.id),
            ]

            if line.order_id.id:
                domain.append(('id', '!=', line.order_id.id))

            previous_po = self.env['purchase.order'].search(
                domain,
                order='date_approve desc',
                limit=1
            )

            if previous_po:
                previous_line = previous_po.order_line.filtered(
                    lambda l: l.product_id == line.product_id
                )[:1]
                line.last_purchase_amount = previous_line.price_unit