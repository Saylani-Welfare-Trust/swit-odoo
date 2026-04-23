from odoo import fields, models, api
from odoo.exceptions import ValidationError, UserError


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

    date = fields.Date(
        string='Date',
        default=fields.Date.context_today,
        required=True
    )

    @api.depends('date', 'action_type', 'rider_id')
    def _set_rider_domain(self):
        for rec in self:
            if rec.date:
                schedule_days = self.env['rider.schedule.day'].search([
                    ('date', '=', rec.date)
                ])
                rec.rider_ids = [(6, 0, schedule_days.mapped('rider_shift_id.rider_id').ids)]
            else:
                rec.rider_ids = [(6, 0, [])]

    @api.depends('date', 'action_type', 'rider_id')
    def _set_location_domain(self):
        for rec in self:
            domain_ids = []

            if rec.date and rec.rider_id:

                schedule_days = self.env['rider.schedule.day'].search([
                    ('date', '=', rec.date),
                    ('rider_shift_id.rider_id', '=', rec.rider_id.id)
                ])

                if rec.action_type == 'issue':
                    # ✅ Only bunch assigned in shift
                    domain_ids = schedule_days.mapped('key_bunch_id').ids

                elif rec.action_type == 'return':
                    # ✅ Only bunch where payment received
                    issuances = self.env['key.issuance'].search([
                        ('rider_id', '=', rec.rider_id.id),
                        ('state', 'in', ['donation_receive', 'pending']),
                    ])
                    domain_ids = issuances.mapped('key_id.key_bunch_id').ids

            rec.domain_key_bunch_ids = [(6, 0, list(set(domain_ids)))]

    def action_issue(self):
        if not self.rider_id:
            raise ValidationError('Please Select a Rider')
        
        if not self.key_bunch_ids:
            raise ValidationError('Please Select a Key Group to issue')

        for group in self.key_bunch_ids:
            # raise ValidationError(f'Key Group Info: {group.read()[0]}')
            for key in group.key_ids:
                if key.state == 'available':
                    # 🔍 Check if already issued today
                    existing_issue = self.env['key.issuance'].search([
                        ('key_id', '=', key.id),
                        ('issue_date', '=', self.date)
                    ], limit=1)

                    if existing_issue:
                        continue
                    
                    key_issuance_obj = self.env['key.issuance'].create({
                        'rider_id': self.rider_id.id,
                        'key_id': key.id
                    })
                    key_issuance_obj.action_issue()
            
        
                

    def action_return(self):
        if not self.rider_id:
            raise ValidationError('Please Select a Rider')

        if not self.key_bunch_ids:
            raise ValidationError('Please Select a Key Group')

        for group in self.key_bunch_ids:
            for key in group.key_ids:

                key_issuance = self.env['key.issuance'].search([
                    ('key_id', '=', key.id),
                    ('rider_id', '=', self.rider_id.id),
                    ('state', 'in', ['donation_receive', 'pending'])
                ], limit=1)

                if not key_issuance:
                    # raise ValidationError(
                    #     f'Key "{key.name}" is not in Donation Received / Pending state.'
                    # )
                    pass

                key_issuance.action_return()