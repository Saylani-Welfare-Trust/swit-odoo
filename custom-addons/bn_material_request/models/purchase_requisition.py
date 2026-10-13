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

    def _get_request_reference_lines(self):
        """[(product, quantity in the product's unit, description)]: what the
        source Material Request needs purchased. A purchase-type request is to
        be bought as a whole, so its own lines say it - whatever was taken off
        or lowered on a requisition later. An internal request only buys what
        was short in stock, which is on the lines of its first requisition."""
        self.ensure_one()
        # sudo: the Material Request record rule hides requests the user didn't create.
        request = self.material_request_id.sudo()
        if request.purchase_request_id:
            return [(line.product_id, line.quantity, line.description) for line in request.line_ids]
        return [(
            line.product_id,
            (line.product_uom_id or line.product_id.uom_id)._compute_quantity(line.product_qty, line.product_id.uom_id),
            line.product_description_variants,
        ) for line in request.auto_purchase_request_id.line_ids]

    def _get_request_shortfall(self):
        """The confirmed Purchase Orders of the source Material Request - from
        all its requisitions - matched against what that request needs
        purchased: {product: quantity not ordered yet, in the product's unit}."""
        self.ensure_one()
        if not self.material_request_id:
            return {}
        requested = defaultdict(float)
        for product, quantity, _description in self._get_request_reference_lines():
            requested[product] += quantity
        ordered = self._get_ordered_quantities([('material_request_id', '=', self.material_request_id.id)])
        shortfall = {}
        for product, quantity in requested.items():
            missing = quantity - ordered[product.id]
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
        needs purchased, and return it. It is a requisition of its own, to go
        through the same steps as the first one."""
        self.ensure_one()
        descriptions = {}
        for product, _quantity, description in self._get_request_reference_lines():
            descriptions.setdefault(product, description)
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
                'product_description_variants': descriptions.get(product),
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
