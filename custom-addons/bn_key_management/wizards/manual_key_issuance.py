from odoo import fields, models, api
from odoo.exceptions import ValidationError


action_type_selection = [
    ('issue', 'Issue'),
    ('return', 'Return'),
]


class ManualKeyIssuance(models.TransientModel):
    _name = 'manual.key.issuance'
    _description = 'Manual Key Issuance'


    action_type = fields.Selection(selection=action_type_selection, string="Type")

    rider_ids = fields.Many2many('hr.employee', string="Rider IDs", compute="_set_rider_domain")

    rider_id = fields.Many2one('hr.employee', string="Rider")
    
    key_name = fields.Char(string="Key")

    date = fields.Date('Date')


    @api.depends('date')
    def _set_rider_domain(self):
        for rec in self:
            if rec.date:
                schedule_days = self.env['rider.schedule.day'].search([('date', '=', rec.date)])
                rec.rider_ids = [(6, 0, schedule_days.mapped('rider_shift_id.rider_id').ids)]
            else:
                rec.rider_ids = [(6, 0, [])]

    def _get_key(self):
        """Search for key by name"""
        if not self.key_name:
            raise ValidationError('Please enter a Key name')
        
        key = self.env['key'].search([('name', '=', self.key_name)], limit=1)
        
        if not key:
            raise ValidationError(f'Key "{self.key_name}" not found')
        
        return key

    def action_issue(self):
        if not self.rider_id:
            raise ValidationError('Please Select a Rider')
        
        key = self._get_key()
        
        if key.state != 'available':
            raise ValidationError(f'Key "{key.name}" is not available for issuance')
        
        key_issuance_obj = self.env['key.issuance'].create({
            'rider_id': self.rider_id.id,
            'key_id': key.id
        })

        key_issuance_obj.action_issue()

    def action_return(self):
        if not self.rider_id:
            raise ValidationError('Please Select a Rider')
        
        key = self._get_key()
        
        key_issuance = self.env['key.issuance'].search([
            ('key_id', '=', key.id), 
            ('state', '=', 'issued')
        ], limit=1)
        
        if key_issuance:
            raise ValidationError(f'Please move key "{key.name}" to Donation Received state first.')

        key_issuance = self.env['key.issuance'].search([
            ('key_id', '=', key.id),
            ('state', '=', 'donation_receive')
        ], limit=1)
        
        if key_issuance:
            key_issuance.action_return()
        else:
            raise ValidationError(f'No issuance record found for key "{key.name}" in Donation Received state.')
