from odoo import api, fields, models, _
from odoo.exceptions import UserError

class AdvanceDonationWizard(models.TransientModel):
    _name = 'advance.donation.wizard'
    _description = 'Wizard to Select Advance Donation'

    advance_donation_id = fields.Many2one(
        'advance.donation', 
        string="Advance Donation",
        required=True,
        help="Select an advance donation to import its lines."
    )
    
    product_id = fields.Many2one('product.product', string="Product", required=True)
    today_date = fields.Date(string="Today Date", default=fields.Date.today)
    
    # Context fields
    welfare_line_id = fields.Many2one('welfare.line', string="Welfare Line")
    recurring_line_id = fields.Many2one('welfare.recurring.line', string="Recurring Line")
    microfinance_id = fields.Many2one('microfinance', string="Microfinance")

    def action_show_lines(self):
        """Automatically select and confirm the first available donation line"""

        if not self.advance_donation_id or not self.product_id:
            raise UserError(_("Please select both Advance Donation and Product."))
        
        # Get filtered lines
        donation_lines = self.advance_donation_id.advance_donation_lines.filtered(
            lambda l: l.product_id.id == self.product_id.id
        )
        
        if not donation_lines:
            raise UserError(_("No donation lines found for this product."))
        
        # Find first non-reserved line
        available_line = donation_lines.filtered(lambda l: not l.is_reserved)
        if not available_line:
            raise UserError(_("All donation lines for this product are already reserved."))
        
        available_line = available_line[0]  # Take the first available line
        
        
        if self.welfare_line_id:
            target_model = self.welfare_line_id
            limit_amount = target_model.total_amount

        elif self.recurring_line_id:
            target_model = self.recurring_line_id
            limit_amount = target_model.amount 

        elif self.microfinance_id:
            target_model = self.microfinance_id
            limit_amount = target_model.total_amount

        else:
            raise UserError(_("No target record found to link the donation."))

        if target_model.advance_donation_id and target_model.advance_donation_id.id == self.advance_donation_id.id:
            raise UserError(_("This Advance Donation is already linked to this record."))
       
        if not available_line.paid_amount > limit_amount:
        
            # Prepare values to write
            vals = {
                'advance_donation_id': self.advance_donation_id.id,
                'advance_donation_line_id': available_line.id,
                'advance_donation_amount': available_line.paid_amount
            }
        else:
            vals = {
                'advance_donation_id': self.advance_donation_id.id,
                'advance_donation_line_id': available_line.id,
                'advance_donation_amount': limit_amount
            }
        
        # Apply deduction only if recurring_line_id exists
        if self.recurring_line_id:
            current_amount = target_model.amount or 0.0
            if not self.advance_donation_id.contract_type == 'open_contract':

                vals['amount'] = current_amount - available_line.paid_amount
            else:
                vals['amount'] = current_amount - limit_amount

        
        # Update the target record
        target_model.write(vals)
        if not self.advance_donation_id.contract_type == 'open_contract':
            # Mark original line as reserved
            available_line.write({'is_reserved': True})
        else:
            # For open contracts, we reserve the amount instead of the line
            if available_line.reserved_amount + limit_amount > available_line.paid_amount:
                raise UserError(_("Not enough available amount in the selected donation line."))
            available_line.write({'reserved_amount': available_line.reserved_amount + limit_amount})      
        # Close wizard
        return {'type': 'ir.actions.act_window_close'}


class AdvanceDonationLineSelectionWizard(models.TransientModel):
    _name = 'advance.donation.line.selection.wizard'
    _description = 'Wizard to Select Specific Donation Line'

    advance_donation_id = fields.Many2one('advance.donation', string="Advance Donation", required=True)
    product_id = fields.Many2one('product.product', string="Product", required=True)
    
    # One2many to display available lines
    donation_line_ids = fields.One2many(
        'advance.donation.line.wizard',
        'selection_wizard_id',
        string="Available Donation Lines"
    )
    
    # Context fields (to know where to write back)
    welfare_line_id = fields.Many2one('welfare.line', string="Welfare Line")
    recurring_line_id = fields.Many2one('welfare.recurring.line', string="Recurring Line")
    microfinance_id = fields.Many2one('microfinance', string="Microfinance")
    
    def action_confirm(self):
        """Confirm selected donation line"""
        selected_line = self.donation_line_ids.filtered(lambda l: l.is_selected)
        
        if not selected_line:
            raise UserError(_("Please select a donation line."))
        
        if len(selected_line) > 1:
            raise UserError(_("You can only select one donation line."))
        
        selected_line = selected_line[0]
        
        # Check if already reserved
        if selected_line.is_reserved:
            raise UserError(_("This donation line is already reserved."))
        
        # Determine which model to update
        if self.welfare_line_id:
            target_model = self.welfare_line_id
        elif self.recurring_line_id:
            target_model = self.recurring_line_id
        elif self.microfinance_id:
            target_model = self.microfinance_id
        else:
            raise UserError(_("No target record found to link the donation."))
        
        # Update the target record
        target_model.write({
            'advance_donation_id': self.advance_donation_id.id,
            'advance_donation_line_id': selected_line.original_line_id.id,
            'advance_donation_amount': selected_line.paid_amount
            
        })
        
        
        vals = {
        'advance_donation_id': self.advance_donation_id.id,
        'advance_donation_line_id': selected_line.original_line_id.id,
        'advance_donation_amount': selected_line.paid_amount
            }

        # ✅ Apply deduction only if recurring_line_id exists
        if self.recurring_line_id:
            current_amount = target_model.amount or 0.0
            vals['amount'] = current_amount - selected_line.paid_amount

        target_model.write(vals)
        # Mark original line as reserved
        selected_line.original_line_id.write({'is_reserved': True})
        
        # Close wizard
        return {'type': 'ir.actions.act_window_close'}


class AdvanceDonationLineWizard(models.TransientModel):
    _name = 'advance.donation.line.wizard'
    _description = 'Wizard Lines for Donation Selection'

    selection_wizard_id = fields.Many2one(
        'advance.donation.line.selection.wizard',
        string="Selection Wizard",
        required=True,
        ondelete='cascade'
    )
    
    original_line_id = fields.Many2one(
        'advance.donation.lines',
        string="Original Donation Line",
    )
    
    product_id = fields.Many2one('product.product', string="Product")
    paid_amount = fields.Monetary('Paid Amount', currency_field='currency_id')
    is_reserved = fields.Boolean(string="Reserved", readonly=True)
    is_selected = fields.Boolean(string="Select")
    currency_id = fields.Many2one('res.currency', 'Currency', 
                                   default=lambda self: self.env.company.currency_id)