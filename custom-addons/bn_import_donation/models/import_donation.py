from odoo import models, fields
from odoo.exceptions import ValidationError

import base64
from io import BytesIO
import openpyxl
import xlrd


state_selection = [
    ('draft', 'Draft'),
    ('validated', 'Validated'),
    ('create_donor', 'Create Donor'),
    ('upload', 'Uploaded'),
    ('done', 'Done'),
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

    picking_type_id = fields.Many2one('stock.picking.type', string="Picking Type", default=_default_picking_type)
    source_location_id = fields.Many2one(related='picking_type_id.default_location_src_id', string="Source Location", store=True)
    destination_location_id = fields.Many2one(related='picking_type_id.default_location_dest_id', string="Destination Location", store=True)
    state = fields.Selection(selection=state_selection, string="State", default='draft', tracking=True)
    file_name = fields.Char('File Name', tracking=True)
    import_file = fields.Binary('Import File')
    invalid_import_donation_ids = fields.One2many('invalid.import.donation', 'import_donation_id', string="Invalid Import Donations")
    valid_import_donation_ids = fields.One2many('valid.import.donation', 'import_donation_id', string="Valid Import Donations")

    def action_draft(self):
        # Bulk unlink instead of loop — single DELETE per model
        self.invalid_import_donation_ids.unlink()
        self.valid_import_donation_ids.unlink()
        self.state = 'draft'

    def action_validate_excel_file(self):
        if not self.import_file:
            raise ValidationError('No file uploaded.')

        file_data = base64.b64decode(self.import_file)
        if not file_data:
            raise ValidationError('The uploaded file is empty.')

        file_stream = BytesIO(file_data)

        try:
            if file_data[:4] == b'PK\x03\x04':
                workbook = openpyxl.load_workbook(file_stream)
                sheet = workbook.active
                rows = sheet.iter_rows(min_row=2, values_only=True)
            elif file_data[:4] == b'\xD0\xCF\x11\xE0':
                workbook = xlrd.open_workbook(file_contents=file_data)
                sheet = workbook.sheet_by_index(0)
                rows = (sheet.row_values(i) for i in range(1, sheet.nrows))
            else:
                raise ValidationError('Unsupported file format.')
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f'The uploaded file is not a valid Excel file. Error: {str(e)}')

        header_map = {h.header_type_id.name: h.position for h in self.gateway_config_id.gateway_config_header_ids}
        gateway_name = self.gateway_config_id.name or ''
        is_student_import = gateway_name in ['SMIT', 'PIAIC']

        def get_value(row, name):
            idx = header_map.get(name)
            if idx is not None and idx < len(row):
                value = row[idx]
                return str(value).strip() if value is not None else None
            return None

        # ── PRE-LOAD all transaction IDs and courses in bulk ──────────────────
        # Collect all transaction IDs from the sheet first (two-pass approach)
        # to avoid N × search_count inside the row loop.
        all_rows = list(rows)  # materialise the generator once

        all_transaction_ids = set()
        all_course_names = set()
        all_products_in_file = set()

        for row in all_rows:
            tid = get_value(row, 'Transaction ID')
            if tid:
                all_transaction_ids.add(tid)
            if is_student_import:
                c = get_value(row, 'Course')
                if c:
                    all_course_names.add(c)
            else:
                p = get_value(row, 'Product')
                if p:
                    all_products_in_file.add(p)

        # Single bulk query for existing transaction IDs
        if is_student_import:
            existing_tids = set(
                self.env['donation'].search([
                    ('transaction_id', 'in', list(all_transaction_ids)),
                    ('is_fee', '=', True)
                ]).mapped('transaction_id')
            )
        else:
            existing_tids = set(
                self.env['donation'].search([
                    ('transaction_id', 'in', list(all_transaction_ids))
                ]).mapped('transaction_id')
            )

        # Single bulk query for valid courses
        valid_courses = {}
        if is_student_import and all_course_names:
            courses = self.env['product.product'].search([
                ('name', 'in', list(all_course_names)),
                ('is_course', '=', True)
            ])
            for c in courses:
                valid_courses[c.name.lower()] = c  # case-insensitive match

        # Pre-build product map from gateway config (already loaded, no extra query)
        config_product_map = {
            line.name: line.product_id
            for line in self.gateway_config_id.gateway_config_line_ids
        }

        valid_vals_list = []
        invalid_vals_list = []

        for row_num, row in enumerate(all_rows, start=2):
            try:
                transaction_id = get_value(row, 'Transaction ID')
                name = get_value(row, 'Name')
                mobile = str(get_value(row, 'Cell Number') or '').strip()
                cnic = get_value(row, 'CNIC No.')
                email = get_value(row, 'Email')
                date = get_value(row, 'Date')
                amount = get_value(row, 'Amount')
                product = get_value(row, 'Product')
                reference = get_value(row, 'Reference')
                course = get_value(row, 'Course')

                if not amount or float(amount) < 0:
                    continue

                if mobile and mobile.lower() != 'none' and len(mobile) != 10:
                    mobile = mobile[-10:]

                mobile = mobile if mobile and mobile.lower() != 'none' else ''
                name = name if name and name.lower() != 'none' else ''
                cnic = cnic if cnic and cnic.lower() != 'none' else ''
                email = email if email and email.lower() != 'none' else ''

                base_vals = {
                    'import_donation_id': self.id,
                    'transaction_id': transaction_id,
                    'donor_student_name': name,
                    'mobile': mobile,
                    'cnic_no': cnic,
                    'email': email,
                    'date': date,
                    'amount': amount,
                }

                if is_student_import:
                    base_vals['is_student'] = True
                    base_vals['product'] = course

                    # Use pre-loaded set — no DB call
                    if transaction_id in existing_tids:
                        invalid_vals_list.append({**base_vals, 'reason': 'A Transaction with same ID already exists in the System.'})
                        continue

                    # Use pre-loaded dict — no DB call
                    course_obj = valid_courses.get((course or '').lower())
                    if not course_obj:
                        invalid_vals_list.append({**base_vals, 'reason': f'The specified course "{course}" does not exist in the System.'})
                        continue

                    if not name:
                        invalid_vals_list.append({**base_vals, 'reason': 'Student Name is not defined.'})
                        continue

                    valid_vals_list.append(base_vals)

                else:
                    base_vals['product'] = product
                    base_vals['reference'] = reference

                    if not product:
                        continue

                    if transaction_id in existing_tids:
                        invalid_vals_list.append({**base_vals, 'reason': 'A Transaction with same ID already exists in the System.'})
                        continue

                    # Use pre-built map — no filtered() call
                    if not config_product_map.get(product):
                        invalid_vals_list.append({**base_vals, 'reason': f'The specified product "{product}" does not exist in the System.'})
                        continue

                    valid_vals_list.append(base_vals)

            except Exception as e:
                invalid_vals_list.append({
                    'import_donation_id': self.id,
                    'reason': f'Unexpected error processing row {row_num}: {str(e)}'
                })

        self.env['invalid.import.donation'].create(invalid_vals_list)
        self.env['valid.import.donation'].create(valid_vals_list)
        self.state = 'validated'

    def action_register_donors(self):
        if not self.valid_import_donation_ids:
            raise ValidationError('No valid records to register donors for.')

        Partner = self.env['res.partner']
        Country = self.env['res.country'].search([('name', '=', 'Pakistan')], limit=1)
        country_id = Country.id if Country else False

        category_refs = {
            'student': self.env.ref('bn_profile_management.student_partner_category').id,
            'donee': self.env.ref('bn_profile_management.donee_partner_category').id,
            'individual': self.env.ref('bn_profile_management.individual_partner_category').id,
            'donor': self.env.ref('bn_profile_management.donor_partner_category').id,
        }

        # Separate mobile pools, track line→mobile mapping
        donor_mobiles = set()
        student_mobiles = set()
        lines_by_key = {}  # (mobile, is_student) → [lines]
        first_contact = {}  # (mobile, is_student) → first line seen (for name/cnic/email)

        for line in self.valid_import_donation_ids:
            if not line.mobile:
                continue
            key = (line.mobile, line.is_student)
            lines_by_key.setdefault(key, []).append(line)
            if key not in first_contact:
                first_contact[key] = line
            (student_mobiles if line.is_student else donor_mobiles).add(line.mobile)

        # Bulk search — use category ID, not name (avoids JOIN)
        existing_donors = Partner.search([
            ('mobile', 'in', list(donor_mobiles)),
            ('category_id', 'in', [category_refs['donor']]),
        ])
        existing_students = Partner.search([
            ('mobile', 'in', list(student_mobiles)),
            ('category_id', 'in', [category_refs['donee']]),
        ])

        donor_by_mobile = {p.mobile: p for p in existing_donors}
        student_by_mobile = {p.mobile: p for p in existing_students}

        partners_to_create = []
        create_keys = []  # parallel list to track which key each vals belongs to

        for key, line in first_contact.items():
            mobile, is_student = key

            if is_student:
                if mobile in student_by_mobile:
                    continue
                cats = [category_refs['donee'], category_refs['individual'], category_refs['student']]
            else:
                if mobile in donor_by_mobile:
                    continue
                cats = [category_refs['donor'], category_refs['individual']]

            partners_to_create.append({
                'name': line.donor_student_name or f'Undefined {mobile}',
                'country_code_id': country_id,
                'mobile': mobile,
                'cnic_no': line.cnic_no,
                'email': line.email,
                'category_id': [(6, 0, cats)],
            })
            create_keys.append(key)

        # Single bulk create + single action_register on full recordset
        created_count = 0
        if partners_to_create:
            new_partners = Partner.create(partners_to_create)  # 1 DB call
            new_partners.action_register()                      # 1 ORM call
            created_count = len(new_partners)

            # Map newly created partners back to their keys
            for key, partner in zip(create_keys, new_partners):
                mobile, is_student = key
                if is_student:
                    student_by_mobile[mobile] = partner
                else:
                    donor_by_mobile[mobile] = partner

        # Bulk write donor_student_id — collect all (id, partner_id) pairs
        # then write in one pass per partner group
        lines_to_update = []
        for key, lines in lines_by_key.items():
            mobile, is_student = key
            partner = student_by_mobile.get(mobile) if is_student else donor_by_mobile.get(mobile)
            if partner:
                for line in lines:
                    lines_to_update.append((line, partner.id))

        # Write in bulk using a single SQL update per partner is ideal,
        # but Odoo ORM doesn't expose that directly; batch by partner_id at least
        for line, pid in lines_to_update:
            line.donor_student_id = pid

        existing_count = len(first_contact) - created_count
        self.state = 'done'  # was unreachable before — fixed

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Donor Registration',
                'message': f'New partners created: {created_count} | Already existed: {existing_count}',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_upload_excel_file(self):
        if not self.valid_import_donation_ids:
            raise ValidationError('There are no Valid Lines in Excel File.')

        journal = self.env['account.journal'].search([('name', 'ilike', 'Bank')], limit=1)
        if not journal:
            raise ValidationError("Bank journal not found.")

        default_partner = self.env['res.partner'].search(
            [('primary_registration_id', '=', '2025-9999998-9')], limit=1
        )

        # ── Pre-load all partners by mobile in one query ──────────────────────
        all_mobiles = [l.mobile for l in self.valid_import_donation_ids if l.mobile]
        partners_by_mobile = {
            p.mobile: p
            for p in self.env['res.partner'].search([('mobile', 'in', all_mobiles)])
        }

        # ── Pre-build config product map (no repeated filtered() calls) ───────
        config_map = {
            line.name: line.product_id
            for line in self.gateway_config_id.gateway_config_line_ids
        }

        # ── Pre-load all courses referenced in student lines ──────────────────
        student_product_names = list({
            l.product for l in self.valid_import_donation_ids if l.is_student and l.product
        })
        courses_by_name = {}
        if student_product_names:
            for c in self.env['product.product'].search([
                ('name', 'in', student_product_names),
                ('is_course', '=', True)
            ]):
                courses_by_name[c.name] = c

        Donation = self.env['donation']
        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']

        credit_groups = {}
        total_amount = 0.0
        donation_vals_list = []
        stock_move_map = {}
        picking = False

        for line in self.valid_import_donation_ids:
            # O(1) dict lookup instead of Partner.search() per row
            partner = partners_by_mobile.get(line.mobile) or default_partner

            # O(1) dict lookup instead of filtered() per row
            product = config_map.get(line.product)
            if not product:
                raise ValidationError(f"Missing configuration for: {line.product}")

            product_id = product.id
            account_id = product.property_account_income_id.id

            if line.is_student:
                # O(1) dict lookup instead of search() per row
                course = courses_by_name.get(line.product)
                donation_vals_list.append({
                    'transaction_id': line.transaction_id,
                    'donor_id': partner.id,
                    'journal_id': journal.id,
                    'product_id': course.id if course else product_id,
                    'date': line.date,
                    'amount': line.amount,
                    'reference': line.reference,
                    'gateway_config_id': self.gateway_config_id.id,
                    'is_fee': True,
                })
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

            if product.detailed_type == 'product':
                stock_move_map.setdefault(product.id, {'product': product, 'qty': 0.0})
                stock_move_map[product.id]['qty'] += 1.0

                if not picking:
                    picking = StockPicking.create({
                        'picking_type_id': self.picking_type_id.id,
                        'location_id': self.source_location_id.id,
                        'location_dest_id': self.destination_location_id.id,
                        'origin': self.name,
                    })

            credit_groups[account_id] = credit_groups.get(account_id, 0.0) + line.amount
            total_amount += line.amount

        donations = Donation.create(donation_vals_list)
        donations.action_confirm()

        if picking:
            StockMove.create([{
                'name': data['product'].name,
                'product_id': data['product'].id,
                'product_uom_qty': data['qty'],
                'quantity': data['qty'],
                'product_uom': data['product'].uom_id.id,
                'picking_id': picking.id,
                'location_id': self.source_location_id.id,
                'location_dest_id': self.destination_location_id.id,
            } for data in stock_move_map.values()])

            picking.action_confirm()
            picking.action_assign()
            picking.button_validate()

        journal_entry = self.env['account.move'].sudo().create({
            'move_type': 'entry',
            'ref': self.name,
            'date': fields.Date.today(),
            'journal_id': journal.id,
            'line_ids': [(0, 0, {
                'account_id': self.gateway_config_id.account_id.id,
                'name': f'Total Donations Received from {self.name}',
                'debit': total_amount,
            })] + [(0, 0, {
                'account_id': acc_id,
                'name': 'Various Donations',
                'credit': amt,
            }) for acc_id, amt in credit_groups.items()],
        })

        self.journal_entry_id = journal_entry.id
        self.state = 'create_donor'

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