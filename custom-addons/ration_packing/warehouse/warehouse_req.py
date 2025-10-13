from odoo import models, fields, api, _
from odoo.exceptions import UserError

class warehouseRationIssuanceRequest(models.Model):
    _name = 'warehouse.issuance.req'
    _description = 'warehouse Issuance Request to Warehouse'

    name       = fields.Char(string="Request #", readonly=True, default=lambda self: _('New'))
    date       = fields.Date(default=fields.Date.context_today, required=True)
    center_id  = fields.Many2one('res.partner', string="Distribution Center", required=True)
    line_ids   = fields.One2many('warehouse.issuance.line', 'req_id', string="Lines")
    state      = fields.Selection([
                    ('draft','Draft'),
                    ('requested','Requested'),
                    ('done','Done'),
                ], default='draft')

    res_id = fields.Char(
        string='Res_id',
        required=False)

    def create_internal_transfer(self):
        Warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        Picking = self.env['stock.picking']
        Move = self.env['stock.move']



        # 1. Find or define your internal transfer type
        pick_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id', '=', Warehouse.id),
        ], limit=1)
        if not pick_type:
            raise UserError(_("No internal transfer operation type for %s") % Warehouse.name)

        # 2. Lookup your custom locations by name (or XML ID)
        src = self.env['stock.location'].search([('name', '=', 'Warehouse')], limit=1)
        dst = self.env['stock.location'].search([('name', '=', 'Ration Packing')], limit=1)
        if not src or not dst:
            raise UserError(_("Please configure both 'Warehouse' and 'Ration Packing' locations."))

        # 3. Create and populate the picking
        picking = Picking.create({
            'picking_type_id': pick_type.id,
            'location_id': src.id,
            'location_dest_id': dst.id,
            'origin': self.name,
        })
        for line in self.line_ids:
            Move.create({
                'picking_id': picking.id,
                'product_id': line.product_id.id,
                'name': line.product_id.display_name,
                'product_uom_qty': line.quantity,
                'product_uom': line.product_id.uom_id.id,
                'location_id': src.id,
                'location_dest_id': dst.id,
            })

        # 4. Confirm & assign
        picking.action_confirm()
        picking.action_assign()
        picking.button_validate()  # calls action_done -> moves stock on‐hand


        packing_dept = self.env['ration.issuance.req'].browse(self.res_id)

        packing_dept.write({
            'state': 'received'
        })

        self.state = 'requested'

    def create_internal_transfer22(self):
        """For each pack request line, fetch its ingredients and move stock."""
        Warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)], limit=1
        )  # find company warehouse :contentReference[oaicite:0]{index=0}
        if not Warehouse:
            raise UserError(_("No Warehouse configured for company %s") % self.env.company.name)

        # 1) Locate or error on transfer type
        PickType = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id', '=', Warehouse.id),
        ], limit=1)  # internal transfers :contentReference[oaicite:1]{index=1}
        if not PickType:
            raise UserError(_("No Internal Transfer type for warehouse %s") % Warehouse.name)

        # 2) Find custom locations
        Loc = self.env['stock.location']
        src = Loc.search([('name', '=', 'Warehouse')], limit=1)
        dst = Loc.search([('name', '=', 'Ration Packing')], limit=1)
        if not src or not dst:
            raise UserError(_("Configure both 'Warehouse' and 'Ration Packing' locations."))

        # 3) Aggregate required raw ingredients
        ingredient_qty = {}
        for req in self:
            for pack_req in req.line_ids:
                # find the pack category record
                pack_cat = self.env['ration.pack.category'].browse(pack_req.product_id.id)

                print('pack_req.product_id.id', pack_req.product_id.id)
                # read its ingredient lines
                for pl in pack_cat.pack_line_ids:  # ration.pack.line :contentReference[oaicite:2]{index=2}
                    # compute total = packs * qty per pack
                    total = pack_req.quantity * pl.quantity
                    ingredient_qty.setdefault(pl.product_id.id, 0.0)
                    ingredient_qty[pl.product_id.id] += total

                    print('pl.product_id.id', pl.product_id.id)

        if not ingredient_qty:
            raise UserError(_("No ingredients to transfer."))

        # 4) Build the picking
        Picking = self.env['stock.picking']
        Move = self.env['stock.move']
        picking = Picking.create({
            'picking_type_id': PickType.id,
            'location_id': src.id,
            'location_dest_id': dst.id,
            'origin': self.name,
        })  # create internal transfer :contentReference[oaicite:3]{index=3}

        # 5) Create stock moves
        for prod_id, qty in ingredient_qty.items():
            Move.create({
                'picking_id': picking.id,
                'product_id': prod_id,
                'name': self.env['product.product'].browse(prod_id).display_name,
                'product_uom_qty': qty,
                'product_uom': self.env['product.product'].browse(prod_id).uom_id.id,
                'location_id': src.id,
                'location_dest_id': dst.id,
            })  # stock.move.create :contentReference[oaicite:4]{index=4}

        # 6) Confirm, assign, and validate (deduct stock)
        picking.action_confirm()  # state → Ready :contentReference[oaicite:5]{index=5}
        picking.action_assign()  # reserve stock :contentReference[oaicite:6]{index=6}
        picking.button_validate()  # apply moves → Done :contentReference[oaicite:7]{index=7}

        # 7) Update request state
        self.state = 'requested'
        return True


class RationIssuanceLine(models.Model):
    _name = 'warehouse.issuance.line'
    _description = 'Issuance Request Line'

    req_id     = fields.Many2one('warehouse.issuance.req', ondelete='cascade')
    product_id = fields.Many2one('product.template', string="Raw Material", required=True)
    quantity   = fields.Float(string="Quantity", required=True)
