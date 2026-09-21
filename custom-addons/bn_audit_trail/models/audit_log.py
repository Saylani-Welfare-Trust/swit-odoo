# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class AuditTrailLog(models.Model):
    """One row per audited create / update / delete."""
    _name = 'audit.trail.log'
    _description = 'Audit Trail Log'
    _order = 'date desc, id desc'
    _rec_name = 'summary'

    user_id = fields.Many2one('res.users', string='User', required=True, index=True)
    model_id = fields.Many2one('ir.model', string='Model', ondelete='cascade', required=True, index=True)
    model_name = fields.Char(related='model_id.model', store=True, index=True,
                              string='Technical Model')
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
    line_ids = fields.One2many('audit.trail.log.line', 'log_id',
                                string='Field Changes')

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

    def _format_value(self, model_name, field_name, value):
        """Best-effort human readable rendering of a field value, whether it
        comes as a raw create()/write() value or as a live recordset."""
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
                if callable(selection):
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

    # ---------------------------------------------------------------
    # Logging entry points, called from the 'base' model override
    # ---------------------------------------------------------------
    @api.model
    def _log_create(self, records, vals_list):
        model_id = self.env['ir.model']._get_id(records._name)
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
                    'new_value': self._format_value(rec._name, fname, fval),
                }))
            name = self._safe_display_name(rec)
            logs.append({
                'user_id': self.env.uid,
                'model_id': model_id,
                'res_id': rec.id,
                'record_name': name,
                'method': 'create',
                'date': fields.Datetime.now(),
                'summary': _('Created %s') % name,
                'line_ids': lines,
            })
        if logs:
            self.sudo().create(logs)

    @api.model
    def _log_write(self, records, vals, old_values):
        model_id = self.env['ir.model']._get_id(records._name)
        logs = []
        for rec in records:
            old_vals = old_values.get(rec.id, {})
            lines = []
            for fname, new_val in vals.items():
                if fname not in rec._fields:
                    continue
                old_val = old_vals.get(fname)
                old_disp = self._format_value(rec._name, fname, old_val)
                new_disp = self._format_value(rec._name, fname, new_val)
                if old_disp == new_disp:
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
            logs.append({
                'user_id': self.env.uid,
                'model_id': model_id,
                'res_id': rec.id,
                'record_name': name,
                'method': 'write',
                'date': fields.Datetime.now(),
                'summary': _('Updated %s') % name,
                'line_ids': lines,
            })
        if logs:
            self.sudo().create(logs)

    @api.model
    def _log_read(self, model_name, result_rows):
        """Log which user viewed which record(s). Deduplicated within the
        current request/transaction so opening one form doesn't produce a
        dozen rows just because several widgets each re-read the record."""
        if not result_rows:
            return
        seen = getattr(self.env, '_audit_read_seen', None)
        if seen is None:
            seen = set()
            try:
                self.env._audit_read_seen = seen
            except Exception:
                pass  # fall back to logging without dedup for this call

        model_id = self.env['ir.model']._get_id(model_name)
        logs = []
        for row in result_rows:
            res_id = row.get('id')
            key = (model_name, res_id, self.env.uid)
            if key in seen:
                continue
            seen.add(key)
            name = row.get('display_name') or ''
            logs.append({
                'user_id': self.env.uid,
                'model_id': model_id,
                'res_id': res_id,
                'record_name': name,
                'method': 'read',
                'date': fields.Datetime.now(),
                'summary': _('Viewed %s') % (name or ('#%s' % res_id)),
            })
        if logs:
            self.sudo().create(logs)

    @api.model
    def _log_unlink(self, model_name, snapshot):
        """snapshot: {res_id: display_name} captured BEFORE deletion."""
        model_id = self.env['ir.model']._get_id(model_name)
        logs = [{
            'user_id': self.env.uid,
            'model_id': model_id,
            'res_id': res_id,
            'record_name': name,
            'method': 'unlink',
            'date': fields.Datetime.now(),
            'summary': _('Deleted %s') % name,
        } for res_id, name in snapshot.items()]
        if logs:
            self.sudo().create(logs)


class AuditTrailLogLine(models.Model):
    """A single field's before/after value within one audit log entry."""
    _name = 'audit.trail.log.line'
    _description = 'Audit Trail Log Line'

    log_id = fields.Many2one('audit.trail.log', required=True,
                              ondelete='cascade', index=True)
    field_name = fields.Char(required=True)
    field_description = fields.Char()
    old_value = fields.Text()
    new_value = fields.Text()
