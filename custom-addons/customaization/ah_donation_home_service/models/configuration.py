from odoo import fields,api,models

class DhsAccountConfiguration(models.Model):
    _name = 'dhs.account.configuration'

    name = fields.Char(string='Name')
    account_id = fields.Many2one('account.account', 'Chart of Account')


import logging

_logger = logging.getLogger(__name__)


class ProductConfiguration(models.Model):
    _name = 'dhs.product.conf'

    @api.model
    def get_dhs_products(self):
    # Get products directly from product.product model where check_stock is True
        product_records = self.env['product.product'].search([('check_stock', '=', True)])
        return product_records.ids

    # product_id = fields.Many2one('product.product', 'Product')
    # return_product_id = fields.Many2one('product.product', 'Return Product')
    # @api.model
    # def get_dhs_products(self):
    #     records = self.search([]).filtered(lambda r: r.product_id)
    #       # Product data ko log mein print karein
        
        
    #     return [r.product_id.id for r in records if r.product_id.check_stock == True]

        # return [r.product_id.id for r in records]
# 
    # @api.model
    # def get_dhs_products(self):
    #     records = self.search([]).filtered(lambda r: r.product_id)
        
    #     _logger.info("=== DHS PRODUCT CONFIGURATION LOG ===")
        
    #     result_product_ids = []
        
    #     for record in records:
    #         # Default stock check (always True)
    #         check_stock = True  # Ya kisi condition ke hisab se set karein
            
    #         if check_stock:  # check_stock == True
               
    #             result_product_ids.append(record.product_id.id)
              
    #             # If stock check is disabled
    #             result_product_ids.append(record.product_id.id)
    #             _logger.info("Product: %s (ID: %s) - Added without stock check", 
    #                         record.product_id.name, 
    #                         record.product_id.id)
        
    #     _logger.info("Final Product IDs: %s", result_product_ids)
    #     _logger.info("=== END LOG ===")
        
    #     return result_product_ids