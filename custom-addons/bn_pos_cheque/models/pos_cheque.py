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
    name = fields.Char('Cheque Number')
    state = fields.Selection(selection=state_selection, string="State", default='draft')
    order_reference = fields.Char('Order Reference', compute="_set_details", store=True)
    bank_name = fields.Char('Bank Name')
    date = fields.Date('Date')
    bounce_count = fields.Integer('Bounce Count')
    amount = fields.Float('Amount', compute="_set_details", store=True)
    against_record_name = fields.Char('Against Record', compute="_set_details", store=True)

    def _get_donor_account_order_lines(self):
        """Find the linked POS order's lines for the 'Donor A/c' product."""
        self.ensure_one()
        pos_order = self.env['pos.order'].search([('pos_cheque_id', '=', self.id)], limit=1)
        if not pos_order:
            return self.env['pos.order.line']

        return pos_order.lines.filtered(
            lambda l: l.product_id and (l.product_id.name or '').strip() == 'Donor A/c'
        )

    def _create_advance_donation_receipts(self):
        """For any 'Donor A/c' line on the linked POS order, create a paid
        advance.donation.receipt. Only runs when the cheque is cleared -
        not when the cheque was first created/recorded."""
        self.ensure_one()
        donor_lines = self._get_donor_account_order_lines()
        Receipt = self.env['advance.donation.receipt']
        created = Receipt

        for line in donor_lines:
            amount = line.price_subtotal_incl
            if amount <= 0:
                continue

            receipt = Receipt.create({
                'donor_id': self.donor_id.id,
                'amount': amount,
                'product_id': line.product_id.id,
                'payment_type': 'cheque',
                'cheque_number': self.name,
                'cheque_date': self.date,
                'date': fields.Date.today(),
                'remarks': 'Auto-created from POS Cheque %s' % self.name,
                'state': 'paid',
            })
            created |= receipt

        return created

    @api.depends('name')
    def _set_details(self):
        for rec in self:
            rec.donor_id = None
            # rec.analytic_account_id = None
            rec.amount = 0
            rec.order_reference = ''
            rec.against_record_name = ''
            pos_order = self.env['pos.order'].search([('pos_cheque_id', '=', rec.id)], limit=1)
            if pos_order:
                rec.donor_id = pos_order.partner_id.id
                # rec.analytic_account_id = pos_order.analytic_account_id.id
                rec.amount = pos_order.amount_total
                branch_code = pos_order.user_id.employee_id.analytic_account_id.code
                company = pos_order.company_id.name[:3].upper()
                order_date = pos_order.date_order and pos_order.date_order.year or ''
                order_ref = pos_order.name and pos_order.name[-4:] or '0000'
                rec.order_reference = f'{branch_code}-{company}-{order_date}-{order_ref}'
                rec.against_record_name = rec._get_against_record_name(pos_order)

    def _get_against_record_name(self, pos_order):
        """Return the name/sequence (e.g. 'MF/00023') of whichever source
        record - Microfinance, Medical Equipment, Welfare, Direct Deposit,
        Donation Home Service, Qurbani, Advance Donation - the linked POS
        order was raised against.

        IMPORTANT: `candidate_fields` must match the real Many2one field
        names on pos.order that store this link in your other modules
        (bn_microfinance, bn_medical_equipment, bn_welfare, etc). Update
        this list with the correct names if these guesses are wrong.
        """
        self.ensure_one()
        candidate_fields = [
            'microfinance_id',
            'medical_equipment_id',
            'welfare_id',
            'direct_deposit_id',
            'donation_home_service_id',
            'qurbani_id',
            'advance_donation_id',
        ]
        for field_name in candidate_fields:
            if field_name in pos_order._fields:
                record = pos_order[field_name]
                if record:
                    return record.name
        return ''

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
        if pdc_line and pdc_line.microfinance_line_id:
            return pdc_line.microfinance_line_id
        return None

    def _update_microfinance_cheque_line(self, new_state_cheque):
        """Update the state_cheque on the matching microfinance.pdc.line"""
        self.ensure_one()
        pdc_line = self._get_microfinance_pdc_line()
        if pdc_line:
            pdc_line.write({'state_cheque': new_state_cheque})

    def _update_microfinance_line_state(self, new_state):
        """Update the state of the linked microfinance.line"""
        self.ensure_one()
        microfinance_line = self._get_microfinance_line()
        if microfinance_line:
            if new_state == 'paid':
                microfinance_line.write({
                    'state': 'paid',
                    'paid_amount': microfinance_line.amount,
                    'payment_date': fields.Date.today()
                })
            elif new_state == 'unpaid':
                microfinance_line.write({
                    'state': 'unpaid',
                    'paid_amount': 0.0,
                    'payment_date': False
                })
            elif new_state == 'partial':
                # Handle partial payment logic if needed
                pass

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

    def _get_or_repair_microfinance_line(self, pdc_line):
        """Get microfinance line from link or fallback to installment_number search, and repair the link"""
        microfinance_line = pdc_line.microfinance_line_id
        if not microfinance_line and pdc_line.installment_number and pdc_line.microfinance_id:
            microfinance_line = self.env['microfinance.line'].search([
                ('microfinance_id', '=', pdc_line.microfinance_id.id),
                ('installment_no', '=', pdc_line.installment_number),
            ], limit=1)
            if microfinance_line:
                pdc_line.microfinance_line_id = microfinance_line.id  # self-heal
        return microfinance_line

    def action_clear(self):
        self._create_advance_donation_receipts()

        pdc_line = self._get_microfinance_pdc_line()
        if pdc_line:
            pdc_line.write({'state_cheque': 'cleared'})
            microfinance_line = self._get_or_repair_microfinance_line(pdc_line)
            if microfinance_line:
                microfinance_line.write({
                    'state': 'paid',
                    'paid_amount': microfinance_line.amount,
                    'payment_date': fields.Date.today(),
                })
        self.state = 'clear'

    def action_bounce(self):
        if self.bounce_count >= 3:
            raise ValidationError('You cannot bounce the cheque more than 3 times.')

        pdc_line = self._get_microfinance_pdc_line()
        if pdc_line:
            pdc_line.write({'state_cheque': 'bounced'})
            microfinance_line = self._get_or_repair_microfinance_line(pdc_line)
            if microfinance_line:
                microfinance_line.write({
                    'state': 'unpaid',
                    'paid_amount': 0.0,
                    'payment_date': False,
                })

        self.bounce_count += 1
        self.state = 'bounce'

    def action_cancel(self):
        pdc_line = self._get_microfinance_pdc_line()
        if pdc_line:
            pdc_line.write({'state_cheque': 'draft'})
            microfinance_line = self._get_or_repair_microfinance_line(pdc_line)
            if microfinance_line:
                microfinance_line.write({
                    'state': 'unpaid',
                    'paid_amount': 0.0,
                    'payment_date': False,
                })
        self.state = 'cancel'