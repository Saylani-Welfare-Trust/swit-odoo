# -*- coding: utf-8 -*-
from odoo import api, fields, models


class KeyIssuance(models.Model):
    _inherit = 'key.issuance'

    rider_collection_id = fields.Many2one('rider.collection', string="Rider Collection", copy=False)

    def _bn_do_issue(self):
        super()._bn_do_issue()
        # Rider Shift record: created as superuser, the Key Management group
        # checked by action_issue is the gate.
        key = self.key_id
        collection = self.env['rider.collection'].sudo().create({
            'rider_id': self.rider_id.id,
            'donation_box_registration_installation_id': key.donation_box_registration_installation_id.id,
            'lot_id': key.lot_id.id,
            'date': self.issue_date,
        })
        self._bn_write({'rider_collection_id': collection.id})

    # ------------------------------------------------------------------
    # POS RPC entry point
    # ------------------------------------------------------------------
    @api.model
    def set_donation_amount(self, data):
        """Called from the POS Donation Box screen when a rider closes out a box."""
        if not data:
            return {"status": "error", "body": "Please specify Key and Collection Amount"}

        collection_id = data.get('collection_id')
        if not collection_id:
            return {"status": "error", "body": "Collection ID is required"}

        collection = self.env['rider.collection'].browse(collection_id)
        if not collection.exists():
            return {"status": "error", "body": "Collection record not found for %s" % data.get('box_no', 'unknown box')}

        # -- CFB (Counterfeit) ------------------------------------------------
        if collection.remarks == 'CFB':
            collection.write({'state': 'paid'})
            if collection.counterfeit_note_ids:
                collection.counterfeit_note_ids.write({'state': 'paid'})

            counterfeit_donor = self.env['res.partner'].search([('name', 'ilike', 'Counterfeit')], limit=1)
            if not counterfeit_donor:
                counterfeit_donor = self.env['res.partner'].create({
                    'name': 'Counterfeit Donor', 'is_company': False, 'customer_rank': 1,
                })
            self._bn_mark_collection_issuance(collection, is_cfb=True)
            return {"status": "success", "donor_id": counterfeit_donor.id, "is_cfb": True}

        # -- FCB (Foreign currency) --------------------------------------------
        if collection.remarks == 'FCB':
            collection.write({'state': 'paid'})
            foreign_currency_lines = self.env['foreign.currency'].search([
                ('rider_collection_id', '=', collection.id)])
            lines_to_update = foreign_currency_lines.filtered(lambda line: line.state == 'payment_received')
            if lines_to_update:
                lines_to_update.write({'state': 'paid'})

            fcb_donor = self.env['res.partner'].search([('name', 'ilike', 'Foreign Currency Donor')], limit=1)
            if not fcb_donor:
                fcb_donor = self.env['res.partner'].create({
                    'name': 'Foreign Currency Donor', 'is_company': False, 'customer_rank': 1,
                })
            self._bn_mark_collection_issuance(collection, is_fcb=True)
            return {"status": "success", "donor_id": fcb_donor.id, "is_fcb": True}

        # -- Normal collection ---------------------------------------------------
        if collection.state != 'donation_submit':
            return {"status": "error", "body": "Please first submit your Collection against %s" % data.get('box_no')}

        try:
            amount = float(data.get('amount'))
        except (TypeError, ValueError):
            return {"status": "error", "body": "Invalid amount for %s" % data.get('box_no')}
        if collection.amount != amount:
            return {"status": "error", "body": "Please enter the correct amount collected against %s" % data.get('box_no')}

        issuance = self.sudo().search([('rider_collection_id', '=', collection_id)], limit=1)
        if not issuance:
            issuance = self.sudo().search([
                ('key_id.lot_id', '=', data.get('lot_id')),
                ('issue_date', '=', data.get('date')),
                ('state', 'in', ['issued', 'overdue']),
            ], limit=1)
        if not issuance:
            return {"status": "error", "body": "Invalid Donation Box"}

        # The issuance's own registration: a reused box number also has closed ones.
        box = issuance.donation_box_registration_installation_id or self.env['donation.box.registration.installation'].search([
            ('lot_id', '=', data.get('lot_id')),
            ('status', '!=', 'close'),
            ('shop_name', '=', data.get('shop_name')),
            ('contact_person', '=', data.get('contact_person')),
            ('contact_no', '=', data.get('contact_number')),
            ('location', '=', data.get('box_location')),
        ], limit=1)

        if not data.get('check_validation'):
            issuance._bn_write({'donation_amount': amount})
            issuance.action_donation_receive()
            collection.state = 'paid'
            return {"status": "success"}

        return {"status": "success", "id": issuance.id, "donor_id": box.donor_id.id}

    def _bn_mark_collection_issuance(self, collection, is_fcb=False, is_cfb=False):
        """CFB/FCB collections have no real box return: close their issuance record
        (if any) explicitly so it does not block a later bulk issuance of its bunch."""
        issuance = self.sudo().search([('rider_collection_id', '=', collection.id)], limit=1)
        if issuance and issuance.state in ('issued', 'overdue', 'pending'):
            issuance._bn_write({
                'state': 'returned',
                'returned_on': fields.Datetime.now(),
                'is_fcb': is_fcb,
                'is_cfb': is_cfb,
            })
            issuance.key_id._bn_lock()
            issuance.key_id._bn_write({'state': 'available'})
