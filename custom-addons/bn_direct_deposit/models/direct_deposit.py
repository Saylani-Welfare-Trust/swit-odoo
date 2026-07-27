from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import re
import logging

_logger = logging.getLogger(__name__)


status_selection = [       
    ('draft', 'Draft'),
    ('clear', 'Clear'),
    ('not_clear', 'Not Clear'),
    ('transferred', 'Transferred to DHS')
]


class DirectDeposit(models.Model):
    _name = 'direct.deposit'
    _description = "Direct Deposit"
    _order = "id desc"

    favor = fields.Char('favor')
    cnic_no = fields.Char('CNIC No.', size=15)
    bank_id = fields.Many2one('account.journal', string="Bank")
    donor_id = fields.Many2one('res.partner', string="Donor")
    microfinance_id = fields.Many2one('microfinance', string="Microfinance")
    user_id = fields.Many2one('res.users', string="Created By", default=lambda self: self.env.user)
    analytic_account_id = fields.Many2one('account.analytic.account', string="Branch Location", related='user_id.employee_id.analytic_account_id', store=True, readonly=True)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    country_code_id = fields.Many2one(related='donor_id.country_code_id', string="Country Code", store=True)

    address = fields.Char('Address')
    name = fields.Char('Name', default="New")
    transaction_ref = fields.Char('Transaction Reference')
    
    remarks = fields.Text('Remarks')

    transfer_to_dhs=fields.Boolean('Transfer to DHS', default=False)
    
    state = fields.Selection(selection=status_selection, string="Status", default="draft")
    
    amount = fields.Monetary('Amount', currency_field='currency_id')
    service_charges = fields.Monetary('Service Charges', currency_field='currency_id')

    move_id = fields.Many2one('account.move', string="Journal Entry")
    picking_id = fields.Many2one('stock.picking', string="Picking")

    mobile = fields.Char(related='donor_id.mobile', string="Mobile No.", size=10)
    
    dhs_ids = fields.One2many('donation.home.service', 'direct_deposit_id', string="Donation Home Service Records")

    direct_deposit_line_ids = fields.One2many('direct.deposit.line', 'direct_deposit_id', string="Direct Deposit Lines")


    @api.constrains('mobile')
    def _check_mobile_number(self):
        for rec in self:
            if rec.mobile:
                if not re.fullmatch(r"\d{10}", rec.mobile):
                    raise ValidationError(
                        "Mobile number must contain exactly 10 digits."
                    )

    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('direct_deposit') or ('New')

        # If a microfinance record is provided, set donor if missing.
        # transaction_ref is no longer auto-filled from the microfinance
        # record - it's independent, free-text data entered by the user.
        if vals.get('microfinance_id') and not vals.get('donor_id'):
            mf = self.env['microfinance'].browse(vals.get('microfinance_id'))
            if mf and mf.donee_id:
                vals['donor_id'] = mf.donee_id.id

        return super(DirectDeposit, self).create(vals)
    
    def calculate_amount(self):
        self.amount = 0

        for line in self.direct_deposit_line_ids:
            self.amount += line.amount*line.quantity

    def set_remarks(self):
        remarks = []
        for line in self.direct_deposit_line_ids:
            if line.remarks:
                remarks.append(line.remarks)
        
        self.remarks = "-".join(remarks)

    def _find_microfinance_from_source(self, source_request_type, source_request_no):
        """Resolve the exact microfinance record the POS popup auto-filled
        (via source_request_no / record_number), so the DD record can be
        linked directly instead of relying on a later text match."""
        _logger.info("DD create - source_request_type=%r source_request_no=%r", source_request_type, source_request_no)

        if source_request_type != 'Microfinance' or not source_request_no:
            _logger.info("DD create - skipping microfinance lookup (type/no missing or mismatched)")
            return self.env['microfinance']

        mf = self.env['microfinance'].search([
            '|', ('name', '=', source_request_no), ('old_system_record', '=', source_request_no)
        ], limit=1)

        _logger.info("DD create - microfinance search result: %r (id=%s)", mf, mf.id if mf else False)

        return mf

    @api.model
    def create_dd_record(self, data):
        address = data.get('address')
        bank_id = data.get('bank_id')
        service_charges = data.get('service_charges')
        user_id = data.get('user_id') or self.env.user.id
        transaction_ref = data.get('transaction_ref')

        # -------------------------
        # 0. Resolve the microfinance record this DD is tied to, based on
        #    what the POS popup auto-filled (source_request_type / source_request_no)
        # -------------------------
        source_request_type = data.get('source_request_type')
        source_request_no = data.get('source_request_no')
        mf = self._find_microfinance_from_source(source_request_type, source_request_no)

        # -------------------------
        # 1. Prepare Line Items
        # -------------------------
        product_lines = []
        for line in data['order_lines']:
            product_lines.append((0, 0, {
                'product_id': line['product_id'],
                'quantity': line['quantity'],
                'amount': line['price'],
                'remarks': line['remarks'] if line.get('remarks') else '',
            }))

        # -------------------------
        # 2. Create DD Record
        # -------------------------
        dd = self.create({
            'donor_id': data['donor_id'],
            'bank_id': bank_id,
            'user_id': user_id,
            'address': address,
            'service_charges': service_charges,
            'transaction_ref': transaction_ref,
            'microfinance_id': mf.id if mf else False,
            'transfer_to_dhs': data.get('transfer_to_dhs', False),
            'direct_deposit_line_ids': product_lines,
        })

        # -------------------------
        # 3. Calculate prices & taxes for all lines
        # -------------------------
        for line in dd.direct_deposit_line_ids:
            base_price = line.product_id.lst_price
            taxes = line.product_id.taxes_id

            total_price_incl_tax = base_price
            for tax in taxes:
                if tax.amount_type == 'percent':
                    total_price_incl_tax += base_price * (tax.amount / 100)
                else:
                    total_price_incl_tax += tax.amount

            if not line.amount:
                line.amount = total_price_incl_tax * line.quantity

        # -------------------------
        # 4. Recalculate totals
        # -------------------------
        dd.calculate_amount()
        dd.set_remarks()

        return {
            "status": "success",
            "id": dd.id,
            "debug": {
                "source_request_type": source_request_type,
                "source_request_no": source_request_no,
                "matched_microfinance_id": mf.id if mf else False,
                "matched_microfinance_name": mf.name if mf else False,
            },
        }

    @api.onchange('microfinance_id')
    def _onchange_microfinance_id(self):
        for rec in self:
            if rec.microfinance_id:
                mf = rec.microfinance_id
                # transaction_ref is independent, free-text data - no longer
                # auto-filled from the microfinance record's name.
                if mf.donee_id:
                    rec.donor_id = mf.donee_id.id
    
    def _create_invoice(self):
        self.ensure_one()

        if not self.bank_id:
            raise ValidationError(_("Please select a bank for the direct deposit."))

        journal = self.env['account.journal'].browse(self.bank_id.id)

        move_vals = {
            "move_type": "entry",
            "date": fields.Date.today(),
            "ref": self.name,
            "journal_id": journal.id,
            "line_ids": [],
        }

        line_vals = []

        total_amount = 0.0

        for line in self.direct_deposit_line_ids:

            # CREDIT LINE (One per product line)
            credit_account = (
                line.product_id.property_account_income_id
                or line.product_id.categ_id.property_account_income_categ_id
            )
            if not credit_account:
                raise ValidationError(_("Missing credit account for product %s") % line.product_id.name)

            credit_line = (0, 0, {
                "name": credit_account.name,
                "account_id": credit_account.id,
                "credit": line.amount,
                "debit": 0,
                "company_id": self.env.company.id,
                "date_maturity": fields.Date.today(),
            })
            line_vals.append(credit_line)

            total_amount += line.amount

        prefix=self.env['direct.deposit.account.setup'].search([], limit=1)
        # NOW ADD ONLY ONE DEBIT LINE
        receivable_account = self.env['account.account'].search([
            ('code', '=', prefix.name),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        if not receivable_account:
            raise ValidationError(_("Missing debit account for the direct deposit."))

        debit_line = (0, 0, {
            "name": receivable_account.name,
            "account_id": receivable_account.id,
            "debit": total_amount,
            "credit": 0,
            "company_id": self.env.company.id,
            "date_maturity": fields.Date.today(),
        })
        line_vals.append(debit_line)

        move_vals["line_ids"] = line_vals

        move = self.env["account.move"].create(move_vals)

        # journal entry is parked (not posted)
        # move.action_post()  # uncomment if you want posting

        self.move_id = move.id

    def _create_stock_picking(self):
        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']

        picking_type = self.env.ref('stock.picking_type_out')
        destination_location = self.env.ref('stock.stock_location_customers')

        # ✅ Filter only storable products
        product_lines = self.direct_deposit_line_ids.filtered(
            lambda l: l.product_id and l.product_id.detailed_type == 'product'
        )

        # ❌ Do nothing if no product-type lines
        if not product_lines:
            return False

        # ✅ Create picking ONLY if product lines exist
        picking = StockPicking.create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': destination_location.id,
            'origin': self.name,
        })

        for line in product_lines:
            StockMove.create({
                'name': line.product_id.display_name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'quantity': line.quantity,
                'product_uom': line.product_id.uom_id.id,
                'picking_id': picking.id,
                'location_id': picking.location_id.id,
                'location_dest_id': destination_location.id,
            })

        picking.action_confirm()
        picking.action_assign()
        picking.button_validate()

        self.picking_id = picking.id

    def _get_target_microfinance(self):
        # Only use the microfinance record directly linked to this DD record,
        # set at creation time from the POS popup's source_request_no.
        # Text-based transaction_ref matching has been removed - it's no
        # longer a reliable way to identify the record.
        if self.microfinance_id:
            return self.microfinance_id

        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        if active_model == 'microfinance' and active_id:
            return self.env['microfinance'].browse(int(active_id)).exists()

        microfinance_id = self.env.context.get('microfinance_id') or self.env.context.get('default_microfinance_id')
        if microfinance_id:
            return self.env['microfinance'].browse(int(microfinance_id)).exists()

        if self.donor_id:
            return self.env['microfinance'].search([
                ('donee_id', '=', self.donor_id.id)
            ], limit=1, order='id desc')

        return self.env['microfinance']

    def _apply_microfinance_payment(self):
        """Apply direct deposit amount to matching microfinance installment lines,
        and create a microfinance.installment receipt for each portion paid, so
        the payment shows up under Security/Installment Receipts - the same way
        a payment made directly through the POS 'mf' popup does."""
        payment_amount = self.amount or sum(
            line.amount * line.quantity for line in self.direct_deposit_line_ids
        )
        if payment_amount <= 0:
            return False

        microfinance_record = self._get_target_microfinance()
        if not microfinance_record:
            return False

        lines = microfinance_record.mapped('microfinance_line_ids').filtered(
            lambda line: line.state in ('unpaid', 'partial') and (line.amount - line.paid_amount) > 0
        )
        if not lines:
            return False

        MicrofinanceInstallment = self.env['microfinance.installment']
        remaining_amount = payment_amount
        applied_any = False

        for line in lines.sorted('due_date'):
            if remaining_amount <= 0:
                break

            applied_amount = line._apply_direct_deposit_payment(remaining_amount)
            if applied_amount <= 0:
                continue

            # Record a receipt for this portion of the payment so it appears
            # under Security Receipts / Installment Receipts, keyed off the
            # line's own payment_type (security vs installment).
            MicrofinanceInstallment.create({
                'payment_type': line.payment_type,
                'payment_method': 'direct_deposit',
                'bank_name': self.bank_id.name if self.bank_id else False,
                'amount': applied_amount,
                'microfinance_id': microfinance_record.id,
                'donee_id': microfinance_record.donee_id.id,
                'date': fields.Date.today(),
                'state': 'paid',
                'microfinance_line_id': line.id,
            })

            applied_any = True
            remaining_amount -= applied_amount

        return applied_any

    def action_clear(self):
        if self._apply_microfinance_payment():
            self.state = 'clear'
            return self.env.ref('bn_direct_deposit.report_direct_deposit_dn').report_action(self)

        if self.transfer_to_dhs:
            self.action_transfer_to_dhs()
        else:
            self._create_invoice()
            self._create_stock_picking()

        self.state = 'clear'
        # Auto-print report when transitioning to clear (duplicate watermark)
        return self.env.ref('bn_direct_deposit.report_direct_deposit_dn').report_action(self)

    def action_not_clear(self):
        self.state = 'not_clear'

    def action_transfer_to_dhs(self):
        """Transfer confirmed direct deposit payment to Donation Home Service
        
        Splits lines by product type:
        - Service products → DHS with state 'gate_in'
        - Consumable products → DHS with state 'draft'
        - Both types → Creates separate DHS records for each
        """
        self.ensure_one()
        
        DHS = self.env['donation.home.service']
        DHSLine = self.env['donation.home.service.line']
        
        # Separate lines by product type
        service_lines = self.direct_deposit_line_ids.filtered(
            lambda l: l.product_id.type == 'service'
        )
        consu_lines = self.direct_deposit_line_ids.filtered(
            lambda l: l.product_id.detailed_type == 'product'
        )
        
        created_dhs_ids = []
        
        # Create DHS record for service products (gate_in state)
        if service_lines:
            service_amount = sum(line.amount for line in service_lines)
            dhs_service = DHS.create({
                'donor_id': self.donor_id.id,
                'amount': service_amount,
                'address': self.address or self.donor_id.street or '',
                'direct_deposit_id': self.id,
                'state': 'gate_in',
            })
            
            # Create DHS lines for service products
            for line in service_lines:
                DHSLine.create({
                    'donation_home_service_id': dhs_service.id,
                    'product_id': line.product_id.id,
                    'quantity': line.quantity,
                    'amount': line.amount,
                })
            
            created_dhs_ids.append(dhs_service.id)
        
        # Create DHS record for consumable products (draft state)
        if consu_lines:
            consu_amount = sum(line.amount for line in consu_lines)
            dhs_consu = DHS.create({
                'donor_id': self.donor_id.id,
                'amount': consu_amount,
                'address': self.donor_id.street or '',
                'direct_deposit_id': self.id,
                'service_charges': self.service_charges,
                'state': 'draft',
            })
            
            # Create DHS lines for consumable products
            for line in consu_lines:
                DHSLine.create({
                    'donation_home_service_id': dhs_consu.id,
                    'product_id': line.product_id.id,
                    'quantity': line.quantity,
                    'amount': line.amount,
                })
            
            created_dhs_ids.append(dhs_consu.id)
        self.state = 'transferred'
        if len(self.dhs_ids) == 1:
                # Open single DHS record
                return {
                    "type": "ir.actions.act_window",
                    "res_model": "donation.home.service",
                    "view_mode": "form",
                    "res_id": self.dhs_ids.id,   
                    "target": "current",
                }
        else:
                # Show list of DHS records
                return {
                    "type": "ir.actions.act_window",
                    "res_model": "donation.home.service",
                    "view_mode": "tree,form",
                    "domain": [('id', 'in', self.dhs_ids.ids)],  
                    "target": "current",
                }
   
    def action_show_invoice(self):
        return {
            "name": _("Invoice"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.move_id.id,
        }
        
    def action_show_picking(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "view_mode": "form",
            "res_id": self.picking_id.id,
        }

    def action_show_dhs_records(self):
        self.ensure_one()
        dhs_record_ids = self.dhs_ids.ids
        
        if not dhs_record_ids:
            return
        
        if len(dhs_record_ids) == 1:
            # Open single DHS record
            return {
                "type": "ir.actions.act_window",
                "res_model": "donation.home.service",
                "view_mode": "form",
                "res_id": dhs_record_ids[0],
                "target": "current",
            }
        else:
            # Show list of DHS records
            return {
                "type": "ir.actions.act_window",
                "res_model": "donation.home.service",
                "view_mode": "tree,form",
                "domain": [('id', 'in', dhs_record_ids)],
                "target": "current",
            }
        
    def get_bank_list(self):
        bank_list = [
            {'id': bank.id, 'name': bank.name}
            for bank in self.env['account.journal'].search([])
            if bank.show_in_pos
        ]

        return bank_list