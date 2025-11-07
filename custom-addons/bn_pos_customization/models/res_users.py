from odoo import models, fields


class ResUser(models.Model):
    _inherit = 'res.users'


    branch_code = fields.Char(related='employee_id.analytic_account_id.code', string="Branch Code", store=True)