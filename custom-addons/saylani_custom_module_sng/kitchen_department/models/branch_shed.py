from odoo import models, fields, api
from datetime import date, datetime


class KitchenMenu(models.Model):
    _name = 'branch.request'
    _description = 'Branch Request Monthly Cooked Food Menu'

    branch_name = fields.Many2one(
        comodel_name='res.company',
        string='Branch Name',
        default=lambda self: self.env.company.id,
        required=False)

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
        comodel_name='branch.request.line',
        inverse_name='menu_id',
        string='Menu Items',
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('sent', 'Sent to Kitchen')],
        default='draft',
        string='Status',
        copy=False,
    )

    def action_send_to_kitchen(self):
        kitchen_obj = self.env['branch.kitchen.request']
        for record in self:
            if record.state == 'draft':
                kitchen = kitchen_obj.search([('menu_month', '=', record.menu_month)])

                new_lines = []

                for line in record.line_ids:
                    new_lines.append((0, 0, {
                        'date': line.date,
                        'name': line.name.id,
                        'product_id': line.product_id,
                        'branch_name': record.branch_name.id,
                        'quantity': line.quantity,
                    }))

                if kitchen:
                    kitchen.write({
                        'menu_month': record.menu_month,
                        'line_ids': new_lines,
                    })

                else:
                    kitchen_obj.create({
                        'menu_month': record.menu_month,
                        'line_ids': new_lines,

                    })

                record.write({'state': 'sent'})


class KitchenMenuLine(models.Model):
    _name = 'branch.request.line'
    _description = 'Menu Item'

    menu_id = fields.Many2one('branch.request', required=True, ondelete='cascade')

    date = fields.Date(
        string='Date',
        required=False)

    name = fields.Many2one('kitchen.menu', string='Menu Name', required=True)

    product_id = fields.Integer(
        # related='name.id',
        string='Product ID',
        # store=True,
        # readonly=True,
    )

    @api.onchange('name')
    def _onchange_name(self):
        for rec in self:
            # clear existing lines
            if rec.name:
                rec.product_id = rec.name.product_id

    # product_id = fields.Many2one('product.product', string='Dish')

    quantity = fields.Float(
        string='Quantity',
        required=False)
