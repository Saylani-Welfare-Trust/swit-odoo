# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
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

    date = fields.Date('Date', default=fields.Date.context_today)

    @api.depends('date', 'action_type')
    def _set_rider_domain(self):
        for rec in self:
            rec.domain_rider_ids = [(6, 0, [])]

            if rec.action_type == 'issue':
                schedule_days = self.env['rider.schedule.day'].search([('date', '=', rec.date)])
                scheduled_riders = schedule_days.mapped('rider_shift_id.rider_id')

                issued_riders = self.env['key.issuance'].search([
                    ('issue_date', '=', rec.date),
                    ('state', '!=', 'returned'),
                ]).mapped('rider_id')

                rec.domain_rider_ids = [(6, 0, (scheduled_riders - issued_riders).ids)]

            elif rec.action_type == 'return':
                issuances = self.env['key.issuance'].search([
                    ('state', 'in', ('donation_receive', 'pending')),
                ])
                rec.domain_rider_ids = [(6, 0, issuances.mapped('rider_id').ids)]

    @api.depends('date', 'action_type', 'rider_id')
    def _set_location_domain(self):
        for rec in self:
            domain_ids = []

            if rec.date and rec.rider_id:
                if rec.action_type == 'issue':
                    schedule_days = self.env['rider.schedule.day'].search([
                        ('rider_shift_id.rider_id', '=', rec.rider_id.id),
                        ('date', '=', rec.date),
                    ])
                    scheduled_bunches = schedule_days.mapped('key_bunch_id')

                    issued_bunches = self.env['key.issuance'].search([
                        ('rider_id', '=', rec.rider_id.id),
                        ('issue_date', '=', rec.date),
                        ('state', '!=', 'returned'),
                    ]).mapped('key_bunch_id')

                    domain_ids = (scheduled_bunches - issued_bunches).ids

                elif rec.action_type == 'return':
                    issuances = self.env['key.issuance'].search([
                        ('rider_id', '=', rec.rider_id.id),
                        ('state', 'in', ('donation_receive', 'pending')),
                    ])
                    domain_ids = list(set(issuances.mapped('key_bunch_id').ids))

            rec.domain_key_bunch_ids = [(6, 0, domain_ids)]

    def action_issue(self):
        if not self.rider_id:
            raise ValidationError(_('Please select a Rider.'))
        if not self.key_bunch_ids:
            raise ValidationError(_('Please select a Key Bunch to issue.'))

        KeyIssuance = self.env['key.issuance']
        for bunch in self.key_bunch_ids:
            keys = bunch.key_ids.filtered(lambda k: k.state != 'closed')
            if not keys:
                continue

            already_issued = KeyIssuance.search([
                ('key_id', 'in', keys.ids), ('state', 'in', ('issued', 'overdue', 'pending')),
            ])
            if already_issued:
                raise ValidationError(_(
                    'Cannot issue Key Bunch "%(bunch)s": the following keys are already issued:\n%(keys)s'
                ) % {'bunch': bunch.display_name,
                     'keys': '\n'.join('  • %s (%s)' % (r.key_id.display_name, r.rider_id.display_name)
                                      for r in already_issued)})

            for key in keys.filtered(lambda k: k.state == 'available'):
                issuance = KeyIssuance.create({
                    'rider_id': self.rider_id.id,
                    'key_id': key.id,
                    'action_type': 'bulk',
                    'issue_date': self.date,
                })
                # Real validation (availability, duplicate issuance...) happens here.
                issuance.action_issue()
        return True

    def action_return(self):
        if not self.rider_id:
            raise ValidationError(_('Please select a Rider.'))
        if not self.key_bunch_ids:
            raise ValidationError(_('Please select a Key Bunch.'))

        KeyIssuance = self.env['key.issuance']
        invalid_keys = []
        valid_issuances = self.env['key.issuance']

        all_keys = self.key_bunch_ids.key_ids
        # One batched query for every key in every selected bunch, instead of a
        # separate search per key (which, at up to 50 keys per bunch, could mean
        # hundreds of individual queries for one button click). Ordering by id
        # descending means the first match per key_id we keep is the latest one,
        # matching the original per-key "order=id desc, limit=1" semantics.
        all_issuances = KeyIssuance.search([
            ('key_id', 'in', all_keys.ids), ('rider_id', '=', self.rider_id.id),
        ], order="id desc")
        latest_by_key = {}
        for issuance in all_issuances:
            latest_by_key.setdefault(issuance.key_id.id, issuance)

        for key in all_keys:
            issuance = latest_by_key.get(key.id)
            if not issuance:
                # This particular key was never issued to this rider:
                # nothing to return, nothing to block on - skip it.
                continue
            if issuance.state not in ('donation_receive', 'pending'):
                invalid_keys.append('%s (%s)' % (key.display_name,
                                                  issuance._bn_selection_label('state', issuance.state)))
            else:
                valid_issuances |= issuance

        # if invalid_keys:
        #     raise ValidationError(_(
        #         'Cannot return this Key Bunch!\n\n'
        #         'The following keys are not in a returnable state (Donation Received / Pending):\n%s'
        #     ) % '\n'.join('  • %s' % k for k in invalid_keys))

        for issuance in self.key_bunch_ids.key_ids:
            issuance.action_return()
        return True
