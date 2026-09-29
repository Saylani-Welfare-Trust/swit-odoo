# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

action_type_selection = [
    ('issue', 'Issue'),
    ('return', 'Return'),
]


class ManualKeyIssuance(models.TransientModel):
    _name = 'manual.key.issuance'
    _description = 'Manual Key Issuance'

    action_type = fields.Selection(selection=action_type_selection, string="Type")

    rider_id = fields.Many2one('hr.employee', string="Rider")
    lot_id = fields.Many2one('stock.lot', string="Box No.", domain="[('id', 'in', available_lot_ids)]")
    employee_category_id = fields.Many2one(
        'hr.employee.category', string="Employee Category",
        default=lambda self: self._default_employee_category_id())
    key_id = fields.Many2one('key', string="Key", compute="_set_key_id", store=True)

    available_lot_ids = fields.Many2many('stock.lot', string="Available Lots", compute="_compute_available_lot_ids")

    date = fields.Date('Date', default=fields.Date.context_today)

    @api.model
    def _default_employee_category_id(self):
        category = self.env.ref('bn_donation_box.donation_box_rider_hr_employee_category', raise_if_not_found=False)
        return category.id if category else False

    @api.depends('action_type', 'date', 'rider_id')
    def _compute_available_lot_ids(self):
        for rec in self:
            lot_ids = []
            Key = self.env['key']
            KeyIssuance = self.env['key.issuance']

            if rec.action_type == 'issue' and rec.date:
                blocked_key_ids = KeyIssuance.search([
                    '|', ('state', 'in', ('issued', 'overdue', 'pending')),
                    ('issue_date', '=', rec.date),
                ]).mapped('key_id').ids

                keys = Key.search([
                    ('state', '=', 'available'),
                    ('lot_id', '!=', False),
                    ('id', 'not in', blocked_key_ids),
                ])
                lot_ids = keys.mapped('lot_id').ids

            elif rec.action_type == 'return' and rec.rider_id:
                issuances = KeyIssuance.search([
                    ('rider_id', '=', rec.rider_id.id),
                    ('state', 'in', ('donation_receive', 'pending')),
                ])
                lot_ids = issuances.mapped('key_id.lot_id').ids

            rec.available_lot_ids = [(6, 0, list(set(lot_ids)))]

    @api.depends('lot_id')
    def _set_key_id(self):
        for rec in self:
            rec.key_id = False
            if rec.lot_id:
                key = self.env['key'].search([('lot_id', '=', rec.lot_id.id)], limit=1)
                if not key:
                    raise ValidationError(_('Key with Box No. "%s" not found.') % rec.lot_id.display_name)
                rec.key_id = key.id

    def action_issue(self):
        if not self.rider_id:
            raise ValidationError(_('Please select a Rider.'))
        if not self.key_id:
            raise ValidationError(_('Please select a key.'))
        if not self.date:
            raise ValidationError(_('Please select the issue date.'))

        issuance = self.env['key.issuance'].create({
            'rider_id': self.rider_id.id,
            'key_id': self.key_id.id,
            'action_type': 'manual',
            'issue_date': self.date,
        })
        # Availability / duplicate-issuance validation happens here.
        issuance.action_issue()
        return True

    def action_return(self):
        if not self.rider_id:
            raise ValidationError(_('Please select a Rider.'))
        if not self.key_id:
            raise ValidationError(_('Please select a Key.'))

        issuance = self.env['key.issuance'].search([
            ('key_id', '=', self.key_id.id),
            ('rider_id', '=', self.rider_id.id),
            ('state', 'in', ('donation_receive', 'pending')),
        ], order="id desc", limit=1)

        if not issuance:
            raise ValidationError(_(
                'Key "%s" cannot be returned. Only keys in "Donation Received" or "Pending" '
                'state can be returned.'
            ) % self.key_id.display_name)

        issuance.action_return()
        return True
