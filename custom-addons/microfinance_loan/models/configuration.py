
from odoo import fields, api, models, _
from odoo.exceptions import UserError


class MfdBank(models.Model):
    _name = 'mfd.bank'

    name = fields.Char(string='Name')
    is_active = fields.Boolean(string='Active')


class MfdRecoveryDaysConf(models.Model):
    _name = 'mfd.recovery.conf'

    installment_type = fields.Char(string='Installment Type')
    days = fields.Integer(string='Recovery Days', default=0)

    @api.onchange('days')
    def onchange_days(self):
        for rec in self:
            if rec.days < 0:
                raise UserError('Recovery days cannot be negative')


class MfdAccountConfiguration(models.Model):
    _name = 'mfd.account.configuration'
    _order = 'create_date asc'

    name = fields.Char(string='Name')
    account_id = fields.Many2one('account.account', 'Chart of Account')
    account_type = fields.Selection([
        ('loan_conf_asset', 'Loan Configuration (Movable Asset)'),
        ('loan_conf_cash', 'Loan Configuration (Cash)'),
        ('payment_conf_cash', 'Payment Configuration (Cash)'),
        ('deposit_conf_cheque', 'Deposit Configuration (Cheque)'),
        ('payment_conf_cheque', 'Payment Configuration (Cheque)')
    ])

    # @api.ondelete(at_uninstall=False)
    # def restrict_delete(self):
    #     for rec in self:
    #         if rec.name in ['Loan Credit Account', 'Loan Debit Account',
    #                         'Cash Credit Account', 'Cash Debit Account',
    #                         'Cheque Credit Account', 'Cheque Debit Account',
    #                         'Cheque Bounced Credit Account', 'Cheque Bounced Debit Account']:
    #             raise UserError('You cannot delete this record')

class MfdScheme(models.Model):
    _name = 'mfd.scheme'

    name = fields.Char(string='Name')
    prefix = fields.Char(string='Prefix')
    is_created = fields.Boolean()
    installment_type = fields.Selection([('daily', 'Daily'), ('monthly', 'Monthly')], string='Installment Type', default='daily')
    daily_recovery_days = fields.Integer(string='Recovery Days', default=30)
    monthly_recovery_days = fields.Integer(string='Recovery Days', default=30)
    application_lines = fields.One2many('mfd.scheme.line', 'scheme_id')

    @api.model
    def create(self, vals):
        # vals['is_created'] = True
        record = super().create(vals)
        self.env['ir.sequence'].create({
            'name': f"{record.name} Sequence",
            'code': f"mfd.loan.request.{record.id}",
            'padding': 7,
            'prefix': record.prefix,
        })
        return record

    def write(self, vals):
        record = super().write(vals)
        seq_record = self.env['ir.sequence'].search([
            ('code', '=', f"mfd.loan.request.{self.id}")
        ])
        seq_record.write({'prefix': self.prefix})
        return record

class MfdSchemeLine(models.Model):
    _name = 'mfd.scheme.line'

    name = fields.Char(string='Application for Name')
    asset_type = fields.Selection([('cash', 'Cash'), ('movable_asset', 'Movable Asset'), ('immovable_asset', 'Immovable Asset')], string='Asset Type', default='cash')
    scheme_id = fields.Many2one('mfd.scheme')

    product_lines = fields.One2many('loan.product.line', 'application_id', string='New Product')  # New field


class LoanProductLine(models.Model):
    _name = 'loan.product.line'

    product_id = fields.Many2one('product.product', string='Product')
    price = fields.Float('Ins. Amount')
    sd_amount = fields.Float('SD Amount')
    recover_product_id = fields.Many2many('product.product', string='Recover Product')
    is_recover_product = fields.Boolean('Is Recover Product?')
    application_id = fields.Many2one('mfd.scheme.line', string='Application for')
    application_name = fields.Char(related='application_id.name', string='Application Name')







