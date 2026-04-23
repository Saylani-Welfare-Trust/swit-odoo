from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.addons.analytic.models.analytic_distribution_model import NonMatchingDistribution


class AnalyticDistributionModel(models.Model):
    _inherit = 'account.analytic.distribution.model'


    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account")
    
    product_id = fields.Many2many(
        'product.product',
        string='Product',
        ondelete='cascade',
        check_company=True,
        help="Select a product for which the analytic distribution will be used (e.g. create new customer invoice or Sales order if we select this product, it will automatically take this as an analytic account)",
    )


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
    
    def _check_score(self, key, value):
        self.ensure_one()

        if key == 'company_id':
            if not self.company_id or value == self.company_id.id:
                return 1 if self.company_id else 0.5
            raise NonMatchingDistribution
        if not self[key]:
            return 0
        if value and ((self[key].id in value) if isinstance(value, (list, tuple))
                      else (value.startswith(self[key])) if key.endswith('_prefix')
                      else (value == self[key].id) if key != 'product_id' else  (value in self[key].ids)
                      ):
            return 1
        
        raise NonMatchingDistribution
    
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