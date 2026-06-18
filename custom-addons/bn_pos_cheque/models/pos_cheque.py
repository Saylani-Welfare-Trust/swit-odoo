from odoo import models, fields, api
from odoo.exceptions import ValidationError

state_selection = [
    ('draft', 'Draft'),
    ('clear', 'Clear'),
    ('bounce', 'Bounce'),
    ('cancel', 'Cancelled'),
]

class POSCheque(models.Model):
    _name = 'pos.cheque'
    _description = "POS Cheque"

    bank_id = fields.Many2one('account.journal', string="Bank")
    donor_id = fields.Many2one('res.partner', string="Donor", compute="_set_details", store=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", compute="_set_details", store=True)
    name = fields.Char('Cheque Number')  # ← this is the cheque number, matched against microfinance.line.cheque_no
    state = fields.Selection(selection=state_selection, string="State", default='draft')
    order_reference = fields.Char('Order Reference', compute="_set_details", store=True)
    bank_name = fields.Char('Bank Name')
    date = fields.Date('Date')
    bounce_count = fields.Integer('Bounce Count')
    amount = fields.Float('Amount', compute="_set_details", store=True)

    @api.depends('name')
    def _set_details(self):
        for rec in self:
            rec.donor_id = None
            rec.analytic_account_id = None
            rec.amount = 0
            rec.order_reference = ''
            pos_order = self.env['pos.order'].search([('pos_cheque_id', '=', rec.id)], limit=1)
            if pos_order:
                rec.donor_id = pos_order.partner_id.id
                rec.analytic_account_id = pos_order.analytic_account_id.id
                rec.amount = pos_order.amount_total
                branch_code = pos_order.user_id.employee_id.analytic_account_id.code
                company = pos_order.company_id.name[:3].upper()
                order_date = pos_order.date_order and pos_order.date_order.year or ''
                order_ref = pos_order.name and pos_order.name[-4:] or '0000'
                rec.order_reference = f'{branch_code}-{company}-{order_date}-{order_ref}'

    def _get_microfinance_line(self):
        """
        Search for a microfinance.line whose cheque_no matches
        this cheque's name (cheque number). Returns the line or
        an empty recordset if not found — meaning this cheque is
        not linked to any microfinance document.
        """
        self.ensure_one()
        return self.env['microfinance.line'].search([
            ('cheque_no', '=', self.name),
        ], limit=1)

    def _update_microfinance_cheque_line(self, new_state_cheque):
        """
        Update the state_cheque on the matching microfinance.line.

        new_state_cheque:
            'cleared' → called from action_clear  (cheque cleared by bank)
            'bounced' → called from action_bounce (cheque returned/bounced)
            'draft'   → reset to draft on re-bounce after correction
        """
        self.ensure_one()
        line = self._get_microfinance_line()
        if not line:
            return  # Not a microfinance cheque — skip silently
        line.write({'state_cheque': new_state_cheque})

    def action_show_pos_order(self):
        pos_order = self.env['pos.order'].search([('pos_cheque_id', '=', self.id)])
        return {
            'name': 'POS Order',
            'type': 'ir.actions.act_window',
            'res_model': 'pos.order',
            'context': {
                'edit': '0',
                'delete': '0',
            },
            'view_mode': 'form',
            'res_id': pos_order.id,
            'target': 'new',
        }

    def action_clear(self):
        self._update_microfinance_cheque_line('cleared')  # microfinance line → Cleared
        self.state = 'clear'

    def action_bounce(self):
        if self.bounce_count >= 3:
            raise ValidationError('You cannot bounce the cheque more than 3 times.')
        self._update_microfinance_cheque_line('bounced')  # microfinance line → Bounced
        self.bounce_count += 1
        self.state = 'bounce'

    def action_cancel(self):
        self.state = 'cancel'