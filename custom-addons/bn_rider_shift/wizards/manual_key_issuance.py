from odoo import models, fields
from odoo.exceptions import ValidationError


class ManualKeyIssuance(models.TransientModel):
    _inherit = 'manual.key.issuance'

    def action_issue(self):
        if not self.rider_id:
            raise ValidationError('Please Select a Rider')

        key = self.key_id

        if not key:
            raise ValidationError('Please select a key')

        if key.state != 'available':
            raise ValidationError(f'Key "{key.name}" is not available for issuance')

        # 🔍 Get key bunch
        bunch = key.key_bunch_id

        if bunch:
            bunch_keys = bunch.key_ids

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

        today = fields.Date.today()

        # =========================================================
        # 🔥 APPLY rider.collection LOGIC (same as shift screen)
        # =========================================================
        box = key.donation_box_registration_installation_id

        RiderCollection = self.env['rider.collection']

        if box:
            rider_collection = RiderCollection.search([
                ('rider_id', '=', self.rider_id.id),
                ('date', '=', today),
                ('donation_box_registration_installation_id', '=', box.id),
            ], limit=1)

            if not rider_collection:
                rider_collection = RiderCollection.create({
                    'rider_id': self.rider_id.id,
                    'date': today,
                    'donation_box_registration_installation_id': box.id,
                })
        else:
            rider_collection = False

        # =========================================================
        # ✅ Create Key Issuance
        # =========================================================
        key_issuance_obj = self.env['key.issuance'].create({
            'rider_id': self.rider_id.id,
            'key_id': key.id,
            'action_type': 'manual',
            'rider_collection_id': rider_collection.id if rider_collection else False,
        })

        key_issuance_obj.action_issue()