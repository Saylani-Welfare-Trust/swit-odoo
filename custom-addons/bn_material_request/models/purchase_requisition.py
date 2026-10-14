# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class PurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'
    material_request_id = fields.Many2one(
        'material.request',
        string='Source Material Request',
        readonly=True,
        copy=False,
        help='Material Request that generated this Purchase Request.'
    )
    material_request_requisition_count = fields.Integer(
        string='Purchase Requests of the Material Request',
        compute='_compute_material_request_requisition_count',
        help='How many Purchase Requests were made for the source Material Request, this one included.')

    @api.depends('material_request_id')
    def _compute_material_request_requisition_count(self):
        for requisition in self:
            # sudo: the Material Request record rule hides requests the user didn't create.
            requisition.material_request_requisition_count = \
                requisition.material_request_id.sudo().purchase_requisition_count

    def action_view_material_request_requisitions(self):
        """View every Purchase Request made for the source Material Request"""
        self.ensure_one()
        if not self.material_request_id:
            raise ValidationError(_('No source Material Request found.'))
        # sudo: the Material Request record rule hides requests the user didn't create.
        return self.material_request_id.sudo().action_view_purchase_requisitions()
    

    
    def action_create_multi_vendor_rfqs(self):
        """Open wizard to create RFQs (Purchase Orders) for multiple vendors"""
        self.ensure_one()
        
        if not self.line_ids:
            raise ValidationError(_('Please add product lines before creating RFQs for vendors.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Select Vendors for RFQs'),
            'res_model': 'vendor.selection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_source_requisition_id': self.id,
            },
        }
    def _get_ordered_quantities(self, domain):
        """{product id: quantity on the confirmed Purchase Orders matching
        ``domain``}, in the product's own unit of measure."""
        ordered = defaultdict(float)
        # sudo: whoever opens the requisition need not be a purchase user.
        orders = self.env['purchase.order'].sudo().search(
            domain + [('state', 'in', ('purchase', 'done'))])
        for order_line in orders.order_line:
            ordered[order_line.product_id.id] += order_line.product_uom_qty
        return ordered

    def _get_request_reference(self):
        """{product: [quantity in the product's unit, description]}: what the
        source Material Request needs purchased, whatever was taken off or
        lowered on a requisition afterwards.

        A purchase-type request is bought as a whole, so its own lines say it.
        An internal request only buys what was short in stock: that is kept on
        its stock-shortage transfer, created together with its first
        requisition - whose own lines can be edited, and so cannot be relied on
        alone."""
        self.ensure_one()
        # sudo: the Material Request record rule hides requests the user didn't create.
        request = self.material_request_id.sudo()
        reference = {}

        def add(target, product, quantity, description):
            entry = target.setdefault(product, [0.0, description])
            entry[0] += quantity
            entry[1] = entry[1] or description

        if request.purchase_request_id:
            for line in request.line_ids:
                add(reference, line.product_id, line.quantity, line.description)
            return reference

        transfers = request.shortage_picking_id
        while transfers.backorder_ids - transfers:
            transfers |= transfers.backorder_ids
        for move in transfers.move_ids.filtered(lambda move: move.state != 'cancel'):
            add(reference, move.product_id, move.product_qty, move.description_picking)
        # The first requisition's lines count where they ask for more than the
        # transfer does, or where the transfer has been cancelled.
        on_lines = {}
        for line in request.auto_purchase_request_id.line_ids:
            uom = line.product_id.uom_id
            add(on_lines, line.product_id,
                (line.product_uom_id or uom)._compute_quantity(line.product_qty, uom),
                line.product_description_variants)
        for product, (quantity, description) in on_lines.items():
            entry = reference.setdefault(product, [0.0, description])
            entry[0] = max(entry[0], quantity)
            entry[1] = entry[1] or description
        return reference

    def _get_request_shortfall(self):
        """The confirmed Purchase Orders of the source Material Request - from
        all its requisitions - and what its open requisitions still ask for,
        matched against what that request needs purchased: {product: quantity
        neither ordered nor requested yet, in the product's unit}. A closed
        requisition no longer asks for what it did not order."""
        self.ensure_one()
        if not self.material_request_id:
            return {}
        covered = self._get_ordered_quantities([('material_request_id', '=', self.material_request_id.id)])
        # sudo: requisitions the user may not all be allowed to read.
        open_requests = self.sudo().search([
            ('material_request_id', '=', self.material_request_id.id),
            ('state', 'not in', ('done', 'cancel')),
        ])
        for requisition in open_requests:
            for line, quantity in requisition._get_pending_rfq_line_quantities().items():
                uom = line.product_id.uom_id
                covered[line.product_id.id] += (line.product_uom_id or uom)._compute_quantity(quantity, uom)
        shortfall = {}
        for product, (quantity, _description) in self._get_request_reference().items():
            missing = quantity - covered[product.id]
            if float_compare(missing, 0.0, precision_rounding=product.uom_id.rounding) > 0:
                shortfall[product] = missing
        return shortfall

    def _has_newer_request(self):
        """Whether the source Material Request has a more recent requisition
        than this one (a cancelled one does not count)."""
        self.ensure_one()
        # sudo: a count across requisitions the user may not all be allowed to read.
        return bool(self.sudo().search_count([
            ('material_request_id', '=', self.material_request_id.id),
            ('state', '!=', 'cancel'),
            ('id', '>', self._origin.id),
        ], limit=1))

    def _create_remaining_request(self):
        """Create the requisition for what the source Material Request still
        needs purchased, and return it. It is a requisition of its own; this
        one is left as it is."""
        self.ensure_one()
        reference = self._get_request_reference()
        # sudo: like the first requisition of a Material Request, it may be
        # created by someone who is not a purchase user.
        return self.env['purchase.requisition'].sudo().create({
            'origin': self.origin,
            'material_request_id': self.material_request_id.id,
            'user_id': self.user_id.id,
            'type_id': self.type_id.id,
            'company_id': self.company_id.id,
            'line_ids': [(0, 0, {
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'product_qty': quantity,
                'product_description_variants': reference[product][1],
            }) for product, quantity in self._get_request_shortfall().items()],
        }).sudo(False)

    def _get_pending_rfq_line_quantities(self):
        """{requisition line: quantity still to send out for quotation, in the
        line's unit}: what the line asks for, less what the confirmed Purchase
        Orders of this requisition already cover. A requisition without a
        Material Request always sends all its lines in full."""
        self.ensure_one()
        if not self.material_request_id:
            return {line: line.product_qty for line in self.line_ids}
        ordered = self._get_ordered_quantities([('requisition_id', '=', self.id)])
        pending = {}
        for line in self.line_ids:
            uom = line.product_id.uom_id
            line_uom = line.product_uom_id or uom
            requested = line_uom._compute_quantity(line.product_qty, uom)
            # An ordered quantity is taken off the lines of its product one after the other.
            covered = min(requested, ordered[line.product_id.id])
            ordered[line.product_id.id] -= covered
            if float_compare(requested - covered, 0.0, precision_rounding=uom.rounding) > 0:
                pending[line] = uom._compute_quantity(requested - covered, line_uom)
        return pending

    def action_view_material_request(self):
        """View the source Material Request"""
        self.ensure_one()
        if not self.material_request_id:
            raise ValidationError(_('No source Material Request found.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Material Request'),
            'res_model': 'material.request',
            'res_id': self.material_request_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
