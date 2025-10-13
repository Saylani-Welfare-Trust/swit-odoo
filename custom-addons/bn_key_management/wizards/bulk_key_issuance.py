from odoo import fields, models, api, exceptions

type_selection = [
    ('issue', 'Issue'),
    ('return', 'Return'),
]


class BulkKeyIssuance(models.TransientModel):
    _name = 'bulk.key.issuance'
    _description = 'Bulk Key Issuance'


    type = fields.Selection(selection=type_selection, string="Type")

    domain_rider_ids = fields.Many2many('hr.employee', string="Rider IDs", compute="_set_rider_domain")
    domain_key_location_ids = fields.Many2many('key.location', string="Key Location IDs", compute="_set_location_domain")

    rider_id = fields.Many2one('hr.employee', string="Rider ID")
    
    key_location_ids = fields.Many2many('key.location', string="Key IDs")

    date = fields.Date('Date')


    @api.depends('date')
    def _set_rider_domain(self):
        for rec in self:
            if rec.date:
                schedule_days = self.env['schedule.day'].search([('date', '=', rec.date)])
                rec.domain_rider_ids = [(6, 0, schedule_days.mapped('rider_shift_id.rider_id').ids)]
            else:
                rec.domain_rider_ids = [(6, 0, [])]  # clear all
    
    @api.depends('date')
    def _set_location_domain(self):
        for rec in self:
            if rec.date:
                schedule_days = self.env['schedule.day'].search([('date', '=', rec.date)])
                rec.domain_key_location_ids = [(6, 0, schedule_days.mapped('key_location_id').ids)]
            else:
                rec.domain_key_location_ids = [(6, 0, [])]  # clear all

    def action_issue(self):
        if not self.rider_id:
            raise exceptions.ValidationError('Please Select a Rider')
        if not self.key_location_ids:
            raise exceptions.ValidationError('Please Select a Key Group to issue')

        for group in self.key_location_ids:
            # raise exceptions.ValidationError(f'Key Group Info: {group.read()[0]}')
            for key in group.key_ids:
                if key.state == 'available':
                    key_issuance_obj = self.env['key.issuance'].create({
                        'rider_id': self.rider_id.id,
                        'key_id': key.id
                    })

                    key_issuance_obj.action_key_issued()

    def action_return(self):
        if not self.rider_id:
            raise exceptions.ValidationError('Please Select a Rider')
        if not self.key_location_ids:
            raise exceptions.ValidationError('Please Select a Key Group to issue')
 

        for group in self.key_location_ids:
            key_issuance = self.env['key.issuance'].search([('key_id', 'in', self.key_location_ids.key_ids.ids), ('state', '=', 'issued')])
            if key_issuance:
                raise exceptions.ValidationError('Please move all keys in Donation Received state.')

            for key in group.key_ids:
                key_issuance = self.env['key.issuance'].search([('key_id', '=', key.id)])
                
                if key_issuance:
                    key_issuance.action_return_key()