# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

from .bn_workflow import bn_transition

APPROVE_GROUP = 'bn_donation_box.donation_box_manager_group'


class DonationBoxRequestLine(models.Model):
    _name = 'donation.box.request.line'
    _description = 'Donation Box Request Line'
    _inherit = ['bn.workflow.mixin']
    _bn_guarded_fields = ('is_returned', 'return_picking_id')

    # Fields that cannot be changed once the parent request left the draft status.
    _bn_locked_after_draft = ('product_id', 'lot_id', 'lock_no', 'old_box_no', 'key_tag',
                              'donation_box_request_id')

    donation_box_request_id = fields.Many2one(
        'donation.box.request', string="Donation Box Request", ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', string="Product")
    lot_id = fields.Many2one('stock.lot', string="Lot")

    lock_no = fields.Char('Lock No.')
    key_tag = fields.Char('Key Tag')
    old_box_no = fields.Char('Old Box No.')

    is_returned = fields.Boolean('Returned', default=False, copy=False, readonly=True)
    return_picking_id = fields.Many2one('stock.picking', string="Return Transfer", copy=False, readonly=True)

    allowed_lot_ids = fields.Many2many(
        'stock.lot',
        string="Allowed Lots",
        compute="_compute_allowed_lot_ids",
        store=False
    )

    on_hand_qty = fields.Float(
        string="On Hand Qty",
        compute="_compute_on_hand_qty",
        store=False
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('product_id', 'donation_box_request_id.source_location_id')
    def _compute_on_hand_qty(self):
        Quant = self.env['stock.quant']
        for line in self:
            location = line.donation_box_request_id.source_location_id
            if not line.product_id or not location:
                line.on_hand_qty = 0.0
                continue

            quants = Quant.search([
                ('product_id', '=', line.product_id.id),
                ('location_id', 'child_of', location.id),
            ])
            line.on_hand_qty = sum(quants.mapped('quantity'))

    @api.depends('product_id', 'donation_box_request_id.source_location_id')
    def _compute_allowed_lot_ids(self):
        Lot = self.env['stock.lot']
        for line in self:
            location = line.donation_box_request_id.source_location_id
            if not line.product_id or not location:
                line.allowed_lot_ids = [(5, 0, 0)]
                continue

            domain = [
                ('product_id', '=', line.product_id.id),
                ('lot_consume', '=', False),
            ]
            if location.usage == 'internal':
                domain.append(('location_id', 'child_of', location.id))
            line.allowed_lot_ids = Lot.search(domain)

    # ------------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('key_tag'):
                vals['key_tag'] = self.env['ir.sequence'].next_by_code('donation_box_key') or 'Unknown'
        lines = super().create(vals_list)
        for line in lines:
            if line.donation_box_request_id and line.donation_box_request_id.status != 'draft' and not self.env.su:
                raise UserError(_('Lines can only be added to a request in Draft status.'))
        return lines

    def write(self, vals):
        if not self.env.su:
            locked = [name for name in self._bn_locked_after_draft if name in vals]
            if locked:
                for line in self:
                    if line.donation_box_request_id.status != 'draft':
                        raise UserError(_(
                            'The lines of request "%s" cannot be edited because it is not in Draft status.'
                        ) % line.donation_box_request_id.display_name)
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            for line in self:
                if line.donation_box_request_id.status == 'approved':
                    raise UserError(_(
                        'Boxes of the approved request "%s" cannot be deleted. '
                        'Use the "Return" button of the line instead.'
                    ) % line.donation_box_request_id.display_name)
        return super().unlink()

    # ------------------------------------------------------------------
    # Approval helpers (called by donation.box.request)
    # ------------------------------------------------------------------
    def _bn_validate_for_approval(self):
        """Server side validation of the lines of one request (see the request)."""
        Registration = self.env['donation.box.registration.installation']
        Quant = self.env['stock.quant']
        active_lines = self.filtered(lambda l: not l.is_returned)

        for line in active_lines:
            label = line.lot_id.display_name or line.product_id.display_name or _('a box line')
            if not line.product_id:
                raise ValidationError(_('Please select the Box Type on every line.'))
            if not line.product_id.is_donation_box:
                raise ValidationError(_('Product "%s" is not flagged as a Donation Box.') % line.product_id.display_name)
            if not line.lot_id:
                raise ValidationError(_('Please select the Box No. on every line (%s).') % line.product_id.display_name)
            if line.lot_id.product_id != line.product_id:
                raise ValidationError(_('Box No. "%(lot)s" does not belong to product "%(product)s".') % {
                    'lot': line.lot_id.display_name, 'product': line.product_id.display_name})
            if not (line.lock_no or '').strip():
                raise ValidationError(_('Please enter the Lock No. for box "%s".') % label)

        lots = active_lines.mapped('lot_id')
        if not lots:
            return

        # Serialise concurrent approvals that would use the same box.
        self.env.cr.execute("SELECT id FROM stock_lot WHERE id IN %s FOR UPDATE", (tuple(lots.ids),))
        lots.invalidate_recordset(['lot_consume'])

        consumed = lots.filtered('lot_consume')
        if consumed:
            raise ValidationError(_(
                'The following boxes are already issued to another request: %s'
            ) % ', '.join(consumed.mapped('display_name')))

        busy = Registration.search([('lot_id', 'in', lots.ids), ('status', '!=', 'close')])
        if busy:
            raise ValidationError(_(
                'The following boxes still have an active registration: %s'
            ) % ', '.join(busy.mapped('lot_id.display_name')))

        for line in active_lines:
            request = line.donation_box_request_id
            source = request.source_location_id
            if source.usage != 'internal':
                # e.g. a Receipt: the boxes come from outside, there is no stock to check.
                continue
            lot = line.lot_id if line.product_id.tracking != 'none' else None
            available = Quant._get_available_quantity(line.product_id, source, lot_id=lot, strict=False)
            if float_compare(available, 1.0, precision_digits=2) < 0:
                raise ValidationError(_(
                    'Box "%(lot)s" is not available in "%(location)s".'
                ) % {'lot': line.lot_id.display_name, 'location': source.display_name})

    def _bn_prefix_key_tags(self):
        """Key tag format: <YY><box class><lock no>-<sequence>."""
        year = str(fields.Date.today().year)[2:]
        for line in self.filtered(lambda l: not l.is_returned):
            name = (line.product_id.name or '').lower()
            if 'crystal' in name:
                box_class = '22'
            elif 'iron' in name:
                box_class = '23'
            else:
                box_class = '21'
            line.key_tag = f'{year}{box_class}{line.lock_no}-{line.key_tag}'

    # ------------------------------------------------------------------
    # "Return" button of an approved request line
    # ------------------------------------------------------------------
    def action_draft_line(self):
        """Take a box back to the warehouse *before* it was installed.

        The stock is really returned (a return transfer is created and validated), the
        registration and key are closed and the box becomes selectable again.
        Installed boxes must go through the Complain Center.
        """
        self._bn_require_group(APPROVE_GROUP)
        for line in self:
            line._bn_return_line()
        return True

    def _bn_return_line(self):
        self.ensure_one()
        request = self.donation_box_request_id
        if request.status != 'approved':
            raise UserError(_('Only boxes of an approved request can be returned.'))
        if self.is_returned:
            raise UserError(_('Box "%s" has already been returned.') % self.lot_id.display_name)

        registrations = self.env['donation.box.registration.installation'].search([
            ('donation_box_request_id', '=', request.id),
            ('lot_id', '=', self.lot_id.id),
            ('status', '!=', 'close'),
        ])
        if not registrations:
            raise ValidationError(_("No active installation record found for this line."))
        registration = registrations[0]

        if registration.box_status == 'installed' or registration.status != 'draft':
            raise ValidationError(_(
                'Cannot return box "%s" because it is already installed. '
                'Use the Complain Center to return an installed box.'
            ) % self.lot_id.display_name)
        if registration.complain_center_ids.filtered(lambda c: c.status in ('draft', 'process')):
            raise ValidationError(_('Box "%s" has an open complaint.') % self.lot_id.display_name)
        registration._bn_check_can_release()

        picking = request._bn_find_done_picking(request)
        if not picking:
            raise ValidationError(_('No completed stock transfer found for request "%s".') % request.display_name)
        return_picking = request._bn_return_lot(picking, self.lot_id)

        with bn_transition():
            registration._bn_write({'status': 'close'})
            registration._bn_key_close()
            self.lot_id.write({'lot_consume': False})
            self.write({'is_returned': True, 'return_picking_id': return_picking.id})
        request.message_post(body=_('Box %(lot)s returned to stock (%(picking)s).') % {
            'lot': self.lot_id.display_name, 'picking': return_picking.display_name})
