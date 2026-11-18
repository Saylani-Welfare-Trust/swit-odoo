from collections import defaultdict

from markupsafe import Markup

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    bulk_price_state = fields.Selection([
        ('draft', 'Draft'),
        ('price_update', 'Price Updated'),
        ('confirmed', 'Confirmed'),
    ], string='Bulk Price Entry Status', default='draft', copy=False, tracking=True)

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
        string='Source Purchase Request Count', compute='_compute_requisition_tag_count')

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

    # ------------------------------------------------------------------
    # Purchase Request quantities taken by the RFQs
    # ------------------------------------------------------------------
    def button_cancel(self):
        res = super().button_cancel()
        self._release_requisition_quantities()
        return res

    def button_draft(self):
        self._retake_requisition_quantities()
        return super().button_draft()

    def _release_requisition_quantities(self):
        """Once every RFQ of a batch is cancelled, the Purchase Request lines get
        back the quantity it had taken, to send out on a new RFQ. While one RFQ
        of the batch is still open - another vendor's quote, or the winning one
        once the others are cancelled - the quantity stays taken."""
        # sudo: the lines are given back whoever cancels the RFQ
        locks = self.env['purchase.requisition.line.lock'].sudo().search([
            ('order_ids', 'in', self.ids), ('released', '=', False)])
        locks = locks.filtered(lambda lock: all(order.state == 'cancel' for order in lock.order_ids))
        if not locks:
            return
        items = defaultdict(list)
        for lock in locks:
            line = lock.requisition_line_id
            line._unlock_quantity(lock.quantity)
            items[line.requisition_id].append(Markup('<li>%s: %s %s</li>') % (
                line.product_id.display_name, lock.quantity, line.product_uom_id.name or ''))
        locks.released = True
        orders = ', '.join(locks.order_ids.mapped('display_name'))
        for requisition, lines in items.items():
            requisition.message_post(body=Markup('%s<ul>%s</ul>') % (
                _('RFQ(s) %s cancelled - available again to send out on a new RFQ:') % orders,
                Markup().join(lines)))

    def _retake_requisition_quantities(self):
        """A cancelled RFQ set back to draft takes back the quantity its batch
        had given back - refused if it has gone out on another RFQ since."""
        locks = self.env['purchase.requisition.line.lock'].sudo().search([
            ('order_ids', 'in', self.filtered(lambda order: order.state == 'cancel').ids),
            ('released', '=', True)])
        for lock in locks:
            line = lock.requisition_line_id
            uom = line.product_id.uom_id
            if float_compare(lock.quantity, line.remaining_qty, precision_rounding=uom.rounding or 0.01) > 0:
                raise ValidationError(_(
                    'This RFQ cannot be set back to draft: %(product)s of Purchase Request %(request)s '
                    'has been sent out on another RFQ since it was cancelled (%(remaining)s left, '
                    '%(quantity)s needed).') % {
                        'product': line.product_id.display_name, 'request': line.requisition_id.name,
                        'remaining': line.remaining_qty, 'quantity': lock.quantity})
            line._lock_quantity(lock.quantity)
        locks.released = False


class PurchaseOrderLine(models.Model):
    _name = 'purchase.order.line'
    _inherit = ['purchase.order.line', 'line.change.log.mixin']
    _line_log_parent = 'order_id'
    _line_log_fields = ['product_id', 'name', 'product_qty', 'product_uom', 'price_unit', 'discount', 'taxes_id']

    def _line_log_ignored(self, field_name):
        # Odoo itself already logs a quantity change on a confirmed Purchase Order.
        return field_name == 'product_qty' and self.order_id.state == 'purchase'
