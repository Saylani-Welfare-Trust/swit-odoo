from odoo import models, fields
from odoo.exceptions import UserError


class TermsReference(models.Model):
    _name = 'terms.reference'

    state = fields.Selection([('draft', 'Draft'),
                              ('confirmed', 'Confirmed')],
                             default='draft')
    # department_id = fields.Many2one('hr.department', string="Department", help="Department linked to this budget")

    milestone = fields.Float(string="Milestone")
    duration = fields.Date(string="Duration")

    def action_draft(self):
        self.write({'state': 'draft'})

    # def action_submit(self):
    #     print('123')
    #     self.write({'state':'confirmed'})


    def action_submit(self):
        self.write({'state': 'confirmed'})

        partner = self.env['res.partner'].search([], limit=1)
        if not partner:
            raise UserError("No supplier found. Please create a supplier first.")

        product = self.env['product.product'].search([], limit=1)
        if not product:
            raise UserError("No product found. Please create a product first.")

        purchase_order = self.env['purchase.order'].create({
            'partner_id': partner.id,
            'date_order': fields.Date.today(),
            'order_line': [(0, 0, {
                'product_id': product.id,
                'name': product.name,
                'product_qty': 1.0,
                'price_unit': product.standard_price
            })]
        })

        if not purchase_order:
            raise UserError("Failed to create Purchase Order.")

        print(f"Purchase Order {purchase_order.name} created successfully!")

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'res_id': purchase_order.id,
            'target': 'current',
        }