from odoo import models, fields


month_selection = [
    ('jan', 'Januray'),
    ('feb', 'February'),
    ('mar', 'March'),
    ('apr', 'April'),
    ('may', 'May'),
    ('jun', 'June'),
    ('jul', 'July'),
    ('aug', 'Auguest'),
    ('aug', 'August'),
    ('sep', 'September'),
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


    product_tmpl_id = fields.Many2one('product.template', string="Product")

    name = fields.Char(related='product_tmpl_id.name', string="Name")

    month = fields.Selection(selection=month_selection, string="Month")

    state = fields.Selection(selection=state_selection, string="State", default='draft')

    kitchen_menu_line_ids = fields.One2many('kitchen.menu.line', 'kitchen_menu_id', string="Kitchen Menu Lines")


    def _generate_bom(self):
        existing = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', self.product_tmpl_id.id)
        ], limit=1)
        
        if existing:
            self.bom_id = existing.id

        # create new BOM
        bom_vals = {
            'product_tmpl_id': self.product_tmpl_id.id,
            'type': 'phantom',
            'product_qty': 1.0,
            'code': self.product_tmpl_id.default_code or self.product_tmpl_id.name,
        }
        bom = self.env['mrp.bom'].create(bom_vals)

        self.bom_id = bom.id
        
        for line in self.kitchen_menu_line_ids:
            bom.write({'bom_line_ids': [(0, 0, {
                'product_id': line.product_id.id,
                'product_qty': line.quantity,
                'product_uom_id': line.product_id.uom_id.id,
            })]})

    def action_submit(self):
        self.state = 'to_be_approved'

    def action_approve(self):
        self.state = 'approved'
        
        self._generate_bom()