# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .bn_workflow import in_transition

box_status_selection = [
    ('missing', 'Missing'),
    ('broken', 'Broken'),
    ('robbery', 'Robbery'),
    ('return', 'Return'),
    ('repaired', 'Repaired'),
]

status_selection = [
    ('draft', 'Draft'),
    ('process', 'Process'),
    ('not_recovered', 'Not Recovered'),
    ('resolved', 'Resolved'),
]

RESOLVE_GROUP = 'bn_donation_box.donation_box_manager_group'

# Complaint kinds a user can raise (``repaired`` is only ever a *result* of a repair).
RAISABLE_BOX_STATUS = ('missing', 'broken', 'robbery', 'return')


class DonationBoxComplain(models.Model):
    _name = 'donation.box.complain.center'
    _description = 'Donation Box Complain Center'
    _inherit = ["mail.thread", "mail.activity.mixin", "bn.workflow.mixin"]
    _bn_guarded_fields = ('status',)

    lot_id = fields.Many2one('stock.lot', string="Lot", tracking=True)
    rider_id = fields.Many2one('hr.employee', string="Rider", tracking=True)
    complain_officer_id = fields.Many2one('hr.employee', string="Complain Officer", tracking=True)
    donation_box_registration_installation_id = fields.Many2one('donation.box.registration.installation', string="Donation Box", tracking=True)
    return_picking_id = fields.Many2one('stock.picking', string="Return", tracking=True, copy=False)
    scrap_picking_id = fields.Many2one('stock.scrap', string="Scrap", tracking=True, copy=False)
    scrap_return_picking_id = fields.Many2one('stock.picking', string="Scrap Return Picking", tracking=True, copy=False)

    employee_category_id = fields.Many2one(
        'hr.employee.category', string="Employee Category",
        default=lambda self: self._default_category_id('bn_donation_box.donation_box_rider_hr_employee_category'))
    complain_officer_category_id = fields.Many2one(
        'hr.employee.category', string="Complain Officer Category",
        default=lambda self: self._default_category_id('bn_donation_box.donation_box_complain_officer_hr_employee_category'))

    name = fields.Char(related='donation_box_registration_installation_id.name', string='Registration / Installation No.', store=True, tracking=True)
    shop_name = fields.Char(related='donation_box_registration_installation_id.shop_name', string='Shop Name', store=True, tracking=True)
    contact_no = fields.Char(related='donation_box_registration_installation_id.contact_no', string='Contact No', store=True, tracking=True)
    location = fields.Char(related='donation_box_registration_installation_id.location', string='Requested Location', store=True, tracking=True)
    contact_person = fields.Char(related='donation_box_registration_installation_id.contact_person', string='Contact Person', store=True, tracking=True)

    status = fields.Selection(selection=status_selection, string='Status', default='draft', tracking=True, copy=False, index=True)
    box_status = fields.Selection(selection=box_status_selection, string="Box Status", tracking=True, index=True)

    installer_id = fields.Many2one(related='donation_box_registration_installation_id.installer_id', string="Installer")
    zone_id = fields.Many2one(related='donation_box_registration_installation_id.zone_id', string="Zone", store=True, tracking=True)
    city_id = fields.Many2one(related='donation_box_registration_installation_id.city_id', string="City", store=True, tracking=True)
    donor_id = fields.Many2one(related='donation_box_registration_installation_id.donor_id', string="Donor", store=True, tracking=True)
    sub_zone_id = fields.Many2one(related='donation_box_registration_installation_id.sub_zone_id', string="Sub Zone", store=True, tracking=True)
    product_id = fields.Many2one(related='donation_box_registration_installation_id.product_id', string="Donation Box Category", store=True, tracking=True)
    donation_box_request_id = fields.Many2one(related='donation_box_registration_installation_id.donation_box_request_id', string="Donation Box Request", store=True)
    installation_category_id = fields.Many2one(related='donation_box_registration_installation_id.installation_category_id', string="Installation Category", store=True, tracking=True)

    installation_date = fields.Date(related='donation_box_registration_installation_id.installation_date', string='Installation Date', store=True, tracking=True)
    date = fields.Date('Date', tracking=True)

    remarks = fields.Text('Remarks', tracking=True)
    complain_officer_remark = fields.Text('Complain Officer Remark', tracking=True)
    box_recovered = fields.Boolean('Box Recovered', default=False, tracking=True)
    active = fields.Boolean('Active', default=True, tracking=True)

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------
    @api.model
    def _default_category_id(self, xmlid):
        category = self.env.ref(xmlid, raise_if_not_found=False)
        return category.id if category else False

    # ------------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('box_status') and vals['box_status'] not in RAISABLE_BOX_STATUS:
                raise ValidationError(_('A complaint cannot be raised with the box status "%s".') % vals['box_status'])
            registration_id = vals.get('donation_box_registration_installation_id')
            if registration_id:
                registration = self.env['donation.box.registration.installation'].browse(registration_id)
                if vals.get('lot_id') and registration.lot_id.id != vals['lot_id']:
                    raise ValidationError(_('The Box No. does not match the selected registration.'))
                open_complaint = self.search([
                    ('donation_box_registration_installation_id', '=', registration_id),
                    ('status', 'in', ('draft', 'process')),
                ], limit=1)
                if open_complaint:
                    raise ValidationError(_(
                        'Box "%(lot)s" already has an open complaint (%(status)s).'
                    ) % {'lot': registration.lot_id.display_name,
                         'status': open_complaint._bn_selection_label('status', open_complaint.status)})
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and not in_transition():
            frozen = [name for name in ('lot_id', 'box_status', 'donation_box_registration_installation_id',
                                        'rider_id', 'remarks') if name in vals]
            if frozen:
                for rec in self:
                    if rec.status != 'draft':
                        raise UserError(_(
                            'The complaint details cannot be edited once the complaint left the Draft status.'))
            officer_fields = [name for name in ('complain_officer_id', 'complain_officer_remark',
                                                'box_recovered') if name in vals]
            if officer_fields:
                for rec in self:
                    if rec.status not in ('draft', 'process'):
                        raise UserError(_('A closed complaint cannot be edited.'))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            for rec in self:
                if rec.status != 'draft':
                    raise UserError(_('Only complaints in Draft status can be deleted.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _bn_registration(self):
        self.ensure_one()
        registration = self.donation_box_registration_installation_id
        if not registration:
            raise ValidationError(_("No installation record found for this serial."))
        if not self.lot_id:
            raise ValidationError(_("Please select a Serial (Lot) for this complaint."))
        if registration.lot_id != self.lot_id:
            raise ValidationError(_("The serial does not match the installation record."))
        return registration

    def _bn_close_registration(self, registration):
        if registration.status != 'close':
            registration._bn_write({'status': 'close'})

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_process(self):
        self._bn_check_state('status', ('draft',), _('Process Complain'))
        for rec in self:
            rec._bn_check_required(['rider_id', 'lot_id', 'box_status', 'remarks'])
            if rec.box_status in ('missing', 'robbery'):
                rec._bn_check_required(['complain_officer_id'])
            rec._bn_write({'status': 'process'})
        return True

    def action_resolve(self):
        self._bn_require_group(RESOLVE_GROUP)
        self._bn_check_state('status', ('process',), _('Complain Resolved'))
        for rec in self:
            rec._bn_resolve()
        return True

    def _bn_resolve(self):
        self.ensure_one()
        registration = self._bn_registration()

        # Every key of the box must be back before the complaint can be resolved.
        pending_keys = registration._bn_unreturned_key_messages()
        if pending_keys:
            raise ValidationError(
                _("Cannot resolve complaint!\n\nKey(s) must be returned before resolution.\n\n"
                  "Unreturned Keys:\n%s\n\nPlease ensure all keys are returned and marked as available.")
                % "\n".join("  • %s" % message for message in pending_keys))

        box_status = self.box_status
        if box_status in ('missing', 'robbery'):
            if not self.complain_officer_remark:
                raise ValidationError(_(
                    "Complain Officer Remark is required before resolving Missing or Robbery cases."))
            recovered = self.box_recovered
            self._bn_close_registration(registration)
            registration._bn_key_close()
            lot_vals = {'is_not_return': True}
            if recovered:
                lot_vals['lot_consume'] = False
            self.lot_id.write(lot_vals)
            self._bn_write({'status': 'resolved' if recovered else 'not_recovered'})
        elif box_status == 'broken':
            self._bn_do_scrap()
        elif box_status == 'return':
            self._bn_write({'status': 'resolved'})
        else:
            raise UserError(_('A complaint with the box status "%s" cannot be resolved.')
                            % self._bn_selection_label('box_status', box_status))

    def action_return(self):
        """Return ONLY the selected serial (lot) of the original transfer to stock."""
        self._bn_require_group(RESOLVE_GROUP)
        self._bn_check_state('status', ('resolved',), _('Box Return'))
        for rec in self:
            rec._bn_do_return()
        return True

    def _bn_do_return(self):
        self.ensure_one()
        if self.return_picking_id:
            raise UserError(_('This box has already been returned (%s).') % self.return_picking_id.display_name)
        eligible = self.box_status == 'return' or (self.box_status in ('missing', 'robbery') and self.box_recovered)
        if not eligible:
            raise UserError(_(
                'Box Return is only available for "Return" complaints and recovered Missing / Robbery boxes.'))

        registration = self._bn_registration()
        request = registration.donation_box_request_id
        picking = request._bn_find_done_picking(request)
        if not picking:
            raise ValidationError(_("No completed Stock Picking found for this box."))

        return_picking = request._bn_return_lot(picking, self.lot_id)

        self._bn_close_registration(registration)
        registration._bn_key_close()
        self.lot_id.write({'lot_consume': False, 'is_not_return': False})
        self._bn_write({'return_picking_id': return_picking.id})

    def action_scrap(self):
        """Scrap the selected serial (lot) instead of returning it."""
        self._bn_require_group(RESOLVE_GROUP)
        self._bn_check_state('status', ('process',), _('Scrap'))
        for rec in self:
            rec._bn_do_scrap()
        return True

    def _bn_do_scrap(self):
        self.ensure_one()
        if self.scrap_picking_id:
            raise UserError(_('This box has already been scrapped (%s).') % self.scrap_picking_id.display_name)

        registration = self._bn_registration()
        request = registration.donation_box_request_id
        picking = request._bn_find_done_picking(request)
        if not picking:
            raise ValidationError(_("No completed Stock Picking found for this box."))

        serial_used = picking.move_line_ids.filtered(lambda ml: ml.lot_id == self.lot_id)[:1]
        if not serial_used:
            raise ValidationError(_("This serial does not belong to the selected picking."))

        scrap_location = self.env['stock.location'].search([
            ('scrap_location', '=', True),
            ('company_id', 'in', [picking.company_id.id, False]),
        ], limit=1)
        if not scrap_location:
            raise ValidationError(_("Scrap location not configured in the system."))

        scrap = self.env['stock.scrap'].create({
            'product_id': serial_used.product_id.id,
            'lot_id': self.lot_id.id,
            'scrap_qty': 1,
            'product_uom_id': serial_used.product_uom_id.id,
            'location_id': picking.location_dest_id.id,   # where the box is now
            'scrap_location_id': scrap_location.id,
            'company_id': picking.company_id.id,
            'origin': picking.name,
        })
        # action_validate() can return a wizard (insufficient quantity) instead of scrapping.
        scrap.action_validate()
        if scrap.state != 'done':
            raise UserError(_(
                'The scrap of box "%s" could not be validated. Please check the stock of the box.'
            ) % self.lot_id.display_name)

        self._bn_close_registration(registration)
        registration._bn_key_close()
        self._bn_write({'status': 'resolved', 'scrap_picking_id': scrap.id})

    def action_return_picking(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.return_picking_id.id,
            'target': 'current'
        }

    def action_scrap_picking(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.scrap',
            'view_mode': 'form',
            'res_id': self.scrap_picking_id.id,
            'target': 'current'
        }

    def action_scrap_return_move(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.scrap_return_picking_id.id,
            'target': 'current'
        }

    def action_repair(self):
        """
        Repair broken donation boxes (single or bulk).
        The scrap is reversed (scrap location -> warehouse stock), so the box becomes
        available in stock again for a new request.
        """
        self._bn_require_group(RESOLVE_GROUP)
        if not self:
            raise UserError(_('Please select the complaints to repair.'))

        # Validate every selected record first: this action is also reachable from the
        # list view, where the form's button conditions do not apply.
        problems = []
        for rec in self:
            label = rec.lot_id.display_name or rec.display_name
            if rec.box_status != 'broken':
                problems.append(_('%s: only "Broken" boxes can be repaired.') % label)
            elif rec.status != 'resolved':
                problems.append(_('%s: the complaint must be resolved (scrapped) first.') % label)
            elif not rec.scrap_picking_id or rec.scrap_picking_id.state != 'done':
                problems.append(_('%s: no completed scrap found.') % label)
            elif rec.scrap_return_picking_id:
                problems.append(_('%s: already repaired (%s).') % (label, rec.scrap_return_picking_id.display_name))
        if problems:
            raise UserError('\n'.join(problems))

        for rec in self:
            rec._bn_do_repair()

        if len(self) > 1:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Repair Successful'),
                    'message': _('%s boxes have been repaired and are now available for re-allocation.') % len(self),
                    'type': 'success',
                    'sticky': False,
                }
            }
        return True

    def _bn_do_repair(self):
        self.ensure_one()
        scrap = self.scrap_picking_id
        registration = self._bn_registration()
        request = registration.donation_box_request_id
        original_picking = request._bn_find_done_picking(request)

        warehouse = original_picking.picking_type_id.warehouse_id or request.warehouse_id
        stock_location = warehouse.lot_stock_id
        if not stock_location:
            raise ValidationError(_("Cannot determine the warehouse stock location for this box."))

        PickingType = self.env['stock.picking.type']
        picking_type = PickingType.search([
            ('code', '=', 'internal'), ('warehouse_id', '=', warehouse.id)], limit=1)
        if not picking_type:
            picking_type = PickingType.search([
                ('code', '=', 'internal'), ('company_id', '=', scrap.company_id.id)], limit=1)
        if not picking_type:
            raise ValidationError(_("No internal transfer picking type found."))

        origin = _('Repair - %s') % (self.name or self.lot_id.name)
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': scrap.scrap_location_id.id,
            'location_dest_id': stock_location.id,
            'origin': origin,
        })
        move = self.env['stock.move'].create({
            'name': _('Repair Return: %s') % self.lot_id.name,
            'product_id': scrap.product_id.id,
            'product_uom_qty': scrap.scrap_qty,
            'product_uom': scrap.product_uom_id.id,
            'location_id': scrap.scrap_location_id.id,
            'location_dest_id': stock_location.id,
            'picking_id': picking.id,
            'origin': origin,
            'company_id': picking.company_id.id,
        })
        self.env['stock.move.line'].create({
            'move_id': move.id,
            'picking_id': picking.id,
            'product_id': scrap.product_id.id,
            'product_uom_id': scrap.product_uom_id.id,
            'quantity': scrap.scrap_qty,
            'lot_id': self.lot_id.id,
            'location_id': scrap.scrap_location_id.id,
            'location_dest_id': stock_location.id,
        })
        picking.action_confirm()
        request._bn_validate_picking(picking)

        self.lot_id.write({'lot_consume': False, 'is_not_return': False})
        self._bn_close_registration(registration)
        registration._bn_key_close()
        self._bn_write({
            'box_status': 'repaired',
            'scrap_return_picking_id': picking.id,
            'status': 'resolved',
        })
