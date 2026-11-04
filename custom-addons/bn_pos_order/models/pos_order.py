from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.sql import column_exists, create_column

import re


class POSOrder(models.Model):
    _inherit = 'pos.order'

    customer_note = fields.Char(
        string='Customer Note',
        compute='_compute_customer_note',
        store=True,
        readonly=False,
    )

    @api.depends('lines.customer_note')
    def _compute_customer_note(self):
        # POS keeps the customer note on each line; the order shows them together
        for order in self:
            notes = (line.customer_note.strip() for line in order.lines if line.customer_note)
            order.customer_note = ', '.join(note for note in notes if note) or False

    def _auto_init(self):
        # Fill the new column from the line notes in SQL, so the upgrade
        # doesn't recompute it for every existing order through the ORM
        if not column_exists(self.env.cr, 'pos_order', 'customer_note'):
            create_column(self.env.cr, 'pos_order', 'customer_note', 'varchar')
            self.env.cr.execute("""
                UPDATE pos_order o
                   SET customer_note = l.note
                  FROM (
                        SELECT order_id, string_agg(btrim(customer_note), ', ' ORDER BY id) AS note
                          FROM pos_order_line
                         WHERE btrim(customer_note) != ''
                      GROUP BY order_id
                       ) l
                 WHERE o.id = l.order_id
            """)
        return super()._auto_init()

    mobile = fields.Char(related='partner_id.mobile', string="Mobile No.")

    state = fields.Selection(
        [('draft', 'New'), ('cancel', 'Cancelled'), ('cfo_approval', 'CFO Approval'), ('paid', 'Paid'), ('done', 'Posted'), ('invoiced', 'Invoiced'), ('refund', 'Refunded'), ('reject', 'Reject')],
        'Status', readonly=True, copy=False, default='draft', index=True)
    
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", compute="_set_employee_branch", store=True)
    

    @api.constrains('mobile')
    def _check_mobile_number(self):
        for rec in self:
            if rec.mobile:
                if not re.fullmatch(r"\d{10}", rec.mobile):
                    raise ValidationError(
                        "Mobile number must contain exactly 10 digits."
                    )

    # ------------------------------------------------------------------
    # Refunds: a refund order waits for CFO approval before it is paid
    # ------------------------------------------------------------------
    def _check_refund_request(self, action):
        """``self`` must be draft refund orders, handled by a CFO approver."""
        if not self.env.su and not self.env.user.has_group('bn_pos_order.pos_order_cfo_approval_group'):
            raise AccessError(_('Only "POS Order / CFO Approval" users can do "%s".') % action)
        for order in self:
            if order.state != 'draft' or not order.refunded_order_ids:
                raise UserError(_('"%(action)s" is only possible for a refund waiting for approval (%(order)s).')
                                % {'action': action, 'order': order.name})

    def _restore_refunded_state(self):
        """Put the original orders of a rejected refund back to their status."""
        for order in self:
            if order.state != 'refund':
                continue
            if order.account_move:
                order.state = 'invoiced'
            elif order.session_id.state == 'closed':
                order.state = 'done'
            else:
                order.state = 'paid'

    def action_reject(self):
        self._check_refund_request(_('Reject'))
        self.refunded_order_ids._restore_refunded_state()
        self.write({'state': 'reject'})

    def action_cfo_approval(self):
        self._check_refund_request(_('CFO Approval'))
        self.write({'state': 'cfo_approval'})

    def refund(self):
        for order in self:
            if order.state not in ('paid', 'done', 'invoiced'):
                raise UserError(_('Only paid orders can be refunded (%s is "%s").') % (
                    order.name, dict(self._fields['state'].selection).get(order.state)))
        self.write({'state': 'refund'})
        return {
            'name': _('Return Products'),
            'view_mode': 'form',
            'res_model': 'pos.order',
            'res_id': self._refund().ids[0],
            'view_id': False,
            'context': self.env.context,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    @api.depends('user_id')
    def _set_employee_branch(self):
        for rec in self:
            if rec.user_id:
                rec.analytic_account_id = rec.user_id.employee_id.analytic_account_id.id or None