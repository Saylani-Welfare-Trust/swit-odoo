from odoo import models, fields
from odoo.exceptions import ValidationError

import base64
from io import BytesIO
import openpyxl
import xlrd


state_selection = [
    ('draft', 'Draft'),
    ('validated',  'Validated'),
    ('donee_created', 'Donee Created'),
    ('upload', 'Uploaded'),
]


class ImportDonation(models.Model):
    _name = 'import.donation'
    _description = "Import Donation"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char('File Name', tracking=True)

    gateway_config_id = fields.Many2one('gateway.config', string="Gateway Config", tracking=True)
    journal_entry_id = fields.Many2one('account.move', string="Journal Entry", tracking=True)
    picking_id = fields.Many2one('stock.picking', string="Picking", tracking=True)

    def _default_picking_type(self):
        picking_type = self.env.ref(
            'bn_import_donation.online_donation_stock_picking_type',
            raise_if_not_found=False
        )
        return picking_type.id if picking_type else False

    picking_type_id = fields.Many2one(
        'stock.picking.type',
        string="Picking Type",
        default=_default_picking_type
    )
    source_location_id = fields.Many2one(related='picking_type_id.default_location_src_id', string="Source Location", store=True)
    destination_location_id = fields.Many2one(related='picking_type_id.default_location_dest_id', string="Destination Location", store=True)
    state = fields.Selection(selection=state_selection, string="State", default='draft', tracking=True)

    file_name = fields.Char('File Name', tracking=True)
    import_file = fields.Binary('Import File')

    invalid_import_donation_ids = fields.One2many('invalid.import.donation', 'import_donation_id', string="Invalid Import Donations")
    valid_import_donation_ids = fields.One2many('valid.import.donation', 'import_donation_id', string="Valid Import Donations")

    # ─────────────────────────────────────────────
    # DRAFT
    # ─────────────────────────────────────────────

    def action_draft(self):
        for line in self.invalid_import_donation_ids:
            line.unlink()
        for line in self.valid_import_donation_ids:
            line.unlink()
        self.state = 'draft'

    # ─────────────────────────────────────────────
    # STEP 1 — VALIDATE EXCEL FILE
    # Parses rows, checks duplicates/courses/products,
    # buffers valid/invalid records.
    # Donee/donor partner lookup & creation is NOT done here.
    # ─────────────────────────────────────────────

    def action_validate_excel_file(self):
        if not self.import_file:
            raise ValidationError('No file uploaded.')

        file_data = base64.b64decode(self.import_file)
        if not file_data:
            raise ValidationError('The uploaded file is empty.')

        file_stream = BytesIO(file_data)

        # ── Detect file format ──────────────────────────────
        try:
            if file_data[:4] == b'PK\x03\x04':            # .xlsx
                workbook = openpyxl.load_workbook(file_stream)
                sheet = workbook.active
                rows = list(sheet.iter_rows(min_row=2, values_only=True))
            elif file_data[:4] == b'\xD0\xCF\x11\xE0':    # .xls
                workbook = xlrd.open_workbook(file_contents=file_data)
                sheet = workbook.sheet_by_index(0)
                rows = [sheet.row_values(i) for i in range(1, sheet.nrows)]
            else:
                raise ValidationError('Unsupported file format.')
        except ValidationError:
            raise
        except Exception:
            raise ValidationError('The uploaded file is not a valid Excel file.')

        ValidDonation = self.env['valid.import.donation']
        InvalidDonation = self.env['invalid.import.donation']

        valid_vals_list = []
        invalid_vals_list = []

        # ── Header mapping ──────────────────────────────────
        header_list = [(h.header_type_id.name, h.position) for h in self.gateway_config_id.gateway_config_header_ids]
        header_map = {name: pos for name, pos in header_list}

        def get_value(row, name):
            idx = header_map.get(name)
            return row[idx] if idx is not None and idx < len(row) else None

        gateway_name = self.gateway_config_id.name or ''
        is_student_import = gateway_name in ['SMIT', 'PIAIC']

        # ── Pre-collect all transaction IDs in this file for bulk duplicate check ──
        all_transaction_ids = []
        for row in rows:
            tid = get_value(row, 'Transaction ID')
            if tid:
                all_transaction_ids.append(tid)

        if is_student_import:
            existing_fee_txn_ids = set(
                self.env['donation'].search([
                    ('transaction_id', 'in', all_transaction_ids),
                    ('is_fee', '=', True),
                ]).mapped('transaction_id')
            )
        else:
            existing_txn_ids = set(
                self.env['donation'].search([
                    ('transaction_id', 'in', all_transaction_ids),
                ]).mapped('transaction_id')
            )

        # ── Pre-validate all course names in one query (student imports) ──────────
        if is_student_import:
            course_names_in_file = set()
            for row in rows:
                c = get_value(row, 'Course')
                if c:
                    course_names_in_file.add(c)

            valid_courses = self.env['product.product'].search([
                ('name', 'in', list(course_names_in_file)),
                ('is_course', '=', True),
            ])
            valid_course_names = {p.name for p in valid_courses}

        # ── Main loop ───────────────────────────────────────
        for row in rows:
            try:
                transaction_id = get_value(row, 'Transaction ID')
                name          = get_value(row, 'Name')
                mobile        = str(get_value(row, 'Cell Number') or '').strip()
                cnic          = get_value(row, 'CNIC No.')
                email         = get_value(row, 'Email')
                date          = get_value(row, 'Date')
                amount        = get_value(row, 'Amount')
                product       = get_value(row, 'Product')
                reference     = get_value(row, 'Reference')
                course        = get_value(row, 'Course')

                if not amount or float(amount) < 0:
                    continue

                # Normalize mobile
                if mobile and len(mobile) != 10:
                    mobile = mobile[-10:]

                # ══ STUDENT (DONEE) IMPORTS ═══════════════════════════
                if is_student_import:

                    if transaction_id in existing_fee_txn_ids:
                        invalid_vals_list.append({
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
                            'reason': 'A Transaction with same ID already exists in the System.',
                        })
                        continue

                    if course not in valid_course_names:
                        invalid_vals_list.append({
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
                            'reason': f'The specified course "{course}" does not exist in the System.',
                        })
                        continue

                    if not name:
                        invalid_vals_list.append({
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
                            'reason': 'Student Name is not defined.',
                        })
                        continue

                    # ✅ Partner search/create is deferred to action_create_donees
                    valid_vals_list.append({
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

                # ══ DONOR IMPORTS ══════════════════════════════════════
                else:
                    if not product:
                        continue

                    if transaction_id in existing_txn_ids:
                        invalid_vals_list.append({
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
                            'reason': 'A Transaction with same ID already exists in the System.',
                        })
                        continue

                    config_line = self.gateway_config_id.gateway_config_line_ids.filtered(
                        lambda x: x.name == product
                    )
                    product_id = config_line.mapped('product_id')

                    if not product_id:
                        invalid_vals_list.append({
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
                            'reason': f'The specified product "{product}" does not exist in the System.',
                        })
                        continue

                    # Donor partner search/create kept here (not the slow path)
                    Partner = self.env['res.partner']
                    Country = self.env['res.country'].search([('name', '=', 'Pakistan')], limit=1)
                    category_refs = {
                        'donor': self.env.ref('bn_profile_management.donor_partner_category').id,
                        'individual': self.env.ref('bn_profile_management.individual_partner_category').id,
                    }

                    donor = Partner.search([
                        ('mobile', '=', mobile),
                        ('category_id.name', 'in', ['Donor']),
                    ], limit=1)

                    if not donor and mobile:
                        donor = Partner.create({
                            'name': name or f'Undefined {mobile}',
                            'country_code_id': Country.id,
                            'mobile': mobile,
                            'cnic_no': cnic,
                            'email': email,
                            'category_id': [(6, 0, [
                                category_refs['donor'],
                                category_refs['individual'],
                            ])]
                        })
                        donor.action_register()

                    valid_vals_list.append({
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
                    })

            except Exception as e:
                InvalidDonation.create({
                    'import_donation_id': self.id,
                    'reason': f'Unexpected error processing row: {str(e)}',
                })

        InvalidDonation.create(invalid_vals_list)
        ValidDonation.create(valid_vals_list)

        self.state = 'validated'

    # ─────────────────────────────────────────────
    # STEP 2 — CREATE DONEES  (new button)
    def action_create_donees(self):
        Partner = self.env['res.partner']
        Country = self.env['res.country'].search([('name', '=', 'Pakistan')], limit=1)

        category_refs = {
            'student':    self.env.ref('bn_profile_management.student_partner_category').id,
            'donee':      self.env.ref('bn_profile_management.donee_partner_category').id,
            'individual': self.env.ref('bn_profile_management.individual_partner_category').id,
            'donor':      self.env.ref('bn_profile_management.donor_partner_category').id,
        }

        valid_records = self.env['valid.import.donation'].search([
            ('import_donation_id', '=', self.id),
        ])
        invalid_records = self.env['invalid.import.donation'].search([
            ('import_donation_id', '=', self.id),
        ])

        if not valid_records and not invalid_records:
            raise ValidationError('No records found for this import.')

        # Collect all mobiles from both
        mobiles = list(set(
            [r.mobile for r in valid_records if r.mobile] +
            [r.mobile for r in invalid_records if r.mobile]
        ))

        # Bulk fetch existing partners
        existing_donees_by_mobile = {
            p.mobile: p for p in Partner.search([
                ('mobile', 'in', mobiles),
                ('category_id.name', 'in', ['Donee']),
            ])
        }
        existing_donors_by_mobile = {
            p.mobile: p for p in Partner.search([
                ('mobile', 'in', mobiles),
                ('category_id.name', 'in', ['Donor']),
            ])
        }

        partners_to_register = []

        def process_record(record):
            mobile = record.mobile
            if not mobile:
                return

            if record.is_student:
                if mobile in existing_donees_by_mobile:
                    return
                partner = Partner.create({
                    'name': record.donor_student_name or f'Undefined {mobile}',
                    'country_code_id': Country.id,
                    'mobile': mobile,
                    'cnic_no': record.cnic_no,
                    'email': record.email,
                    'category_id': [(6, 0, [
                        category_refs['donee'],
                        category_refs['individual'],
                        category_refs['student'],
                    ])]
                })
                existing_donees_by_mobile[mobile] = partner
                partners_to_register.append(partner)
            else:
                if mobile in existing_donors_by_mobile:
                    return
                partner = Partner.create({
                    'name': record.donor_student_name or f'Undefined {mobile}',
                    'country_code_id': Country.id,
                    'mobile': mobile,
                    'cnic_no': record.cnic_no,
                    'email': record.email,
                    'category_id': [(6, 0, [
                        category_refs['donor'],
                        category_refs['individual'],
                    ])]
                })
                existing_donors_by_mobile[mobile] = partner
                partners_to_register.append(partner)

        for record in valid_records:
            process_record(record)

        for record in invalid_records:
            process_record(record)

        for partner in partners_to_register:
            partner.action_register()

        self.state = 'donee_created'

    def action_upload_excel_file(self):
        if not self.valid_import_donation_ids:
            raise ValidationError('There are no Valid Lines in Excel File.')

        journal = self.env['account.journal'].search([('name', 'ilike', 'Bank')], limit=1)
        if not journal:
            raise ValidationError("Bank journal not found.")

        default_partner = self.env['res.partner'].search(
            [('primary_registration_id', '=', '2025-9999998-9')], limit=1
        )

        Donation = self.env['donation']
        Partner = self.env['res.partner']
        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']

        credit_groups = {}
        total_amount = 0.0

        donation_vals_list = []
        stock_move_map = {}
        picking = False

        for line in self.valid_import_donation_ids:

            partner = Partner.search([('mobile', '=', line.mobile)], limit=1) or default_partner

            config_line = self.gateway_config_id.gateway_config_line_ids.filtered(
                lambda c: c.name == line.product
            )

            if not config_line:
                raise ValidationError(f"Missing configuration for: {line.product}")

            product = config_line.product_id
            product_id = product.id if product else False
            account_id = product.property_account_income_id.id

            # ── Student (fee) ───────────────────────────────
            if line.is_student:
                course = self.env['product.product'].search([
                    ('name', '=', line.product),
                    ('is_course', '=', True),
                ], limit=1)

                donation_vals_list.append({
                    'transaction_id': line.transaction_id,
                    'donor_id': partner.id,
                    'journal_id': journal.id,
                    'product_id': course.id,
                    'date': line.date,
                    'amount': line.amount,
                    'reference': line.reference,
                    'gateway_config_id': self.gateway_config_id.id,
                    'is_fee': True,
                })

            # ── Normal donation ─────────────────────────────
            else:
                donation_vals_list.append({
                    'transaction_id': line.transaction_id,
                    'donor_id': partner.id,
                    'journal_id': journal.id,
                    'product_id': product_id,
                    'date': line.date,
                    'amount': line.amount,
                    'reference': line.reference,
                    'gateway_config_id': self.gateway_config_id.id,
                })

            # ── Stock logic ─────────────────────────────────
            if product and product.detailed_type == 'product':
                stock_move_map.setdefault(product.id, {'product': product, 'qty': 0.0})
                stock_move_map[product.id]['qty'] += 1.0

                if not picking:
                    picking = StockPicking.create({
                        'picking_type_id': self.picking_type_id.id,
                        'location_id': self.source_location_id.id,
                        'location_dest_id': self.destination_location_id.id,
                        'origin': self.name,
                    })

            # ── Accounting grouping ─────────────────────────
            credit_groups[account_id] = credit_groups.get(account_id, 0.0) + line.amount
            total_amount += line.amount

        # ── Bulk create & confirm donations ────────────────
        donations = Donation.create(donation_vals_list)
        donations.action_confirm()

        # ── Stock moves ────────────────────────────────────
        if picking:
            StockMove.create([
                {
                    'name': data['product'].name,
                    'product_id': data['product'].id,
                    'product_uom_qty': data['qty'],
                    'quantity': data['qty'],
                    'product_uom': data['product'].uom_id.id,
                    'picking_id': picking.id,
                    'location_id': self.source_location_id.id,
                    'location_dest_id': self.destination_location_id.id,
                }
                for data in stock_move_map.values()
            ])
            picking.action_confirm()
            picking.action_assign()
            picking.button_validate()

        # ── Journal entry ──────────────────────────────────
        journal_entry = self.env['account.move'].sudo().create({
            'move_type': 'entry',
            'ref': self.name,
            'date': fields.Date.today(),
            'journal_id': journal.id,
            'line_ids': [
                (0, 0, {
                    'account_id': self.gateway_config_id.account_id.id,
                    'name': f'Total Donations Received from {self.name}',
                    'debit': total_amount,
                }),
                *[
                    (0, 0, {
                        'account_id': acc_id,
                        'name': 'Various Donations',
                        'credit': amt,
                    })
                    for acc_id, amt in credit_groups.items()
                ],
            ],
        })

        self.journal_entry_id = journal_entry.id
        self.state = 'upload'

    # ─────────────────────────────────────────────
    # UI ACTIONS
    # ─────────────────────────────────────────────

    def action_show_journal_entry(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.journal_entry_id.id,
        }

    def action_show_picking(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.picking_id.id,
        }