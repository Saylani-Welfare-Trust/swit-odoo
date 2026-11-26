from odoo import api, models, fields, _
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

    @api.depends('advance_donation_line_id.date', 'advance_donation_id.create_date')
    def _compute_order_date(self):
        return super()._compute_order_date()

    def _order_date(self):
        """A line funded by an advance donation: the date of its contract line (a
        frequency contract: the day of that line), else the day the contract was made."""
        date = super()._order_date()
        donation = self.sudo().advance_donation_id
        if not date and donation:
            date = self.sudo().advance_donation_line_id.date or (
                fields.Date.context_today(self, donation.create_date) if donation.create_date else False)
        return date

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