from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ReceiveByWeight(models.TransientModel):
    """Each unit of a livestock purchase product on a receipt is weighed and,
    by its livestock variant and weight band (Livestock Variants), received as
    the product of that band, valued at weight x the purchase line's price per kg."""
    _name = 'receive.by.weight'
    _description = "Receive By Weight"

    picking_id = fields.Many2one('stock.picking', required=True, ondelete='cascade')
    line_ids = fields.One2many('receive.by.weight.line', 'wizard_id', string="Lines")
    is_received = fields.Boolean(string="Is Received", default=False)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', readonly=True,
        default=lambda self: self.env.company.currency_id.id)
    total_weight = fields.Float(string='Total Weight (kg)', compute='_compute_totals', digits='Stock Weight')
    bill_amount = fields.Monetary(string='Bill Amount', currency_field='currency_id', compute='_compute_totals')

    @api.depends('line_ids.weight', 'line_ids.amount')
    def _compute_totals(self):
        for rec in self:
            rec.total_weight = sum(rec.line_ids.mapped('weight'))
            rec.bill_amount = sum(rec.line_ids.mapped('amount'))

    @api.model
    def _unit_lines(self, picking):
        """One line per unit of each livestock move of the receipt."""
        lines, s_no = [], 1
        for move in picking.move_ids.filtered(lambda m: m.product_id.check_stock and m.state not in ('done', 'cancel')):
            variants = self.env['livestock.variant.line'].search(
                [('purchase_product_id', '=', move.product_id.id)]).variant_id
            units = move.product_uom._compute_quantity(move.product_uom_qty, move.product_id.uom_id)
            if units != int(units):
                raise UserError(_("%s is received by weight, unit by unit: its quantity (%s) must be a whole number.")
                                % (move.product_id.display_name, move.product_uom_qty))
            for _unit in range(int(units)):
                lines.append((0, 0, {
                    's_no': s_no,
                    'move_id': move.id,
                    # preset only when the product is bought for one variant
                    'livestock_variant': variants.id if len(variants) == 1 else False,
                }))
                s_no += 1
        return lines

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
        for line in self.line_ids:
            if not line.livestock_variant:
                errors.append(_("Unit %s: choose its livestock variant.") % line.s_no)
            elif line.weight <= 0:
                errors.append(_("Unit %s: enter its weight.") % line.s_no)
            elif not line.band_id:
                errors.append(_("Unit %(n)s: no weight band of %(variant)s / %(product)s holds %(w)s kg "
                                "(Inventory > Configuration > Livestock Variants).",
                                n=line.s_no, variant=line.livestock_variant.name,
                                product=line.product_id.display_name, w=line.weight))
        if errors:
            raise UserError('\n'.join(errors))

    def action_receive(self):
        """The receipt's purchase-product (placeholder) moves are replaced by
        moves of the products of the units' weight bands, linked to the same
        purchase lines and valued at what the units weighed. Stock enters when
        the receipt is validated."""
        self.ensure_one()
        picking = self.picking_id
        if self.is_received:
            raise UserError(_("These units are already received."))
        if picking.state in ('done', 'cancel'):
            raise UserError(_("Units can only be received on a receipt that is not done or cancelled."))
        placeholder_moves = picking.move_ids.filtered(
            lambda m: m.product_id.check_stock and m.state not in ('done', 'cancel'))
        expected = {line[2]['move_id'] for line in self._unit_lines(picking)}
        if set(self.line_ids.move_id.ids) != expected or len(self.line_ids) != len(self._unit_lines(picking)):
            raise UserError(_("The receipt changed since these units were listed: close and open Receive by Weight again."))
        self._check_lines()

        # units grouped by (received product, purchase line)
        groups = {}
        for line in self.line_ids:
            key = (line.received_product_id, line.move_id.purchase_line_id)
            group = groups.setdefault(key, {'qty': 0.0, 'weight': 0.0, 'amount': 0.0})
            group['qty'] += 1.0
            group['weight'] += line.weight
            group['amount'] += line.amount

        # the placeholder moves never entered stock: cancelled, then removed
        placeholder_moves._action_cancel()
        placeholder_moves.unlink()

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
        picking.bill_amount = self.bill_amount
        return {
            'name': _('Receive by Weight'),
            'type': 'ir.actions.act_window',
            'res_model': 'receive.by.weight',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
