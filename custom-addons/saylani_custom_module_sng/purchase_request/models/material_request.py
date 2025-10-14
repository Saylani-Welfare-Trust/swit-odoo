from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MaterialRequest(models.Model):
    _name = "material.request"
    _description = "Material Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    @api.model
    def _company_get(self):
        return self.env["res.company"].browse(self.env.company.id)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('material.request') or 'New'
        return super(MaterialRequest, self).create(vals)

    @api.model
    def _default_picking_type(self):
        type_obj = self.env["stock.picking.type"]
        company_id = self.env.context.get("company_id") or self.env.company.id
        types = type_obj.search(
            [("code", "=", "incoming"), ("warehouse_id.company_id", "=", company_id)]
        )
        if not types:
            types = type_obj.search(
                [("code", "=", "incoming"), ("warehouse_id", "=", False)]
            )
        return types[:1]

    name = fields.Char(
        string="Request Number",
        required=True,
        default=lambda self: _("New"),
        tracking=True,
    )
    date_start = fields.Date(
        string="Creation Date",
        default=fields.Date.context_today,
        tracking=True,
    )
    requested_by = fields.Many2one(
        comodel_name="res.users",
        string="Requested By",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    origin = fields.Char(string="Source Document")
    description = fields.Text()
    group_id = fields.Many2one(
        comodel_name="procurement.group",
        string="Procurement Group",
        copy=False,
        index=True,
    )

    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("to_approve", "To Be Approved"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("done", "Done"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )

    picking_type_id = fields.Many2one(
        comodel_name="stock.picking.type",
        string="Picking Type",
        required=True,
        default=_default_picking_type,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=False,
        default=_company_get,
        tracking=True,
    )
    department_id = fields.Many2one(
        comodel_name="hr.department",
        string="User Department",
        required=True,
        default=lambda self: self.env.user.employee_id.department_id,
        tracking=True,
    )


    uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unit of Measure",
        required=True,
    )
    analytical_tag_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Analytical Tag",
    )

    line_ids = fields.One2many(
        comodel_name="material.request.line",
        inverse_name="request_id",
        string="Material Lines",
        tracking=True,
    )

    to_approve_allowed = fields.Boolean(
        string="To Approve Allowed", compute="_compute_to_approve_allowed", store=True
    )
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    estimated_cost = fields.Monetary(
        compute="_compute_estimated_cost",
        string="Total Estimated Cost",
        store=True,
    )

    @api.depends("line_ids", "line_ids.estimated_cost")
    def _compute_estimated_cost(self):
        for rec in self:
            rec.estimated_cost = sum(rec.line_ids.mapped("estimated_cost"))

    def button_draft(self):
        self.mapped("line_ids").do_uncancel()
        return self.write({"state": "draft"})

    def button_to_approve(self):
        self.to_approve_allowed_check()
        return self.write({"state": "to_approve"})

    @api.depends("state", "line_ids.product_qty", "line_ids.cancelled")
    def _compute_to_approve_allowed(self):
        for rec in self:
            rec.to_approve_allowed = rec.state == "draft" and any(
                not line.cancelled and line.product_qty for line in rec.line_ids
            )

    def to_approve_allowed_check(self):
        for rec in self:
            if not rec.to_approve_allowed:
                raise UserError(
                    _(
                        "You can't request an approval for a purchase request "
                        "which is empty. (%s)"
                    )
                    % rec.name
                )


    # def button_done(self):
    #     return self.write({"state": "done"})

    def button_done(self):
        purchase_request_lines = self.env['material.request.line'].search([('request_id', '=', self.id)])

        if not purchase_request_lines:
            raise UserError("No purchase request lines found.")

        move_lines = []
        for line in purchase_request_lines:
            move = self.env['stock.move'].create({
                'name': line.product_id.name,
                'product_id': line.product_id.id,
                'product_uom': line.product_id.uom_id.id,
                'product_uom_qty': line.product_qty,
                'location_id': self.env.ref('stock.stock_location_stock').id,
                'location_dest_id': self.env.ref('stock.stock_location_customers').id,
                'state': 'draft',
            })
            move_lines.append(move)

        stock_picking_vals = {
            'picking_type_id': self.env.ref('stock.picking_type_in').id,
            'origin': self.name,
            'location_id': self.env.ref('stock.stock_location_stock').id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'move_ids': [(6, 0, [move.id for move in move_lines])],
        }

        stock_picking = self.env['stock.picking'].create(stock_picking_vals)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': stock_picking.id,
            'view_mode': 'form',
            'target': 'current',
        }


    def button_approved(self):
        self.write({"state": "approved"})

    def button_rejected(self):
        self.write({"state": "rejected"})

    def unlink(self):
        for request in self:
            if request.state != "draft":
                raise UserError("You can only delete draft requests.")
        return super(MaterialRequest, self).unlink()

#     name = fields.Char(string="Vendor Name", required=True)
#     cell_number = fields.Char(string="Cell Number")
#     email = fields.Char(string="Email Address")
#     cnic_ntn = fields.Char(string="CNIC/NTN Number")
#     contact_person = fields.Char(string="Contact Person")
#     office_contact_number = fields.Char(string="Office Contact Number")
#     registered_office_address = fields.Text(string="Registered Office Address")
#     payment_terms = fields.Selection([
#         ('immediate', 'Immediate'),
#         ('15_days', '15 Days'),
#         ('30_days', '30 Days'),
#         ('60_days', '60 Days')
#     ], string="Payment Terms", default='immediate')
#     bank_details = fields.Char(string="Bank Details")
#     preferred_payment_mode = fields.Selection([
#         ('cheque', 'Cheque'),
#         ('bank_transfer', 'Bank Transfer'),
#         ('cash', 'Cash')
#     ], string="Preferred Payment Mode", default='cheque')
#     vendor_category = fields.Selection([
#         ('livestock', 'Livestock Vendors'),
#         ('food_ration', 'Food & Ration Vendors'),
#         ('medical', 'Medicines & Medical Equipment'),
#         ('contractors', 'Service Providers / Contractors'),
#         ('others', 'Others'),
#         ('capex', 'CAPEX Vendors')
#     ], string="Vendor Category", required=True)
#     gl_account = fields.Char(string="GL Account (Control Account)")
#
#     state = fields.Selection([
#         ('draft', 'Draft'),
#         ('hod_approval', 'HOD Approval'),
#         ('store_processing', 'Store Processing'),
#         ('finished', 'Finished')
#     ], default='draft', string="Status")
#     line_ids = fields.One2many('material.request.line', 'request_id', string="Request Lines")
#
#     def action_submit(self):
#         """Submit for HOD Approval"""
#         self.state = 'hod_approval'
#
#     def action_hod_approve(self):
#         """HOD Approval"""
#         self.state = 'store_processing'
#
#     def action_check_inventory(self):
#         """Check Inventory Availability"""
#         for line in self.line_ids:
#             product = self.env['stock.quant'].search(
#                 [('product_id', '=', line.product_id.id), ('quantity', '>=', line.quantity)], limit=1)
#             if not product:
#                 raise UserError(_(f"Product '{line.product_id.name}' is not available in inventory."))
#         self.state = 'finished'
#
#
# class MaterialRequestLine(models.Model):
#     _name = 'material.request.line'
#     _description = 'Material Request Line'
#
#     request_id = fields.Many2one('material.request', string="Material Request", required=True)
#     product_id = fields.Many2one('product.product', string="Product", required=True)
#     quantity = fields.Float(string="Quantity", required=True)
