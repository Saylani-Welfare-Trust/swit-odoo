from odoo import models, fields


class MaterialRequestLog(models.Model):
    _name = 'material.request.log'
    _description = 'Material Request Audit Trail'
    _order = 'date desc, id desc'

    request_id = fields.Many2one('material.request', required=True, ondelete='cascade', index=True)
    date = fields.Datetime('Date & Time', default=fields.Datetime.now, readonly=True)
    user_id = fields.Many2one('res.users', string='Performed By', readonly=True)
    stage = fields.Selection(lambda self: self.env['material.request']._fields['state'].selection, string='Stage', readonly=True)
    action = fields.Selection([
        ('submit', 'Submitted'),
        ('start_validation', 'Technical Validation Started'),
        ('validate', 'Technically Validated'),
        ('tech_hod_approve', 'Technical HOD Approved'),
        ('verify', 'Supply Chain Verified'),
        ('hold', 'Put On Hold (Fund Shortage)'),
        ('resume', 'Resumed'),
        ('committee', 'Sent to Committee Approval'),
        ('hod_approve', 'HOD Approved'),
        ('cfo_approve', 'CFO Approved'),
        ('coo_approve', 'COO Approved'),
        ('reject', 'Rejected'),
        ('reset', 'Reset to Draft'),
    ], string='Action', readonly=True)
    remarks = fields.Text('Remarks', readonly=True)
