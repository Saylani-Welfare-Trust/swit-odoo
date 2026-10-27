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
    
    def action_disbursed(self):
        res = super().action_disbursed()
        for line in self.filtered('advance_donation_line_id'):
            line.advance_donation_line_id.sudo()._register_disbursement(
                line.advance_donation_amount, line.total_amount,
                welfare=line.welfare_id, welfare_line=line, record_name=line.welfare_id.name or '')
        return res

    def unlink(self):
        # a line that holds part of an advance donation must give it back first
        linked = self.filtered('advance_donation_line_id')
        if linked:
            raise UserError(_('Welfare lines linked to an advance donation cannot be deleted (%s).')
                            % ', '.join(linked.mapped(lambda l: l.display_name or str(l.id))))
        return super().unlink()
