from odoo import fields, models


class ConfigBankLine(models.Model):
    _name = 'config.bank.line'
    _description = "Config Bank Line"


    name = fields.Char('Product Name')

    product_id = fields.Many2one('product.product', string="Product ID")
    config_bank_id = fields.Many2one('config.bank', string="Config Bank ID")
    analytic_plan_id = fields.Many2one('account.analytic.plan', string="Analytic Plan ID")
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account ID")
    account_id = fields.Many2one('account.account', string="Analytic Account ID")
    
    sub_analytic_plan_ids = fields.Many2many('account.analytic.plan', string="Sub Analytic Plan ID")