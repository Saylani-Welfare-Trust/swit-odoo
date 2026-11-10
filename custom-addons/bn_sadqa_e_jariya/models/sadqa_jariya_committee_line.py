from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class SadqaJariyaCommitteeLine(models.Model):
    """A committee member's decision on the application, given in Committee Approval"""
    _name = 'sadqa.jariya.committee.line'
    _description = 'Committee Member Decision'

    application_id = fields.Many2one('sadqa.jariya', string='Application', required=True, ondelete='cascade')
    member_id = fields.Many2one('sadqa.jariya.committee.member', string='Member', required=True, ondelete='restrict')
    remarks = fields.Text(string='Remarks')
    is_approved = fields.Boolean(string='Approve')
    is_rejected = fields.Boolean(string='Reject')

    _sql_constraints = [
        ('member_unique', 'unique(application_id, member_id)', 'A committee member can only be added once to an application.'),
    ]

    @api.onchange('is_approved')
    def _onchange_is_approved(self):
        if self.is_approved:
            self.is_rejected = False

    @api.onchange('is_rejected')
    def _onchange_is_rejected(self):
        if self.is_rejected:
            self.is_approved = False

    @api.constrains('is_approved', 'is_rejected')
    def _check_one_decision(self):
        for line in self:
            if line.is_approved and line.is_rejected:
                raise ValidationError(_('%s can either approve or reject the application, not both.') % line.member_id.name)
