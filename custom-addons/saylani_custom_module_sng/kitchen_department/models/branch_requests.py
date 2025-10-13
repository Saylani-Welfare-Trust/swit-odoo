from odoo import models, fields, api
from datetime import date, datetime


class branch_request_for_kitchen(models.Model):
    _name = 'branch.kitchen.request'
    _description = 'Branch Request Monthly Cooked Food Menu'

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
        comodel_name='branch.kitchen.request.line',
        inverse_name='menu_id',
        string='Menu Items',
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('sent', 'Sent to Kitchen')],
        default='draft',
        string='Status',
        copy=False,
    )

    mr_id = fields.Many2one('kitchen.material.requisition', string='Material Requisition')

    def action_execute_daily_requirement(self):
        """Create daily kitchen request lines based on the selected date in branch.kitchen.request.line"""
        self.ensure_one()

        DailyRequest = self.env['kitchen.daily.request']
        DailyRequestLine = self.env['kitchen.daily.request.line']

        for line in self.line_ids:
            if line.date:
                daily_request = DailyRequest.create({
                    'date': line.date,
                    'branch_id': line.branch_name.id,
                    'request_line_ids': [(0, 0, {
                        'product_id': line.product_id,
                        'quantity': line.quantity,
                        'menu_name_id': line.name.id,
                    })],
                })

    def action_issue_mr(self):
        self.ensure_one()
        # Create the requisition header
        mr = self.env['kitchen.material.requisition'].create({
            'request_id': self.id,
            'line_ids': [
                (0, 0, {
                    'product_id': line.product_id,
                    'branch_name': line.branch_name.id,
                    'quantity': line.quantity,
                    # 'uom_id': line.product_id.uom_id.id,
                })
                for line in self.line_ids
            ],
        })
        self.write({'state': 'sent', 'mr_id': mr.id})
        mr._process_requisition()


class KitchenMenuLine(models.Model):
    _name = 'branch.kitchen.request.line'
    _description = 'Menu Item'

    menu_id = fields.Many2one('branch.kitchen.request', required=True, ondelete='cascade')

    date = fields.Date(
        string='Date',
        required=False)

    name = fields.Many2one('kitchen.menu', string='Menu Name')



    product_id = fields.Integer(
        # related='name.id',
        string='Product ID',
        store=True,
        # readonly=True,
    )
    # product_id = fields.Many2one('product.product', string='Dish')

    branch_name = fields.Many2one(
        comodel_name='res.company',
        string='Branch Name',
        required=False)

    quantity = fields.Float(
        string='Quantity',
        required=False)
