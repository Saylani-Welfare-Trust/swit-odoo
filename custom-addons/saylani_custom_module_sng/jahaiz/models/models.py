from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class JahaizRequest(models.Model):
    _name = 'jahaiz.request'
    _description = 'Jahaiz (Wedding) Request'

    name = fields.Char(string='Request Reference', required=True, copy=False,
                       default=lambda self: self.env['ir.sequence'].next_by_code('jahaiz.request'))
    donee_id = fields.Many2one('res.partner', string='Donee', required=True)
    date_request = fields.Date(string='Request Date', default=fields.Date.context_today)
    welfare_approved = fields.Boolean(string='Welfare Approved', default=False)

    selection_ids = fields.One2many('jahaiz.selection', 'request_id', string='Selections')
    slip_date = fields.Date(string='Delivery Date', readonly=True)
    slip_location = fields.Char(string='Delivery Location', readonly=True)
    state = fields.Selection([
        ('draft','Draft'),
        ('approved','Welfare Approved'),
        ('selected','Items Selected'),
        ('pr','Purchase Requisition'),
        ('po','Purchase Order'),
        ('grn','Received'),
        ('done','Delivered')], default='draft', string='Status', copy=False)
    
    
    location = fields.Text(
        string="Location",
        required=False)

    lead_time = fields.Integer(
        string='Lead Time (days)',
        default=7,
        help="Number of days from request to delivery",
    )

    date_of_delivery = fields.Date(
        string='Date of Delivery',
        compute='_compute_date_of_delivery',
        store=True,
    )



    @api.depends('date_request', 'lead_time')
    def _compute_date_of_delivery(self):
        for rec in self:
            if rec.date_request is not False and rec.lead_time is not False:
                rec.date_of_delivery = rec.date_request + relativedelta(days=rec.lead_time)
            else:
                rec.date_of_delivery = False

    # 1. Approve by welfare
    def action_welfare_approve(self):
        self.ensure_one()
        # 1) Mark this JahaizRequest approved
        self.welfare_approved = True
        self.state = 'approved'

        # 2) Prepare lines for Distribution Request
        dist_lines = []
        for sel in self.selection_ids:
            dist_lines.append((0, 0, {
                'product_id': sel.product_id.id,
                'qty': sel.qty,
            }))

        # 3) Create the distribution.request
        self.env['distribution.request'].create({
            'name': self.name,
            'donee_id': self.donee_id.id,
            'date_request': fields.Date.context_today(self),
            'location': self.location,
            'lead_time': self.lead_time,
            'date_of_delivery': self.date_of_delivery,
            'selection_ids': [(5,0,0)] + dist_lines,
        })

        return True


    def action_confirm_selection(self):
        self.ensure_one()
        if not self.selection_ids:
            raise UserError(_('Please select at least one item.'))
        self.state = 'selected'

    # 6–8. Create Purchase Requisition → Purchase Order
    def action_create_pr(self):
        self.ensure_one()
        if self.state != 'selected':
            raise UserError(_('Selection must be confirmed first.'))
        requisition = self.env['purchase.requisition'].create({
            'name': self.name + '/PR',
            'line_ids': [(0,0,{
                'product_id': sel.product_id.id,
                'product_qty': sel.qty,
            }) for sel in self.selection_ids]
        })
        requisition.action_in_progress()
        # convert to purchase orders
        for po in requisition.purchase_ids:
            po.button_confirm()
        self.state = 'po'
        return True

    # 9–12. Receive (GRN) & Deliver
    @api.model
    def _cron_check_due(self):
        '''Scheduled action: on slip_date, auto-create delivery picking'''
        today = fields.Date.today()
        for req in self.search([('state','=','po'), ('slip_date','<=', today)]):
            picking = req._create_delivery_picking()
            picking.action_confirm()
            req.state = 'grn'

    def _create_delivery_picking(self):
        stock_picking = self.env['stock.picking'].create({
            'partner_id': self.donee_id.id,
            'picking_type_id': self.env.ref('stock.picking_type_out').id,
            'location_id': self.env.ref('stock.stock_location_stock').id,
            'location_dest_id': self.donee_id.property_stock_customer.id,
            'move_lines': [(0,0,{
                'product_id': sel.product_id.id,
                'product_uom_qty': sel.qty,
                'product_uom': sel.product_id.uom_id.id,
            }) for sel in self.selection_ids],
        })
        return stock_picking

    def action_mark_done(self):
        '''Called when Delivery Note is signed'''
        for req in self:
            pickings = self.env['stock.picking'].search([
                ('origin','=', req.name + '/PR')
            ])
            pickings.button_validate()
            req.state = 'done'

class JahaizSelection(models.Model):
    _name = 'jahaiz.selection'
    _description = 'Selected Wedding Item'
    request_id = fields.Many2one('jahaiz.request', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Item', required=True)
    qty = fields.Float(string='Quantity', default=1.0)

