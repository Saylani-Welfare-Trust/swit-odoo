# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosLinkMixin(models.AbstractModel):
    """Where a record was made or paid at the POS: its order, session and POS
    (shop). Every program record created or settled at the POS carries them,
    so it can be traced back - and reported on - by shop and session.

    - created from a POS popup (before the payment): the session and POS of
      the user's open session (_pos_creation_vals)
    - paid by a POS order: the order, and with it its session and POS
      (pos.order._pos_documents / _link_pos)
    - created by the POS screen itself: give pos_reference, the order's
      reference, and the order is found once it is saved"""
    _name = 'pos.link.mixin'
    _description = 'Link to the POS order / session / POS it comes from'

    pos_order_id = fields.Many2one('pos.order', string='POS Order', readonly=True, copy=False,
                                   index='btree_not_null')
    pos_session_id = fields.Many2one('pos.session', string='POS Session', readonly=True, copy=False,
                                     index='btree_not_null')
    pos_config_id = fields.Many2one('pos.config', string='Point of Sale', readonly=True, copy=False,
                                    index='btree_not_null')
    pos_reference = fields.Char(string='POS Order Ref.', readonly=True, copy=False)

    def init(self):
        """Install / update of every model using the mixin: records already
        linked to their order get its session and POS."""
        super().init()
        if self._abstract or not self._auto:
            return
        self.env.cr.execute("""
            UPDATE "{table}" t
               SET pos_session_id = COALESCE(t.pos_session_id, o.session_id),
                   pos_config_id = COALESCE(t.pos_config_id, s.config_id),
                   pos_reference = COALESCE(t.pos_reference, o.pos_reference)
              FROM pos_order o JOIN pos_session s ON s.id = o.session_id
             WHERE t.pos_order_id = o.id
               AND (t.pos_session_id IS NULL OR t.pos_config_id IS NULL)
        """.format(table=self._table))
        self.env.cr.execute("""
            UPDATE "{table}" t SET pos_config_id = s.config_id
              FROM pos_session s
             WHERE t.pos_session_id = s.id AND t.pos_config_id IS NULL
        """.format(table=self._table))

    @api.model
    def _current_pos_session(self):
        """The POS session the current user works in (context, else their open one)."""
        Session = self.env['pos.session'].sudo()
        session = Session.browse(self.env.context.get('pos_session_id') or []).exists()
        return session or Session.search([
            ('user_id', '=', self.env.uid), ('state', 'in', ('opening_control', 'opened', 'closing_control')),
        ], order='id desc', limit=1)

    @api.model
    def _pos_creation_vals(self, session=None):
        session = session or self._current_pos_session()
        return {'pos_session_id': session.id, 'pos_config_id': session.config_id.id} if session else {}

    @api.model
    def _complete_pos_vals(self, vals):
        """Session and POS follow the order; the order is found by its reference."""
        if vals.get('pos_reference') and not vals.get('pos_order_id'):
            order = self.env['pos.order'].sudo().search([('pos_reference', '=', vals['pos_reference'])], limit=1)
            if order:
                vals['pos_order_id'] = order.id
        if vals.get('pos_order_id'):
            order = self.env['pos.order'].sudo().browse(vals['pos_order_id'])
            vals.setdefault('pos_session_id', order.session_id.id)
            vals.setdefault('pos_config_id', order.config_id.id)
            vals.setdefault('pos_reference', order.pos_reference)
        elif vals.get('pos_session_id') and not vals.get('pos_config_id'):
            vals['pos_config_id'] = self.env['pos.session'].sudo().browse(vals['pos_session_id']).config_id.id
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        # made from a POS popup: the user's open session and its POS
        creation = self._pos_creation_vals() if self.env.context.get('pos_link_create') else {}
        for vals in vals_list:
            if creation and not vals.get('pos_session_id') and not vals.get('pos_order_id'):
                vals.update(creation)
            self._complete_pos_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('pos_order_id') or vals.get('pos_reference') or vals.get('pos_session_id'):
            vals = self._complete_pos_vals(dict(vals))
        return super().write(vals)

    def _link_pos(self, order):
        """Link the records to ``order`` (paid by it); a link already set is kept."""
        order = order.sudo()
        for rec in self.sudo():
            vals = {}
            if not rec.pos_order_id:
                vals['pos_order_id'] = order.id
            if not rec.pos_session_id:
                vals['pos_session_id'] = order.session_id.id
            if not rec.pos_config_id:
                vals['pos_config_id'] = order.config_id.id
            if not rec.pos_reference:
                vals['pos_reference'] = order.pos_reference
            if vals:
                rec.write(vals)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _process_order(self, order, draft, existing_order):
        order_id = super()._process_order(order, draft, existing_order)
        pos_order = self.browse(order_id)
        if not draft and pos_order.state in ('paid', 'done', 'invoiced'):
            extra_data = (order.get('data') or {}).get('extra_data') or {}
            for records in pos_order.sudo()._pos_documents(extra_data):
                if records and 'pos_order_id' in records._fields and hasattr(records, '_link_pos'):
                    records._link_pos(pos_order)
        return order_id

    def _pos_documents(self, extra_data):
        """Program records paid or settled by this order (from its extra_data):
        a list of recordsets, each module adds its own."""
        return []
