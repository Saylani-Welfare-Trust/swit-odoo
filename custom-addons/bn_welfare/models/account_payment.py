from odoo import models, api
# from odoo.exceptions import Warning
import logging

_logger = logging.getLogger(__name__)

class AccountRegisterPayments(models.TransientModel):
    _inherit = 'account.payment.register'
    
    @api.onchange('source_amount', 'source_amount_currency', 'source_currency_id', 'company_id', 'currency_id', 'payment_date', 'line_ids')
    def _onchange_set_bank_reference(self):
        """Set bank reference when wizard loads or changes"""
        _logger.info("=== DEBUG: _onchange_set_bank_reference called ===")
        
        if self.line_ids:
            for line in self.line_ids:
                if line.move_id:
                    bill = line.move_id
                    _logger.info(f"Checking bill: {bill.name}")
                    
                    # Check if bill is linked to welfare recurring line
                    if hasattr(bill, 'recurring_line_id') and bill.recurring_line_id:
                        _logger.info(f"Found recurring_line_id: {bill.recurring_line_id}")
                        if bill.recurring_line_id.welfare_id and bill.recurring_line_id.welfare_id.donee_id:
                            bank_ref = bill.recurring_line_id.welfare_id.donee_id.bank_wallet_account
                            if bank_ref:
                                self.bank_reference = bank_ref
                                _logger.info(f"Set bank_reference from recurring: {bank_ref}")
                                return
                    
                    # Check if bill is linked to welfare line
                    if hasattr(bill, 'welfare_line_id') and bill.welfare_line_id:
                        _logger.info(f"Found welfare_line_id: {bill.welfare_line_id}")
                        if bill.welfare_line_id.welfare_id and bill.welfare_line_id.welfare_id.donee_id:
                            bank_ref = bill.welfare_line_id.welfare_id.donee_id.bank_wallet_account
                            if bank_ref:
                                self.bank_reference = bank_ref
                                _logger.info(f"Set bank_reference from welfare: {bank_ref}")
                                return
        
        _logger.info("No bank reference found in onchange")
    
    
    def action_create_payments(self):
        res = super().action_create_payments()
        # Handle welfare line and recurring line disbursement for Cash + Bank payments
        if self.line_ids:
            for line in self.line_ids:
                if line.move_id:
                    bill = line.move_id
                    
                    # Check if bill is linked to welfare recurring line
                    if bill.recurring_line_id and bill.recurring_line_id.state == 'delivered':
                        bill.recurring_line_id.action_disbursed()
                    # Check if bill is linked to welfare line
                    elif bill.welfare_line_id and bill.welfare_line_id.state == 'delivered':
                        # raise Warning("Debug: action_create_payments called. Check logs for details.")
                        bill.welfare_line_id.action_disbursed()

        return res


