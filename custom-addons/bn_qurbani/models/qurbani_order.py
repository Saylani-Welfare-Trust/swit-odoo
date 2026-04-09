from odoo import models, fields, api, _


class QurbaniOrder(models.Model):
    _name = 'qurbani.order'
    _description = 'Qurbani POS Orders'

    pos_order_id = fields.Many2one('pos.order', string="Order")
    
    name = fields.Char('Name', default="New")
    receipt_number = fields.Char('Receipt Number')
    
    product_ids = fields.Many2many('product.product', string="Products")


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('qurbani_order') or ('New')

        return super(QurbaniOrder, self).create(vals)

    def action_show_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'POS Order',
            'res_model': 'pos.order',
            'view_mode': 'form',
            'res_id': self.pos_order_id.id,
            'target': 'current',
        }
    
    @api.model
    def select_order(self, data):
        if not data:
            return {
                "status": "error",
                "body": "Please provide order reference",
            }

        # -------------------------
        # Find POS Order
        # -------------------------
        order = self.env['pos.order'].search(
            [('pos_reference', '=', data)],
            limit=1
        )

        if not order:
            return {
                "status": "error",
                "body": f"POS Order not found for reference {data}",
            }

        # -------------------------
        # Find Qurbani Order
        # -------------------------
        qurbani_order = self.env['qurbani.order'].search(
            [('pos_order_id', '=', order.id)],
            limit=1
        )

        if not qurbani_order:
            return {
                "status": "error",
                "body": f"Qurbani Order not found for reference {data}",
            }

        # -------------------------
        # Success Response
        # -------------------------
        return {
            "status": "success",
            "id": qurbani_order.id,
            "name": qurbani_order.name,
            "pos_reference": order.pos_reference,
            "customer": order.partner_id.name if order.partner_id else None,
        }