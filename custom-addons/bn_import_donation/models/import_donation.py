from odoo import fields, models, exceptions
import base64
from io import BytesIO
import openpyxl
import xlrd
from datetime import datetime
import re


state_selection = [
    ('draft', 'Draft'),
    ('validated',  'Validated'),
    ('upload', 'Uploaded'),
]


class ImportDonation(models.Model):
    _name = 'import.donation'
    _description = "Import Donation"

    name = fields.Char('File Name', required=True)
    
    # Binary field to upload the donation file
    file_name = fields.Char('File Name')
    file = fields.Binary('Donation File', required=True)

    gateway_id = fields.Many2one('config.bank', string="Bank ID")
    journal_entry_id = fields.Many2one('account.move', string="Journal Entry")

    state = fields.Selection(selection=state_selection, string='State', default='draft')

    invalid_donation_ids = fields.One2many('invalid.donation', 'import_donation_id', string="Invalid Donation IDs")
    valid_donation_ids = fields.One2many('valid.donation', 'import_donation_id', string="Valid Donation IDs")


    def action_reset(self):
        for line in self.invalid_donation_ids:
            line.unlink()

        for line in self.valid_donation_ids:
            line.unlink()

        self.state = 'draft'

    def action_validate_excel_file(self):
        if not self.file:
            raise exceptions.ValidationError('No file uploaded.')

        # Decode the base64 file to binary
        file_data = base64.b64decode(self.file)
        file_stream = BytesIO(file_data)

        # Check file extension
        if not file_data:
            raise exceptions.ValidationError('The uploaded file is not an Excel file.')

        try:
            # Check file type based on extension
            if file_data[:4] == b'PK\x03\x04':  # .xlsx file signature
                workbook = openpyxl.load_workbook(file_stream)
            elif file_data[:4] == b'\xD0\xCF\x11\xE0':  # .xls file signature
                workbook = xlrd.open_workbook(file_contents=file_data)
            else:
                raise exceptions.ValidationError('Unsupported file format.')

            sheet = workbook.active
            header_list = [(header.header_type_id.name, header.position) for header in self.gateway_id.config_bank_header_ids]

            transaction_id_index = next((i for i, (name, _) in enumerate(header_list) if name == "Transaction ID"), -1)
            name_index = next((i for i, (name, _) in enumerate(header_list) if name == "Name"), -1)
            mobile_index = next((i for i, (name, _) in enumerate(header_list) if name == "Cell Number"), -1)
            email_index = next((i for i, (name, _) in enumerate(header_list) if name == "Email"), -1)
            cnic_index = next((i for i, (name, _) in enumerate(header_list) if name == "CNIC No."), -1)
            payment_method_index = next((i for i, (name, _) in enumerate(header_list) if name == "Payment Method"), -1)
            course_index = next((i for i, (name, _) in enumerate(header_list) if name == "Course"), -1)
            date_index = next((i for i, (name, _) in enumerate(header_list) if name == "Date"), -1)
            amount_index = next((i for i, (name, _) in enumerate(header_list) if name == "Amount"), -1)
            product_index = next((i for i, (name, _) in enumerate(header_list) if name == "Product"), -1)
            reference_index = next((i for i, (name, _) in enumerate(header_list) if name == "Reference"), -1)

            for row in sheet.iter_rows(min_row=2, values_only=True):  # Skip header row
                if self.gateway_id.name in ['SMIT', 'PIAIC']:
                    transaction_id = None
                    donee_name = None
                    mobile = None
                    cnic_no = None
                    email = None
                    payment_method = None
                    course = None
                    date = None
                    amount = None

                    if transaction_id_index != -1:
                        transaction_id = row[header_list[transaction_id_index][1]]
                    if name_index != -1:
                        donee_name = row[header_list[name_index][1]]
                    if mobile_index != -1:
                        mobile = str(row[header_list[mobile_index][1]])
                        if mobile:
                            if len(mobile) != 10:
                                diff = len(mobile) - 10
                                mobile = mobile[diff:]
                    if email_index != -1:
                        email = row[header_list[email_index][1]]
                    if cnic_index != -1:
                        cnic_no = row[header_list[cnic_index][1]]
                    if payment_method_index != -1:
                        payment_method = row[header_list[payment_method_index][1]]
                    if course_index and course_index != -1:
                        course = row[header_list[course_index][1]]
                    if date_index != -1:
                        date = row[header_list[date_index][1]]
                    if amount_index != -1:
                        amount = row[header_list[amount_index][1]]

                    if float(amount) < 0:
                        continue

                    fee_box_id = self.env['fee.box'].search([('transaction_id', '=', transaction_id)])
                    
                    if fee_box_id:
                        self.env['invalid.donation'].create({
                            'import_donation_id': self.id,
                            'transaction_id': transaction_id,
                            'donor_donee_name': donee_name,
                            'mobile': mobile,
                            'cnic_no': cnic_no,
                            'email': email,
                            'payment_method': payment_method,
                            'course': course,
                            'date': date,
                            'amount': amount,
                            'reason': 'A Transaction with same ID already exist in the System.'
                        })
                        continue

                    partner_id = self.env['res.partner'].search([('mobile', '=', mobile)], limit=1)
                    if not partner_id and mobile:
                        partner_obj = self.env['res.partner'].create({
                            'name': donee_name or f'Undefine {mobile}',
                            'mobile': mobile,
                            'cnic_no': cnic_no,
                            'email': email,
                            'donee_type': 'individual',
                            'registration_category': 'donor',
                            'is_donee': False,
                            # 'is_student': True,
                        })

                        partner_obj.action_validate()
                        partner_obj.action_register()

                    elif not donee_name:
                        self.env['invalid.donation'].create({
                            'import_donation_id': self.id,
                            'transaction_id': transaction_id,
                            'donor_donee_name': donee_name,
                            'mobile': mobile,
                            'cnic_no': cnic_no,
                            'email': email,
                            'payment_method': payment_method,
                            'course': course,
                            'date': date,
                            'amount': amount,
                            'create_record': False,
                            'reason': f'Donee Name is not define.'
                        })
                        continue
                    
                    course_id = self.env['product.product'].search([('name', 'ilike', course), ('is_course', '=', True)])
                    if not course_id:
                        self.env['invalid.donation'].create({
                            'import_donation_id': self.id,
                            'transaction_id': transaction_id,
                            'donor_donee_name': donee_name,
                            'mobile': mobile,
                            'cnic_no': cnic_no,
                            'email': email,
                            'payment_method': payment_method,
                            'course': course,
                            'date': date,
                            'amount': amount,
                            'create_record': False,
                            'reason': f'The specified ( {course} ) Course does not exist in the System.'
                        })
                        continue

                    self.env['valid.donation'].create({
                        'import_donation_id': self.id,
                        'transaction_id': transaction_id,
                        'donor_donee_name': donee_name,
                        'mobile': mobile,
                        'cnic_no': cnic_no,
                        'email': email,
                        'payment_method': payment_method,
                        'course': course,
                        'date': date,
                        'amount': amount,
                    })

                else:
                    transaction_id = None
                    donor_name = None
                    mobile = None
                    cnic_no = None
                    email = None
                    payment_method = None
                    product = None
                    date = None
                    amount = None
                    reference = None

                    # raise exceptions.ValidationError(str([row, date_index, header_list[date_index], row[header_list[date_index][1]]]))
                    if transaction_id_index != -1:
                        transaction_id = row[header_list[transaction_id_index][1]]
                    if name_index != -1:
                        donor_name = row[header_list[name_index][1]]
                    if mobile_index != -1:
                        mobile = str(row[header_list[mobile_index][1]])
                        if mobile:
                            if len(mobile) != 10:
                                if 'EasyPaisa' in self.gateway_id.name:
                                    mobile = mobile.split(':')[1]
                                    mobile = mobile.split('/')[0]
                                    diff = len(mobile) - 10
                                    mobile = mobile[diff:]
                                else:
                                    diff = len(mobile) - 10
                                    mobile = mobile[diff:]
                    if email_index != -1:
                        email = row[header_list[email_index][1]]
                    if cnic_index != -1:
                        cnic_no = row[header_list[cnic_index][1]]
                    if payment_method_index != -1:
                        payment_method = row[header_list[payment_method_index][1]]
                    if product_index != -1:
                        product = row[header_list[product_index][1]]
                    if date_index != -1:
                        date = row[header_list[date_index][1]]
                    if amount_index != -1:
                        amount = row[header_list[amount_index][1]]
                    if reference_index != -1:
                        reference = row[header_list[reference_index][1]]

                    if float(amount) < 0:
                        continue

                    if not product:
                        continue

                    fund_utilization = self.gateway_id.config_bank_line_ids.filtered(lambda x: x.name == product).mapped('analytic_account_id.name')
                    
                    if not fund_utilization:
                        self.env['invalid.donation'].create({
                            'import_donation_id': self.id,
                            'transaction_id': transaction_id,
                            'donor_donee_name': donor_name,
                            'mobile': mobile,
                            'cnic_no': cnic_no,
                            'email': email,
                            'payment_method': payment_method,
                            'product': product,
                            'fund_utilization': fund_utilization,
                            'date': date,
                            'amount': amount,
                            'reference': reference,
                            'create_record': False,
                            'reason': f'No fund utilization is configured against the Product ( {product} ).'
                        })
                        continue

                    donation_id = self.env['donation'].search([('transaction_id', '=', transaction_id)])
                    
                    if donation_id:
                        self.env['invalid.donation'].create({
                            'import_donation_id': self.id,
                            'transaction_id': transaction_id,
                            'donor_donee_name': donor_name,
                            'mobile': mobile,
                            'cnic_no': cnic_no,
                            'email': email,
                            'payment_method': payment_method,
                            'product': product,
                            'fund_utilization': fund_utilization[0],
                            'date': date,
                            'amount': amount,
                            'reference': reference,
                            'create_record': False,
                            'reason': f'A Transaction with same ID already exist in the System.'
                        })
                        continue

                    partner_id = self.env['res.partner'].search([('mobile', '=', mobile)], limit=1)
                    if not partner_id and mobile:
                        partner_obj = self.env['res.partner'].create({
                            'name': donor_name or f'Undefine {mobile}',
                            'mobile': mobile,
                            'cnic_no': cnic_no,
                            'email': email,
                            'donor_type': 'individual',
                            'registration_category': 'donor',
                            'is_donee': False,
                        })

                        partner_obj.action_validate()
                        partner_obj.action_register()
                
                    product_id = self.gateway_id.config_bank_line_ids.filtered(lambda x: x.name == product).mapped('product_id')
                    if not product_id:
                        self.env['invalid.donation'].create({
                            'import_donation_id': self.id,
                            'transaction_id': transaction_id,
                            'donor_donee_name': donor_name,
                            'mobile': mobile,
                            'cnic_no': cnic_no,
                            'email': email,
                            'payment_method': payment_method,
                            'product': product,
                            'fund_utilization': fund_utilization[0],
                            'date': date,
                            'amount': amount,
                            'reference': reference,
                            'create_record': False,
                            'reason': f'The specified ( {product} ) Product does not exist in the System.'
                        })
                        continue
                    

                    self.env['valid.donation'].create({
                        'import_donation_id': self.id,
                        'transaction_id': transaction_id,
                        'donor_donee_name': donor_name,
                        'mobile': mobile,
                        'cnic_no': cnic_no,
                        'email': email,
                        'payment_method': payment_method,
                        'product': product,
                        'fund_utilization': fund_utilization[0],
                        'date': date,
                        'amount': amount,
                        'reference': reference,
                    })

            self.state = 'validated'

            return True

        except (openpyxl.utils.exceptions.InvalidFileException, xlrd.biffh.XLRDError) as e:
            raise exceptions.ValidationError('The uploaded file is not a valid Excel file.')
        except Exception as e:
            raise exceptions.ValidationError(f'Error while processing the file: {str(e)}')

    def action_upload_excel_file(self):
        if not self.valid_donation_ids:
            raise exceptions.ValidationError('There are no Valid Lines in Excel File.')
        
        total_amount = 0.0
        # Dictionary to store consolidated credit lines: {(account_id, analytic_key): amount}
        credit_groups = {}
        journal_id = None
        
        for line in self.valid_donation_ids:
            transaction_id = line.transaction_id
            mobile_no = line.mobile
            course = line.course
            product = line.product
            date = line.date
            amount = line.amount
            reference = line.reference
            journal = 'Bank'

            # Find partner
            partner_id = self.env['res.partner'].search([('barcode', '=', '2025-9999998-9')], limit=1)
            if mobile_no:
                mobile_partner = self.env['res.partner'].search([('mobile', '=', mobile_no)], limit=1)
                if mobile_partner:
                    partner_id = mobile_partner

            journal_id = self.env['account.journal'].search([('name', 'ilike', journal)], limit=1)
            
            analytic_account_id = None
            config_line = None

            if course:
                # Handle Course (Fee Box)
                course_id = self.env['product.product'].search([
                    ('name', '=', course), 
                    ('is_course', '=', True)
                ], limit=1)
                
                fee_box_obj = self.env['fee.box'].create({
                    'transaction_id': transaction_id,
                    'partner_id': partner_id.id,
                    'journal_id': journal_id.id,
                    'course_id': course_id.id,
                    'date': date,
                    'amount': amount,
                    'file_ref': self.name,
                    'gateway_id': self.gateway_id.id,
                })
                fee_box_obj.action_confirm()
                
                # Get config for credit line
                config_line = self.gateway_id.config_bank_line_ids.filtered(
                    lambda x: x.name == course
                )
                analytic_account_id = config_line.analytic_account_id.id if config_line else False
                
            else:
                # Handle Product (Donation)
                config_line = self.gateway_id.config_bank_line_ids.filtered(
                    lambda x: x.name == product
                )
                fund_utilization = config_line.analytic_account_id.id if config_line else False
                credit_account = config_line.account_id.id if config_line else False
                product_id = config_line.product_id.id if config_line else False

                donation_obj = self.env['donation'].create({
                    'transaction_id': transaction_id,
                    'partner_id': partner_id.id,
                    'journal_id': journal_id.id,
                    'product_id': product_id,
                    'analytic_account_id': fund_utilization,
                    'credit_account_id': credit_account,
                    'date': date,
                    'amount': amount,
                    'reference': reference,
                    'file_ref': self.name,
                    'gateway_id': self.gateway_id.id,
                })
                donation_obj.action_confirm()
                analytic_account_id = fund_utilization
            
            # Get account ID for credit line
            account_id = False
            if config_line and config_line.account_id:
                account_id = config_line.account_id.id
                
            if not account_id:
                raise exceptions.ValidationError(
                    f'Missing account configuration for: {course or product}'
                )
            
            # Create key for grouping: (account_id, analytic_account_id)
            analytic_key = analytic_account_id or None
            group_key = (account_id, analytic_key)
            
            # Add amount to consolidated group
            credit_groups.setdefault(group_key, 0.0)
            credit_groups[group_key] += amount
            total_amount += amount

        # Build consolidated credit lines
        credit_lines = []
        for (account_id, analytic_account_id), amount in credit_groups.items():
            # Prepare analytic distribution if exists
            analytic_distribution = {}
            if analytic_account_id:
                analytic_distribution = {str(analytic_account_id): 100}
            
            credit_lines.append((0, 0, {
                'account_id': account_id,
                'name': 'Various Donations',
                'credit': amount,
                'analytic_distribution': analytic_distribution,
            }))

        # Create debit line
        debit_line = (0, 0, {
            'account_id': self.gateway_id.account_id.id,
            'name': f'Total Donations Received from {self.name}',
            'debit': total_amount,
            'analytic_distribution': {},
        })
        
        # Create journal entry
        journal_entry = self.env['account.move'].create({
            'move_type': 'entry',
            'ref': self.name,
            'date': fields.Date.today(),
            'journal_id': journal_id.id,
            'line_ids': [debit_line] + credit_lines
        })
        
        self.journal_entry_id = journal_entry.id
        journal_entry.action_post()
        self.state = 'upload'
        return True
    
    def action_show_journal_entry(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.journal_entry_id.id,
            'target': 'new'
        }
        

class InValidDonation(models.Model):
    _name = 'invalid.donation'

    import_donation_id = fields.Many2one('import.donation', string="Import Donation ID")
    
    transaction_id = fields.Char('Transacetion ID')
    donor_donee_name = fields.Char('Donor/Donee Name')
    mobile = fields.Char('Contact/Mobile No.')
    cnic_no = fields.Char('CNIC No.')
    email = fields.Char('Email Address')
    payment_method = fields.Char('Payment Method')
    course = fields.Char('Course Name')
    product = fields.Char('Product Name')
    fund_utilization = fields.Char('Fund Utilization', help="Fund Utilization Options and there syntax are:\n1. Fitra\n2. Zakat\n3. Fidyah")
    date = fields.Char('Date')
    amount = fields.Float('Amount')
    reference = fields.Char('Reference')

    reason = fields.Char('Reason')
    create_record = fields.Boolean('Create Contact', default=False)
    hide_button = fields.Boolean('Hide Button', default=False)


    def action_approve(self):
        journal_id = self.env['account.journal'].search([('name', 'ilike', 'Bank')], limit=1)

        if self.course:
            if not self.birth_day:
                raise exceptions.ValidationError('Please enter Student Birth Day as it is necessary for creating Registration ID.')

            fee_box_id = self.env['fee.box'].search([('transaction_id', '=', self.transaction_id)])
            
            if fee_box_id:
                # raise exceptions.ValidationError(str(f'A Transaction with same ID already exist in the system. Line {count}'))

                self.reason = 'A Transaction with same ID already exist in the System.'
                self.hide_button = True
                return True
            
            course_id = self.env['product.product'].search([('name', '=', course), ('is_course', '=', True)])
            if not course_id:
                raise exceptions.ValidationError(str(f'The specified ( {course} ) Course does not exist in the System'))
            
            partner_obj = None

            if self.create_record:
                partner_obj = self.env['res.partner'].create({
                    'name': self.donor_donee_name if self.donor_donee_name else 'Muslim 1',
                    'mobile': self.mobile,
                    'cnic_no': self.cnic_no,
                    'email': self.email,
                    'donee_type': 'individual',
                    'course_ids': [(4, course_id.id)],
                    'is_donee': True,
                    'is_student': True,
                    'student': True,
                })

                partner_obj.action_register()

            transaction_id = self.transaction_id
            donee_name = self.donor_donee_name
            mobile_no = self.mobile
            course = self.course
            payment_method = self.payment_method
            date = self.date
            amount = self.amount

            partner_id = self.env['res.partner'].search([('mobile', '=', mobile_no)], limit=1)

            if not partner_id:
                self.reason = f'A Donor against specified mobile no. ( {mobile_no} ) does not exist in the System.'
                self.create_record = True
                return True
            elif not donee_name:
                raise exceptions.ValidationError(str(f'Please specify the Donee Name.'))
            
            fee_box_obj = self.env['fee.box'].create({
                'transaction_id': transaction_id,
                'partner_id': partner_id.id,
                'journal_id': journal_id.id,
                'course_id': course_id.id,
                'date': date,
                'amount': amount,
                'file_ref': self.import_donation_id.name,
                'gateway_id': self.import_donation_id.gateway_id.id,
            })

            fee_box_obj.action_confirm()
            
        else:
            donation_id = self.env['donation'].search([('transaction_id', '=', self.transaction_id)])

            if donation_id:
                # raise exceptions.ValidationError(str(f'A Transaction with same ID already exist in the system. Line {count}'))

                self.reason = 'A Transaction with same ID already exist in the System.'
                self.hide_button = True
                return True

            partner_obj = None

            if self.create_record:
                partner_obj = self.env['res.partner'].create({
                    'name': self.donor_donee_name if self.donor_donee_name else 'Muslim 1',
                    'mobile': self.mobile,
                    'cnic_no': self.cnic_no,
                    'email': self.email,
                    'donor_type': 'individual',
                    'is_donee': False
                })

                partner_obj.action_register()

            transaction_id = self.transaction_id
            mobile_no = self.mobile
            product = self.product
            payment_method = self.payment_method
            fund_utilization = self.fund_utilization
            date = self.date
            amount = self.amount
            reference = self.reference
        
            partner_id = self.env['res.partner'].search([('mobile', '=', mobile_no)], limit=1)

            if not partner_id:
                self.reason = f'A Donor against specified mobile no. ( {mobile_no} ) does not exist in the System.'
                self.create_record = True
                return True
        
            fund_utilization = self.import_donation_id.gateway_id.config_bank_line_ids.filtered(lambda x: x.name == product).mapped('analytic_account_id')[0]
            if not fund_utilization:
                raise exceptions.ValidationError(str(f'The specified ( {fund_utilization.name} ) Fund Utilization does not match our SOP.'))
            
            product_id = self.import_donation_id.gateway_id.config_bank_line_ids.filtered(lambda x: x.name == product).mapped('product_id')[0]
            if not product_id:
                raise exceptions.ValidationError(str(f'The specified ( {product} ) Product does not exist in the System'))

            credit_account = self.import_donation_id.gateway_id.config_bank_line_ids.filtered(lambda x: x.name == product).mapped('account_id.id')[0]
            if not credit_account:
                raise exceptions.ValidationError(str(f'The specified ( {credit_account} ) Credit Account does not exist in the System or is not configure.'))
            

            donation_obj = self.env['donation'].create({
                'transaction_id': transaction_id,
                'partner_id': partner_id.id,
                'journal_id': journal_id.id,
                'product_id': product_id.id,
                'analytic_account_id': fund_utilization.id,
                'credit_account_id': credit_account,
                'date': date,
                'amount': amount,
                'reference': reference,
                'file_ref': self.import_donation_id.name,
                'gateway_id': self.import_donation_id.gateway_id.id,
            })

            donation_obj.action_confirm()

        self.hide_button = True

class ValidDonation(models.Model):
    _name = 'valid.donation'

    import_donation_id = fields.Many2one('import.donation', string="Import Donation ID")
    
    transaction_id = fields.Char('Transacetion ID')
    donor_donee_name = fields.Char('Donor/Donee Name')
    mobile = fields.Char('Contact/Mobile No.')
    cnic_no = fields.Char('CNIC No.')
    email = fields.Char('Email Address')
    payment_method = fields.Char('Payment Method')
    course = fields.Char('Course Name')
    product = fields.Char('Product Name')
    fund_utilization = fields.Char('Fund Utilization')
    date = fields.Char('Date')
    amount = fields.Float('Amount')
    reference = fields.Char('Reference')