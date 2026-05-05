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

    rider_id = fields.Many2one('hr.employee', string="Rider")
    
    key_bunch_ids = fields.Many2many('key.bunch', string="Key Bunch")
    domain_rider_ids = fields.Many2many('hr.employee', string="Rider IDs", compute="_set_rider_domain")
    domain_key_bunch_ids = fields.Many2many('key.bunch', string="Key Bunchs", compute="_set_location_domain")

    date = fields.Date('Date', default=fields.Date.today())


    @api.depends('date', 'action_type')
    def _set_rider_domain(self):
        for rec in self:
            rec.domain_rider_ids = [(6, 0, [])]

            if rec.action_type == 'issue':

                # 1. Riders from schedule
                schedule_days = self.env['rider.schedule.day'].search([
                    ('date', '=', rec.date)
                ])

                scheduled_riders = schedule_days.mapped('rider_shift_id.rider_id')

                # 2. Riders already having issued keys on same date
                issued_riders = self.env['key.issuance'].search([
                    ('issue_date', '=', rec.date),
                    ('state', '!=', 'returned')
                ]).mapped('rider_id')

                # 3. Remove already issued riders
                available_riders = scheduled_riders - issued_riders

                rec.domain_rider_ids = [(6, 0, available_riders.ids)]

            elif rec.action_type == 'return':
                KeyIssuance = self.env['key.issuance']

                issuances = KeyIssuance.search([
                    ('rider_id', '=', rec.rider_id.id),
                    ('state', '!=', 'returned')
                ], order="key_id, id desc")

                latest_per_key = {}
                for iss in issuances:
                    if iss.key_id.id not in latest_per_key:
                        latest_per_key[iss.key_id.id] = iss

                rider_map = {}
                for iss in latest_per_key.values():
                    rider = iss.rider_id
                    if not rider:
                        continue
                    rider_map.setdefault(rider.id, []).append(iss)

                valid_riders = list(rider_map.keys())

                rec.domain_rider_ids = [(6, 0, valid_riders)]

    @api.depends('date', 'action_type', 'rider_id')
    def _set_location_domain(self):
        for rec in self:
            domain_ids = []

            if rec.date and rec.rider_id:

                if rec.action_type == 'issue':

                    # 1. All scheduled bunches for that rider on that date
                    schedule_days = self.env['rider.schedule.day'].search([
                        ('rider_shift_id.rider_id', '=', rec.rider_id.id),
                        ('date', '=', rec.date)
                    ])

                    scheduled_bunches = schedule_days.mapped('key_bunch_id')

                    # 2. Already issued bunches on same date
                    issued_bunches = self.env['key.issuance'].search([
                        ('rider_id', '=', rec.rider_id.id),
                        ('issue_date', '=', rec.date),
                        ('state', '!=', 'returned')
                    ]).mapped('key_bunch_id')

                    # 3. Remove already issued ones
                    available_bunches = scheduled_bunches - issued_bunches

                    domain_ids = available_bunches.ids

                elif rec.action_type == 'return':
                    KeyIssuance = self.env['key.issuance']

                    issuances = KeyIssuance.search([
                        ('rider_id', '=', rec.rider_id.id),
                        ('state', '!=', 'returned')
                    ], order="key_id, id desc")

                    latest_per_key = {}
                    for iss in issuances:
                        if iss.key_id.id not in latest_per_key:
                            latest_per_key[iss.key_id.id] = iss

                    active_keys = [
                        iss.key_id for iss in latest_per_key.values()
                        if iss.state != 'returned'
                    ]

                    domain_ids = list(set(
                        key.key_bunch_id.id
                        for key in active_keys
                        if key.key_bunch_id
                    ))

            rec.domain_key_bunch_ids = [(6, 0, domain_ids)]

    def action_issue(self):
        if not self.rider_id:
            raise ValidationError('Please Select a Rider')

        if not self.key_bunch_ids:
            raise ValidationError('Please Select a Key Group to issue')

        KeyIssuance = self.env['key.issuance']

        for group in self.key_bunch_ids:
            keys = group.key_ids

            # 🚫 1. Check ANY key already issued (active only)
            issued_keys = KeyIssuance.search([
                ('key_id', 'in', keys.ids),
                ('state', '!=', 'returned')
            ])

            if issued_keys:
                raise ValidationError(
                    "❌ Cannot issue this Key Bunch!\n\n"
                    "Some keys are already issued:\n" +
                    "\n".join([f"  • {rec.key_id.name}" for rec in issued_keys])
                )

            # 🚫 2. Prevent same-day duplicate issue (IMPORTANT FIX)
            same_day_issue = KeyIssuance.search([
                ('key_id', 'in', keys.ids),
                ('issue_date', '=', self.date),
                ('state', '!=', 'returned')
            ])

            if same_day_issue:
                raise ValidationError(
                    "❌ This Key Bunch already has issued keys for selected date."
                )

            # 🚫 3. Ensure bunch is not already assigned (any rider)
            bunch_issued = KeyIssuance.search([
                ('key_id.key_bunch_id', '=', group.id),
                ('state', '!=', 'returned')
            ])

            if bunch_issued:
                raise ValidationError(
                    "❌ This Key Bunch is already issued to another rider."
                )

            # ✅ Issue keys
            for key in keys:
                if key.state != 'available':
                    continue

                issuance = KeyIssuance.create({
                    'rider_id': self.rider_id.id,
                    'key_id': key.id,
                    'action_type': 'bulk',
                    'issue_date': self.date,
                })
                issuance.action_issue()

    def action_return(self):
        if not self.rider_id:
            raise ValidationError('Please Select a Rider')

        if not self.key_bunch_ids:
            raise ValidationError('Please Select a Key Group')

        KeyIssuance = self.env['key.issuance']

        for group in self.key_bunch_ids:
            keys = group.key_ids

            invalid_keys = []
            valid_issuances = []

            for key in keys:
                # 🔥 Get latest issuance for this key + rider
                issuance = KeyIssuance.search([
                    ('key_id', '=', key.id),
                    ('rider_id', '=', self.rider_id.id),
                ], order="id desc", limit=1)

                # ❌ If no issuance OR wrong state → block
                if not issuance or issuance.state not in ['donation_receive', 'pending']:
                    invalid_keys.append(key.name)
                else:
                    valid_issuances.append(issuance)

            # 🚫 Block entire bunch if any key invalid
            if invalid_keys:
                raise ValidationError(
                    "❌ Cannot return this Key Bunch!\n\n"
                    "Following keys are not in returnable state:\n" +
                    "\n".join([f"  • {k}" for k in invalid_keys])
                )

            # ✅ All keys valid → return entire bunch
            for issuance in valid_issuances:
                issuance.action_return()