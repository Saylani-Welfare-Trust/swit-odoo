from odoo import models, fields, api

from odoo.addons.analytic.models.analytic_distribution_model import NonMatchingDistribution


class AnalyticDistributionModel(models.Model):
    _name = 'account.analytic.distribution.model'
    _inherit = ['account.analytic.distribution.model', 'mail.thread', 'mail.activity.mixin']


    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", tracking=True)

    partner_id = fields.Many2one('res.partner', string="Partner", tracking=True)
    partner_category_id = fields.Many2one('res.partner.category', string="Partner Category", tracking=True)

    account_prefix = fields.Char(string="Account Prefix", tracking=True)

    product_categ_id = fields.Many2one('product.category', string='Product Category', tracking=True)
    
    product_id = fields.Many2many(
        'product.product',
        string='Product',
        ondelete='cascade',
        check_company=True,
        help="Select a product for which the analytic distribution will be used (e.g. create new customer invoice or Sales order if we select this product, it will automatically take this as an analytic account)",
    )


    @api.model
    def _bn_product_commands(self, vals):
        """product_id is a Many2many here, but Odoo (and imports) may still
        give one product id, as for the standard Many2one."""
        if isinstance(vals.get('product_id'), int):
            vals = dict(vals, product_id=[(6, 0, [vals['product_id']] if vals['product_id'] else [])])
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._bn_product_commands(vals) for vals in vals_list])

    def write(self, vals):
        return super().write(self._bn_product_commands(vals))

    @api.model
    def _get_distribution(self, vals):
        """Odoo's matching, plus the user's branch: the analytic account of
        the current user's employee is matched against the model's Branch."""
        vals = dict(vals)
        vals['analytic_account_id'] = self.env.user.employee_id.analytic_account_id.id
        return super()._get_distribution(vals)

    def _get_fields_to_check(self):
        # The chatter (mail.thread / mail.activity.mixin) adds fields such as
        # message_ids: they are not matching conditions.
        chatter = set(self.env['mail.thread']._fields) | set(self.env['mail.activity.mixin']._fields)
        return super()._get_fields_to_check() - chatter

    def _create_domain(self, fname, value):
        if fname == 'product_id' and value:
            # product_id holds several products here: a model applies to one
            # of its products, or to every product when it has none.
            return ['|', ('product_id', 'in', [value]), ('product_id', '=', False)]
        return super()._create_domain(fname, value)

    def _check_score(self, key, value):
        """As in Odoo: a condition the model sets but the line does not meet
        rejects the model (NonMatchingDistribution); it does not just score 0."""
        self.ensure_one()
        if key == 'product_id':
            if not self.product_id:
                return 0
            if value and value in self.product_id.ids:
                return 1
            raise NonMatchingDistribution
        return super()._check_score(key, value)

    @api.onchange('analytic_account_id')
    def _onchange_analytic_account_id(self):
        """Put the Branch in front of every distribution line, replacing a
        branch of the same plan chosen before (instead of piling them up)."""
        branch = self.analytic_account_id
        if not branch:
            return
        distribution = self.analytic_distribution or {}
        if not distribution:
            self.analytic_distribution = {str(branch.id): 100}
            return
        Account = self.env['account.analytic.account']
        new = {}
        for key, value in distribution.items():
            ids = [int(i) for i in key.split(',') if i]
            others = [i for i in ids if Account.browse(i).plan_id != branch.plan_id]
            new_key = ','.join(str(i) for i in [branch.id] + others)
            new[new_key] = new.get(new_key, 0) + value
        self.analytic_distribution = new
