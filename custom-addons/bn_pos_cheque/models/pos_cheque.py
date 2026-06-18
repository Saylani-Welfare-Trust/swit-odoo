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
    name = fields.Char('Cheque Number')
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

    def _get_microfinance_pdc_line(self):
        """Get the PDC line linked to this cheque"""
        self.ensure_one()
        return self.env['microfinance.pdc.line'].search([
            ('cheque_no', '=', self.name),
        ], limit=1)

    def _get_microfinance_line(self):
        """Get the microfinance.line linked through the PDC line"""
        self.ensure_one()
        pdc_line = self._get_microfinance_pdc_line()
        return pdc_line.microfinance_line_id if pdc_line else None

    def _update_microfinance_cheque_line(self, new_state_cheque):
        """Update the state_cheque on the matching microfinance.pdc.line"""
        self.ensure_one()
        pdc_line = self._get_microfinance_pdc_line()
        if pdc_line:
            pdc_line.write({'state_cheque': new_state_cheque})

    def _update_microfinance_installment_state(self, new_state):
        """Update the state of the linked microfinance.line"""
        self.ensure_one()
        microfinance_line = self._get_microfinance_line()
        if microfinance_line:
            microfinance_line.write({
                'state': new_state,
                'paid_amount': microfinance_line.amount if new_state == 'paid' else 0,
                'payment_date': fields.Date.today() if new_state == 'paid' else False
            })

    def action_show_pos_order(self):
        pos_order = self.env['pos.order'].search([('pos_cheque_id', '=', self.id)])
        return {
            'name': 'POS Order',
            'type': 'ir.actions.act_window',
            'res_model': 'pos.order',
            'context': {'edit': '0', 'delete': '0'},
            'view_mode': 'form',
            'res_id': pos_order.id,
            'target': 'new',
        }

    def action_clear(self):
        """When cheque clears: Update PDC line to cleared, microfinance line to paid"""
        self._update_microfinance_cheque_line('cleared')
        self._update_microfinance_installment_state('paid')
        self.state = 'clear'

    def action_bounce(self):
        """When cheque bounces: Update PDC line to bounced, microfinance line back to unpaid"""
        if self.bounce_count >= 3:
            raise ValidationError('You cannot bounce the cheque more than 3 times.')
        
        self._update_microfinance_cheque_line('bounced')
        self._update_microfinance_installment_state('unpaid')
        self.bounce_count += 1
        self.state = 'bounce'

    def action_cancel(self):
        """When cheque is cancelled: Reset PDC line to draft, microfinance line to unpaid"""
        self._update_microfinance_cheque_line('draft')
        self._update_microfinance_installment_state('unpaid')
        self.state = 'cancel'