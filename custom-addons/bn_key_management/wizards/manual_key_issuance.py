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

    rider_id = fields.Many2one('hr.employee', string="Rider")
    lot_id = fields.Many2one('stock.lot', string="Box No.", domain="[('id', 'in', available_lot_ids)]")
    employee_category_id = fields.Many2one('hr.employee.category', string="Employee Category", default=lambda self: self.env.ref('bn_donation_box.donation_box_rider_hr_employee_category', raise_if_not_found=False).id)
    key_id = fields.Many2one('key', string="Key", compute="_set_key_id", store=True)
    
    available_lot_ids = fields.Many2many('stock.lot', string="Available Lots", compute="_compute_available_lot_ids")

    date = fields.Date('Date', default=fields.Date.context_today)


    @api.depends('action_type', 'date', 'rider_id')
    def _compute_available_lot_ids(self):
        for rec in self:
            lot_ids = []

            Key = self.env['key']
            KeyIssuance = self.env['key.issuance']

            if rec.action_type == 'issue' and rec.date:
                # 🔴 Active issuances
                active_issuances = KeyIssuance.search([
                    ('state', '!=', 'returned')
                ])
                active_bunch_ids = active_issuances.mapped('key_id.key_bunch_id').ids

                # 🔴 Same-day issuances
                today_issuances = KeyIssuance.search([
                    ('issue_date', '=', rec.date),
                    ('state', '!=', 'returned')
                ])
                today_bunch_ids = today_issuances.mapped('key_id.key_bunch_id').ids

                blocked_bunch_ids = list(set(active_bunch_ids + today_bunch_ids))

                keys = Key.search([
                    ('state', '=', 'available'),
                    ('lot_id', '!=', False),
                    ('key_bunch_id', 'not in', blocked_bunch_ids)
                ])

                lot_ids = keys.mapped('lot_id').ids

            elif rec.action_type == 'return' and rec.rider_id:

                # 🔵 Only issued or overdue keys for selected rider
                key_issuances = KeyIssuance.search([
                    ('rider_id', '=', rec.rider_id.id),
                    ('state', '!=', 'returned')
                ])

                keys = key_issuances.mapped('key_id')

                lot_ids = keys.mapped('lot_id').ids

            rec.available_lot_ids = [(6, 0, list(set(lot_ids)))]

    @api.depends('lot_id')
    def _set_key_id(self):
        """Search for key by lot_id"""
        if self.lot_id:
        
            key = self.env['key'].search([('lot_id', '=', self.lot_id.id)], limit=1)
            
            if not key:
                raise ValidationError(f'Key with Box No. "{self.lot_id.name}" not found')
            
            self.key_id = key.id

    def action_issue(self):
        if not self.rider_id:
            raise ValidationError('Please Select a Rider')

        key = self.key_id  # record

        if not key:
            raise ValidationError('Please select a key')

        if key.state != 'available':
            raise ValidationError(f'Key "{key.name}" is not available for issuance')

        if not self.date:
            raise ValidationError('Please select issue date')

        # 🔍 Get key bunch
        bunch = key.key_bunch_id

        if bunch:
            bunch_keys = bunch.key_ids

            # 🚫 1. Block if ANY key from bunch is already issued (active)
            issued_keys = self.env['key.issuance'].search([
                ('key_id', 'in', bunch_keys.ids),
                ('state', '=', 'issued')
            ])

            if issued_keys:
                raise ValidationError(
                    "❌ Cannot manually issue this key!\n\n"
                    "Another key from the same bunch is already issued:\n" +
                    "\n".join([f"  • {rec.key_id.name}" for rec in issued_keys])
                )

            # 🚫 2. SAME-DAY constraint (IMPORTANT FIX)
            same_day_issue = self.env['key.issuance'].search([
                ('key_id', 'in', bunch_keys.ids),
                ('issue_date', '=', self.date),
                ('state', '=', 'issued')
            ])

            if same_day_issue:
                raise ValidationError(
                    "❌ This key bunch already has an issue recorded for the selected date."
                )

        # ✅ Safe to issue manually
        key_issuance_obj = self.env['key.issuance'].create({
            'rider_id': self.rider_id.id,
            'key_id': key.id,
            'action_type': 'manual',
            'issue_date': self.date,
        })

        key_issuance_obj.action_issue()

    def action_return(self):
        if not self.rider_id:
            raise ValidationError('Please Select a Rider')

        key = self.key_id

        if not key:
            raise ValidationError('Please Select a Key')

        KeyIssuance = self.env['key.issuance']

        # 🔴 Find valid returnable record
        key_issuance = KeyIssuance.search([
            ('key_id', '=', key.id),
            ('state', 'in', ['donation_receive', 'pending'])
        ], limit=1)

        # ❌ If not found → cannot return
        if not key_issuance:
            raise ValidationError(
                f'Key "{key.name}" cannot be returned.\n'
                f'Only keys in "Donation Received" or "Pending" state can be returned.'
            )

        # 🚀 Proceed return
        key_issuance.action_return()
