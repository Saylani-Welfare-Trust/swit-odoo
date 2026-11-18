from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import base64
import logging

_logger = logging.getLogger(__name__)


state_selection = [
    ('draft', 'Draft'),
    ('posted', 'Posted')
]

notification_selection = [
    ('pending', 'Pending'),
    ('sent', 'Sent'),
    ('failed', 'Failed')
]


class Donation(models.Model):
    _name = 'donation'
    _description = "Donation"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    donor_id = fields.Many2one('res.partner', string="Donor / Student", tracking=True)
    journal_id = fields.Many2one('account.journal', string="Journal", tracking=True)
    product_id = fields.Many2one('product.product', string="Product", tracking=True)
    gateway_config_id = fields.Many2one('gateway.config', string="Gateway Config", tracking=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.user.company_id.id)
    currency_id = fields.Many2one(related='company_id.currency_id', string="Currency")
    import_donation_id = fields.Many2one('import.donation', string="Import Donation")

    name = fields.Char('Name', default="New", tracking=True)
    transaction_id = fields.Char('Transaction ID', tracking=True)

    reference = fields.Text('Reference/Remarks', tracking=True)
    
    date = fields.Char('Date', tracking=True)

    amount = fields.Monetary('Amount', tracking=True)

    is_fee = fields.Boolean('Is Fee', tracking=True)

    state = fields.Selection(selection=state_selection, string="State", default="draft", tracking=True)
    notification_state = fields.Selection(selection=notification_selection, string="WhatsApp / SMS", copy=False)
    notification_result = fields.Char('WhatsApp / SMS Result', copy=False)

    # ---------- DONATION NOTIFICATION ----------
    def _build_donation_receipt_message(self):
        self.ensure_one()

        return f"""Dear {self.donor_id.name},

Thank you for your donation!

Reference: {self.name}
Transaction ID: {self.transaction_id or '-'}
Amount: {self.amount:,.2f} {self.currency_id.name or 'PKR'}
Purpose: {self.product_id.name or '-'}

May Allah bless you!

- SWIT"""

    def _generate_donation_receipt_pdf(self):
        try:
            pdf_data = self.env['ir.actions.report']._render_qweb_pdf(
                'bn_import_donation.donation_form',
                [self.id]
            )[0]
            return pdf_data
        except Exception as e:
            _logger.error('Donation receipt PDF error: %s', str(e))
            return None

    def _save_donation_receipt_attachment(self, pdf_data):
        self.ensure_one()
        safe_name = self.name.replace('/', '_')
        filename = f"Receipt_{safe_name}.pdf"

        old = self.env['ir.attachment'].search([
            ('res_model', '=', 'donation'),
            ('res_id', '=', self.id),
            ('name', '=', filename)
        ])
        old.unlink()

        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf_data),
            'res_model': 'donation',
            'res_id': self.id,
            'mimetype': 'application/pdf',
            'public': True,
        })
        attachment.generate_access_token()

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        pdf_url = f"{base_url}/web/content/{attachment.id}?access_token={attachment.access_token}&download=true"

        return attachment, pdf_url

    def _send_donation_notification(self):
        """Send WhatsApp (with PDF receipt) and/or SMS to the donor of an
        imported (wallet) donation. Mirrors pos.order.send_whatsapp_after_payment
        but is driven off this record's own donor instead of a POS order."""
        self.ensure_one()
        donor = self.donor_id
        if not donor:
            _logger.warning('Donation %s has no donor_id set - skipping notification', self.name)
            return {'status': 'error', 'message': 'No donor on this donation'}

        message = self._build_donation_receipt_message()

        whatsapp_ok = False
        sms_ok = False
        whatsapp_error = None
        sms_error = None

        if donor.whatsapp:
            try:
                pdf_data = self._generate_donation_receipt_pdf()
                if not pdf_data or not pdf_data.startswith(b'%PDF'):
                    raise Exception("Invalid PDF generated")

                attachment, pdf_url = self._save_donation_receipt_attachment(pdf_data)
                _logger.info('Donation receipt PDF URL: %s', pdf_url)

                self.env['whatsapp.service'].send_template_message(
                    donor.whatsapp,
                    pdf_url,
                    attachment.name
                )
                whatsapp_ok = True
                _logger.info('Donation WhatsApp sent successfully for %s', self.name)
            except Exception as e:
                whatsapp_error = str(e)
                _logger.error('Donation WhatsApp failed for %s: %s', self.name, whatsapp_error)
        else:
            whatsapp_error = "No WhatsApp number"

        mobile = donor.mobile or donor.phone
        if mobile:
            try:
                self.env['sms.service'].send_sms(mobile, message)
                sms_ok = True
                _logger.info('Donation SMS sent successfully for %s', self.name)
            except Exception as e:
                sms_error = str(e)
                _logger.error('Donation SMS failed for %s: %s', self.name, sms_error)
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

    @api.model
    def _cron_send_donation_notifications(self, limit=30):
        """An import can hold hundreds of donations, so the messages go out
        from this cron instead of the import's Confirm button."""
        donations = self.search([('notification_state', '=', 'pending')], order='id', limit=limit)

        for donation in donations:
            # Taken out of the queue before sending: if the worker dies half
            # way, the donor is never messaged again on the next run.
            donation.write({
                'notification_state': 'failed',
                'notification_result': 'Interrupted while sending',
            })
            self.env.cr.commit()

            try:
                result = donation._send_donation_notification()
                donation.write({
                    'notification_state': 'failed' if result['status'] == 'error' else 'sent',
                    'notification_result': result['message'],
                })
                self.env.cr.commit()
            except Exception as e:
                self.env.cr.rollback()
                _logger.error('Donation %s: notification step failed: %s', donation.name, str(e))

        if self.search_count([('notification_state', '=', 'pending')]):
            self.env.ref('bn_import_donation.send_donation_notification_cron')._trigger()


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('import_donation') or ('New')

        return super(Donation, self).create(vals)
    
    def action_confirm(self):
        self.state = 'posted'
    
    def action_draft(self):
        self.state = 'draft'

    def action_sync_existing_donors(self):
        import base64
        from io import BytesIO
        import openpyxl
        import xlrd

        if not self:
            raise ValidationError(_("No donation records selected. Please select one or more donations first."))

        Partner = self.env['res.partner']
        GLITCH_NAME = '3 START KK MART'

        fixed_count = 0
        skipped_count = 0

        # cache parsed excel name_map per import_donation_id, so we don't re-parse per row
        name_map_cache = {}

        def get_name_map(import_donation):
            if import_donation.id in name_map_cache:
                return name_map_cache[import_donation.id]

            name_map = {}
            if import_donation.import_file:
                data = base64.b64decode(import_donation.import_file)
                stream = BytesIO(data)

                if data[:4] == b'PK\x03\x04':
                    workbook = openpyxl.load_workbook(stream)
                    sheet = workbook.active
                    headers = [c.value for c in next(sheet.iter_rows(min_row=1, max_row=1))]
                    rows = sheet.iter_rows(min_row=2, values_only=True)
                elif data[:4] == b'\xD0\xCF\x11\xE0':
                    workbook = xlrd.open_workbook(file_contents=data)
                    sheet = workbook.sheet_by_index(0)
                    headers = sheet.row_values(0)
                    rows = (sheet.row_values(i) for i in range(1, sheet.nrows))
                else:
                    rows = []
                    headers = []

                if 'Id' in headers and 'From name' in headers:
                    id_idx = headers.index('Id')
                    name_idx = headers.index('From name')
                    for row in rows:
                        raw_id = row[id_idx]
                        if isinstance(raw_id, float) and raw_id.is_integer():
                            txn_id = str(int(raw_id))
                        else:
                            txn_id = str(raw_id or '').strip()
                        from_name = row[name_idx]
                        if txn_id and from_name:
                            name_map[txn_id] = from_name

            name_map_cache[import_donation.id] = name_map
            return name_map

        for donation in self:
            if not donation.donor_id or (donation.donor_id.name or '').strip() != GLITCH_NAME:
                skipped_count += 1
                continue
            txn_id = (donation.transaction_id or '').strip()

            # 1st try: donor_student_name already on the valid line
            source_line = self.env['valid.import.donation'].search([
                ('transaction_id', '=', txn_id)
            ], limit=1)

            correct_name = False
            if source_line and source_line.donor_student_name:
                correct_name = source_line.donor_student_name.strip()

            # 2nd try: fall back to reading the Excel file directly
            if not correct_name:
                import_donation = donation.import_donation_id or (source_line.import_donation_id if source_line else False)
                if import_donation:
                    name_map = get_name_map(import_donation)
                    correct_name = name_map.get(txn_id)

            if not correct_name or correct_name == GLITCH_NAME:
                skipped_count += 1
                continue

            partner = Partner.search([('name', '=', correct_name)], limit=1)

            if not partner:
                partner = Partner.create({
                    'name': correct_name,
                    'mobile': source_line.mobile if source_line else False,
                    'cnic_no': source_line.cnic_no if source_line else False,
                    'email': source_line.email if source_line else False,
                })

            donation.donor_id = partner.id

            # also backfill the valid.import.donation line, so future runs don't hit this again
            if source_line and not source_line.donor_student_name:
                source_line.donor_student_name = correct_name

            fixed_count += 1

        if fixed_count == 0:
            raise ValidationError(
                _("No donations were fixed. None of the selected records currently "
                  "show '%s', or no name could be found in the linked import line "
                  "or the uploaded Excel file. %s record(s) were skipped.")
                % (GLITCH_NAME, skipped_count)
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Donor Name Fixed'),
                'message': _('%s donation(s) fixed, %s skipped.') % (fixed_count, skipped_count),
                'type': 'success',
                'sticky': False,
            },
        }