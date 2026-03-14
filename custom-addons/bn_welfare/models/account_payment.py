from odoo import models, api, fields
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
    
    # @api.model
    # def default_get(self, fields_list):
    #     """Override to set bank_reference from welfare/recurring line donee bank account"""
    #     res = super().default_get(fields_list)
        
    #     _logger.info("=== DEBUG: Payment Register default_get called ===")
    #     _logger.info(f"Context: {self._context}")
    #     _logger.info(f"Fields list: {fields_list}")
        
    #     # Get the active invoices/bills from context
    #     if self._context.get('active_model') == 'account.move' and self._context.get('active_ids'):
    #         bills = self.env['account.move'].browse(self._context.get('active_ids'))
    #         _logger.info(f"Bills found: {bills}")
            
    #         bank_reference = ''
    #         # Check each bill for welfare or recurring line linkage
    #         for bill in bills:
    #             _logger.info(f"Checking bill: {bill.name}")
    #             _logger.info(f"Has recurring_line_id: {hasattr(bill, 'recurring_line_id')}")
    #             _logger.info(f"Has welfare_line_id: {hasattr(bill, 'welfare_line_id')}")
                
    #             # Check if bill is linked to welfare recurring line
    #             if hasattr(bill, 'recurring_line_id') and bill.recurring_line_id:
    #                 _logger.info(f"Recurring line found: {bill.recurring_line_id}")
    #                 if bill.recurring_line_id.welfare_id and bill.recurring_line_id.welfare_id.donee_id:
    #                     bank_reference = bill.recurring_line_id.welfare_id.donee_id.bank_wallet_account or ''
    #                     _logger.info(f"Bank reference from recurring: {bank_reference}")
    #                     break
    #             # Check if bill is linked to welfare line
    #             elif hasattr(bill, 'welfare_line_id') and bill.welfare_line_id:
    #                 _logger.info(f"Welfare line found: {bill.welfare_line_id}")
    #                 if bill.welfare_line_id.welfare_id and bill.welfare_line_id.welfare_id.donee_id:
    #                     bank_reference = bill.welfare_line_id.welfare_id.donee_id.bank_wallet_account or ''
    #                     _logger.info(f"Bank reference from welfare: {bank_reference}")
    #                     break
            
    #         if bank_reference:
    #             res['bank_reference'] = bank_reference
    #             _logger.info(f"Final bank_reference set: {bank_reference}")
    #         else:
    #             _logger.info("No bank reference found")
    #     else:
    #         _logger.info("No active bills in context")
        
    #     _logger.info(f"=== Returning res: {res} ===")
    #     return res
    
    def action_create_payments(self):
        res = super().action_create_payments()

        # Handle welfare line and recurring line disbursement for Cash + Bank payments
        if self.line_ids:
            for line in self.line_ids:
                if line.move_id:
                    bill = line.move_id
                    
                    # Check if bill is linked to welfare recurring line
                    if bill.recurring_line_id and bill.recurring_line_id.state == 'draft':
                        bill.recurring_line_id.action_disbursed()
                    # Check if bill is linked to welfare line
                    elif bill.welfare_line_id and bill.welfare_line_id.state == 'draft':
                        bill.welfare_line_id.action_disbursed()

        return res



