# -*- coding: utf-8 -*-
import contextvars
import re

from odoo import api, fields, models, _

# Values of these fields are never stored, only the fact that they changed.
SECRET_FIELD_PATTERN = re.compile(
    r'(^|_)(password|passwd|pwd|secret|token|apikey|api_key|totp|otp|'
    r'private_key|signing_key|access_key|secret_key)(_|$)')
MASK = '********'

# Set while the web client reads one audit log entry, so the sub-operation
# rows displayed inside it are not logged as separate views.
_VIEWING_LOG = contextvars.ContextVar('bn_audit_viewing_log', default=False)


def outer_hands_up(frame, outer):
    """Pass the entries of a finished frame to the frame that was running
    around it (pure Python, no SQL)."""
    own = frame['own']
    if (frame['kind'] == 'read' and not outer['own'] and outer['kind'] == 'read'
            and outer['model'] == frame['model']):
        # The same read seen through several layers
        # (web_search_read > web_read > read): still the outer's own entry.
        outer['own'] += own
        if not own:
            outer['children'] += frame['children']
        outer['descendants'] += frame['descendants']
    else:
        outer['children'] += own or frame['children']
        outer['descendants'] += own + frame['descendants']


class AuditTrailLog(models.Model):
    """One row per audited create / update / delete / view of one record.

    Rows are linked into operations: ``parent_id`` is the entry that was
    running when this one happened (e.g. "Updated SO001" for the stock move
    it created), and every row of one top-level operation shares the same
    ``operation_ref``.
    """
    _name = 'audit.trail.log'
    _description = 'Audit Trail Log'
    _order = 'date desc, id desc'
    _rec_name = 'summary'

    user_id = fields.Many2one('res.users', string='User', required=True, index=True)
    # Not required / set null: uninstalling a module deletes its ir.model
    # rows, which must not delete the audit history of its records.
    model_id = fields.Many2one('ir.model', string='Model', ondelete='set null', index=True)
    model_name = fields.Char(string='Technical Model', index=True)
    res_id = fields.Integer(string='Record ID', index=True)
    record_name = fields.Char(string='Record')
    method = fields.Selection([
        ('create', 'Create'),
        ('write', 'Update'),
        ('unlink', 'Delete'),
        ('read', 'View'),
    ], string='Action', required=True, index=True)
    date = fields.Datetime(string='Date', default=fields.Datetime.now,
                            index=True, required=True)
    summary = fields.Char(string='Summary')
    is_sudo = fields.Boolean(
        string='Internal (sudo)', index=True,
        help="Done by program code running with superuser rights on behalf "
             "of the user, not directly by the user.")
    line_ids = fields.One2many('audit.trail.log.line', 'log_id',
                                string='Field Changes')

    parent_id = fields.Many2one('audit.trail.log', string='Triggered By',
                                ondelete='cascade', index=True, readonly=True)
    child_ids = fields.One2many('audit.trail.log', 'parent_id', string='Sub-Operations')
    child_count = fields.Integer(compute='_compute_child_count', string='Sub-Operations Count')
    operation_ref = fields.Char(string='Operation', index=True, readonly=True,
                                help="Shared by every entry of one top-level operation.")
    operation_log_ids = fields.Many2many(
        'audit.trail.log', compute='_compute_operation_log_ids',
        string='Whole Operation')
    is_root = fields.Boolean(compute='_compute_is_root', search='_search_is_root',
                             string='Top-Level')

    # ---------------------------------------------------------------
    # Computes
    # ---------------------------------------------------------------
    def _compute_child_count(self):
        data = self._read_group([('parent_id', 'in', self.ids)], ['parent_id'], ['__count'])
        counts = {parent.id: count for parent, count in data}
        for log in self:
            log.child_count = counts.get(log.id, 0)

    def _compute_operation_log_ids(self):
        refs = [ref for ref in self.mapped('operation_ref') if ref]
        others = self.search([('operation_ref', 'in', refs)], order='id') if refs else self.browse()
        for log in self:
            log.operation_log_ids = others.filtered(
                lambda o: o.operation_ref == log.operation_ref and o != log) if log.operation_ref else False

    @api.depends('parent_id')
    def _compute_is_root(self):
        for log in self:
            log.is_root = not log.parent_id

    def _search_is_root(self, operator, value):
        positive = (operator == '=') == bool(value)
        return [('parent_id', '=' if positive else '!=', False)]

    # ---------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------
    def _safe_display_name(self, rec):
        try:
            return rec.display_name
        except Exception:
            return '%s,%s' % (rec._name, rec.id)

    def _field_string(self, model_name, field_name):
        field = self.env[model_name]._fields.get(field_name)
        return field.string if field else field_name

    @api.model
    def _is_secret_field(self, model_name, field_name):
        model = self.env.registry.get(model_name)
        field = model._fields.get(field_name) if model is not None else None
        if field is not None and field.groups == '.':
            # fields.NO_ACCESS: nobody may read it (e.g. the 2FA secret).
            return True
        return bool(SECRET_FIELD_PATTERN.search(field_name))

    def _format_value(self, model_name, field_name, value):
        """Best-effort human readable rendering of a field value, whether it
        comes as a raw create()/write() value or as a live recordset."""
        if self._is_secret_field(model_name, field_name):
            return MASK if value else ''
        field = self.env[model_name]._fields.get(field_name)
        if field is None:
            return str(value) if value not in (False, None) else ''
        try:
            if field.type == 'many2one':
                if not value:
                    return ''
                if isinstance(value, models.BaseModel):
                    return value.exists() and value.display_name or ''
                rec = self.env[field.comodel_name].sudo().browse(value)
                return rec.exists() and rec.display_name or str(value)
            if field.type in ('many2many', 'one2many'):
                if isinstance(value, models.BaseModel):
                    return ', '.join(value.mapped('display_name'))
                if isinstance(value, (list, tuple)):
                    return _('%s change command(s)') % len(value)
                return str(value)
            if field.type == 'selection':
                selection = field.selection
                if callable(selection) or isinstance(selection, str):
                    selection = field._description_selection(self.env)
                sel_dict = dict(selection) if selection else {}
                return str(sel_dict.get(value, value))
            if field.type == 'boolean':
                return _('Yes') if value else _('No')
            if field.type == 'binary':
                return _('<binary data>') if value else ''
            return str(value) if value not in (False, None) else ''
        except Exception:
            return str(value)

    def _new_value(self, rec, fname, raw_value):
        """Value to show as "After": for x2many fields the commands sent to
        create()/write() are unreadable, so show the resulting records."""
        field = rec._fields[fname]
        if field.type in ('many2many', 'one2many') and not self._is_secret_field(rec._name, fname):
            try:
                return rec.with_context(_audit_trail_skip_read=True)[fname]
            except Exception:
                return raw_value
        return raw_value

    def _base_vals(self, model_name):
        return {
            'user_id': self.env.uid,
            'model_id': self.env['ir.model']._get_id(model_name),
            'model_name': model_name,
            'is_sudo': self.env.su,
            'date': fields.Datetime.now(),
        }

    def _create_logs(self, vals_list, kind):
        logs = self.sudo().create(vals_list)
        self.env[logs[:1].model_name or 'base']._audit_register(logs, kind)
        return logs

    # ---------------------------------------------------------------
    # Logging entry points, called from the 'base' model override
    # ---------------------------------------------------------------
    @api.model
    def _log_create(self, records, vals_list):
        base = self._base_vals(records._name)
        logs = []
        for rec, vals in zip(records, vals_list):
            lines = []
            for fname, fval in vals.items():
                if fname not in rec._fields:
                    continue
                lines.append((0, 0, {
                    'field_name': fname,
                    'field_description': self._field_string(rec._name, fname),
                    'old_value': '',
                    'new_value': self._format_value(rec._name, fname, self._new_value(rec, fname, fval)),
                }))
            name = self._safe_display_name(rec)
            logs.append(dict(base, res_id=rec.id, record_name=name, method='create',
                             summary=_('Created %s') % name, line_ids=lines))
        if logs:
            self._create_logs(logs, 'create')

    @api.model
    def _log_write(self, records, vals, old_values):
        base = self._base_vals(records._name)
        logs = []
        for rec in records:
            old_vals = old_values.get(rec.id, {})
            lines = []
            for fname, new_val in vals.items():
                if fname not in rec._fields:
                    continue
                old_val = old_vals.get(fname)
                new_val = self._new_value(rec, fname, new_val)
                old_disp = self._format_value(rec._name, fname, old_val)
                new_disp = self._format_value(rec._name, fname, new_val)
                if self._is_secret_field(rec._name, fname):
                    if not new_val and not old_val:
                        continue
                elif old_disp == new_disp:
                    continue
                lines.append((0, 0, {
                    'field_name': fname,
                    'field_description': self._field_string(rec._name, fname),
                    'old_value': old_disp,
                    'new_value': new_disp,
                }))
            if not lines:
                continue
            name = self._safe_display_name(rec)
            logs.append(dict(base, res_id=rec.id, record_name=name, method='write',
                             summary=_('Updated %s') % name, line_ids=lines))
        if logs:
            self._create_logs(logs, 'write')

    @api.model
    def _unseen_read_rows(self, model_name, result_rows):
        """Rows not logged as viewed by this user yet in this transaction,
        so opening one form doesn't produce a dozen rows just because
        several widgets each re-read the record. Pure Python: the caller
        uses it to skip the logging savepoint entirely."""
        transaction = self.env.transaction
        seen = getattr(transaction, '_audit_read_seen', None)
        if seen is None:
            seen = transaction._audit_read_seen = set()
        rows = []
        for row in result_rows:
            key = (model_name, row.get('id'), self.env.uid)
            if key not in seen:
                seen.add(key)
                rows.append(row)
        return rows

    @api.model
    def _log_read(self, model_name, result_rows):
        """Log which user viewed which record(s) (rows already filtered by
        _unseen_read_rows)."""
        base = self._base_vals(model_name)
        records = self.env[model_name].browse([row.get('id') for row in result_rows])
        logs = []
        for row, rec in zip(result_rows, records):
            res_id = row.get('id')
            name = row.get('display_name') or self._safe_display_name(rec)
            logs.append(dict(base, res_id=res_id, record_name=name, method='read',
                             summary=_('Viewed %s') % (name or ('#%s' % res_id))))
        if logs:
            self._create_logs(logs, 'read')

    @api.model
    def _log_unlink(self, model_name, snapshot):
        """snapshot: {res_id: display_name} captured BEFORE deletion."""
        base = self._base_vals(model_name)
        logs = [dict(base, res_id=res_id, record_name=name, method='unlink',
                     summary=_('Deleted %s') % name)
                for res_id, name in snapshot.items()]
        if logs:
            self._create_logs(logs, 'unlink')

    # ---------------------------------------------------------------
    # Operation structure (frames are opened by the 'base' override)
    # ---------------------------------------------------------------
    @api.model
    def _audit_close_frame(self, frame, outer):
        """Link the entries of a finished operation.

        ``own``: entries of the operation itself; ``children``: entries
        produced while it ran that are not linked yet; ``descendants``:
        every entry produced while it ran.
        """
        own, children = frame['own'], frame['children']
        if own and children:
            self.env.cr.execute(
                "UPDATE audit_trail_log SET parent_id = %s WHERE id IN %s AND parent_id IS NULL",
                (own[0], tuple(children)))
            self.browse(children).invalidate_recordset(['parent_id'])
        if outer is not None:
            outer_hands_up(frame, outer)
        elif frame['descendants']:
            ids = own + frame['descendants']
            self.env.cr.execute(
                "UPDATE audit_trail_log SET operation_ref = %s WHERE id IN %s",
                (str(ids[0]), tuple(ids)))
            self.browse(ids).invalidate_recordset(['operation_ref'])

    # ---------------------------------------------------------------
    # Who looked at the audit trail itself
    # ---------------------------------------------------------------
    # audit.trail.log is excluded from the generic logging (it would log
    # itself endlessly). Views of the trail are logged here instead: one
    # entry per list / search, one per entry opened.
    def _log_trail_view(self, summary, res_id=0, record_name=''):
        self.sudo().create(dict(
            self._base_vals('audit.trail.log'),
            res_id=res_id, record_name=record_name or _('Audit Trail'),
            method='read', summary=summary,
        ))

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        result = super().web_search_read(domain, specification, offset=offset, limit=limit,
                                         order=order, count_limit=count_limit)
        if not _VIEWING_LOG.get():
            self._audit_safe(self._log_trail_view,
                             _('Viewed the audit trail list (%s entries)') % result.get('length', 0))
        return result

    def web_read(self, specification):
        if _VIEWING_LOG.get() or len(self) != 1:
            return super().web_read(specification)
        token = _VIEWING_LOG.set(True)
        try:
            result = super().web_read(specification)
        finally:
            _VIEWING_LOG.reset(token)
        self._audit_safe(self._log_trail_view, _('Viewed audit entry: %s') % (self.summary or self.id),
                         res_id=self.id, record_name=self.summary)
        return result

    # ---------------------------------------------------------------
    # Deleting log entries always leaves a trace
    # ---------------------------------------------------------------
    def unlink(self):
        if not self:
            return super().unlink()
        all_logs = self | self.search([('parent_id', 'child_of', self.ids)])
        dates = all_logs.mapped('date')
        count = len(all_logs)
        res = super().unlink()
        self.sudo().create(dict(
            self._base_vals('audit.trail.log'),
            res_id=0,
            record_name=_('Audit log purge'),
            method='unlink',
            summary=_('Deleted %(count)s audit log entries dated %(start)s to %(end)s') % {
                'count': count,
                'start': fields.Datetime.to_string(min(dates)),
                'end': fields.Datetime.to_string(max(dates)),
            },
        ))
        return res


class AuditTrailLogLine(models.Model):
    """A single field's before/after value within one audit log entry."""
    _name = 'audit.trail.log.line'
    _description = 'Audit Trail Log Line'

    log_id = fields.Many2one('audit.trail.log', required=True,
                              ondelete='cascade', index=True)
    field_name = fields.Char(required=True)
    field_description = fields.Char(string='Field')
    old_value = fields.Text(string='Before')
    new_value = fields.Text(string='After')
