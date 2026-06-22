from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import csv
import io
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

try:
    import xlrd
except ImportError:
    xlrd = None


class BankStatementImportWizard(models.TransientModel):
    _name = 'import.bank.statement.wizard'
    _description = 'Bank Statement Import Wizard'

    master_id = fields.Many2one(
        'bank.reconciliation.master',
        string='Reconciliation Master',
        help='If empty, a new master will be created.'
    )

    name = fields.Char(string='Reference', help='Leave empty for auto-sequence')
    date = fields.Date(string='Statement Date', required=True, default=fields.Date.context_today)
    account_id = fields.Many2one(
        'account.account',
        string='Bank Account',
        required=True,
        domain="[('account_type', 'in', ['asset_cash', 'asset_current'])]"
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        required=True,
        domain="[('type', 'in', ['bank', 'cash'])]"
    )
    opening_balance = fields.Monetary(
        string='Opening Balance',
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        readonly=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )

    skip_first_row = fields.Boolean(string='Skip First Row (Header)', default=True)
    create_master = fields.Boolean(string='Create New Reconciliation', default=True)

    def action_import(self):
        self.ensure_one()
        if not self.master_id.file:
            raise UserError(_('Please select a file to upload.'))

        ext = self.master_id.file_name.lower().split('.')[-1]
        if ext == 'csv':
            data = self._parse_csv()
        elif ext in ('xls', 'xlsx'):
            data = self._parse_excel()
        else:
            raise UserError(_('Unsupported file format. Please upload CSV or Excel (.xls/.xlsx).'))

        if not data:
            raise UserError(_('No data found in the file.'))

        master = self._get_or_create_master()

        Transaction = self.env['bank.reconciliation.transaction']
        for row in data:
            vals = {
                'master_id': master.id,
                'date': row.get('Date'),
                'description': row.get('Description', ''),
                'amount': row.get('Amount', 0.0),
                'reference': row.get('Reference', ''),
                'payment_reference': row.get('Payment Reference', ''),
                'invoice_number': row.get('Invoice Number', ''),
            }
            partner_name = row.get('Partner', '')
            if partner_name:
                partner = self.env['res.partner'].search([('name', 'ilike', partner_name)], limit=1)
                if partner:
                    vals['partner_id'] = partner.id
            if not vals['date']:
                raise UserError(_('Date is required for each transaction.'))
            Transaction.create(vals)

        master._compute_transaction_counts()
        master._compute_totals()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bank.reconciliation.master',
            'res_id': master.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _get_or_create_master(self):
        if self.master_id:
            return self.master_id
        vals = {
            'date': self.date,
            'account_id': self.account_id.id,
            'journal_id': self.journal_id.id,
            'company_id': self.company_id.id,
            'opening_balance': self.opening_balance or 0.0,
            'state': 'draft',
        }
        if self.name:
            vals['name'] = self.name
        return self.env['bank.reconciliation.master'].create(vals)

    def _parse_csv(self):
        data = []
        try:
            file_content = base64.b64decode(self.master_id.file)
            try:
                content = file_content.decode('utf-8')
            except UnicodeDecodeError:
                content = file_content.decode('latin-1')
            csv_reader = csv.DictReader(io.StringIO(content), delimiter=self.master_id.delimiter)
            expected_headers = ['Date', 'Description', 'Amount', 'Reference', 'Payment Reference', 'Partner', 'Invoice Number']
            if not all(h in csv_reader.fieldnames for h in expected_headers):
                raise UserError(_(
                    'CSV headers must include: Date, Description, Amount, Reference, Payment Reference, Partner, Invoice Number. '
                    'Found headers: %s' % ', '.join(csv_reader.fieldnames)
                ))
            for row in csv_reader:
                date_str = row.get('Date', '').strip()
                if not date_str:
                    continue
                try:
                    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y'):
                        try:
                            date_obj = datetime.strptime(date_str, fmt).date()
                            break
                        except ValueError:
                            continue
                    else:
                        raise ValueError
                except:
                    raise UserError(_('Invalid date format in row: %s. Please use YYYY-MM-DD, DD/MM/YYYY, or similar.') % date_str)
                amount_str = row.get('Amount', '0').strip().replace(',', '')
                try:
                    amount = float(amount_str)
                except:
                    amount = 0.0
                data.append({
                    'Date': date_obj,
                    'Description': row.get('Description', '').strip(),
                    'Amount': amount,
                    'Reference': row.get('Reference', '').strip(),
                    'Payment Reference': row.get('Payment Reference', '').strip(),
                    'Partner': row.get('Partner', '').strip(),
                    'Invoice Number': row.get('Invoice Number', '').strip(),
                })
        except Exception as e:
            raise UserError(_('Error parsing CSV: %s') % str(e))
        return data

    def _parse_excel(self):
        if not xlrd:
            raise UserError(_('xlrd library is required to read Excel files. Please install it (pip install xlrd).'))
        data = []
        try:
            file_content = base64.b64decode(self.master_id.file)
            book = xlrd.open_workbook(file_contents=file_content)
            sheet = book.sheet_by_index(0)
            header = [str(cell.value).strip() for cell in sheet.row(0)]
            expected_headers = ['Date', 'Description', 'Amount', 'Reference', 'Payment Reference', 'Partner', 'Invoice Number']
            if not all(h in header for h in expected_headers):
                raise UserError(_(
                    'Excel headers must include: Date, Description, Amount, Reference, Payment Reference, Partner, Invoice Number. '
                    'Found: %s' % ', '.join(header)
                ))
            col_map = {h: header.index(h) for h in expected_headers if h in header}
            for row_idx in range(1, sheet.nrows):
                row = sheet.row(row_idx)
                date_val = row[col_map['Date']].value
                if isinstance(date_val, float):
                    try:
                        date_tuple = xlrd.xldate.xldate_as_tuple(date_val, book.datemode)
                        date_obj = datetime(*date_tuple).date()
                    except:
                        date_obj = False
                else:
                    date_str = str(date_val).strip()
                    try:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                    except:
                        date_obj = False
                if not date_obj:
                    continue
                amount_str = str(row[col_map['Amount']].value).strip().replace(',', '')
                try:
                    amount = float(amount_str)
                except:
                    amount = 0.0
                data.append({
                    'Date': date_obj,
                    'Description': str(row[col_map['Description']].value).strip(),
                    'Amount': amount,
                    'Reference': str(row[col_map['Reference']].value).strip(),
                    'Payment Reference': str(row[col_map['Payment Reference']].value).strip(),
                    'Partner': str(row[col_map['Partner']].value).strip(),
                    'Invoice Number': str(row[col_map['Invoice Number']].value).strip(),
                })
        except Exception as e:
            raise UserError(_('Error parsing Excel: %s') % str(e))
        return data