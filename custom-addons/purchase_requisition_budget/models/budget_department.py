from odoo import models, fields

class BudgetBudget(models.Model):
    _inherit = 'budget.budget'

    department_id = fields.Many2one('hr.department', string="Department", help="Department linked to this budget")
