from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import csv
import io
import logging
import re
from datetime import datetime

_logger = logging.getLogger(__name__)

try:
    import xlrd
except ImportError:
    xlrd = None


def _to_amount(value):
    """Amount of a statement cell: 1,000.00, 1 000.00 or empty"""
    try:
        return float(re.sub(r'[,\s]', '', str(value or 0)) or 0)
    except ValueError:
        return 0.0


def _column_label(position):
    """Position 12 -> '12 (column M)', as the spreadsheet shows it"""
    if position is None or position < 0:
        return _('not set')
    letters, number = '', position
    while number >= 0:
        letters = chr(65 + number % 26) + letters
        number = number // 26 - 1
    return _('%s (column %s)') % (position, letters)


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
            ext = (rec.file_name or '').lower().split('.')[-1]
            rec.file_type = ext if ext in ('csv', 'xls', 'xlsx') else False

    def action_import(self):
        self.ensure_one()
        if not self.file:
            raise UserError(_('Please select a file to upload.'))

        ext = (self.file_name or '').lower().split('.')[-1]
        if ext == 'csv':
            data = self._parse_csv()
        elif ext in ('xls', 'xlsx'):
            data = self._parse_excel()
        else:
            raise UserError(_('Unsupported file format. Please upload CSV or Excel (.xls/.xlsx).'))

        if not data:
            raise UserError(_('No data found in the file.'))
        self._check_amount_rows(data)

        master = self._get_or_create_master()
        self._check_duplicate_rows(data, master)

        Transaction = self.env['bank.reconciliation.transaction']
        for row in data:
            vals = {
                'master_id': master.id,
                'date': row.get('Date'),
                'description': row.get('Description', ''),
                'debit': row.get('Debit', 0.0),
                'credit': row.get('Credit', 0.0),
                # No reference must stay empty (not ''), or two same-day lines of
                # the same amount would be rejected as duplicates
                'reference': row.get('Reference') or False,
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
        # Keep the uploaded statement on the reconciliation
        master.write({
            'file': self.file,
            'file_name': self.file_name,
            'state': 'uploaded',
        })

    def _check_amount_rows(self, data):
        """Every statement line needs a Debit or a Credit amount. Name the rows
        that have none and what was read in their cells: it is nearly always a
        Debit or Credit position pointing at the wrong column."""
        empty_rows = [row for row in data if not row['Debit'] and not row['Credit']]
        if not empty_rows:
            return
        config = self.bank_statement_config_id
        positions = {
            line.header_type_id.name: line.position
            for line in config.bank_statement_header_line_ids
        }
        shown = '\n'.join(
            _('Row %s (%s): Debit read "%s", Credit read "%s"') % (
                row['Row'], row['Date'], row['Debit Text'] or _('empty'), row['Credit Text'] or _('empty')
            )
            for row in empty_rows[:10]
        )
        if len(empty_rows) > 10:
            shown += _('\n... and %s more') % (len(empty_rows) - 10)
        raise UserError(_(
            'These rows have no Debit or Credit amount:\n%s\n\n'
            'The Bank Statement configuration "%s" reads Debit from position %s and Credit from '
            'position %s. Positions start at 0 for the first column of the file (column A). '
            'Check that they point at the Debit and Credit columns.'
        ) % (shown, config.name, _column_label(positions.get('Debit')), _column_label(positions.get('Credit'))))

    def _check_duplicate_rows(self, data, master):
        """A reconciliation cannot hold two lines with the same reference, date
        and amounts. Name the rows of the file that clash, instead of letting the
        import fail on the first one without saying which it is."""
        currency = master.currency_id
        seen = {
            (line.reference, line.date, line.debit, line.credit): _('a line already in this reconciliation')
            for line in master.transaction_ids if line.reference
        }
        clashes = []
        for row in data:
            if not row['Reference']:
                continue
            key = (row['Reference'], row['Date'], currency.round(row['Debit']), currency.round(row['Credit']))
            if key in seen:
                clashes.append(_('Row %s is the same as %s: reference %s, date %s, debit %s, credit %s') % (
                    row['Row'], seen[key], key[0], key[1], key[2], key[3]
                ))
            else:
                seen[key] = _('row %s') % row['Row']
        if clashes:
            shown = '\n'.join(clashes[:10])
            if len(clashes) > 10:
                shown += _('\n... and %s more') % (len(clashes) - 10)
            raise UserError(_(
                'Some rows of the file have the same reference, date and amount as another row:\n%s\n\n'
                'If they are different transactions, the column used as Reference is not unique for '
                'each transaction. In the Bank Statement configuration, set the Reference header to the '
                'column holding the transaction ID, or remove it, then upload again.'
            ) % shown)

    def _get_or_create_master(self):
        if self.master_id:
            return self.master_id
        vals = {
            'date': self.date,
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
                for line in config.bank_statement_header_line_ids
            }

            def get(row, key):
                index = header_map.get(key)
                if index is None or index < 0 or index >= len(row):
                    return ""
                return row[index]

            for row_number, row in enumerate(rows[1:], start=2):

                date_str = str(get(row, "Date")).strip()

                if not date_str:
                    continue

                date_obj = False

                for fmt in (
                    "%Y-%m-%d",
                    "%d/%m/%Y",
                    "%m/%d/%Y",
                    "%d-%m-%Y",
                    "%d-%b-%Y",
                ):
                    try:
                        date_obj = datetime.strptime(date_str, fmt).date()
                        break
                    except Exception:
                        pass

                if not date_obj:
                    continue

                debit = _to_amount(get(row, "Debit"))
                credit = _to_amount(get(row, "Credit"))

                data.append({
                    "Row": row_number,
                    "Date": date_obj,
                    "Description": str(get(row, "Description") or "").strip(),
                    "Debit": debit,
                    "Credit": credit,
                    "Debit Text": str(get(row, "Debit")).strip(),
                    "Credit Text": str(get(row, "Credit")).strip(),
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
                for line in config.bank_statement_header_line_ids
            }

            def get(row, key):
                index = header_map.get(key)
                if index is None or index < 0 or index >= len(row):
                    return ""
                return row[index].value

            def text(row, key):
                value = get(row, key)
                # An ID typed as a number comes back as 12338204.0
                if isinstance(value, float) and value.is_integer():
                    value = int(value)
                return str(value or "").strip()

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
                        "%d-%b-%Y",
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

                debit = _to_amount(get(row, "Debit"))
                credit = _to_amount(get(row, "Credit"))

                data.append({
                    "Row": row_no + 1,
                    "Date": date_obj,
                    "Description": text(row, "Description"),
                    "Debit": debit,
                    "Credit": credit,
                    "Debit Text": str(get(row, "Debit")).strip(),
                    "Credit Text": str(get(row, "Credit")).strip(),
                    "Reference": text(row, "Reference"),
                    "Payment Reference": text(row, "Payment Reference"),
                    "Partner": text(row, "Partner"),
                    "Invoice Number": text(row, "Invoice Number"),
                })

        except Exception as e:
            raise UserError(_("Error parsing Excel: %s") % str(e))

        return data