from odoo import models, fields


class ProductCategory(models.Model):
    _inherit = 'product.category'

    technical_department_id = fields.Many2one(
        'hr.department', string='Technical Department',
        help='The manager of this department is the Technical HOD approving material requests for products of this category. '
             'Sub-categories without a department use their parent\'s.')

    def _get_technical_department(self):
        self.ensure_one()
        category = self
        while category:
            if category.technical_department_id:
                return category.technical_department_id
            category = category.parent_id
        return self.env['hr.department']
