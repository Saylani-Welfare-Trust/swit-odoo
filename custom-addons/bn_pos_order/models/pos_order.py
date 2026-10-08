from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import re


class POSOrder(models.Model):
    _inherit = 'pos.order'


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