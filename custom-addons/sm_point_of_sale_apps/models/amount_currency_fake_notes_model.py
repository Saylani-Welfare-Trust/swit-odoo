from odoo import api, fields, models, _


class AmountCurrencyBoxFakeNotesModel(models.Model):
    _name = 'amount.currency.fake.notes'
    _description = 'Amount Currency Fake Notes Model'
    _rec_name = 'amount_type_id'

    currency_id = fields.Many2one(comodel_name='res.currency', string='Currency', required=True, domain="[('active', '=', True)]")
    amount_type_id = fields.Many2one(comodel_name='amount.type', string='Amount Type', required=True, domain="[('currency_id', '=', currency_id)]")
    quantity = fields.Float(string='Quantity', required=True)
    amount_currency_box_id = fields.Many2one(comodel_name='amount.currency.box', string='Amount Currency Box', required=True)
    company_id = fields.Many2one(comodel_name='res.company', string='Company', default=lambda self: self.env.company)
    name = fields.Char(string="Reference", default=lambda self: _('New'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('amount.currency.fake.notes.sequence')
        return super(AmountCurrencyBoxFakeNotesModel, self).create(vals_list)

    def name_get(self):
        result = []
        for record in self:
            name = f'{record.amount_type_id.name}'
            result.append((record.id, name))
        return result

