from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDonationHomeServiceLivestock(TransactionCase):
    """The livestock lines of a Donation Home Service come into livestock once it
    is Paid; the POS order or Direct Deposit that pays it makes no second record."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.goat = env['product.product'].create({'name': 'DHS Goat', 'type': 'product'})
        cls.goat.product_tmpl_id.is_livestock = True
        cls.cow = env['product.product'].create({'name': 'DHS Cow', 'type': 'product'})
        cls.cow.product_tmpl_id.is_livestock = True
        cls.rice = env['product.product'].create({'name': 'DHS Rice', 'type': 'product'})
        cls.donor = env['res.partner'].create({'name': 'DHS Donor'})
        cls.pos_location = env['stock.location'].create({'name': 'DHS Shop', 'usage': 'internal'})
        warehouse = env['stock.warehouse'].search([('company_id', '=', env.company.id)], limit=1)
        picking_type = warehouse.out_type_id.copy({'name': 'DHS Shop Orders', 'sequence_code': 'DHSPOS',
                                                   'default_location_src_id': cls.pos_location.id})
        journal = env['account.journal'].create({'name': 'DHS Cash', 'code': 'DHSC', 'type': 'cash'})
        method = env['pos.payment.method'].create({'name': 'DHS Cash', 'journal_id': journal.id})
        cls.config = env['pos.config'].create({'name': 'DHS Shop', 'picking_type_id': picking_type.id,
                                               'payment_method_ids': [(6, 0, method.ids)]})
        cls.session = env['pos.session'].create({'config_id': cls.config.id, 'user_id': env.uid})

    def _service(self, **vals):
        return self.env['donation.home.service'].create(dict({
            'donor_id': self.donor.id, 'state': 'gate_in',
            'donation_home_service_line_ids': [
                (0, 0, {'product_id': self.goat.id, 'quantity': 2, 'amount': 30000}),
                (0, 0, {'product_id': self.rice.id, 'quantity': 5, 'amount': 100}),
            ]}, **vals))

    def _records(self, service):
        return self.env['livestock.slaugther'].search(
            [('dhs_line_id', 'in', service.donation_home_service_line_ids.ids)])

    def test_paid_service_comes_into_livestock(self):
        service = self._service()
        self.assertFalse(self._records(service), "not Paid yet")
        service.state = 'paid'
        records = self._records(service)
        self.assertEqual(len(records), 2, "one record per animal")
        self.assertEqual(records.product_id, self.goat, "only its livestock products")
        self.assertEqual(records.mapped('price'), [30000, 30000])
        self.assertEqual(set(records.mapped('ref')), {service.name})
        self.assertEqual(records.donee_id, self.donor)
        self.assertTrue(records[0].is_goat_depart)
        self.assertEqual(records[0]._livestock_source(), 'dhs')
        service.write({'state': 'paid'})
        self.assertEqual(len(self._records(service)), 2, "Paid again: nothing more")
        cancelled = self._service()
        cancelled.state = 'cancel'
        self.assertFalse(self._records(cancelled), "never Paid: never in livestock")

    def test_pos_order_paying_the_service(self):
        env = self.env
        service = self._service()
        # the POS gives the order the service number as Source Document; the
        # cashier added one more animal of their own
        order = env['pos.order'].create({
            'session_id': self.session.id, 'partner_id': self.donor.id, 'source_document': service.name,
            'amount_tax': 0, 'amount_total': 90500, 'amount_paid': 90500, 'amount_return': 0,
            'lines': [(0, 0, {'product_id': product.id, 'qty': qty, 'price_unit': price,
                              'price_subtotal': price * qty, 'price_subtotal_incl': price * qty})
                      for product, qty, price in ((self.goat, 2, 30000), (self.rice, 5, 100), (self.cow, 1, 30000))]})
        order.write({'state': 'paid'})
        from_order = env['livestock.slaugther'].search([('pos_order_line_id', 'in', order.lines.ids)])
        self.assertEqual(from_order.product_id, self.cow, "the service's goats are not made by the order")
        self.assertEqual(order.source_document, service.name, "the order keeps the service number")
        service._link_pos(order)
        service.state = 'paid'
        records = self._records(service)
        self.assertEqual(len(records), 2)
        self.assertEqual(records.pos_order_id, order)
        self.assertEqual(records[0].source_location_id, self.pos_location, "lands at the POS it was paid at")
        self.assertEqual(records[0].order_date, from_order.order_date)
        order.write({'state': 'done'})
        self.assertEqual(env['livestock.slaugther'].search([('pos_order_line_id', 'in', order.lines.ids)]),
                         from_order, "later writes of the order make no second record")

    def test_location_set_for_the_service(self):
        pen = self.env['stock.location'].create({'name': 'DHS Pen', 'usage': 'internal'})
        self.env['livestock.source.location'].search([('source', '=', 'dhs')]).location_id = pen
        service = self._service(pos_config_id=self.config.id)
        service.state = 'paid'
        self.assertEqual(self._records(service).source_location_id, pen,
                         "Master Setup > Livestock Locations: the location set for Donation Home Service")

    def test_direct_deposit_paying_the_service(self):
        env = self.env
        service = self._service()
        deposit = env['direct.deposit'].create({
            'donor_id': self.donor.id, 'source_model': 'donation_home_service', 'source_record_id': service.id,
            'direct_deposit_line_ids': [(0, 0, {'product_id': self.goat.id, 'quantity': 2, 'amount': 30000})]})
        service.direct_deposit_id = deposit
        deposit._create_livestock_slaughter_records()
        self.assertFalse(env['livestock.slaugther'].search(
            [('direct_deposit_line_id', 'in', deposit.direct_deposit_line_ids.ids)]),
            "the deposit makes none for the service's goats")
        service.state = 'paid'
        self.assertEqual(len(self._records(service)), 2, "the service makes them once Paid")
        # a deposit of its own still makes its animals
        own = env['direct.deposit'].create({
            'donor_id': self.donor.id,
            'direct_deposit_line_ids': [(0, 0, {'product_id': self.goat.id, 'quantity': 1, 'amount': 30000})]})
        own._create_livestock_slaughter_records()
        self.assertEqual(len(env['livestock.slaugther'].search(
            [('direct_deposit_line_id', 'in', own.direct_deposit_line_ids.ids)])), 1)
