from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'


    first_para_halfnama = fields.Text('First Halfnama')
    second_para_halfnama = fields.Text('Second Halfnama')
    third_para_halfnama = fields.Text('Third Halfnama')
    # also set from bn_res_qurbani's company form; used by web qurbani orders
    web_no_meat_distribution_location_id = fields.Many2one('stock.location', string="Web No-Meat Distribution Location")
