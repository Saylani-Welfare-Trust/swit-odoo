from odoo import models, fields, api


class ProductMaster(models.Model):
    _name = 'product.master'
    _descripiton = "Product Master"


    product_id = fields.Many2one('product.product', string="Product")

    ref = fields.Char('Ref')
    name = fields.Char('Name', compute="_set_name", store=True)

    product_master_line_ids = fields.One2many('product.master.line', 'product_master_id', string="Product Master Lines")


    @api.depends('product_id')
    def _set_name(self):
        for rec in self:
            rec.name = rec.product_id.name