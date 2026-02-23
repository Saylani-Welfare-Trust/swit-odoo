# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class RFQPriceWizardRFQLine(models.TransientModel):
    _name = 'rfq.price.wizard.rfq.line'
    _description = 'RFQ Price Wizard - RFQ Level Data'

    wizard_id = fields.Many2one('rfq.price.wizard', string='Wizard', ondelete='cascade')
    rfq_id = fields.Many2one('purchase.order', string='RFQ', readonly=True)
    rfq_name = fields.Char(related='rfq_id.name', string='RFQ Reference', readonly=True)
    vendor_id = fields.Many2one(related='rfq_id.partner_id', string='Vendor', readonly=True)
    expected_date = fields.Date(string='Expected Delivery Date', help='Expected delivery date for this RFQ')
    total_amount = fields.Monetary(string='Total Amount', compute='_compute_total_amount', store=True, currency_field='currency_id')
    currency_id = fields.Many2one(related='rfq_id.currency_id', string='Currency')
    is_nearest_date = fields.Boolean(string='Nearest Date', compute='_compute_checks', store=False)
    is_minimum_total = fields.Boolean(string='Minimum Total', compute='_compute_checks', store=False)
    is_selected = fields.Boolean(string='Selected', compute='_compute_checks', store=False)

    @api.depends('wizard_id.line_ids.price_unit', 'wizard_id.line_ids.product_qty')
    def _compute_total_amount(self):
        """Calculate total amount for this RFQ from all its product lines"""
        for record in self:
            price_lines = record.wizard_id.line_ids.filtered(lambda l: l.rfq_id == record.rfq_id)
            record.total_amount = sum(line.price_unit * line.product_qty for line in price_lines)

    @api.depends('expected_date', 'total_amount', 'wizard_id.rfq_line_ids.expected_date', 'wizard_id.rfq_line_ids.total_amount')
    def _compute_checks(self):
        """Determine which RFQ has nearest date and minimum total"""
        for record in self:
            record.is_nearest_date = False
            record.is_minimum_total = False
            record.is_selected = False
            
            if not record.wizard_id or not record.expected_date:
                continue
            
            all_rfq_lines = record.wizard_id.rfq_line_ids.filtered(lambda l: l.expected_date)
            
            if all_rfq_lines:
                # Find nearest date
                nearest_date = min(all_rfq_lines.mapped('expected_date'))
                if record.expected_date == nearest_date:
                    record.is_nearest_date = True
                
                # Find minimum total
                min_total = min(all_rfq_lines.mapped('total_amount'))
                if record.total_amount == min_total:
                    record.is_minimum_total = True
                
                # For is_selected: Only mark the FIRST RFQ that has both conditions
                # This ensures only one RFQ is visually marked as selected
                qualifying_rfqs = all_rfq_lines.filtered(
                    lambda l: l.expected_date == nearest_date and l.total_amount == min_total
                )
                if qualifying_rfqs and record == qualifying_rfqs[0]:
                    record.is_selected = True


class RFQPriceWizardLine(models.TransientModel):
    _name = 'rfq.price.wizard.line'
    _description = 'RFQ Price Wizard Line'

    wizard_id = fields.Many2one('rfq.price.wizard', string='Wizard', ondelete='cascade')
    rfq_id = fields.Many2one('purchase.order', string='RFQ', readonly=True)
    rfq_name = fields.Char(related='rfq_id.name', string='RFQ Reference', readonly=True)
    vendor_id = fields.Many2one(related='rfq_id.partner_id', string='Vendor', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_qty = fields.Float(string='Quantity', readonly=True)
    product_uom_id = fields.Many2one('uom.uom', string='UoM', readonly=True)
    price_unit = fields.Float(string='Unit Price', digits='Product Price')
    rfq_line_id = fields.Many2one('purchase.order.line', string='RFQ Line', readonly=True)


class RFQPriceWizard(models.TransientModel):
    _name = 'rfq.price.wizard'
    _description = 'Bulk RFQ Price Entry Wizard'

    rfq_ids = fields.Many2many('purchase.order', string='Selected RFQs')
    rfq_line_ids = fields.One2many('rfq.price.wizard.rfq.line', 'wizard_id', string='RFQ Lines')
    line_ids = fields.One2many('rfq.price.wizard.line', 'wizard_id', string='Price Lines')
    rfq_count = fields.Integer(compute='_compute_rfq_count', string='RFQ Count')
    total_lines = fields.Integer(compute='_compute_total_lines', string='Total Products')
    selected_rfq_id = fields.Many2one('purchase.order', string='Selected RFQ', compute='_compute_selected_rfq', store=False)
    selected_rfq_name = fields.Char(string='Selected RFQ Name', compute='_compute_selected_rfq', store=False)

    @api.depends('rfq_ids')
    def _compute_rfq_count(self):
        for wizard in self:
            wizard.rfq_count = len(wizard.rfq_ids)

    @api.depends('line_ids')
    def _compute_total_lines(self):
        for wizard in self:
            wizard.total_lines = len(wizard.line_ids)

    @api.depends('rfq_line_ids.is_selected')
    def _compute_selected_rfq(self):
        """Find the RFQ that has both nearest date and minimum total (only one)"""
        for wizard in self:
            selected_lines = wizard.rfq_line_ids.filtered(lambda l: l.is_selected)
            if selected_lines:
                # If multiple RFQs qualify, take only the first one
                wizard.selected_rfq_id = selected_lines[0].rfq_id
                wizard.selected_rfq_name = selected_lines[0].rfq_name
            else:
                wizard.selected_rfq_id = False
                wizard.selected_rfq_name = False

    @api.model
    def default_get(self, fields_list):
        """Pre-populate wizard with selected RFQs and their lines"""
        res = super().default_get(fields_list)
        
        # Get selected RFQ IDs from context
        rfq_ids = self.env.context.get('active_ids', [])
        if not rfq_ids:
            return res
        
        rfqs = self.env['purchase.order'].browse(rfq_ids)
        res['rfq_ids'] = [(6, 0, rfq_ids)]
        
        # Build RFQ-level lines (for expected dates)
        rfq_lines = []
        for rfq in rfqs:
            # Get the expected date from the first order line if available
            expected_date = False
            if rfq.order_line:
                expected_date = rfq.order_line[0].date_planned or fields.Date.today()
            rfq_lines.append((0, 0, {
                'rfq_id': rfq.id,
                'expected_date': expected_date,
            }))
        res['rfq_line_ids'] = rfq_lines
        
        # Build price lines for all RFQ lines
        price_lines = []
        for rfq in rfqs:
            for order_line in rfq.order_line:
                price_lines.append((0, 0, {
                    'rfq_id': rfq.id,
                    'product_id': order_line.product_id.id,
                    'product_qty': order_line.product_qty,
                    'product_uom_id': order_line.product_uom.id,
                    'price_unit': order_line.price_unit or 0.0,
                    'rfq_line_id': order_line.id,
                }))
        
        res['line_ids'] = price_lines
        return res

    def action_update_prices(self):
        """Update prices in all RFQs and confirm the selected one (with both checks)"""
        self.ensure_one()
        
        if not self.line_ids:
            raise ValidationError(_('No price lines to update.'))
        
        # Check if there's a selected RFQ (with both nearest date and minimum total)
        # If multiple RFQs qualify, only the first one will be selected
        if not self.selected_rfq_id:
            raise ValidationError(_('No RFQ qualifies with both Nearest Date and Minimum Total. Please ensure at least one RFQ has both conditions met.'))
        
        # Validate that all lines have required data
        invalid_lines = self.line_ids.filtered(lambda l: not l.rfq_line_id or not l.rfq_id)
        if invalid_lines:
            raise ValidationError(_('Some price lines are missing required RFQ information. Please refresh the wizard.'))
        
        # Build a mapping of RFQ to expected date
        rfq_date_map = {}
        for rfq_line in self.rfq_line_ids:
            if rfq_line.expected_date:
                rfq_date_map[rfq_line.rfq_id.id] = rfq_line.expected_date
        
        # Update ALL RFQ lines (prices and dates)
        updated_rfqs = self.env['purchase.order']
        updated_count = 0
        
        for line in self.line_ids:
            if line.rfq_line_id and line.rfq_line_id.exists():
                # Update the RFQ line price and expected date
                update_vals = {
                    'price_unit': line.price_unit,
                }
                # Get expected date for this RFQ from the mapping
                if line.rfq_id.id in rfq_date_map:
                    update_vals['date_planned'] = rfq_date_map[line.rfq_id.id]
                line.rfq_line_id.write(update_vals)
                updated_rfqs |= line.rfq_id
                updated_count += 1
        
        if not updated_rfqs:
            raise ValidationError(_('No RFQ lines were updated. Please check if the RFQs still exist.'))
        
        # Post message to all updated RFQs
        for rfq in updated_rfqs:
            rfq_lines_in_wizard = self.line_ids.filtered(lambda l: l.rfq_id == rfq)
            message = '<p><b>Prices Updated via Bulk Entry:</b></p><ul>'
            for wiz_line in rfq_lines_in_wizard:
                message += f'<li>{wiz_line.product_id.display_name}: {wiz_line.price_unit:.2f} {rfq.currency_id.symbol or ""}</li>'
            message += '</ul>'
            # Add expected date info if set
            if rfq.id in rfq_date_map:
                message += f'<p><b>Expected Delivery Date:</b> {rfq_date_map[rfq.id].strftime("%Y-%m-%d")}</p>'
            
            # Mark if this is the selected RFQ
            if rfq == self.selected_rfq_id:
                message += '<p><b>✓ Selected RFQ (Nearest Date + Minimum Total) - Confirmed</b></p>'
            
            rfq.message_post(body=message)
        
        # Confirm ONLY the selected RFQ (the one with both checks)
        try:
            if hasattr(self.selected_rfq_id, 'button_confirm'):
                self.selected_rfq_id.button_confirm()
                confirm_message = _('RFQ %s has been confirmed.') % self.selected_rfq_id.name
            else:
                confirm_message = _('Note: button_confirm method not available.')
        except Exception as e:
            confirm_message = _('Error confirming RFQ: %s') % str(e)
        
        # Show success message and close wizard
        message = _('Updated %d price(s) for %d RFQ(s). %s') % (updated_count, len(updated_rfqs), confirm_message)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
