from odoo import fields, models, exceptions

class FundUtilization(models.Model):
    _name = 'fund.utilization'
    _inherit = ['mail.thread']


    name = fields.Char('Fund Name', required=True, tracking=True)

    for_credit = fields.Many2one('account.account', string='For Credit', required=True, tracking=True)
    for_debit = fields.Many2one('account.account', string='For Debit', required=True, tracking=True)
    