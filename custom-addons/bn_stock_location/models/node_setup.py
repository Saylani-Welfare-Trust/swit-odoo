import logging
from collections import Counter

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

# the users of these groups get every Branch / Site (national access)
# (Unrestricted Custom Access sees every warehouse: national keeps it so)
NATIONAL_GROUP_XMLIDS = ('base.group_system', 'account.group_account_manager', 'account.group_account_user',
                         'bn_stock_location.stock_scope_unrestricted_group')
NATIONAL_GROUP_NAME_PARTS = ('audit', 'cfo')
# the location-based inputs of the previous versions, read from their tables when
# they still exist (upgrade): Allowed Locations / Warehouses of the user, and the
# dashboards' access lists (bn_dashboard)
OLD_LOCATION_RELATION = ('res_users_stock_location_rel', 'res_users_id', 'stock_location_id')
OLD_WAREHOUSE_RELATION = ('res_users_stock_warehouse_rel', 'res_users_id', 'stock_warehouse_id')
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
    def _relation_ids(self, relation, user):
        """The ids linked to ``user`` in an old relation table ([] if it is gone)."""
        table, user_column, other_column = relation
        self.env.cr.execute("SELECT to_regclass(%s)", (table,))
        if not self.env.cr.fetchone()[0]:
            return []
        self.env.cr.execute('SELECT "%s" FROM "%s" WHERE "%s" = %%s' % (other_column, table, user_column), (user.id,))
        return [row[0] for row in self.env.cr.fetchall()]

    @api.model
    def _dashboard_nodes(self, user):
        ids = set()
        for relation in DASHBOARD_RELATIONS:
            ids.update(self._relation_ids(relation, user))
        return self.env['account.analytic.account'].sudo().browse(ids).exists()

    @api.model
    def _current_nodes(self, user):
        """The nodes of a user's location-based set-up (previous versions): the
        tags of their Allowed Locations / Warehouses, those warehouses' Branch /
        Site, their employee's branch and their dashboard access lists."""
        user = user.sudo()
        locations = self.env['stock.location'].sudo().browse(self._relation_ids(OLD_LOCATION_RELATION, user)).exists()
        warehouses = self.env['stock.warehouse'].sudo().browse(self._relation_ids(OLD_WAREHOUSE_RELATION, user)).exists()
        nodes = (locations | warehouses.view_location_id | warehouses.lot_stock_id).analytic_account_id
        nodes |= warehouses.node_id
        # an untagged allowed location counts for its warehouse's Branch / Site
        nodes |= locations.filtered(lambda l: not l.analytic_account_id).warehouse_id.node_id
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
    def _named_national_groups(self):
        data = self.env['ir.model.data'].sudo().search([('model', '=', 'res.groups'), ('module', '=like', 'bn\\_%')])
        return self.env['res.groups'].sudo().browse(
            data.filtered(lambda d: any(part in d.name.lower() for part in NATIONAL_GROUP_NAME_PARTS)).mapped('res_id')).exists()

    @api.model
    def _national_users(self, users):
        """The users of ``users`` who are national: in a national group directly.
        An Audit / CFO group of a module counts only when the user does not have
        it through a higher tier of the module (a module's Administrator has its
        Audit tier too, and is not national for it)."""
        users = users.sudo().filtered(lambda u: not u.share)
        explicit = self.env['res.groups']
        for xmlid in NATIONAL_GROUP_XMLIDS:
            explicit |= self.env.ref(xmlid, raise_if_not_found=False) or self.env['res.groups']
        named = self._named_national_groups()
        national = self.env['res.users']
        for user in users:
            groups = user.groups_id
            if groups & explicit:
                national |= user
                continue
            # a named group the user has not through another (non-national) group of theirs
            for group in groups & named:
                if not (groups - named).filtered(lambda other: group in other.trans_implied_ids):
                    national |= user
                    break
        return national

    @api.model
    def _fill_national(self):
        candidates = self.env['res.users'].sudo().search([('share', '=', False), ('all_nodes', '=', False)])
        users = self._national_users(candidates)
        users.write({'all_nodes': True})
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
            'documents': [],
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
        data['national'] = self.env['res.users'].sudo().search([('share', '=', False), ('all_nodes', '=', True)])
        data['without_nodes'] = self.env['res.users'].sudo().search([
            ('share', '=', False), ('all_nodes', '=', False), ('allowed_node_ids', '=', False)])
        Mixin = self.env['node.document.mixin']
        for name in Mixin._node_document_models():
            Model = self.env[name].sudo().with_context(active_test=False)
            missing = Model.search_count([('node_id', '=', False)])
            if missing:
                data['documents'].append((Model._description or name, missing))
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
        html += section(_('Users without any Branch / Site'),
                        _('They see no program document, not even the ones they create: give them Allowed '
                          'Branches / Sites, or All Branches / Sites (Users > Inventory tab).'),
                        [_('User')], [[u.display_name] for u in data['without_nodes']])
        html += section(_('National users (All Branches / Sites)'),
                        _('They see every Branch / Site. Review this list: remove All Branches / Sites from anyone '
                          'who should be limited to some Branches / Sites (Users > Inventory tab).'),
                        [_('User'), _('Allowed Branches / Sites when not national')],
                        [[u.display_name, names(u.allowed_node_ids)] for u in data['national']])
        html += section(_('Documents without a Branch / Site'),
                        _('Their POS, location, warehouse and creator give none, so only national users see them. '
                          'Correct the set-up above, then press "Update documents".'),
                        [_('Document'), _('Count')],
                        [[label, count] for label, count in data['documents']])
        return html + Markup('</div>')


class NodeSetupWizard(models.TransientModel):
    _name = 'node.setup.wizard'
    _description = 'Branch / Site Set-up Check'

    report_html = fields.Html(readonly=True, sanitize=False)

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
