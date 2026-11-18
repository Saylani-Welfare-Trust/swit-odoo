from odoo import _, models
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        """A journal entry is analysed completely or not at all: once one of
        its lines carries an analytic distribution, every line on an income
        or expense account must carry one. Receivable / payable, bank and
        tax lines are exempt (Odoo never puts analytic on them)."""
        for move in self:
            lines = move.line_ids.filtered(lambda l: l.display_type not in ('line_section', 'line_note'))
            if not any(lines.mapped('analytic_distribution')):
                continue
            missing = lines.filtered(
                lambda l: l.account_id.internal_group in ('income', 'expense') and not l.analytic_distribution)
            if missing:
                raise ValidationError(_(
                    '%(move)s: some lines have an Analytic Account and these income / expense lines do not:\n%(lines)s\n\n'
                    'Please set the Analytic Account on them too.'
                ) % {
                    'move': move.display_name,
                    'lines': '\n'.join('  • %s - %s' % (l.account_id.display_name, l.name or '') for l in missing),
                })
        return super()._post(soft)
