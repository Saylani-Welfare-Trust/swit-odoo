from odoo import models, fields


class BranchKitchenRequestLine(models.Model):
    _name = 'branch.kitchen.request.line'
    _descripiton = "Branch Kitchen Request Line"


    branch_kitchen_request_id = fields.Many2one('branch.kitchen.request', string="Branch Kitchen Request")
    kitchen_menu_id = fields.Many2one('kitchen.menu', string="Kitchen Menu")
    
    quantity = fields.Float('Quantity', default=1)