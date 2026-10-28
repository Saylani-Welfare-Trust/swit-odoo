# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools import float_compare


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
        """POS Donation Box screen. With check_validation (the popup) the box
        is only checked and its donor returned; the collection is closed when
        the POS order is saved (pos.order._process_order), never before."""
        result, collection, issuance = self._bn_check_donation_box(data)
        if result.get('status') != 'success' or (data or {}).get('check_validation'):
            return result
        self._bn_apply_donation_box(collection, issuance, data)
        return {"status": "success"}

    def _bn_special_donor(self, name):
        donor = self.env['res.partner'].sudo().search([('name', 'ilike', name)], limit=1)
        return donor or self.env['res.partner'].sudo().create({
            'name': name, 'is_company': False, 'customer_rank': 1,
        })

    def _bn_check_donation_box(self, data):
        """(result, collection, issuance) - nothing is written."""
        none = self.env['rider.collection'], self.browse()
        if not data:
            return ({"status": "error", "body": "Please specify Key and Collection Amount"},) + none
        collection_id = data.get('collection_id')
        if not collection_id:
            return ({"status": "error", "body": "Collection ID is required"},) + none
        collection = self.env['rider.collection'].sudo().browse(collection_id).exists()
        if not collection:
            return ({"status": "error", "body": "Collection record not found for %s" % data.get('box_no', 'unknown box')},) + none
        if collection.state == 'paid':
            return ({"status": "error", "body": "The collection of %s is already paid." % data.get('box_no', '')},) + none

        # CFB (counterfeit notes) / FCB (foreign currency): no box amount to match
        if collection.remarks == 'CFB':
            donor = self._bn_special_donor('Counterfeit Donor')
            return {"status": "success", "donor_id": donor.id, "is_cfb": True}, collection, self.browse()
        if collection.remarks == 'FCB':
            donor = self._bn_special_donor('Foreign Currency Donor')
            return {"status": "success", "donor_id": donor.id, "is_fcb": True}, collection, self.browse()

        if collection.state != 'donation_submit':
            return ({"status": "error", "body": "Please first submit your Collection against %s" % data.get('box_no')},) + none
        try:
            amount = float(data.get('amount'))
        except (TypeError, ValueError):
            return ({"status": "error", "body": "Invalid amount for %s" % data.get('box_no')},) + none
        if float_compare(collection.amount, amount, precision_digits=2):
            return ({"status": "error", "body": "Please enter the correct amount collected against %s" % data.get('box_no')},) + none

        issuance = self.sudo().search([('rider_collection_id', '=', collection.id)], limit=1)
        if not issuance:
            issuance = self.sudo().search([
                ('key_id.lot_id', '=', data.get('lot_id')),
                ('issue_date', '=', data.get('date')),
                ('state', 'in', ['issued', 'overdue']),
            ], limit=1)
        if not issuance:
            return ({"status": "error", "body": "Invalid Donation Box"},) + none

        # The issuance's own registration: a reused box number also has closed ones.
        box = issuance.donation_box_registration_installation_id or self.env['donation.box.registration.installation'].sudo().search([
            ('lot_id', '=', data.get('lot_id')),
            ('status', '!=', 'close'),
            ('shop_name', '=', data.get('shop_name')),
            ('contact_person', '=', data.get('contact_person')),
            ('contact_no', '=', data.get('contact_number')),
            ('location', '=', data.get('box_location')),
        ], limit=1)
        return {"status": "success", "id": issuance.id, "donor_id": box.donor_id.id}, collection, issuance

    def _bn_apply_donation_box(self, collection, issuance, data):
        """Close the collection paid at the POS."""
        collection = collection.sudo()
        if collection.remarks == 'CFB':
            collection.write({'state': 'paid'})
            collection.counterfeit_note_ids.write({'state': 'paid'})
            self._bn_mark_collection_issuance(collection, is_cfb=True)
        elif collection.remarks == 'FCB':
            collection.write({'state': 'paid'})
            self.env['foreign.currency'].sudo().search([
                ('rider_collection_id', '=', collection.id),
                ('state', '=', 'payment_received'),
            ]).write({'state': 'paid'})
            self._bn_mark_collection_issuance(collection, is_fcb=True)
        else:
            issuance._bn_write({'donation_amount': float(data.get('amount'))})
            issuance.action_donation_receive()
            collection.state = 'paid'

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
