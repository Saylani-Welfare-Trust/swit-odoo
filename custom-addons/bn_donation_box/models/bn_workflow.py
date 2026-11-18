# -*- coding: utf-8 -*-
"""
Shared workflow-guard helpers for the Donation Box family of modules
(bn_donation_box, bn_key_management, bn_rider_shift).

Why this exists
---------------
The workflow buttons are reachable from several places (form headers, list
headers, server actions, wizards, inline-editable lists, POS RPC calls ...).
Hiding a button with ``invisible=`` is only cosmetic: anybody can still call
the Python method, or simply ``write()`` the state field.  Every workflow
model therefore:

* checks the *user's group* inside the method,
* checks the *current state* inside the method,
* refuses direct ``write()`` calls on its state fields unless the write comes
  from one of its own workflow methods.

The "I am inside a legitimate transition" marker is a Python ``ContextVar`` and
NOT an Odoo ``context`` key on purpose: an RPC client can put any key it likes
in ``context``, but it cannot touch server side Python state.
"""
import contextlib
import contextvars

from odoo import _, models
from odoo.exceptions import AccessError, UserError

_BN_TRANSITION = contextvars.ContextVar('bn_donation_box_transition', default=False)


@contextlib.contextmanager
def bn_transition():
    """Mark the enclosed block as a legitimate workflow transition."""
    token = _BN_TRANSITION.set(True)
    try:
        yield
    finally:
        _BN_TRANSITION.reset(token)


def in_transition():
    return _BN_TRANSITION.get()


class BnWorkflowMixin(models.AbstractModel):
    _name = 'bn.workflow.mixin'
    _description = 'BytesNode Workflow Guard Mixin'

    # Fields that may only be changed by the model's own workflow methods.
    _bn_guarded_fields = ()

    # ------------------------------------------------------------------
    # Direct write protection
    # ------------------------------------------------------------------
    def write(self, vals):
        if self._bn_guarded_fields and not self.env.su and not _BN_TRANSITION.get():
            touched = [name for name in self._bn_guarded_fields if name in vals]
            if touched:
                labels = ', '.join(self._fields[name].string for name in touched)
                raise UserError(_(
                    'The field(s) "%s" cannot be edited directly. '
                    'Please use the workflow buttons of the record.'
                ) % labels)
        return super().write(vals)

    def _bn_write(self, vals):
        """Write ``vals`` as a legitimate workflow transition."""
        with bn_transition():
            return self.write(vals)

    # ------------------------------------------------------------------
    # Permission helpers
    # ------------------------------------------------------------------
    def _bn_user_has_any_group(self, *xmlids):
        user = self.env.user
        if self.env.su or user.has_group('base.group_system'):
            return True
        return any(user.has_group(xmlid) for xmlid in xmlids)

    def _bn_require_group(self, *xmlids):
        """Raise ``AccessError`` unless the user is in one of ``xmlids``
        (or is an administrator)."""
        if self._bn_user_has_any_group(*xmlids):
            return
        names = []
        for xmlid in xmlids:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            names.append(group.full_name if group else xmlid)
        raise AccessError(_(
            'You are not allowed to perform this action. '
            'Required access group: %s.'
        ) % ' / '.join(names))

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def _bn_selection_label(self, field, value):
        selection = dict(self._fields[field]._description_selection(self.env))
        return selection.get(value, value)

    def _bn_check_state(self, field, allowed, action):
        """Raise unless every record is in one of the ``allowed`` states."""
        for rec in self:
            current = rec[field]
            if current not in allowed:
                raise UserError(_(
                    '"%(action)s" is not allowed for "%(record)s" because it is in status '
                    '"%(current)s". Allowed status: %(allowed)s.'
                ) % {
                    'action': action,
                    'record': rec.display_name,
                    'current': self._bn_selection_label(field, current),
                    'allowed': ', '.join(self._bn_selection_label(field, a) for a in allowed),
                })

    def _bn_check_required(self, field_names):
        """Raise a single readable error listing every empty required field."""
        for rec in self:
            missing = [rec._fields[name].string for name in field_names if not rec[name]]
            if missing:
                raise UserError(_(
                    'Cannot continue with "%(record)s". Please fill in: %(fields)s.'
                ) % {'record': rec.display_name, 'fields': ', '.join(missing)})
