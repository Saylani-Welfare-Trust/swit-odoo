from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSplitPrice(TransactionCase):
    """One record per animal; the prices add up to the amount paid."""

    def test_rounding_goes_to_the_last_animal(self):
        product = self.env['product.product'].create({'name': 'Goat (split)', 'detailed_type': 'service'})
        source = self.env['res.partner'].create({'name': 'Split source'})
        records = self.env['livestock.slaugther']._create_for_source(
            'donee_id', source, 3, 100.0, {'product_id': product.id})
        self.assertEqual(len(records), 3)
        self.assertEqual(records.mapped('price'), [33.33, 33.33, 33.34])
        self.assertAlmostEqual(sum(records.mapped('price')), 100.0)
        self.assertFalse(self.env['livestock.slaugther']._create_for_source(
            'donee_id', source, 3, 100.0, {'product_id': product.id}), 'run again, nothing more')
