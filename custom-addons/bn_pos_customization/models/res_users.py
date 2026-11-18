from odoo import models, fields


class ResUser(models.Model):
    _inherit = 'res.users'


    # the cashier's branch: the POS falls back to it when the shop has no Branch
    branch_code = fields.Char(related='employee_id.analytic_account_id.code', string="Branch Code")
    branch_name = fields.Char(related='employee_id.analytic_account_id.name', string="Branch Name")