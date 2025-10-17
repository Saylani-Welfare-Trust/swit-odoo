from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.addons.analytic.models.analytic_distribution_model import NonMatchingDistribution


class AnalyticDistributionModel(models.Model):
    _inherit = 'account.analytic.distribution.model'


    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account")


    @api.model
    def _get_distribution(self, vals):
        # Make a mutable copy of the input frozendict
        vals = dict(vals)

        # Now safe to modify
        vals['analytic_account_id'] = self.env.user.employee_id.analytic_account_id.id

        # raise ValidationError(str(vals))

        """ Returns the distribution model that has the most fields that corresponds to the vals given
            This method should be called to prefill analytic distribution field on several models """
        domain = []
        for fname, value in vals.items():
            domain += self._create_domain(fname, value) or []
        best_score = 0
        res = {}
        fnames = set(self._get_fields_to_check())

        for rec in self.search(domain):
            try:
                score = sum(rec._check_score(key, vals.get(key)) for key in fnames)
                if score > best_score:
                    res = rec.analytic_distribution
                    best_score = score
            except NonMatchingDistribution:
                continue
        return res
    
    @api.onchange('analytic_account_id')
    def _onchange_analytic_account_id(self):
        if self.analytic_account_id:
            if self.analytic_distribution:
                analytic_distribution = self.analytic_distribution
                # raise ValidationError(str(analytic_distribution))
                self.analytic_distribution = {}

                for key, value in analytic_distribution.items():
                    custom_key = f"{str(self.analytic_account_id.id)},{key}"
                    
                    self.analytic_distribution[custom_key] = value
            else:
                self.analytic_distribution = {
                    str(self.analytic_account_id.id): 100
                }