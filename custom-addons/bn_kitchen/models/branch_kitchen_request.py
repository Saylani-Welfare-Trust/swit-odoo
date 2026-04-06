from odoo import models, fields
from odoo.exceptions import ValidationError


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

type_selection = [
    ('daily', 'Daily'),
    ('monthly', 'Monthly'),
]

state_selection = [
    ('draft', 'Draft'),
    ('approve', 'Approve'),
    ('done', 'Done'),
]


class BranchKitchenRequest(models.Model):
    _name = 'branch.kitchen.request'
    _description = "Branch Kitchen Request"


    branch_id = fields.Many2one('stock.location', string="Branch")

    type = fields.Selection(selection=type_selection, string="Type")

    month = fields.Selection(selection=month_selection, string="Month")

    date = fields.Date('Date', default=fields.Date.today())

    name = fields.Char(related='branch_id.name', string="Name")
    year = fields.Char('Year', size=4)

    state = fields.Selection(selection=state_selection, string="State", default='draft')

    mrp_ids = fields.Many2many('mrp.production', string="MRP's")

    is_daily_request = fields.Boolean('Is daily Request')

    branch_kitchen_request_line_ids = fields.One2many('branch.kitchen.request.line', 'branch_kitchen_request_id', string="Branch Kitchen Request Line")
    daily_branch_kitchen_request_line_ids = fields.One2many('daily.branch.kitchen.request.line', 'branch_kitchen_request_id', string="Branch Kitchen Request Line")


    def action_approve(self):
        self.state = 'approve'

    def action_manufacture(self):
        Production = self.env['mrp.production']
        kitchen_loc = self.env['stock.location'].search([('usage', '=', 'internal'), ('name', 'ilike', 'kitchen')], limit=1)
        warehouse_loc = self.env['stock.location'].search([('usage', '=', 'internal'), ('name', 'ilike', 'stock')],limit=1)

        mo_ids = []

        for bn_line in self.branch_kitchen_request_line_ids:
            for line in bn_line.kitchen_menu_line_ids:
                bom = self.env['mrp.bom'].search([
                    '|',
                    ('product_id', '=', line.product_id.id),
                    ('product_tmpl_id', '=', line.product_id.product_tmpl_id.id),
                    ('company_id', '=', self.env.company.id),
                ], order='sequence, product_id', limit=1)
                
                if not bom:
                    raise ValidationError(f"No BOM found for {line.product_id.display_name}")
                
                mo = Production.create({
                    'product_id': line.product_id.id,
                    'product_qty': line.quantity,
                    'product_uom_id': line.product_id.uom_id.id,
                    'bom_id': bom.id,
                    'location_src_id': warehouse_loc.id,
                    'location_dest_id': kitchen_loc.id,
                    'origin': f"Kitchen Request {self.id}",
                })

                # confirm and reserve components
                mo.action_confirm()

                mo_ids.append(mo.id)

        # add all MOs at once
        self.mrp_ids = [(6, 0, mo_ids)]

        self.state = 'done'