from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

from dateutil.relativedelta import relativedelta


state_selection = [
    ('draft', 'Draft'),
    ('item_selected', 'Items Selected'),
    ('welfare_approved', 'Welfare Approved'),
    ('purchase_requisition', 'Purchase Requisition'),
    ('delivery_note', 'Delivery Note'),
]

type_selection = [
    ('jahaiz', 'Jahaiz'),
    ('others', 'Others'),
]


class DistributionCenter(models.Model):
    _name = 'distribution.center'
    _decription = "Distribution Center"


    name = fields.Char('Name', default="New")

    donee_id = fields.Many2one('res.partner', string="Donee")
    purchase_requisition_id = fields.Many2one('purchase.requisition', string="Purchase Requisition")
    picking_id = fields.Many2one('stock.picking', string="Picking")

    request_date = fields.Date('Request Date', default=fields.Date.today())
    delivery_date = fields.Date('Delivery Date', compute="_set_delivery_date", store=True)

    type = fields.Selection(selection=type_selection, string="Type")

    lead_time = fields.Integer('Lead Time', default=7)

    state = fields.Selection(selection=state_selection, string='State', default='draft')

    location = fields.Text('Location')
    delivery_instruction = fields.Text('Delivery Instruction')

    distribution_center_line_ids = fields.One2many('distribution.center.line', 'distribution_center_id', string="Distribution Center Lines")


    @api.depends('request_date', 'lead_time')
    def _set_delivery_date(self):
        for rec in self:
            rec.delivery_date = None

            if rec.request_date and rec.lead_time:
                rec.delivery_date = rec.request_date + relativedelta(days=rec.lead_time)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('distribution_center') or ('New')
        
        return super(DistributionCenter, self).create(vals)
    
    def action_confirm(self):
        self.ensure_one()

        if not self.distribution_center_line_ids:
            raise ValidationError(_('Please select at least one item.'))
        
        self.state = 'item_selected'

    def action_welfare_approve(self):
        self.ensure_one()

        self.state = 'welfare_approved'

    def action_issue_purchase_requisition(self):
        """Purchase Requisition to Supply Chain Dept for all distribution lines."""
        self.ensure_one()

        PurchaseRequisition = self.env['purchase.requisition']

        if not self.distribution_center_line_ids:
            raise ValidationError("No distribution lines found to create a Purchase Request.")

        purchase_requisition_line = []

        for line in self.distribution_center_line_ids:
            purchase_requisition_line.append((0, 0, {
                'product_id': line.product_id.id,
                'product_qty': line.quantity,
                'qty_ordered': 0,
                'product_uom_id': line.product_id.uom_id.id
            }))

        purchase_requisition = PurchaseRequisition.create({
            'origin': self.name,
            'user_id': self.env.user.id,
            'ordering_date': fields.Date.today(),
            'line_ids': purchase_requisition_line,
        })

        self.state = 'purchase_requisition'
        self.purchase_requisition_id = purchase_requisition.id
        
        purchase_requisition.message_post(body=f"Purchase Requisition has been issued from Distribution Request {self.name}")

    def action_issue_delivery_note(self):
        """Manually create and confirm the outgoing Delivery Note."""
        self.ensure_one()

        purchase_order = self.purchase_requisition_id.purchase_ids.filtered(lambda x: x.state in ['purchase', 'done'])

        if not purchase_order:
            raise ValidationError('Please validate one of the respected Purchase Requisition RFQ.')

        warehouse_loc = self.env['stock.location'].search([
            ('name', 'ilike', 'stock'),
            ('usage', '=', 'internal'),
        ], limit=1)
        
        picking = self.env['stock.picking'].create({
            'origin': self.name,
            'partner_id': self.donee_id.id,
            'picking_type_id': self.env.ref('stock.picking_type_out').id,
            'location_id': warehouse_loc.id,
            'location_dest_id': self.donee_id.property_stock_customer.id,
            'move_ids': [
                (0, 0, {
                    'name': line.product_id.display_name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'quantity': line.quantity,
                    'product_uom': line.product_id.uom_id.id,
                    'location_id': warehouse_loc.id,
                    'location_dest_id': self.donee_id.property_stock_customer.id,
                })
                for line in self.distribution_center_line_ids
            ],
        })
        
        picking.action_confirm()

        if picking.state == 'assigned':
            picking.button_validate()

        self.picking_id = picking.id
        self.state = 'delivery_note'

    def action_show_purchase_requisition(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "purchase.requisition",
            "view_mode": "form",
            "res_id": self.purchase_requisition_id.id,
        }
    
    def action_show_delivery_note(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "view_mode": "form",
            "res_id": self.picking_id.id,
        }