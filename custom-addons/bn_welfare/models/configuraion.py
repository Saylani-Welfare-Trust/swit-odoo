from odoo import fields, models, api

class MfdScheme(models.Model):
    _name = 'wlf.scheme'

    name = fields.Char(string='Name')
    prefix = fields.Char(string='Prefix')
    is_created = fields.Boolean()
    installment_type = fields.Selection([('daily', 'Daily'), ('monthly', 'Monthly')], string='Installment Type', default='daily')
    daily_recovery_days = fields.Integer(string='Recovery Days', default=30)
    monthly_recovery_days = fields.Integer(string='Recovery Days', default=30)
    application_lines = fields.One2many('wlf.scheme.line', 'scheme_id')

    @api.model
    def create(self, vals):
        # vals['is_created'] = True
        record = super().create(vals)
        self.env['ir.sequence'].create({
            'name': f"{record.name} Sequence",
            'code': f"wlf.loan.request.{record.id}",
            'padding': 7,
            'prefix': record.prefix,
        })
        return record

    def write(self, vals):
        record = super().write(vals)
        seq_record = self.env['ir.sequence'].search([
            ('code', '=', f"wlf.loan.request.{self.id}")
        ])
        seq_record.write({'prefix': self.prefix})
        return record

class MfdSchemeLine(models.Model):
    _name = 'wlf.scheme.line'

    name = fields.Char(string='Application for Name')
    asset_type = fields.Selection([('cash', 'Cash'), ('movable_asset', 'Movable Asset'), ('immovable_asset', 'Immovable Asset')], string='Asset Type', default='cash')
    scheme_id = fields.Many2one('wlf.scheme')

    product_lines = fields.One2many('wfloan.product.line', 'application_id', string='New Product')  # New field


class LoanProductLine(models.Model):
    _name = 'wfloan.product.line'

    product_id = fields.Many2one('product.product', string='Product')
    price = fields.Float('Ins. Amount')
    sd_amount = fields.Float('SD Amount')
    recover_product_id = fields.Many2many('product.product', string='Recover Product')
    is_recover_product = fields.Boolean('Is Recover Product?')
    application_id = fields.Many2one('wlf.scheme.line', string='Application for')
    application_name = fields.Char(related='application_id.name', string='Application Name')