from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestKitchenLocation(TransactionCase):
    """Kitchens are the locations marked Is Kitchen Location (a warehouse may hold
    several); each request names its kitchen, never the first location named like
    "kitchen" / "stock"."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['stock.location'].search([('is_kitchen_location', '=', True)]).write({'is_kitchen_location': False})
        Warehouse = cls.env['stock.warehouse']
        cls.wh_a = Warehouse.create({'name': 'KT WH A', 'code': 'KTA'})
        cls.wh_b = Warehouse.create({'name': 'KT WH B', 'code': 'KTB'})

    def _kitchen(self, name, warehouse):
        return self.env['stock.location'].create({'name': name, 'usage': 'internal', 'is_kitchen_location': True,
                                                  'location_id': warehouse.view_location_id.id})

    def test_kitchen_of_the_request(self):
        Request = self.env['branch.kitchen.request']
        self.assertFalse(Request._default_kitchen_location(), "no kitchen yet: chosen by hand")
        kitchen = self._kitchen('KT Kitchen A', self.wh_a)
        self.assertEqual(Request._default_kitchen_location(), kitchen, "the only kitchen")
        self._kitchen('KT Kitchen A2', self.wh_a)
        self.assertFalse(Request._default_kitchen_location(), "a warehouse with two kitchens: chosen")
        request = Request.create({'branch_id': self.wh_b.lot_stock_id.id, 'state': 'approve'})
        with self.assertRaises(UserError):
            request.action_manufacture()
