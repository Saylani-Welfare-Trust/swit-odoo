from odoo import models, fields


class SadqaJariyaInquiryReport(models.Model):
    """Completed inquiry of the assigned officer, from the portal's completed-inquiry export"""
    _name = 'sadqa.jariya.inquiry.report'
    _description = 'Inquiry Report'
    _order = 'report_date desc, id desc'

    application_id = fields.Many2one('sadqa.jariya', string='Application', required=True, ondelete='cascade')
    external_id = fields.Char(string='Portal Report ID')
    status = fields.Char(string='Status')
    content = fields.Text(string='Officer Remarks')
    officer_id = fields.Many2one('hr.employee', string='Officer')
    officer_name = fields.Char(string='Officer Name')
    officer_employee_code = fields.Char(string='Officer Employee ID')
    # completedAt on the portal, create_date is when Odoo imported it
    report_date = fields.Datetime(string='Completed At')
