from odoo import fields, models


class SadqaJariyaOfficerWizard(models.TransientModel):
    """Officer for Reopen Inquiry (a new report) or Change Inquiry Officer (the open report)"""
    _name = 'sadqa.jariya.officer.wizard'
    _description = 'Sadqa e Jariya Inquiry Officer'

    application_id = fields.Many2one('sadqa.jariya', string='Application', required=True, readonly=True)
    mode = fields.Selection([('reopen', 'Reopen Inquiry'), ('change', 'Change Inquiry Officer')], required=True, readonly=True)
    employee_category_id = fields.Many2one(related='application_id.employee_category_id')
    employee_id = fields.Many2one('hr.employee', string='Inquiry Officer', required=True,
                                  domain="[('category_ids', 'in', [employee_category_id])]")

    def action_confirm(self):
        self.ensure_one()
        if self.mode == 'reopen':
            return self.application_id.action_reopen_inquiry(self.employee_id)
        return self.application_id.action_change_inquiry_officer(self.employee_id)
