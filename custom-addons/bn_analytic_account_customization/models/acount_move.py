from odoo import models
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'


    def _post(self, soft=True):
        flag = False

        for line in self.line_ids:
            if line.analytic_distribution:
                flag = True

        if flag:
            for line in self.line_ids:
                if not line.analytic_distribution:
                    raise ValidationError('Please contact your friendly Administrator and ask him/her to assign (Analytic Account) on untag lines.')

        return super(AccountMove, self)._post(soft)