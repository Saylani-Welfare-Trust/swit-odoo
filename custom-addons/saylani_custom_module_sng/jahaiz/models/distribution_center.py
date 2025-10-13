from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class distributionJahaizRequest(models.Model):
    _name = 'distribution.request'
    _description = 'distribution Jahaiz (Wedding) Request'

    name = fields.Char(string='Request Reference', required=True, copy=False,
                       default=lambda self: self.env['ir.sequence'].next_by_code('jahaiz.request'))
    donee_id = fields.Many2one('res.partner', string='Donee', required=True)
    date_request = fields.Date(string='Request Date', default=fields.Date.context_today)
    welfare_approved = fields.Boolean(string='Welfare Approved', default=False)

    selection_ids = fields.One2many('distribution.selection', 'request_id', string='Selections')
    slip_date = fields.Date(string='Delivery Date', readonly=True)
    slip_location = fields.Char(string='Delivery Location', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Welfare Approved'),
        ('selected', 'Items Selected'),
        ('pr', 'Purchase Requisition'),
        ('po', 'Purchase Order'),
        ('grn', 'Received'),
        ('done', 'Delivered')], default='draft', string='Status', copy=False)

    location = fields.Text(
        string="Location",
        required=False)

    lead_time = fields.Integer(
        string='Lead Time (days)',
        default=7,
        help="Number of days from request to delivery",
    )

    date_of_delivery = fields.Date(
        string='Date of Delivery',
        compute='_compute_date_of_delivery',
        store=True,
    )

    delivery_instruction = fields.Text(
        string="Delivery Instructions",
        required=False)

    purchase_req_id = fields.Many2one(
        comodel_name='purchase.request',
        string='Purchase_req_id',
        required=False)

    @api.depends('date_request', 'lead_time')
    def _compute_date_of_delivery(self):
        for rec in self:
            if rec.date_request is not False and rec.lead_time is not False:
                rec.date_of_delivery = rec.date_request + relativedelta(days=rec.lead_time)
            else:
                rec.date_of_delivery = False

    def action_issue_pr22(self):
        """Issue a Purchase Requisition to Supply Chain Dept for all distribution lines."""
        self.ensure_one()


        # 1) Build the requisition lines from your distribution.selection records
        requisition_lines = []
        for line in self.selection_ids:
            requisition_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'product_qty': line.qty,
                'qty_ordered': line.qty,
                # Optionally set a UoM, delivery date, analytic account, etc.
                # 'product_uom': line.product_id.uom_id.id,
                # 'date_planned': self.date_of_delivery,
            }))

        # 2) Create the Purchase Requisition
        pr = self.env['purchase.requisition'].create({
            'name': f"{self.name}/PR",
            'schedule_date': self.date_of_delivery,
            'line_ids': requisition_lines,
            'origin': self.name,
        })

        # 3) Move the distribution request into the 'pr' state
        self.state = 'pr'

        # Optionally, log a chatter message for traceability
        pr.message_post(body=f"Issued from Distribution Request {self.name}")

        return {
            'name': "Purchase Requisition",
            'view_mode': 'form,tree',
            'res_model': 'purchase.requisition',
            'res_id': pr.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def action_issue_pr(self):
        """Issue a Purchase Request to Supply Chain Dept for all distribution lines."""
        self.ensure_one()

        PurchaseRequest = self.env['purchase.request']
        PurchaseRequestLine = self.env['purchase.request.line']

        if not self.selection_ids:
            raise UserError("No distribution lines found to create a Purchase Request.")

        # 1. Create the Purchase Request (without line_ids)
        pr = PurchaseRequest.create({
            'origin': self.name,
            'requested_by': self.env.user.id,
            'date_start': fields.Date.today(),
            'description': f"Generated from Distribution Request {self.name}",
            # Do NOT assign 'line_ids': []
        })

        # 2. Add lines to the Purchase Request using create
        for line in self.selection_ids:
            PurchaseRequestLine.create({
                'request_id': pr.id,
                'product_id': line.product_id.id,
                'product_qty': line.qty,
                'qty_done': 0,
                'product_uom_id': line.product_id.uom_id.id,
                'date_required': self.date_of_delivery,
                # 'analytic_account_id': getattr(line, 'analytic_account_id',
                #                                False) and line.analytic_account_id.id or False,
            })

        # 3. Update state and log message
        self.state = 'pr'
        self.purchase_req_id = pr.id
        pr.message_post(body=f"Issued from Distribution Request {self.name}")

        return {
            'name': "Purchase Request",
            'view_mode': 'form',
            'res_model': 'purchase.request',
            'res_id': pr.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def action_receive_grn22(self):
        """Validate the incoming shipment (GRN) linked to this request."""
        self.ensure_one()
        # Find the purchase orders created in action_issue_pr
        po = self.env['purchase.order'].search([
            # ('origin', '=', f"{self.name}/PR"),
            ('origin', '=', self.purchase_req_id.name),

            ('state', 'in', ['purchase', 'done'])
        ], limit=1)
        if not po:
            raise UserError("No confirmed Purchase Order found for GRN.")
        # Find the incoming picking(s) for that PO
        pickings = po.picking_ids.filtered(lambda p: p.picking_type_code == 'incoming' and p.state == 'assigned')
        if not pickings:
            raise UserError("No incoming shipment to receive.")
        # Validate each picking to record the GRN
        for pick in pickings:
            pick.button_validate()
        # Move state to 'grn' so we know receipt is done
        self.state = 'grn'

    def action_receive_grn(self):
        self.ensure_one()

        print("=== STARTING GRN PROCESS ===")
        print(f"Current record: {self.name}")
        print(f"Linked Purchase Request: {self.purchase_req_id.name}")

        # Step 1: Get PR lines
        pr_lines = self.purchase_req_id.line_ids
        print(f"PR Line IDs: {pr_lines.ids}")

        # Step 2: Find related Purchase Order Lines
        po_lines = self.env['purchase.order.line'].search([
            ('request_line_id', 'in', pr_lines.ids)
        ])
        print(f"Found PO Line IDs: {po_lines.ids}")

        # Step 3: Get PO(s)
        pos = po_lines.mapped('order_id').filtered(lambda po: po.state in ['purchase', 'done'])
        print(f"Found PO IDs: {pos.ids}")

        if not pos:
            print("❌ No confirmed Purchase Order found.")
            raise UserError("No confirmed Purchase Order found for GRN.")

        # Step 4: Find incoming pickings
        pickings = pos.mapped('picking_ids').filtered(
            lambda p: p.picking_type_code == 'incoming' and p.state == 'assigned'
        )
        print(f"Found Picking IDs: {pickings.ids}")

        if not pickings:
            print("❌ No incoming shipment to receive.")
            raise UserError("No incoming shipment to receive.")

        # Step 5: Validate each picking
        for pick in pickings:
            print(f"✅ Validating Picking ID: {pick.id}")
            pick.button_validate()

        self.state = 'grn'
        print("✅ GRN process completed and state updated to 'grn'")
        return True

    # ---------------------------------------------------
    # 10. On Due Date, Issue Delivery Note for Distribution
    # ---------------------------------------------------
    def action_issue_delivery_note(self):
        """Manually create and confirm the outgoing Delivery Note."""
        self.ensure_one()

        warehouse_loc = self.env['stock.location'].search([
            ('name', 'ilike', 'warehouse'),
            ('usage', '=', 'internal'),
        ], limit=1)
        # if self.state != 'grn':
        #     raise UserError("You can only issue a Delivery Note after GRN is done.")
        # Build the outgo
        # ing picking
        picking = self.env['stock.picking'].create({
            'origin': self.name,
            'partner_id': self.donee_id.id,
            'picking_type_id': self.env.ref('stock.picking_type_out').id,
            'location_id': warehouse_loc.id,
            'location_dest_id': self.donee_id.property_stock_customer.id,
            'move_ids': [
                (0, 0, {
                    'name': line.product_id.display_name,  # << mandatory

                    'product_id': line.product_id.id,
                    'product_uom_qty': line.qty,
                    'quantity': line.qty,
                    'product_uom': line.product_id.uom_id.id,
                    # set the source again for the move:
                    'location_id': warehouse_loc.id,
                    'location_dest_id': self.donee_id.property_stock_customer.id,
                })
                for line in self.selection_ids
            ],
        })
        # Confirm so the Delivery Note is generated
        picking.action_confirm()

        if picking.state == 'assigned':
            picking.button_validate()
        # Optionally, you could reserve stock immediately:
        # picking.action_assign()
        # self.state = 'delivery_ready'
        return {
            'name':        "Delivery Note",
            'view_mode':   'form',
            'res_model':   'stock.picking',
            'res_id':      picking.id,
            'type':        'ir.actions.act_window',
        }

    @api.model
    def _cron_auto_issue_delivery(self):
        """Scheduled daily: if due date reached, auto-issue delivery note."""
        today = fields.Date.context_today(self)
        requests = self.search([
            ('state', '=', 'grn'),
            ('date_of_delivery', '<=', today)
        ])
        for req in requests:
            req.action_issue_delivery_note()




class distributionJahaizSelection(models.Model):
    _name = 'distribution.selection'
    _description = 'distribution Selected Wedding Item'
    request_id = fields.Many2one('distribution.request', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Item', required=True)

    qty = fields.Float(string='Quantity', default=1.0)

