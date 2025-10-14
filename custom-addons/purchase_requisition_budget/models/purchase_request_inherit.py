from odoo import api, fields, models
from odoo.exceptions import UserError


class PurchaseRequestInherit(models.Model):
    _inherit = 'purchase.request'

    employee_purchase_requisition_id = fields.Many2one(
        'employee.purchase.requisition',
        string='Employee Purchase Requisition',
        readonly=True,
    )
    purchase_milestone = fields.Char(string="Milestone")
    purchase_duration = fields.Float(string="duration")
    purchase_request_type = fields.Selection([
        ('trainers_teachers', 'Trainers / Teachers'),
        ('medical_practitioners', 'Medical practitioners’ services'),
        ('professional_consulting', 'Professional and Consulting'),
        ('repair_maintenance_general', 'Repair and Maintenance – General'),
        ('masajid_construction_repairs', 'Masajid Construction / Repairs'),
        ('madaris_construction_repairs', 'Madaris Construction / Repairs'),
        ('marketing', 'Marketing (including Digital marketing)'),
        ('contractual_employees_volunteers', 'Contractual employees / Volunteers'),
        ('insurance', 'Insurance'),
        ('rental_payments', 'Rental payments'),
        ('livestock_cutting_charges', 'Livestock cutting charges'),
        ('functions_events', 'Functions, Events'),
        ('it_services', 'IT Services'),
    ], string="Request Type")
    # vendor_id = fields.Many2one('res.partner',string="Vendor")

    def button_done(self):
        super(PurchaseRequestInherit, self).button_done()
        purchase_request_lines = self.env['purchase.request.line'].search([('request_id', '=', self.id)])

        if not purchase_request_lines:
            raise UserError("No purchase request lines found.")

        order_lines = []
        for line in purchase_request_lines:
            order_line = (0, 0, {
                'product_id': line.product_id.id,
                'name': line.product_id.name,
                'product_qty': line.product_qty,
                'product_uom': line.product_id.uom_id.id,
                'date_planned': fields.Datetime.now(),
            })
            order_lines.append(order_line)

        default_vendor = self.env['res.partner'].search([], limit=1)

        if self.employee_purchase_requisition_id and self.employee_purchase_requisition_id.work_order_visible:
            wo_sequence = self.env['ir.sequence'].next_by_code('purchase.order.wo') or "WO00001"
            po_name = f"WO{wo_sequence.split('WO')[-1]}"
        else:
            po_name = self.env['ir.sequence'].next_by_code('purchase.order')

        purchase_order_vals = {
            'partner_id': default_vendor.id,
            'order_line': order_lines,
            'date_order': fields.Datetime.now(),
            'origin': self.name,
            'name': po_name,
            'order_milestone': self.purchase_milestone,
            'order_duration': self.purchase_duration,
            'order_request_type': self.purchase_request_type,
        }

        purchase_order = self.env['purchase.order'].create(purchase_order_vals)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': purchase_order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # def button_done(self):
    #     super(PurchaseRequestInherit, self).button_done()
    #     purchase_request_lines = self.env['purchase.request.line'].search([('request_id', '=', self.id)])
    #
    #     if not purchase_request_lines:
    #         raise UserError("No purchase request lines found.")
    #
    #     order_lines = []
    #     for line in purchase_request_lines:
    #         order_line = (0, 0, {
    #             'product_id': line.product_id.id,
    #             'name': line.product_id.name,
    #             'product_qty': line.product_qty,
    #             'product_uom': line.product_id.uom_id.id,
    #             'date_planned': fields.Datetime.now(),
    #         })
    #         order_lines.append(order_line)
    #
    #     default_vendor = self.env['res.partner'].search([], limit=1)
    #
    #     purchase_order_vals = {
    #         'partner_id': default_vendor.id,
    #         'order_line': order_lines,
    #         'date_order': fields.Datetime.now(),
    #         'origin': self.name,
    #     }
    #
    #     purchase_order = self.env['purchase.order'].create(purchase_order_vals)
    #
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'purchase.order',
    #         'res_id': purchase_order.id,
    #         'view_mode': 'form',
    #         'target': 'current',
    #     }

