import json

from odoo import api, fields, models


class WelfareOfficerWizard(models.TransientModel):
    """Officer for Reopen Inquiry (a new report) or Change Inquiry Officer (the open report), for one application
    (form) or several selected in the list"""
    _name = 'welfare.officer.wizard'
    _description = 'Welfare Inquiry Officer'

    welfare_ids = fields.Many2many('welfare', string='Applications', required=True, readonly=True)
    mode = fields.Selection([('reopen', 'Reopen Inquiry'), ('change', 'Change Inquiry Officer')], required=True, readonly=True)
    employee_domain = fields.Char(compute='_compute_employee_domain')
    employee_id = fields.Many2one('hr.employee', string='Inquiry Officer', required=True, domain="employee_domain")

    @api.depends('welfare_ids.employee_domain')
    def _compute_employee_domain(self):
        for wizard in self:
            domains = set(wizard.welfare_ids.mapped('employee_domain'))
            if len(domains) == 1:
                wizard.employee_domain = domains.pop()
            else:
                # donees in different areas: no officer covers all of them, list every inquiry officer
                categories = wizard.welfare_ids.employee_category_id
                wizard.employee_domain = json.dumps([('category_ids', 'in', categories.ids)] if categories else [])

    def action_confirm(self):
        self.ensure_one()
        if self.mode == 'reopen':
            return self.welfare_ids.action_reopen_inquiry(self.employee_id)
        return self.welfare_ids.action_change_inquiry_officer(self.employee_id)
