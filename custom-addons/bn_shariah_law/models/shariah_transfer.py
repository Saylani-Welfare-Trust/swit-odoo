from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ShariahTransfer(models.Model):
    _name = 'shariah.transfer'
    _description = 'Shariah Fund Transfer'
    _order = 'date desc, id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', default=lambda self: _('New'), required=True, copy=False)
    date = fields.Date(string='Transfer Date', required=True, default=fields.Date.context_today)
    source_analytic_account_id = fields.Many2one('account.analytic.account', string='Source Account', required=True)
    destination_analytic_account_id = fields.Many2one('account.analytic.account', string='Destination Account', required=True)
    amount = fields.Monetary(string='Amount', currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    note = fields.Text(string='Notes')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
    ], string='Status', default='draft', tracking=True)

    member_posted = fields.Boolean(string='Member Posted', default=False, tracking=True)

    def action_post(self):
        """Post the transfer: update daily balances."""
        for rec in self:
            if rec.state == 'posted':
                continue
            if rec.destination_analytic_account_id.member_approval and not rec.member_posted:
                raise UserError(_('Need member approval first.'))

            today = rec.date
            # Source: transfer_out
            daily_source = self.env['shariah.daily.balance'].search([
                ('analytic_account_id', '=', rec.source_analytic_account_id.id),
                ('date', '=', today)
            ], limit=1)
            if daily_source:
                daily_source.write({'transfer_out': daily_source.transfer_out + rec.amount})
            else:
                self.env['shariah.daily.balance'].create({
                    'analytic_account_id': rec.source_analytic_account_id.id,
                    'date': today,
                    'transfer_out': rec.amount,
                })
            # Destination: transfer_in
            daily_dest = self.env['shariah.daily.balance'].search([
                ('analytic_account_id', '=', rec.destination_analytic_account_id.id),
                ('date', '=', today)
            ], limit=1)
            if daily_dest:
                daily_dest.write({'transfer_in': daily_dest.transfer_in + rec.amount})
            else:
                self.env['shariah.daily.balance'].create({
                    'analytic_account_id': rec.destination_analytic_account_id.id,
                    'date': today,
                    'transfer_in': rec.amount,
                })
            # Recompute balances
            daily_source._compute_balances()
            daily_dest._compute_balances()
            rec.state = 'posted'

    def action_member_post(self):
        """Post the transfer: update daily balances."""
        for rec in self:
            rec.member_posted = True

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('shariah.transfer') or _('New')
        return super().create(vals)