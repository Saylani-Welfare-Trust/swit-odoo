import io
import json
import re
import xlsxwriter
from odoo import models, api
from odoo.osv import expression
from datetime import date, datetime


class AdvanceDonationStatementWizard(models.AbstractModel):
    _name = 'advance.donation.statement.wizard'
    _description = 'Advance Donation Statement'

    # Contact fields a donor / donee is found by (the ones a contact does not
    # have are skipped)
    _PARTNER_SEARCH_FIELDS = (
        'name', 'mobile', 'phone', 'cnic_no', 'ref',
        'primary_registration_id', 'secondary_registration_id',
        'registration_ids.code',
    )

    # ------------------------------------------------------------------
    #  Donor lookup (statement filter)
    # ------------------------------------------------------------------
    @api.model
    def search_donors(self, term='', limit=20):
        """Donors matching ``term`` by name, mobile, CNIC, registration ID..."""
        Partner = self.env['res.partner']
        domain = Partner._tag_domain('donor')
        term = (term or '').strip()
        if term:
            domain = expression.AND([domain, self._partner_search_domain(Partner, term)])
        return [
            {'id': p.id, 'name': p.name or '', 'details': self._partner_details(p)}
            for p in Partner.search(domain, limit=limit, order='name')
        ]

    def _partner_search_domain(self, Partner, term):
        fields_ = [f for f in self._PARTNER_SEARCH_FIELDS if f.split('.')[0] in Partner._fields]
        domain = expression.OR([[(f, 'ilike', term)] for f in fields_])
        digits = re.sub(r'[\s-]', '', term)
        if 'cnic_no' in Partner._fields and len(digits) == 13 and digits.isdigit():
            # a CNIC typed without its dashes
            cnic = '%s-%s-%s' % (digits[:5], digits[5:12], digits[12:])
            domain = expression.OR([domain, [('cnic_no', '=', cnic)]])
        return domain

    def _partner_details(self, partner):
        return ' · '.join(
            partner[f] for f in ('primary_registration_id', 'mobile', 'cnic_no')
            if f in partner._fields and partner[f])

    def _partner_search_text(self, partners):
        """Name and numbers of the donees of a line, for the statement search."""
        parts = []
        for p in partners or []:
            parts.append(p.name or '')
            parts += [p[f] for f in ('mobile', 'phone', 'cnic_no', 'ref',
                                     'primary_registration_id', 'secondary_registration_id')
                      if f in p._fields and p[f]]
            if 'registration_ids' in p._fields:
                parts += p.registration_ids.mapped('code')
        return ' '.join(parts)

    # ------------------------------------------------------------------
    #  Statement
    # ------------------------------------------------------------------
    @api.model
    def get_statement_data(self, date_from=None, date_to=None, donor_id=False):
        """Movements of ONE donor. Without a donor the statement is empty.

        The movements before ``date_from`` make the opening balance, so the
        running balance of the period continues the donor's whole history.
        Without dates every movement is listed (opening balance 0)."""
        currency = self.env.company.currency_id
        result = {
            'donor':           False,
            'lines':           [],
            'opening_balance': 0.0,
            'total_in':        0.0,
            'total_out':       0.0,
            'balance':         0.0,
            'currency':        currency.name,
        }
        donor = self.env['res.partner'].browse(int(donor_id)).exists() if donor_id else None
        if not donor:
            return result

        df = self._to_date(date_from)
        dt = self._to_date(date_to)
        df_s = df.isoformat() if df else None
        dt_s = dt.isoformat() if dt else None

        movements = self._get_movements(donor)
        movements.sort(key=lambda m: (m['date'] or '0000-00-00',
                                      0 if m['direction'] == 'in' else 1,
                                      m['reference'] or ''))

        opening = 0.0
        lines = []
        for m in movements:
            if df_s and (m['date'] or '') < df_s:
                opening += m['amount_in'] - m['amount_out']
            elif not (dt_s and m['date'] and m['date'] > dt_s):
                lines.append(m)

        opening = currency.round(opening)
        running = opening
        for line in lines:
            running = currency.round(running + line['amount_in'] - line['amount_out'])
            line['balance'] = running

        total_in = currency.round(sum(l['amount_in'] for l in lines))
        total_out = currency.round(sum(l['amount_out'] for l in lines))
        result.update({
            'donor':           {'id': donor.id, 'name': donor.name or '',
                                'details': self._partner_details(donor)},
            'lines':           lines,
            'opening_balance': opening,
            'total_in':        total_in,
            'total_out':       total_out,
            'balance':         currency.round(opening + total_in - total_out),
        })
        return result

    def _get_movements(self, donor):
        """Every movement of the donor, undated by the statement period."""
        lines = []

        # ---------------- IN side : paid receipts ------------------------
        Receipt = self.env['advance.donation.receipt']
        payment_types = dict(Receipt._fields['payment_type'].selection)
        for r in Receipt.search([('state', '=', 'paid'), ('donor_id', '=', donor.id)]):
            lines.append(self._movement(
                r.date, r.name, 'Receipt', 'in',
                amount_in=float(r.amount or 0.0),
                partner=r.donor_id.name or '',
                description=payment_types.get(r.payment_type, ''),
            ))

        # ---------------- OUT side : disbursements -----------------------
        # What was actually given out of the donation lines (welfare and
        # recurring lines register one record per payment).
        records = self.env['advance.donation.disbursement.line'].search(
            [('advance_donation_id.donor_id', '=', donor.id)])
        covered_line_ids = set(records.mapped('advance_donation_line_id').ids)
        # the donee / source record is in a program module (welfare,
        # microfinance) the statement user may have no access to
        for rec in records.sudo():
            amount = float(rec.disbursed_amount or rec.advance_amount or 0.0)
            if amount > 0:
                lines.append(self._disbursement_record_line(rec, amount))

        # program records using a donation line without such a record
        program_lines, linked_line_ids = self._get_program_disbursements(None, None, donor.id)
        lines += program_lines
        covered_line_ids |= set(linked_line_ids)

        # donation lines marked disbursed by hand
        disbursed_lines = self.env['advance.donation.lines'].search([
            ('is_disbursed', '=', True),
            ('advance_donation_id.donor_id', '=', donor.id),
            ('id', 'not in', list(covered_line_ids)),
        ])
        for line in disbursed_lines:
            donation = line.advance_donation_id
            amount = float(line.paid_amount or line.amount or 0.0)
            if amount <= 0:
                continue
            lines.append(self._movement(
                line.disbursement_date, donation.name or '', 'Disbursement', 'out',
                amount_out=amount,
                partner=donation.donor_id.name or '',
                purpose='Advance Donation Disbursement',
                beneficiary=donation.donor_id.name or '',
                description=(line.product_id.display_name if line.product_id
                             else (line.description or '')),
            ))
        return lines

    # ---------- helpers --------------------------------------------------
    def _movement(self, rec_date, reference, type_, direction, amount_in=0.0, amount_out=0.0,
                  partner='', purpose='', beneficiary='', description='', donees=None):
        return {
            'date':         rec_date.strftime('%Y-%m-%d') if rec_date else '',
            'reference':    reference or '',
            'partner':      partner,
            'type':         type_,
            'direction':    direction,
            'purpose':      purpose,
            'beneficiary':  beneficiary,
            'description':  description,
            'amount_in':    amount_in,
            'amount_out':   amount_out,
            'search_text':  self._partner_search_text(donees),
        }

    def _disbursement_record_line(self, rec, amount):
        donation = rec.advance_donation_id or rec.advance_donation_line_id.advance_donation_id
        donees = self._disbursement_donees(rec)
        product = rec.product_id or rec.advance_donation_line_id.product_id
        return self._movement(
            rec.date, rec.disbursed_record or donation.name, 'Disbursement', 'out',
            amount_out=amount,
            partner=donation.donor_id.name or '',
            purpose=self._disbursement_purpose(rec),
            beneficiary=', '.join(n for n in donees.mapped('name') if n),
            description=product.display_name or '',
            donees=donees,
        )

    def _disbursement_donees(self, rec):
        """Donees of a disbursement record, extended by the program modules."""
        return rec._get_donees()

    def _disbursement_purpose(self, rec):
        labels = [label for label, _name in rec._get_source_links() if label]
        return labels[0] if labels else 'Advance Donation Disbursement'

    def _get_program_disbursements(self, df, dt, donor_id):
        """Hook for the program modules: (statement lines, ids of the
        advance donation lines they cover). The covered donation lines are
        not listed again on their own."""
        return [], set()

    def _keep_disbursement(self, rec, df, dt, donor_id):
        """Whether a program record linked to an advance donation line is
        in the statement's donor / period."""
        d = rec.advance_donation_line_id.advance_donation_id
        if not d:
            return False
        if donor_id and d.donor_id.id != donor_id:
            return False
        rd = self._rec_date(rec)
        if df and rd and rd < df:
            return False
        if dt and rd and rd > dt:
            return False
        return True

    def _disbursement_line(self, rec, purpose, amount, beneficiary, description,
                           donees=None, rec_date=None):
        d = rec.advance_donation_line_id.advance_donation_id
        return self._movement(
            rec_date or self._rec_date(rec), rec.display_name, 'Disbursement', 'out',
            amount_out=amount,
            partner=d.donor_id.name or '',
            purpose=purpose,
            beneficiary=beneficiary,
            description=description,
            donees=donees,
        )

    def _pick_amount(self, rec, field_names):
        for f in field_names:
            if f in rec._fields:
                v = rec[f]
                if v:
                    return float(v)
        return 0.0

    def _rec_date(self, rec, field_names=('date', 'disbursement_date', 'create_date')):
        """Best-effort date for a welfare / microfinance record."""
        for fname in field_names:
            if fname in rec._fields and rec[fname]:
                v = rec[fname]
                return v.date() if isinstance(v, datetime) else v
        return None

    def _to_date(self, s):
        if not s:
            return None
        if isinstance(s, datetime):
            return s.date()
        if isinstance(s, date):
            return s
        return datetime.strptime(s, '%Y-%m-%d').date()

    @api.model
    def get_xlsx_report(self, data, response, report_name, report_action):
        """
        XLSX export for the Advance Donation Statement.
        `data` is the JSON string sent from the OWL component.
        """
        payload = json.loads(data)
        lines           = payload.get("lines", [])
        date_from       = payload.get("date_from", "")
        date_to         = payload.get("date_to", "")
        search          = payload.get("search", "")
        donor_name      = payload.get("donor_name", "")
        opening_balance = payload.get("opening_balance", 0)
        total_in        = payload.get("total_in", 0)
        total_out       = payload.get("total_out", 0)
        balance         = payload.get("balance", 0)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Advance Donation")

        # -------- formats --------
        head_fmt       = workbook.add_format({"bold": True, "font_size": 15, "align": "center"})
        sub_fmt        = workbook.add_format({"font_size": 10, "align": "center", "italic": True})
        th_fmt         = workbook.add_format({"bold": True, "font_size": 10,
                                              "align": "center", "border": 1,
                                              "bg_color": "#D3D3D3"})
        cell_left      = workbook.add_format({"font_size": 10, "border": 1, "align": "left"})
        cell_right_num = workbook.add_format({"font_size": 10, "border": 1,
                                              "align": "right", "num_format": "#,##0.00"})
        total_fmt      = workbook.add_format({"bold": True, "font_size": 11,
                                              "align": "right", "border": 1,
                                              "num_format": "#,##0.00",
                                              "bg_color": "#EFEFEF"})
        total_lbl_fmt  = workbook.add_format({"bold": True, "font_size": 11,
                                              "align": "right", "border": 1,
                                              "bg_color": "#EFEFEF"})

        # -------- column widths --------
        widths = [12, 18, 26, 14, 26, 24, 34, 14, 14, 14]
        for i, w in enumerate(widths):
            sheet.set_column(i, i, w)

        # -------- title --------
        sheet.merge_range(0, 0, 0, 9, report_name or "Advance Donation Statement", head_fmt)
        sub_txt = "Donor: %s   |   %s" % (donor_name, self._period_label(date_from, date_to))
        if search:
            sub_txt += f'   |   search: "{search}"'
        sheet.merge_range(1, 0, 1, 9, sub_txt, sub_fmt)

        # -------- header row --------
        headers = ["Date", "Reference", "Donor", "Type", "Purpose",
                   "Beneficiary", "Description", "In", "Out", "Balance"]
        row = 3
        for i, h in enumerate(headers):
            sheet.write(row, i, h, th_fmt)
        row += 1

        # -------- opening balance --------
        sheet.write(row, 0, date_from or "", cell_left)
        sheet.merge_range(row, 1, row, 8, "Opening Balance", cell_left)
        sheet.write(row, 9, float(opening_balance or 0), cell_right_num)
        row += 1

        # -------- data rows --------
        for l in lines:
            sheet.write(row, 0, l.get("date") or "", cell_left)
            sheet.write(row, 1, l.get("reference") or "", cell_left)
            sheet.write(row, 2, l.get("partner") or "", cell_left)
            sheet.write(row, 3, l.get("type") or "", cell_left)
            sheet.write(row, 4, l.get("purpose") or "", cell_left)
            sheet.write(row, 5, l.get("beneficiary") or "", cell_left)
            sheet.write(row, 6, l.get("description") or "", cell_left)
            sheet.write(row, 7, float(l.get("amount_in") or 0), cell_right_num)
            sheet.write(row, 8, float(l.get("amount_out") or 0), cell_right_num)
            sheet.write(row, 9, float(l.get("balance") or 0), cell_right_num)
            row += 1

        # -------- totals --------
        sheet.merge_range(row, 0, row, 6, "Totals / Closing Balance", total_lbl_fmt)
        sheet.write(row, 7, float(total_in),  total_fmt)
        sheet.write(row, 8, float(total_out), total_fmt)
        sheet.write(row, 9, float(balance),   total_fmt)

        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()

    def _period_label(self, date_from, date_to):
        if date_from and date_to:
            return "From %s to %s" % (date_from, date_to)
        if date_from:
            return "From %s" % date_from
        if date_to:
            return "Up to %s" % date_to
        return "All transactions"
