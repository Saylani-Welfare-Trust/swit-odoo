from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import base64
import datetime
from io import BytesIO
import openpyxl
import xlrd

from .gateway_config import LEGACY_DEFAULT_DONOR_REGISTRATION


state_selection = [
    ('draft', 'Draft'),
    ('validated', 'Validated'),
    ('uploaded', 'Uploaded'),
    ('confirmed', 'Confirmed'),
    ('sync_donor', 'Sync Donor'),
]

USER_GROUP = 'bn_import_donation.import_donation_user_group'
MANAGER_GROUP = 'bn_import_donation.import_donation_manager_group'

# Header types the import reads (Header Type names of the gateway configuration).
HEADER_KEYS = {
    'transaction_id': 'Transaction ID',
    'name': 'Name',
    'mobile': 'Cell Number',
    'cnic_no': 'CNIC No.',
    'email': 'Email',
    'date': 'Date',
    'amount': 'Amount',
    'product': 'Product',
    'reference': 'Reference',
    'course': 'Course',
}

ROW_FIELDS = ('transaction_id', 'donor_student_name', 'mobile', 'cnic_no', 'email',
              'product', 'date', 'amount', 'reference', 'is_student')


class ImportDonation(models.Model):
    _name = 'import.donation'
    _description = "Import Donation"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    name = fields.Char('Name', tracking=True)
    file_name = fields.Char('File Name', tracking=True)

    gateway_config_id = fields.Many2one('gateway.config', tracking=True)

    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    warehouse_id = fields.Many2one(
        'stock.warehouse', string="Warehouse",
        default=lambda self: self._default_warehouse_id(),
        domain="[('company_id', '=', company_id)]")
    picking_type_id = fields.Many2one(
        'stock.picking.type', string="Operation Type",
        default=lambda self: self._default_picking_type_id(),
        domain="[('warehouse_id', '=', warehouse_id), ('bn_program', '=', 'online_donation')]",
        help="Operation type used for the receipt of stockable donated products. "
             "Only needed when a line's product is a storable product.")
    source_location_id = fields.Many2one(
        'stock.location', string="Source Location", compute='_compute_locations', store=True)
    destination_location_id = fields.Many2one(
        'stock.location', string="Destination Location", compute='_compute_locations', store=True)

    journal_entry_id = fields.Many2one('account.move')
    picking_id = fields.Many2one('stock.picking')

    state = fields.Selection(state_selection, default='draft', tracking=True, index=True)

    import_file = fields.Binary('Import File')

    invalid_import_donation_ids = fields.One2many(
        'invalid.import.donation', 'import_donation_id'
    )
    valid_import_donation_ids = fields.One2many(
        'valid.import.donation', 'import_donation_id'
    )
    donation_ids = fields.One2many('donation', 'import_donation_id', string="Donations")
    donation_count = fields.Integer('Donation Count', compute='_compute_donation_count')

    @api.model
    def _default_warehouse_id(self):
        # the user's warehouse
        return self.env['stock.warehouse']._bn_warehouse_for().id

    @api.model
    def _default_picking_type_id(self):
        return self.env['stock.warehouse']._bn_get_program_type('online_donation').id

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id_program_type(self):
        if self.warehouse_id:
            self.picking_type_id = self.warehouse_id._bn_program_type('online_donation')

    @api.depends('picking_type_id', 'picking_type_id.default_location_src_id',
                 'picking_type_id.default_location_dest_id')
    def _compute_locations(self):
        for rec in self:
            rec.source_location_id = rec.picking_type_id.default_location_src_id
            rec.destination_location_id = rec.picking_type_id.default_location_dest_id

    def _compute_donation_count(self):
        for rec in self:
            rec.donation_count = len(rec.donation_ids)

    def _check_state(self, allowed, action):
        for rec in self:
            if rec.state not in allowed:
                raise ValidationError(_(
                    '"%(action)s" is not allowed for "%(record)s" because it is in status '
                    '"%(current)s".'
                ) % {'action': action, 'record': rec.display_name,
                     'current': dict(state_selection).get(rec.state, rec.state)})

    def _check_group(self, xmlid, action):
        if not self.env.su and not self.env.user.has_group(xmlid):
            raise UserError(_('You are not allowed to "%(action)s" (group "%(group)s" required).') % {
                'action': action, 'group': self.env.ref(xmlid).full_name})

    def write(self, vals):
        if 'gateway_config_id' in vals and any(rec.state != 'draft' for rec in self):
            raise UserError(_('The Gateway Config can only be changed in Draft.'))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.state == 'confirmed':
                raise UserError(_('"%s" is confirmed and cannot be deleted.') % rec.display_name)
            if rec.donation_ids:
                raise UserError(_('Reset "%s" to Draft before deleting it.') % rec.display_name)
        return super().unlink()

    # =========================================================
    # Draft
    # =========================================================
    def action_draft(self):
        self._check_group(USER_GROUP, _('Reset to Draft'))
        self._check_state(('draft', 'validated', 'uploaded', 'sync_donor'), _('Reset to Draft'))
        # The donations of a batch that is not confirmed have no journal entry
        # yet: they are removed with the lines, so the file can be validated
        # and uploaded again (otherwise its transactions count as imported).
        self.sudo().donation_ids.unlink()
        self.sudo().valid_import_donation_ids.unlink()
        self.sudo().invalid_import_donation_ids.unlink()

        self.state = 'draft'

    # =========================================================
    # CATEGORY CACHE
    # =========================================================
    def _get_category_refs(self):
        return {
            'student': self.env.ref('bn_profile_management.student_partner_category').id,
            'donee': self.env.ref('bn_profile_management.donee_partner_category').id,
            'individual': self.env.ref('bn_profile_management.individual_partner_category').id,
            'donor': self.env.ref('bn_profile_management.donor_partner_category').id,
        }

    def _partner_tag_ids(self, is_student):
        cats = self._get_category_refs()
        return [cats['donee'] if is_student else cats['donor'], cats['individual']]

    # =========================================================
    # READ THE FILE
    # =========================================================
    @staticmethod
    def _norm_id(val):
        """Normalize an Id value so '41933352497' and 41933352497.0 match."""
        if val is None:
            return ''
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        return str(val).strip()

    @staticmethod
    def _norm_text(val):
        if val is None:
            return ''
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        if isinstance(val, datetime.datetime):
            return val.strftime('%Y-%m-%d %H:%M:%S')
        if isinstance(val, datetime.date):
            return val.strftime('%Y-%m-%d')
        return str(val).strip()

    def _read_rows(self):
        """(header row, iterator over the data rows) of the uploaded file."""
        self.ensure_one()
        if not self.import_file:
            raise ValidationError(_("No file uploaded."))
        data = base64.b64decode(self.import_file)

        if data[:4] == b'PK\x03\x04':
            workbook = openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=True)
            sheet = workbook.active
            rows = sheet.iter_rows(values_only=True)
            headers = next(rows, ()) or ()
            return list(headers), rows
        if data[:4] == b'\xD0\xCF\x11\xE0':
            workbook = xlrd.open_workbook(file_contents=data)
            sheet = workbook.sheet_by_index(0)
            if not sheet.nrows:
                return [], iter(())
            return sheet.row_values(0), (sheet.row_values(i) for i in range(1, sheet.nrows))
        raise ValidationError(_("Unsupported file format. Please upload an Excel file (.xlsx or .xls)."))

    def _column_positions(self, headers):
        """{header type name: column index}. A header with a position (0 = first
        column) uses it; a header without one (-1) is found by its name in the
        file's first row."""
        names = [self._norm_text(h).lower() for h in headers]
        positions = {}
        missing = []
        for header in self.gateway_config_id.gateway_config_header_ids:
            key = header.header_type_id.name
            if not key:
                continue
            if header.position is not None and header.position >= 0:
                positions[key] = header.position
            elif (header.name or '').strip().lower() in names:
                positions[key] = names.index(header.name.strip().lower())
            else:
                missing.append(header.name or key)
        if missing:
            raise ValidationError(_(
                'Column(s) %s of the gateway configuration were not found in the first row of the file.'
            ) % ', '.join('"%s"' % name for name in missing))
        required = [HEADER_KEYS['transaction_id'], HEADER_KEYS['amount'],
                    HEADER_KEYS['course'] if self.gateway_config_id.is_fee else HEADER_KEYS['product']]
        absent = [key for key in required if key not in positions]
        if absent:
            raise ValidationError(_(
                'The gateway configuration "%(gateway)s" has no header of type %(types)s.'
            ) % {'gateway': self.gateway_config_id.display_name,
                 'types': ', '.join('"%s"' % key for key in absent)})
        return positions

    # =========================================================
    # ROW CHECKS (also used when an invalid row is approved)
    # =========================================================
    def _check_row(self, vals, seen=None, exclude_line=None):
        """Normalise ``vals`` in place and return the reason it is invalid, or ''."""
        self.ensure_one()
        Partner = self.env['res.partner']
        vals['transaction_id'] = self._norm_id(vals.get('transaction_id'))
        if not vals['transaction_id']:
            return _('Transaction ID is missing.')

        if seen is not None:
            if vals['transaction_id'] in seen:
                return _('Transaction ID appears more than once in the file.')
            seen.add(vals['transaction_id'])

        existing = self.env['donation'].sudo().search([
            ('transaction_id', '=', vals['transaction_id']),
            ('is_fee', '=', bool(vals.get('is_student'))),
        ], limit=1)
        if existing:
            return _('Already imported (%s).') % existing.display_name
        domain = [('transaction_id', '=', vals['transaction_id']), ('import_donation_id', '=', self.id)]
        if exclude_line:
            domain.append(('id', '!=', exclude_line.id))
        if self.env['valid.import.donation'].sudo().search_count(domain):
            return _('Transaction ID is already a valid line of this import.')

        try:
            vals['amount'] = float(vals.get('amount') or 0.0)
        except (TypeError, ValueError):
            return _('Amount "%s" is not a number.') % vals.get('amount')
        if vals['amount'] <= 0:
            return _('Amount must be greater than zero.')

        vals['product'] = self._norm_text(vals.get('product'))
        if not vals['product']:
            return _('Course is missing.') if vals.get('is_student') else _('Product is missing.')
        line = self.gateway_config_id._get_product_line(vals['product'])
        if not line.product_id:
            return _('"%(product)s" is not mapped to a product in the gateway configuration "%(gateway)s".') % {
                'product': vals['product'], 'gateway': self.gateway_config_id.display_name}
        if not line.product_id.property_account_income_id:
            return _('Product "%s" has no Income Account.') % line.product_id.display_name

        raw_mobile = vals.get('mobile')
        mobile = Partner._import_normalize_mobile(raw_mobile)
        if mobile is None:
            return _('Mobile "%s" is not a valid 10 digit mobile number.') % self._norm_text(raw_mobile)
        vals['mobile'] = mobile

        raw_cnic = vals.get('cnic_no')
        cnic = Partner._import_normalize_cnic(raw_cnic)
        if cnic is None:
            return _('CNIC "%s" is not valid (13 digits, XXXXX-XXXXXXX-X).') % self._norm_text(raw_cnic)
        vals['cnic_no'] = cnic

        for key in ('donor_student_name', 'email', 'date', 'reference'):
            vals[key] = self._norm_text(vals.get(key))
        if not (vals['mobile'] or vals['cnic_no']) and not self.gateway_config_id._get_default_donor():
            return _('No donor number (mobile / CNIC) and no default donor %s.') % LEGACY_DEFAULT_DONOR_REGISTRATION
        return ''

    # =========================================================
    # VALIDATE EXCEL
    # =========================================================
    def action_validate_excel_file(self):
        self.ensure_one()
        self._check_group(USER_GROUP, _('Validate Excel'))
        self._check_state(('draft',), _('Validate Excel'))
        if not self.gateway_config_id:
            raise ValidationError(_("Please select the Gateway Config first."))

        headers, rows = self._read_rows()
        positions = self._column_positions(headers)
        is_student = self.gateway_config_id.is_fee

        def get(row, key):
            idx = positions.get(HEADER_KEYS[key])
            return row[idx] if idx is not None and idx < len(row) else None

        valid_vals, invalid_vals = [], []
        seen = set()
        for row in rows:
            if not row or all(cell in (None, '') for cell in row):
                continue
            vals = {
                'import_donation_id': self.id,
                'transaction_id': get(row, 'transaction_id'),
                'donor_student_name': get(row, 'name'),
                'mobile': get(row, 'mobile'),
                'cnic_no': get(row, 'cnic_no'),
                'email': get(row, 'email'),
                'date': get(row, 'date'),
                'amount': get(row, 'amount'),
                'product': get(row, 'course' if is_student else 'product'),
                'reference': get(row, 'reference'),
                'is_student': is_student,
            }
            original = dict(vals)
            reason = self._check_row(vals, seen)
            if reason:
                invalid_vals.append(self._invalid_vals(original, reason))
            else:
                valid_vals.append(vals)

        self.env['invalid.import.donation'].create(invalid_vals)
        self.env['valid.import.donation'].create(valid_vals)
        self._message_log(body=_('File validated: %(valid)s valid and %(invalid)s invalid row(s).') % {
            'valid': len(valid_vals), 'invalid': len(invalid_vals)})

        self.state = 'validated'

    def _invalid_vals(self, raw, reason):
        """An invalid row keeps what the file contained, so it can be corrected."""
        Partner = self.env['res.partner']
        mobile = Partner._import_normalize_mobile(raw.get('mobile'))
        cnic = Partner._import_normalize_cnic(raw.get('cnic_no'))
        try:
            amount = float(raw.get('amount') or 0.0)
        except (TypeError, ValueError):
            amount = 0.0
        return {
            'import_donation_id': self.id,
            'transaction_id': self._norm_id(raw.get('transaction_id')),
            'donor_student_name': self._norm_text(raw.get('donor_student_name')),
            # Unusable values are left empty (the line only accepts valid ones)
            # and quoted in the reason.
            'mobile': mobile or False,
            'cnic_no': cnic or False,
            'email': self._norm_text(raw.get('email')),
            'product': self._norm_text(raw.get('product')),
            'date': self._norm_text(raw.get('date')),
            'amount': amount,
            'reference': self._norm_text(raw.get('reference')),
            'is_student': bool(raw.get('is_student')),
            'reason': reason,
        }

    # =========================================================
    # UPLOAD (ONLY DONATION CREATION)
    # =========================================================
    def action_upload(self):
        self.ensure_one()
        self._check_group(USER_GROUP, _('Upload'))
        self._check_state(('validated',), _('Upload'))
        if not self.valid_import_donation_ids:
            raise ValidationError(_("No valid records."))
        failed = self._upload_lines(self.valid_import_donation_ids)
        for line, reason in failed:
            self._move_to_invalid(line, reason)
        self.env['valid.import.donation'].sudo().browse([line.id for line, reason in failed]).unlink()
        self.state = 'uploaded'
        if failed:
            self._message_log(body=_('%s line(s) could not be uploaded and were moved to the invalid lines.') % len(failed))

    def _upload_lines(self, lines):
        """Create the donations of valid ``lines``. Returns [(line, reason)] for
        the lines that could not be uploaded (already imported, donor could not
        be found or created)."""
        self.ensure_one()
        Partner = self.env['res.partner']
        partner_cache = {}
        donation_vals = []
        failed = []
        default_donor = self.gateway_config_id._get_default_donor()

        for line in lines:
            # Another batch may have uploaded the same transaction since validation.
            existing = self.env['donation'].sudo().search([
                ('transaction_id', '=', line.transaction_id), ('is_fee', '=', line.is_student)], limit=1)
            if existing:
                failed.append((line, _('Already imported (%s).') % existing.display_name))
                continue

            if not (line.mobile or line.cnic_no):
                # no donor number: the default donor
                partner, error = default_donor, _('No donor number and no default donor.')
            else:
                key = (line.cnic_no, line.mobile, (line.email or '').lower(), line.is_student)
                if key not in partner_cache:
                    partner_cache[key] = Partner._import_find_or_create_partner(
                        line.donor_student_name, mobile=line.mobile, cnic=line.cnic_no, email=line.email,
                        tag_ids=self._partner_tag_ids(line.is_student))
                partner, error = partner_cache[key]
            if not partner:
                failed.append((line, _('Donor: %s') % error))
                continue

            product = self.gateway_config_id._get_product_line(line.product).product_id
            donation_vals.append({
                'import_donation_id': self.id,
                'transaction_id': line.transaction_id,
                'donor_id': partner.id,
                'product_id': product.id,
                'date': line.date,
                'amount': line.amount,
                'reference': line.reference,
                'gateway_config_id': self.gateway_config_id.id,
                'is_fee': line.is_student,
            })

        self.env['donation'].create(donation_vals)
        return failed

    def _move_to_invalid(self, line, reason):
        vals = {name: line[name] for name in ROW_FIELDS}
        vals.update({'import_donation_id': self.id, 'reason': reason})
        self.env['invalid.import.donation'].sudo().create(vals)

    # =========================================================
    # SYNC PARTNER (ONLY PARTNER + LINKING)
    # =========================================================
    def action_sync_partner(self):
        """Link every donation of the batch to its donor again, e.g. after
        duplicate contacts were merged or contact details were completed."""
        self.ensure_one()
        self._check_group(USER_GROUP, _('Sync Donor'))
        self._check_state(('uploaded', 'sync_donor'), _('Sync Donor'))
        Partner = self.env['res.partner']
        lines = {line.transaction_id: line for line in self.valid_import_donation_ids}
        relinked = 0
        for donation in self.donation_ids:
            line = lines.get(donation.transaction_id)
            if not line:
                continue
            if not (line.mobile or line.cnic_no):
                partner = self.gateway_config_id._get_default_donor()
            else:
                partner, error = Partner._import_find_or_create_partner(
                    line.donor_student_name, mobile=line.mobile, cnic=line.cnic_no, email=line.email,
                    tag_ids=self._partner_tag_ids(line.is_student))
            if partner and partner != donation.donor_id:
                donation.donor_id = partner
                relinked += 1
        self._message_log(body=_('Donors synchronised: %s donation(s) re-linked.') % relinked)

        self.state = 'sync_donor'

    # =========================================================
    # CONFIRM (ACCOUNT + STOCK CREATION HERE)
    # =========================================================
    def action_confirm(self):
        self.ensure_one()
        self._check_group(MANAGER_GROUP, _('Confirm'))
        self._check_state(('uploaded', 'sync_donor'), _('Confirm'))

        # The Import Manager group is the gate: the transfer and the (Draft)
        # entry are created as superuser, like the API fetch does, so the
        # manager needs no Inventory / Accounting rights.
        StockPicking = self.env['stock.picking'].sudo()
        StockMove = self.env['stock.move'].sudo()

        journal = self.env['account.journal'].sudo().search(
            [('type', '=', 'bank'), ('company_id', '=', self.company_id.id)], limit=1
        )
        if not journal:
            raise ValidationError(_("No Bank journal found for company %s.") % self.company_id.display_name)

        if not self.gateway_config_id.account_id:
            raise ValidationError(_(
                'Gateway Config "%s" has no Debit Account configured.'
            ) % self.gateway_config_id.display_name)

        donations = self.donation_ids
        if not donations:
            raise ValidationError(_("No donations found to confirm for this import batch."))

        needs_stock = donations.filtered(
            lambda d: d.product_id and d.product_id.detailed_type == 'product')
        if needs_stock and not self.picking_type_id:
            raise ValidationError(_(
                'Some donated products are storable and require a stock transfer, but no '
                'Operation Type is configured on this import. Please select one.'))
        if needs_stock and (not self.source_location_id or not self.destination_location_id):
            raise ValidationError(_(
                'The operation type "%s" has no default source/destination location.'
            ) % self.picking_type_id.display_name)

        credit_groups = {}
        total = 0.0

        stock_map = {}
        picking = False

        for d in donations:

            total += d.amount

            acc = d.product_id.property_account_income_id.id if d.product_id else False
            if not acc:
                raise ValidationError(_(
                    'Donation "%(donation)s": product "%(product)s" has no Income Account '
                    'configured, so no credit line can be created for it.'
                ) % {'donation': d.display_name,
                     'product': d.product_id.display_name if d.product_id else _('(none)')})
            credit_groups[acc] = credit_groups.get(acc, 0.0) + d.amount

            if d.product_id and d.product_id.detailed_type == 'product':
                stock_map.setdefault(d.product_id.id, {'product': d.product_id, 'qty': 0})
                stock_map[d.product_id.id]['qty'] += 1

                if not picking:
                    picking = StockPicking.create({
                        'picking_type_id': self.picking_type_id.id,
                        'location_id': self.source_location_id.id,
                        'location_dest_id': self.destination_location_id.id,
                        'origin': self.name,
                    })

        # STOCK
        if picking:
            StockMove.create([
                {
                    'name': v['product'].name,
                    'product_id': v['product'].id,
                    'product_uom_qty': v['qty'],
                    'quantity': v['qty'],
                    'product_uom': v['product'].uom_id.id,
                    'picking_id': picking.id,
                    'location_id': self.source_location_id.id,
                    'location_dest_id': self.destination_location_id.id,
                }
                for v in stock_map.values()
            ])

            picking.action_confirm()
            picking.action_assign()
            picking.with_context(skip_backorder=True, skip_immediate=True).button_validate()
            if picking.state != 'done':
                raise ValidationError(_(
                    'The stock transfer %(picking)s could not be validated automatically '
                    '(status: %(state)s). Nothing has been posted.'
                ) % {'picking': picking.display_name, 'state': picking.state})

        # ACCOUNT MOVE (left in Draft for review by Accounts)
        debit = (0, 0, {
            'account_id': self.gateway_config_id.account_id.id,
            'name': f"Donations {self.name}",
            'debit': total,
        })

        credits = [
            (0, 0, {
                'account_id': acc,
                'name': 'Donation',
                'credit': amt,
            })
            for acc, amt in credit_groups.items()
        ]

        move = self.env['account.move'].sudo().create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'ref': self.name,
            'line_ids': [debit] + credits,
        })

        donations.write({'state': 'posted', 'journal_id': journal.id})
        self.journal_entry_id = move.id
        self.picking_id = picking.id if picking else False
        self.state = 'confirmed'

    def action_show_donations(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Donations'),
            'res_model': 'donation',
            'view_mode': 'tree,form',
            'domain': [('import_donation_id', '=', self.id)],
        }

    def action_show_journal_entry(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.journal_entry_id.id
        }

    def action_show_picking(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.picking_id.id
        }

    # =========================================================
    # FETCH DONOR NAME FROM EXCEL (match by transaction_id / Id)
    # =========================================================
    def action_fetch_donor_name_from_excel(self):
        for rec in self:
            headers, rows = rec._read_rows()
            headers = [rec._norm_text(h) for h in headers]
            try:
                id_idx = headers.index('Id')
                name_idx = headers.index('From name')
            except ValueError:
                raise ValidationError(
                    f"{rec.name}: Could not find 'Id' or 'From name' columns in the file."
                )

            name_map = {}
            for row in rows:
                if not row or max(id_idx, name_idx) >= len(row):
                    continue
                txn_id = self._norm_id(row[id_idx])
                from_name = row[name_idx]
                if txn_id:
                    name_map[txn_id] = from_name

            updated = 0
            for lines in (rec.valid_import_donation_ids, rec.invalid_import_donation_ids):
                for line in lines:
                    key = self._norm_id(line.transaction_id)
                    match_name = name_map.get(key)
                    if match_name and match_name != line.donor_student_name:
                        line.sudo().donor_student_name = match_name
                        updated += 1

            rec._message_log(body=f"Fetched donor/student names from Excel for {updated} line(s).")
