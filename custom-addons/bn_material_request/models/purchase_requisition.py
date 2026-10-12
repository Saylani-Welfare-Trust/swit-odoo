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
    def _get_ordered_quantities(self):
        """{product id: quantity on the confirmed Purchase Orders of the source
        Material Request}, in the product's own unit of measure."""
        self.ensure_one()
        ordered = defaultdict(float)
        # sudo: whoever opens the requisition need not be a purchase user.
        orders = self.env['purchase.order'].sudo().search([
            ('material_request_id', '=', self.material_request_id.id),
            ('state', 'in', ('purchase', 'done')),
        ])
        for order_line in orders.order_line:
            ordered[order_line.product_id.id] += order_line.product_uom_qty
        return ordered

    def _get_request_shortfall(self):
        """What the Material Request asks for and no confirmed Purchase Order
        covers yet: {product: quantity, in the product's unit}.

        The Material Request is the reference here, so a product taken off this
        requisition, or a quantity lowered on it or on the RFQ, still counts.
        Only for the Purchase Request of a purchase-type Material Request: a
        stock-shortage requisition buys just the part its own lines say."""
        self.ensure_one()
        # sudo: the Material Request record rule hides requests the user didn't create.
        request = self.material_request_id.sudo()
        if request.purchase_request_id != self:
            return {}
        requested = defaultdict(float)
        for line in request.line_ids:
            requested[line.product_id] += line.quantity
        ordered = self._get_ordered_quantities()
        shortfall = {}
        for product, quantity in requested.items():
            missing = quantity - ordered[product.id]
            if float_compare(missing, 0.0, precision_rounding=product.uom_id.rounding) > 0:
                shortfall[product] = missing
        return shortfall

    def _get_pending_rfq_line_quantities(self):
        """{requisition line: quantity still to send out for quotation, in the
        line's unit}: what the line asks for, less what the confirmed Purchase
        Orders of the source Material Request already cover. A requisition
        without a Material Request always sends all its lines in full."""
        self.ensure_one()
        if not self.material_request_id:
            return {line: line.product_qty for line in self.line_ids}
        ordered = self._get_ordered_quantities()
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

    def _get_pending_rfq_lines(self):
        """Lines that still have something to send out for quotation."""
        pending = self._get_pending_rfq_line_quantities()
        return self.line_ids.filtered(lambda line: line in pending)

    def _restore_lines_from_request(self):
        """Bring the lines back in step with the Material Request for what it
        still needs: a product that was taken off this requisition gets a line
        again, a quantity that was lowered is raised by what is missing.
        Returns the {product: quantity} put back."""
        self.ensure_one()
        restored = {}
        pending = self._get_pending_rfq_line_quantities()
        for product, shortfall in self._get_request_shortfall().items():
            uom = product.uom_id
            lines = self.line_ids.filtered(lambda line: line.product_id == product)
            on_lines = sum(
                (line.product_uom_id or uom)._compute_quantity(quantity, uom)
                for line, quantity in pending.items() if line in lines)
            missing = shortfall - on_lines
            if float_compare(missing, 0.0, precision_rounding=uom.rounding) <= 0:
                continue
            if lines:
                line = lines[0]
                line.product_qty += uom._compute_quantity(missing, line.product_uom_id or uom)
            else:
                # sudo: the Material Request record rule hides requests the user didn't create.
                request_line = self.material_request_id.sudo().line_ids.filtered(
                    lambda l: l.product_id == product)[:1]
                self.env['purchase.requisition.line'].create({
                    'requisition_id': self.id,
                    'product_id': product.id,
                    'product_uom_id': uom.id,
                    'product_qty': missing,
                    'product_description_variants': request_line.description,
                })
            restored[product] = missing
        return restored

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
