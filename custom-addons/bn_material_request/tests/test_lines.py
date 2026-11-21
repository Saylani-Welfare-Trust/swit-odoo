from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMaterialRequestLines(TransactionCase):
    """A product is on one line of a request: its quantity is changed instead."""

    def test_one_line_per_product(self):
        product = self.env['product.product'].create({'name': 'MR Paper', 'detailed_type': 'consu'})
        other = self.env['product.product'].create({'name': 'MR Pen', 'detailed_type': 'consu'})
        request = self.env['material.request'].create({
            'line_ids': [(0, 0, {'product_id': product.id, 'quantity': 2})],
        })
        self.assertEqual(request.selected_product_ids, product)
        request.write({'line_ids': [(0, 0, {'product_id': other.id, 'quantity': 1})]})
        self.assertEqual(request.selected_product_ids, product | other)
        with self.assertRaises(ValidationError):
            request.write({'line_ids': [(0, 0, {'product_id': product.id, 'quantity': 5})]})

    def test_products_of_the_allowed_categories(self):
        """The requester's Allowed Categories and their sub-categories."""
        food = self.env['product.category'].create({'name': 'MR Food'})
        rice = self.env['product.category'].create({'name': 'MR Rice', 'parent_id': food.id})
        tools = self.env['product.category'].create({'name': 'MR Tools'})
        self.env.user.allowed_product_category_ids = food
        in_sub = self.env['product.product'].create({'name': 'MR Basmati', 'detailed_type': 'consu', 'categ_id': rice.id})
        outside = self.env['product.product'].create({'name': 'MR Hammer', 'detailed_type': 'consu', 'categ_id': tools.id})
        request = self.env['material.request'].create({'line_ids': [(0, 0, {'product_id': in_sub.id, 'quantity': 1})]})
        self.assertEqual(request.line_ids.product_id, in_sub)
        with self.assertRaises(ValidationError):
            request.write({'line_ids': [(0, 0, {'product_id': outside.id, 'quantity': 1})]})
