from odoo import models, api


class AdvanceDonationStatementWizard(models.TransientModel):
    _name = 'advance.donation.statement.wizard'
    _description = 'Advance Donation Statement'

    @api.model
    def get_statement_data(self, date_from=None, date_to=None, donor_id=False):
        Receipt = self.env['advance.donation.receipt']
        Welfare = self.env['welfare.line']
        Micro   = self.env['microfinance']

        # ---------- domains ------------------------------------------------
        rec_domain = [('state', '=', 'paid')]
        if date_from:
            rec_domain.append(('date', '>=', date_from))
        if date_to:
            rec_domain.append(('date', '<=', date_to))
        if donor_id:
            rec_domain.append(('donor_id', '=', donor_id))

        receipts = Receipt.search(rec_domain)

        # Welfare / microfinance lines that actually consumed an advance
        # donation.  We filter by the linked donation line, not by date,
        # because welfare lines may not carry a natural "date" field.
        welfare_lines = Welfare.search([('advance_donation_line_id', '!=', False)])
        micro_records = Micro.search([('advance_donation_line_id', '!=', False)])

        # Optional date + donor filter on the out-side
        def _keep(rec):
            d = (rec.advance_donation_line_id
                 and rec.advance_donation_line_id.advance_donation_id)
            if not d:
                return False
            if donor_id and d.donor_id.id != donor_id:
                return False
            if date_from and rec.create_date and \
                    rec.create_date.date() < self._to_date(date_from):
                return False
            if date_to and rec.create_date and \
                    rec.create_date.date() > self._to_date(date_to):
                return False
            return True

        welfare_lines = welfare_lines.filtered(_keep)
        micro_records = micro_records.filtered(_keep)

        # ---------- assemble movements ------------------------------------
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
                'date':         (w.create_date.strftime('%Y-%m-%d')
                                 if w.create_date else
                                 (w.date.strftime('%Y-%m-%d')
                                  if getattr(w, 'date', False) else '')),
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
                'date':         (m.create_date.strftime('%Y-%m-%d')
                                 if m.create_date else ''),
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

        # ---------- sort + running balance --------------------------------
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

    # ---------- helpers ---------------------------------------------------
    def _pick_amount(self, rec, field_names):
        """Return the first non-zero numeric field from the list."""
        for f in field_names:
            if f in rec._fields:
                v = rec[f]
                if v:
                    return float(v)
        return 0.0

    def _to_date(self, s):
        from datetime import datetime
        return datetime.strptime(s, '%Y-%m-%d').date()