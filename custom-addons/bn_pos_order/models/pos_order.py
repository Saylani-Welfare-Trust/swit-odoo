from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools.sql import column_exists, create_column

import re


class POSOrder(models.Model):
    _inherit = 'pos.order'

    is_non_donation_receipt = fields.Boolean(
        string='Non-donation Receipt',
        copy=False,
    )

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

    @api.model
    def _order_fields(self, ui_order):
        vals = super()._order_fields(ui_order)
        extra_data = ui_order.get('extra_data') or {}
        vals['is_non_donation_receipt'] = any(
            extra_data.get(source)
            for source in ('medical_equipment', 'microfinance', 'welfare')
        )
        return vals


    product_ids = fields.Many2many(
        'product.product',
        compute='_compute_product_ids',
        string='Products',
        store=True,          # required for search / filter / group by
    )
    
    @api.depends('lines.product_id')
    def _compute_product_ids(self):
        for order in self:
            order.product_ids = order.lines.mapped('product_id')
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

    def action_reject(self):
        pos_order = self.env['pos.order'].search([('id', '=', self.refunded_order_ids[0].id)])
        
        if pos_order:
            if self.session_id.state != 'closed':
                pos_order.state = 'paid'
            else:
                pos_order.state = 'done'
        
        self.state = 'reject'

    def action_cfo_approval(self):
        self.state = 'cfo_approval'
    
    def refund(self):
        self.state = 'refund'
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

    def action_correct_order_ref(self):
        fixed_count = 0
        skipped_count = 0

        for rec in self:
            pos_name = rec.config_id.name

            # Order Ref is "<POS name>/<number>"; draft orders are still "/"
            old_pos_name, sep, number = (rec.name or '').rpartition('/')

            if not pos_name or not old_pos_name or not number:
                skipped_count += 1
                continue

            if old_pos_name != pos_name:
                rec.name = f"{pos_name}/{number}"
                fixed_count += 1

        # Renaming a POS does not rename its sequence, so new orders
        # would keep coming with the old POS name
        for config in self.config_id.sudo():
            prefix = f"{config.name}/"

            if config.sequence_id.prefix != prefix:
                config.sequence_id.prefix = prefix

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Order Ref Corrected'),
                'message': _('%s order(s) updated, %s skipped.') % (fixed_count, skipped_count),
                'type': 'warning' if skipped_count else 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    @api.depends('user_id')
    def _set_employee_branch(self):
        for rec in self:
            if rec.user_id:
                rec.analytic_account_id = rec.user_id.employee_id.analytic_account_id.id or None
