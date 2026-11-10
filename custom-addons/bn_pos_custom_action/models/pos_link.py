# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools.sql import column_exists


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
    pos_cashier_id = fields.Many2one('res.users', string='Cashier', readonly=True, copy=False,
                                     index='btree_not_null')
    pos_employee_id = fields.Many2one('hr.employee', string='Cashier (Employee)', readonly=True, copy=False,
                                      index='btree_not_null')
    # the Branch of the shop (session) the record was made or paid at
    pos_analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Branch (Shop)', compute='_compute_pos_analytic_account_id',
        store=True, readonly=True, copy=False, index='btree_not_null',
        help="Branch of the POS shop the record was made or paid at.")

    @api.depends('pos_session_id', 'pos_config_id')
    def _compute_pos_analytic_account_id(self):
        # kept as it was at the time: a later change of the shop's Branch does not retag it
        for rec in self:
            rec.pos_analytic_account_id = (
                rec.pos_session_id.analytic_account_id or rec.pos_config_id.analytic_account_id)

    def init(self):
        """Install / update of every model using the mixin: records already
        linked to their order get its session, POS and cashier."""
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
        # cashier: the order's, else the session's user
        employee = column_exists(self.env.cr, 'pos_order', 'employee_id')
        self.env.cr.execute("""
            UPDATE "{table}" t
               SET pos_cashier_id = COALESCE(t.pos_cashier_id, o.user_id){employee}
              FROM pos_order o
             WHERE t.pos_order_id = o.id AND (t.pos_cashier_id IS NULL{employee_missing})
        """.format(table=self._table,
                   employee=', pos_employee_id = COALESCE(t.pos_employee_id, o.employee_id)' if employee else '',
                   employee_missing=' OR t.pos_employee_id IS NULL' if employee else ''))
        self.env.cr.execute("""
            UPDATE "{table}" t SET pos_cashier_id = s.user_id
              FROM pos_session s
             WHERE t.pos_session_id = s.id AND t.pos_cashier_id IS NULL
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
        """Made from a POS popup: the user's open session, its POS, and the
        user at the POS as cashier."""
        session = session or self._current_pos_session()
        if not session:
            return {}
        user = self.env.user
        return {
            'pos_session_id': session.id,
            'pos_config_id': session.config_id.id,
            'pos_cashier_id': user.id,
            'pos_employee_id': user.employee_id.id or False,
        }

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
            vals.update({k: v for k, v in self._order_cashier_vals(order).items() if not vals.get(k)})
        elif vals.get('pos_session_id'):
            session = self.env['pos.session'].sudo().browse(vals['pos_session_id'])
            if not vals.get('pos_config_id'):
                vals['pos_config_id'] = session.config_id.id
            if not vals.get('pos_cashier_id'):
                vals['pos_cashier_id'] = session.user_id.id
        return vals

    @api.model
    def _order_cashier_vals(self, order):
        """The cashier who rang up ``order``: its user and, with POS employees
        (pos_hr), the employee logged in at the till."""
        vals = {'pos_cashier_id': order.user_id.id}
        employee = order.employee_id if 'employee_id' in order._fields else self.env['hr.employee']
        vals['pos_employee_id'] = (employee or order.user_id.employee_id).id or False
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
            cashier = self._order_cashier_vals(order)
            if not rec.pos_cashier_id:
                vals['pos_cashier_id'] = cashier['pos_cashier_id']
            if not rec.pos_employee_id and cashier['pos_employee_id']:
                vals['pos_employee_id'] = cashier['pos_employee_id']
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
