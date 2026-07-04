from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
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
    date = fields.Date(related='master_id.date', string='Date', store=True)
    
    account_id = fields.Many2one(related='master_id.account_id', string='Account', store=True)
    journal_id = fields.Many2one(related='master_id.journal_id', string='Journal', store=True)
    posted_account_id = fields.Many2one(related='master_id.posted_account_id', string='Posted Account', store=True)
    opening_balance = fields.Monetary(related='master_id.opening_balance', string='Opening Balance', store=True)
    currency_id = fields.Many2one(related='master_id.currency_id', string='Currency', store=True)
    company_id = fields.Many2one(related='master_id.company_id', string='Company', store=True)
    bank_statement_config_id = fields.Many2one(related='master_id.bank_statement_config_id', string='Bank Statement Config', store=True)

    file = fields.Binary(string='File', required=True, attachment=True)
    file_name = fields.Char(string='File Name', required=True)
    file_type = fields.Selection([
        ('csv', 'CSV'),
        ('xls', 'Excel (.xls)'),
        ('xlsx', 'Excel (.xlsx)'),
    ], string='File Type', compute='_compute_file_type', store=False)

    delimiter = fields.Selection([
        (',', 'Comma (,)'),
        (';', 'Semicolon (;)'),
        ('\t', 'Tab'),
    ], string='CSV Delimiter', default=',')


    @api.depends('file_name')
    def _compute_file_type(self):
        for rec in self:
            if rec.file_name:
                ext = rec.file_name.lower().split('.')[-1]
                if ext in ('csv',):
                    rec.file_type = 'csv'
                elif ext in ('xls',):
                    rec.file_type = 'xls'
                elif ext in ('xlsx',):
                    rec.file_type = 'xlsx'
                else:
                    rec.file_type = False
            else:
                rec.file_type = False

    def action_import(self):
        self.ensure_one()
        if not self.file:
            raise UserError(_('Please select a file to upload.'))

        ext = self.file_name.lower().split('.')[-1]
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
                'debit': row.get('Debit', 0.0),
                'credit': row.get('Credit', 0.0),
                'account_id': self.account_id.id,
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
        master.state = 'uploaded'

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
            file_content = base64.b64decode(self.file)

            try:
                content = file_content.decode("utf-8")
            except UnicodeDecodeError:
                content = file_content.decode("latin-1")

            rows = list(csv.reader(io.StringIO(content), delimiter=self.delimiter))

            if len(rows) <= 1:
                return []

            config = self.bank_statement_config_id

            if not config:
                raise UserError(_("Please select a Bank Statement Configuration."))

            header_map = {
                line.header_type_id.name: line.position
                for line in config.header_ids
            }

            def get(row, key):
                index = header_map.get(key)
                if index is None or index >= len(row):
                    return ""
                return row[index]

            for row in rows[1:]:

                date_str = str(get(row, "Date")).strip()

                if not date_str:
                    continue

                date_obj = False

                for fmt in (
                    "%Y-%m-%d",
                    "%d/%m/%Y",
                    "%m/%d/%Y",
                    "%d-%m-%Y",
                ):
                    try:
                        date_obj = datetime.strptime(date_str, fmt).date()
                        break
                    except Exception:
                        pass

                if not date_obj:
                    continue

                try:
                    debit = float(str(get(row, "Debit") or 0).replace(",", ""))
                except Exception:
                    debit = 0.0

                try:
                    credit = float(str(get(row, "Credit") or 0).replace(",", ""))
                except Exception:
                    credit = 0.0

                data.append({
                    "Date": date_obj,
                    "Description": str(get(row, "Description") or "").strip(),
                    "Debit": debit,
                    "Credit": credit,
                    "Reference": str(get(row, "Reference") or "").strip(),
                    "Payment Reference": str(get(row, "Payment Reference") or "").strip(),
                    "Partner": str(get(row, "Partner") or "").strip(),
                    "Invoice Number": str(get(row, "Invoice Number") or "").strip(),
                })

        except Exception as e:
            raise UserError(_("Error parsing CSV: %s") % str(e))

        return data

    def _parse_excel(self):
        if not xlrd:
            raise UserError(_("Please install xlrd."))

        data = []

        try:
            file_content = base64.b64decode(self.file)
            book = xlrd.open_workbook(file_contents=file_content)
            sheet = book.sheet_by_index(0)

            config = self.bank_statement_config_id

            if not config:
                raise UserError(_("Please select a Bank Statement Configuration."))

            header_map = {
                line.header_type_id.name: line.position
                for line in config.header_ids
            }

            def get(row, key):
                index = header_map.get(key)
                if index is None or index >= len(row):
                    return ""
                return row[index].value

            for row_no in range(1, sheet.nrows):
                row = sheet.row(row_no)

                date_val = get(row, "Date")
                if not date_val:
                    continue

                if isinstance(date_val, float):
                    try:
                        date_tuple = xlrd.xldate.xldate_as_tuple(
                            date_val,
                            book.datemode
                        )
                        date_obj = datetime(*date_tuple).date()
                    except Exception:
                        continue
                else:
                    date_obj = False
                    for fmt in (
                        "%Y-%m-%d",
                        "%d/%m/%Y",
                        "%m/%d/%Y",
                        "%d-%m-%Y",
                    ):
                        try:
                            date_obj = datetime.strptime(
                                str(date_val).strip(),
                                fmt,
                            ).date()
                            break
                        except Exception:
                            pass

                    if not date_obj:
                        continue

                try:
                    debit = float(str(get(row, "Debit") or 0).replace(",", ""))
                except Exception:
                    debit = 0.0

                try:
                    credit = float(str(get(row, "Credit") or 0).replace(",", ""))
                except Exception:
                    credit = 0.0

                data.append({
                    "Date": date_obj,
                    "Description": str(get(row, "Description") or "").strip(),
                    "Debit": debit,
                    "Credit": credit,
                    "Reference": str(get(row, "Reference") or "").strip(),
                    "Payment Reference": str(get(row, "Payment Reference") or "").strip(),
                    "Partner": str(get(row, "Partner") or "").strip(),
                    "Invoice Number": str(get(row, "Invoice Number") or "").strip(),
                })

        except Exception as e:
            raise UserError(_("Error parsing Excel: %s") % str(e))

        return data