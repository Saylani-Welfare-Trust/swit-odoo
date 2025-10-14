from odoo import api, fields, models,_
from odoo.exceptions import UserError

class PosOrder(models.Model):
    _inherit = 'pos.order'

    medical_equipment = fields.Boolean(string='Medical Equipment Orders',default=False)

    def get_medical_product(self):
        products = self.env['product.product'].search([('is_medical_equipment','=',True),('available_in_pos','=',True)])
        data = []
        for rec in products:
            dic = {
                "display_name":rec.name,
                "id":rec.id,
                "price":rec.lst_price,
                "image_url":rec.image_1920,

            } 
            data.append(dic)
        return products
    
    def _order_fields(self, ui_order):
        """To get the value of field in pos session to pos order"""
        res = super()._order_fields(ui_order)
        if ui_order.get('lines'):
            for i in ui_order.get('lines'):
                
                product = self.env['product.product'].search([('id','=',i[2].get('product_id')),('is_medical_equipment','=',True)])
                if product:
                    res['medical_equipment'] = True
        return res

