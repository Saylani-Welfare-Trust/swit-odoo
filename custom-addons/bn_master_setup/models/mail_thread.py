# -*- coding: utf-8 -*-
from odoo import models, tools

# Field types the chatter can show a change of (mail.tracking.value)
TRACKABLE_TYPES = {
    'char', 'text', 'integer', 'float', 'monetary', 'date', 'datetime',
    'boolean', 'selection', 'many2one', 'many2many',
}
# Bookkeeping fields: never tracked
UNTRACKED_FIELDS = {
    'id', 'display_name', 'create_uid', 'create_date', 'write_uid', 'write_date',
    'sequence', 'color', 'access_token', 'access_url',
}


class MailThread(models.AbstractModel):
    """Maximum tracking on the SWIT (bn_*) documents.

    Every stored field a user can change is tracked in the chatter, without
    ``tracking=True`` on each definition: fields added later are tracked too.
    One2many lines are left out (changes of the lines themselves are not
    tracked by Odoo; their own chatter shows them), as are binary / html
    contents and related fields (their own record tracks them)."""
    _inherit = 'mail.thread'

    @tools.ormcache('self.env.uid', 'self.env.su')
    def _track_get_fields(self):
        tracked = super()._track_get_fields() or set()
        if not (self._original_module or '').startswith('bn_'):
            return tracked
        extra = {
            name for name, field in self._fields.items()
            if field.store and not field.related
            and field.type in TRACKABLE_TYPES
            and name not in UNTRACKED_FIELDS
            and not name.startswith(('message_', 'activity_', 'website_message', 'rating_'))
        }
        # fields the user may not read are left out, as Odoo does for tracked fields
        return tracked | set(self.fields_get(extra, attributes=()))
