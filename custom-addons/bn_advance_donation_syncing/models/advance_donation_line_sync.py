from odoo import models, fields, api


class AdvanceDonationLineSync(models.Model):
    """Extend advance donation line with reservation status"""
    _name = 'advance.donation.lines'
    _inherit = 'advance.donation.lines'

    # Simple boolean to track if this donation line is reserved by a welfare/recurring line
    is_reserved = fields.Boolean(
        'Reserved',
        default=False,
        help='Indicates if this donation line is reserved for a welfare line or recurring order'
    )
    reserved_amount = fields.Float(
        'Reserved Amount',
        default=0.0,
        help='The amount reserved for this donation line'
    )   

    def _register_disbursement(self, amount, total_amount, welfare=None, welfare_line=None, record_name=''):
        """A welfare / recurring line funded by this donation line was paid:
        record the disbursement and mark the line disbursed once all of it is used."""
        self.ensure_one()
        disbursed = self.disbursed_amount + amount
        currency = self.currency_id or self.env.company.currency_id
        # a single-product line is reserved whole by one record (see the wizard)
        used_whole = (self.is_reserved and self.quantity <= 1
                      and self.advance_donation_id.contract_type != 'open_contract')
        self.write({
            'disbursed_amount': disbursed,
            'is_disbursed': used_whole or currency.compare_amounts(disbursed, self.amount) >= 0,
        })
        vals = {
            'advance_donation_id': self.advance_donation_id.id,
            'advance_donation_line_id': self.id,
            'product_id': self.product_id.id,
            'date': fields.Date.today(),
            'total_amount': total_amount,
            'advance_amount': amount,
            'disbursed_amount': amount,
            'disbursed_record': record_name,
        }
        if welfare:
            vals['welfare_id'] = welfare.id
        if welfare_line:
            vals['welfare_line_id'] = welfare_line.id
        return self.env['advance.donation.disbursement.line'].create(vals)
