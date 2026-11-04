from collections import defaultdict

from odoo import models
from odoo.exceptions import ValidationError
from odoo.tools import float_round


class AccountMove(models.Model):
    _inherit = 'account.move'


    def _get_invoice_lines_analytic_distribution(self):
        """The analytic distribution of the bill as a whole: that of its invoice
        lines, weighted by their amounts."""
        self.ensure_one()
        lines = self.invoice_line_ids.filtered(lambda l: l.display_type == 'product' and l.analytic_distribution)
        by_amount = any(lines.mapped('balance'))
        shares = defaultdict(float)
        total = 0.0
        for line in lines:
            weight = abs(line.balance) if by_amount else 1.0
            total += weight
            for key, percentage in line.analytic_distribution.items():
                shares[key] += weight * percentage
        if not total:
            return {}
        digits = self.env['decimal.precision'].precision_get('Percentage Analytic')
        distribution = {key: float_round(share / total, precision_digits=digits) for key, share in shares.items()}
        # Rounding must not leave a fraction of the payable out, or add one.
        largest = max(distribution, key=distribution.get)
        distribution[largest] = float_round(
            distribution[largest] + sum(shares.values()) / total - sum(distribution.values()), precision_digits=digits)
        return {key: percentage for key, percentage in distribution.items() if percentage}

    def _set_payable_analytic_distribution(self):
        """Odoo only fills the analytic distribution of invoice lines, so the
        payable line of a vendor bill would always be an untagged line. Unless it
        was tagged by hand, it takes the distribution of the bill's invoice lines."""
        for move in self:
            if not move.is_purchase_document(include_receipts=True):
                continue
            payable_lines = move.line_ids.filtered(
                lambda l: l.display_type == 'payment_term' and not l.analytic_distribution)
            distribution = payable_lines and move._get_invoice_lines_analytic_distribution()
            if distribution:
                payable_lines.analytic_distribution = distribution

    def _post(self, soft=True):
        self._set_payable_analytic_distribution()

        flag = False

        for line in self.line_ids:
            if line.analytic_distribution:
                flag = True

        if flag:
            for line in self.line_ids:
                if not line.analytic_distribution:
                    raise ValidationError('Please contact your friendly Administrator and ask him/her to assign (Analytic Account) on untag lines.')

        return super(AccountMove, self)._post(soft)