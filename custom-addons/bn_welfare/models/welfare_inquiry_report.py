from odoo import models, fields, api
from datetime import datetime

class WelfareInquiryReport(models.Model):
    _name = 'welfare.inquiry.report'
    _description = 'Inquiry Report'
    _order = 'create_date desc'
    
    welfare_id = fields.Many2one('welfare', string='Welfare Application', required=True, ondelete='cascade')
    
    status = fields.Char(string='Status')
    images = fields.Text(string='Image URLs')
    verified = fields.Boolean(string='Verified')
    
    officer_id = fields.Many2one('hr.employee', string='Officer')
    officer_name = fields.Char(string='Officer Name')
    officer_email = fields.Char(string='Officer Email')
    
    content = fields.Text(string='Report Content')
    external_id = fields.Char(string='External ID')
    create_date = fields.Datetime(string='Created At')
    write_date = fields.Datetime(string='Updated At')