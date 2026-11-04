# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

KEY_USER_GROUP = 'bn_key_management.key_management_user_group'

key_selection = [
    ('draft', 'Draft'),
    ('issued', 'Issued'),
    ('donation_receive', 'Donation Received'),
    ('overdue', 'Overdue'),
    ('pending', 'Pending'),
    ('returned', 'Returned'),
]

action_type_selection = [
    ('bulk', 'Bulk'),
    ('manual', 'Manual'),
]

# key.issuance is fully driven by its state and never edited by hand.
GUARDED_FIELDS = ('state', 'returned_on', 'donation_amount', 'is_fcb', 'is_cfb')


class KeyIssuance(models.Model):
    _name = 'key.issuance'
    _description = 'Key Issuance'
    _inherit = ["mail.thread", "mail.activity.mixin", "bn.workflow.mixin"]
    _bn_guarded_fields = GUARDED_FIELDS

    rider_id = fields.Many2one('hr.employee', string="Rider", tracking=True)
    key_id = fields.Many2one('key', string="Key", tracking=True)
    donation_box_registration_installation_id = fields.Many2one(
        related='key_id.donation_box_registration_installation_id',
        string="Donation Box Registration / Installation", store=True)

    name = fields.Char('Key Name', default="New")
    key_name = fields.Char(related='key_id.name', string="Key Name", store=True)

    issued_on = fields.Datetime('Issued On', default=fields.Datetime.now)
    issue_date = fields.Date('Issued Date', default=fields.Date.today)
    returned_on = fields.Datetime('Returned On')

    state = fields.Selection(selection=key_selection, default='draft', string="Status", tracking=True, index=True)
    action_type = fields.Selection(selection=action_type_selection, default='bulk', string="Action Type")

    donation_amount = fields.Float('Donation Amount')

    shop_name = fields.Char(related='donation_box_registration_installation_id.shop_name', string='Requestor Name', store=True)
    contact_no = fields.Char(related='donation_box_registration_installation_id.contact_no', string='Contact No', store=True)
    location = fields.Char(related='donation_box_registration_installation_id.location', string='Requested Location', store=True)
    contact_person = fields.Char(related='donation_box_registration_installation_id.contact_person', string='Contact Person', store=True)

    installer_id = fields.Many2one(related='donation_box_registration_installation_id.installer_id', string="Installer")
    donor_id = fields.Many2one(related='donation_box_registration_installation_id.donor_id', string="Donor", store=True)
    lot_id = fields.Many2one(related='donation_box_registration_installation_id.lot_id', string="Box No.", store=True)
    city_id = fields.Many2one(related='donation_box_registration_installation_id.city_id', string="City", store=True)
    zone_id = fields.Many2one(related='donation_box_registration_installation_id.zone_id', string="Zone", store=True)
    sub_zone_id = fields.Many2one(related='donation_box_registration_installation_id.sub_zone_id', string="Sub Zone", store=True)
    key_bunch_id = fields.Many2one(related='key_id.key_bunch_id', string="Key Bunch", store=True)
    donation_box_request_id = fields.Many2one(related='donation_box_registration_installation_id.donation_box_request_id', string="Donation Box Request", store=True)
    product_id = fields.Many2one(related='donation_box_registration_installation_id.product_id', string="Donation Box Category", store=True)
    installation_category_id = fields.Many2one(related='donation_box_registration_installation_id.installation_category_id', string="Installation Category", store=True)

    installation_date = fields.Date(related='donation_box_registration_installation_id.installation_date', string='Installation Date', store=True)
    is_fcb = fields.Boolean('Is FCB Collection', default=False, copy=False)
    is_cfb = fields.Boolean('Is CFB Collection', default=False, copy=False)

    # ------------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('key_issuance') or 'New'
        return super().create(vals_list)

    def unlink(self):
        if not self.env.su:
            raise UserError(_('Key Issuance records cannot be deleted. Return the key instead.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_issue(self):
        self._bn_require_group(KEY_USER_GROUP)
        for record in self:
            record._bn_do_issue()
        return True

    def _bn_do_issue(self):
        self.ensure_one()
        key = self.key_id
        if not key:
            raise ValidationError(_('No key selected for this issuance.'))
        if self.state != 'draft':
            raise UserError(_('Issuance "%s" is not in Draft status.') % self.display_name)

        key._bn_lock()
        if key.state != 'available':
            raise ValidationError(_(
                'Key "%(key)s" is not Available (current status: %(state)s).'
            ) % {'key': key.display_name, 'state': key._bn_selection_label('state', key.state)})
        open_issuance = self.search([
            ('key_id', '=', key.id), ('state', 'in', ('issued', 'overdue', 'pending', 'donation_receive')),
        ], limit=1)
        if open_issuance:
            raise ValidationError(_(
                'Key "%(key)s" is already issued to %(rider)s.'
            ) % {'key': key.display_name, 'rider': open_issuance.rider_id.display_name})

        key._bn_write({'state': 'issued'})
        self._bn_write({'state': 'issued', 'issued_on': fields.Datetime.now()})

    def action_return(self):
        self._bn_require_group(KEY_USER_GROUP)
        for record in self:
            record._bn_do_return()
        return True

    def _bn_do_return(self):
        self.ensure_one()
        if self.state not in ('donation_receive', 'pending'):
            raise UserError(_(
                'Issuance "%(name)s" cannot be returned from status "%(state)s".'
            ) % {'name': self.display_name, 'state': self._bn_selection_label('state', self.state)})
        key = self.key_id
        key._bn_lock()
        key._bn_write({'state': 'available'})
        self._bn_write({'state': 'returned', 'returned_on': fields.Datetime.now()})

    def action_donation_receive(self):
        self._bn_check_state('state', ('issued', 'overdue', 'pending'), _('Donation Received'))
        for rec in self:
            rec._bn_write({'state': 'donation_receive'})
        return True

    def action_overdue(self):
        self._bn_require_group(KEY_USER_GROUP)
        for rec in self:
            if rec.state == 'issued':
                rec._bn_write({'state': 'overdue'})
        return True

    def action_pending(self):
        self._bn_check_state('state', ('issued', 'overdue'), _('Mark Pending'))
        for rec in self:
            rec.key_id._bn_lock()
            rec.key_id._bn_write({'state': 'pending'})
            rec._bn_write({'state': 'pending'})
        return True
