import io
import json
import xlsxwriter
from odoo import models, api
from datetime import datetime


class AdvanceDonationStatementWizard(models.TransientModel):
    _name = 'advance.donation.statement.wizard'
    _description = 'Advance Donation Statement'

    @api.model
    def get_statement_data(self, date_from=None, date_to=None, donor_id=False):
        Receipt    = self.env['advance.donation.receipt']
        DonLine    = self.env['advance.donation.lines']
        Welfare    = self.env['welfare.line']
        Micro      = self.env['microfinance']

        df = self._to_date(date_from) if date_from else None
        dt = self._to_date(date_to)   if date_to   else None

        # ---------------- IN side : receipts -----------------------------
        rec_domain = [('state', '=', 'paid')]
        if df:
            rec_domain.append(('date', '>=', df))
        if dt:
            rec_domain.append(('date', '<=', dt))
        if donor_id:
            rec_domain.append(('donor_id', '=', donor_id))

        receipts = Receipt.search(rec_domain)

        # ---------------- OUT side : welfare / microfinance --------------
        welfare_lines = Welfare.search([('advance_donation_line_id', '!=', False)])
        micro_records = Micro.search([('advance_donation_line_id', '!=', False)])

        def _keep(rec):
            d = rec.advance_donation_line_id.advance_donation_id
            if not d:
                return False
            if donor_id and d.donor_id.id != donor_id:
                return False
            # Prefer a real date field if it exists, otherwise fall back to create_date
            rd = None
            for fname in ('date', 'disbursement_date', 'create_date'):
                if fname in rec._fields and rec[fname]:
                    v = rec[fname]
                    rd = v.date() if isinstance(v, datetime) else v
                    break
            if df and rd and rd < df:
                return False
            if dt and rd and rd > dt:
                return False
            return True

        welfare_lines = welfare_lines.filtered(_keep)
        micro_records = micro_records.filtered(_keep)

        # ---------------- OUT side : disbursed donation lines -----------
        # This is the important addition. Even if no welfare / microfinance
        # record links back, the donation line itself carries the flag.
        disb_domain = [('is_disbursed', '=', True)]
        if donor_id:
            disb_domain.append(('advance_donation_id.donor_id', '=', donor_id))
        if df:
            disb_domain.append(('disbursement_date', '>=', df))
        if dt:
            disb_domain.append(('disbursement_date', '<=', dt))

        disbursed_lines = DonLine.search(disb_domain)

        # Lines already represented by a welfare / microfinance row (avoid
        # double counting). We key them by the donation‑line id.
        linked_line_ids = set()
        for w in welfare_lines:
            if w.advance_donation_line_id:
                linked_line_ids.add(w.advance_donation_line_id.id)
        for m in micro_records:
            if m.advance_donation_line_id:
                linked_line_ids.add(m.advance_donation_line_id.id)

        # ---------------- assemble movements ----------------------------
        lines = []

        for r in receipts:
            lines.append({
                'date':         r.date.strftime('%Y-%m-%d') if r.date else '',
                'reference':    r.name,
                'partner':      r.donor_id.name or '',
                'type':         'Receipt',
                'direction':    'in',
                'purpose':      '',
                'beneficiary':  '',
                'description':  dict(r._fields['payment_type'].selection)
                                .get(r.payment_type, ''),
                'amount_in':    float(r.amount or 0.0),
                'amount_out':   0.0,
            })

        for w in welfare_lines:
            d = w.advance_donation_line_id.advance_donation_id
            amount = self._pick_amount(w, [
                'advance_donation_amount', 'total_amount',
                'amount', 'disbursed_amount',
            ])
            if not amount:
                continue
            lines.append({
                'date':         self._rec_date(w).strftime('%Y-%m-%d')
                                 if self._rec_date(w) else '',
                'reference':    w.display_name,
                'partner':      d.donor_id.name or '',
                'type':         'Disbursement',
                'direction':    'out',
                'purpose':      'Welfare',
                'beneficiary':  (w.welfare_id.display_name
                                 if getattr(w, 'welfare_id', False) else ''),
                'description':  (w.product_id.display_name
                                 if getattr(w, 'product_id', False) else ''),
                'amount_in':    0.0,
                'amount_out':   amount,
            })

        for m in micro_records:
            d = m.advance_donation_line_id.advance_donation_id
            amount = self._pick_amount(m, [
                'advance_donation_amount', 'amount',
                'loan_amount', 'disbursed_amount',
            ])
            if not amount:
                continue
            lines.append({
                'date':         self._rec_date(m).strftime('%Y-%m-%d')
                                 if self._rec_date(m) else '',
                'reference':    m.display_name,
                'partner':      d.donor_id.name or '',
                'type':         'Disbursement',
                'direction':    'out',
                'purpose':      'Microfinance',
                'beneficiary':  m.display_name,
                'description':  (m.product_id.display_name
                                 if getattr(m, 'product_id', False) else ''),
                'amount_in':    0.0,
                'amount_out':   amount,
            })

        # ---- NEW: disbursed donation lines without a welfare/micro link ----
        for line in disbursed_lines:
            if line.id in linked_line_ids:
                continue  # already accounted for above
            donation = line.advance_donation_id
            amount   = float(line.paid_amount or line.amount or 0.0)
            if amount <= 0:
                continue
            lines.append({
                'date':         line.disbursement_date.strftime('%Y-%m-%d')
                                 if line.disbursement_date else '',
                'reference':    donation.name or '',
                'partner':      donation.donor_id.name or '',
                'type':         'Disbursement',
                'direction':    'out',
                'purpose':      'Advance Donation Disbursement',
                'beneficiary':  donation.donor_id.name or '',
                'description':  (line.product_id.display_name
                                 if line.product_id else
                                 (line.description or '')),
                'amount_in':    0.0,
                'amount_out':   amount,
            })

        # ---------------- sort + running balance ------------------------
        lines.sort(key=lambda x: (x['date'] or '0000-00-00',
                                  0 if x['direction'] == 'in' else 1))

        running = 0.0
        for l in lines:
            running += l['amount_in'] - l['amount_out']
            l['balance'] = running

        total_in  = sum(l['amount_in']  for l in lines)
        total_out = sum(l['amount_out'] for l in lines)

        return {
            'lines':     lines,
            'total_in':  total_in,
            'total_out': total_out,
            'balance':   total_in - total_out,
            'currency':  self.env.company.currency_id.name,
        }

    # ---------- helpers --------------------------------------------------
    def _pick_amount(self, rec, field_names):
        for f in field_names:
            if f in rec._fields:
                v = rec[f]
                if v:
                    return float(v)
        return 0.0

    def _rec_date(self, rec):
        """Best-effort date for a welfare / microfinance record."""
        for fname in ('date', 'disbursement_date', 'create_date'):
            if fname in rec._fields and rec[fname]:
                v = rec[fname]
                return v.date() if isinstance(v, datetime) else v
        return None

    def _to_date(self, s):
        if not s:
            return None
        if isinstance(s, datetime):
            return s.date()
        return datetime.strptime(s, '%Y-%m-%d').date()
    
    @api.model
    def get_xlsx_report(self, data, response, report_name, report_action):
        """
        XLSX export for the Advance Donation Statement.
        `data` is the JSON string sent from the OWL component.
        """
        payload = json.loads(data)
        lines        = payload.get("lines", [])
        currency     = payload.get("currency", "")
        date_from    = payload.get("date_from", "")
        date_to      = payload.get("date_to", "")
        search       = payload.get("search", "")
        total_in     = payload.get("total_in", 0)
        total_out    = payload.get("total_out", 0)
        balance      = payload.get("balance", 0)

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
        sub_txt = f"{date_from}  →  {date_to}"
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
        sheet.merge_range(row, 0, row, 6, "Totals", total_lbl_fmt)
        sheet.write(row, 7, float(total_in),  total_fmt)
        sheet.write(row, 8, float(total_out), total_fmt)
        sheet.write(row, 9, float(balance),   total_fmt)

        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()
