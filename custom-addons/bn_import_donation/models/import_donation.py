from odoo import models, fields
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


    name = fields.Char('File Name', tracking=True)

    gateway_config_id = fields.Many2one('gateway.config', tracking=True)

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
        if not self.valid_import_donation_ids:
            raise ValidationError("No valid records.")

        Donation = self.env['donation']

        donation_vals = []

        for line in self.valid_import_donation_ids:

            config_line = self.gateway_config_id.gateway_config_line_ids.filtered(
                lambda c: c.name == line.product
            )

            product = config_line.product_id if config_line else False

            donation_vals.append({
                'import_donation_id': self.id,
                'transaction_id': line.transaction_id,
                'donor_id': False,  # NOT LINKED HERE
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
        Partner = self.env['res.partner']
        Donation = self.env['donation']

        donation_map = {
            d.transaction_id: d
            for d in Donation.search([
                ('transaction_id', 'in', self.valid_import_donation_ids.mapped('transaction_id'))
            ])
        }

        partner_cache = {}

        cats = self._get_category_refs()

        for line in self.valid_import_donation_ids:

            key = line.mobile

            if key in partner_cache:
                partner = partner_cache[key]
            else:
                partner = Partner.search([('mobile', '=', line.mobile)], limit=1)

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
        Donation = self.env['donation']
        StockPicking = self.env['stock.picking']
        StockMove = self.env['stock.move']

        journal = self.env['account.journal'].search(
            [('name', 'ilike', 'Bank')], limit=1
        )

        if not journal:
            raise ValidationError("Bank journal not found.")

        donations = Donation.search([
            ('transaction_id', 'in', self.valid_import_donation_ids.mapped('transaction_id'))
        ])

        credit_groups = {}
        total = 0.0

        stock_map = {}
        picking = False

        for d in donations:

            total += d.amount

            acc = d.product_id.property_account_income_id.id if d.product_id else False
            if acc:
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
            picking.button_validate()

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