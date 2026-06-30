from odoo import models, fields, api, exceptions
from odoo.exceptions import UserError, ValidationError


class Hijri(models.Model):
    _name = 'hijri'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = 'Hijri'
    _order = 'create_date desc'

    name = fields.Char('Hijri', tracking=True, required=True)
    
    # Approval workflow fields
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft', tracking=True)
    
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approval_date = fields.Datetime(string='Approval Date', readonly=True)
    rejected_by = fields.Many2one('res.users', string='Rejected By', readonly=True)
    rejection_reason = fields.Text(string='Rejection Reason')
    
    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Name must be unique!')
    ]

    def action_request_approval(self):
        """Request approval for the record - Changes state to pending"""
        for record in self:
            # Validate current state
            if record.state == 'approved':
                raise UserError('This record is already approved!')
            if record.state == 'pending':
                raise UserError('This record is already pending approval!')
            if record.state == 'rejected':
                raise UserError('Rejected records cannot be sent for approval. Please create a new one.')
            
            # CHANGE STATE TO PENDING
            record.write({
                'state': 'pending'
            })
            
            # Send notification to approvers
            self._notify_approvers()
            
            # Optional: Add a message to the chatter
            record.message_post(
                body=f"<b>Approval Requested</b><br/>"
                     f"Record <b>{record.name}</b> has been submitted for approval by {self.env.user.name}.",
                subject="Approval Requested"
            )

    def action_approve(self):
        """Approve the record - Only for approver group"""
        for record in self:
            if record.state != 'pending':
                raise UserError('Only pending records can be approved!')
            
            # CHANGE STATE TO APPROVED
            record.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approval_date': fields.Datetime.now()
            })
            
            # Add message to chatter
            record.message_post(
                body=f"<b>Approved</b><br/>"
                     f"Record <b>{record.name}</b> has been approved by {self.env.user.name}.",
                subject="Approved"
            )

    def action_reject(self):
        """Reject the record - Only for approver group"""
        for record in self:
            if record.state != 'pending':
                raise UserError('Only pending records can be rejected!')
            
            # Open wizard to capture rejection reason
            return {
                'type': 'ir.actions.act_window',
                'name': 'Rejection Reason',
                'res_model': 'hijri.reject.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_hijri_id': record.id,
                    'active_ids': self.ids,
                }
            }

    def _notify_approvers(self):
        """Send notification to all users in approver group"""
        approver_group = self.env.ref('bn_qurbani.group_hijri_approver', raise_if_not_found=False)
        
        if not approver_group:
            return
            
        approvers = self.env['res.users'].search([
            ('groups_id', 'in', approver_group.id)
        ])
        
        if approvers:
            # Subscribe approvers to the record
            for record in self:
                record.message_subscribe(partner_ids=approvers.mapped('partner_id').ids)
                
                # Send notification
                record.message_post(
                    body=f"<b>Approval Required</b><br/>"
                         f"<b>Record:</b> {record.name}<br/>"
                         f"<b>Requested by:</b> {self.env.user.name}<br/>"
                         f"<b>Date:</b> {fields.Datetime.now()}<br/><br/>"
                         f"Please review and approve/reject this record.",
                    subject="Approval Required",
                    partner_ids=approvers.mapped('partner_id').ids
                )

    @api.model
    def create(self, vals):
        """Override create to set initial state"""
        if 'state' not in vals:
            vals['state'] = 'draft'
        return super(Hijri, self).create(vals)

    def write(self, vals):
        """Override write to prevent editing approved records"""
        for record in self:
            if record.state == 'approved':
                # Only allow state changes for approved records
                if any(field not in ['state', 'approved_by', 'approval_date', 'rejected_by', 'rejection_reason'] 
                       for field in vals.keys()):
                    raise UserError('Approved records cannot be modified!')
        return super(Hijri, self).write(vals)

    def unlink(self):
        """Prevent deletion of approved records"""
        for record in self:
            if record.state == 'approved':
                raise UserError('Approved records cannot be deleted!')
        return super(Hijri, self).unlink()


class HijriRejectWizard(models.TransientModel):
    _name = 'hijri.reject.wizard'
    _description = 'Hijri Rejection Wizard'

    hijri_id = fields.Many2one('hijri', string='Hijri Record', required=True)
    rejection_reason = fields.Text(string='Rejection Reason', required=True)

    def action_confirm_reject(self):
        """Confirm rejection with reason - Changes state to rejected"""
        if not self.hijri_id:
            raise UserError('No Hijri record found!')
        
        if self.hijri_id.state != 'pending':
            raise UserError('Only pending records can be rejected!')
        
        # CHANGE STATE TO REJECTED
        self.hijri_id.write({
            'state': 'rejected',
            'rejected_by': self.env.user.id,
            'rejection_reason': self.rejection_reason
        })
        
        # Send notification to the creator
        if self.hijri_id.create_uid:
            self.hijri_id.message_post(
                body=f"<b>Record Rejected</b><br/>"
                     f"<b>Record:</b> {self.hijri_id.name}<br/>"
                     f"<b>Rejected by:</b> {self.env.user.name}<br/>"
                     f"<b>Reason:</b> {self.rejection_reason}",
                subject="Record Rejected",
                partner_ids=[self.hijri_id.create_uid.partner_id.id]
            )
        
        return {'type': 'ir.actions.act_window_close'}