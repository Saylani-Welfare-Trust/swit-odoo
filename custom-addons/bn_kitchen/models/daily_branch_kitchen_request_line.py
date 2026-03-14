from odoo import models, fields


class DailyBranchKitchenRequestLine(models.Model):
    _name = 'daily.branch.kitchen.request.line'
    _descripiton = "Daily Branch Kitchen Request Line"


    branch_kitchen_request_id = fields.Many2one('branch.kitchen.request', string="Branch Kitchen Request")
    kitchen_menu_id = fields.Many2one('kitchen.menu', string="Kitchen Menu")
    
    quantity = fields.Float('Quantity', default=1)