from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class MicrofinanceSync(models.Model):
    _inherit = 'microfinance'
    
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
                'default_welfare_line_id': False,
                'default_recurring_line_id': False,
                'default_microfinance_id': self.id,
                'default_product_id': self.product_id.id if self.product_id else False,
            }
        }