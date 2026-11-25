from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


state_selection = [
    ('not_received', 'Not Received'),
    ('received', 'Received')
]


class LivestockCutting(models.Model):
    _name = 'livestock.cutting'
    _description = "Livestock Cutting"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    product_id = fields.Many2one('product.product', string="Product")
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id.id)
    picking_id = fields.Many2one('stock.picking', string="Picking")

    name = fields.Char('Name', default='New')
    code = fields.Char(related='product_id.default_code', string="Product Code", store=True)

    quantity = fields.Integer('Quantity', default=1)

    price = fields.Monetary('Price', currency_field='currency_id', default=0)

    state = fields.Selection(selection=state_selection, string="State", default='not_received')

    is_picking = fields.Boolean('Is Picking')
    # the animal moves from its slaughter location to a cutting location (a warehouse may hold several of each)
    slaughter_location_id = fields.Many2one(
        'stock.location', string='Slaughter Location', domain="[('is_slaughter_location', '=', True)]",
        default=lambda self: self._default_role_location('is_slaughter_location'),
        help="Where the animal was slaughtered (a location marked Is Slaughter Location).")
    cutting_location_id = fields.Many2one(
        'stock.location', string='Cutting Location', domain="[('is_cutting_location', '=', True)]",
        default=lambda self: self._default_role_location('is_cutting_location'),
        help="Where the animal is cut (a location marked Is Cutting Location).")
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Warehouse', compute='_compute_warehouse_id', store=True, readonly=True,
        help="The warehouse of the cutting location.")

    @api.depends('cutting_location_id', 'slaughter_location_id')
    def _compute_warehouse_id(self):
        for record in self:
            record.warehouse_id = (record.cutting_location_id.warehouse_id
                                   or record.slaughter_location_id.warehouse_id or record.warehouse_id)

    @api.onchange('slaughter_location_id')
    def _onchange_slaughter_location_id(self):
        warehouse = self.slaughter_location_id.warehouse_id
        if warehouse and (not self.cutting_location_id or self.cutting_location_id.warehouse_id != warehouse):
            self.cutting_location_id = self.env['stock.location']._single_role_location('is_cutting_location', warehouse)

    @api.model
    def _default_role_location(self, role):
        """The only ``role`` location of the user's Branch / Site warehouse."""
        user = self.env.user
        try:
            warehouse = self.env['stock.warehouse']._warehouse_for(
                branch=user.employee_ids[:1].analytic_account_id, user=user)
        except Exception:
            # several warehouses without a default: the user chooses
            return self.env['stock.location']
        return self.env['stock.location']._single_role_location(role, warehouse)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('livestock_cutting') or ('New')
        return super().create(vals_list)

    def action_confirm(self):
        if self.filtered(lambda r: r.state != 'not_received'):
            raise ValidationError(_('Only cuttings not received yet can be confirmed.'))
        self.write({'state': 'received'})

    def action_validate_picking(self):
        self.ensure_one()
        # once: a second run would create a second cutting material and transfer
        if self.is_picking:
            raise ValidationError(_('The picking of %s is already validated.') % self.name)
        if not self.slaughter_location_id:
            raise ValidationError(_('Please choose the slaughter location of %s.') % self.name)
        if not self.cutting_location_id:
            raise ValidationError(_('Please choose the cutting location of %s.') % self.name)
        product_pro = self.product_id

        cutting_record = self.env['livestock.cutting.material'].create({
            'product_id': self.product_id.id,
            'quantity': self.quantity,
            'price': self.price,
            'code': self.code,
            'cutting_location_id': self.cutting_location_id.id,
        })

        # from the slaughter location into the cutting location
        slaughter_location = self.slaughter_location_id
        cutting_location = self.cutting_location_id
        picking_type = self.env['stock.warehouse']._get_program_type('livestock', cutting_location)

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': slaughter_location.id,
            'location_dest_id': cutting_location.id,
            'origin': self.name or 'Live Stock Slaughter',
            'source_record_ref': '%s,%s' % (self._name, self.id),
        })

        # Create the stock move
        self.env['stock.move'].create({
            'name': product_pro.display_name,
            'product_id': product_pro.id,
            'product_uom_qty': self.quantity,
            'quantity': self.quantity,
            'product_uom': product_pro.uom_id.id,
            'picking_id': picking.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
        })

        # Confirm and assign the picking
        picking.action_confirm()
        picking.action_assign()
        picking.button_validate()

        self.is_picking = True

        return {
            'type': 'ir.actions.act_window',
            'name': 'Cutting Material Record',
            'res_model': 'livestock.cutting.material',
            'res_id': cutting_record.id,
            'view_mode': 'form',
            'target': 'current',
        }