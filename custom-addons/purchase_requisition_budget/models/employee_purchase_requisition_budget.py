from odoo import api, fields, models
from odoo.exceptions import UserError


class PurchaseRequisition(models.Model):
    _inherit = 'employee.purchase.requisition'

    epr_visible = fields.Boolean(string="Create EPRRR", default=True)
    work_order_visible = fields.Boolean(string="Create Work Order")

    budget = fields.Float(string='Budget', help='Budget for the purchase requisition')
    state = fields.Selection([
        ('new', 'New'),
        ('approval_committee', 'Approval Committee'),
        ('waiting_department_approval', 'Waiting Department Approval'),
        ('waiting_head_approval', 'Waiting Head Approval'),
        ('approved', 'Approved'),
        # ('purchase_order_created', 'Purchase Order Created'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled')
    ], default='new', tracking=True, copy=False)
    within_budget = fields.Boolean(compute="_compute_within_budget",string="Out of budget" ,store=True)
    # location_id = fields.Many2one('stock.location', string="location")

    location_id = fields.Many2one(
        'stock.location',
        string="Location",
        default=lambda self: self.env['stock.location']
        .search([('complete_name', '=', 'WH/Stock')], limit=1)
    )
    backorder_picking_id  = fields.Many2one('stock.picking', string="Related Picking")

    milestone = fields.Char(string="Milestone")
    duration = fields.Float(string="duration")
    request_type = fields.Selection([
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

    def action_revert_to_new(self):
        for rec in self:
            rec.state = 'new'

    # @api.onchange('employee_id')
    # def _onchange_employee_id(self):
    #     for record in self:
    #         if record.employee_id:
    #             record.dept_id = record.employee_id.department_id
    #
    #             budget = self.env['budget.budget'].search([
    #                 ('department_id', '=', record.dept_id.id),
    #                 ('state', '=', 'draft')
    #             ], limit=1)
    #
    #             if budget:
    #                 budget_line = self.env['budget.lines'].search([
    #                     ('budget_id', '=', budget.id)
    #                 ], limit=1)
    #
    #                 record.budget = budget_line.planned_amount if budget_line else 0.0
    #             else:
    #                 record.budget = 0.0
    #         else:
    #             record.dept_id = False
    #             record.budget = 0.0

    def action_confirm_requisition(self):
        for record in self:
            if record.budget and record.dept_id:
                budget = self.env['budget.budget'].search([
                    ('department_id', '=', record.dept_id.id),
                    ('state', '=', 'draft')
                ], limit=1)

                if budget:
                    budget_line = self.env['budget.lines'].search([
                        ('budget_id', '=', budget.id)
                    ], limit=1)

                    if budget_line:
                        budget_line.write({
                            'planned_amount': budget_line.planned_amount - record.budget
                        })

                        if record.budget <= budget_line.planned_amount:
                            record.state = 'waiting_department_approval'
                        else:
                            record.state = 'approval_committee'

                        message = f"Requisition confirmed successfully. Remaining Budget: {budget_line.planned_amount}"
                        return {
                            'effect': {
                                'fadeout': 'slow',
                                'message': message,
                                'type': 'rainbow_man',
                            }
                        }
                    else:
                        raise UserError("No budget line found for this department.")
                else:
                    raise UserError("No approved budget found for this department.")
            else:
                raise UserError("Please select an employee and ensure the budget is set.")

        return super(PurchaseRequisition, self).action_confirm_requisition()

    def action_receive(self):
        """Received purchase requisition"""
        self.write({'state': 'received'})
        super(PurchaseRequisition, self).action_receive()

    def action_committee_approval(self):
        # print("1")
        self.write({'state': 'waiting_department_approval'})

        budget_record = self.env['budget.budget'].search([('department_id', '=', self.dept_id.id)], limit=1)

        if budget_record:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Department Budget',
                'res_model': 'budget.budget',
                'view_mode': 'form',
                'res_id': budget_record.id,
                'target': 'current',
            }


    @api.depends('budget', 'dept_id')
    def _compute_within_budget(self):
        for record in self:
            record.within_budget = False

            if record.budget and record.dept_id:
                budget = self.env['budget.budget'].search([
                    ('department_id', '=', record.dept_id.id),
                    ('state', '=', 'draft')
                ], limit=1)

                if budget:
                    budget_line = self.env['budget.lines'].search([
                        ('budget_id', '=', budget.id)
                    ], limit=1)

                    if budget_line and record.budget > budget_line.planned_amount:
                        record.within_budget = True

    def action_head_approval(self):

        super(PurchaseRequisition, self).action_head_approval()
        requisition_order_lines = self.requisition_order_ids

        if not requisition_order_lines:
            raise UserError("No requisition order lines found.")

        move_lines = []
        # quality_check_lines = []
        for line in requisition_order_lines:
            stock_quant = self.env['stock.quant'].sudo().search(
                [('location_id', '=', self.location_id.id), ('product_id', '=', line.product_id.id)])
            if stock_quant:
                qty_available = stock_quant.inventory_quantity_auto_apply
            else:
                qty_available = line.product_id.qty_available
            if line.quantity <= qty_available:
                quantity = line.quantity
            else:
                quantity = qty_available
            move = self.env['stock.move'].create({
                'name': line.product_id.name,
                'product_id': line.product_id.id,
                'product_uom': line.product_id.uom_id.id,
                'product_uom_qty': line.quantity,
                'quantity': quantity,
                'location_id': self.location_id.id,
                'location_dest_id': self.location_id.id,
                'state': 'draft',
            })
            move_lines.append(move)

            stock_picking_vals = {
                'picking_type_id': self.delivery_type_id.id,
                'origin': self.name,
                'location_id': self.location_id.id,
                # 'location_id': self.env.ref('stock.stock_location_stock').id,
                'location_dest_id':self.location_id.id,
                'move_ids': [(6, 0, [move.id for move in move_lines])],
                'employee_purchase_requisition_id': self.id,

                # 'quality_check_ids': [(6, 0, [quality_check.id for quality_check in quality_check_lines])]
            }

        if self.work_order_visible:
            stock_picking_vals.update({
                'stock_milestone': self.milestone,
                'stock_duration': self.duration,
                'stock_request_type': self.request_type,
            })

        # move = self.env['stock.move'].create(stock_picking_vals)

        stock_picking = self.env['stock.picking'].create(stock_picking_vals)
        stock_picking.action_assign()
        if stock_picking:
            self.write({
                'backorder_picking_id': stock_picking.id
            })

        # Return the stock.picking record to the user
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': stock_picking.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_department_approval(self):
        """Override method to remove vendor selection validation"""
        self.write({'state': 'waiting_head_approval'})
        self.manager_id = self.env.uid
        self.department_approval_date = fields.Date.today()
    # def action_department_approval(self):
    #     for rec in self.requisition_order_ids:
    #         if rec.requisition_type == 'purchase_order':
    #             continue
    #     super(PurchaseRequisition,self).action_department_approval()

    def action_open_picking(self):
        print('value', self.backorder_picking_id)
        if not self.backorder_picking_id:
            raise UserError("No related stock picking found!")

        return {
            'name': 'Stock Picking',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.backorder_picking_id.id,
            'target': 'current',
        }

