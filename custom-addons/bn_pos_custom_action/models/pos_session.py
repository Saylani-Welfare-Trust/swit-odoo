from odoo import models, fields, api


class PosSession(models.Model):
    _inherit = 'pos.session'

    analytic_account_id = fields.Many2one(
        'account.analytic.account', string="Analytic Account",
        compute="_set_employee_branch", store=True, tracking=True)

    def _loader_params_res_company(self):
        # OVERRIDE to load the fields in pos data (load_pos_data)
        vals = super()._loader_params_res_company()
        vals['search_params']['fields'] += [
            'donation_box_product', 'donation_home_service_product',
            'microfinance_intallement_product', 'microfinance_security_depsoit_product',
            'medical_equipment_security_depsoit_product', 'welfare_product',
        ]
        return vals

    def _loader_params_res_partner(self):
        vals = super()._loader_params_res_partner()
        vals["search_params"]["fields"] += ["categories", "cnic_no"]
        return vals

    def _loader_params_res_users(self):
        vals = super()._loader_params_res_users()
        vals["search_params"]["fields"] += ["branch_code", "branch_name"]
        return vals

    @api.depends('user_id')
    def _set_employee_branch(self):
        for rec in self:
            rec.analytic_account_id = (
                rec.user_id.employee_id.analytic_account_id.id if rec.user_id else False
            )
