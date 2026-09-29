from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64
from io import BytesIO
import openpyxl
import xlrd


state_selection = [
    ('draft', 'Draft'),
    ('validated', 'Validated'),
    ('uploaded', 'Uploaded'),
    ('confirmed', 'Confirmed'),
    ('sync_donor', 'Sync Donor'),
]


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
        domain="['|', ('warehouse_id', '=', warehouse_id), ('warehouse_id', '=', False)]",
        help="Operation type used for the receipt of stockable donated products. "
             "Only needed when a line's product is a storable product.")
    source_location_id = fields.Many2one(
        'stock.location', string="Source Location", compute='_compute_locations', store=True)
    destination_location_id = fields.Many2one(
        'stock.location', string="Destination Location", compute='_compute_locations', store=True)

    journal_entry_id = fields.Many2one('account.move')
    picking_id = fields.Many2one('stock.picking')

    state = fields.Selection(state_selection, default='draft', tracking=True)

    import_file = fields.Binary('Import File')

    invalid_import_donation_ids = fields.One2many(
        'invalid.import.donation', 'import_donation_id'
    )
    valid_import_donation_ids = fields.One2many(
        'valid.import.donation', 'import_donation_id'
    )

    @api.model
    def _default_warehouse_id(self):
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)], limit=1)
        return warehouse.id

    @api.depends('picking_type_id', 'picking_type_id.default_location_src_id',
                 'picking_type_id.default_location_dest_id')
    def _compute_locations(self):
        for rec in self:
            rec.source_location_id = rec.picking_type_id.default_location_src_id
            rec.destination_location_id = rec.picking_type_id.default_location_dest_id

    def _check_state(self, allowed, action):
        for rec in self:
            if rec.state not in allowed:
                raise ValidationError(_(
                    '"%(action)s" is not allowed for "%(record)s" because it is in status '
                    '"%(current)s".'
                ) % {'action': action, 'record': rec.display_name, 'current': rec.state})

    
    # =========================================================
    # Draft
    # =========================================================
    def action_draft(self):
        self._check_state(('draft', 'validated', 'uploaded', 'sync_donor'), _('Reset to Draft'))
        self.valid_import_donation_ids.unlink()
        self.invalid_import_donation_ids.unlink()

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

    # =========================================================
    # VALIDATE EXCEL
    # =========================================================
    def action_validate_excel_file(self):
        self._check_state(('draft',), _('Validate Excel'))
        if not self.import_file:
            raise ValidationError("No file uploaded.")

        data = base64.b64decode(self.import_file)
        stream = BytesIO(data)

        if data[:4] == b'PK\x03\x04':
            workbook = openpyxl.load_workbook(stream)
            sheet = workbook.active
            rows = sheet.iter_rows(min_row=2, values_only=True)

        elif data[:4] == b'\xD0\xCF\x11\xE0':
            workbook = xlrd.open_workbook(file_contents=data)
            sheet = workbook.sheet_by_index(0)
            rows = (sheet.row_values(i) for i in range(1, sheet.nrows))
        else:
            raise ValidationError("Unsupported file format.")

        Gateway = self.gateway_config_id

        header_map = {
            h.header_type_id.name: h.position
            for h in Gateway.gateway_config_header_ids
        }

        def get(row, key):
            idx = header_map.get(key)
            return row[idx] if idx is not None else None

        is_student = Gateway.name in ['SMIT', 'PIAIC']

        valid_vals, invalid_vals = [], []

        for row in rows:
            try:
                transaction_id = get(row, 'Transaction ID')
                name = get(row, 'Name')
                mobile = str(get(row, 'Cell Number') or '').strip()
                cnic = get(row, 'CNIC No.')
                email = get(row, 'Email')
                date = get(row, 'Date')
                amount = get(row, 'Amount')
                product = get(row, 'Product')
                reference = get(row, 'Reference')
                course = get(row, 'Course')

                if not amount or float(amount) < 0:
                    continue

                if mobile and len(mobile) != 10:
                    mobile = mobile[-10:]

                if is_student:
                    if self.env['donation'].search_count([
                        ('transaction_id', '=', transaction_id),
                        ('is_fee', '=', True)
                    ]):
                        continue

                    valid_vals.append({
                        'import_donation_id': self.id,
                        'transaction_id': transaction_id,
                        'donor_student_name': name,
                        'mobile': mobile,
                        'cnic_no': cnic,
                        'email': email,
                        'product': course,
                        'date': date,
                        'amount': amount,
                        'is_student': True,
                    })

                else:
                    if not product:
                        continue

                    if self.env['donation'].search_count([
                        ('transaction_id', '=', transaction_id),
                        ('is_fee', '=', False)
                    ]):
                        continue

                    valid_vals.append({
                        'import_donation_id': self.id,
                        'transaction_id': transaction_id,
                        'donor_student_name': name,
                        'mobile': mobile,
                        'cnic_no': cnic,
                        'email': email,
                        'product': product,
                        'date': date,
                        'amount': amount,
                        'reference': reference,
                        'is_student': False,
                    })

            except Exception as e:
                invalid_vals.append({
                    'import_donation_id': self.id,
                    'reason': str(e)
                })

        self.env['invalid.import.donation'].create(invalid_vals)
        self.env['valid.import.donation'].create(valid_vals)

        self.state = 'validated'

    # =========================================================
    # UPLOAD (ONLY DONATION CREATION)
    # =========================================================
    def action_upload(self):
        self._check_state(('validated',), _('Upload'))
        if not self.valid_import_donation_ids:
            raise ValidationError("No valid records.")

        Donation = self.env['donation']
        Partner = self.env['res.partner']
        cats = self._get_category_refs()
        partner_cache = {}

        donation_vals = []

        for line in self.valid_import_donation_ids:

            config_line = self.gateway_config_id.gateway_config_line_ids.filtered(
                lambda c: c.name == line.product
            )

            product = config_line.product_id if config_line else False

            partner_key = line.mobile or line.cnic_no or line.email or line.donor_student_name
            partner = partner_cache.get(partner_key)
            if not partner:
                partner = False
                if line.mobile:
                    partner = Partner.search([('mobile', '=', line.mobile)], limit=1)
                if not partner and line.cnic_no:
                    partner = Partner.search([('cnic_no', '=', line.cnic_no)], limit=1)
                if not partner and line.email:
                    partner = Partner.search([('email', '=', line.email)], limit=1)
                if not partner and line.donor_student_name:
                    partner = Partner.search([('name', '=', line.donor_student_name)], limit=1)
                if not partner:
                    partner = Partner.create({
                        'name': line.donor_student_name or f"Undefined {line.mobile}",
                        'mobile': line.mobile,
                        'cnic_no': line.cnic_no,
                        'email': line.email,
                        'category_id': [(6, 0, [
                            cats['donee'] if line.is_student else cats['donor'],
                            cats['individual'],
                        ])],
                    })
                partner_cache[partner_key] = partner

            donation_vals.append({
                'import_donation_id': self.id,
                'transaction_id': line.transaction_id,
                'donor_id': partner.id,
                'product_id': product.id if product else False,
                'date': line.date,
                'amount': line.amount,
                'reference': line.reference,
                'gateway_config_id': self.gateway_config_id.id,
                'is_fee': line.is_student,
            })

        Donation.create(donation_vals)

        self.state = 'uploaded'

    # =========================================================
    # SYNC PARTNER (ONLY PARTNER + LINKING)
    # =========================================================
    def action_sync_partner(self):
        self._check_state(('uploaded', 'sync_donor'), _('Sync Donor'))
        Partner = self.env['res.partner']
        Donation = self.env['donation']

        donation_map = {
            d.transaction_id: d
            for d in Donation.search([
                ('import_donation_id', '=', self.id),
                ('transaction_id', 'in', self.valid_import_donation_ids.mapped('transaction_id'))
            ])
        }

        partner_cache = {}

        cats = self._get_category_refs()

        for line in self.valid_import_donation_ids:

            key = line.mobile or line.cnic_no or line.email or line.donor_student_name

            if key in partner_cache:
                partner = partner_cache[key]
            else:
                partner = False
                if line.mobile:
                    partner = Partner.search([('mobile', '=', line.mobile)], limit=1)
                if not partner and line.cnic_no:
                    partner = Partner.search([('cnic_no', '=', line.cnic_no)], limit=1)
                if not partner and line.email:
                    partner = Partner.search([('email', '=', line.email)], limit=1)
                if not partner and line.donor_student_name:
                    partner = Partner.search([('name', '=', line.donor_student_name)], limit=1)

                if not partner:
                    vals = {
                        'name': line.donor_student_name or f"Undefined {line.mobile}",
                        'mobile': line.mobile,
                        'cnic_no': line.cnic_no,
                        'email': line.email,
                    }

                    vals['category_id'] = [(6, 0, [
                        cats['donee'] if line.is_student else cats['donor'],
                        cats['individual']
                    ])]

                    partner = Partner.create(vals)

                partner_cache[key] = partner

            donation = donation_map.get(line.transaction_id)
            if donation:
                donation.write({'donor_id': partner.id})

        self.state = 'sync_donor'

    # =========================================================
    # CONFIRM (ACCOUNT + STOCK CREATION HERE)
    # =========================================================
    def action_confirm(self):
        self.ensure_one()
        self._check_state(('uploaded', 'sync_donor'), _('Confirm'))

        Donation = self.env['donation']
        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']

        journal = self.env['account.journal'].search(
            [('type', '=', 'bank'), ('company_id', '=', self.company_id.id)], limit=1
        )
        if not journal:
            raise ValidationError(_("No Bank journal found for company %s.") % self.company_id.display_name)

        if not self.gateway_config_id.account_id:
            raise ValidationError(_(
                'Gateway Config "%s" has no Debit Account configured.'
            ) % self.gateway_config_id.display_name)

        donations = Donation.search([
            ('import_donation_id', '=', self.id),
            ('transaction_id', 'in', self.valid_import_donation_ids.mapped('transaction_id')),
        ])
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

        # ACCOUNT MOVE
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

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'ref': self.name,
            'line_ids': [debit] + credits,
        })

        self.journal_entry_id = move.id
        self.picking_id = picking.id if picking else False
        self.state = 'confirmed'
    
    def action_show_donations(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'donation',
            'view_mode': 'tree',
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
    @staticmethod
    def _norm_id(val):
        """Normalize an Id value so '41933352497' and 41933352497.0 match."""
        if val is None:
            return ''
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        return str(val).strip()

    def action_fetch_donor_name_from_excel(self):
        for rec in self:
            if not rec.import_file:
                raise ValidationError(f"{rec.name}: No file uploaded.")

            data = base64.b64decode(rec.import_file)
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
                raise ValidationError(f"{rec.name}: Unsupported file format.")

            try:
                id_idx = headers.index('Id')
                name_idx = headers.index('From name')
            except ValueError:
                raise ValidationError(
                    f"{rec.name}: Could not find 'Id' or 'From name' columns in the file."
                )

            name_map = {}
            for row in rows:
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
                        line.donor_student_name = match_name
                        updated += 1

            rec.message_post(body=f"Fetched donor/student names from Excel for {updated} line(s).")