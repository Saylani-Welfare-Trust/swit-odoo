from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class MaterialRequestRevertWizard(models.TransientModel):
    _name = 'material.request.revert.wizard'
    _description = 'Material Request Revert Wizard'

    request_id = fields.Many2one('material.request', string='Material Request', required=True, readonly=True)
    current_state = fields.Char(string='Current State', readonly=True)
    reason = fields.Text(string='Revert Reason', required=True, help='Please provide a reason for reverting this request.')
    
    # NEW: Add target state selection
    target_state = fields.Selection([
        ('draft', 'Draft'),
        ('hod_approval', 'HOD Approval'),
        ('committee_approval', 'Committee Approval')
    ], string='Revert To', required=True, default='draft')

    def action_revert(self):
        self.ensure_one()
        if not self.reason:
            raise ValidationError(_('You must provide a reason to revert this request.'))
        
        # Pass the target_state to the main model
        self.request_id.action_process_revert(self.reason, self.target_state)
        return {'type': 'ir.actions.act_window_close'}