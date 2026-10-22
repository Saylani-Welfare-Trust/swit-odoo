# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .bn_workflow import in_transition

box_status_selection = [
    ('not_installed', 'Not Installed'),
    ('installed', 'Installed'),
    ('removed', 'Removed'),
]

status_selection = [
    ('draft', 'Draft'),
    ('installed', 'Installed'),
    ('available', 'Available'),
    ('change_request', 'Change Request'),
    ('close', 'Closed'),
]

USER_GROUP = 'bn_donation_box.donation_box_user_group'
ADMIN_GROUP = 'bn_donation_box.donation_box_admin_group'
APPROVE_GROUP = 'bn_donation_box.donation_box_manager_group'
CHANGE_REQUEST_GROUP = 'bn_donation_box.donation_box_manager_group'

DONOR_CATEGORY_XMLIDS = (
    'bn_profile_management.donor_partner_category',
    'bn_profile_management.individual_partner_category',
    'bn_profile_management.donation_box_donor_partner_category',
)


class DonationBoxRegistrationInstallation(models.Model):
    _name = 'donation.box.registration.installation'
    _description = 'Donation Box Registration'
    _inherit = ["mail.thread", "mail.activity.mixin", "bn.workflow.mixin"]
    _rec_name = 'shop_name'
    _bn_guarded_fields = ('status', 'box_status')

    # Technical links, set once by the approval of the request.
    _bn_immutable_fields = ('lot_id', 'product_id', 'donation_box_request_id', 'installer_id',
                            'lock_no', 'old_box_no')

    donation_box_request_id = fields.Many2one('donation.box.request', string="Donation Box Request", index=True)
    lot_id = fields.Many2one('stock.lot', string="Lot", index=True)
    donor_id = fields.Many2one('res.partner', string="Donor", tracking=True)
    installation_category_id = fields.Many2one('installation.category', string="Installation Category", tracking=True)
    product_id = fields.Many2one('product.product', string="Box Category")
    country_id = fields.Many2one(related='donor_id.country_code_id', string="Phone Code", store=True, tracking=True)

    installer_id = fields.Many2one('hr.employee', string="Installer", tracking=True)
    employee_category_2_id = fields.Many2one(
        'hr.employee.category', string="Employee Installer Category",
        default=lambda self: self._default_employee_category_id())

    city_id = fields.Many2one('account.analytic.account', string="City", tracking=True)
    zone_id = fields.Many2one('account.analytic.account', string="Zone", tracking=True)
    sub_zone_id = fields.Many2one('sub.zone', string="Sub Zone", tracking=True)

    name = fields.Char('Name', default="New", copy=False)
    request_no = fields.Char(related='donation_box_request_id.name', string="Request No.", store=True)
    shop_name = fields.Char('Shop Name', tracking=True)
    contact_no = fields.Char(related='donor_id.mobile', string="Contact No", size=10, store=True, tracking=True)
    location = fields.Char('Requested Location', tracking=True)
    contact_person = fields.Char('Contact Person', tracking=True)
    old_box_no = fields.Char('Old Box No.')
    lock_no = fields.Char('Lock No.')
    shop_plot_no = fields.Char('Shop / Plot No.', tracking=True)
    street = fields.Char('Street', tracking=True)
    landmark = fields.Char('Landmark', tracking=True)
    block_floor_office_no = fields.Char('Block / Floor / Office No.', tracking=True)

    installation_date = fields.Date('Installation Date', default=fields.Date.context_today, tracking=True)

    key_issuance = fields.Boolean('Key Issuance')

    complain_center_ids = fields.One2many('donation.box.complain.center', 'donation_box_registration_installation_id', string="Complain Centers")

    status = fields.Selection(selection=status_selection, string='Status', default='draft', tracking=True, copy=False, index=True)
    box_status = fields.Selection(selection=box_status_selection, string="Box Status", default='not_installed', index=True,
                                  tracking=True, copy=False)

    donor_category_ids = fields.Many2many(
        'res.partner.category', string="Donor Categories", compute='_compute_donor_category_ids',
        help="Categories given to a donor created from the donation box screens.")

    # ------------------------------------------------------------------
    # Defaults / computes
    # ------------------------------------------------------------------
    @api.model
    def _default_employee_category_id(self):
        category = self.env.ref('bn_donation_box.installer_hr_employee_category', raise_if_not_found=False)
        return category.id if category else False

    @api.model
    def _get_donor_categories(self):
        categories = self.env['res.partner.category']
        for xmlid in DONOR_CATEGORY_XMLIDS:
            category = self.env.ref(xmlid, raise_if_not_found=False)
            if category:
                categories |= category
        return categories

    def _compute_donor_category_ids(self):
        categories = self._get_donor_categories()
        for rec in self:
            rec.donor_category_ids = categories

    # ------------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('donation_box') or 'New'
        return super().create(vals_list)

    def _bn_locked_fields_by_status(self):
        """Business fields that cannot be edited any more, per status.
        (The form already makes them read-only; this enforces it on the server.)"""
        approved = {
            'shop_name', 'contact_person', 'location', 'shop_plot_no', 'street', 'landmark',
            'block_floor_office_no', 'installation_date', 'installation_category_id',
            'city_id', 'zone_id', 'sub_zone_id', 'donor_id', 'contact_no', 'country_id',
        }
        change_request = {
            'shop_name', 'location', 'shop_plot_no', 'street', 'landmark', 'block_floor_office_no',
            'installation_date', 'installation_category_id', 'city_id', 'zone_id', 'donor_id',
        }
        return {
            'installed': {'location', 'donor_id'},
            'change_request': change_request,
            'available': approved,
        }

    # Fields that may still change on a Closed registration (chatter only).
    _bn_closed_writable_prefixes = ('message_', 'activity_', 'website_message')

    def write(self, vals):
        if not self.env.su and not in_transition():
            immutable = [name for name in self._bn_immutable_fields if name in vals]
            if immutable:
                labels = ', '.join(self._fields[name].string for name in immutable)
                raise UserError(_('The field(s) "%s" are set by the request and cannot be edited.') % labels)
            locked_map = self._bn_locked_fields_by_status()
            touched = set(vals)
            if any(rec.status == 'close' for rec in self):
                business = {name for name in touched
                            if not name.startswith(self._bn_closed_writable_prefixes)}
                if business:
                    raise UserError(_(
                        'A closed registration belongs to a box taken out of service and cannot be '
                        'edited. Create a new request to install a box again.'))
            for rec in self:
                locked = touched & locked_map.get(rec.status, set())
                if locked:
                    labels = ', '.join(self._fields[name].string for name in sorted(locked))
                    raise UserError(_(
                        '"%(labels)s" cannot be edited while the registration is in status "%(status)s".'
                    ) % {'labels': labels, 'status': self._bn_selection_label('status', rec.status)})
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise UserError(_(
                'Registrations cannot be deleted. Use the "Return" button of the request line '
                'or the Complain Center to take a box out of service.'))
        return super().unlink()

    @api.model
    def _bn_find_by_lot(self, lot):
        """The registration of a box number. A box can be reused after it was taken
        out of service, so the registration in service wins over closed ones; when
        every registration is closed, the most recent one is returned."""
        if not lot:
            return self.browse()
        return (self.search([('lot_id', '=', lot.id), ('status', '!=', 'close')], order='id desc', limit=1)
                or self.search([('lot_id', '=', lot.id)], order='id desc', limit=1))

    def _bn_take_out_of_service(self):
        """Close the registration: the box was returned, scrapped or lost."""
        for rec in self.filtered(lambda r: r.status != 'close'):
            vals = {'status': 'close'}
            if rec.box_status == 'installed':
                vals['box_status'] = 'removed'
            rec._bn_write(vals)

    @api.model
    def _bn_setup_removed_box_status(self):
        """Data hook: boxes closed by earlier versions still read "Installed"."""
        self.sudo().search([('status', '=', 'close'), ('box_status', '=', 'installed')]) \
            ._bn_write({'box_status': 'removed'})

    def _bn_check_in_service(self):
        for rec in self:
            if rec.status == 'close':
                raise ValidationError(_(
                    'Box "%(lot)s" was taken out of service (registration %(name)s is Closed).'
                ) % {'lot': rec.lot_id.display_name, 'name': rec.name})

    # ------------------------------------------------------------------
    # Hooks overridden by bn_key_management (the key model lives there)
    # ------------------------------------------------------------------
    def _bn_required_for_install(self):
        return ['shop_name', 'contact_person', 'location', 'shop_plot_no', 'street', 'landmark',
                'block_floor_office_no', 'installation_date', 'installation_category_id',
                'country_id', 'contact_no']

    def _bn_required_for_approval(self):
        return ['city_id', 'zone_id', 'sub_zone_id']

    def _bn_key_create(self, line):
        """Create the key of this registration (bn_key_management)."""
        return False

    def _bn_key_activate(self):
        """Make the key(s) available in the selected bunch (bn_key_management)."""
        return True

    def _bn_key_change_request(self):
        """Validate that the key(s) can be re-assigned (bn_key_management)."""
        return True

    def _bn_key_close(self):
        """Close the key(s) of this registration (bn_key_management)."""
        return True

    def _bn_check_can_release(self):
        """Raise if the box cannot be taken back (key with a rider ...)."""
        return True

    def _bn_unreturned_key_messages(self):
        """Human readable list of keys that still have to be returned."""
        return []

    # ------------------------------------------------------------------
    # Donor
    # ------------------------------------------------------------------
    def _bn_find_or_create_donor(self):
        self.ensure_one()
        Partner = self.env['res.partner']
        categories = self._get_donor_categories()

        donor = Partner
        if self.contact_no:
            donor = Partner.search([
                ('mobile', '=', self.contact_no),
                ('category_id', 'in', categories.ids),
            ], limit=1)
        if not donor:
            # Same shop name, but never re-use a partner that has a different phone number.
            candidates = Partner.search([('name', '=', self.shop_name)])
            donor = candidates.filtered(lambda p: not p.mobile or p.mobile == self.contact_no)[:1]
        if not donor:
            donor = Partner.create({
                'name': self.shop_name,
                'street': self.location,
                'country_code_id': self.country_id.id,
                'mobile': self.contact_no,
                'category_id': [(6, 0, categories.ids)],
            })
        return donor

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_install(self):
        self._bn_require_group(USER_GROUP, ADMIN_GROUP, APPROVE_GROUP)
        self._bn_check_state('status', ('draft',), _('Install'))
        for rec in self:
            rec._bn_check_required(rec._bn_required_for_install())
            donor = rec.donor_id or rec._bn_find_or_create_donor()
            rec._bn_write({
                'donor_id': donor.id,
                'box_status': 'installed',
                'status': 'installed',
            })
        return True

    def action_approved(self):
        self._bn_require_group(APPROVE_GROUP)
        self._bn_check_state('status', ('installed', 'change_request'), _('Approve'))
        for rec in self:
            rec._bn_check_required(rec._bn_required_for_approval())
            rec._bn_key_activate()
            rec._bn_write({'status': 'available'})
        return True

    def action_change_request(self):
        # Closed is final: a registration is only closed once its box was returned,
        # scrapped or reported lost. Installing the box again needs a new request.
        self._bn_require_group(CHANGE_REQUEST_GROUP)
        self._bn_check_state('status', ('available',), _('Change Request'))
        for rec in self:
            rec._bn_key_change_request()
            rec._bn_write({'status': 'change_request'})
        return True

    # -- entry points of the server actions (list view > Action menu) ----
    def install_donation_box(self, records):
        return records.action_install()

    def approve_donation_box(self, records):
        return records.action_approved()

    def populate_lock_no(self, records):
        self._bn_require_group(ADMIN_GROUP, APPROVE_GROUP)
        for rec in records.filtered(lambda r: r.status != 'close'):
            lines = rec.donation_box_request_id.donation_box_request_line_ids.filtered(
                lambda x: x.lot_id == rec.lot_id and not x.is_returned)
            lock_no = lines[:1].lock_no
            if lock_no and lock_no != rec.lock_no:
                rec._bn_write({'lock_no': lock_no})
        return True
