from odoo import models, fields, api, _
from odoo.exceptions import UserError

class RationIssuanceRequest(models.Model):
    _name = 'ration.issuance.req'
    _description = 'Issuance Request to Warehouse'

    name       = fields.Char(string="Request #", readonly=True, default=lambda self: _('New'))
    date       = fields.Date(default=fields.Date.context_today, required=True)
    center_id  = fields.Many2one('res.partner', string="Distribution Center",)
    line_ids   = fields.One2many('ration.issuance.line', 'req_id', string="Lines")
    state      = fields.Selection([
                    ('draft','Draft'),
                    ('dispatched','Dispatched to Customer'),
                ], default='draft')

    def action_dispatch_to_customer(self):
        """Create an outbound delivery from Distribution to Customer."""
        Picking = self.env['stock.picking']
        Move = self.env['stock.move']

        # 1) Locate your Distribution and Customer locations
        dist_loc = self.env['stock.location'].search([
            ('name', 'ilike', 'Distribution'), ('usage', '=', 'internal')
        ], limit=1)
        cust_loc = self.env['stock.location'].search([
            ('usage', '=', 'customer')
        ], limit=1)

        if not dist_loc or not cust_loc:
            raise UserError(
                "Please ensure you have:\n"
                " • an internal location named 'Distribution'\n"
                " • a customer location (usage='customer')"
            )

        # 2) Find the outgoing picking type for your warehouse
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)], limit=1)
        if not warehouse:
            raise UserError("No warehouse configured for your company.")
        out_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('warehouse_id', '=', warehouse.id)
        ], limit=1)
        if not out_type:
            raise UserError(
                f"No 'Outgoing' picking type found for warehouse '{warehouse.name}'."
            )

        # 3) Create a single picking for this request
        for req in self:
            picking = Picking.create({
                'picking_type_id': out_type.id,
                'location_id': dist_loc.id,
                'location_dest_id': cust_loc.id,
                'scheduled_date': req.date,
                'origin': req.name,
            })

            # 4) Add one move per line→product (qty = line.quantity or 1)
            moves = []
            for line in req.line_ids:
                for prod in line.product:
                    moves.append((0, 0, {
                        'name': prod.display_name,
                        'product_id': prod.id,
                        'product_uom_qty': line.quantity or 1.0,
                        'product_uom': prod.uom_id.id,
                        'location_id': dist_loc.id,
                        'location_dest_id': cust_loc.id,
                    }))
            picking.write({'move_ids_without_package': moves})

            # 5) Confirm, assign and validate to complete the delivery
            picking.action_confirm()
            picking.action_assign()
            if picking.state == 'assigned':
                picking.button_validate()

            # 6) Update state
            req.state = 'dispatched'

        return True






class RationIssuanceLine(models.Model):
    _name = 'ration.issuance.line'
    _description = 'Issuance Request Line'

    req_id     = fields.Many2one('ration.issuance.req', ondelete='cascade')
    product_id = fields.Many2one('product.template', string="Raw Material")
    quantity   = fields.Float(string="Quantity")

    category_id = fields.Many2one('disbursement.category', string="Disbursement Category")
    product = fields.Many2many(
        comodel_name='product.product',
        string='Product',
        required=False)
    donee = fields.Many2one('res.partner', string="Donee")
    name = fields.Char(
        string='Voucher',
        required=False)

    disbursement_type_ids = fields.Many2many('disbursement.type', string="Disbursement Type ID", tracking=True)


