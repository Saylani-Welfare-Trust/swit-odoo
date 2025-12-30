from odoo import models, fields
from odoo.exceptions import ValidationError

import base64
from io import BytesIO
import openpyxl
import xlrd


state_selection = [
    ('draft', 'Draft'),
    ('validated',  'Validated'),
    ('upload', 'Uploaded'),
]


class ImportDonation(models.Model):
    _name = 'import.donation'
    _description = "Import Donation"


    name = fields.Char('File Name')

    gateway_config_id = fields.Many2one('gateway.config', string="Gateway Config")
    journal_entry_id = fields.Many2one('account.move', string="Journal Entry")
    picking_id = fields.Many2one('stock.picking', string="Picking")
    # picking_type_id = fields.Many2one('stock.picking.type', string="Picking Type", default=lambda self: self.env.ref('bn_import_donation.online_donation_stock_picking_type', raise_if_not_found=False).id)
    # source_location_id = fields.Many2one(related='picking_type_id.default_location_src_id', string="Source Location", store=True)
    # destination_location_id = fields.Many2one(related='picking_type_id.default_location_dest_id', string="Destination Location", store=True)

    state = fields.Selection(selection=state_selection, string="State", default='draft')

    file_name = fields.Char('File Name')
    import_file = fields.Binary('Import File')

    invalid_import_donation_ids = fields.One2many('invalid.import.donation', 'import_donation_id', string="Invalid Import Donations")
    valid_import_donation_ids = fields.One2many('valid.import.donation', 'import_donation_id', string="Valid Import Donations")


    def action_draft(self):
        for line in self.invalid_import_donation_ids:
            line.unlink()

        for line in self.valid_import_donation_ids:
            line.unlink()

        self.state = 'draft'

    def action_validate_excel_file(self):
        if not self.import_file:
            raise ValidationError('No file uploaded.')

        file_data = base64.b64decode(self.import_file)
        if not file_data:
            raise ValidationError('The uploaded file is empty.')

        file_stream = BytesIO(file_data)

        # Detect file format
        try:
            if file_data[:4] == b'PK\x03\x04':  # .xlsx
                workbook = openpyxl.load_workbook(file_stream)
                sheet = workbook.active
                rows = sheet.iter_rows(min_row=2, values_only=True)
            elif file_data[:4] == b'\xD0\xCF\x11\xE0':  # .xls
                workbook = xlrd.open_workbook(file_contents=file_data)
                sheet = workbook.sheet_by_index(0)
                rows = (sheet.row_values(i) for i in range(1, sheet.nrows))
            else:
                raise ValidationError('Unsupported file format.')
        except Exception:
            raise ValidationError('The uploaded file is not a valid Excel file.')

        # Cache frequently used models
        Partner = self.env['res.partner']
        Country = self.env['res.country'].search([('name', '=', 'Pakistan')])
        ValidDonation = self.env['valid.import.donation']
        InvalidDonation = self.env['invalid.import.donation']

        # Header mapping
        header_list = [(h.header_type_id.name, h.position) for h in self.gateway_config_id.gateway_config_header_ids]
        header_map = {name: pos for name, pos in header_list}

        def get_value(row, name):
            idx = header_map.get(name)
            return row[idx] if idx is not None and idx < len(row) else None

        # Preload category IDs to avoid ref() calls repeatedly
        category_refs = {
            'student': self.env.ref('bn_profile_management.student_partner_category').id,
            'donee': self.env.ref('bn_profile_management.donee_partner_category').id,
            'individual': self.env.ref('bn_profile_management.individual_partner_category').id,
            'donor': self.env.ref('bn_profile_management.donor_partner_category').id,
        }

        for row in rows:
            try:
                # Shared fields
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

                # Normalize mobile number
                if mobile and len(mobile) != 10:
                    mobile = mobile[-10:]

                gateway_name = self.gateway_config_id.name or ''
                is_student_import = gateway_name in ['SMIT', 'PIAIC']

                # ===== Student (Donee) Imports =====
                if is_student_import:
                    if self.env['donation'].search_count([('transaction_id', '=', transaction_id), ('is_fee', '=', True)]):
                        InvalidDonation.create({
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

                    # Validate course
                    course_id = self.env['product.product'].search([
                        ('name', 'ilike', course),
                        ('is_course', '=', True)
                    ], limit=1)

                    if not course_id:
                        InvalidDonation.create({
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

                    # Create or find partner
                    partner = Partner.search([('mobile', '=', mobile), ('category_id.name', 'in', ['Donee'])], limit=1)
                    if not partner and mobile:
                        partner = Partner.create({
                            'name': name or f'Undefined {mobile}',
                            'country_code_id': Country.id,
                            'mobile': mobile,
                            'cnic_no': cnic,
                            'email': email,
                            'category_id': [(6, 0, [
                                category_refs['donee'],
                                category_refs['individual'],
                                category_refs['student']
                            ])]
                        })
                        partner.action_register()

                    if not name:
                        InvalidDonation.create({
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

                    ValidDonation.create({
                        'import_donation_id': self.id,
                        'transaction_id': transaction_id,
                        'donor_student_name': name,
                        'mobile': mobile,
                        'cnic_no': cnic,
                        'email': email,
                        'product': course,  # ✅ course explicitly used here
                        'date': date,
                        'is_student': True,
                        'amount': amount,
                    })

                # ===== Donor Imports =====
                else:
                    if not product:
                        continue

                    if self.env['donation'].search_count([('transaction_id', '=', transaction_id)]):
                        InvalidDonation.create({
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

                    config_line = self.gateway_config_id.gateway_config_line_ids.filtered(lambda x: x.name == product)
                    product_id = config_line.mapped('product_id')

                    if not product_id:
                        InvalidDonation.create({
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

                    donor = Partner.search([('mobile', '=', mobile), ('category_id.name', 'in', ['Donor'])], limit=1)
                    if not donor and mobile:
                        donor = Partner.create({
                            'name': name or f'Undefined {mobile}',
                            'country_code_id': Country.id,
                            'mobile': mobile,
                            'cnic_no': cnic,
                            'email': email,
                            'category_id': [(6, 0, [
                                category_refs['donor'],
                                category_refs['individual']
                            ])]
                        })
                        donor.action_register()

                    ValidDonation.create({
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
                    'reason': f'Unexpected error processing row: {str(e)}'
                })

        self.state = 'validated'

    def action_upload_excel_file(self):
        if not self.valid_import_donation_ids:
            raise ValidationError('There are no Valid Lines in Excel File.')

        journal = self.env['account.journal'].search([('name', 'ilike', 'Bank')], limit=1)
        if not journal:
            raise ValidationError("Bank journal not found.")

        default_partner = self.env['res.partner'].search([('primary_registration_id', '=', '2025-9999998-9')], limit=1)
        credit_groups = {}
        total_amount = 0.0
        
        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']

        picking = False
        stock_move_map = {}

        for line in self.valid_import_donation_ids:
            # Resolve partner (prefer mobile match)
            partner = self.env['res.partner'].search([('mobile', '=', line.mobile)], limit=1) or default_partner

            # Determine configuration line
            config_line = self.gateway_config_id.gateway_config_line_ids.filtered(lambda c: c.name == line.product)

            if not config_line:
                raise ValidationError(f"Missing configuration for: {line.product}")

            product = config_line.product_id if config_line.product_id else False
            product_id = product.id if product else False
            account_id = config_line.product_id.property_account_income_id.id

            if line.is_student:
                # Handle Course (Fee Box)
                course_id = self.env['product.product'].search([
                    ('name', '=', line.product),
                    ('is_course', '=', True)
                ], limit=1)

                fee_box = self.env['donation'].create({
                    'transaction_id': line.transaction_id,
                    'donor_id': partner.id,
                    'journal_id': journal.id,
                    'product_id': course_id.id,
                    'date': line.date,
                    'amount': line.amount,
                    'reference': line.reference,
                    'gateway_config_id': self.gateway_config_id.id,
                    'is_fee': True
                })
                fee_box.action_confirm()
            else:
                # Handle Donation
                donation = self.env['donation'].create({
                    'transaction_id': line.transaction_id,
                    'donor_id': partner.id,
                    'journal_id': journal.id,
                    'product_id': product_id,
                    'date': line.date,
                    'amount': line.amount,
                    'reference': line.reference,
                    'gateway_config_id': self.gateway_config_id.id,
                })
                donation.action_confirm()

            # ----------------------------
            # STOCK LOGIC (ONLY PRODUCT)
            # ----------------------------
            if product.detailed_type == 'product':
                stock_move_map.setdefault(product, {
                    'product': product,
                    'qty': 0.0
                })
                stock_move_map[product]['qty'] += 1.0  # qty per line

                if not picking:
                    picking = StockPicking.create({
                        'picking_type_id': self.picking_type_id.id,
                        'location_id': self.source_location_id.id,
                        'location_dest_id': self.destination_location_id.id,
                        'origin': self.name,
                    })

            # Consolidate amounts by (account, analytic)
            key = account_id
            credit_groups[key] = credit_groups.get(key, 0.0) + line.amount
            total_amount += line.amount

        # ----------------------------
        # CREATE STOCK MOVES
        # ----------------------------
        if picking:
            for data in stock_move_map.values():
                StockMove.create({
                    'name': data['product'].name,
                    'product_id': data['product'].id,
                    'product_uom_qty': data['qty'],
                    'quantity': data['qty'],
                    'product_uom': data['product'].uom_id.id,
                    'picking_id': picking.id,
                    'location_id': self.source_location_id.id,
                    'location_dest_id': self.destination_location_id.id,
                })

            picking.action_confirm()
            picking.action_assign()
            picking.button_validate()

        # Build journal entry lines
        debit_line = (0, 0, {
            'account_id': self.gateway_config_id.account_id.id,
            'name': f'Total Donations Received from {self.name}',
            'debit': total_amount,
        })

        credit_lines = [
            (0, 0, {
                'account_id': acc_id,
                'name': 'Various Donations',
                'credit': amt,
            })
            for acc_id, amt in credit_groups.items()
        ]

        # Create and post journal entry
        journal_entry = self.env['account.move'].sudo().create({
            'move_type': 'entry',
            'ref': self.name,
            'date': fields.Date.today(),
            'journal_id': journal.id,
            'line_ids': [debit_line] + credit_lines,
        })

        # journal_entry.action_post()
        self.journal_entry_id = journal_entry.id
        self.state = 'upload'

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