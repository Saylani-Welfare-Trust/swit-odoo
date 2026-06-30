from odoo import api, fields, models, _
from odoo.exceptions import UserError

class TransferWizard(models.TransientModel):
    _name = 'shariah.transfer.wizard'
    _description = 'Transfer Funds Wizard'

    source_analytic_account_id = fields.Many2one('account.analytic.account', string='Source Account', required=True)
    destination_analytic_account_id = fields.Many2one('account.analytic.account', string='Destination Account', required=True)
    amount = fields.Monetary(string='Amount', currency_field='currency_id', required=True)
    date = fields.Date(string='Transfer Date', required=True, default=fields.Date.context_today)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    note = fields.Text(string='Notes')

    def action_create_transfer(self):
        """Create and post the transfer."""
        self.ensure_one()
        if self.source_analytic_account_id == self.destination_analytic_account_id:
            raise UserError(_('Source and destination accounts must be different.'))

        transfer = self.env['shariah.transfer'].create({
            'date': self.date,
            'source_analytic_account_id': self.source_analytic_account_id.id,
            'destination_analytic_account_id': self.destination_analytic_account_id.id,
            'amount': self.amount,
            'note': self.note,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'shariah.transfer',
            'res_id': transfer.id,
            'view_mode': 'form',
            'target': 'current',
        }