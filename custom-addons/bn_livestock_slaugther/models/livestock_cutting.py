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
    # the warehouse the animal is cut in: its Slaughter Stock and Cutting locations
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Warehouse', default=lambda self: self._default_warehouse(),
        help="The animal moves from this warehouse's Slaughter Stock to its Livestock Cutting location.")

    @api.model
    def _default_warehouse(self):
        user = self.env.user
        branch = user.employee_ids[:1].analytic_account_id
        try:
            return self.env['stock.warehouse']._warehouse_for(branch=branch, user=user)
        except Exception:
            # several warehouses without a default: the user chooses
            return self.env['stock.warehouse']


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
        if not self.warehouse_id:
            raise ValidationError(_('Please choose the warehouse of %s.') % self.name)
        product_pro = self.product_id
        warehouse = self.warehouse_id

        cutting_record = self.env['livestock.cutting.material'].create({
            'product_id': self.product_id.id,
            'quantity': self.quantity,
            'price': self.price,
            'code': self.code,
            'warehouse_id': warehouse.id,
        })

        # within the warehouse: from its Slaughter Stock into its Livestock Cutting location
        slaughter_location = warehouse._livestock_location('slaughter')
        cutting_location = warehouse._livestock_location('cutting')
        picking_type = warehouse._program_type('livestock')

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