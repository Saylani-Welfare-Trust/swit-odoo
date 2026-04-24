from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class QurbaniOrderLine(models.Model):
    _name = 'qurbani.order.line'
    _description = "Qurbani Order Line"


    qurbani_order_id = fields.Many2one('qurbani.order', string="Qurbani Order")
    product_id = fields.Many2one('product.product', string="Product")
    currency_id = fields.Many2one('res.currency', related='qurbani_order_id.currency_id')
    city_id = fields.Many2one('stock.location', string="City")
    distribution_id = fields.Many2one('stock.location', string="Distribution")
    day_id = fields.Many2one('qurbani.day', string="Day")
    hijri_id = fields.Many2one('hijri', string="Hijri")

    name = fields.Char('Name', default="New")
    hissa_name = fields.Char('Hissa Name')

    start_time = fields.Float('Start Time')
    end_time = fields.Float('End Time')

    quantity = fields.Integer('Quantity', default=1)

    amount = fields.Monetary('Amount', currency_field='currency_id')


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('qurbani_order_line') or ('New')

        return super(QurbaniOrderLine, self).create(vals)
    
    def write(self, vals):

        if vals.get('hissa_name'):
            if self.env.user.has_group('bn_qurbani.edit_hissa_name_group'):
                pos_order = self.env['pos.order'].search([('source_document', '=', self.qurbani_order_id.name)])

                if pos_order:
                    line = pos_order.lines.filtered(lambda l:l.customer_note == self.hissa_name and l.product_id.id == self.product_id.id and l.qty == self.quantity)

                    # raise ValidationError(str(self.hissa_name))
                    if line:
                        line.customer_note = vals.get('hissa_name')
            else:
                raise ValidationError("You don't have access to edit the hissa name.")

        return super(QurbaniOrderLine, self).write(vals)