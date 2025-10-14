from odoo import models, fields, api
from datetime import date, datetime


class KitchenMenu(models.Model):
    _name = 'kitchen.menu'
    _description = 'Monthly Cooked Food Menu'

    name = fields.Many2one( 'product.product',string='Menu Name', required=True)

    product_id = fields.Integer(
        related='name.id',
        string='Product ID',
        store=True,
        readonly=True,
    )

    MONTHS = [
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
    ]

    # store as string keys '1'..'12'; default to current month
    menu_month = fields.Selection(
        selection=MONTHS,
        string='Menu For Month',
        required=True,
        default=lambda self: str(datetime.now().month),
    )

    line_ids = fields.One2many(
        comodel_name='kitchen.menu.line',
        inverse_name='menu_id',
        string='Menu Items',
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('to_approve', 'To Approve'), ('approved', 'Approved')],
        default='draft',
        string='Status',
        copy=False,
    )

    bom_id = fields.Integer(
        string='Bom_id',
        required=False)

    bom_product_id = fields.Integer(
        string='bom_product_id',
        required=False)



    def _generate_bom(self):
        for menu in self:
            # check if BOM exists
            existing = self.env['mrp.bom'].search([
                ('product_tmpl_id', '=', menu.name.id)
            ], limit=1)
            if existing:
                menu.bom_id = existing.id
                menu.bom_product_id = existing.product_tmpl_id.id
                continue
            # create new BOM
            bom_vals = {
                'product_tmpl_id': menu.name.id,
                'type': 'phantom',
                'product_qty': 1.0,
                'code': menu.name.default_code or menu.name.name,
            }
            bom = self.env['mrp.bom'].create(bom_vals)

            menu.bom_id = bom.id
            for ing in menu.line_ids:
                bom.write({'bom_line_ids': [(0, 0, {
                    'product_id': ing.product_id.id,
                    'product_qty': ing.quantity,
                    'product_uom_id': ing.product_id.uom_id.id,
                })]})

    # @api.model
    # def _check_menu_deadline(self):
    #     today = date.today()
    #     if today.day > 20:
    #         overdue = self.search([('state', '=', 'draft'),
    #                                ('menu_date', '=', today.replace(day=1))])
    #         for rec in overdue:
    #             rec.message_post(
    #                 body="⚠️ Menu not prepared by the 20th.")

    def action_submit(self):
        self.write({'state': 'to_approve'})
        # self._send_approval_email()

    def action_approve(self):
        self.write({'state': 'approved'})
        self._generate_bom()

    def _send_approval_email(self):
        template = self.env.ref('kitchen_department.email_template_menu_approval')
        template.send_mail(self.id, force_send=True)



class KitchenMenuLine(models.Model):
    _name = 'kitchen.menu.line'
    _description = 'Menu Item'

    menu_id = fields.Many2one('kitchen.menu', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Dish', required=True)

    quantity = fields.Float(
        string='Quantity',
        required=False)
    ingredient_ids = fields.One2many(
        comodel_name='kitchen.menu.line.ingredient',
        inverse_name='line_id',
        string='Ingredients',
    )

    ingredient_count = fields.Integer(
        string='Ingredient Count',
        compute='_compute_ingredient_count',
        store=True)

    @api.depends('ingredient_ids')
    def _compute_ingredient_count(self):
        for line in self:
            line.ingredient_count = len(line.ingredient_ids)

class KitchenMenuLineIngredient(models.Model):
    _name = 'kitchen.menu.line.ingredient'
    _description = 'Ingredient for Menu Item'

    line_id = fields.Many2one('kitchen.menu.line', required=True, ondelete='cascade')
    ingredient_id = fields.Many2one('product.product', string='Ingredient', required=True)
    percentage = fields.Float(
        string='Percentage',
        digits=(12, 2),
        help='% of this ingredient in the recipe',
        required=True,
    )




