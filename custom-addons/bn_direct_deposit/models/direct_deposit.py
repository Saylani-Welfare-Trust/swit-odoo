from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError, ValidationError

import re
import base64
import logging

_logger = logging.getLogger(__name__)

TREASURY_GROUP = 'bn_pos_cheque.pos_cheque_menu_group'
POS_GROUP = 'bn_direct_deposit.direct_deposit_pos_action_group'

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
    payment_type = fields.Selection([
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
        ('directdeposit', 'Direct Deposit'),
    ], string="Payment Type", default='directdeposit')
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
    # program modules (bn_welfare, bn_medical_equipment) add their own type
    source_model = fields.Selection([
        ('microfinance', 'Microfinance'),
        ('donation_home_service', 'Donation Home Service'),
    ], string="Source Type")
    source_record_id = fields.Integer(string="Source Record ID")

    # ---------- CLEAR NOTIFICATION ----------
    def _build_dd_receipt_message(self):
        self.ensure_one()
        donation_items = ""
        for line in self.direct_deposit_line_ids:
            donation_items += f"{line.quantity} x {line.product_id.name} = {line.amount * line.quantity} PKR\n"

        return f"""Dear {self.donor_id.name},

Thank you for your donation!

Reference: {self.name}
Amount: {self.amount} PKR
Items:
{donation_items}

May Allah bless you!

- SWIT"""

    def _generate_dd_receipt_pdf(self):
        try:
            pdf_data, _ = self.env['ir.actions.report']._render_qweb_pdf(
                'bn_direct_deposit.report_direct_deposit_dn',
                [self.id]
            )
            return pdf_data
        except Exception as e:
            _logger.error('DD receipt PDF error: %s', str(e))
            return None

    def _save_dd_receipt_attachment(self, pdf_data):
        self.ensure_one()
        safe_name = self.name.replace('/', '_')
        filename = f"Receipt_{safe_name}.pdf"

        Attachment = self.env['ir.attachment'].sudo()
        Attachment.search([
            ('res_model', '=', 'direct.deposit'),
            ('res_id', '=', self.id),
            ('name', '=', filename)
        ]).unlink()

        # not public: the link below carries its own access token
        attachment = Attachment.create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf_data),
            'res_model': 'direct.deposit',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })
        attachment.generate_access_token()

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        pdf_url = f"{base_url}/web/content/{attachment.id}?access_token={attachment.access_token}&download=true"

        return attachment, pdf_url

    def _send_clear_notification(self):
        """Send WhatsApp (with PDF receipt) and/or SMS to the donor when a
        direct deposit is cleared. Mirrors pos.order.send_whatsapp_after_payment
        but is driven off this record's own donor/lines instead of a POS order."""
        self.ensure_one()
        donor = self.donor_id
        if not donor:
            _logger.warning('DD %s cleared with no donor_id set - skipping notification', self.name)
            return {'status': 'error', 'message': 'No donor on this deposit'}

        message = self._build_dd_receipt_message()

        whatsapp_ok = False
        sms_ok = False
        whatsapp_error = None
        sms_error = None

        if donor.whatsapp:
            try:
                pdf_data = self._generate_dd_receipt_pdf()
                if not pdf_data or not pdf_data.startswith(b'%PDF'):
                    raise Exception("Invalid PDF generated")

                attachment, pdf_url = self._save_dd_receipt_attachment(pdf_data)

                self.env['whatsapp.service'].send_template_message(
                    donor.whatsapp,
                    pdf_url,
                    f"Receipt_{self.name}.pdf"
                )
                whatsapp_ok = True
                _logger.info('DD WhatsApp sent successfully for %s', self.name)
            except Exception as e:
                whatsapp_error = str(e)
                _logger.error('DD WhatsApp failed for %s: %s', self.name, whatsapp_error)
        else:
            whatsapp_error = "No WhatsApp number"

        mobile = donor.mobile or donor.phone
        if mobile:
            try:
                self.env['sms.service'].send_sms(mobile, message)
                sms_ok = True
                _logger.info('DD SMS sent successfully for %s', self.name)
            except Exception as e:
                sms_error = str(e)
                _logger.error('DD SMS failed for %s: %s', self.name, sms_error)
        else:
            sms_error = "No contact number"

        if whatsapp_ok and sms_ok:
            return {'status': 'success', 'message': 'WhatsApp and SMS sent successfully'}
        if whatsapp_ok:
            return {'status': 'warning', 'message': f'WhatsApp sent. SMS failed: {sms_error}'}
        if sms_ok:
            return {'status': 'warning', 'message': f'SMS sent. WhatsApp failed: {whatsapp_error}'}
        return {
            'status': 'error',
            'message': f'WhatsApp failed: {whatsapp_error}. SMS failed: {sms_error}'
        }

    def _get_donor_account_lines(self):
        """Lines paid into the donor's advance donation account."""
        self.ensure_one()
        return self.direct_deposit_line_ids.filtered(
            lambda l: l.product_id and (
                l.product_id.is_advance_donation
                or (l.product_id.name or '').strip() == 'Donor A/c'
            )
        )

    def _get_non_donor_lines(self):
        donor_lines = self._get_donor_account_lines()
        return self.direct_deposit_line_ids - donor_lines

    def _create_advance_donation_receipts(self):
        """For every advance donation line on this direct deposit, create a
        paid advance.donation.receipt. Only runs when the deposit is
        cleared - not at creation time."""
        self.ensure_one()
        donor_lines = self._get_donor_account_lines()
        Receipt = self.env['advance.donation.receipt'].sudo()
        created = Receipt

        for line in donor_lines:
            amount = line.amount * line.quantity
            if amount <= 0:
                continue

            receipt = Receipt.create({
                'donor_id': self.donor_id.id,
                'amount': amount,
                'product_id': line.product_id.id,
                'payment_type': self.payment_type or 'directdeposit',
                'date': fields.Date.today(),
                'direct_deposit_id': self.id,
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

        return self.sudo().search([
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('direct_deposit') or 'New'

            # the donee of a microfinance request is the donor of its deposit
            if vals.get('microfinance_id') and not vals.get('donor_id'):
                mf = self.env['microfinance'].sudo().browse(vals['microfinance_id'])
                if mf.donee_id:
                    vals['donor_id'] = mf.donee_id.id

        return super().create(vals_list)

    def calculate_amount(self):
        for rec in self:
            rec.amount = sum(line.amount * line.quantity for line in rec.direct_deposit_line_ids)

    def set_remarks(self):
        for rec in self:
            rec.remarks = "-".join(line.remarks for line in rec.direct_deposit_line_ids if line.remarks)

    def _find_microfinance_from_source(self, source_request_type, source_request_no):
        """Resolve the exact microfinance record the POS popup auto-filled
        (via source_request_no / record_number), so the DD record can be
        linked directly instead of relying on a later text match."""
        if source_request_type != 'Microfinance' or not source_request_no:
            return self.env['microfinance']

        return self.env['microfinance'].sudo().search([
            '|', ('name', '=', source_request_no), ('old_system_record', '=', source_request_no)
        ], limit=1)

    def _prepare_dd_source_vals(self, data):
        """Link the deposit to the request the POS popup paid for. Returns
        the values to add to the deposit; raises UserError when the request
        cannot be found. Program modules (bn_welfare, bn_medical_equipment)
        extend it for their own request types."""
        source_request_type = data.get('source_request_type')
        source_request_no = data.get('source_request_no')

        if source_request_type == 'Donation Home Service' and source_request_no:
            dhs = self.env['donation.home.service'].sudo().search([
                ('name', '=', source_request_no),
                ('donor_id', '=', data.get('donor_id')),
            ], limit=1)
            if not dhs:
                raise UserError(_('Donation Home Service record %s was not found for this donor.') % source_request_no)
            return {'source_model': 'donation_home_service', 'source_record_id': dhs.id}

        mf = self._find_microfinance_from_source(source_request_type, source_request_no)
        if source_request_type == 'Microfinance' and source_request_no and not mf:
            raise UserError(_('Microfinance request %s was not found.') % source_request_no)
        if mf:
            return {'source_model': 'microfinance', 'source_record_id': mf.id, 'microfinance_id': mf.id}
        return {}

    def _check_dd_pos_access(self):
        if not self.env.su and not (self.env.user.has_group(POS_GROUP) or self.env.user.has_group(TREASURY_GROUP)):
            raise AccessError(_('You are not allowed to record direct deposits.'))

    @api.model
    def create_dd_record(self, data):
        self._check_dd_pos_access()

        transaction_ref = data.get('transaction_ref')
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

        try:
            source_vals = self._prepare_dd_source_vals(data)
        except UserError as e:
            return {'status': 'error', 'body': e.args[0]}

        product_lines = []
        for line in data['order_lines']:
            product = self.env['product.product'].browse(line['product_id'])
            amount = line.get('price')
            if not amount:
                # unit price incl. taxes when the POS sent none
                amount = product.lst_price
                for tax in product.taxes_id:
                    if tax.amount_type == 'percent':
                        amount += product.lst_price * (tax.amount / 100)
                    else:
                        amount += tax.amount
            product_lines.append((0, 0, {
                'product_id': product.id,
                'quantity': line['quantity'],
                'amount': amount,
                'remarks': line.get('remarks') or '',
            }))

        dd_vals = {
            'donor_id': data['donor_id'],
            'bank_id': data.get('bank_id'),
            'user_id': data.get('user_id') or self.env.user.id,
            'address': data.get('address'),
            'service_charges': data.get('service_charges'),
            'transaction_ref': transaction_ref,
            'payment_type': data.get('payment_type') or 'directdeposit',
            'transfer_to_dhs': data.get('transfer_to_dhs', False),
            'direct_deposit_line_ids': product_lines,
        }
        dd_vals.update(source_vals)

        # created for the cashier: POS users only read deposits
        dd = self.sudo().create(dd_vals)
        if dd.source_model == 'donation_home_service':
            self.env['donation.home.service'].sudo().browse(dd.source_record_id).write({'direct_deposit_id': dd.id})

        dd.calculate_amount()
        dd.set_remarks()
        return {"status": "success", "id": dd.id}

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

        line_vals = []
        total_amount = 0.0

        for line in non_donor_lines:
            credit_account = (
                line.product_id.property_account_income_id
                or line.product_id.categ_id.property_account_income_categ_id
            )
            if not credit_account:
                raise ValidationError(_("Missing credit account for product %s") % line.product_id.name)

            line_amount = line.amount * line.quantity
            line_vals.append((0, 0, {
                "name": credit_account.name,
                "account_id": credit_account.id,
                "credit": line_amount,
                "debit": 0,
                "company_id": self.env.company.id,
                "date_maturity": fields.Date.today(),
            }))
            total_amount += line_amount

        prefix = self.env['direct.deposit.account.setup'].sudo().search([], limit=1)
        receivable_account = self.env['account.account'].search([
            ('code', '=', prefix.name),
            ('company_id', '=', self.env.company.id)
        ], limit=1) if prefix.name else self.env['account.account']
        if not receivable_account:
            raise ValidationError(_("Missing debit account for the direct deposit."))

        line_vals.append((0, 0, {
            "name": receivable_account.name,
            "account_id": receivable_account.id,
            "debit": total_amount,
            "credit": 0,
            "company_id": self.env.company.id,
            "date_maturity": fields.Date.today(),
        }))

        self.move_id = self.env["account.move"].create({
            "move_type": "entry",
            "date": fields.Date.today(),
            "ref": self.name,
            "journal_id": self.bank_id.id,
            "line_ids": line_vals,
        })

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

    def _apply_microfinance_payment(self):
        """Apply the deposit to the installments of the microfinance request
        it was made for, and create a microfinance.installment receipt for
        each portion paid, so the payment shows up under Security/Installment
        Receipts - the same way a payment made through the POS 'mf' popup
        does. Only the request linked to the deposit is used: never another
        loan of the same donor."""
        microfinance_record = self.microfinance_id.sudo()
        if not microfinance_record:
            return False

        payment_amount = sum(line.amount * line.quantity for line in self._get_non_donor_lines())
        if payment_amount <= 0:
            return False

        lines = microfinance_record.microfinance_line_ids.filtered(
            lambda line: line.state in ('unpaid', 'partial') and (line.amount - line.paid_amount) > 0
        )
        if not lines:
            return False

        MicrofinanceInstallment = self.env['microfinance.installment'].sudo()
        remaining_amount = payment_amount
        applied_any = False

        for line in lines.sorted('due_date'):
            if remaining_amount <= 0:
                break

            applied_amount = line._apply_direct_deposit_payment(remaining_amount)
            if applied_amount <= 0:
                continue

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

    def _clear_source(self):
        """Apply the cleared deposit to the request it paid. Returns True
        when the request took the money (then no donation entry is made).
        Program modules extend it for their own source_model."""
        self.ensure_one()
        return self._apply_microfinance_payment()

    # ---------- LIFECYCLE ----------
    def _check_dd_treasury(self):
        if not self.env.su and not self.env.user.has_group(TREASURY_GROUP):
            raise AccessError(_('Only Treasury users can clear direct deposits.'))

    def _check_dd_state(self, allowed, action):
        labels = dict(self._fields['state']._description_selection(self.env))
        for rec in self:
            if rec.state not in allowed:
                raise UserError(_('"%(action)s" is not possible for direct deposit %(name)s in status "%(state)s".') % {
                    'action': action, 'name': rec.name, 'state': labels.get(rec.state, rec.state)})

    def action_clear(self):
        self._check_dd_treasury()
        self._check_dd_state(('draft',), _('Clear'))

        for rec in self:
            rec._create_advance_donation_receipts()

            if not rec._clear_source():
                if rec.transfer_to_dhs:
                    rec._transfer_to_dhs()
                else:
                    rec._create_invoice()
                    rec._create_stock_picking()

            rec.dhs_ids.sudo().write({'state': 'paid'})
            if rec.source_model == 'donation_home_service':
                rec.env['donation.home.service'].sudo().browse(rec.source_record_id).exists().write({'state': 'paid'})
            rec.state = 'clear'

            try:
                rec._send_clear_notification()
            except Exception as e:
                _logger.error('DD %s: notification step failed: %s', rec.name, str(e))

        return self.action_print_receipt()

    def action_print_receipt(self):
        return self.env.ref('bn_direct_deposit.report_direct_deposit_dn').report_action(self)

    def action_not_clear(self):
        """The money never reached the bank. Nothing was applied to the
        request while the deposit was a draft, so there is nothing to undo."""
        self._check_dd_treasury()
        self._check_dd_state(('draft',), _('Not Clear'))
        self.state = 'not_clear'

    def _transfer_to_dhs(self):
        self.ensure_one()

        DHS = self.env['donation.home.service'].sudo()
        DHSLine = self.env['donation.home.service.line'].sudo()

        non_donor_lines = self._get_non_donor_lines()

        service_lines = non_donor_lines.filtered(
            lambda l: l.product_id.type == 'service'
        )
        consu_lines = non_donor_lines.filtered(
            lambda l: l.product_id.detailed_type == 'product'
        )

        for lines, vals in (
            (service_lines, {'address': self.address or self.donor_id.street or '', 'state': 'gate_in'}),
            (consu_lines, {'address': self.donor_id.street or '', 'service_charges': self.service_charges, 'state': 'draft'}),
        ):
            if not lines:
                continue
            dhs = DHS.create(dict(vals, **{
                'donor_id': self.donor_id.id,
                'amount': sum(line.amount * line.quantity for line in lines),
                'direct_deposit_id': self.id,
            }))
            for line in lines:
                DHSLine.create({
                    'donation_home_service_id': dhs.id,
                    'product_id': line.product_id.id,
                    'quantity': line.quantity,
                    'amount': line.amount,
                })

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
        return [
            {'id': bank.id, 'name': bank.name}
            for bank in self.env['account.journal'].search([('show_in_pos', '=', True)])
        ]
