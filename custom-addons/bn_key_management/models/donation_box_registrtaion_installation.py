# -*- coding: utf-8 -*-
from odoo import _, fields, models
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
    # They run as superuser: the Donation Box group checked by the calling
    # action is the gate, so its users need no Key Management rights.
    # ------------------------------------------------------------------
    def _bn_key_create(self, line):
        self.ensure_one()
        if self.sudo().key_ids:
            return self.sudo().key_ids
        key = self.env['key'].sudo().create({
            'donation_box_request_id': self.donation_box_request_id.id,
            'donation_box_registration_installation_id': self.id,
            'name': line.key_tag,
            'lot_id': self.lot_id.id,
            'lock_no': self.lock_no,
        })
        return key

    # Key issuance states in which the key is still out with the rider
    _BN_KEY_OUT_STATES = ('issued', 'overdue', 'pending', 'donation_receive')

    def _bn_open_issuances(self, bunches=None):
        """Open issuances of this registration's keys and of every key of its
        bunch(es): a bunch goes out with a rider as a whole, so nothing about a
        box of the bunch changes until the whole bunch is back."""
        self.ensure_one()
        keys = self.sudo().key_ids
        bunches = (bunches or self.env['key.bunch']) | self.sudo().key_bunch_id | keys.key_bunch_id
        keys |= bunches.sudo().key_ids
        return self.env['key.issuance'].sudo().search([
            ('key_id', 'in', keys.ids), ('state', 'in', self._BN_KEY_OUT_STATES)])

    def _bn_raise_if_out(self, message, bunches=None):
        self.ensure_one()
        issuances = self._bn_open_issuances(bunches)
        if issuances:
            lines = '\n'.join('- %s: %s (%s)' % (
                i.key_id.display_name, i.rider_id.display_name,
                i._bn_selection_label('state', i.state)) for i in issuances[:20])
            raise ValidationError('%s\n%s' % (message, lines))

    def _bn_key_activate(self):
        self.ensure_one()
        if not self.key_bunch_id:
            raise ValidationError(_('Please select a Key Bunch before approving.'))
        keys = self.sudo().key_ids.filtered(lambda k: k.state != 'closed')
        if not keys:
            raise ValidationError(_('No key found for this registration.'))
        # the key leaves its bunch for this one: neither may be out with a rider
        self._bn_raise_if_out(_(
            'Box "%s" cannot be approved while its key bunch, or the bunch it moves to, '
            'is out with a rider. Return these keys first:') % self.lot_id.display_name,
            bunches=self.key_bunch_id)
        for key in keys:
            key._bn_lock()
            key._bn_make_available(self.key_bunch_id)
        return True

    def _bn_key_change_request(self):
        self.ensure_one()
        self._bn_raise_if_out(_(
            'A change cannot be requested for box "%s" while its key bunch is out with a '
            'rider. The whole bunch must be returned first:') % self.lot_id.display_name)
        return True

    def _bn_key_close(self):
        self.ensure_one()
        for key in self.sudo().key_ids.filtered(lambda k: k.state != 'closed'):
            key._bn_lock()
            key._bn_close()
        return True

    def _bn_check_can_release(self):
        self.ensure_one()
        self._bn_raise_if_out(_(
            'Box "%s" cannot be returned while its key bunch is out with a rider. '
            'Return these keys first:') % self.lot_id.display_name)
        return True

    def _bn_unreturned_key_messages(self):
        self.ensure_one()
        return [_('%(key)s — issued to %(rider)s (%(state)s)') % {
            'key': issuance.key_id.display_name,
            'rider': issuance.rider_id.display_name,
            'state': issuance._bn_selection_label('state', issuance.state),
        } for issuance in self._bn_open_issuances()]
