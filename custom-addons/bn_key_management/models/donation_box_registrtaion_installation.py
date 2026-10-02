# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DonationBoxRegistrationInstallation(models.Model):
    _inherit = 'donation.box.registration.installation'

    # The bunch the key WILL be stored in once the registration is approved.
    # Guarded: it only takes effect through _bn_key_activate(), so picking it on the
    # form does not attach the (still draft) key to the bunch early.
    key_bunch_id = fields.Many2one('key.bunch', string="Key Bunch", tracking=True)

    key_ids = fields.One2many('key', 'donation_box_registration_installation_id', string="Keys")

    def _bn_required_for_approval(self):
        # city_id / zone_id / sub_zone_id from the base module, plus the bunch the key
        # will be stored in.
        return super()._bn_required_for_approval() + ['key_bunch_id']

    # ------------------------------------------------------------------
    # Hooks called by donation.box.request / donation.box.request.line /
    # donation.box.complain.center (see bn_donation_box).
    # ------------------------------------------------------------------
    def _bn_key_create(self, line):
        self.ensure_one()
        if self.key_ids:
            return self.key_ids
        key = self.env['key'].create({
            'donation_box_request_id': self.donation_box_request_id.id,
            'donation_box_registration_installation_id': self.id,
            'name': line.key_tag,
            'lot_id': self.lot_id.id,
            'lock_no': self.lock_no,
        })
        return key

    def _bn_key_activate(self):
        self.ensure_one()
        if not self.key_bunch_id:
            raise ValidationError(_('Please select a Key Bunch before approving.'))
        keys = self.key_ids.filtered(lambda k: k.state != 'closed')
        if not keys:
            raise ValidationError(_('No key found for this registration.'))
        for key in keys:
            key._bn_lock()
            key._bn_make_available(self.key_bunch_id)
        return True

    def _bn_key_change_request(self):
        self.ensure_one()
        open_issuance = self.env['key.issuance'].search([
            ('key_id', 'in', self.key_ids.ids),
            ('state', 'in', ('issued', 'overdue', 'pending', 'donation_receive')),
        ], limit=1)
        if open_issuance:
            raise ValidationError(_(
                'Key "%(key)s" is currently issued to %(rider)s. It must be returned before '
                'requesting a change.'
            ) % {'key': open_issuance.key_id.display_name, 'rider': open_issuance.rider_id.display_name})
        return True

    def _bn_key_close(self):
        self.ensure_one()
        for key in self.key_ids.filtered(lambda k: k.state != 'closed'):
            key._bn_lock()
            key._bn_close()
        return True

    def _bn_check_can_release(self):
        self.ensure_one()
        open_issuance = self.env['key.issuance'].search([
            ('key_id', 'in', self.key_ids.ids),
            ('state', 'in', ('issued', 'overdue', 'pending', 'donation_receive')),
        ], limit=1)
        if open_issuance:
            raise ValidationError(_(
                'Cannot return box "%(box)s": its key is currently issued to %(rider)s.'
            ) % {'box': self.lot_id.display_name, 'rider': open_issuance.rider_id.display_name})
        return True

    def _bn_unreturned_key_messages(self):
        self.ensure_one()
        messages = []
        open_issuance = self.env['key.issuance'].search([
            ('key_id', 'in', self.key_ids.ids),
            ('state', 'in', ('issued', 'overdue', 'pending', 'donation_receive')),
        ])
        for issuance in open_issuance:
            messages.append(_('%(key)s — issued to %(rider)s (%(state)s)') % {
                'key': issuance.key_id.display_name,
                'rider': issuance.rider_id.display_name,
                'state': issuance._bn_selection_label('state', issuance.state),
            })
        return messages
