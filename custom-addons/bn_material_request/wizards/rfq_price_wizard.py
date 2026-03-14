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
    select_for_confirm = fields.Boolean(string='Select for Confirmation', default=False, help='Check to confirm this entire RFQ')

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
    to_confirm = fields.Boolean(string='Confirm', default=False, help='Select this line to confirm in the RFQ')


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
    remarks = fields.Text(string='Remarks', help='These remarks will be posted to all RFQs (confirmed or updated)')

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
        """Update prices in all RFQs without confirmation"""
        self.ensure_one()
        
        if not self.line_ids:
            raise ValidationError(_('No price lines to update.'))
        
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
            message = 'Prices Updated via Bulk Entry\n\n'
            message += 'Updated Products:\n'
            for wiz_line in rfq_lines_in_wizard:
                message += f'  - {wiz_line.product_id.display_name}: {wiz_line.price_unit:.2f} {rfq.currency_id.symbol or ""}\n'
            
            # Add expected date info if set
            if rfq.id in rfq_date_map:
                message += f'\nExpected Delivery Date: {rfq_date_map[rfq.id].strftime("%d %B %Y")}'
            
            # Add remarks if provided
            if self.remarks:
                message += f'\n\nRemarks:\n{self.remarks}'
            
            rfq.message_post(body=message)
        
        # Show success message and close wizard
        message = _('Updated %d price(s) for %d RFQ(s).') % (updated_count, len(updated_rfqs))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_confirm_selected(self):
        """Confirm selected lines from RFQs with remarks validation"""
        self.ensure_one()
        
        # Get RFQs selected at RFQ level (entire RFQ)
        rfqs_selected_entirely = self.rfq_line_ids.filtered(lambda l: l.select_for_confirm).mapped('rfq_id')
        
        # Get lines marked for confirmation at line level
        lines_to_confirm = self.line_ids.filtered(lambda l: l.to_confirm)
        
        # Combine: if RFQ is selected entirely, include all its lines
        all_lines_to_confirm = lines_to_confirm
        for rfq in rfqs_selected_entirely:
            rfq_lines = self.line_ids.filtered(lambda l: l.rfq_id == rfq and not l.to_confirm)
            all_lines_to_confirm |= rfq_lines
        
        if not all_lines_to_confirm:
            raise ValidationError(_('Please select at least one RFQ or line to confirm.'))
        
        # Check if any non-suggested RFQ is being confirmed - if so, remarks are mandatory
        suggested_rfq_id = self.selected_rfq_id.id if self.selected_rfq_id else False
                
        if  not self.remarks:
            raise ValidationError(_('Remarks are required when confirming non-suggested RFQs.'))
        
        # Group lines by RFQ
        rfqs_to_confirm = {}
        for line in all_lines_to_confirm:
            if line.rfq_id.id not in rfqs_to_confirm:
                rfqs_to_confirm[line.rfq_id.id] = {
                    'rfq': line.rfq_id,
                    'lines': self.env['rfq.price.wizard.line'],
                    'is_entire_rfq': line.rfq_id in rfqs_selected_entirely
                }
            rfqs_to_confirm[line.rfq_id.id]['lines'] |= line
        
        # Process each RFQ
        confirmed_rfqs = []
        
        for rfq_id, data in rfqs_to_confirm.items():
            rfq = data['rfq']
            selected_lines = data['lines']
            is_entire_rfq = data['is_entire_rfq']
            
            # Get all order lines from this RFQ
            all_order_lines = rfq.order_line
            selected_order_line_ids = selected_lines.mapped('rfq_line_id').ids
            
            # Find lines to remove (not selected) - only if not confirming entire RFQ
            lines_to_remove = self.env['purchase.order.line']
            if not is_entire_rfq:
                lines_to_remove = all_order_lines.filtered(lambda l: l.id not in selected_order_line_ids)
            
            # Save removed lines info BEFORE unlinking
            removed_lines_info = []
            if lines_to_remove:
                for line in lines_to_remove:
                    removed_lines_info.append({
                        'name': line.product_id.display_name,
                        'qty': line.product_qty,
                    })
                lines_to_remove.unlink()
            
            # Prepare confirmation message
            message = 'RFQ Confirmed via Bulk Confirmation\n\n'
            
            # Status badges
            if is_entire_rfq:
                message += 'Status: Entire RFQ Confirmed\n'
            
            if rfq_id == suggested_rfq_id:
                message += 'Suggested RFQ (Nearest Date + Minimum Total)\n'
            
            # Confirmed lines
            message += '\nConfirmed Lines:\n'
            for wiz_line in selected_lines:
                message += f'  - {wiz_line.product_id.display_name} - Qty: {wiz_line.product_qty} @ {wiz_line.price_unit:.2f}\n'
            
            # Removed lines
            if removed_lines_info:
                message += '\nRemoved Lines:\n'
                for removed_line in removed_lines_info:
                    message += f'  - {removed_line["name"]}\n'
            
            # Add remarks if provided
            if self.remarks:
                message += f'\nRemarks:\n{self.remarks}'
            
            rfq.message_post(body=message)
            
            # Confirm the RFQ
            try:
                if hasattr(rfq, 'button_confirm'):
                    rfq.button_confirm()
                    confirmed_rfqs.append(rfq.name)
            except Exception as e:
                raise ValidationError(_('Error confirming RFQ %s: %s') % (rfq.name, str(e)))
        
        # Show success message
        message = _('Successfully confirmed %d RFQ(s): %s') % (len(confirmed_rfqs), ', '.join(confirmed_rfqs))
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
