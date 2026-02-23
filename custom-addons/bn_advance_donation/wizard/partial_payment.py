from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AdvanceDonationPaymentWizard(models.TransientModel):
    _name = 'advance.donation.payment.wizard'
    _description = 'Add Payment to Advance Donation'

    advance_donation_id = fields.Many2one('advance.donation', required=True)
    donor_id = fields.Many2one(related='advance_donation_id.donor_id', readonly=True)
    currency_id = fields.Many2one(related='advance_donation_id.currency_id')

    # Display total available balance from donor's paid receipts
    available_balance = fields.Monetary(string='Available Balance', currency_field='currency_id', compute='_compute_available_balance')

    # Payment amount to allocate
    payment_amount = fields.Monetary(string='Payment Amount', currency_field='currency_id', required=True)

    # Optionally, allow manual selection of receipts (or auto-select by FIFO)
    receipt_ids = fields.Many2many('advance.donation.receipt', string='Use Specific Receipts',
                                   domain="[('donor_id', '=', donor_id), ('state', '=', 'paid'), ('remaining_amount', '>', 0)]")

    @api.depends('advance_donation_id')
    def _compute_available_balance(self):
        for wizard in self:
            if wizard.donor_id:
                receipts = self.env['advance.donation.receipt'].search([
                    ('donor_id', '=', wizard.donor_id.id),
                    ('state', '=', 'paid'),
                    ('remaining_amount', '>', 0)
                ])
                wizard.available_balance = sum(receipts.mapped('remaining_amount'))
            else:
                wizard.available_balance = 0.0

    @api.constrains('payment_amount')
    def _check_payment_amount(self):
        for wizard in self:
            if wizard.payment_amount <= 0:
                raise UserError(_('Payment amount must be positive.'))
            if wizard.payment_amount > wizard.available_balance:
                raise UserError(_('Payment amount cannot exceed the available balance.'))

    def action_confirm(self):
        self.ensure_one()
        # Validate
        self._check_payment_amount()

        # Determine which receipts to use (FIFO order if none selected)
        receipts = self.receipt_ids
        if not receipts:
            receipts = self.env['advance.donation.receipt'].search([
                ('donor_id', '=', self.donor_id.id),
                ('state', '=', 'paid'),
                ('remaining_amount', '>', 0)
            ], order='date asc, id asc')

        # Call the allocation method on the advance donation
        self.advance_donation_id.allocate_payment(self.payment_amount, receipts.ids)
        return {'type': 'ir.actions.act_window_close'}