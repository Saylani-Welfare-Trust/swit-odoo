from odoo import models, fields


class SubZone(models.Model):
    _name = 'sub.zone'
    _description = "Sub Zone"


    name = fields.Char('Name')

    analytic_account_id = fields.Many2one('account.analytic.account', string="Zone")

    analytic_account_ids = fields.Many2many('account.analytic.account', string="Branchs")