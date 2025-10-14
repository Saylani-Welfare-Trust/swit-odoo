from odoo import api, fields, models, _
from odoo.exceptions import UserError


status_selection = [
    ('draft', 'Draft'),
    ('validate', 'Validate'),
    ('box_validate', 'Box Validate'),
    ('journal_entries', 'Journal Entries'),
    ('cancel', 'Cancelled')
]

class AmountCurrencyBoxModel(models.Model):
    _name = 'amount.currency.box'
    _description = 'Amount Currency Box Model'
    _rec_name = 'name'

    def debit_account_default(self):
        ir_model = self.env['ir.model'].sudo().search([('model', 'ilike', 'amount.currency.box')], limit=1)
        if ir_model:
            account_config_settings = self.env['account.config.settings'].sudo().search([('model_id', 'ilike', ir_model[0].id)], limit=1)
            if account_config_settings:
                return account_config_settings[0].debit_account_id.id
            else:
                return None
        else:
            return None

    def credit_account_default(self):
        ir_model = self.env['ir.model'].sudo().search([('model', 'ilike', 'amount.currency.box')], limit=1)
        if ir_model:
            account_config_settings = self.env['account.config.settings'].sudo().search([('model_id', 'ilike', ir_model[0].id)], limit=1)
            if account_config_settings:
                return account_config_settings[0].credit_account_id.id
            else:
                return None
        else:
            return None

    def journal_default(self):
        ir_model = self.env['ir.model'].sudo().search([('model', 'ilike', 'amount.currency.box')], limit=1)
        if ir_model:
            account_config_settings = self.env['account.config.settings'].sudo().search([('model_id', 'ilike', ir_model[0].id)], limit=1)
            if account_config_settings:
                return account_config_settings[0].journal_id.id
            else:
                return None
        else:
            return None

    type = fields.Selection(selection=[('big_iron_box', 'Big Iron Box'),('public_donation_box', 'Public Donation Box'),('crystal_standing_box', 'Crystal Standing Box')], string='Type', required=True)
    location_partner_id = fields.Many2one(comodel_name='res.partner', string='Location Name', required=True, domain="[('is_donee', '=', False),('state', '=', 'register')]")
    partner_id = fields.Many2one(comodel_name='res.partner', string='Ride Name', required=True, domain="[('is_rider', '=', True),('state', '=', 'register')]")
    box_count = fields.Float(string='Total Number of Box', required=True, default='1.0')
    state = fields.Selection(selection=status_selection, string='Status', default='draft')
    amount_currency_box_lines = fields.One2many(comodel_name='amount.currency.box.lines', inverse_name='amount_currency_box_id', string='Amount Currency Box Lines')
    amount_currency_fake_notes = fields.One2many(comodel_name='amount.currency.fake.notes', inverse_name='amount_currency_box_id', string='Amount Currency Fake Notes')
    company_id = fields.Many2one(comodel_name='res.company', string='Company', default=lambda self: self.env.company)
    debit_account_id = fields.Many2one(comodel_name='account.account', string='Account (Dr)', required=True, domain="[('account_type', 'in', ['asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current', 'asset_prepayments', 'asset_fixed'])]", default=lambda self: self.debit_account_default())
    credit_account_id = fields.Many2one(comodel_name='account.account', string='Account (Cr)', required=True, domain="[('account_type', 'in', ['income', 'income_other'])]", default=lambda self: self.credit_account_default())
    journal_id = fields.Many2one(comodel_name='account.journal', string='Journal', required=True, domain="[('type', 'in', ['sale'])]", default=lambda self: self.journal_default())
    accounting_date = fields.Date(string='Accounting Date', required=True, default=fields.Date.today())
    name = fields.Char(string="Reference", default=lambda self: _('New'))
    account_move_id = fields.Many2one(comodel_name='account.move', string='Account Move')
    deposit_id = fields.Many2one(comodel_name='amount.currency.deposit', string='Deposit')
    amount = fields.Float(string='Amount', compute='compute_amount', readonly=True, store=True)
    fake_notes_amount = fields.Float(string='Fake Notes Amount', compute='compute_fake_notes_amount', readonly=True, store=True)

    @api.constrains('amount_currency_box_lines', 'amount_currency_box_lines.amount_type_id')
    def _check_unique_amount_type(self):
        for record in self:
            amount_currency_lines = []
            for lines in record.amount_currency_box_lines:
                amount_currency_lines.append(lines.amount_type_id.id)
            if len(amount_currency_lines) != 0:
                duplicates = [item for item in set(amount_currency_lines) if amount_currency_lines.count(item) > 1]
                if duplicates:
                    amount_type = self.env['amount.type'].sudo().search([('id', 'in', duplicates)])
                    raise UserError(f"The following values are duplicated: {', '.join(map(str, amount_type.mapped('name')))}")

    @api.constrains('partner_id')
    def compute_partner_id(self):
        for record in self:
            if record.name == 'New':
                record.name = self.env['ir.sequence'].next_by_code('amount.currency.box.sequence')

    @api.constrains('account_move_id')
    @api.onchange('account_move_id')
    def compute_amount(self):
        for record in self:
            rupee_another = []
            for lines in record.amount_currency_box_lines:
                if lines.currency_id.name != 'PKR':
                    res_currency_rate = self.env['res.currency.rate'].sudo().search([('currency_id', '=', lines.currency_id.id)])
                    if res_currency_rate:
                        rate_amount = round(res_currency_rate[0].inverse_company_rate, 2)
                    else:
                        raise UserError(f"Currency rate not found for currency: {lines.currency_id.name}")
                else:
                    rate_amount = 1
                convent_amount = (float(rate_amount) * float(lines.amount_type_id.name))
                price = (float(convent_amount) * float(lines.quantity))
                rupee_another.append(round(price, 2))
            real_amount = round(sum(rupee_another), 2)
            record.amount = real_amount

    @api.constrains('account_move_id')
    @api.onchange('account_move_id')
    def compute_fake_notes_amount(self):
        for record in self:
            rupee_another = []
            for lines in record.amount_currency_fake_notes:
                if lines.currency_id.name != 'PKR':
                    res_currency_rate = self.env['res.currency.rate'].sudo().search([('currency_id', '=', lines.currency_id.id)])
                    if res_currency_rate:
                        rate_amount = round(res_currency_rate[0].inverse_company_rate, 2)
                    else:
                        raise UserError(f"Currency rate not found for currency: {lines.currency_id.name}")
                else:
                    rate_amount = 1
                convent_amount = (float(rate_amount) * float(lines.amount_type_id.name))
                price = (float(convent_amount) * float(lines.quantity))
                rupee_another.append(round(price, 2))
            real_amount = round(sum(rupee_another), 2)
            record.fake_notes_amount = real_amount

    def name_get(self):
        result = []
        for record in self:
            name = f'{record.partner_id.name}'
            result.append((record.id, name))
        return result

    def unlink(self):
        for record in self:
            if record.state != 'cancel':
                raise UserError("You cannot delete a record that is in the 'Cancelled' state.")
        return super(AmountCurrencyBoxModel, self).unlink()

    def action_validate(self):
        for record in self:
            if not record.debit_account_id:
                raise UserError(_("Create 'Cash In Hand' record Account (Dr) Field Chart of Account"))
            if not record.credit_account_id:
                raise UserError(_("Create 'Income from Donation Box' record Account (Cr) Field Chart of Account"))
            if not record.journal_id:
                raise UserError(_("Create 'Income from Donation Box' record Chart of Account"))
            if not self.env.company.currency_id:
                raise UserError("Company currency must be set before proceeding.")
            amount_type = self.env['amount.type'].sudo().search([('currency_id', '=', self.env.company.currency_id.id)])
            if amount_type:
                for line in amount_type:
                    amount_currency_box_lines = self.env['amount.currency.box.lines'].sudo().search([('currency_id', '=', line.currency_id.id), ('amount_type_id', '=', line.id), ('amount_currency_box_id', '=', record.id)])
                    if not amount_currency_box_lines:
                        amount_currency_box_lines_id = self.env['amount.currency.box.lines'].sudo().create({
                            'currency_id': line.currency_id.id,
                            'amount_type_id': line.id,
                            'quantity': 0.0,
                            'amount_currency_box_id': record.id,
                        })
                    else:
                        amount_currency_box_lines.write({
                            'quantity': 0.0,
                        })
                    amount_currency_fake_notes = self.env['amount.currency.fake.notes'].sudo().search([('currency_id', '=', line.currency_id.id), ('amount_type_id', '=', line.id),('amount_currency_box_id', '=', record.id)])
                    if not amount_currency_fake_notes:
                        amount_currency_fake_notes_id = self.env['amount.currency.fake.notes'].sudo().create({
                            'currency_id': line.currency_id.id,
                            'amount_type_id': line.id,
                            'quantity': 0.0,
                            'amount_currency_box_id': record.id,
                        })
                    else:
                        amount_currency_fake_notes.write({
                            'quantity': 0.0,
                        })
            record.write({
                'state': 'validate',
            })

    def action_box_validate(self):
        for record in self:
            if not record.amount_currency_box_lines:
                raise UserError("No amount currency box lines to process.")
            rupee_another = []
            for lines in record.amount_currency_box_lines:
                if lines.currency_id.name != 'PKR':
                    res_currency_rate = self.env['res.currency.rate'].sudo().search(
                        [('currency_id', '=', lines.currency_id.id)])
                    if res_currency_rate:
                        rate_amount = round(res_currency_rate[0].inverse_company_rate, 2)
                    else:
                        raise UserError(f"Currency rate not found for currency: {lines.currency_id.name}")
                else:
                    rate_amount = 1
                convent_amount = (float(rate_amount) * float(lines.amount_type_id.name))
                price = (float(convent_amount) * float(lines.quantity))
                rupee_another.append(round(price, 2))
            real_amount = round(sum(rupee_another), 2)
            if real_amount == 0:
                raise UserError("The calculated real amount cannot be zero. Please check the currency conversion rates or input data.")
            record.write({
                'state': 'box_validate',
            })

    def action_journal_entries(self):
        for record in self:
            rupee_another = []
            for lines in record.amount_currency_box_lines:
                if lines.currency_id.name != 'PKR':
                    res_currency_rate = self.env['res.currency.rate'].sudo().search([('currency_id', '=', lines.currency_id.id)])
                    if res_currency_rate:
                        rate_amount = round(res_currency_rate[0].inverse_company_rate, 2)
                    else:
                        raise UserError(f"Currency rate not found for currency: {lines.currency_id.name}")
                else:
                    rate_amount = 1
                convent_amount = (float(rate_amount) * float(lines.amount_type_id.name))
                price = (float(convent_amount) * float(lines.quantity))
                rupee_another.append(round(price, 2))
            real_amount = round(sum(rupee_another), 2)
            if real_amount == 0:
                raise UserError("The calculated real amount cannot be zero. Please check the currency conversion rates or input data.")
            account_move = self.env['account.move'].sudo().create({
                'ref': record.name,
                'partner_id': record.partner_id.id,
                'date': record.accounting_date,
                'journal_id': record.journal_id.id,
            })
            if account_move:
                account_move_lines = [
                    {
                        'account_id': record.debit_account_id.id,
                        'partner_id': record.partner_id.id,
                        'journal_id': record.journal_id.id,
                        'name': 'Donation Box',
                        'debit': real_amount,
                        'credit': 0.0,
                        'move_id': account_move.id,
                    },
                    {
                        'account_id': record.credit_account_id.id,
                        'partner_id': record.partner_id.id,
                        'journal_id': record.journal_id.id,
                        'name': 'Donation Box',
                        'debit': 0.0,
                        'credit': real_amount,
                        'move_id': account_move.id,
                    }
                ]
                self.env['account.move.line'].sudo().create(account_move_lines)
                account_move.action_post()
                record.write({
                    'account_move_id': account_move.id,
                    'state': 'journal_entries',
                })

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

    def action_bundle_journal_entries(self):
        deposit_id = []
        amount = 0.0
        for record in self:
            if not record.deposit_id:
                deposit_id.append(record.id)
                amount += record.amount
        if not deposit_id:
            raise UserError("No journal entries selected to bundle.")
        amount_currency_wizard_unlink = self.env['amount.currency.wizard'].sudo().search([('amount_currency_box_id', 'in', deposit_id)])
        for line in amount_currency_wizard_unlink:
            line.unlink()
        amount_currency_wizard_search = self.env['amount.currency.wizard'].sudo().search([('amount_currency_box_id', 'in', deposit_id)])
        if not amount_currency_wizard_search:
            amount_currency_wizard = self.env['amount.currency.wizard'].create({
                'amount_currency_box_id': [(6, 0, deposit_id)],
                'amount': amount,
            })
            wizard_id = amount_currency_wizard.id
        else:
            amount_currency_wizard_search.write({
                'amount_currency_box_id': [(6, 0, deposit_id)],
                'amount': amount,
            })
            wizard_id = amount_currency_wizard_search.id
        return {
            'name': "Deposit",
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'amount.currency.wizard',
            'view_id': self.env.ref('sm_point_of_sale_apps.amount_currency_wizard_view_form').id,
            'res_id': wizard_id,
            'target': 'new',
        }

