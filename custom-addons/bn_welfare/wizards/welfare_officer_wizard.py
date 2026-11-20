from odoo import fields, models


class WelfareOfficerWizard(models.TransientModel):
    """Officer for Reopen Inquiry (a new report) or Change Inquiry Officer (the open report)"""
    _name = 'welfare.officer.wizard'
    _description = 'Welfare Inquiry Officer'

    welfare_id = fields.Many2one('welfare', string='Application', required=True, readonly=True)
    mode = fields.Selection([('reopen', 'Reopen Inquiry'), ('change', 'Change Inquiry Officer')], required=True, readonly=True)
    employee_domain = fields.Char(related='welfare_id.employee_domain')
    employee_id = fields.Many2one('hr.employee', string='Inquiry Officer', required=True, domain="employee_domain")

    def action_confirm(self):
        self.ensure_one()
        if self.mode == 'reopen':
            return self.welfare_id.action_reopen_inquiry(self.employee_id)
        return self.welfare_id.action_change_inquiry_officer(self.employee_id)
