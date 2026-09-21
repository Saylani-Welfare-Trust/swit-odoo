from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MaterialRequestActionWizard(models.TransientModel):
    _name = 'material.request.action.wizard'
    _description = 'Material Request Stage Action'

    request_id = fields.Many2one(
        'material.request', required=True, readonly=True,
        default=lambda self: self.env.context.get('active_id'))
    action_type = fields.Selection([
        ('validate', 'Technical Validation'),
        ('hod_approve', 'Technical HOD Approval'),
        ('verify', 'Supply Chain Verification'),
        ('resume', 'Resume (Funds Available)'),
        ('send_committee', 'Send to Committee Approval'),
        ('reject', 'Reject'),
    ], string='Action', required=True, readonly=True)
    remarks = fields.Text('Remarks')

    def action_confirm(self):
        self.ensure_one()
        if self.action_type == 'reject' and not (self.remarks or '').strip():
            raise ValidationError(_('Please provide remarks for the rejection.'))
        method = {
            'validate': '_do_validate',
            'hod_approve': '_do_hod_approve',
            'verify': '_do_verify',
            'resume': '_do_resume',
            'send_committee': '_do_send_committee',
            'reject': '_do_reject',
        }[self.action_type]
        getattr(self.request_id, method)(self.remarks)
        return {'type': 'ir.actions.act_window_close'}
