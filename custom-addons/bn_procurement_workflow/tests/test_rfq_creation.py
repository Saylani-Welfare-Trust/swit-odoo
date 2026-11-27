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
        # once assigned, only these employees select a request's vendors
        cls.officer = cls.env['hr.employee'].create({'name': 'RFQ Officer', 'user_id': cls.env.user.id})
        other_user = cls.env['res.users'].create({'name': 'Other RFQ Officer', 'login': 'other_rfq_officer'})
        cls.other_officer = cls.env['hr.employee'].create({'name': 'Other RFQ Officer', 'user_id': other_user.id})

    def _request(self, state, assignees=None):
        request = self.env['purchase.requisition'].create({
            'line_ids': [(0, 0, {'product_id': self.rice.id, 'product_qty': 5}),
                         (0, 0, {'product_id': self.oil.id, 'product_qty': 3})],
            'assigned_employee_ids': [(6, 0, assignees.ids)] if assignees else [],
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

    def test_only_assigned_officers_select_vendors(self):
        request = self._request('procurement_approval')
        self.assertTrue(request.is_rfq_creator_allowed, "anyone, until someone is assigned")

        request.assigned_employee_ids = self.other_officer
        self.assertFalse(request.is_rfq_creator_allowed, "assigned to someone else")
        with self.assertRaises(ValidationError):
            self._wizard(request).action_create_rfqs()

        request.assigned_employee_ids |= self.officer
        self.assertTrue(request.is_rfq_creator_allowed, "one of several assigned officers")
        self.assertEqual(request.assigned_user_ids, self.env.user | self.other_officer.user_id)
        self.assertEqual(request.assigned_by_id, self.env.user)
        wizard = self._wizard(request)
        wizard.action_create_rfqs()
        self.assertTrue(request.purchase_ids)

    def test_other_requests_only_when_assigned(self):
        request = self._request('procurement_approval', assignees=self.officer)
        unassigned = self._request('procurement_approval')
        other = self._request('procurement_approval', assignees=self.other_officer)
        offered = self._wizard(request).procurement_line_ids.requisition_line_id.requisition_id
        self.assertIn(unassigned, offered)
        self.assertNotIn(other, offered, "its vendors are for the other officer to select")
        other.assigned_employee_ids |= self.officer
        offered = self._wizard(request).procurement_line_ids.requisition_line_id.requisition_id
        self.assertIn(other, offered)
