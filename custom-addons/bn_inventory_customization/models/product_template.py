from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    check_stock = fields.Boolean(
        string='Is Livestock Product',
        default=False,
        tracking=True,
        help='Enable weight-based receiving for livestock products. '
             'When checked, this product will use the Receive by Weight wizard.'
    )
    
    livestock_variant = fields.Many2one(
        comodel_name='livestock.variant',
        string='Livestock Variant',
        required=False
    )

    purchase_product = fields.Many2one(
        comodel_name='product.product',
        relation='livestock_product',
        string='Purchase Product',
        help='Product you will make PO',
        required=False
    )

    main_attribute_id = fields.Many2one(
        comodel_name='product.attribute',
        string='Main Attribute',
        help='When set, only this attribute\'s values are used to determine the highest to_kg.'
    )

    analytic_account_id = fields.Many2one('account.analytic.account', string="Analytic Account", tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._link_analytic_products()
        return records

    def write(self, vals):
        old_accounts = {}
        if 'analytic_account_id' in vals:
            old_accounts = {t.id: t.analytic_account_id for t in self}
        res = super().write(vals)
        if 'analytic_account_id' in vals:
            for template in self:
                old = old_accounts.get(template.id)
                if old and old != template.analytic_account_id:
                    old.product_ids = [(3, pid) for pid in template.product_variant_ids.ids]
            self._link_analytic_products()
        return res

    def _link_analytic_products(self):
        for template in self.filtered('analytic_account_id'):
            template.analytic_account_id.product_ids = [(4, pid) for pid in template.product_variant_ids.ids]

    @api.model
    def _backfill_analytic_products(self):
        self.with_context(active_test=False).search([('analytic_account_id', '!=', False)])._link_analytic_products()
