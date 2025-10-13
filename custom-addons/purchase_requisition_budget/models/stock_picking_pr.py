from odoo import models, fields, api
from odoo.exceptions import UserError


class StockPickingInherit(models.Model):
    _inherit = 'stock.picking'

    is_epr_creator = fields.Boolean(
        string="Has Employee Request Origin",
        compute="_compute_has_mr_origin",
        store=False
    )
    stock_milestone = fields.Char(string="Milestone")
    stock_duration = fields.Float(string="duration")
    stock_request_type = fields.Selection([
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
    show_create_purchase_request = fields.Boolean(compute='_compute_show_purchase_request')
    # stock_picking_id = fields.Many2one('stock.picking', string="Picking")
    employee_purchase_requisition_id = fields.Many2one('employee.purchase.requisition', string="Purchase Requisition")
    quality_check_ids = fields.One2many(comodel_name='stock.quality.check', inverse_name='stock_picking_id', string="Quality Check")

    @api.depends('origin')
    def _compute_has_mr_origin(self):
        for picking in self:
            if picking.origin:
                employee_request = self.env['employee.purchase.requisition'].search([('name', '=', picking.origin)], limit=1)
                picking.is_epr_creator = bool(employee_request)
            else:
                picking.is_epr_creator = False

    @api.depends('move_ids_without_package.product_id', 'move_ids_without_package.product_uom_qty')
    def _compute_show_purchase_request(self):
        """Check if any product's quantity exceeds on-hand quantity"""
        for picking in self:
            show_button = False
            for move in picking.move_ids_without_package:
                product = move.product_id
                if move.product_uom_qty > product.qty_available:
                    show_button = True
                    break
            picking.show_create_purchase_request = show_button

    def action_create_purchase_request(self):
        """Create a purchase request for products exceeding on-hand quantity"""
        purchase_request = self.env['purchase.request'].create({
            'requested_by': self.env.user.id,
            'date_start': fields.Date.today(),
            'employee_purchase_requisition_id': self.employee_purchase_requisition_id.id,
            'purchase_milestone': self.stock_milestone,
            'purchase_duration': self.stock_duration,
            'purchase_request_type': self.stock_request_type,
        })
        for move in self.move_ids_without_package:
            product = move.product_id
            stock_quant = self.env['stock.quant'].sudo().search(
                [('location_id', '=', self.location_dest_id.id), ('product_id', '=', self.product_id.id)])
            if stock_quant:
                qty_available = stock_quant.inventory_quantity_auto_apply
            else:
                qty_available = product.qty_available
            print(move.product_uom_qty)
            print(qty_available)
            if move.product_uom_qty > qty_available:
                self.env['purchase.request.line'].create({
                    'request_id': purchase_request.id,
                    'product_id': product.id,
                    'product_qty': move.product_uom_qty - qty_available,
                })

        return {
            'name': 'Purchase Request',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.request',
            'view_mode': 'form',
            'res_id': purchase_request.id,
            'target': 'current',
        }

    # def button_validate(self):
    #     for pick in self:
    #         for check in pick.quality_check_ids:
    #             if check.quality_check == 'default':
    #                 raise UserError("You cannot validate the transfer until all quality checks are either 'Pass' or 'Fail'.")
    #     return super(StockPickingInherit,self).button_validate()
    def button_validate(self):
        for pick in self:
            if pick.picking_type_id.code == 'incoming':
                for check in pick.quality_check_ids:
                    if check.quality_check == 'default':
                        raise UserError(
                            "You cannot validate the transfer until all quality checks are either 'Pass' or 'Fail'.")
        return super(StockPickingInherit, self).button_validate()
