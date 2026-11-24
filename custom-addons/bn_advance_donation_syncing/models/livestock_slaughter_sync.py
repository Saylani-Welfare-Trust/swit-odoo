from odoo import models, fields, _
import logging

_logger = logging.getLogger(__name__)


class LivestockSlaughterSync(models.Model):
    """Extend livestock.slaugther with advance donation integration."""
    _inherit = 'livestock.slaugther'

    advance_donation_id = fields.Many2one(
        'advance.donation',
        string="Advance Donation",
        ondelete='set null',
        copy=False,
    )
    advance_donation_line_id = fields.Many2one(
        'advance.donation.lines',
        string='Advance Donation Line',
        ondelete='set null',
        copy=False,
    )
    advance_donation_amount = fields.Float(
        string="Advance Donation Amount",
        help="Amount from the advance donation line allocated to this slaughter",
    )

    def action_confirm(self):
        """Slaughtered: the advance donation line funding the animal is disbursed
        (fully once all the animals of the line are slaughtered)."""
        self.ensure_one()
        was_draft = self.state == 'not_received'
        res = super().action_confirm()
        if was_draft and self.state != 'not_received' and self.advance_donation_line_id:
            self.advance_donation_line_id.sudo()._register_disbursement(
                self.advance_donation_amount, self.price, record_name=self.name)
        return res

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
                'default_microfinance_id': False,
                'default_livestock_slaughter_id': self.id,
                'default_product_id': self.product_id.id if self.product_id else False,
            }
        }