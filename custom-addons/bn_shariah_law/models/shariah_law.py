from odoo import models, fields


class ShariahLaw(models.Model):
    _name = 'shariah.law'
    _description = "Shariah Law"


    parent_id = fields.Many2one('account.analytic.account', string="Parent Analytic Account")
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)

    inflow_restricted_amount = fields.Monetary('Inflow (Restricted)', currency_field='currency_id', default=0)
    inflow_unrestricted_amount = fields.Monetary('Inflow (Unrestricted)', currency_field='currency_id', default=0)
    
    purchase_amount = fields.Monetary('Purchase', currency_field='currency_id', default=0)
    
    welfare_individual_amount = fields.Monetary('Welfare (Individual)', currency_field='currency_id', default=0)
    welfare_portal_amount = fields.Monetary('Welfare (Portal)', currency_field='currency_id', default=0)
    
    expense_amount = fields.Monetary('Expense', currency_field='currency_id', default=0)
    

    def action_transfer_to(self):
        pass
    
    def action_transfer_from(self):
        pass