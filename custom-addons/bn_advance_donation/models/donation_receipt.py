from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError

import logging
_logger = logging.getLogger(__name__)


class DonationReceipt(models.Model):
    _name = 'advance.donation.receipt'
    _description = "Advance Donation Receipt"


    category_id = fields.Many2one('product.category', string='Category')    
    name = fields.Char(string="Name", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    is_donation_id = fields.Boolean('Donation ID?')
    donation_id = fields.Many2one('advance.donation', string='Donation ID')
    order_id = fields.Many2one('pos.order', string='POS Order')
    donor_id = fields.Many2one('res.partner', string='Donor')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)
    amount = fields.Monetary('Amount', currency_field='currency_id')
    used_amount = fields.Monetary('Used Amount', currency_field='currency_id', default=0, compute='_compute_amount', store=True)
    remaining_amount = fields.Monetary('Remaining Amount', currency_field='currency_id', compute='_compute_amount', store=True)
    update_used_amount = fields.Boolean('Update')
    date = fields.Date(string='Date', default=fields.Date.context_today)
    product_id = fields.Many2one('product.product', string='Product')
    cheque_number = fields.Char(string='Cheque Number')
    cheque_date = fields.Date(string='Cheque Date')
    bounced_reason = fields.Html(string='Reason')
    mobile_number = fields.Char(string='Mobile Number')
       # POS related fields
    pos_session_id = fields.Many2one('pos.session', string='POS Session')
    pos_order_id = fields.Many2one('pos.order', string='POS Order')
    pos_reference = fields.Char(string='POS Order Reference', copy=False, readonly=True)
    remarks = fields.Text(string='Remarks') 
    product_name = fields.Char(string='Product Name')  # If you want a separate text field
    payment_type = fields.Selection([
    ('cash', 'Cash'),
    ('cheque', 'Cheque'),
    ('directdeposit', 'Direct Deposit'),
], string="Payment Type", default='directdeposit')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('bounced', 'Bounced')],
        string='Status',
        default='draft')
    bank_id = fields.Many2one('bank', string='Bank')
    has_pos_source = fields.Boolean(compute='_compute_has_pos_source')
    has_disbursement = fields.Boolean(compute='_compute_has_disbursement')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('advance.donation.receipt') or _('New')
        return super().create(vals_list)

    def _check_receipt_state(self, allowed, action):
        labels = dict(self._fields['state'].selection)
        for rec in self:
            if rec.state not in allowed:
                raise UserError(_('"%(action)s" is not possible for %(name)s in status "%(state)s".') % {
                    'action': action, 'name': rec.name, 'state': labels.get(rec.state, rec.state)})

    def _check_treasury(self):
        if not self.env.su and not self.env.user.has_group('bn_pos_cheque.pos_cheque_menu_group'):
            raise AccessError(_('Only Treasury users can confirm or bounce a deposited cheque.'))

    @api.onchange('donation_id')
    def onchange_donation_id(self):
        if self.donation_id:
            self.donor_id = self.donation_id.donor_id.id # type: ignore

    @api.onchange('is_donation_id')
    def onchange_is_donation_id(self):
        self.donation_id = False


    def action_pending(self):
        """Deposit a cheque receipt: posted once, then waits for treasury."""
        self._check_receipt_state(('draft',), _('Deposit Cheque'))
        if not self.env.su and not self.env.user.has_group('bn_advance_donation.group_adv_don_menu'):
            raise AccessError(_('Only Advance Donation users can deposit cheques.'))
        for rec in self:
            if rec.payment_type != 'cheque':
                raise UserError(_('Only cheque receipts are deposited (%s).') % rec.name)
            if not rec.product_id:
                raise UserError(_('No product selected for account determination.'))
            product = rec.product_id
            credit_account = product.categ_id.property_account_income_categ_id or product.property_account_income_id
            debit_account = product.categ_id.property_account_expense_categ_id or product.property_account_expense_id
            if not credit_account:
                raise UserError(_('No Credit Account found on product or category.'))
            if not debit_account:
                raise UserError(_('No Debit Account found on product or category.'))
            line = {'name': rec.name, 'partner_id': rec.donor_id.id,
                    'currency_id': rec.currency_id.id if rec.currency_id else None}
            # the deposit entry is part of the receipt, not an accounting task
            move = self.env['account.move'].sudo().create({
                'ref': rec.name,
                'partner_id': rec.donor_id.id,
                'line_ids': [
                    (0, 0, dict(line, account_id=credit_account.id, credit=rec.amount, debit=0.0)),
                    (0, 0, dict(line, account_id=debit_account.id, debit=rec.amount, credit=0.0)),
                ],
                'date': fields.Date.today(),
                'move_type': 'entry',
            })
            move.action_post()
        self.write({'state': 'pending'})


    def action_bounced(self):
        self._check_receipt_state(('pending',), _('Bounced'))
        self._check_treasury()
        for rec in self:
            if not rec.bounced_reason:
                raise UserError(_('Please provide reason'))
        self.write({'state': 'bounced'})


    def action_paid(self):
        """Cash (and direct deposit) receipts are confirmed from Draft; a
        deposited cheque is confirmed by treasury once the bank pays it."""
        self._check_receipt_state(('draft', 'pending'), _('Confirm Payment'))
        for rec in self:
            if rec.state == 'pending':
                rec._check_treasury()
            elif rec.payment_type == 'cheque':
                raise UserError(_('Deposit the cheque %s first.') % rec.name)
        self.write({'state': 'paid'})

    def action_redeposit_cheque(self):
        """A new receipt for a bounced cheque, filled from this one."""
        self.ensure_one()
        self._check_receipt_state(('bounced',), _('Redeposit Cheque'))
        action = self.env['ir.actions.act_window']._for_xml_id('bn_advance_donation.action_advance_donation_receipt')
        action['views'] = [[self.env.ref('bn_advance_donation.view_advance_donation_receipt_form').id, 'form']]
        action['context'] = {
            'default_is_donation_id': bool(self.donation_id),
            'default_donation_id': self.donation_id.id,
            'default_donor_id': self.donor_id.id,
            'default_amount': self.amount,
            'default_product_id': self.product_id.id,
            'default_payment_type': self.payment_type,
            'default_currency_id': self.currency_id.id,
            'default_bank_id': self.bank_id.id,
            'default_cheque_number': self.cheque_number,
            'default_cheque_date': self.cheque_date,
        }
        return action

    @api.depends('update_used_amount')
    def _compute_amount(self):
        for rec in self:
            donation_slip_usage_lines = self.env['advance.donation.slip.usage'].search([
                ('donation_slip_id', '=', rec.id)
            ])
            rec.used_amount = sum(donation_slip_usage_lines.mapped('usage_amount'))
            rec.remaining_amount = rec.amount - rec.used_amount


    @api.ondelete(at_uninstall=False)
    def restrict_delete(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(f'You cannot delete record in {rec.state} state')


    def _get_disbursement_lines(self):
        """Disbursement lines of the advance donation(s) this receipt was used on."""
        self.ensure_one()
        usages = self.env['advance.donation.slip.usage'].search([('donation_slip_id', '=', self.id)])
        donations = self.donation_id | usages.advance_donation_id
        donations |= self.env['advance.donation'].search([('donation_slip_ids', 'in', self.ids)])
        return donations.disbursement_line_ids

    def _compute_has_disbursement(self):
        for rec in self:
            rec.has_disbursement = bool(rec._get_disbursement_lines())

    def action_print_disbursement_receipt(self):
        self.ensure_one()
        lines = self._get_disbursement_lines()
        if not lines:
            raise UserError(_('Nothing has been disbursed against this receipt yet.'))
        return lines.action_print_line_non_cash_disbursement_report()

    # ------------POS Functions----------------
    def _get_pos_source_record(self):
        """Return the POS record this receipt was created from, if any."""
        self.ensure_one()
        order = self.order_id or self.pos_order_id
        if not order and self.name:
            # Cash receipts are created from the payment screen before the
            # order reaches the backend - the order keeps the receipt number.
            order = self.env['pos.order'].search([('source_document', '=', self.name)], limit=1)
        if not order:
            # An order keeps a single source document, so it can point to
            # another receipt of the same order - use the order reference.
            reference = self.pos_reference
            if not reference and (self.cheque_number or '').startswith('POS-'):
                # Older cheque receipts only carry it in the cheque number.
                reference = self.cheque_number[4:]
            if reference:
                order = self.env['pos.order'].search([('pos_reference', '=', reference)], order='id', limit=1)
        return order

    def _get_pos_source_report(self, source):
        return self.env.ref('bn_pos_order.pos_donation_receipt_report')

    def _compute_has_pos_source(self):
        for rec in self:
            rec.has_pos_source = bool(rec._get_pos_source_record())

    def action_print_pos_receipt(self):
        # Also called from the Print menu, so several receipts can be selected.
        sources = {}
        for rec in self:
            source = rec._get_pos_source_record()
            if source:
                report = rec._get_pos_source_report(source)
                sources[report] = sources.get(report, source.browse()) | source
        if not sources:
            raise UserError(_('The selected receipt was not created from POS.'))
        if len(sources) > 1:
            raise UserError(_(
                'The selected receipts are printed with different reports (%s). Please print them separately.',
                ', '.join(report.name for report in sources),
            ))
        report, records = next(iter(sources.items()))
        return report.report_action(records)

    @api.model
    def register_pos_payment(self, data):
        """Kept for POS clients loaded before 17.0.1.3.0: receipts are now
        created by the server when the order is saved (cash) or the cheque is
        cleared, so nothing is created here (it would be a duplicate)."""
        return {"status": "success", "receipt_name": False, "receipt_id": False}
