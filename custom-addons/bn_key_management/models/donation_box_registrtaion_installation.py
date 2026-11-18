# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DonationBoxRegistrationInstallation(models.Model):
    _inherit = 'donation.box.registration.installation'

    # The bunch the key WILL be stored in once the registration is approved.
    # Guarded: it only takes effect through _key_activate(), so picking it on the
    # form does not attach the (still draft) key to the bunch early.
    key_bunch_id = fields.Many2one('key.bunch', string="Key Bunch", tracking=True)

    key_ids = fields.One2many('key', 'donation_box_registration_installation_id', string="Keys")

    def _required_for_approval(self):
        # city_id / zone_id / sub_zone_id from the base module, plus the bunch the key
        # will be stored in.
        return super()._required_for_approval() + ['key_bunch_id']

    # ------------------------------------------------------------------
    # Hooks called by donation.box.request / donation.box.request.line /
    # donation.box.complain.center (see bn_donation_box).
    # They run as superuser: the Donation Box group checked by the calling
    # action is the gate, so its users need no Key Management rights.
    # ------------------------------------------------------------------
    def _key_create(self, line):
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

    def _sync_key_lock_no(self, lock_no):
        self.ensure_one()
        keys = self.sudo().key_ids.filtered(lambda k: k.lot_id == self.lot_id and k.lock_no != lock_no)
        keys.write({'lock_no': lock_no})
        return True

    # Key issuance states in which the key is still out with the rider
    _KEY_OUT_STATES = ('issued', 'overdue', 'pending', 'donation_receive')

    def _open_issuances(self, bunches=None):
        """Open issuances of this registration's keys and of every key of its
        bunch(es): a bunch goes out with a rider as a whole, so nothing about a
        box of the bunch changes until the whole bunch is back."""
        self.ensure_one()
        keys = self.sudo().key_ids
        bunches = (bunches or self.env['key.bunch']) | self.sudo().key_bunch_id | keys.key_bunch_id
        keys |= bunches.sudo().key_ids
        return self.env['key.issuance'].sudo().search([
            ('key_id', 'in', keys.ids), ('state', 'in', self._KEY_OUT_STATES)])

    def _out_keys(self, bunches=None):
        """Keys of this registration and of its bunch(es) whose status still says
        they are with a rider (Issued / Pending), even without an open issuance."""
        self.ensure_one()
        keys = self.sudo().key_ids
        bunches = (bunches or self.env['key.bunch']) | self.sudo().key_bunch_id | keys.key_bunch_id
        keys |= bunches.sudo().key_ids
        return keys.filtered(lambda k: k.state in ('issued', 'pending'))

    def _raise_if_out(self, message, bunches=None):
        self.ensure_one()
        issuances = self._open_issuances(bunches)
        lines = ['- %s: %s (%s)' % (
            i.key_id.display_name, i.rider_id.display_name,
            i._selection_label('state', i.state)) for i in issuances[:20]]
        for key in self._out_keys(bunches) - issuances.key_id:
            lines.append('- %s: %s' % (key.display_name, key._selection_label('state', key.state)))
        if lines:
            raise ValidationError('%s\n%s' % (message, '\n'.join(lines[:20])))

    def _key_activate(self):
        self.ensure_one()
        if not self.key_bunch_id:
            raise ValidationError(_('Please select a Key Bunch before approving.'))
        keys = self.sudo().key_ids.filtered(lambda k: k.state != 'closed')
        if not keys:
            raise ValidationError(_('No key found for this registration.'))
        # the key leaves its bunch for this one: neither may be out with a rider
        self._raise_if_out(_(
            'Box "%s" cannot be approved while its key bunch, or the bunch it moves to, '
            'is out with a rider. Return these keys first:') % self.sudo().lot_id.display_name,
            bunches=self.key_bunch_id)
        for key in keys:
            key._lock_key()
            key._make_available(self.key_bunch_id)
        return True

    def _key_change_request(self):
        self.ensure_one()
        self._raise_if_out(_(
            'A change cannot be requested for box "%s" while its key bunch is out with a '
            'rider. The whole bunch must be returned first:') % self.sudo().lot_id.display_name)
        return True

    def _key_close(self):
        """The box is out of service: its key is closed and leaves its bunch (so a
        bulk issuance of the bunch no longer hands it out), and its issuances still
        open are finished - except those with money still to settle at the POS."""
        self.ensure_one()
        self._close_key_issuances()
        for key in self.sudo().key_ids.filtered(lambda k: k.state != 'closed' or k.key_bunch_id):
            key._lock_key()
            key._close_key()
        return True

    def _close_key_issuances(self):
        """Finish the open issuances of this (closed) box's keys as Returned.
        Returns (finished, kept): ``kept`` are those whose collection still has
        money to settle at the POS (key.issuance._money_to_settle)."""
        self.ensure_one()
        issuances = self.env['key.issuance'].sudo().search([
            ('key_id', 'in', self.sudo().key_ids.ids), ('state', 'in', self._KEY_OUT_STATES)])
        kept = issuances._money_to_settle()
        finished = issuances - kept
        for issuance in finished:
            issuance._workflow_write({'state': 'returned', 'returned_on': fields.Datetime.now()})
            issuance.message_post(body=_('Returned: box %s was taken out of service.')
                                  % self.sudo().lot_id.display_name)
        return finished, kept

    # ------------------------------------------------------------------
    # Correction of boxes closed before their keys were (server action)
    # ------------------------------------------------------------------
    @api.model
    def _correct_closed_box_keys(self, records=None):
        """Boxes already Closed whose key is still Issued / Pending / Available or
        still in its bunch, or still has open issuances: the same correction as
        when a box is closed now (_key_close). ``records``: the selected
        registrations (only the Closed ones are touched), else every one."""
        self.env['key.issuance']._require_group(
            'bn_key_management.key_management_admin_group', 'bn_donation_box.donation_box_admin_group')
        Key = self.env['key'].sudo()
        Issuance = self.env['key.issuance'].sudo()
        closed = (records or self.sudo().search([])).sudo().filtered(lambda r: r.status == 'close')
        to_fix = closed.filtered(lambda r: r.key_ids.filtered(lambda k: k.state != 'closed' or k.key_bunch_id)
                                 or Issuance.search_count([('key_id', 'in', r.key_ids.ids),
                                                           ('state', 'in', self._KEY_OUT_STATES)]))
        keys_before = to_fix.key_ids.filtered(lambda k: k.state != 'closed' or k.key_bunch_id)
        finished = kept = Issuance
        for registration in to_fix:
            done, waiting = registration._close_key_issuances()
            finished |= done
            kept |= waiting
            for key in registration.key_ids.filtered(lambda k: k.state != 'closed' or k.key_bunch_id):
                key._lock_key()
                key._close_key()
            registration.message_post(body=_(
                'Correction: the key of this closed box was closed and removed from its bunch; '
                '%(done)s open issuance(s) returned, %(kept)s left open with money to settle at the POS.')
                % {'done': len(done), 'kept': len(waiting)})
        # keys closed by an earlier version but still listed in a bunch
        stray = Key.search([('state', '=', 'closed'), ('key_bunch_id', '!=', False)])
        stray._workflow_write({'key_bunch_id': False})
        lines = [_('%(boxes)s closed box(es) corrected: %(keys)s key(s) closed and removed from their bunch, '
                   '%(done)s issuance(s) returned.') % {
                     'boxes': len(to_fix), 'keys': len(keys_before), 'done': len(finished)}]
        if stray:
            lines.append(_('%s closed key(s) removed from their bunch.') % len(stray))
        if kept:
            lines.append(_('Left open, money still to settle at the POS: %s') % ', '.join(
                '%s (%s)' % (i.name, i.key_id.display_name) for i in kept[:20]))
        if not to_fix and not stray:
            lines = [_('Nothing to correct: every closed box already has its key closed.')]
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Closed Box Keys'), 'message': '\n'.join(lines),
                       'type': 'warning' if kept else 'success', 'sticky': bool(kept)},
        }

    def _check_can_release(self):
        self.ensure_one()
        self._raise_if_out(_(
            'Box "%s" cannot be returned while its key bunch is out with a rider. '
            'Return these keys first:') % self.sudo().lot_id.display_name)
        return True

    def _unreturned_key_messages(self):
        self.ensure_one()
        return [_('%(key)s — issued to %(rider)s (%(state)s)') % {
            'key': issuance.key_id.display_name,
            'rider': issuance.rider_id.display_name,
            'state': issuance._selection_label('state', issuance.state),
        } for issuance in self._open_issuances()]
