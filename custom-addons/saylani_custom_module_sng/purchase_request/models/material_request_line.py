from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MaterialRequestLine(models.Model):
    _name = "material.request.line"
    _description = "Material Request Line"


    purpose = fields.Text(string="Purpose")
    delivery_location = fields.Char(string="Delivery Location")
    priority = fields.Selection(
        [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
        string="Priority",
        default='medium',
        required=True,
    )
    request_id = fields.Many2one(
        comodel_name="material.request",
        string="Material Request",
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        required=True,
    )
    cancelled = fields.Boolean(readonly=True, default=False, copy=False)

    product_qty = fields.Float(
        string="Demand",
        required=True,
        default=1.0,
    )
    description = fields.Text(string="Description")

    date_required = fields.Date(
        string="Request Date",
        required=True,
        tracking=True,
        default=fields.Date.context_today,
    )
    estimated_cost = fields.Monetary(
        currency_field="currency_id",
        default=0.0,
        help="Estimated cost of Purchase Request Line, not propagated to PO.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        related="request_id.company_id",
        string="Company",
        store=True,
    )
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)



    def do_uncancel(self):
        """Actions to perform when uncancelling a purchase request line."""
        self.write({"cancelled": False})

