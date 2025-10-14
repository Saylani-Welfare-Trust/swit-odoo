from odoo import fields, models, api, _
from odoo.exceptions import UserError

status_selection = [
    ('draft', 'Draft'),
    ('done', 'Done'),
    ('cancel', 'Cancel'),
]


class AmountCurrencyDepositModel(models.Model):
    _name = 'amount.currency.deposit'
    _description = 'Amount Currency Deposit'
    _rec_name = 'name'

    def debit_account_default(self):
        ir_model = self.env['ir.model'].sudo().search([('model', 'ilike', 'amount.currency.deposit')], limit=1)
        if ir_model:
            account_config_settings = self.env['account.config.settings'].sudo().search([('model_id', 'ilike', ir_model[0].id)], limit=1)
            if account_config_settings:
                return account_config_settings[0].debit_account_id.id
            else:
                return None
        else:
            return None

    def credit_account_default(self):
        ir_model = self.env['ir.model'].sudo().search([('model', 'ilike', 'amount.currency.deposit')], limit=1)
        if ir_model:
            account_config_settings = self.env['account.config.settings'].sudo().search([('model_id', 'ilike', ir_model[0].id)], limit=1)
            if account_config_settings:
                return account_config_settings[0].credit_account_id.id
            else:
                return None
        else:
            return None

    def journal_default(self):
        ir_model = self.env['ir.model'].sudo().search([('model', 'ilike', 'amount.currency.deposit')], limit=1)
        if ir_model:
            account_config_settings = self.env['account.config.settings'].sudo().search([('model_id', 'ilike', ir_model[0].id)], limit=1)
            if account_config_settings:
                return account_config_settings[0].journal_id.id
            else:
                return None
        else:
            return None

    slip_number = fields.Char(string='Slip No', required=True)
    partner_id = fields.Many2one(comodel_name='res.partner', string='Partner Name', required=True)
    debit_account_id = fields.Many2one(comodel_name='account.account', string='Account (Dr)', domain="[('account_type', 'in', ['asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current', 'asset_prepayments', 'asset_fixed'])]", default=lambda self: self.debit_account_default(), required=True)
    credit_account_id = fields.Many2one(comodel_name='account.account', string='Account (Cr)', domain="[('account_type', 'in', ['asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current', 'asset_prepayments', 'asset_fixed'])]", default=lambda self: self.credit_account_default(), required=True)
    amount_currency_box_id = fields.Many2many(comodel_name='amount.currency.box', string='Amount Currency Box', required=True, domain="[('deposit_id', '=', False)]")
    journal_id = fields.Many2one(comodel_name='account.journal', string='Journal', required=True, domain="[('type', 'in', ['sale'])]", default=lambda self: self.journal_default())
    amount = fields.Float(string='Amount', required=True)
    name = fields.Char(string="Reference", default='New')
    state = fields.Selection(selection=status_selection, string='Status', default='draft')
    accounting_date = fields.Date(string='Accounting Date', required=True, default=fields.Date.today())
    account_move_id = fields.Many2one(comodel_name='account.move', string='Account Move')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('amount.currency.deposit.sequence')
        return super(AmountCurrencyDepositModel, self).create(vals_list)

    def name_get(self):
        result = []
        for record in self:
            name = f'{record.amount_type_id.name}'
            result.append((record.id, name))
        return result

    @api.onchange('amount_currency_box_id')
    def onchange_amount_currency_box_id(self):
        for record in self:
            amount = sum(lines.amount for lines in record.amount_currency_box_id)
            record.amount = amount

    def action_journal_entries_list(self):
        for record in self:
            return {
                'name': _('Journal Entries'),
                'view_mode': 'form',
                'view_id': self.env.ref('account.view_move_form').id,
                'res_model': 'account.move',
                'context': "{'move_type':'entry'}",
                'type': 'ir.actions.act_window',
                'res_id': record.account_move_id.id,
            }

    def action_done(self):
        for record in self:
            if not record.accounting_date:
                raise UserError(_("The field 'Accounting Date' is required. Please provide a date."))
            if not record.partner_id:
                raise UserError(_("The field 'Partner' is required. Please select a partner."))
            if not record.debit_account_id:
                raise UserError(_("The field 'Debit Account' is required. Please select a debit account."))
            if not record.credit_account_id:
                raise UserError(_("The field 'Credit Account' is required. Please select a credit account."))
            if not record.journal_id:
                raise UserError(_("Create 'Income from Donation Box' record Chart of Account"))
            box_lines = [
                {
                    'account_id': record.debit_account_id.id,
                    'partner_id': record.partner_id.id,
                    'journal_id': record.journal_id.id,
                    'name': 'Deposit',
                    'debit': record.amount,
                    'credit': 0.0,
                },
                {
                    'account_id': record.credit_account_id.id,
                    'partner_id': record.partner_id.id,
                    'journal_id': record.journal_id.id,
                    'name': 'Deposit',
                    'debit': 0.0,
                    'credit': record.amount,
                }
            ]
            box_lines_tuples = [(0, 0, line) for line in box_lines]
            vals = {
                'ref': record.name,
                'partner_id': record.partner_id.id,
                'date': record.accounting_date,
                'journal_id': record.journal_id.id,
                'line_ids': box_lines_tuples,
            }
            account_move = self.env['account.move'].sudo().create(vals)
            if account_move:
                account_move.action_post()
                for lines in record.amount_currency_box_id:
                    lines.write({
                        'deposit_id': record.id,
                    })
                record.write({
                    'account_move_id': account_move.id,
                })
            record.write({
                'state': 'done',
            })

    def action_cancel(self):
        for record in self:
            record.write({
                'state': 'cancel',
            })

    def action_draft(self):
        for record in self:
            record.write({
                'state': 'draft',
            })

