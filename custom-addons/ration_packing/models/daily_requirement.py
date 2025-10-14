from datetime import timedelta

from odoo import models, fields, api
from odoo.exceptions import UserError


class DailyRequirement(models.Model):
    _name = 'ration.daily.req'
    _description = 'Daily Requirement'

    date = fields.Date(required=True)
    center_id = fields.Many2one('res.partner')
    line_ids = fields.One2many('ration.daily.line', 'req_id', string="Lines")

    state = fields.Selection(
        string='State',
        selection=[('draft', 'Draft'),
                   ('req_to_warehouse', 'Issuance Request to Warehouse'), ],
        default='draft',
        required=False, )

    def _get_aggregated_products(self):
        """
        Return a list of dicts: [{'product': <product.record>, 'qty': total_qty}, ...]
        grouping all DailyLine products by product and summing quantities.
        """
        agg = {}
        for line in self.line_ids:
            # Each line.product is a recordset; iterate products
            for prod in line.product:
                agg.setdefault(prod.id, {'product': prod, 'qty': 0})
                # If no quantity set, default to 1
                agg[prod.id]['qty'] += (line.quantity or 1)
        # Return as list
        return list(agg.values())

    # def action_send_issuance(self):
    #     """Create a ration.issuance.req from this daily plan."""
    #     IssReq = self.env['ration.issuance.req']
    #     for rec in self:
    #         # build issuance lines
    #         iss_lines = [
    #             (0, 0, {
    #                 'product_id': line.product_id
    #                 if line.product_id
    #                 else False,
    #                 'quantity': line.quantity,
    #             })
    #             for line in rec.line_ids
    #         ]
    #         # create the issuance request header
    #         IssReq.create({
    #             'date': rec.date,
    #             'center_id': rec.center_id.id,
    #             'line_ids': iss_lines,
    #         })
    #     return True

    def action_send_issuance(self):
        """Create an internal picking from Ration Packing to Distribution."""
        IssReq = self.env['ration.issuance.req']

        StockPicking = self.env['stock.picking']

        # 1) Find your two locations by name (adjust the names as needed)
        source_loc = self.env['stock.location'].search([
            ('name', '=ilike', 'Ration Packing'),
            ('usage', '=', 'internal'),
        ], limit=1)
        dest_loc = self.env['stock.location'].search([
            ('name', '=ilike', 'Distribution'),
            ('usage', '=', 'internal'),
        ], limit=1)

        if not source_loc or not dest_loc:
            raise UserError(
                "Could not find both 'Ration Packing' and 'Distribution' internal locations. "
                "Please check their names in Inventory ▶ Configuration ▶ Locations."
            )

        # 2) Get the internal transfer picking type
        picking_type = self.env.ref('stock.picking_type_internal')

        for rec in self:
            # 3) Create the picking
            picking = StockPicking.create({
                'picking_type_id': picking_type.id,
                'location_id': source_loc.id,
                'location_dest_id': dest_loc.id,
                # 'origin': rec.name or False,
                'scheduled_date': rec.date,
            })

            move_vals = []
            for line in rec.line_ids:
                for prod in line.product:
                    move_vals.append((0, 0, {
                        'name': prod.display_name,
                        'product_id': prod.id,
                        'product_uom_qty': 1.0,  # always 1
                        'product_uom': prod.uom_id.id,
                        'location_id': source_loc.id,
                        'location_dest_id': dest_loc.id,
                    }))

            if not move_vals:
                picking.unlink()
                raise UserError(
                    f"No products found on Daily Requirement {rec.id}; "
                    "cannot create transfer."
                )

            # 4) Write all moves at once, then confirm/assign/validate
            picking.write({'move_ids_without_package': move_vals})
            picking.action_confirm()
            picking.action_assign()
            if picking.state == 'assigned':
                picking.button_validate()

            iss_lines = [
                (0, 0, {
                    'category_id': line.category_id.id,
                    'donee': line.donee.id,
                    'product': line.product,
                    'name': line.name,
                    'disbursement_type_ids': line.disbursement_type_ids,
                })
                for line in rec.line_ids
            ]
            # create the issuance request header
            IssReq.create({
                'date': rec.date,
                'center_id': rec.center_id.id,
                'line_ids': iss_lines,
            })

            # 5) Update daily document state
            rec.state = 'req_to_warehouse'

        return True


class DailyLine(models.Model):
    _name = 'ration.daily.line'
    req_id = fields.Many2one('ration.daily.req', ondelete='cascade')
    # category_id = fields.Many2one('ration.pack.category')
    category_id = fields.Many2one('disbursement.category', string="Disbursement Category")
    product = fields.Many2many(
        comodel_name='product.product',
        string='Product',
        required=False)
    donee = fields.Many2one('res.partner', string="Donee")
    quantity = fields.Integer(string="Quantity")
    name = fields.Char(
        string='Voucher',
        required=False)

    disbursement_type_ids = fields.Many2many('disbursement.type', string="Disbursement Type ID", tracking=True)


class DailyWizard(models.TransientModel):
    _name = 'ration.daily.wizard'
    _description = 'Daily Req Wizard'

    date = fields.Date(default=fields.Date.context_today)
    center_id = fields.Many2one('res.partner')

    # method called by button

    def _compute_req(self):
        """
        Compute tomorrow’s pack quantities.
        Return a list of (category, qty) tuples.
        """
        # Example stub: fetch all pack categories with zero qty
        cats = self.env['ration.pack.category'].search([])
        return [(cat, 0) for cat in cats]  # one2many prep format

    def action_confirm(self):
        for rec in self:
            self.env['ration.daily.req'].create({
                'date': rec.date + timedelta(days=1),
                'center_id': rec.center_id.id,
                'line_ids': [
                    (0, 0, {'category_id': cat.id, 'quantity': qty})
                    for cat, qty in rec._compute_req()
                ]
            })
