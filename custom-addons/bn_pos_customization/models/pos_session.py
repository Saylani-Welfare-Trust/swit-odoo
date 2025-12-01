from odoo import models, fields, api


class POSSession(models.Model):
    _inherit = 'pos.session'


    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", compute="_set_employee_branch", store=True)
    

    def _loader_params_res_partner(self):
        vals = super()._loader_params_res_partner()
        
        vals["search_params"]["fields"] += ["categories"]
        return vals
    
    def _loader_params_res_users(self):
        vals = super()._loader_params_res_users()
        
        vals["search_params"]["fields"] += ["branch_code"]
        return vals
    
    @api.depends('user_id')
    def _set_employee_branch(self):
        for rec in self:
            if rec.user_id:
                rec.analytic_account_id = rec.user_id.employee_id.analytic_account_id.id or None