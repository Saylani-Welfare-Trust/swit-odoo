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
    _inherit = ["mail.thread", "mail.activity.mixin", "bn.workflow.mixin"]
    # _inherit = ["mail.thread", "mail.activity.mixin"]
    _bn_guarded_fields = ('state', 'key_bunch_id')

    donation_box_request_id = fields.Many2one('donation.box.request', string="Donation Box Request")
    donation_box_registration_installation_id = fields.Many2one(
        'donation.box.registration.installation', string="Donation Box Registration", index=True)
    # Assigned when the registration is approved (see the registration's _bn_key_activate).
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

    def unlink(self):
        if not self.env.su:
            raise UserError(_('Keys cannot be deleted. They are closed automatically by the donation box workflow.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Workflow (internal: keys are moved by the registration / issuance workflows)
    # ------------------------------------------------------------------
    def _bn_lock(self):
        """Serialise concurrent issue/return operations on the same keys."""
        if self.ids:
            self.env.cr.execute('SELECT id FROM "key" WHERE id IN %s FOR UPDATE', (tuple(self.ids),))
            self.invalidate_recordset(['state'])

    def _bn_make_available(self, bunch=None):
        vals = {'state': 'available'}
        if bunch:
            vals['key_bunch_id'] = bunch.id
        self._bn_write(vals)

    def _bn_close(self):
        self._bn_write({'state': 'closed', 'key_bunch_id': False})

    def action_available(self):
        """Kept for backward compatibility. Keys can no longer be made available by hand:
        that skipped the approval of the donation box registration."""
        raise UserError(_(
            'A key becomes available when its Donation Box registration is approved '
            '(Registration / Installation > Approved).'))
