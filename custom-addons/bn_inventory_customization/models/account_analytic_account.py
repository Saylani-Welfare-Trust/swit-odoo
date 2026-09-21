from odoo import api, fields, models


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    product_template_ids = fields.One2many(
        comodel_name='product.template',
        inverse_name='analytic_account_id',
        string='Products',
    )
    product_template_count = fields.Integer(
        string='Product Count',
        compute='_compute_product_template_count',
    )

    @api.depends('product_template_ids')
    def _compute_product_template_count(self):
        for account in self:
            account.product_template_count = len(account.product_template_ids)

    def action_view_products(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('product.product_template_action_all')
        action['domain'] = [('analytic_account_id', '=', self.id)]
        action['context'] = {'default_analytic_account_id': self.id}
        return action
