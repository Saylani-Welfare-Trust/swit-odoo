from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.sql import column_exists, create_column, table_exists
from datetime import date as td


class AdvanceDonationLine(models.Model):
    _name = 'advance.donation.lines'
    # _table = 'advance_donation_line_new'   

    advance_donation_id = fields.Many2one('advance.donation', 'Donation ID', ondelete='cascade', required=True)
    # advance_donation_id = fields.Integer(string="Temp Fix")  # 👈 TEMP
    serial_no = fields.Char('Serial No.')
    product_id = fields.Many2one('product.product', 'Product')
    description = fields.Char('Description')
    quantity = fields.Integer(
        'Quantity',
        default=1,
        help='Number of products this line stands for (frequency based contracts have one line per day)',
    )
    amount = fields.Monetary('Amount', currency_field='currency_id')
    service_charge_amount = fields.Monetary(
        'Service Charge Amount',
        currency_field='currency_id',
    )

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
    is_disbursed = fields.Boolean('Is Disbursed?', default=False)
    currency_id = fields.Many2one('res.currency', 'Currency', related='advance_donation_id.currency_id', readonly=True)

    date = fields.Date(
        string='Date',
        help='Date of this line (visible if contract type is frequency based)',
    )
    disbursement_date = fields.Date(
        string='Disbursement Date',
        compute='_compute_disbursement_and_disbursed',
        store=True,
        readonly=False,
        help='Date when the disbursement is made'
    )

    date_visibility = fields.Boolean(
        string='Date Visibility',
        help='Controls the visibility of the date field in the tree view. It is set to True if the contract type is frequency based, otherwise False.',
        compute='_compute_date_visibility'
    )

    def _auto_init(self):
        # disbursement_date used to be recomputed to today on every read. Now that
        # it is stored, lines already disbursed get the date of their last change
        # instead of the date of the module upgrade.
        cr = self.env.cr
        if table_exists(cr, self._table) and not column_exists(cr, self._table, 'disbursement_date'):
            create_column(cr, self._table, 'disbursement_date', 'date')
            if column_exists(cr, self._table, 'is_disbursed'):
                cr.execute(
                    "UPDATE advance_donation_lines SET disbursement_date = write_date::date WHERE is_disbursed"
                )
        return super()._auto_init()

    @api.depends('is_disbursed')
    def _compute_disbursement_and_disbursed(self):
        for rec in self:
            if not rec.is_disbursed:
                rec.disbursement_date = False
            elif not rec.disbursement_date:
                # Keep a date entered manually, only default it to today
                rec.disbursement_date = td.today()
    
    @api.depends('advance_donation_id.contract_type')
    def _compute_date_visibility(self):
        for rec in self:
            if rec.advance_donation_id.contract_type == 'frequency':
                rec.date_visibility = True
            else: rec.date_visibility = False
    
    @api.depends('paid_amount', 'amount')
    def _compute_installment_state(self):
        for rec in self:
            if rec.paid_amount < rec.amount and rec.paid_amount != 0:
                rec.state = 'partial'
            elif rec.paid_amount == rec.amount:
                rec.state = 'paid'
            else:
                rec.state = 'unpaid'
    
    def action_print_line_non_cash_report(self):
        """Print non-cash donation report for the given line(s)"""
        not_disbursed = self.filtered(lambda l: not l.is_disbursed)
        if not_disbursed:
            raise UserError(_('Only disbursed lines can be printed. Not disbursed: %s')
                            % ', '.join(not_disbursed.mapped(lambda l: l.serial_no or l.product_id.display_name or str(l.id))))
        return self.env.ref('bn_advance_donation.action_report_advance_donation_line_non_cash').report_action(self)

    def _get_receipt_day(self):
        """Day a line stands for on the receipt: its own date (frequency based), else the disbursement date"""
        self.ensure_one()
        if self.advance_donation_id.contract_type == 'product':
            # Quantity based lines only carry the day they were computed
            return self.disbursement_date
        return self.date or self.disbursement_date

    def _get_receipt_groups(self, per_day=True):
        """Lines with the same product and day are merged into one receipt item"""
        groups = {}
        for line in self.sorted(lambda l: (l._get_receipt_day() or td.min, l.id)):
            key = (line.product_id.id, line._get_receipt_day() if per_day else None)
            groups[key] = groups.get(key, self.browse()) | line
        return list(groups.values())
    
