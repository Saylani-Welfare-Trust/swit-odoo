from odoo import fields, models, api, _
from odoo.exceptions import UserError


class AmountCurrencyWizard(models.TransientModel):
    _name = 'amount.currency.wizard'
    _description = 'Amount Currency Wizard'

    def debit_account_default(self):
        ir_model = self.env['ir.model'].sudo().search([('model', 'ilike', 'amount.currency.deposit')], limit=1)
        if ir_model:
            account_config_settings = self.env['account.config.settings'].sudo().search(
                [('model_id', 'ilike', ir_model[0].id)], limit=1)
            if account_config_settings:
                return account_config_settings[0].debit_account_id.id
            else:
                return None
        else:
            return None

    def credit_account_default(self):
        ir_model = self.env['ir.model'].sudo().search([('model', 'ilike', 'amount.currency.deposit')], limit=1)
        if ir_model:
            account_config_settings = self.env['account.config.settings'].sudo().search(
                [('model_id', 'ilike', ir_model[0].id)], limit=1)
            if account_config_settings:
                return account_config_settings[0].credit_account_id.id
            else:
                return None
        else:
            return None

    def journal_default(self):
        ir_model = self.env['ir.model'].sudo().search([('model', 'ilike', 'amount.currency.deposit')], limit=1)
        if ir_model:
            account_config_settings = self.env['account.config.settings'].sudo().search(
                [('model_id', 'ilike', ir_model[0].id)], limit=1)
            if account_config_settings:
                return account_config_settings[0].journal_id.id
            else:
                return None
        else:
            return None

    slip_number = fields.Char(string='Slip No')
    partner_id = fields.Many2one(comodel_name='res.partner', string='Partner Name')
    debit_account_id = fields.Many2one(comodel_name='account.account', string='Account (Dr)',domain="[('account_type', 'in', ['asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current', 'asset_prepayments', 'asset_fixed'])]",default=lambda self: self.debit_account_default(), required=True)
    credit_account_id = fields.Many2one(comodel_name='account.account', string='Account (Cr)',domain="[('account_type', 'in', ['asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current', 'asset_prepayments', 'asset_fixed'])]",default=lambda self: self.credit_account_default(), required=True)
    amount_currency_box_id = fields.Many2many(comodel_name='amount.currency.box', string='Amount Currency Box',required=True)
    journal_id = fields.Many2one(comodel_name='account.journal', string='Journal', required=True,domain="[('type', 'in', ['sale'])]", default=lambda self: self.journal_default())
    amount = fields.Float(string='Amount', required=True)
    name = fields.Char(string="Reference", default=lambda self: _('New'))
    accounting_date = fields.Date(string='Accounting Date', required=True, default=fields.Date.today())


    def action_amount_currency_wizard(self):
        if not self.slip_number:
            raise UserError(_("The field 'Slip No' is required"))
        if not self.accounting_date:
            raise UserError(_("The field 'Accounting Date' is required. Please provide a date."))
        if not self.partner_id:
            raise UserError(_("The field 'Partner' is required. Please select a partner."))
        if not self.debit_account_id:
            raise UserError(_("The field 'Debit Account' is required. Please select a debit account."))
        if not self.credit_account_id:
            raise UserError(_("The field 'Credit Account' is required. Please select a credit account."))
        if not self.journal_id:
            raise UserError(_("Create 'Income from Donation Box' record Chart of Account"))
        if not self.amount_currency_box_id:
            raise UserError("No amount currency box to process.")
        amount = 0.0
        amount_currency_box_ids = []
        for record in self.amount_currency_box_id:
            amount_currency_box_ids.append(record.id)
            amount += record.amount
        vals = {
            'name': 'New',
            'saction_donelip_number': self.slip_number,
            'partner_id': self.partner_id.id,
            'accounting_date': self.accounting_date,
            'amount': amount,
            'debit_account_id': self.debit_account_id.id,
            'credit_account_id': self.credit_account_id.id,
            'journal_id': self.journal_id.id,
            'amount_currency_box_id': [(6, 0, amount_currency_box_ids)],
            'state': 'draft',
        }
        amount_currency_deposit = self.env['amount.currency.deposit'].sudo().create(vals)
        if amount_currency_deposit:
            amount_currency_deposit.action_done()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

