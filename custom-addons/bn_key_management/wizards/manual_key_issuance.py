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


    @api.depends('action_type', 'date')
    def _compute_available_lot_ids(self):
        for rec in self:
            lot_ids = []

            if rec.action_type == 'issue':
                # Only available keys
                keys = self.env['key'].search([
                    ('state', '=', 'available'),
                    ('lot_id', '!=', False)
                ])
                lot_ids = keys.mapped('lot_id').ids

            elif rec.action_type == 'return':
                # Keys where:
                # payment received + submitted in POS + DN prepared
                key_issuances = self.env['key.issuance'].search([
                    ('state', 'in', ['donation_receive'])
                ])
                lot_ids = key_issuances.mapped('key_id.lot_id').ids

            rec.available_lot_ids = [(6, 0, lot_ids)]

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

        key = self.key_id  # ✅ correct (record, not ID)

        if not key:
            raise ValidationError('Please select a key')

        if key.state != 'available':
            raise ValidationError(f'Key "{key.name}" is not available for issuance')

        # 🔍 Get key bunch
        bunch = key.key_bunch_id  # assuming this relation exists

        if bunch:
            bunch_keys = bunch.key_ids

            # 🔴 Check if ANY key in this bunch is already issued
            issued_keys = self.env['key.issuance'].search([
                ('key_id', 'in', bunch_keys.ids),
                ('state', 'in', ['issued', 'overdue']),
                ('action_type', '=', 'manual')
            ])

            if issued_keys:
                raise ValidationError(
                    "❌ Cannot manually issue this key!\n\n"
                    "Another key from the same bunch is already issued:\n" +
                    "\n".join([f"  • {rec.key_id.name}" for rec in issued_keys])
                )

        # ✅ Safe to issue manually
        key_issuance_obj = self.env['key.issuance'].create({
            'rider_id': self.rider_id.id,
            'key_id': key.id,
            'action_type': 'manual',  # ✅ important
        })

        key_issuance_obj.action_issue()

    def action_return(self):
        if not self.rider_id:
            raise ValidationError('Please Select a Rider')
        
        key = self.key_id
        
        key_issuance = self.env['key.issuance'].search([
            ('key_id', '=', key.id), 
            ('state', '=', 'issued')
        ], limit=1)
        
        if key_issuance:
            raise ValidationError(f'Please move key "{key.name}" to Donation Received state first.')

        key_issuance = self.env['key.issuance'].search([
            ('key_id', '=', key.id),
            ('state', 'in', ['donation_receive', 'pending'])
        ], limit=1)
        
        if not key_issuance:
            return

        key_issuance.action_return()
