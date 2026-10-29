# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, float_is_zero

# A requisition in one of these states is excluded from the "Other Purchase
# Requests" page, because it already has its own page ('procurement_approval',
# shown separately) or it is finished and has nothing left to offer
# ('done', 'cancel').
_OTHER_PAGE_EXCLUDED_STATES = ('procurement_approval', 'done', 'cancel')


class VendorSelectionWizard(models.TransientModel):
    _name = 'vendor.selection.wizard'
    _description = 'Vendor Selection for RFQ Creation'

    source_requisition_id = fields.Many2one('purchase.requisition', string='Source Purchase Requisition',
                                     help='Original Purchase Requisition to copy products from')
    vendor_ids = fields.Many2many('res.partner', string='Vendors',
                                   domain="[('category_id.name', '=', 'Vendor')]",
                                   help='Select multiple vendors to create RFQs')
    vendor_count = fields.Integer(compute='_compute_vendor_count', string='Selected Vendors')

    # Page 1: the source Purchase Request's own lines.
    source_line_ids = fields.One2many(
        'vendor.selection.wizard.source.line', 'wizard_id', string='Source PR Lines')
    # Page 2: lines of OTHER Purchase Requests holding one of the same
    # products, currently in "Procurement Manager Approval".
    procurement_line_ids = fields.One2many(
        'vendor.selection.wizard.procurement.line', 'wizard_id', string='Procurement Manager Approval')
    # Page 3: lines of OTHER Purchase Requests holding one of the same
    # products, in any state not already covered above and not finished.
    other_line_ids = fields.One2many(
        'vendor.selection.wizard.other.line', 'wizard_id', string='Other Purchase Requests')

    has_selected_lines = fields.Boolean(compute='_compute_has_selected_lines')

    @api.depends('vendor_ids')
    def _compute_vendor_count(self):
        for wizard in self:
            wizard.vendor_count = len(wizard.vendor_ids)

    @api.depends('source_line_ids.selected', 'procurement_line_ids.selected')
    def _compute_has_selected_lines(self):
        # "Other Purchase Requests" is informational only (see action_create_rfqs) -
        # it never contributes to whether the Create RFQ's button is enabled.
        for wizard in self:
            wizard.has_selected_lines = bool(
                wizard.source_line_ids.filtered('selected')
                or wizard.procurement_line_ids.filtered('selected')
            )

    @api.model
    def default_get(self, fields_list):
        """Get source Purchase Requisition from context, and build the three
        selectable pages: the source PR's own lines, other PRs for the same
        product(s) waiting on Procurement Manager Approval, and other PRs for
        the same product(s) in any other (non-final) state."""
        res = super().default_get(fields_list)

        active_id = self.env.context.get('active_id')
        if not active_id:
            return res
        res['source_requisition_id'] = active_id

        requisition = self.env['purchase.requisition'].browse(active_id)
        if not requisition.exists():
            return res

        source_lines = requisition.line_ids.filtered(lambda l: not l.is_locked)
        res['source_line_ids'] = [(0, 0, {
            'requisition_line_id': line.id,
            'qty_to_order': line.remaining_qty,
            'selected': True,
        }) for line in source_lines]

        product_ids = requisition.line_ids.mapped('product_id').ids
        if product_ids:
            other_lines = self.env['purchase.requisition.line'].search([
                ('product_id', 'in', product_ids),
                ('requisition_id', '!=', requisition.id),
                ('is_locked', '=', False),
            ])

            procurement_lines = other_lines.filtered(
                lambda l: l.requisition_id.state == 'procurement_approval')
            res['procurement_line_ids'] = [(0, 0, {
                'requisition_line_id': line.id,
                'qty_to_order': line.remaining_qty,
                'selected': False,
            }) for line in procurement_lines]

            # Informational only (not selectable - see action_create_rfqs): other
            # open Purchase Requests for the same product(s), excluding whichever
            # ones are already shown, selectable, on the Procurement Manager
            # Approval page above, and excluding finished ones.
            other_state_lines = other_lines.filtered(
                lambda l: l.requisition_id.state not in _OTHER_PAGE_EXCLUDED_STATES)
            res['other_line_ids'] = [(0, 0, {
                'requisition_line_id': line.id,
            }) for line in other_state_lines]

        return res

    def action_create_rfqs(self):
        """Create one consolidated RFQ (Purchase Order) per selected vendor
        from every selected line across all three pages. Lines for the same
        product are summed into a single RFQ line; the RFQ is tagged with
        every Purchase Request that contributed a line; every consumed line
        is locked for that quantity (and fully locked once nothing is left on
        it); and any Purchase Request left with every line locked is closed.
        """
        self.ensure_one()

        if not self.vendor_ids:
            raise ValidationError(_('Please select at least one vendor.'))

        # "Other Purchase Requests" is informational only - it is never part of
        # the consolidated RFQ, by design (see its page in the view).
        #
        # source_line_ids and procurement_line_ids are DIFFERENT models
        # (vendor.selection.wizard.source.line vs .procurement.line), so they
        # cannot be combined with recordset "|" (Odoo's union() requires both
        # sides to share the same model and raises "inconsistent models"
        # otherwise). A plain Python list holds both kinds of record just
        # fine, since every subsequent use below is per-item.
        selected = [
            entry for entry in list(self.source_line_ids.filtered('selected'))
            + list(self.procurement_line_ids.filtered('selected'))
            if not float_is_zero(entry.qty_to_order, precision_digits=4)
        ]

        if not selected:
            raise ValidationError(_('Please select at least one Purchase Request line to order, with a quantity greater than zero.'))

        # Guard against a stale wizard (another run may have locked some of
        # this quantity in the meantime) and against a qty raised past what
        # the line still has left.
        for entry in selected:
            line = entry.requisition_line_id
            if not line.exists():
                raise ValidationError(_('One of the selected lines no longer exists. Please close and reopen this wizard.'))
            uom = line.product_id.uom_id
            if float_compare(entry.qty_to_order, line.remaining_qty, precision_rounding=uom.rounding or 0.01) > 0:
                raise ValidationError(_(
                    'The quantity to order for "%s" (%s) exceeds what is still '
                    'remaining on Purchase Request %s (%s). Please refresh the wizard.'
                ) % (line.product_id.display_name, entry.qty_to_order, line.requisition_id.name, line.remaining_qty))

        # Sum quantities per product across every selected line (regardless of
        # which PR it came from) - each vendor's RFQ gets one line per product.
        product_qty_map = defaultdict(float)
        product_uom_map = {}
        for entry in selected:
            product_qty_map[entry.product_id.id] += entry.qty_to_order
            product_uom_map[entry.product_id.id] = entry.product_uom_id.id or entry.product_id.uom_id.id

        contributing_requisitions = self.env['purchase.requisition']
        for entry in selected:
            contributing_requisitions |= entry.requisition_line_id.requisition_id

        created_rfqs = self.env['purchase.order']
        for vendor in self.vendor_ids:
            order_line_vals = [(0, 0, {
                'product_id': product_id,
                'product_uom': product_uom_map[product_id],
                'product_qty': qty,
                'price_unit': 0.0,  # Will be filled later
            }) for product_id, qty in product_qty_map.items()]

            rfq = self.env['purchase.order'].create({
                'partner_id': vendor.id,
                'requisition_id': self.source_requisition_id.id,
                'requisition_ids': [(6, 0, contributing_requisitions.ids)],
                'origin': ', '.join(contributing_requisitions.mapped('name')) or (self.source_requisition_id.name or ''),
                'order_line': order_line_vals,
            })
            created_rfqs |= rfq

        # Lock what was consumed. The quantity is locked once (not once per
        # vendor): fanning the same consolidated quantity out to several
        # vendors for quotation does not mean more of it was actually ordered.
        for entry in selected:
            entry.requisition_line_id._lock_quantity(entry.qty_to_order)

        # A Purchase Request with every line now locked is finished.
        contributing_requisitions._close_if_fully_locked()

        # Post a traceability message on every contributing Purchase Request.
        vendor_names = ', '.join(self.vendor_ids.mapped('name'))
        for requisition in contributing_requisitions:
            message = _('<p><b>Consolidated RFQ(s) created for vendor(s): %s</b></p><ul>') % vendor_names
            for rfq in created_rfqs:
                message += '<li><a href="/web#id=%s&model=purchase.order&view_type=form">%s</a> - %s</li>' % (
                    rfq.id, rfq.name or rfq.display_name, rfq.partner_id.name)
            message += '</ul>'
            requisition.message_post(body=message)

        if len(created_rfqs) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('RFQ Created'),
                'res_model': 'purchase.order',
                'res_id': created_rfqs[0].id,
                'view_mode': 'form',
                'target': 'current',
            }
        return created_rfqs


class VendorSelectionWizardLineMixin(models.AbstractModel):
    """Shared fields for the three selectable-line pages of the wizard. Each
    page is its own TransientModel (rather than one model shown three times)
    so each has its own inverse Many2one and its own tree view, filtered to
    its own domain from default_get."""
    _name = 'vendor.selection.wizard.line.mixin'
    _description = 'Vendor Selection Wizard Line (shared fields)'

    # ondelete='cascade': this is only a reference the wizard builds for its own
    # lifetime. Without an explicit ondelete, Odoo defaults a required Many2one
    # to 'restrict' - which, since a transient row can outlive the wizard screen
    # until the next cleanup sweep, was blocking deletion of the real PR line
    # (and, by extension, of the Purchase Request itself) with "another model
    # requires the record being deleted". A stale wizard row has no reason to
    # survive the line it points to.
    requisition_line_id = fields.Many2one('purchase.requisition.line', string='PR Line',
                                           required=True, readonly=True, ondelete='cascade')
    requisition_id = fields.Many2one(related='requisition_line_id.requisition_id', string='Purchase Request', readonly=True, store=False)
    requisition_state = fields.Selection(related='requisition_line_id.requisition_id.state', string='PR Status', readonly=True, store=False)
    product_id = fields.Many2one(related='requisition_line_id.product_id', string='Product', readonly=True, store=False)
    product_uom_id = fields.Many2one(related='requisition_line_id.product_uom_id', string='UoM', readonly=True, store=False)
    requested_qty = fields.Float(related='requisition_line_id.product_qty', string='Requested Qty', readonly=True, store=False)
    remaining_qty = fields.Float(related='requisition_line_id.remaining_qty', string='Remaining Qty', readonly=True, store=False)
    qty_to_order = fields.Float(string='Qty to Order', help='Quantity of this line to include in the consolidated RFQ(s).')
    selected = fields.Boolean(string='Select', default=False)

    def _qty_to_order_exceeds_requested(self):
        uom = self.product_uom_id or self.product_id.uom_id
        return float_compare(self.qty_to_order, self.requested_qty,
                             precision_rounding=uom.rounding or 0.01) > 0

    @api.onchange('qty_to_order')
    def _onchange_qty_to_order(self):
        # Immediate feedback while editing the row; _check_qty_to_order below
        # is what actually enforces the rule on save.
        for entry in self:
            if entry._qty_to_order_exceeds_requested():
                entered_qty = entry.qty_to_order
                entry.qty_to_order = entry.requested_qty
                return {'warning': {
                    'title': _('Quantity Too High'),
                    'message': _(
                        'Qty to Order (%s) cannot be greater than the Requested Qty (%s) '
                        'for "%s". It has been reset to the Requested Qty.'
                    ) % (entered_qty, entry.requested_qty, entry.product_id.display_name),
                }}

    @api.constrains('qty_to_order')
    def _check_qty_to_order(self):
        for entry in self:
            if entry._qty_to_order_exceeds_requested():
                raise ValidationError(_(
                    'Qty to Order (%s) cannot be greater than the Requested Qty (%s) for "%s".'
                ) % (entry.qty_to_order, entry.requested_qty, entry.product_id.display_name))


class VendorSelectionWizardSourceLine(models.TransientModel):
    _name = 'vendor.selection.wizard.source.line'
    _inherit = 'vendor.selection.wizard.line.mixin'
    _description = 'Vendor Selection Wizard - Source PR Line'

    wizard_id = fields.Many2one('vendor.selection.wizard', string='Wizard', ondelete='cascade', required=True)


class VendorSelectionWizardProcurementLine(models.TransientModel):
    _name = 'vendor.selection.wizard.procurement.line'
    _inherit = 'vendor.selection.wizard.line.mixin'
    _description = 'Vendor Selection Wizard - Procurement Manager Approval Line'

    wizard_id = fields.Many2one('vendor.selection.wizard', string='Wizard', ondelete='cascade', required=True)


class VendorSelectionWizardOtherLine(models.TransientModel):
    _name = 'vendor.selection.wizard.other.line'
    _inherit = 'vendor.selection.wizard.line.mixin'
    _description = 'Vendor Selection Wizard - Other Purchase Request Line'

    wizard_id = fields.Many2one('vendor.selection.wizard', string='Wizard', ondelete='cascade', required=True)
