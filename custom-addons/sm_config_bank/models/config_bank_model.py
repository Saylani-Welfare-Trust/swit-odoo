from odoo import api, fields, models, _


type_selection = [
    ('gateway', 'Gateway'),
    ('category', 'Category'),
    ('api', 'API'),
]


class ConfigBankModel(models.Model):
    _name = 'config.bank'
    _description = 'Config Bank Model'
    _rec_name = 'name'

    name = fields.Char(string="Bank Name", required=True)
    bic = fields.Char(string="Bank Identifier Code")
    street = fields.Text(string="Bank Address")
    city = fields.Char(string="City")
    state_id = fields.Many2one(comodel_name='res.country.state', string='State', domain="[('country_id', '=', country_id)]")
    zip = fields.Char(string="Zip")
    country_id = fields.Many2one(comodel_name='res.country',string='Country')
    phone = fields.Char(string="Phone")
    email = fields.Char(string="Email")

    type = fields.Selection(selection=type_selection, string="Type")

    account_id = fields.Many2one('account.account', string="Account ID")

    config_bank_line_ids = fields.One2many('config.bank.line', 'config_bank_id', string="Config Bank Line IDs")
    currency_debit_ids = fields.One2many('currency.debit', 'config_bank_id', string="Currency Debit Line IDs")
    config_bank_header_ids = fields.One2many('config.bank.header', 'config_bank_id', string="Config Bank Header IDs")

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The Bank Name must be unique!')
    ]

    def name_get(self):
        result = []
        for record in self:
            name = f'{record.product_id.name}'
            result.append((record.id, name))
        return result

