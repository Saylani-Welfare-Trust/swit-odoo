from odoo import models, fields, api, _
from odoo.addons.bn_profile_management.models.partner_tag_domain import tag_domain


state_selection = [
    ('unpaid', 'Unpaid'),
    ('partial', 'Partial'),
    ('overdue', 'Overdue'),
    ('paid', 'Paid')
]
state_cheque_selection = [
    ('draft', 'Draft'),
    ('deposited', 'Deposited'),
    ('cleared', 'Cleared'),
    ('bounced', 'Bounced')
]

class MicrofinanceLine(models.Model):
    _name = 'microfinance.line'
    _description = "Microfinance Line"


    microfinance_id = fields.Many2one('microfinance', string="Microfinance")
    product_id = fields.Many2one('product.product', related='microfinance_id.product_id', store=True, string="Product")
    
    bank_name = fields.Char('Bank Name')
    cheque_no = fields.Char('Cheque No.')
    name = fields.Char('Name', default="NEW")
    installment_no = fields.Char('Installment No.')
    installment_number = fields.Char('Installment Number')
    amount_total = fields.Monetary('Amount Total', currency_field='currency_id')

    due_date = fields.Date('Due Date')
    cheque_date = fields.Date('Cheque Date')
    payment_type = fields.Selection(selection=[
        ('security', 'Security Deposit'),
        ('installment', 'Installment Payment')
    ], string="Payment Type")
    
    amount = fields.Monetary('Amount', currency_field='currency_id', default=0)
    paid_amount = fields.Monetary('Paid Amount', currency_field='currency_id', default=0)
    remaining_amount = fields.Monetary('Remaining Amount', currency_field='currency_id', compute='_compute_remaining_amount', store=True)
    donee_id = fields.Many2one('res.partner', string="Donee", domain=tag_domain('donee', 'microfinance'))
    # NOTE: duplicate 'currency_id' declaration removed; the stored related
    # definition (store=True) is the effective one kept here.
    currency_id = fields.Many2one('res.currency', related='microfinance_id.currency_id', store=True)

    state = fields.Selection(selection=state_selection, string='State', default="unpaid")
    state_cheque = fields.Selection(selection=state_cheque_selection, string='Cheque Status', default='draft')
    is_cheque_deposit = fields.Boolean('Is Cheque Deposit')
    payment_id = fields.Many2one('microfinance.installment', string="Payment Reference")
    payment_date = fields.Date('Payment Date')
    paid_date = fields.Date('Paid Date')

    @api.depends('state')
    def _get_payment_status(self):
        for line in self:
            if line.state == 'paid':
                line.payment_status = 'Fully Paid'
            elif line.state == 'partial':
                line.payment_status = 'Partially Paid'
            elif line.state == 'overdue':
                line.payment_status = 'Overdue'
            else:
                line.payment_status = 'Unpaid'
    
    payment_status = fields.Char(compute='_get_payment_status', string='Payment Status')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'NEW') in ('NEW', _('NEW'), False):
                vals['name'] = self.env['ir.sequence'].next_by_code('microfinance_line') or ('New')
        records = super().create(vals_list)
        for res in records:
            res._update_overdue_state()
        return records

    def _update_overdue_state(self):
        """Move unpaid/partial lines past their due date to 'overdue', and
        move overdue lines back to unpaid/partial if the due date is no longer past."""
        today = fields.Date.context_today(self)
        to_overdue = self.filtered(
            lambda l: l.state in ('unpaid', 'partial') and l.due_date and l.due_date < today
        )
        not_overdue = self.filtered(
            lambda l: l.state == 'overdue' and (not l.due_date or l.due_date >= today)
        )
        back_to_partial = not_overdue.filtered(lambda l: l.paid_amount > 0)
        back_to_unpaid = not_overdue - back_to_partial
        if to_overdue:
            to_overdue.write({'state': 'overdue'})
        if back_to_partial:
            back_to_partial.write({'state': 'partial'})
        if back_to_unpaid:
            back_to_unpaid.write({'state': 'unpaid'})

    @api.model
    def _cron_update_overdue_state(self):
        self.search([
            '|',
            '&', ('state', 'in', ('unpaid', 'partial')), ('due_date', '<', fields.Date.context_today(self)),
            '&', ('state', '=', 'overdue'), '|', ('due_date', '=', False), ('due_date', '>=', fields.Date.context_today(self)),
        ])._update_overdue_state()
    
    @api.depends('due_date', 'paid_amount')
    def _compute_remaining_amount(self):
        for rec in self:
            rec.remaining_amount = rec.amount - rec.paid_amount

    def _apply_direct_deposit_payment(self, amount, payment_date=None):
        self.ensure_one()
        if amount <= 0:
            return 0

        outstanding_amount = max(self.amount - self.paid_amount, 0)
        if outstanding_amount <= 0:
            return 0

        applied_amount = min(outstanding_amount, amount)
        new_paid_amount = self.paid_amount + applied_amount
        new_state = 'paid' if new_paid_amount >= self.amount else 'partial'

        self.write({
            'paid_amount': new_paid_amount,
            'payment_date': payment_date or fields.Date.today(),
            'state': new_state,
        })

        return applied_amount

    def write(self, vals):
        if vals.get('state') == 'paid' and not vals.get('paid_date'):
            vals['paid_date'] = vals.get('payment_date') or fields.Date.today()

        res = super().write(vals)
        
        if 'state' in vals or 'paid_amount' in vals:
            for rec in self:
                # Only sync state_cheque if this line has a cheque deposit
                # If no cheque exists, state goes to paid normally — nothing extra happens
                if not rec.is_cheque_deposit:
                    continue  # ← skip, only installment state updates, state_cheque untouched
                
                if rec.state == 'paid':
                    if rec.state_cheque not in ('cleared', 'bounced'):
                        rec.state_cheque = 'deposited'
                elif rec.state in ('unpaid', 'partial', 'overdue'):
                    if rec.state_cheque == 'deposited':
                        rec.state_cheque = 'draft'

        if 'state' in vals or 'due_date' in vals:
            self._update_overdue_state()
        
        return res

    @api.depends('state', 'paid_amount')
    def _sync_cheque_state(self):
        for rec in self:
            # Only sync if this line was created via cheque deposit
            if not rec.is_cheque_deposit:
                continue
            
            if rec.state == 'paid':
                rec.state_cheque = 'deposited'
            elif rec.state == 'partial':
                rec.state_cheque = 'deposited'  # partially deposited, still counts as deposited
            elif rec.state == 'unpaid':
                rec.state_cheque = 'draft'      # reset if payment reversed