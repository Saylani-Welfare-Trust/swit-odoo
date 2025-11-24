from odoo import models, fields


class ShariahLaw(models.Model):
    _name = 'shariah.law'
    _description = "Shariah Law"


    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)

    restricted_amount = fields.Monetary('Restricted Amount', currency_field='currency_id', default=0)
    unrestricted_amount = fields.Monetary('Unrestricted Amount', currency_field='currency_id', default=0)
    

    def action_transfer_to(self):
        pass
    
    def action_transfer_from(self):
        pass