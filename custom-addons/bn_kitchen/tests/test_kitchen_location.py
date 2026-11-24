from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestKitchenLocation(TransactionCase):
    """Kitchen Production uses the kitchen of the request's Kitchen Warehouse,
    never the first location named like "kitchen" / "stock"."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Warehouse = cls.env['stock.warehouse']
        cls.wh_a = Warehouse.create({'name': 'KT WH A', 'code': 'KTA'})
        cls.wh_b = Warehouse.create({'name': 'KT WH B', 'code': 'KTB'})
        # another warehouses' kitchens must not be the default
        Warehouse.search([('id', 'not in', (cls.wh_a | cls.wh_b).ids)]).write({'kitchen_location_id': False})

    def test_kitchen_per_warehouse(self):
        kitchen_a = self.wh_a._kitchen_location()
        self.assertEqual(kitchen_a.warehouse_id, self.wh_a)
        self.assertEqual(self.wh_a._kitchen_location(), kitchen_a, "made once, kept on the warehouse")
        existing = self.env['stock.location'].create({'name': 'kitchen', 'usage': 'internal',
                                                      'location_id': self.wh_b.view_location_id.id})
        self.assertEqual(self.wh_b._kitchen_location(), existing, "the warehouse's own location named Kitchen")
        with self.assertRaises(ValidationError):
            self.wh_a.kitchen_location_id = existing  # another warehouse's location

    def test_kitchen_warehouse_of_the_request(self):
        Request = self.env['branch.kitchen.request']
        self.assertFalse(Request._default_kitchen_warehouse(), "no kitchen yet: chosen by hand")
        self.wh_a._kitchen_location()
        self.assertEqual(Request._default_kitchen_warehouse(), self.wh_a, "the only kitchen")
        request = Request.create({'branch_id': self.wh_b.lot_stock_id.id, 'state': 'approve'})
        request.kitchen_warehouse_id = False
        with self.assertRaises(UserError):
            request.action_manufacture()
