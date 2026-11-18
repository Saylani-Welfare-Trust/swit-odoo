# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

key_status = [
    ('draft', 'Draft'),
    ('available', 'Available'),
    ('issued', 'Issued'),
    ('pending', 'Pending'),
    ('closed', 'Closed'),
]

KEY_BUNCH_LIMIT = 50


class Key(models.Model):
    _name = 'key'
    _description = 'Key'
    _inherit = ["mail.thread", "mail.activity.mixin", "workflow.mixin"]
    _guarded_fields = ('state', 'key_bunch_id')

    donation_box_request_id = fields.Many2one('donation.box.request', string="Donation Box Request")
    donation_box_registration_installation_id = fields.Many2one(
        'donation.box.registration.installation', string="Donation Box Registration", index=True)
    # Assigned when the registration is approved (see the registration's _key_activate).
    # It used to be a stored related field, which attached a still-draft key to the bunch as
    # soon as the bunch was chosen on the registration form.
    key_bunch_id = fields.Many2one('key.bunch', string="Key Bunch", index=True, tracking=True)

    name = fields.Char('Key')
    lot_id = fields.Many2one('stock.lot', string="Lot", index=True)
    lock_no = fields.Char('Lock No')

    state = fields.Selection(selection=key_status, default='draft', string="Status", tracking=True, index=True)

    key_issuance_ids = fields.One2many('key.issuance', 'key_id', string="Key Issued")

    reason = fields.Text('Reason')

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('key_bunch_id')
    def _check_key_bunch_limit(self):
        for bunch in self.mapped('key_bunch_id'):
            count = self.search_count([('key_bunch_id', '=', bunch.id), ('state', '!=', 'closed')])
            if count > KEY_BUNCH_LIMIT:
                raise ValidationError(_(
                    'Key Bunch Limit Exceeded: bunch "%(bunch)s" would hold %(count)s/%(limit)s keys.'
                ) % {'bunch': bunch.display_name, 'count': count, 'limit': KEY_BUNCH_LIMIT})

    @api.constrains('lot_id', 'state')
    def _check_one_key_per_box(self):
        """Only the key of the registration in service is open; the keys of a
        box's earlier registrations are closed."""
        for key in self.filtered(lambda k: k.lot_id and k.state != 'closed'):
            other = self.sudo().search([('lot_id', '=', key.lot_id.id), ('state', '!=', 'closed'),
                                        ('id', '!=', key.id)], limit=1)
            if other:
                raise ValidationError(_(
                    'Box "%(lot)s" already has an open key (%(key)s). Close it before another one is used.'
                ) % {'lot': key.sudo().lot_id.display_name, 'key': other.display_name})

    def unlink(self):
        if not self.env.su:
            raise UserError(_('Keys cannot be deleted. They are closed automatically by the donation box workflow.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Workflow (internal: keys are moved by the registration / issuance workflows)
    # ------------------------------------------------------------------
    def _lock_key(self):
        """Serialise concurrent issue/return operations on the same keys."""
        if self.ids:
            self.env.cr.execute('SELECT id FROM "key" WHERE id IN %s FOR UPDATE', (tuple(self.ids),))
            self.invalidate_recordset(['state'])

    def _make_available(self, bunch=None):
        """Put the key (back) in service in ``bunch``. Never while the key, or a
        key of that bunch, is out with a rider: the bunch goes out as a whole."""
        out_keys = self | (bunch.sudo().key_ids if bunch else self.browse())
        out = self.env['key.issuance'].sudo().search([
            ('key_id', 'in', out_keys.ids), ('state', 'in', ('issued', 'overdue', 'pending', 'donation_receive'))], limit=1)
        busy = out.key_id or out_keys.filtered(lambda k: k.state in ('issued', 'pending'))[:1]
        if busy:
            raise ValidationError(_(
                'Key "%(key)s" cannot be made available: %(what)s is out with a rider. '
                'Return the keys of the bunch first.'
            ) % {'key': self[:1].display_name,
                 'what': _('key %s of its bunch') % busy.display_name if busy not in self else _('it')})
        vals = {'state': 'available'}
        if bunch:
            vals['key_bunch_id'] = bunch.id
        self._workflow_write(vals)

    def _close_key(self):
        self._workflow_write({'state': 'closed', 'key_bunch_id': False})
