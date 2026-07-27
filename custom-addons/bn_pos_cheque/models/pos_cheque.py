# pos_cheque.py

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
    
    # NEW: Reference fields for Welfare and Medical Equipment
    welfare_id = fields.Many2one('welfare', string="Welfare Reference", 
                                compute="_set_details", store=True,
                                help="Related Welfare record if payment is for welfare")
    medical_equipment_id = fields.Many2one('medical.equipment', string="Medical Equipment Reference", 
                                          compute="_set_details", store=True,
                                          help="Related Medical Equipment record if payment is for medical equipment")
    security_deposit_id = fields.Many2one('medical.security.deposit', string="Security Deposit Reference", 
                                         compute="_set_details", store=True,
                                         help="Related Security Deposit record")
    
    # NEW: Display name for related record
    reference_record_name = fields.Char('Reference Record Name', 
                                       compute="_compute_reference_record_name", 
                                       store=True)
    reference_type = fields.Selection([
        ('welfare', 'Welfare'),
        ('medical_equipment', 'Medical Equipment'),
        ('none', 'None')
    ], string="Reference Type", compute="_compute_reference_type", store=True)

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
            rec.welfare_id = None
            rec.medical_equipment_id = None
            rec.security_deposit_id = None
            
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
                
                # NEW: Extract welfare and medical equipment references from extra_data
                if pos_order.extra_data:
                    import json
                    extra_data = json.loads(pos_order.extra_data) if isinstance(pos_order.extra_data, str) else pos_order.extra_data
                    
                    # Check for medical equipment
                    me_data = extra_data.get('medical_equipment', {})
                    if me_data:
                        medical_equipment = self.env['medical.equipment'].search(
                            [('name', '=', me_data.get('medical_equipment_request_no'))], limit=1
                        )
                        if medical_equipment:
                            rec.medical_equipment_id = medical_equipment.id
                            # Find linked security deposit
                            security_deposit = self.env['medical.security.deposit'].search(
                                [('medical_equipment_id', '=', medical_equipment.id)], limit=1
                            )
                            if security_deposit:
                                rec.security_deposit_id = security_deposit.id

    @api.depends('welfare_id', 'medical_equipment_id')
    def _compute_reference_record_name(self):
        for rec in self:
            if rec.welfare_id:
                rec.reference_record_name = rec.welfare_id.name
            elif rec.medical_equipment_id:
                rec.reference_record_name = rec.medical_equipment_id.name
            else:
                rec.reference_record_name = ''

    @api.depends('welfare_id', 'medical_equipment_id')
    def _compute_reference_type(self):
        for rec in self:
            if rec.welfare_id:
                rec.reference_type = 'welfare'
            elif rec.medical_equipment_id:
                rec.reference_type = 'medical_equipment'
            else:
                rec.reference_type = 'none'

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
                pdc_line.microfinance_line_id = microfinance_line.id
        return microfinance_line

    def action_clear(self):
        """Clear the cheque - disburse welfare lines and mark security deposits as paid"""
        self._create_advance_donation_receipts()
    
        # Handle microfinance PDC lines
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
        
        # NEW: Handle Welfare - disburse all welfare lines
        if self.welfare_id:
            for welfare_line in self.welfare_id.welfare_line_ids:
                if welfare_line.state not in ['disbursed', 'return']:
                    welfare_line.write({'state': 'disbursed'})
            
            # Check if all lines are disbursed to update welfare state
            self.welfare_id._auto_disburse_if_all_lines_delivered()
        
        # NEW: Handle Medical Equipment Security Deposit
        if self.security_deposit_id:
            self.security_deposit_id.write({'state': 'paid'})
        
        self.state = 'clear'

    def action_bounce(self):
        """Bounce the cheque - revert welfare lines to draft and mark security deposits as bounced"""
        if self.bounce_count >= 3:
            raise ValidationError('You cannot bounce the cheque more than 3 times.')

        # Handle microfinance PDC lines
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
        
        # NEW: Handle Welfare - revert to draft
        if self.welfare_id:
            for welfare_line in self.welfare_id.welfare_line_ids:
                if welfare_line.state in ['disbursed', 'collected']:
                    welfare_line.write({'state': 'draft'})
            
            # Update welfare state back to approve
            self.welfare_id.write({'state': 'approve'})
        
        # NEW: Handle Medical Equipment Security Deposit
        if self.security_deposit_id:
            self.security_deposit_id.write({'state': 'bounced'})

        self.bounce_count += 1
        self.state = 'bounce'

    def action_cancel(self):
        """Cancel the cheque - revert to draft state"""
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
        
        # NEW: Handle Welfare - revert to draft
        if self.welfare_id:
            for welfare_line in self.welfare_id.welfare_line_ids:
                if welfare_line.state in ['disbursed', 'collected']:
                    welfare_line.write({'state': 'draft'})
            self.welfare_id.write({'state': 'approve'})
        
        # NEW: Handle Medical Equipment Security Deposit
        if self.security_deposit_id:
            self.security_deposit_id.write({'state': 'draft'})
        
        self.state = 'cancel'