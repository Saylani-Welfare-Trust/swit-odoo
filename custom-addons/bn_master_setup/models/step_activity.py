import ast
import logging

from odoo import _, api, models
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

ACTIVITY_TYPE = 'bn_master_setup.mail_activity_type_next_step'
# Everybody has these: a button restricted to them names no one in particular
GENERIC_GROUPS = ('base.group_user', 'base.group_portal', 'base.group_public', 'base.group_system')
PRIMARY_CLASSES = ('oe_highlight', 'btn-primary')


class StepActivityMixin(models.AbstractModel):
    """An activity for whoever has to act next on a record.

    When the record's state changes, the next step is what its form shows:
    the primary (highlighted) header buttons visible in that state, and the
    groups allowed to press them. Those people get an "Action Required"
    activity; when the record moves on, the activity of the user who acted is
    marked done and the others are removed. When the record's own owner
    (responsible user, else its creator) may do the step, only they get it.

    Steps follow the views: a new button or group needs no change here."""
    _name = 'step.activity.mixin'
    _description = 'Activities for the next approval / action step'

    _step_field = 'state'
    _step_owner_fields = ('user_id', 'create_uid')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_step_activities()
        return records

    def write(self, vals):
        res = super().write(vals)
        if self._step_field in vals:
            self._sync_step_activities()
        return res

    # ------------------------------------------------------------------
    @api.model
    def _step_buttons(self):
        """[(label, groups, invisible)] of the form's primary header buttons."""
        cache = self.env.registry.__dict__.setdefault('_step_buttons', {})
        if self._name in cache:
            return cache[self._name]
        buttons = []
        try:
            # the combined form before the per-user filtering, which drops
            # the buttons (and their groups) the current user may not press
            arch, _view = self.sudo().with_context(lang='en_US')._get_view(view_type='form')
        except Exception:  # noqa: BLE001 - no form, no steps
            arch = None
        for node in (arch.iter('button') if arch is not None else ()):
            parent = node.getparent()
            while parent is not None and parent.tag != 'header':
                parent = parent.getparent()
            classes = node.get('class') or ''
            groups = tuple(g.strip() for g in (node.get('groups') or '').split(',')
                           if g.strip() and not g.strip().startswith('!') and g.strip() not in GENERIC_GROUPS)
            if parent is None or not groups or not any(c in classes for c in PRIMARY_CLASSES):
                continue
            buttons.append((node.get('string') or node.get('name'), groups, node.get('invisible') or ''))
        cache[self._name] = buttons
        return buttons

    def _button_visible(self, expression):
        if not expression:
            return True
        try:
            names = {n.id for n in ast.walk(ast.parse(expression.strip(), mode='eval')) if isinstance(n, ast.Name)}
        except SyntaxError:
            return False
        values = {'context': {}, 'uid': self.env.uid, 'True': True, 'False': False, 'None': None}
        for name in names - set(values):
            if name not in self._fields:
                return False   # depends on something we cannot know here
            field, value = self._fields[name], self[name]
            if field.type == 'many2one':
                value = value.id or False
            elif field.type in ('one2many', 'many2many'):
                value = value.ids
            elif field.type in ('date', 'datetime') and value:
                value = str(value)
            values[name] = value
        try:
            return not safe_eval(expression, values)
        except Exception:  # noqa: BLE001
            return False

    def _step_assignees(self):
        """{user: [button labels]} of whoever has to act on this record now."""
        self.ensure_one()
        assignees = {}
        owner = self.env['res.users']
        for fname in self._step_owner_fields:
            if fname in self._fields and self._fields[fname].comodel_name == 'res.users' and self[fname]:
                owner = self[fname]
                break
        for label, groups, invisible in self._step_buttons():
            if not self._button_visible(invisible):
                continue
            users = self.env['res.users']
            for xmlid in groups:
                group = self.env.ref(xmlid, raise_if_not_found=False)
                if group:
                    users |= group.sudo().users
            users = users.filtered(lambda u: u.active and not u.share)
            if owner and owner in users:
                users = owner
            for user in users:
                assignees.setdefault(user, []).append(label)
        return assignees

    def _sync_step_activities(self):
        if self.env.context.get('no_step_activity') or not self:
            return
        activity_type = self.env.ref(ACTIVITY_TYPE, raise_if_not_found=False)
        if not activity_type or 'activity_ids' not in self._fields:
            return
        for record in self.sudo():
            try:
                with self.env.cr.savepoint():
                    record._sync_one(activity_type)
            except Exception as e:  # noqa: BLE001 - an activity must never block the step
                _logger.warning('%s: next-step activity not updated: %s', record.display_name, e)

    def _sync_one(self, activity_type):
        current = self.activity_ids.filtered(lambda a: a.activity_type_id == activity_type)
        mine = current.filtered(lambda a: a.user_id == self.env.user)
        if mine:
            mine.action_feedback(feedback=_('Done: the record moved on.'))
        (current - mine).unlink()
        state_label = dict(self._fields[self._step_field]._description_selection(self.env)).get(
            self[self._step_field], self[self._step_field])
        for user, labels in self._step_assignees().items():
            self.activity_schedule(
                ACTIVITY_TYPE, user_id=user.id,
                summary=_('%(actions)s: %(record)s', actions=' / '.join(dict.fromkeys(labels)),
                          record=self.display_name),
                note=_('%(record)s is waiting for you (%(state)s).', record=self.display_name, state=state_label))
