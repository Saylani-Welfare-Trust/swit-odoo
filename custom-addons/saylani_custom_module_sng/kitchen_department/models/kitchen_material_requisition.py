from odoo import models, fields, api
from datetime import date, datetime



class KitchenMaterialRequisition(models.Model):
    _name = 'kitchen.material.requisition'
    _description = 'Kitchen Material Requisition'

    request_id = fields.Many2one(
        'branch.kitchen.request',
        string='Branch Request',
        required=True,
        ondelete='cascade',
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Internal Transfer',
        readonly=True,
    )
    purchase_requisition_id = fields.Many2one(
        'purchase.requisition',
        string='Purchase Requisition',
        readonly=True,
    )
    line_ids = fields.One2many(
        'kitchen.material.requisition.line',
        'requisition_id',
        string='Lines',
    )
    state = fields.Selection([
        ('draft','Draft'),
        ('requested','Requested'),
        ('done','Done'),
    ], default='draft')

    def _create_internal_meat_po(self, meat_lines):
        # Assume you have a partner record for Goat & Meat Dept
        meat_partner = self.env.ref('kitchen_department.res_partner_goat_meat')
        po = self.env['purchase.order'].create({
            'partner_id': meat_partner.id,
            'date_order': fields.Date.today(),
            'order_line': [
                (0, 0, {
                    'product_id': l.product_id.id,
                    'product_qty': l.quantity,
                    'product_uom': l.uom_id.id,
                    'price_unit': l.product_id.standard_price,
                }) for l in meat_lines
            ],
        })
        # Optionally confirm immediately:
        po.button_confirm()
        return po

    def _process_requisition(self):
        for req in self:
            stock_lines = []
            purchase_lines = []
            meat_lines = []
            normal_lines = []

            for line in req.line_ids:
                product = line.product_id

                # Check for BoM
                bom = self.env['mrp.bom'].search([('product_tmpl_id', '=', product.product_tmpl_id.id)], limit=1)
                if bom:
                    bom_lines = bom.bom_line_ids
                    for bom_line in bom_lines:
                        component_product = bom_line.product_id
                        qty_needed = bom_line.product_qty * line.quantity

                        # Check for meat category
                        if component_product.categ_id.is_meat:
                            meat_lines.append({
                                'product_id': component_product.id,
                                'quantity': qty_needed,
                                'uom_id': component_product.uom_id.id
                            })
                        else:
                            if component_product.qty_available >= qty_needed:
                                stock_lines.append({
                                    'product_id': component_product.id,
                                    'quantity': qty_needed,
                                    'uom_id': component_product.uom_id.id
                                })
                            else:
                                purchase_lines.append({
                                    'product_id': component_product.id,
                                    'quantity': qty_needed,
                                    'uom_id': component_product.uom_id.id
                                })
                else:
                    # No BoM, treat the line itself
                    if product.categ_id.is_meat:
                        meat_lines.append({
                            'product_id': product.id,
                            'quantity': line.quantity,
                            'uom_id': product.uom_id.id
                        })
                    else:
                        if product.qty_available >= line.quantity:
                            stock_lines.append({
                                'product_id': product.id,
                                'quantity': line.quantity,
                                'uom_id': product.uom_id.id
                            })
                        else:
                            purchase_lines.append({
                                'product_id': product.id,
                                'quantity': line.quantity,
                                'uom_id': product.uom_id.id
                            })

            # Handle Stock Moves
            if stock_lines:
                kitchen_location = self.env['stock.location'].search(
                    [('usage', '=', 'internal'), ('name', 'ilike', 'Kitchen')], limit=1)
                picking = self.env['stock.picking'].create({
                    'picking_type_id': self.env.ref('stock.picking_type_internal').id,
                    'location_id': self.env.ref('stock.stock_location_stock').id,
                    'location_dest_id': kitchen_location.id,
                    'move_ids_without_package': [
                        (0, 0, {
                            'name': self.env['product.product'].browse(l['product_id']).name,
                            'product_id': l['product_id'],
                            'product_uom_qty': l['quantity'],
                            'product_uom': l['uom_id'],
                            'location_id': self.env.ref('stock.stock_location_stock').id,
                            'location_dest_id': kitchen_location.id,
                        }) for l in stock_lines
                    ],
                })
                picking.action_confirm()
                picking.action_assign()
                picking.button_validate()
                req.write({'picking_id': picking.id})

            # Handle Purchase Requisition for non-meat
            if purchase_lines:
                pr = self.env['purchase.request'].create({
                    'name': f"MR/{req.request_id.menu_month}/{req.id}",
                    'requested_by': self.env.user.id,
                    'date_start': fields.Date.today(),
                    'line_ids': [
                        (0, 0, {
                            'product_id': l['product_id'],
                            'product_qty': l['quantity'],
                            'product_uom_id': l['uom_id'],
                        }) for l in purchase_lines
                    ],
                })
                req.write({'purchase_requisition_id': pr.id})



            # Handle Meat Requisition

            # aggregated = {}
            # for line in meat_lines:
            #     pid = line['product_id']
            #     if pid not in aggregated:
            #         # start a new entry
            #         aggregated[pid] = {
            #             'product_id': pid,
            #             'quantity': line['quantity'],
            #             'uom_id': line['uom_id'],
            #         }
            #     else:
            #         # add to existing quantity
            #         aggregated[pid]['quantity'] += line['quantity']
            #
            # # Step 2: turn back into list of (0, 0, vals) tuples for create()
            # meat_lines_grouped = [
            #     (0, 0, vals)
            #     for vals in aggregated.values()
            # ]
            #
            # # Step 3: use in your create
            # if meat_lines_grouped:
            #     meat_req = self.env['meat.requisition'].create({
            #         'material_from': line.branch_name.id,
            #         'type': 'meat',
            #         'line_ids': meat_lines_grouped,
            #     })

            for line in req.line_ids:
                if meat_lines:
                    meat_req = self.env['meat.requisition'].create({
                        'material_from': line.branch_name.id,
                        'type': 'meat',
                        'line_ids': [
                            (0, 0, {
                                'product_id': l['product_id'],
                                'quantity': l['quantity'],
                                'uom_id': l['uom_id'],
                            }) for l in meat_lines
                        ],
                    })
                    # You can trigger workflow if needed: meat_req.action_confirm()

                req.write({'state': 'done'})

    def _process_requisition222(self):
        for req in self:
            stock_lines = []
            purchase_lines = []
            # Split lines into stock vs purchase
            for line in req.line_ids:
                product = line.product_id
                if product.qty_available >= line.quantity:
                    stock_lines.append(line)
                else:
                    purchase_lines.append(line)

            # 2.1 Create an internal transfer for in‑stock items
            if stock_lines:

                kitchen_location = self.env['stock.location'].search([('usage', '=', 'internal'), ('name', 'ilike', 'Kitchen')], limit=1)
                picking = self.env['stock.picking'].create({
                    'picking_type_id': self.env.ref('stock.picking_type_internal').id,
                    'location_id': self.env.ref('stock.stock_location_stock').id,
                    'location_dest_id': kitchen_location,
                    'move_ids_without_package': [
                        (0, 0, {
                            'name': l.product_id.name,
                            'product_id': l.product_id.id,
                            'product_uom_qty': l.quantity,
                            'product_uom': l.uom_id.id,
                            'location_id': self.env.ref('stock.stock_location_stock').id,
                            'location_dest_id': self.env.ref('kitchen_department.location_kitchen_stock').id,
                        }) for l in stock_lines
                    ],
                })
                picking.action_confirm()
                picking.action_assign()
                picking.action_done()
                req.write({'picking_id': picking.id})

            # 2.2 Create a Purchase Requisition for out‑of‑stock items
            if purchase_lines:
                pr = self.env['purchase.requisition'].create({
                    'name': f"MR/{req.request_id.menu_month}/{req.id}",
                    'line_ids': [
                        (0, 0, {
                            'product_id': l.product_id.id,
                            'product_qty': l.quantity,
                            'product_uom_id': l.uom_id.id,
                        }) for l in purchase_lines
                    ],
                })
                req.write({'purchase_requisition_id': pr.id})

            # 2.3 Handle meat separately: if any line is flagged meat, generate an internal PO
            meat_lines = req.line_ids.filtered(lambda l: l.meat_category)
            if meat_lines:
                self._create_internal_meat_po(meat_lines)

            req.write({'state': 'done'})


class KitchenMaterialRequisitionLine(models.Model):
    _name = 'kitchen.material.requisition.line'
    _description = 'Material Requisition Line'

    requisition_id = fields.Many2one(
        'kitchen.material.requisition',
        ondelete='cascade',
        required=True
    )
    product_id = fields.Many2one('product.product', string='Product', )
    quantity = fields.Float(string='Qty', required=True)
    uom_id = fields.Many2one('uom.uom', string='UoM',)
    meat_category = fields.Boolean(
        # related='product_id.categ_id.is_meat',
        string='Is Meat',
        readonly=True,
    )

    branch_name = fields.Many2one(
        comodel_name='res.company',
        string='Branch Name',
        required=False)
