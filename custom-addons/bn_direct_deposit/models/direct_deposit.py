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
    source_model = fields.Selection([
        ('microfinance', 'Microfinance'),
        ('welfare', 'Welfare'),
        ('medical_equipment', 'Medical Equipment'),
    ], string="Source Type")
    source_record_id = fields.Integer(string="Source Record ID")
    remarks = fields.Char('Remarks')
    welfare_line_ids = fields.Many2many('welfare.line', string="Welfare Lines")
    welfare_recurring_line_ids = fields.Many2many('welfare.recurring.line', string="Welfare Recurring Lines")
    medical_security_deposit_id = fields.Many2one('medical.security.deposit', string="Security Deposit")

    def _find_welfare_from_source(self, source_request_type, source_request_no):
        _logger.info("DD create - welfare lookup type=%r no=%r", source_request_type, source_request_no)
        if source_request_type != 'Welfare' or not source_request_no:
            return self.env['welfare']
        return self.env['welfare'].search(
            ['|', ('name', '=', source_request_no), ('old_system_id', '=', source_request_no)],
            limit=1
        )
    def _find_medical_equipment_from_source(self, source_request_type, source_request_no):
        _logger.info("DD create - medical equipment lookup type=%r no=%r", source_request_type, source_request_no)
        if source_request_type != 'Medical Equipment' or not source_request_no:
            return self.env['medical.equipment']
        return self.env['medical.equipment'].search(
            [('name', '=', source_request_no)], limit=1
        )
    def _get_donor_account_lines(self):
        self.ensure_one()
        donor_lines = self.direct_deposit_line_ids.filtered(
            lambda l: l.product_id and (l.product_id.name or '').strip() == 'Donor A/c'
        )
        return donor_lines
    
    
    def _get_non_donor_lines(self):
        donor_lines = self._get_donor_account_lines()
        return self.direct_deposit_line_ids - donor_lines
    

    

    def _create_advance_donation_receipts(self):
        """For every 'Donor A/c' line on this direct deposit, create a
        paid advance.donation.receipt. Only runs when the deposit is
        cleared - not at creation time."""
        self.ensure_one()
        donor_lines = self._get_donor_account_lines()
        Receipt = self.env['advance.donation.receipt']
        created = Receipt
    
        for line in donor_lines:
            amount = line.amount * line.quantity
            if amount <= 0:
                continue
    
            receipt = Receipt.create({
                'donor_id': self.donor_id.id,
                'amount': amount,
                'product_id': line.product_id.id,
                'payment_type': 'cheque',
                'date': fields.Date.today(),
                'remarks': _('Auto-created from Direct Deposit %s') % self.name,
                'state': 'paid',
            })
            created |= receipt
    
        return created
    
    def _check_duplicate_transaction_ref(self, transaction_ref):
        """Return the existing direct.deposit record (if any) that already
        uses this transaction reference. Used to block a second Direct
        Deposit payment from being made with the same transaction_ref."""
        transaction_ref = (transaction_ref or '').strip()
        if not transaction_ref:
            return self.env['direct.deposit']

        return self.search([
            ('transaction_ref', '=', transaction_ref),
        ], limit=1)



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

        source_request_type = data.get('source_request_type')
        source_request_no = data.get('source_request_no')

        mf = self._find_microfinance_from_source(source_request_type, source_request_no)
        welfare = self._find_welfare_from_source(source_request_type, source_request_no)
        equipment = self._find_medical_equipment_from_source(source_request_type, source_request_no)
        duplicate = self._check_duplicate_transaction_ref(transaction_ref)
        if duplicate:
            return {
                'status': 'error',
                'body': _(
                    'This Transaction Reference (%s) has already been used '
                    'in Direct Deposit record %s. Please use a different '
                    'transaction reference.'
                ) % (transaction_ref, duplicate.name),
            }
        product_lines = []
        for line in data['order_lines']:
            product_lines.append((0, 0, {
                'product_id': line['product_id'],
                'quantity': line['quantity'],
                'amount': line['price'],
                'remarks': line['remarks'] if line.get('remarks') else '',
            }))

        dd_vals = {
            'donor_id': data['donor_id'],
            'bank_id': bank_id,
            'user_id': user_id,
            'address': address,
            'service_charges': service_charges,
            'transaction_ref': transaction_ref,
            'microfinance_id': mf.id if mf else False,
            'transfer_to_dhs': data.get('transfer_to_dhs', False),
            'direct_deposit_line_ids': product_lines,
        }

        if welfare:
            dd_vals['source_model'] = 'welfare'
            dd_vals['source_record_id'] = welfare.id

            line_ids = [l['id'] for l in (data.get('source_welfare_line_ids') or []) if l.get('id')]
            recurring_ids = [l['id'] for l in (data.get('source_welfare_recurring_line_ids') or []) if l.get('id')]
            if line_ids:
                dd_vals['welfare_line_ids'] = [(6, 0, line_ids)]
            if recurring_ids:
                dd_vals['welfare_recurring_line_ids'] = [(6, 0, recurring_ids)]

        elif equipment:
            dd_vals['source_model'] = 'medical_equipment'
            dd_vals['source_record_id'] = equipment.id

            sd_slip = equipment.sd_slip_id
            if not sd_slip:
                sd_slip = self.env['medical.security.deposit'].search(
                    [('medical_equipment_id', '=', equipment.id)], limit=1
                )
            if sd_slip:
                dd_vals['medical_security_deposit_id'] = sd_slip.id

        elif mf:
            dd_vals['source_model'] = 'microfinance'
            dd_vals['source_record_id'] = mf.id

        dd = self.create(dd_vals)

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

        dd.calculate_amount()
        dd.set_remarks()

        return {
            "status": "success",
            "id": dd.id,
            "debug": {
                "source_request_type": source_request_type,
                "source_request_no": source_request_no,
                "matched_microfinance_id": mf.id if mf else False,
                "matched_welfare_id": welfare.id if welfare else False,
                "matched_medical_equipment_id": equipment.id if equipment else False,
            },
        }
    # ---------- WELFARE (mirrors pos.cheque) ----------
    def _clear_welfare(self):
        self.ensure_one()
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
            lines.mapped('welfare_id').filtered(lambda w: w.state == 'disbursed').write({'state': 'approve'})

        if recurring_lines:
            recurring_lines.write({'state': 'draft'})
            recurring_lines.mapped('welfare_id').filtered(lambda w: w.state == 'disbursed').write({'state': 'recurring'})

    def link_security_deposit(self):
        self.ensure_one()
        if self.source_model != 'medical_equipment' or self.medical_security_deposit_id:
            return bool(self.medical_security_deposit_id)
        if not self.source_record_id:
            return False

        equipment = self.env['medical.equipment'].browse(self.source_record_id)
        if not equipment.exists():
            return False

        sd_slip = equipment.sd_slip_id
        if not sd_slip:
            sd_slip = self.env['medical.security.deposit'].search(
                [('medical_equipment_id', '=', self.source_record_id)], limit=1
            )
        if sd_slip:
            self.write({'medical_security_deposit_id': sd_slip.id})
            return True
        return False

    def _ensure_security_deposit_link(self):
        self.ensure_one()
        if self.source_model == 'medical_equipment':
            if not self.medical_security_deposit_id:
                self.link_security_deposit()
            return self.medical_security_deposit_id
        return False

    def _clear_medical_equipment(self):
        self.ensure_one()
        equipment = self.env['medical.equipment'].browse(self.source_record_id)
        if not equipment.exists():
            return

        security_deposit = self.medical_security_deposit_id or equipment.sd_slip_id
        if not security_deposit:
            security_deposit = self.env['medical.security.deposit'].search(
                [('medical_equipment_id', '=', equipment.id)], order='id desc', limit=1
            )

        if not security_deposit:
            donee = equipment.donee_id
            security_deposit = self.env['medical.security.deposit'].create({
                'medical_equipment_id': equipment.id,
                'donee_id': donee.id if donee else False,
                'cnic_no': donee.cnic_no if donee else '',
                'amount': equipment.total_amount,
                'date': fields.Date.today(),
                'payment_method': 'cheque' if self.bank_id else 'cash',
                'bank_name': self.bank_id.name if self.bank_id else False,
                'state': 'paid',   # created directly into paid, since we're clearing right now
            })
            equipment.sd_slip_id = security_deposit.id
        else:
            security_deposit.write({'state': 'paid'})

        equipment.write({'state': 'sd_received'})

        if not self.medical_security_deposit_id:
            self.medical_security_deposit_id = security_deposit.id


    def _bounce_medical_equipment(self):
        self.ensure_one()
        equipment = self.env['medical.equipment'].browse(self.source_record_id)
        if not equipment.exists():
            return

        security_deposit = self.medical_security_deposit_id or equipment.sd_slip_id
        if not security_deposit:
            security_deposit = self.env['medical.security.deposit'].search(
                [('medical_equipment_id', '=', equipment.id)], order='id desc', limit=1
            )

        if not security_deposit:
            donee = equipment.donee_id
            security_deposit = self.env['medical.security.deposit'].create({
                'medical_equipment_id': equipment.id,
                'donee_id': donee.id if donee else False,
                'cnic_no': donee.cnic_no if donee else '',
                'amount': equipment.total_amount,
                'date': fields.Date.today(),
                'payment_method': 'cheque' if self.bank_id else 'cash',
                'bank_name': self.bank_id.name if self.bank_id else False,
                'state': 'bounced',   # created directly into bounced, since we're rejecting it now
            })
            equipment.sd_slip_id = security_deposit.id
        else:
            security_deposit.write({'state': 'bounced'})

        equipment.write({'state': 'cfo_approval'})

        if not self.medical_security_deposit_id:
            self.medical_security_deposit_id = security_deposit.id
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
    
        non_donor_lines = self._get_non_donor_lines()
        if not non_donor_lines:
            return False
    
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
    
        for line in non_donor_lines:
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
    
        prefix = self.env['direct.deposit.account.setup'].search([], limit=1)
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
        self.move_id = move.id
    

    def _create_stock_picking(self):
        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']
    
        picking_type = self.env.ref('stock.picking_type_out')
        destination_location = self.env.ref('stock.stock_location_customers')
    
        product_lines = self._get_non_donor_lines().filtered(
            lambda l: l.product_id and l.product_id.detailed_type == 'product'
        )
    
        if not product_lines:
            return False
    
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


    # ---------- LIFECYCLE ----------
    def action_clear(self):
        self._create_advance_donation_receipts()

        if self._apply_microfinance_payment():
            self.state = 'clear'
            return self.env.ref('bn_direct_deposit.report_direct_deposit_dn').report_action(self)

        if self.source_model == 'welfare':
            self._clear_welfare()
            self.state = 'clear'
            return self.env.ref('bn_direct_deposit.report_direct_deposit_dn').report_action(self)

        if self.source_model == 'medical_equipment':
            self._clear_medical_equipment()
            self.state = 'clear'
            return self.env.ref('bn_direct_deposit.report_direct_deposit_dn').report_action(self)

        if self.transfer_to_dhs:
            self.action_transfer_to_dhs()
        else:
            self._create_invoice()
            self._create_stock_picking()

        self.state = 'clear'
        return self.env.ref('bn_direct_deposit.report_direct_deposit_dn').report_action(self)

    def action_not_clear(self):
        if self.source_model == 'welfare':
            self._bounce_welfare()
        elif self.source_model == 'medical_equipment':
            self._bounce_medical_equipment()
        self.state = 'not_clear'



    def action_transfer_to_dhs(self):
        self.ensure_one()
    
        DHS = self.env['donation.home.service']
        DHSLine = self.env['donation.home.service.line']
    
        non_donor_lines = self._get_non_donor_lines()
    
        service_lines = non_donor_lines.filtered(
            lambda l: l.product_id.type == 'service'
        )
        consu_lines = non_donor_lines.filtered(
            lambda l: l.product_id.detailed_type == 'product'
        )
    
        created_dhs_ids = []
    
        if service_lines:
            service_amount = sum(line.amount for line in service_lines)
            dhs_service = DHS.create({
                'donor_id': self.donor_id.id,
                'amount': service_amount,
                'address': self.address or self.donor_id.street or '',
                'direct_deposit_id': self.id,
                'state': 'gate_in',
            })
            for line in service_lines:
                DHSLine.create({
                    'donation_home_service_id': dhs_service.id,
                    'product_id': line.product_id.id,
                    'quantity': line.quantity,
                    'amount': line.amount,
                })
            created_dhs_ids.append(dhs_service.id)
    
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
            return {
                "type": "ir.actions.act_window",
                "res_model": "donation.home.service",
                "view_mode": "form",
                "res_id": self.dhs_ids.id,
                "target": "current",
            }
        else:
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