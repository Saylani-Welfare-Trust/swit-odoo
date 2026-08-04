from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


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
    source_model = fields.Selection([
        ('welfare', 'Welfare'),
        ('medical_equipment', 'Medical Equipment'),
    ], string="Source Type")
    source_record_id = fields.Integer(string="Source Record ID")

    welfare_line_ids = fields.Many2many(
        'welfare.line',
        'pos_cheque_welfare_line_rel',
        'cheque_id',
        'line_id',
        string="Welfare Lines",
    )
    welfare_recurring_line_ids = fields.Many2many(
        'welfare.recurring.line',
        'pos_cheque_welfare_recurring_line_rel',
        'cheque_id',
        'recurring_line_id',
        string="Welfare Recurring Lines",
    )
    medical_security_deposit_id = fields.Many2one('medical.security.deposit', string="Security Deposit")    # ---------- WELFARE ----------
    def _update_welfare_lines_state(self, new_state):
        """new_state: 'paid'/'disbursed' or 'unpaid'/'bounced' — confirm exact
        selection values against welfare.line's state field before deploying."""
        self.ensure_one()
        if self.welfare_line_ids:
            self.welfare_line_ids.write({'state': new_state})
        if self.welfare_recurring_line_ids:
            self.welfare_recurring_line_ids.write({'state': new_state})

    # ---------- MEDICAL EQUIPMENT ----------
    def _update_medical_equipment_lines_state(self, new_state):
        self.ensure_one()
        if self.medical_equipment_line_ids:
            self.medical_equipment_line_ids.write({'state': new_state})
            
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

    # ---------- WELFARE ----------
    def _clear_welfare(self):
        self.ensure_one()
        # call the real action, not a raw write — this also handles
        # advance_donation_line_id disbursement creation and calls
        # welfare_id._auto_disburse_if_all_lines_delivered() internally
        payable_lines = self.welfare_line_ids.filtered(lambda l: l.state in ('draft', 'delivered'))
        if payable_lines:
            payable_lines.action_disbursed()

        payable_recurring = self.welfare_recurring_line_ids.filtered(lambda l: l.state in ('draft', 'delivered'))
        if payable_recurring:
            payable_recurring.action_disbursed()

    def _bounce_welfare(self):
        self.ensure_one()
        lines = self.welfare_line_ids
        recurring_lines = self.welfare_recurring_line_ids

        if lines:
            lines.write({'state': 'draft'})
            lines.mapped('welfare_id').filtered(
                lambda w: w.state == 'disbursed'
            ).write({'state': 'approve'})

        if recurring_lines:
            recurring_lines.write({'state': 'draft'})
            recurring_lines.mapped('welfare_id').filtered(
                lambda w: w.state == 'disbursed'
            ).write({'state': 'recurring'})

    # ---------- MEDICAL EQUIPMENT ----------
    def _clear_medical_equipment(self):
        self.ensure_one()
        
        # Ensure security deposit is linked
        security_deposit = self._ensure_security_deposit_link()
        
        if security_deposit:
            security_deposit.write({'state': 'paid'})
            equipment = security_deposit.medical_equipment_id
            if equipment and equipment.state == 'approved':
                equipment.write({'state': 'sd_received'})
            
            _logger.info(f"Security deposit {security_deposit.id} marked as paid for cheque {self.name}")
        else:
            _logger.warning(f"No security deposit found for cheque {self.name}")
    def _bounce_medical_equipment(self):
        self.ensure_one()
        
        # Ensure security deposit is linked
        security_deposit = self._ensure_security_deposit_link()
        
        if security_deposit:
            # Update security deposit state
            security_deposit.write({'state': 'bounced'})
            
            # Update equipment
            equipment = security_deposit.medical_equipment_id
            if equipment and equipment.state == 'sd_received':
                equipment.write({'state': 'approved'})
            
            _logger.info(f"Security deposit {security_deposit.id} marked as bounced for cheque {self.name}")
        else:
            _logger.warning(f"No security deposit found for cheque {self.name}")
    # ---------- LIFECYCLE ----------
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

        if self.source_model == 'welfare':
            self._clear_welfare()
        elif self.source_model == 'medical_equipment':
            self._clear_medical_equipment()

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

        if self.source_model == 'welfare':
            self._bounce_welfare()
        elif self.source_model == 'medical_equipment':
            self._bounce_medical_equipment()

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

        if self.source_model == 'welfare':
            self._bounce_welfare()          # same reset as bounce
        elif self.source_model == 'medical_equipment':
            raise ValidationError('Cannot cancel cheque for medical equipment. Please contact support.')
            self._bounce_medical_equipment()

        self.state = 'cancel'

    def link_security_deposit(self):
        """Link the security deposit to this cheque if not already linked"""
        self.ensure_one()

        if self.source_model != 'medical_equipment':
            return False

        if self.medical_security_deposit_id:
            return True  # already linked, nothing to do

        if not self.source_record_id:
            raise ValidationError(
                f"DEBUG: Cheque {self.name} has no source_record_id set on it."
            )

        equipment = self.env['medical.equipment'].browse(self.source_record_id)

        if not equipment.exists():
            raise ValidationError(
                f"DEBUG: medical.equipment id={self.source_record_id} does not exist."
            )

        sd_slip = equipment.sd_slip_id

        if not sd_slip:
            sd_slip = self.env['medical.security.deposit'].search(
                [('medical_equipment_id', '=', self.source_record_id)], limit=1
            )

        if not sd_slip:
            raise ValidationError(
                f"DEBUG: No medical.security.deposit found for equipment id={self.source_record_id} "
                f"(name={equipment.name}), neither via sd_slip_id nor via direct search."
            )

        self.write({'medical_security_deposit_id': sd_slip.id})
        return True


    def _ensure_security_deposit_link(self):
        self.ensure_one()
        if self.source_model == 'medical_equipment':
            if not self.medical_security_deposit_id:
                self.link_security_deposit()
            return self.medical_security_deposit_id
        return False
    
    def action_view_security_deposit(self):
        """View the linked security deposit"""
        self.ensure_one()
        if self.medical_security_deposit_id:
            return {
                'name': 'Security Deposit',
                'type': 'ir.actions.act_window',
                'res_model': 'medical.security.deposit',
                'view_mode': 'form',
                'res_id': self.medical_security_deposit_id.id,
                'target': 'new',
            }
        return {'type': 'ir.actions.act_window_close'}