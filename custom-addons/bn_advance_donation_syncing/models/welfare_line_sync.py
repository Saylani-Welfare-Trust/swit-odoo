from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class WelfareLineSync(models.Model):
    """Extend welfare line with advance donation integration"""
    _name = 'welfare.line'
    _inherit = 'welfare.line'

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
    


    def action_select_advance_donation(self):
        return {
            'name': _('Select Advance Donation'),
            'type': 'ir.actions.act_window',
            'res_model': 'advance.donation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_welfare_line_id': self.id,
                'default_recurring_line_id': False,
                'default_microfinance_id': False,
                'default_product_id': self.product_id.id if self.product_id else False,
            }
        }

    # def action_disbursed(self):
    #     """When disbursing, mark the linked donation line as reserved"""

    #     return super(WelfareLineSync, self).action_disburse()
    
    def unlink(self):
        # For each welfare line being deleted, unlink the associated donation line's reserved status
        for record in self:
            if record.advance_donation_line_id and record.advance_donation_line_id.is_reserved:
                record.advance_donation_line_id.write({'is_reserved': False})
        return super(WelfareLineSync, self).unlink()