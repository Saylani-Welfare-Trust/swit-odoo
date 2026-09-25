from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'


    comparative_count = fields.Integer('Comparative Count', compute="_set_comparative_count")

    cxo_approved = fields.Boolean('CXO Approved', copy=False, tracking=True)
    cxo_approved_by = fields.Many2one('res.users', string='CXO Approved By', readonly=True, copy=False)
    cxo_approved_date = fields.Datetime(string='CXO Approved On', readonly=True, copy=False)

    hod_approved = fields.Boolean('HOD Approved', copy=False, tracking=True)
    hod_approved_by = fields.Many2one('res.users', string='HOD Approved By', readonly=True, copy=False)
    hod_approved_date = fields.Datetime(string='HOD Approved On', readonly=True, copy=False)

    def action_cxo_approve_po(self):
        for order in self:
            order.write({
                'cxo_approved': True,
                'cxo_approved_by': self.env.user.id,
                'cxo_approved_date': fields.Datetime.now(),
            })

    def action_hod_approve_po(self):
        for order in self:
            if not order.cxo_approved:
                raise UserError(_('CXO approval is required before HOD approval.'))
            order.write({
                'hod_approved': True,
                'hod_approved_by': self.env.user.id,
                'hod_approved_date': fields.Datetime.now(),
            })


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
        
    @api.model
    def create(self, vals):
        # Don't assign the PO sequence when creating an RFQ
        vals['name'] = '/'
        return super().create(vals)

    def button_confirm(self):
        for order in self:
            if not (order.cxo_approved and order.hod_approved):
                raise UserError(_(
                    'Purchase order %s cannot be confirmed until it has both CXO approval '
                    'and HOD approval.'
                ) % (order.name if order.name != '/' else order.display_name))
            if order.name == '/':
                order.name = self.env['ir.sequence'].next_by_code(
                    'purchase.order'
                ) or '/'
        return super().button_confirm()
        
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