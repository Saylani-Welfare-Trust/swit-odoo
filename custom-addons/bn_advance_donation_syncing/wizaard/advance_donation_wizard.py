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
    
    # Context fields
    welfare_line_id = fields.Many2one('welfare.line', string="Welfare Line")
    recurring_line_id = fields.Many2one('welfare.recurring.line', string="Recurring Line")
    microfinance_id = fields.Many2one('microfinance', string="Microfinance")

    def action_show_lines(self):
        """Open second wizard with filtered donation lines"""
        if not self.advance_donation_id or not self.product_id:
            raise UserError(_("Please select both Advance Donation and Product."))
        
        # Get filtered lines
        donation_lines = self.advance_donation_id.advance_donation_lines.filtered(
            lambda l: l.product_id.id == self.product_id.id
        )
        
        if not donation_lines:
            raise UserError(_("No donation lines found for this product."))
        
        # FIRST, create the selection wizard record
        selection_wizard = self.env['advance.donation.line.selection.wizard'].create({
            'advance_donation_id': self.advance_donation_id.id,
            'product_id': self.product_id.id,
            'welfare_line_id': self.welfare_line_id.id if self.welfare_line_id else False,
            'recurring_line_id': self.recurring_line_id.id if self.recurring_line_id else False,
            'microfinance_id': self.microfinance_id.id if self.microfinance_id else False,
        })
        
        # THEN, create the line wizard records
        wizard_line_commands = []
        for line in donation_lines:
            wizard_line_commands.append((0, 0, {
                'original_line_id': line.id,
                'product_id': line.product_id.id,
                'paid_amount': line.paid_amount,
                'is_reserved': line.is_reserved,
                'currency_id': line.currency_id.id,
            }))
        
        if wizard_line_commands:
            selection_wizard.write({
                'donation_line_ids': wizard_line_commands
            })
        
        # Return the form view of the created wizard
        return {
            'name': _('Select Donation Line'),
            'type': 'ir.actions.act_window',
            'res_model': 'advance.donation.line.selection.wizard',
            'res_id': selection_wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }


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