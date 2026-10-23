from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class WelfareRecurringLineSync(models.Model):
    """Extend welfare recurring line with advance donation integration"""
    _name = 'welfare.recurring.line'
    _inherit = 'welfare.recurring.line'

    advance_donation_id = fields.Many2one(
        'advance.donation',
        string="Advance Donation",
        ondelete='set null'
    )
    
    advance_donation_line_id = fields.Many2one(
        'advance.donation.lines',
        string="Advance Donation",
        ondelete='set null'
    )
    advance_donation_amount = fields.Float(
        string="Advance Donation Amount",
        help="Amount from the advance donation line that is allocated to this recurring line"
    )
    
    # def action_disbursed(self):
    #     """When disbursing, mark the linked donation line as reserved"""
    #     if self.advance_donation_line_id:
    #         self.advance_donation_line_id.write({'is_disbursed': True})
    #     return super(WelfareRecurringLineSync, self).action_disburse()
    
    def action_select_advance_donation(self):
        return {
            'name': _('Select Advance Donation'),
            'type': 'ir.actions.act_window',
            'res_model': 'advance.donation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_welfare_line_id': False,
                'default_recurring_line_id': self.id,
                'default_microfinance_id': False,
                'default_product_id': self.product_id.id if self.product_id else False,
            }
        }
