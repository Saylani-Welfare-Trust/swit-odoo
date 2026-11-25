from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReceiveByWeight(models.TransientModel):
    """The general livestock product of a receipt (e.g. "Cow", 100 units) is
    received as product variants by weight: each line gives a weight and how
    many units weighed that much; the weight band of the product (Livestock
    page) gives the variant. Units not received stay on the receipt (backorder).
    A unit is valued at its weight x the purchase line's price per kg."""
    _name = 'receive.by.weight'
    _description = "Receive By Weight"

    picking_id = fields.Many2one('stock.picking', required=True, ondelete='cascade')
    line_ids = fields.One2many('receive.by.weight.line', 'wizard_id', string="Lines")
    is_received = fields.Boolean(string="Is Received", default=False)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', readonly=True,
        default=lambda self: self.env.company.currency_id.id)
    move_ids = fields.Many2many('stock.move', string='Livestock Lines', compute='_compute_move_ids')
    total_quantity = fields.Float(string='Units', compute='_compute_totals', digits='Product Unit of Measure')
    total_weight = fields.Float(string='Total Weight (kg)', compute='_compute_totals', digits='Stock Weight')
    bill_amount = fields.Monetary(string='Bill Amount', currency_field='currency_id', compute='_compute_totals')

    @api.depends('picking_id')
    def _compute_move_ids(self):
        for rec in self:
            rec.move_ids = rec._livestock_moves(rec.picking_id)

    @api.depends('line_ids.quantity', 'line_ids.total_weight', 'line_ids.amount')
    def _compute_totals(self):
        for rec in self:
            rec.total_quantity = sum(rec.line_ids.mapped('quantity'))
            rec.total_weight = sum(rec.line_ids.mapped('total_weight'))
            rec.bill_amount = sum(rec.line_ids.mapped('amount'))

    @api.model
    def _livestock_moves(self, picking):
        return picking.move_ids.filtered(lambda m: m.product_id.check_stock and m.state not in ('done', 'cancel'))

    @api.model
    def _units(self, move):
        """The units still to receive of a general-product move (a whole number)."""
        units = move.product_uom._compute_quantity(move.product_uom_qty, move.product_id.uom_id)
        if units != int(units):
            raise UserError(_("%s is received by weight, unit by unit: its quantity (%s) must be a whole number.")
                            % (move.product_id.display_name, move.product_uom_qty))
        return int(units)

    @api.model
    def _unit_lines(self, picking):
        """A first line per livestock product of the receipt, with all its units:
        split it into lines of one weight each."""
        return [(0, 0, {'move_id': move.id, 'quantity': self._units(move)})
                for move in self._livestock_moves(picking) if self._units(move)]

    @api.onchange('line_ids')
    def _onchange_line_ids(self):
        for rec in self:
            for idx, line in enumerate(rec.line_ids, start=1):
                line.s_no = idx

    def action_save_only(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'receive.by.weight',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def _check_lines(self):
        errors = []
        if not self.line_ids:
            errors.append(_("Add a line per weight."))
        for line in self.line_ids:
            label = line.s_no or line.id
            if line.move_id.picking_id != self.picking_id or line.move_id not in self.move_ids:
                errors.append(_("Line %s: choose a livestock product of this receipt.") % label)
            elif line.quantity <= 0 or line.quantity != int(line.quantity):
                errors.append(_("Line %s: the quantity must be a whole number of units.") % label)
            elif line.weight <= 0:
                errors.append(_("Line %s: enter the weight of its units.") % label)
            elif not line.band_id:
                errors.append(_("Line %(n)s: no weight band of %(product)s holds %(w)s kg "
                                "(product form > Livestock page).",
                                n=label, product=line.product_id.display_name, w=line.weight))
        for move in self.line_ids.move_id:
            entered = sum(self.line_ids.filtered(lambda l: l.move_id == move).mapped('quantity'))
            if entered > self._units(move):
                errors.append(_("%(product)s: %(entered)s units entered, only %(units)s on the receipt.",
                                product=move.product_id.display_name, entered=int(entered), units=self._units(move)))
        if errors:
            raise UserError('\n'.join(errors))

    def action_receive(self):
        """The general product's units on the receipt are replaced by moves of
        the product variants of their weight, linked to the same purchase lines
        and valued at what they weighed. Units not entered stay on the general
        product's move (a backorder when the receipt is validated). Stock enters
        when the receipt is validated."""
        self.ensure_one()
        picking = self.picking_id
        if self.is_received:
            raise UserError(_("These units are already received."))
        if picking.state in ('done', 'cancel'):
            raise UserError(_("Units can only be received on a receipt that is not done or cancelled."))
        self._check_lines()

        # units grouped by (product variant, purchase line)
        groups = {}
        for line in self.line_ids:
            key = (line.received_product_id, line.move_id.purchase_line_id)
            group = groups.setdefault(key, {'qty': 0.0, 'weight': 0.0, 'amount': 0.0})
            group['qty'] += line.quantity
            group['weight'] += line.total_weight
            group['amount'] += line.amount

        # the general product's moves give up the units received as variants
        for move in self.line_ids.move_id:
            received = sum(self.line_ids.filtered(lambda l: l.move_id == move).mapped('quantity'))
            remaining = self._units(move) - received
            if remaining:
                # what is left waits on the receipt (backorder at validation)
                move.product_uom_qty = move.product_id.uom_id._compute_quantity(remaining, move.product_uom)
                # not received now: never validated as the general product, it goes to a backorder
                move.move_line_ids.unlink()
                move.quantity = 0.0
                move.picked = False
            else:
                # never entered stock: cancelled, then removed
                move._action_cancel()
                move.unlink()

        Move = self.env['stock.move']
        new_moves = Move
        for (product, purchase_line), group in groups.items():
            new_moves |= Move.create({
                'name': product.display_name,
                'product_id': product.id,
                'product_uom_qty': group['qty'],
                'product_uom': product.uom_id.id,
                'picking_id': picking.id,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
                'purchase_line_id': purchase_line.id or False,
                'company_id': picking.company_id.id,
                'livestock_weight': group['weight'],
                'livestock_amount': group['amount'],
            })
        new_moves._action_confirm()
        new_moves._action_assign()
        for move in new_moves:
            move.quantity = move.product_uom_qty

        self.is_received = True
        picking.bill_amount = (picking.bill_amount or 0.0) + self.bill_amount
        return {
            'name': _('Receive by Weight'),
            'type': 'ir.actions.act_window',
            'res_model': 'receive.by.weight',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
