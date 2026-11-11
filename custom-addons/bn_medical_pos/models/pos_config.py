from odoo import fields, models
from odoo.osv import expression


class PosConfig(models.Model):
    _inherit = 'pos.config'

    is_medical_pos = fields.Boolean(
        string="Medical & Health POS",
        help="Patients (registered donees tagged Medical) are the customers of this POS instead of donors, "
             "and new patients can be registered from its customer screen.",
    )

    def _mh_pos_categories(self):
        """POS categories of the Medical & Health counters: those ticked Medical & Health, with their sub-categories"""
        Category = self.env['pos.category'].sudo()
        medical = Category.search([('mh_medical', '=', True)])
        return Category.search([('id', 'child_of', medical.ids)]) if medical else medical

    def _get_available_product_domain(self):
        domain = super()._get_available_product_domain()
        if not self.is_medical_pos:
            return domain
        categories = self._mh_pos_categories()
        if not categories:
            # no category ticked Medical & Health yet: the counter's own category setting applies
            return domain
        return expression.AND([
            [
                *self.env['product.product']._check_company_domain(self.company_id),
                ('available_in_pos', '=', True),
                ('sale_ok', '=', True),
            ],
            [('pos_categ_ids', 'in', categories.ids)],
        ])
