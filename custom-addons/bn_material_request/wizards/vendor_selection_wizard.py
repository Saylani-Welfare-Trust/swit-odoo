# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class VendorSelectionWizard(models.TransientModel):
    _name = 'vendor.selection.wizard'
    _description = 'Vendor Selection for RFQ Creation'

    source_requisition_id = fields.Many2one('purchase.requisition', string='Source Purchase Requisition', 
                                     help='Original Purchase Requisition to copy products from')
    vendor_ids = fields.Many2many('res.partner', string='Vendors', 
                                   domain="[('supplier_rank', '>', 0)]",
                                   help='Select multiple vendors to create RFQs')
    vendor_count = fields.Integer(compute='_compute_vendor_count', string='Selected Vendors')
    
    @api.depends('vendor_ids')
    def _compute_vendor_count(self):
        for wizard in self:
            wizard.vendor_count = len(wizard.vendor_ids)
    
    @api.model
    def default_get(self, fields_list):
        """Get source Purchase Requisition from context"""
        res = super().default_get(fields_list)
        
        # Get from active_id (when called from Purchase Requisition form/list)
        active_id = self.env.context.get('active_id')
        if active_id:
            res['source_requisition_id'] = active_id
        
        return res
    
    def action_create_rfqs(self):
        """Create one RFQ (Purchase Order) per selected vendor"""
        self.ensure_one()
        
        if not self.vendor_ids:
            raise ValidationError(_('Please select at least one vendor.'))
        
        if not self.source_requisition_id or not self.source_requisition_id.line_ids:
            raise ValidationError(_('No product lines found in the source Purchase Requisition.'))
        
        created_rfqs = self.env['purchase.order']
        
        for vendor in self.vendor_ids:
            # Prepare line values from source Purchase Requisition
            line_vals = []
            for line in self.source_requisition_id.line_ids:
                line_vals.append((0, 0, {
                    'product_id': line.product_id.id,
                    'product_uom': line.product_uom_id.id,
                    'product_qty': line.product_qty,
                    'price_unit': 0.0,  # Will be filled later
                }))
            
            # Create RFQ (Purchase Order) for this vendor
            rfq = self.env['purchase.order'].create({
                'partner_id': vendor.id,
                'requisition_id': self.source_requisition_id.id,
                'origin': self.source_requisition_id.name or self.source_requisition_id.origin or '',
                'order_line': line_vals,
            })
            created_rfqs |= rfq
        
        # Post message to source Purchase Requisition
        vendor_names = ', '.join(self.vendor_ids.mapped('name'))
        message = f'<p><b>{len(created_rfqs)} RFQ(s) Created for Vendors:</b></p><ul>'
        for rfq in created_rfqs:
            message += f'<li><a href="/web#id={rfq.id}&model=purchase.order&view_type=form">{rfq.name}</a> - {rfq.partner_id.name}</li>'
        message += '</ul>'
        self.source_requisition_id.message_post(body=message)
        
        # Return action to view created RFQs
        if len(created_rfqs) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('RFQ Created'),
                'res_model': 'purchase.order',
                'res_id': created_rfqs[0].id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': _('RFQs Created'),
                'res_model': 'purchase.order',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', created_rfqs.ids)],
                'target': 'current',
            }
