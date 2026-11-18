# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError

# Odoo's own POS documents: the session / POS forms already show them
# (orders, payments, journal entries, pickings, cash in / out)
CORE_POS_MODELS = {
    'pos.order', 'pos.order.line', 'pos.payment', 'pos.session', 'pos.config', 'pos.bill', 'pos.combo',
    'pos.combo.line', 'pos.printer', 'pos.category', 'pos.payment.method', 'pos.pack.operation.lot',
    'account.bank.statement.line', 'account.payment', 'account.move', 'account.move.line',
    'payment.transaction', 'procurement.group', 'stock.picking', 'stock.move', 'stock.move.line',
}


class PosDocumentSource(models.AbstractModel):
    """The records made or paid at the POS, seen from a session or a POS:

    - direct: the models with the POS link (pos.link.mixin: order, session,
      POS, cashier), whether made from a POS popup or paid by a POS order;
    - indirect: any other model linked to a session or a POS order by its own
      field (e.g. the closing slips of a session).

    Found from the registry, so a new module's records show up by themselves."""
    _name = 'pos.document.source'
    _description = 'Records made or paid at the POS'

    @api.model
    def _sources(self):
        """[(model, {'session': field, 'order': field, 'config': field, 'direct': bool})]"""
        direct = set(self.env['pos.link.mixin']._inherit_children)
        sources = []
        for name in sorted(self.env.registry):
            model = self.env.registry[name]
            if model._abstract or model._transient or not model._auto or name in CORE_POS_MODELS:
                continue
            if name in direct:
                sources.append((name, {'session': 'pos_session_id', 'order': 'pos_order_id',
                                       'config': 'pos_config_id', 'direct': True}))
                continue
            links = {'direct': False}
            for field in model._fields.values():
                if field.type == 'many2one' and field.store:
                    for kind, comodel in (('session', 'pos.session'), ('order', 'pos.order'), ('config', 'pos.config')):
                        if field.comodel_name == comodel and kind not in links:
                            links[kind] = field.name
            if len(links) > 1:
                sources.append((name, links))
        return sources

    @api.model
    def _domain(self, links, sessions=None, configs=None):
        """Records of one source linked to ``sessions`` or to ``configs``."""
        terms = []
        if sessions is not None:
            if links.get('session'):
                terms.append([(links['session'], 'in', sessions.ids)])
            if links.get('order'):
                terms.append([(links['order'] + '.session_id', 'in', sessions.ids)])
        if configs is not None:
            if links.get('config'):
                terms.append([(links['config'], 'in', configs.ids)])
            if links.get('session'):
                terms.append([(links['session'] + '.config_id', 'in', configs.ids)])
            if links.get('order'):
                terms.append([(links['order'] + '.config_id', 'in', configs.ids)])
        if not terms:
            return None
        domain = terms[0]
        for term in terms[1:]:
            domain = ['|'] + domain + term
        return domain

    @api.model
    def _document_name(self, record, label):
        """The record's name; for one without a name (a line, a slip ...), its
        type and its parent / reference instead of "model,id"."""
        name = record.display_name
        if name and name != '%s,%s' % (record._name, record.id):
            return name
        for field_name in ('reference', 'pos_reference', 'application_id', 'session_id', 'pos_session_id', 'partner_id'):
            field = record._fields.get(field_name)
            value = record[field_name] if field else False
            if value:
                return '%s %s' % (label, value.display_name if field.type == 'many2one' else value)
        return '%s #%s' % (label, record.id)

    @api.model
    def _readable(self, name):
        try:
            self.env[name].check_access_rights('read')
            return True
        except AccessError:
            return False

    @api.model
    def _count(self, sessions=None, configs=None):
        total = 0
        for name, links in self._sources():
            domain = self._domain(links, sessions, configs)
            if domain and self._readable(name):
                total += self.env[name].search_count(domain)
        return total

    @api.model
    def _open(self, title, sessions=None, configs=None):
        """List of the records (one row each, grouped by type) the user can read."""
        rows = []
        for name, links in self._sources():
            domain = self._domain(links, sessions, configs)
            if not domain or not self._readable(name):
                continue
            label = self.env['ir.model']._get(name).name or name
            for record in self.env[name].search(domain):
                order = record[links['order']] if links.get('order') else self.env['pos.order']
                session = record[links['session']] if links.get('session') else order.session_id
                config = (record[links['config']] if links.get('config') else self.env['pos.config']) \
                    or session.config_id or order.config_id
                if links['direct']:
                    link = 'order' if order else 'session'
                    cashier = record.pos_cashier_id
                else:
                    link = 'indirect'
                    cashier = order.user_id or session.user_id
                rows.append({
                    'res_model': name, 'res_id': record.id, 'document_type': label,
                    'name': self._document_name(record, label), 'date': record.create_date, 'link': link,
                    'pos_order_id': order.id, 'pos_session_id': session.id, 'pos_config_id': config.id,
                    'pos_cashier_id': cashier.id,
                })
        documents = self.env['pos.document'].create(rows)
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'pos.document',
            'view_mode': 'tree',
            'domain': [('id', 'in', documents.ids)],
            'context': {'search_default_group_document_type': 1, 'create': False, 'edit': False, 'delete': False},
        }


class PosDocument(models.TransientModel):
    """One row of the POS Documents list of a session / POS."""
    _name = 'pos.document'
    _description = 'Record made or paid at the POS'
    _order = 'document_type, date desc, id desc'

    res_model = fields.Char('Model', readonly=True)
    res_id = fields.Integer('Record ID', readonly=True)
    document_type = fields.Char('Document Type', readonly=True)
    name = fields.Char('Document', readonly=True)
    date = fields.Datetime('Created On', readonly=True)
    link = fields.Selection([
        ('session', 'Made at the POS'),
        ('order', 'Paid by a POS order'),
        ('indirect', 'Linked to the session / order'),
    ], string='Link', readonly=True)
    pos_order_id = fields.Many2one('pos.order', string='POS Order', readonly=True)
    pos_session_id = fields.Many2one('pos.session', string='POS Session', readonly=True)
    pos_config_id = fields.Many2one('pos.config', string='Point of Sale', readonly=True)
    pos_cashier_id = fields.Many2one('res.users', string='Cashier', readonly=True)

    def action_open_document(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'res_id': self.res_id,
            'view_mode': 'form',
            'target': 'current',
        }


class PosSession(models.Model):
    _inherit = 'pos.session'

    pos_document_count = fields.Integer('POS Documents', compute='_compute_pos_document_count')

    def _compute_pos_document_count(self):
        Source = self.env['pos.document.source']
        for session in self:
            session.pos_document_count = Source._count(sessions=session) if session.id else 0

    def action_view_pos_documents(self):
        self.ensure_one()
        return self.env['pos.document.source']._open(_('POS Documents: %s', self.name), sessions=self)


class PosConfig(models.Model):
    _inherit = 'pos.config'

    pos_document_count = fields.Integer('POS Documents', compute='_compute_pos_document_count')

    def _compute_pos_document_count(self):
        Source = self.env['pos.document.source']
        for config in self:
            config.pos_document_count = Source._count(configs=config) if config.id else 0

    def action_view_pos_documents(self):
        self.ensure_one()
        return self.env['pos.document.source']._open(_('POS Documents: %s', self.name), configs=self)
