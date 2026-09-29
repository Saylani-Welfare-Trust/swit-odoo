from odoo import models, api, fields


class AdvanceDonationStatementWizard(models.TransientModel):
    _name = 'advance.donation.statement.wizard'
    _description = 'Advance Donation Statement'

    # ------------------------------------------------------------------
    #  Main RPC endpoint – returns a flat list of movements with a
    #  running balance, ready to be rendered by the OWL component.
    # ------------------------------------------------------------------
    @api.model
    def get_statement_data(self, date_from=None, date_to=None, donor_id=False):
        Receipt = self.env['advance.donation.receipt']
        Disb    = self.env['advance.donation.disbursement.line']

        # ---- domains ---------------------------------------------------
        rec_domain  = [('state', '=', 'paid')]
        disb_domain = []
        if date_from:
            rec_domain.append(('date', '>=', date_from))
            disb_domain.append(('date', '>=', date_from))
        if date_to:
            rec_domain.append(('date', '<=', date_to))
            disb_domain.append(('date', '<=', date_to))
        if donor_id:
            rec_domain.append(('donor_id', '=', donor_id))

        receipts      = Receipt.search(rec_domain)
        disbursements = Disb.search(disb_domain)

        # Disbursements carry the donor on the parent donation record.
        if donor_id:
            disbursements = disbursements.filtered(
                lambda d: d.advance_donation_id.donor_id.id == donor_id
            )

        # ---- build the flat movement list ------------------------------
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
                'description':  dict(
                                    r._fields['payment_type'].selection
                                ).get(r.payment_type, ''),
                'amount_in':    float(r.amount or 0.0),
                'amount_out':   0.0,
            })

        for d in disbursements:
            # Determine the purpose from whichever beneficiary field is set.
            purpose     = ''
            beneficiary = ''
            if d.welfare_id:
                purpose     = 'Welfare'
                beneficiary = d.welfare_id.display_name
            elif d.welfare_line_id:
                purpose     = 'Welfare Line'
                beneficiary = d.welfare_line_id.display_name
            elif d.microfinance_id:
                purpose     = 'Microfinance'
                beneficiary = d.microfinance_id.display_name

            lines.append({
                'date':         d.date.strftime('%Y-%m-%d') if d.date else '',
                'reference':    d.disbursed_record or '',
                'partner':      d.advance_donation_id.donor_id.name or '',
                'type':         'Disbursement',
                'direction':    'out',
                'purpose':      purpose,
                'beneficiary':  beneficiary,
                'description':  d.product_id.display_name or '',
                'amount_in':    0.0,
                'amount_out':   float(d.disbursed_amount or 0.0),
            })

        # ---- sort and compute running balance --------------------------
        # Receipts before disbursements when the dates are equal, so the
        # balance line always reads naturally.
        lines.sort(key=lambda x: (x['date'], 0 if x['direction'] == 'in' else 1))

        running = 0.0
        for l in lines:
            running += l['amount_in'] - l['amount_out']
            l['balance'] = running

        # ---- totals ----------------------------------------------------
        total_in  = sum(l['amount_in']  for l in lines)
        total_out = sum(l['amount_out'] for l in lines)

        return {
            'lines':     lines,
            'total_in':  total_in,
            'total_out': total_out,
            'balance':   total_in - total_out,
            'currency':  self.env.company.currency_id.name,
        }