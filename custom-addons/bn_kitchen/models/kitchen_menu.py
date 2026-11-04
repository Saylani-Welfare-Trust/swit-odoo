from odoo import _, models, fields
from odoo.exceptions import UserError


month_selection = [
    ('jan', 'Januray'),
    ('feb', 'February'),
    ('mar', 'March'),
    ('apr', 'April'),
    ('may', 'May'),
    ('jun', 'June'),
    ('jul', 'July'),
    ('aug', 'August'),
    ('sep', 'September'),
    ('oct', 'October'),
    ('nov', 'November'),
    ('dec', 'December'),
]

state_selection = [
    ('draft', 'Draft'),
    ('to_be_approved', 'To Be Approve'),
    ('approved', 'Approved'),
]


class KitchenMenu(models.Model):
    _name = 'kitchen.menu'
    _description = "Kitchen Menu"


    product_tmpl_id = fields.Many2one('product.template', domain=[('is_kitchen', '=', True)], string="Product")

    name = fields.Char(related='product_tmpl_id.name', string="Name")

    month = fields.Selection(selection=month_selection, string="Month")

    state = fields.Selection(selection=state_selection, string="State", default='draft')

    bom_id = fields.Many2one('mrp.bom', string="Bill of Materials", readonly=True, copy=False)

    kitchen_menu_line_ids = fields.One2many('kitchen.menu.line', 'kitchen_menu_id', string="Kitchen Menu Lines")


    def _generate_bom(self):
        """Kit BOM of the menu product from the menu lines (the product's
        existing BOM is updated instead of adding another one)."""
        self.ensure_one()
        lines = [(5, 0, 0)] + [(0, 0, {
            'product_id': line.product_id.id,
            'product_qty': line.quantity,
            'product_uom_id': line.product_id.uom_id.id,
        }) for line in self.kitchen_menu_line_ids]
        bom = self.bom_id or self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', self.product_tmpl_id.id)
        ], limit=1)
        if bom:
            bom.write({'bom_line_ids': lines})
        else:
            bom = self.env['mrp.bom'].create({
                'product_tmpl_id': self.product_tmpl_id.id,
                'type': 'phantom',
                'product_qty': 1.0,
                'code': self.product_tmpl_id.default_code or self.product_tmpl_id.name,
                'bom_line_ids': lines[1:],
            })
        self.bom_id = bom

    def _check_menu_state(self, allowed, action):
        for rec in self:
            if rec.state not in allowed:
                raise UserError(_('"%s" is not possible for menu %s in its current status.') % (action, rec.name))

    def action_submit(self):
        self._check_menu_state(('draft',), _('Submit'))
        for rec in self:
            if not rec.kitchen_menu_line_ids:
                raise UserError(_('Add the items of menu %s first.') % rec.name)
        self.state = 'to_be_approved'

    def action_approve(self):
        self._check_menu_state(('to_be_approved',), _('Approve'))
        for rec in self:
            rec._generate_bom()
        self.state = 'approved'
