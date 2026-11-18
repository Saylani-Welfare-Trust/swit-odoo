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
        """What the RFQs of the source Material Request - from all its
        requisitions - cover, matched against what that request needs
        purchased: {product: quantity not on an RFQ yet, in the product's
        unit}. See _get_rfq_covered_quantities for what a requisition covers."""
        self.ensure_one()
        if not self.material_request_id:
            return {}
        covered = defaultdict(float)
        # sudo: requisitions the user may not all be allowed to read.
        requisitions = self.sudo().search([('material_request_id', '=', self.material_request_id.id)])
        for requisition in requisitions:
            for product_id, quantity in requisition._get_rfq_covered_quantities().items():
                covered[product_id] += quantity
        shortfall = {}
        for product, (quantity, _description) in self._get_request_reference().items():
            missing = quantity - covered[product.id]
            if float_compare(missing, 0.0, precision_rounding=product.uom_id.rounding) > 0:
                shortfall[product] = missing
        return shortfall

    def _get_rfq_covered_quantities(self):
        """{product id: quantity this requisition covers, in the product's
        unit}. What its confirmed Purchase Orders order, and on an open
        requisition what its other RFQs quote for: the RFQs of several vendors
        quote for the same quantities, so the largest one counts, not their
        sum. An open requisition without any RFQ yet covers what its lines ask
        for. A closed or cancelled requisition no longer asks for what it did
        not order."""
        self.ensure_one()
        covered = self._get_ordered_quantities([('requisition_id', '=', self.id)])
        if self.state in ('done', 'cancel'):
            return covered
        # sudo: whoever opens the requisition need not be a purchase user.
        rfqs = self.sudo().purchase_ids.filtered(lambda rfq: rfq.state != 'cancel')
        if not rfqs:
            for line in self.line_ids:
                uom = line.product_id.uom_id
                covered[line.product_id.id] += (line.product_uom_id or uom)._compute_quantity(line.product_qty, uom)
            return covered
        for rfq in rfqs.filtered(lambda rfq: rfq.state not in ('purchase', 'done')):
            quoted = defaultdict(float)
            for order_line in rfq.order_line:
                quoted[order_line.product_id.id] += order_line.product_uom_qty
            for product_id, quantity in quoted.items():
                covered[product_id] = max(covered[product_id], quantity)
        return covered

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

    deleted_line_count = fields.Integer(
        string='Deleted Lines', compute='_compute_deleted_line_count',
        help='How many of this Purchase Request\'s lines were deleted, and by whom - see the deletion log.')

    def _compute_deleted_line_count(self):
        # sudo: the deletion log is a log, not something the requester's own
        # access rights on purchase.requisition.line should gate.
        groups = self.env['purchase.requisition.line.deletion.log'].sudo().read_group(
            [('requisition_id', 'in', self.ids)], ['requisition_id'], ['requisition_id'])
        count_by_requisition = {
            group['requisition_id'][0]: group['requisition_id_count']
            for group in groups if group['requisition_id']
        }
        for requisition in self:
            requisition.deleted_line_count = count_by_requisition.get(requisition.id, 0)

    def action_view_deleted_lines(self):
        """View the deletion log entries for this Purchase Request's lines"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Deleted Lines of %s', self.name),
            'res_model': 'purchase.requisition.line.deletion.log',
            'view_mode': 'tree,form',
            'domain': [('requisition_id', '=', self.id)],
            'context': {'create': False},
            'target': 'current',
        }

    def _close_if_fully_locked(self):
        """Move a requisition to 'done' (Closed) once every one of its lines
        has been fully locked by the consolidated-RFQ process. Called after
        VendorSelectionWizard.action_create_rfqs locks whatever it consumed."""
        for requisition in self:
            if requisition.state in ('done', 'cancel'):
                continue
            if requisition.line_ids and all(line.is_locked for line in requisition.line_ids):
                requisition.state = 'done'

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


class PurchaseRequisitionLine(models.Model):
    _name = 'purchase.requisition.line'
    _inherit = ['purchase.requisition.line', 'line.change.log.mixin']
    _line_log_parent = 'requisition_id'
    _line_log_fields = ['product_id', 'product_qty', 'product_uom_id', 'product_description_variants']

    # Set by VendorSelectionWizard.action_create_rfqs once a quantity of this
    # line has gone out on a consolidated RFQ. A line can be locked a little
    # at a time across several runs (locked_qty keeps the running total); once
    # locked_qty reaches product_qty the line itself is marked is_locked and
    # can never be picked again, while whatever quantity was not yet consumed
    # stays free for a future run.
    locked_qty = fields.Float(
        string='Locked Quantity', default=0.0, copy=False,
        help='Quantity of this line already sent out on a consolidated RFQ. '
             'Grows every time the Vendor Selection Wizard consumes part of this line.')
    is_locked = fields.Boolean(
        string='Fully Locked', default=False, copy=False,
        help='True once the full quantity of this line has been sent out on a '
             'consolidated RFQ. A fully locked line cannot be selected again.')
    remaining_qty = fields.Float(
        string='Remaining Qty', compute='_compute_remaining_qty',
        help='product_qty minus what has already been locked for a consolidated RFQ. '
             'What is still available for a future Vendor Selection Wizard run.')

    @api.depends('product_qty', 'locked_qty')
    def _compute_remaining_qty(self):
        for line in self:
            line.remaining_qty = max(line.product_qty - line.locked_qty, 0.0)

    def _lock_quantity(self, qty):
        """Consume ``qty`` of this line's remaining quantity for a
        consolidated RFQ, and lock the line once nothing is left on it."""
        self.ensure_one()
        uom = self.product_id.uom_id
        self.locked_qty += qty
        if float_compare(self.locked_qty, self.product_qty, precision_rounding=uom.rounding or 0.01) >= 0:
            self.locked_qty = self.product_qty
            self.is_locked = True

    def unlink(self):
        """Log who deleted this line, and what it was, before it is gone for
        good - a deleted purchase.requisition.line leaves nothing else behind
        to say who removed it or when."""
        log_vals = [{
            'requisition_id': line.requisition_id.id,
            'requisition_name': line.requisition_id.name,
            'product_id': line.product_id.id,
            'product_uom_id': line.product_uom_id.id,
            'quantity': line.product_qty,
            'locked_qty': line.locked_qty,
            'description': line.product_description_variants,
            'deleted_by': self.env.uid,
            'deleted_date': fields.Datetime.now(),
        } for line in self]
        result = super().unlink()
        if log_vals:
            # sudo: whoever may delete a PR line need not have access to the log model.
            self.env['purchase.requisition.line.deletion.log'].sudo().create(log_vals)
        return result
