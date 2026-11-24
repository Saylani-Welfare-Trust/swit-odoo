import logging
from collections import Counter

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# the users of these groups get every Branch / Site (national access)
# (Unrestricted Custom Access sees every warehouse today: national keeps it so)
NODE_ACCESS_GROUP_XMLID = 'bn_stock_location.group_node_access'
NATIONAL_GROUP_XMLIDS = ('base.group_system', 'account.group_account_manager', 'account.group_account_user',
                         'bn_stock_location.stock_scope_unrestricted_group')
NATIONAL_GROUP_NAME_PARTS = ('audit', 'cfo')
# the dashboards' access lists (bn_dashboard): read from their tables when they exist
DASHBOARD_RELATIONS = (
    ('treasury_user_analytic_rel', 'user_id', 'analytic_id'),
    ('pos_user_analytic_rel', 'user_id', 'analytic_id'),
    ('donation_box_user_analytic_rel', 'user_id', 'analytic_id'),
    ('pos_dd_report_user_analytic_rel', 'user_id', 'analytic_id'),
    ('res_users_livestock_analytic_rel', 'user_id', 'account_id'),
)


class NodeSetup(models.AbstractModel):
    """Fills the Branch / Site set-up from the location-based one (warehouses,
    users) and reports what needs a decision. Only empty values are filled:
    it can be run again after corrections."""
    _name = 'node.setup'
    _description = 'Branch / Site Set-up'

    # ------------------------------------------------------------------
    # Fill
    # ------------------------------------------------------------------
    @api.model
    def _fill(self):
        stats = {
            'warehouses': self._fill_warehouses(),
            'users': self._fill_users(),
            'national': self._fill_national(),
        }
        _logger.info("Branch / Site set-up filled: %s", stats)
        return stats

    @api.model
    def _warehouse_tag(self, warehouse):
        """The node of a warehouse from its locations' tags: its top location, its
        stock location, else the tag most of its locations carry."""
        tag = warehouse.view_location_id.analytic_account_id or warehouse.lot_stock_id.analytic_account_id
        if tag:
            return tag
        locations = self.env['stock.location'].sudo().search([
            ('id', 'child_of', warehouse.view_location_id.id), ('analytic_account_id', '!=', False)])
        counts = Counter(locations.mapped('analytic_account_id'))
        return counts.most_common(1)[0][0] if counts else self.env['account.analytic.account']

    @api.model
    def _fill_warehouses(self):
        filled = 0
        for warehouse in self.env['stock.warehouse'].sudo().with_context(active_test=False).search([('node_id', '=', False)]):
            tag = self._warehouse_tag(warehouse)
            if tag:
                warehouse.node_id = tag
                filled += 1
        return filled

    @api.model
    def _top_nodes(self, nodes):
        """Only the highest nodes: a node under another one of the set adds nothing."""
        return nodes.filtered(lambda node: not (nodes - node).filtered(
            lambda other: node.parent_path and other.parent_path and node.parent_path.startswith(other.parent_path)))

    @api.model
    def _dashboard_nodes(self, user):
        Account = self.env['account.analytic.account'].sudo()
        ids = set()
        for table, user_column, account_column in DASHBOARD_RELATIONS:
            self.env.cr.execute("SELECT to_regclass(%s)", (table,))
            if not self.env.cr.fetchone()[0]:
                continue
            self.env.cr.execute('SELECT "%s" FROM "%s" WHERE "%s" = %%s' % (account_column, table, user_column), (user.id,))
            ids.update(row[0] for row in self.env.cr.fetchall())
        return Account.browse(ids).exists()

    @api.model
    def _current_nodes(self, user):
        """The nodes of a user's current location-based set-up."""
        user = user.sudo()
        nodes = (user.allowed_location_ids | user.allowed_warehouse_ids.view_location_id
                 | user.allowed_warehouse_ids.lot_stock_id).analytic_account_id
        nodes |= user.allowed_warehouse_ids.node_id
        # an untagged allowed location counts for its warehouse's Branch / Site
        nodes |= user.allowed_location_ids.filtered(lambda l: not l.analytic_account_id).warehouse_id.node_id
        nodes |= user.employee_ids.analytic_account_id
        nodes |= self._dashboard_nodes(user)
        return nodes

    @api.model
    def _fill_users(self):
        filled = 0
        for user in self.env['res.users'].sudo().search([('share', '=', False), ('all_nodes', '=', False),
                                                         ('allowed_node_ids', '=', False)]):
            nodes = self._top_nodes(self._current_nodes(user))
            if nodes:
                user.allowed_node_ids = nodes
                filled += 1
        return filled

    @api.model
    def _national_groups(self):
        groups = self.env['res.groups']
        for xmlid in NATIONAL_GROUP_XMLIDS:
            groups |= self.env.ref(xmlid, raise_if_not_found=False) or self.env['res.groups']
        data = self.env['ir.model.data'].sudo().search([('model', '=', 'res.groups'), ('module', '=like', 'bn\\_%')])
        groups |= self.env['res.groups'].browse(
            data.filtered(lambda d: any(part in d.name.lower() for part in NATIONAL_GROUP_NAME_PARTS)).mapped('res_id')).exists()
        return groups

    @api.model
    def _fill_national(self):
        users = self._national_groups().users.filtered(lambda u: not u.share and not u.all_nodes)
        users.sudo().write({'all_nodes': True})
        return len(users)

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    @api.model
    def _report_data(self):
        Warehouse = self.env['stock.warehouse'].sudo()
        warehouses = Warehouse.search([])
        data = {
            'no_node': warehouses.filtered(lambda w: not w.node_id),
            'mistagged': [],
            'no_default': [],
            'pos': [],
            'users': [],
            'documents': [],
            'switched_without_nodes': [],
        }
        for warehouse in warehouses.filtered('node_id'):
            locations = self.env['stock.location'].sudo().search([
                ('id', 'child_of', warehouse.view_location_id.id), ('analytic_account_id', '!=', False),
                ('analytic_account_id', '!=', warehouse.node_id.id)])
            data['mistagged'] += [(warehouse, location) for location in locations]
        for node in warehouses.node_id:
            if len(node.warehouse_ids) > 1 and not node.default_warehouse_id:
                data['no_default'].append(node)
        if 'analytic_account_id' in self.env['pos.config']._fields:
            for config in self.env['pos.config'].sudo().search([]):
                if config.analytic_account_id and config.node_id and config.analytic_account_id != config.node_id:
                    data['pos'].append(config)
        group = self.env.ref('bn_stock_location.group_node_access', raise_if_not_found=False)
        if group:
            data['switched_without_nodes'] = group.users.filtered(
                lambda u: not u.share and not u.all_nodes and not u.allowed_node_ids)
            data['switched'] = len(group.users.filtered(lambda u: not u.share))
        Mixin = self.env['node.document.mixin']
        for name in Mixin._node_document_models():
            Model = self.env[name].sudo().with_context(active_test=False)
            missing = Model.search_count([('node_id', '=', False)])
            if missing:
                data['documents'].append((Model._description or name, missing))
        for user in self.env['res.users'].sudo().search([('share', '=', False)]):
            if user.has_group('base.group_system'):
                continue
            before = user.scope_warehouse_ids
            after = user.node_warehouse_ids
            if before != after or not after:
                data['users'].append((user, after - before, before - after))
        return data

    @api.model
    def _report_html(self):
        data = self._report_data()

        def names(records):
            return escape(', '.join(records.mapped('display_name'))) or Markup('&mdash;')

        def section(title, help_text, header, rows):
            body = Markup('').join(
                Markup('<tr>%s</tr>') % Markup('').join(Markup('<td>%s</td>') % cell for cell in row) for row in rows)
            if not rows:
                body = Markup('<tr><td colspan="%s" class="text-success">%s</td></tr>') % (len(header), _('Nothing to correct.'))
            head = Markup('').join(Markup('<th>%s</th>') % h for h in header)
            return Markup('<h4 class="mt-4">%s (%s)</h4><p class="text-muted">%s</p>'
                          '<table class="table table-sm table-bordered"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>') % (
                title, len(rows), help_text, head, body)

        html = Markup('<div>')
        html += section(_('Warehouses without a Branch / Site'),
                        _('Set it on the warehouse (Inventory > Configuration > Warehouses).'),
                        [_('Warehouse')], [[w.display_name] for w in data['no_node']])
        html += section(_('Locations tagged differently from their warehouse'),
                        _('Correct the location\'s Analytic Account, unless it is a deliberate exception.'),
                        [_('Warehouse'), _('Its Branch / Site'), _('Location'), _('Location tag')],
                        [[w.display_name, w.node_id.display_name, l.display_name, l.analytic_account_id.display_name]
                         for w, l in data['mistagged']])
        html += section(_('Branches / Sites with several warehouses and no Default Warehouse'),
                        _('Set the Default Warehouse on the analytic account: documents without a location use it.'),
                        [_('Branch / Site'), _('Warehouses')],
                        [[n.display_name, names(n.warehouse_ids)] for n in data['no_default']])
        html += section(_('POS whose Branch differs from its warehouse'),
                        _('A POS belongs to the Branch / Site of its warehouse: correct one of them.'),
                        [_('POS'), _('POS Branch'), _('Warehouse'), _('Warehouse Branch / Site')],
                        [[c.display_name, c.analytic_account_id.display_name, c.warehouse_id.display_name,
                          c.node_id.display_name] for c in data['pos']])
        html += section(_('Users whose warehouses change with Branches / Sites'),
                        _('Not applied yet. Review before the switch: add or remove Allowed Branches / Sites on the user.'),
                        [_('User'), _('Allowed Branches / Sites'), _('Gains'), _('Loses')],
                        [[u.display_name, _('All (Pakistan)') if u.all_nodes else names(u.allowed_node_ids),
                          names(gain), names(lose) if (lose or not u.node_warehouse_ids) else Markup('&mdash;')]
                         for u, gain, lose in data['users']])
        html += section(_('Users with Branch / Site Access but no Branch / Site'),
                        _('They see only the documents they created: give them Allowed Branches / Sites, '
                          'or All Branches / Sites (%s users have Branch / Site Access).') % data.get('switched', 0),
                        [_('User')], [[u.display_name] for u in data['switched_without_nodes']])
        html += section(_('Documents without a Branch / Site'),
                        _('Their POS, location, warehouse and creator give none. Correct the set-up above, '
                          'then press "Update documents".'),
                        [_('Document'), _('Count')],
                        [[label, count] for label, count in data['documents']])
        return html + Markup('</div>')


class _PreviewRollback(Exception):
    """Undoes the trial switch of the rollout preview."""


class NodeRollout(models.AbstractModel):
    """T7: switch the users of a province (or city, zone...) to Branch / Site
    Access, after an exact preview of what each of them will see."""
    _inherit = 'node.setup'

    # besides the program documents: what users notice first
    ROLLOUT_EXTRA_MODELS = ('stock.warehouse', 'stock.picking', 'stock.quant', 'pos.order')

    @api.model
    def _rollout_users(self, node):
        """(to switch, without Branch / Site) of ``node``: internal users whose
        Allowed Branches / Sites are all under it, not switched yet; and its
        users (by employee branch) who have none."""
        group = self.env.ref(NODE_ACCESS_GROUP_XMLID)
        Users = self.env['res.users'].sudo()
        nodes = self.env['account.analytic.account'].sudo().search([('id', 'child_of', node.ids)])
        candidates = Users.search([('share', '=', False), ('all_nodes', '=', False)])
        ready = candidates.filtered(lambda u: u.allowed_node_ids and not (u.allowed_node_ids - nodes)
                                    and group not in u.groups_id)
        missing = candidates.filtered(lambda u: not u.allowed_node_ids
                                      and u.employee_ids[:1].analytic_account_id in nodes)
        return ready, missing

    @api.model
    def _rollout_models(self):
        return self.env['node.document.mixin']._node_document_models() + list(self.ROLLOUT_EXTRA_MODELS)

    @api.model
    def _visible_counts(self, user, models):
        counts = {}
        for name in models:
            Model = self.env[name].with_user(user)
            if not Model.check_access_rights('read', raise_exception=False):
                continue
            counts[name] = Model.with_context(active_test=False).search_count([])
        return counts

    @api.model
    def _rollout_preview(self, users):
        """Per user: warehouses gained / lost and the documents seen before and
        after the switch, measured with the real rules in a trial switch that
        is rolled back (nothing changes)."""
        group = self.env.ref(NODE_ACCESS_GROUP_XMLID)
        models = self._rollout_models()
        before = {user: (user.scope_warehouse_ids, self._visible_counts(user, models)) for user in users}
        after = {}
        try:
            with self.env.cr.savepoint():
                users.write({'groups_id': [(4, group.id)]})
                self.env['res.users']._scope_changed()
                self.env.invalidate_all()
                for user in users:
                    after[user] = (user.scope_warehouse_ids, self._visible_counts(user, models))
                raise _PreviewRollback()
        except _PreviewRollback:
            pass
        self.env['res.users']._scope_changed()
        self.env.invalidate_all()
        preview = []
        for user in users:
            (wh_before, docs_before), (wh_after, docs_after) = before[user], after[user]
            changes = [(self.env[name]._description or name, docs_before.get(name, 0), docs_after.get(name, 0))
                       for name in models if docs_before.get(name, 0) != docs_after.get(name, 0)]
            preview.append({'user': user, 'gains': wh_after - wh_before, 'loses': wh_before - wh_after,
                            'changes': changes})
        return preview

    @api.model
    def _rollout_html(self, node):
        ready, missing = self._rollout_users(node)
        preview = self._rollout_preview(ready)

        def names(records):
            return escape(', '.join(records.mapped('display_name'))) or Markup('&mdash;')

        rows = Markup('')
        for item in preview:
            changes = Markup('<br/>').join(
                Markup('%s: %s &rarr; <b>%s</b>') % (label, old, new) for label, old, new in item['changes']
            ) or Markup('<span class="text-success">%s</span>') % _('no change')
            rows += Markup('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>') % (
                item['user'].display_name, names(item['user'].allowed_node_ids),
                names(item['gains']), names(item['loses']), changes)
        if not preview:
            rows = Markup('<tr><td colspan="5" class="text-muted">%s</td></tr>') % _('No user to switch under this node.')
        html = Markup('<h4>%s</h4><p class="text-muted">%s</p>') % (
            _('Rollout of %s: %s users to switch') % (node.display_name, len(ready)),
            _('Measured with the real rules in a trial switch that was undone: nothing has changed yet. '
              'Documents: what each user sees today \u2192 after the switch.'))
        html += Markup('<table class="table table-sm table-bordered"><thead><tr><th>%s</th><th>%s</th><th>%s</th>'
                       '<th>%s</th><th>%s</th></tr></thead><tbody>%s</tbody></table>') % (
            _('User'), _('Allowed Branches / Sites'), _('Gains warehouses'), _('Loses warehouses'),
            _('Documents seen (today \u2192 after)'), rows)
        if missing:
            html += Markup('<div class="alert alert-warning">%s %s</div>') % (
                _('Not switched: no Allowed Branch / Site (they would see only their own documents):'),
                names(missing))
        return html

    @api.model
    def _rollout_switch(self, node, on=True):
        """Switch the users of ``node`` to Branch / Site Access (or back)."""
        group = self.env.ref(NODE_ACCESS_GROUP_XMLID)
        if on:
            users, _missing = self._rollout_users(node)
            users.write({'groups_id': [(4, group.id)]})
        else:
            nodes = self.env['account.analytic.account'].sudo().search([('id', 'child_of', node.ids)])
            users = group.users.filtered(lambda u: not u.all_nodes and u.allowed_node_ids
                                         and not (u.allowed_node_ids - nodes))
            users.write({'groups_id': [(3, group.id)]})
        _logger.info("Branch / Site Access %s for %s users of %s: %s", 'on' if on else 'off', len(users),
                     node.display_name, users.mapped('login'))
        return users


class NodeSetupWizard(models.TransientModel):
    _name = 'node.setup.wizard'
    _description = 'Branch / Site Set-up Check'

    report_html = fields.Html(readonly=True, sanitize=False)
    rollout_node_id = fields.Many2one(
        'account.analytic.account', string='Roll out to', domain="[('plan_id.name', '=', 'Location')]",
        help="A province, city or zone: its users are switched to Branch / Site Access.")
    rollout_html = fields.Html(readonly=True, sanitize=False)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res['report_html'] = self.env['node.setup']._report_html()
        return res

    def action_fill(self):
        """Fill what is still empty from the current set-up, then show the report again."""
        stats = self.env['node.setup'].sudo()._fill()
        wizard = self.create({})
        wizard.report_html = Markup('<div class="alert alert-info">%s</div>') % _(
            "Filled: %(w)s warehouses, %(u)s users, %(n)s national users.",
            w=stats['warehouses'], u=stats['users'], n=stats['national']) + wizard.report_html
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': wizard.id,
                'view_mode': 'form', 'target': 'new', 'name': _('Branch / Site Set-up Check')}

    def action_update_documents(self):
        """After a correction of the set-up: every document takes its Branch / Site again."""
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only an administrator can update the Branch / Site of the documents.'))
        counts = self.env['node.document.mixin'].sudo()._update_documents()
        wizard = self.create({})
        wizard.report_html = Markup('<div class="alert alert-info">%s</div>') % _(
            "Branch / Site updated on %(count)s documents.", count=sum(counts.values())) + wizard.report_html
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': wizard.id,
                'view_mode': 'form', 'target': 'new', 'name': _('Branch / Site Set-up Check')}

    def action_refresh(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.create({}).id,
                'view_mode': 'form', 'target': 'new', 'name': _('Branch / Site Set-up Check')}

    def _check_admin(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only an administrator can roll out Branch / Site Access.'))

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new', 'name': _('Branch / Site Set-up Check')}

    def action_rollout_preview(self):
        self._check_admin()
        if not self.rollout_node_id:
            raise UserError(_('Choose the province, city or zone to roll out to.'))
        self.rollout_html = self.env['node.setup'].sudo()._rollout_html(self.rollout_node_id)
        return self._reopen()

    def action_rollout_switch(self):
        self._check_admin()
        if not self.rollout_node_id:
            raise UserError(_('Choose the province, city or zone to roll out to.'))
        users = self.env['node.setup'].sudo()._rollout_switch(self.rollout_node_id, on=True)
        self.rollout_html = Markup('<div class="alert alert-success">%s</div>') % _(
            "%(count)s users of %(node)s now use Branch / Site Access: %(users)s",
            count=len(users), node=self.rollout_node_id.display_name,
            users=', '.join(users.mapped('name')) or '-')
        self.report_html = self.env['node.setup']._report_html()
        return self._reopen()

    def action_rollout_back(self):
        self._check_admin()
        if not self.rollout_node_id:
            raise UserError(_('Choose the province, city or zone to switch back.'))
        users = self.env['node.setup'].sudo()._rollout_switch(self.rollout_node_id, on=False)
        self.rollout_html = Markup('<div class="alert alert-warning">%s</div>') % _(
            "%(count)s users of %(node)s are back on the location-based access: %(users)s",
            count=len(users), node=self.rollout_node_id.display_name,
            users=', '.join(users.mapped('name')) or '-')
        return self._reopen()

