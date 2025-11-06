from odoo import fields, models, api
from odoo.exceptions import ValidationError


action_type_selection = [
    ('issue', 'Issue'),
    ('return', 'Return'),
]


class BulkKeyIssuance(models.TransientModel):
    _name = 'bulk.key.issuance'
    _description = 'Bulk Key Issuance'


    action_type = fields.Selection(selection=action_type_selection, string="Type")

    rider_ids = fields.Many2many('hr.employee', string="Rider IDs", compute="_set_rider_domain")
    domain_key_bunch_ids = fields.Many2many('key.bunch', string="Key Bunchs", compute="_set_location_domain")

    rider_id = fields.Many2one('hr.employee', string="Rider")
    
    key_bunch_ids = fields.Many2many('key.bunch', string="Key Bunch")

    date = fields.Date('Date')


    @api.depends('date')
    def _set_rider_domain(self):
        for rec in self:
            if rec.date:
                schedule_days = self.env['rider.schedule.day'].search([('date', '=', rec.date)])
                rec.rider_ids = [(6, 0, schedule_days.mapped('rider_shift_id.rider_id').ids)]
            else:
                rec.rider_ids = [(6, 0, [])]

    @api.depends('date')
    def _set_location_domain(self):
        for rec in self:
            if rec.date:
                schedule_days = self.env['rider.schedule.day'].search([('date', '=', rec.date)])
                rec.domain_key_bunch_ids = [(6, 0, schedule_days.mapped('key_bunch_id').ids)]
            else:
                rec.domain_key_bunch_ids = [(6, 0, [])]

    def action_issue(self):
        if not self.rider_id:
            raise ValidationError('Please Select a Rider')
        
        if not self.key_bunch_ids:
            raise ValidationError('Please Select a Key Group to issue')

        for group in self.key_bunch_ids:
            # raise ValidationError(f'Key Group Info: {group.read()[0]}')
            for key in group.key_ids:
                if key.state == 'available':
                    key_issuance_obj = self.env['key.issuance'].create({
                        'rider_id': self.rider_id.id,
                        'key_id': key.id
                    })

                    key_issuance_obj.action_issue()

    def action_return(self):
        if not self.rider_id:
            raise ValidationError('Please Select a Rider')
        if not self.key_bunch_ids:
            raise ValidationError('Please Select a Key Group to issue')
 

        for group in self.key_bunch_ids:
            key_issuance = self.env['key.issuance'].search([('key_id', 'in', self.key_bunch_ids.key_ids.ids), ('state', '=', 'issued')])
            if key_issuance:
                raise ValidationError('Please move all keys in Donation Received state.')

            for key in group.key_ids:
                key_issuance = self.env['key.issuance'].search([('key_id', '=', key.id)])
                
                if key_issuance:
                    key_issuance.action_return()