from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRfqCreation(TransactionCase):
    """RFQs are created in Procurement Manager Approval (first batch) and, for the
    products not on an RFQ yet, from RFQ Sent on - as the request's buttons show."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rice = cls.env['product.product'].create({'name': 'RFQ Rice', 'detailed_type': 'consu'})
        cls.oil = cls.env['product.product'].create({'name': 'RFQ Oil', 'detailed_type': 'consu'})
        cls.vendor = cls.env['res.partner'].create({'name': 'RFQ Vendor'})

    def _request(self, state):
        request = self.env['purchase.requisition'].create({
            'line_ids': [(0, 0, {'product_id': self.rice.id, 'product_qty': 5}),
                         (0, 0, {'product_id': self.oil.id, 'product_qty': 3})],
        })
        request.state = state
        return request

    def _wizard(self, request):
        return self.env['vendor.selection.wizard'].with_context(
            active_id=request.id, active_model='purchase.requisition',
            default_source_requisition_id=request.id).create({'vendor_ids': [(6, 0, self.vendor.ids)]})

    def test_first_batch_in_procurement_approval(self):
        request = self._request('procurement_approval')
        self.assertTrue(request._can_create_rfqs())
        wizard = self._wizard(request)
        self.assertTrue(wizard.source_line_ids)
        wizard.source_line_ids.write({'selected': True})
        wizard.action_create_rfqs()
        self.assertTrue(request.purchase_ids.filtered(lambda po: po.partner_id == self.vendor))

    def test_remaining_products_after_rfq_sent(self):
        request = self._request('rfq_sent')
        self.assertTrue(request.has_lines_to_rfq)
        self.assertTrue(request._can_create_rfqs(), "products not on an RFQ yet")
        # every line on an RFQ: nothing left to create
        rfq = self.env['purchase.order'].create({
            'partner_id': self.vendor.id, 'requisition_id': request.id,
            'order_line': [(0, 0, {'product_id': line.product_id.id, 'product_qty': line.product_qty, 'price_unit': 1})
                           for line in request.line_ids]})
        for line in request.line_ids:
            line._lock_quantity(line.product_qty, rfq)
        request.invalidate_recordset(['has_lines_to_rfq'])
        self.assertFalse(request.has_lines_to_rfq)
        self.assertFalse(request._can_create_rfqs())

    def test_refused_when_closed(self):
        request = self._request('cancel')
        self.assertFalse(request._can_create_rfqs())
        with self.assertRaises(ValidationError):
            request.action_create_multi_vendor_rfqs()
        wizard = self._wizard(self._request('procurement_approval'))
        wizard.source_requisition_id.state = 'cancel'
        with self.assertRaises(ValidationError):
            wizard.action_create_rfqs()
