from odoo import fields, models
from odoo.tools.sql import table_exists

# the "Shariah Products" list analytic accounts had before products carried
# their analytic account themselves
OLD_PRODUCT_LIST = 'account_analytic_account_product_product_rel'


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # The analytic account (segment) of the product: Shariah Law balances,
    # budgets of material requests and the dashboards read it from here.
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string="Analytic Account", tracking=True, index='btree_not_null')

    def init(self):
        """A product listed on an analytic account keeps that account, set on
        the product (products that already have one are left as they are)."""
        super().init()
        if not table_exists(self.env.cr, OLD_PRODUCT_LIST):
            return
        self.env.cr.execute(f"""
            UPDATE product_template t
               SET analytic_account_id = rel.account_id
              FROM (SELECT p.product_tmpl_id, MIN(r.account_analytic_account_id) AS account_id
                      FROM {OLD_PRODUCT_LIST} r
                      JOIN product_product p ON p.id = r.product_product_id
                     GROUP BY p.product_tmpl_id) rel
             WHERE t.id = rel.product_tmpl_id AND t.analytic_account_id IS NULL
        """)
        self.env.cr.execute("""
            UPDATE product_product p SET analytic_account_id = t.analytic_account_id
              FROM product_template t
             WHERE t.id = p.product_tmpl_id AND p.analytic_account_id IS DISTINCT FROM t.analytic_account_id
        """)
        # copied once: the list is gone from the analytic accounts
        self.env.cr.execute(f"DROP TABLE {OLD_PRODUCT_LIST}")
        self.env.cr.execute("DELETE FROM ir_model_relation WHERE name = %s", [OLD_PRODUCT_LIST])


class ProductProduct(models.Model):
    _inherit = 'product.product'

    analytic_account_id = fields.Many2one(
        related='product_tmpl_id.analytic_account_id', string="Analytic Account", store=True, readonly=False)
