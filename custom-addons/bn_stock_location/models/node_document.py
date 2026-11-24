import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# name of the analytic plan of the Location tree (Province > City > Zone > Branch / Site)
LOCATION_PLAN = 'Location'


class NodeDocumentMixin(models.AbstractModel):
    """The Branch / Site a program document belongs to.

    Stored and indexed on every program document, so record rules, dashboards
    and reports can use one field. It is taken from the document's own sources,
    in the order of ``_node_sources`` (the POS it was made or paid at, its
    location or warehouse, its branch...). A document with none of them keeps
    the Branch / Site of the user who created it.

    Kept as it was when the document was made: a later change of a
    warehouse's Branch / Site does not move the old documents (the set-up
    check's *Update documents* does, after a correction)."""
    _name = 'node.document.mixin'
    _description = 'Document of a Branch / Site'

    node_id = fields.Many2one(
        'account.analytic.account', string='Branch / Site', compute='_compute_node_id', store=True,
        readonly=True, copy=False, index='btree_not_null', compute_sudo=True,
        help="The Branch / Site (Location tree) of this document: from its POS, its location or "
             "warehouse, else the branch of the user who created it.")

    @api.model
    def _node_sources(self):
        """Field paths giving the Branch / Site, first match wins. Each may lead to
        a POS, a POS session, a warehouse, a location, an employee, a user, an
        analytic account of the Location tree, or any record with a node_id."""
        return []

    def _node_depends(self):
        return [path for path in self._node_sources() if path.split('.')[0] in self._fields]

    @api.model
    def _node_is_location_account(self, account):
        """An analytic account of the Location tree (never a Segment)."""
        if not account:
            return False
        cache = self.env.cr.cache
        if 'node_location_plan_ids' not in cache:
            cache['node_location_plan_ids'] = tuple(self.env['account.analytic.plan'].sudo().search(
                [('name', '=', LOCATION_PLAN)]).ids)
        location_plans = self.env['account.analytic.plan'].sudo().browse(cache['node_location_plan_ids'])
        if not location_plans:
            # databases without the Location plan (tests, new companies)
            return True
        root = account.root_plan_id if 'root_plan_id' in account._fields else account.plan_id
        return (root or account.plan_id) in location_plans

    @api.model
    def _node_of(self, record):
        """The Branch / Site of one source record (empty when it has none)."""
        Account = self.env['account.analytic.account']
        if not record:
            return Account
        record = record[:1].sudo()
        model = record._name
        if model == 'account.analytic.account':
            return record if self._node_is_location_account(record) else Account
        if model == 'stock.warehouse':
            return record.node_id
        if model == 'stock.location':
            node = record.warehouse_id.node_id
            if node:
                return node
            # a location outside any warehouse: its own tag, else its parents'
            ids = [int(part) for part in reversed((record.parent_path or '').strip('/').split('/')) if part]
            for location in self.env['stock.location'].sudo().browse(ids):
                if self._node_is_location_account(location.analytic_account_id):
                    return location.analytic_account_id
            return Account
        if model == 'pos.config':
            return record.node_id or self._node_of(record.analytic_account_id)
        if model == 'pos.session':
            return self._node_of(record.config_id) or self._node_of(record.analytic_account_id)
        if model == 'stock.picking':
            return (record.picking_type_id.warehouse_id.node_id or self._node_of(record.location_id)
                    or self._node_of(record.location_dest_id))
        if model == 'hr.employee':
            return self._node_of(record.analytic_account_id)
        if model == 'res.users':
            return self._node_of(record.employee_ids[:1])
        if 'node_id' in record._fields:
            return record.node_id
        return Account

    def _node_from_sources(self):
        self.ensure_one()
        for path in self._node_sources():
            if path.split('.')[0] not in self._fields:
                continue
            node = self._node_of(self.mapped(path))
            if node:
                return node
        return self.env['account.analytic.account']

    @api.depends(lambda self: self._node_depends())
    def _compute_node_id(self):
        for rec in self:
            node = rec._node_from_sources()
            if not node and not rec.node_id:
                # no source: the Branch / Site of the user who created it
                node = self._node_of(rec.create_uid or self.env.user)
            if node or not rec.node_id:
                rec.node_id = node

    @api.model
    def _node_document_models(self):
        return sorted(name for name, model in self.env.registry.items()
                      if not model._abstract and model._auto and name != 'node.document.mixin'
                      and any(getattr(cls, '_name', None) == 'node.document.mixin' for cls in model.__mro__))

    @api.model
    def _update_documents(self, models=None, batch=1000):
        """Recompute the Branch / Site of every document (after a correction of the
        set-up). Returns the number of documents per model."""
        counts = {}
        for name in models or self._node_document_models():
            Model = self.env[name].sudo().with_context(active_test=False, tracking_disable=True)
            ids = Model.search([]).ids
            for start in range(0, len(ids), batch):
                records = Model.browse(ids[start:start + batch])
                self.env.add_to_compute(Model._fields['node_id'], records)
                records.flush_recordset(['node_id'])
                self.env.invalidate_all()
            counts[name] = len(ids)
        _logger.info("Branch / Site of the documents updated: %s", counts)
        return counts


class PosLinkMixinNode(models.AbstractModel):
    """Every program document made or paid at the POS: its Branch / Site comes
    first from the POS (its warehouse's node)."""
    _name = 'pos.link.mixin'
    _inherit = ['pos.link.mixin', 'node.document.mixin']

    @api.model
    def _node_sources(self):
        return ['pos_config_id', 'pos_session_id', 'pos_analytic_account_id'] + super()._node_sources()


class StockWarehouseNodeRules(models.Model):
    """Record rules are cached per user: a warehouse moved to another Branch /
    Site changes what the switched users see."""
    _inherit = 'stock.warehouse'

    def write(self, vals):
        res = super().write(vals)
        if 'node_id' in vals:
            self.env['res.users']._scope_changed()
        return res


class AccountAnalyticAccountNodeRules(models.Model):
    """A Branch / Site added to or moved in the Location tree changes what the
    users of the nodes above it see (cached record rules)."""
    _inherit = 'account.analytic.account'

    @api.model_create_multi
    def create(self, vals_list):
        accounts = super().create(vals_list)
        if any(vals.get('parent_id') for vals in vals_list):
            self.env['res.users']._scope_changed()
        return accounts

    def write(self, vals):
        res = super().write(vals)
        if {'parent_id', 'active'} & set(vals):
            self.env['res.users']._scope_changed()
        return res
