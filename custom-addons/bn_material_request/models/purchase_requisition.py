# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


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
    def _get_pending_rfq_lines(self):
        """Lines still to be sent out for quotation: those whose product is not
        on a confirmed Purchase Order of the source Material Request yet. A
        requisition without a Material Request always sends all its lines."""
        self.ensure_one()
        if not self.material_request_id:
            return self.line_ids
        # sudo: whoever opens the requisition need not be a purchase user.
        ordered_products = self.env['purchase.order'].sudo().search([
            ('material_request_id', '=', self.material_request_id.id),
            ('state', 'in', ('purchase', 'done')),
        ]).order_line.product_id
        return self.line_ids.filtered(lambda line: line.product_id not in ordered_products)

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
