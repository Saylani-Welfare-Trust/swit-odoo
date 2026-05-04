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
    domain_rider_ids = fields.Many2many('hr.employee', string="Rider IDs", compute="_set_rider_domain")
    domain_key_bunch_ids = fields.Many2many('key.bunch', string="Key Bunchs", compute="_set_location_domain")

    rider_id = fields.Many2one('hr.employee', string="Rider")
    employee_category_id = fields.Many2one('hr.employee.category', string="Employee Category", default=lambda self: self.env.ref('bn_donation_box.donation_box_rider_hr_employee_category', raise_if_not_found=False).id)
    
    key_bunch_ids = fields.Many2many('key.bunch', string="Key Bunch")

    date = fields.Date('Date', default=fields.Date.context_today)


    @api.depends('date', 'action_type')
    def _set_rider_domain(self):
        for rec in self:
            if rec.date:
                schedule_days = self.env['rider.schedule.day'].search([
                    ('date', '=', rec.date)
                ])
                rec.domain_rider_ids = [(6, 0, schedule_days.mapped('rider_shift_id.rider_id').ids)]
            else:
                rec.domain_rider_ids = [(6, 0, [])]

    @api.depends('date', 'action_type', 'rider_id')
    def _set_location_domain(self):
        for rec in self:
            domain_ids = []

            if rec.date and rec.rider_id:

                schedule_days = self.env['rider.schedule.day'].search([
                    ('rider_shift_id.rider_id', '=', rec.rider_id.id),
                    ('date', '=', fields.Date.today())
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

        KeyIssuance = self.env['key.issuance']

        for group in self.key_bunch_ids:
            keys = group.key_ids

            # 🚫 Check if any key in bunch is already issued manually
            manual_issued_keys = KeyIssuance.search([
                ('key_id', 'in', keys.ids),
                ('state', '=', 'issued'),
                ('action_type', '=', 'manual')
            ])

            if manual_issued_keys:
                raise ValidationError(
                    "❌ Cannot issue this Key Bunch!\n\n"
                    "Some keys are already issued manually:\n" +
                    "\n".join([f"  • {rec.key_id.name}" for rec in manual_issued_keys])
                )

            # ✅ Proceed with issuing keys
            for key in keys:
                if key.state != 'available':
                    continue

                # Optional: prevent duplicate issue same day
                existing_issue = KeyIssuance.search([
                    ('key_id', '=', key.id),
                    ('issue_date', '=', self.date)
                ], limit=1)

                if existing_issue:
                    continue

                issuance = KeyIssuance.create({
                    'rider_id': self.rider_id.id,
                    'key_id': key.id,
                    'action_type': 'bulk',  # explicitly mark
                })
                issuance.action_issue()





    # def action_return(self):
    #     if not self.rider_id:
    #         raise ValidationError('Please Select a Rider')

    #     if not self.key_bunch_ids:
    #         raise ValidationError('Please Select a Key Group')

    #     for group in self.key_bunch_ids:
    #         for key in group.key_ids:

    #             key_issuance = self.env['key.issuance'].search([
    #                 ('key_id', '=', key.id),
    #                 ('rider_id', '=', self.rider_id.id),
    #                 ('state', 'in', ['donation_receive', 'pending'])
    #             ], limit=1)

    #             if not key_issuance:
    #                 continue

    #             key_issuance.action_return()



    def action_return(self):
        if not self.rider_id:
            raise ValidationError('Please Select a Rider')

        if not self.key_bunch_ids:
            raise ValidationError('Please Select a Key Group')

        invalid_keys = []
        valid_issuances = []

        for group in self.key_bunch_ids:
            for key in group.key_ids:

                key_issuance = self.env['key.issuance'].search([
                    ('key_id', '=', key.id),
                    ('rider_id', '=', self.rider_id.id),
                ], limit=1)

                # No issuance OR wrong state
                if not key_issuance or key_issuance.state not in ['donation_receive', 'pending']:
                    invalid_keys.append(key.name)
                else:
                    valid_issuances.append(key_issuance)

        #  BLOCK if ANY invalid key found
        if invalid_keys:
            raise ValidationError(
                "Cannot proceed with return.\n\n"
                "All keys must be in 'Donation Received' or 'Pending' state.\n\n"
                "Invalid keys:\n" +
                "\n".join([f"  • {name}" for name in invalid_keys])
            )

        #  If all valid → process return
        for issuance in valid_issuances:
            issuance.action_return()