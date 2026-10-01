# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

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
    rider_collection_id = fields.Many2one('rider.collection', string="Rider Collection", copy=False)

    name = fields.Char('Key Name', default="New")
    key_name = fields.Char(related='key_id.name', string="Key Name", store=True)

    issued_on = fields.Datetime('Issued On', default=fields.Datetime.now)
    issue_date = fields.Date('Issued Date', default=fields.Date.today)
    returned_on = fields.Datetime('Returned On')

    state = fields.Selection(selection=key_selection, default='draft', string="Status", tracking=True)
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
    # Cross-module helper: bn_rider_shift defines rider.collection / foreign.currency,
    # but bn_key_management (this module) is a DEPENDENCY of bn_rider_shift, not the
    # other way around, so these models may legitimately not exist in the registry.
    # Never assume they do.
    # ------------------------------------------------------------------
    def _bn_has_rider_collection(self):
        return 'rider.collection' in self.env.registry.models

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_issue(self):
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
        vals = {'state': 'issued', 'issued_on': fields.Datetime.now()}

        if self._bn_has_rider_collection():
            collection = self.env['rider.collection'].create({
                'rider_id': self.rider_id.id,
                'donation_box_registration_installation_id': key.donation_box_registration_installation_id.id,
                'lot_id': key.lot_id.id,
                'date': self.issue_date,
            })
            vals['rider_collection_id'] = collection.id
        else:
            _logger.info('rider.collection model not installed; skipping collection creation for %s.',
                        self.display_name)

        self._bn_write(vals)

    def action_return(self):
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

    # ------------------------------------------------------------------
    # POS RPC entry point
    # ------------------------------------------------------------------
    @api.model
    def set_donation_amount(self, data):
        """Called from the POS Donation Box screen when a rider closes out a box.

        NOTE: the CFB (counterfeit) / FCB (foreign currency) branches operate on
        ``rider.collection`` / ``foreign.currency``, both defined in bn_rider_shift.
        Guarded so this module keeps working (minus that feature) if bn_rider_shift
        is not installed.
        """
        if not data:
            return {"status": "error", "body": "Please specify Key and Collection Amount"}

        collection_id = data.get('collection_id')
        if not collection_id:
            return {"status": "error", "body": "Collection ID is required"}

        if not self._bn_has_rider_collection():
            return {"status": "error", "body": "Rider Collection module is not installed."}

        collection = self.env['rider.collection'].browse(collection_id)
        if not collection.exists():
            return {"status": "error", "body": "Collection record not found for %s" % data.get('box_no', 'unknown box')}

        # -- CFB (Counterfeit) ------------------------------------------------
        if collection.remarks == 'CFB':
            collection.write({'state': 'paid'})
            if collection.counterfeit_note_ids:
                collection.counterfeit_note_ids.write({'state': 'paid'})

            counterfeit_donor = self.env['res.partner'].search([('name', 'ilike', 'Counterfeit')], limit=1)
            if not counterfeit_donor:
                counterfeit_donor = self.env['res.partner'].create({
                    'name': 'Counterfeit Donor', 'is_company': False, 'customer_rank': 1,
                })
            self._bn_mark_collection_issuance(collection, is_cfb=True)
            return {"status": "success", "donor_id": counterfeit_donor.id, "is_cfb": True}

        # -- FCB (Foreign currency) --------------------------------------------
        if collection.remarks == 'FCB':
            collection.write({'state': 'paid'})
            if 'foreign.currency' in self.env.registry.models:
                foreign_currency_lines = self.env['foreign.currency'].search([
                    ('rider_collection_id', '=', collection.id)])
                lines_to_update = foreign_currency_lines.filtered(lambda line: line.state == 'payment_received')
                if lines_to_update:
                    lines_to_update.write({'state': 'paid'})

            fcb_donor = self.env['res.partner'].search([('name', 'ilike', 'Foreign Currency Donor')], limit=1)
            if not fcb_donor:
                fcb_donor = self.env['res.partner'].create({
                    'name': 'Foreign Currency Donor', 'is_company': False, 'customer_rank': 1,
                })
            self._bn_mark_collection_issuance(collection, is_fcb=True)
            return {"status": "success", "donor_id": fcb_donor.id, "is_fcb": True}

        # -- Normal collection ---------------------------------------------------
        if collection.state != 'donation_submit':
            return {"status": "error", "body": "Please first submit your Collection against %s" % data.get('box_no')}

        try:
            amount = float(data.get('amount'))
        except (TypeError, ValueError):
            return {"status": "error", "body": "Invalid amount for %s" % data.get('box_no')}
        if collection.amount != amount:
            return {"status": "error", "body": "Please enter the correct amount collected against %s" % data.get('box_no')}

        issuance = self.sudo().search([('rider_collection_id', '=', collection_id)], limit=1)
        if not issuance:
            issuance = self.sudo().search([
                ('key_id.lot_id', '=', data.get('lot_id')),
                ('issue_date', '=', data.get('date')),
                ('state', 'in', ['issued', 'overdue']),
            ], limit=1)
        if not issuance:
            return {"status": "error", "body": "Invalid Donation Box"}

        box = self.env['donation.box.registration.installation'].search([
            ('lot_id', '=', data.get('lot_id')),
            ('shop_name', '=', data.get('shop_name')),
            ('contact_person', '=', data.get('contact_person')),
            ('contact_no', '=', data.get('contact_number')),
            ('location', '=', data.get('box_location')),
        ], limit=1)

        if not data.get('check_validation'):
            issuance._bn_write({'donation_amount': amount})
            issuance.action_donation_receive()
            collection.state = 'paid'
            return {"status": "success"}

        return {"status": "success", "id": issuance.id, "donor_id": box.donor_id.id}

    def _bn_mark_collection_issuance(self, collection, is_fcb=False, is_cfb=False):
        """CFB/FCB collections have no real box return: close their issuance record
        (if any) explicitly so it does not block a later bulk issuance of its bunch."""
        issuance = self.sudo().search([('rider_collection_id', '=', collection.id)], limit=1)
        if issuance and issuance.state in ('issued', 'overdue', 'pending'):
            issuance._bn_write({
                'state': 'returned',
                'returned_on': fields.Datetime.now(),
                'is_fcb': is_fcb,
                'is_cfb': is_cfb,
            })
            issuance.key_id._bn_lock()
            issuance.key_id._bn_write({'state': 'available'})
