from odoo import models, fields, api, _
from datetime import date as td


class AdvanceDonationLine(models.Model):
    _name = 'advance.donation.lines'
    # _table = 'advance_donation_line_new'   
    welfare_id = fields.Many2one('welfare', string="Linked Welfare")
    welfare_line_id = fields.Many2one('welfare.line', string="Linked Welfare Line")
    microfinance_id = fields.Many2one('microfinance', string="Linked Microfinance")
    advance_donation_id = fields.Many2one('advance.donation', 'Donation ID', ondelete='cascade', required=True)
    linked_record_disbursed = fields.Boolean(
        string="Linked Record Disbursed",
        compute='_compute_linked_record_disbursed',
        store=True
    )
    # advance_donation_id = fields.Integer(string="Temp Fix")  # 👈 TEMP
    serial_no = fields.Char('Serial No.')
    product_id = fields.Many2one('product.product', 'Product')
    amount = fields.Monetary('Amount', currency_field='currency_id')

    paid_amount = fields.Monetary('Paid Amount', currency_field='currency_id')
    remaining_amount = fields.Monetary('Remaining Amount', currency_field='currency_id')
    disbursed_amount = fields.Monetary('Disbursed Amount', currency_field='currency_id')    
    state = fields.Selection([
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial'),
        ('paid', 'Paid')],
        string='Status', compute='_compute_installment_state', store=True)

    donation_state = fields.Selection([
        ('draft', 'Draft'),
        ('approval_1', 'Approval 1'),
        ('approval_2', 'Approval 2'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')],
        default='draft',
        string='Donation State', related='advance_donation_id.state')
    approved_date = fields.Datetime('Approved Date', related='advance_donation_id.approved_date')
    is_disbursed = fields.Boolean('Is Disbursed?', compute='_compute_disbursement_and_disbursed')
    currency_id = fields.Many2one('res.currency', 'Currency', related='advance_donation_id.currency_id', readonly=True)

    date = fields.Date(
        string='Date',
        help='Date of this line (visible if contract type is frequency based)',
    )
    disbursement_date = fields.Date(
        string='Disbursement Date',
        compute='_compute_disbursement_and_disbursed',
        help='Date when the disbursement is made'
    )

    date_visibility = fields.Boolean(
        string='Date Visibility',
        help='Controls the visibility of the date field in the tree view. It is set to True if the contract type is frequency based, otherwise False.',
        compute='_compute_date_visibility'
    )
    @api.depends('disbursed_amount', 'paid_amount', 'linked_record_disbursed')
    def _compute_disbursement_and_disbursed(self):
        for rec in self:
            # Check if there's already a disbursement line
            disbursement_line = self.env['advance.donation.disbursement.line'].search([
                ('advance_donation_line_id', '=', rec.id)
            ], limit=1)
            
            if disbursement_line:
                rec.is_disbursed = True
                rec.disbursement_date = disbursement_line.date or fields.Date.today()
            else:
                # Check if linked record is disbursed
                if rec.linked_record_disbursed:
                    # Auto-create disbursement line
                    rec._create_disbursement_line()
                    rec.is_disbursed = True
                    rec.disbursement_date = fields.Date.today()
                else:
                    rec.is_disbursed = False
                    rec.disbursement_date = False

    
    @api.depends('advance_donation_id.contract_type')
    def _compute_date_visibility(self):
        for rec in self:
            if rec.advance_donation_id.contract_type == 'frequency':
                rec.date_visibility = True
            else: rec.date_visibility = False
    
    def _create_disbursement_line(self):
        """Create disbursement line when linked record is disbursed"""
        self.ensure_one()
        
        if not self.advance_donation_id:
            return
        
        # Check if disbursement line already exists
        existing = self.env['advance.donation.disbursement.line'].search([
            ('advance_donation_line_id', '=', self.id)
        ], limit=1)
        
        if existing:
            return
        
        # Determine source type
        source_type = "Welfare"
        source_id = False
        
        if self.welfare_line_id:
            source_type = "Welfare Line"
            source_id = self.welfare_line_id.id
            # Get welfare ID if available
            if hasattr(self.welfare_line_id, 'welfare_id'):
                welfare = self.welfare_line_id.welfare_id
            elif hasattr(self.welfare_line_id, 'welfare'):
                welfare = self.welfare_line_id.welfare
            else:
                welfare = False
        elif self.microfinance_id:
            source_type = "Microfinance"
            source_id = self.microfinance_id.id
            welfare = False
        else:
            welfare = False
        
        # Create disbursement line
        disbursement_vals = {
            'advance_donation_id': self.advance_donation_id.id,
            'advance_donation_line_id': self.id,
            'product_id': self.product_id.id,
            'date': fields.Date.today(),
            'total_amount': self.amount,
            'advance_amount': self.paid_amount or self.amount,
            'disbursed_amount': self.paid_amount or self.amount,
            'disbursed_record': f"Disbursed from {source_type}",
        }
        
        # Add references
        if self.welfare_line_id:
            disbursement_vals['welfare_line_id'] = self.welfare_line_id.id
        if welfare:
            disbursement_vals['welfare_id'] = welfare.id
        if self.microfinance_id:
            disbursement_vals['microfinance_id'] = self.microfinance_id.id
        
        # Create the disbursement line
        disbursement = self.env['advance.donation.disbursement.line'].create(disbursement_vals)
        
        # Update disbursed_amount on donation line
        self.write({
            'disbursed_amount': self.paid_amount or self.amount
        })
        
        # Also update the advance donation's total if needed
        self.advance_donation_id._compute_disbursement_totals()
        
        return disbursement

    def _compute_installment_state(self):
        for rec in self:
            if rec.paid_amount < rec.amount and rec.paid_amount != 0:
                rec.state = 'partial'
            elif rec.paid_amount == rec.amount:
                rec.state = 'paid'
            else:
                rec.state = 'unpaid'

    
    def action_print_line_non_cash_report(self):
        """Print non-cash donation report for this specific line"""
        return self.env.ref('bn_advance_donation.action_report_advance_donation_line_non_cash').report_action(self)
    
    @api.depends('welfare_line_id', 'microfinance_id')
    def _compute_linked_record_disbursed(self):
        """Check if the linked welfare line or microfinance record is disbursed"""
        for rec in self:
            rec.linked_record_disbursed = False
            
            # Check if linked welfare line is disbursed
            if rec.welfare_line_id:
                # Check for disbursement status in welfare.line
                if hasattr(rec.welfare_line_id, 'state'):
                    rec.linked_record_disbursed = rec.welfare_line_id.state in ['disbursed', 'done', 'completed']
                elif hasattr(rec.welfare_line_id, 'is_disbursed'):
                    rec.linked_record_disbursed = rec.welfare_line_id.is_disbursed
                elif hasattr(rec.welfare_line_id, 'disbursed_date'):
                    rec.linked_record_disbursed = bool(rec.welfare_line_id.disbursed_date)
                elif hasattr(rec.welfare_line_id, 'date_disbursed'):
                    rec.linked_record_disbursed = bool(rec.welfare_line_id.date_disbursed)
                    
            # Check if linked microfinance is disbursed
            elif rec.microfinance_id:
                if hasattr(rec.microfinance_id, 'state'):
                    rec.linked_record_disbursed = rec.microfinance_id.state in ['disbursed', 'done', 'completed']
                elif hasattr(rec.microfinance_id, 'is_disbursed'):
                    rec.linked_record_disbursed = rec.microfinance_id.is_disbursed
                elif hasattr(rec.microfinance_id, 'disbursed_date'):
                    rec.linked_record_disbursed = bool(rec.microfinance_id.disbursed_date)
                elif hasattr(rec.microfinance_id, 'date_disbursed'):
                    rec.linked_record_disbursed = bool(rec.microfinance_id.date_disbursed)
    
