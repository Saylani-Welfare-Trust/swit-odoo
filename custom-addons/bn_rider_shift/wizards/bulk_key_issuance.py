from odoo import models, fields
from odoo.exceptions import ValidationError


class BulkKeyIssuance(models.TransientModel):
    _inherit = 'bulk.key.issuance'

    def action_issue(self):
        if not self.rider_id:
            raise ValidationError('Please Select a Rider')

        if not self.key_bunch_ids:
            raise ValidationError('Please Select a Key Group to issue')

        KeyIssuance = self.env['key.issuance']
        RiderCollection = self.env['rider.collection']

        today = fields.Date.today()

        for group in self.key_bunch_ids:
            keys = group.key_ids

            # 🚫 Check manual issued keys
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

            for key in keys:
                if key.state != 'available':
                    continue

                # جلوگیری از duplicate issue
                existing_issue = KeyIssuance.search([
                    ('key_id', '=', key.id),
                    ('issue_date', '=', today)
                ], limit=1)

                if existing_issue:
                    continue

                box = key.donation_box_registration_installation_id
                if not box:
                    continue

                # =====================================================
                # 🔥 APPLY rider.collection LOGIC (same as shift)
                # =====================================================
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

                # =====================================================
                # 🔹 Create Key Issuance
                # =====================================================
                issuance = KeyIssuance.create({
                    'rider_collection_id': rider_collection.id,
                    'rider_id': self.rider_id.id,
                    'key_id': key.id,
                    'action_type': 'bulk',
                })

                issuance.action_issue()