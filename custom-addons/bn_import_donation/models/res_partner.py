import re

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'


    donation_ids = fields.One2many('donation', 'donor_id', string="Donations")
    api_donation_ids = fields.One2many('api.donation', 'donor_id', string="API Donations")

    # ------------------------------------------------------------------
    # Imported donors (Excel import, API donations)
    # ------------------------------------------------------------------
    @api.model
    def _import_normalize_mobile(self, raw, country=None):
        """10 digit mobile (profile rule) or None when it cannot be made one.
        Pakistani numbers lose their 0 / 92 / 0092 prefix (03001234567,
        +923001234567 -> 3001234567); other countries keep their last 10 digits."""
        if raw in (None, False, ''):
            return ''
        if isinstance(raw, float) and raw.is_integer():
            raw = int(raw)
        digits = re.sub(r'\D', '', str(raw))
        if not digits:
            return ''
        pakistan = self.env.ref('base.pk')
        if not country or country == pakistan:
            for prefix in ('0092', '92', '0'):
                if len(digits) > 10 and digits.startswith(prefix):
                    digits = digits[len(prefix):]
            return digits if len(digits) == 10 else None
        return digits[-10:] if len(digits) >= 10 else None

    @api.model
    def _import_normalize_cnic(self, raw):
        """XXXXX-XXXXXXX-X or None when it is not a CNIC."""
        if raw in (None, False, ''):
            return ''
        if isinstance(raw, float) and raw.is_integer():
            raw = int(raw)
        digits = re.sub(r'\D', '', str(raw))
        if len(digits) != 13:
            return None
        return f'{digits[:5]}-{digits[5:12]}-{digits[12:]}'

    @api.model
    def _import_find_partner(self, mobile='', country=None, cnic='', email=''):
        """The one contact of this person: same CNIC, else same mobile + phone
        code, else (only without CNIC and mobile) same email. Never by name:
        two different people can share a name."""
        Partner = self.sudo()
        if cnic:
            partner = Partner.search([('cnic_no', '=', cnic)], limit=1)
            if partner:
                return partner
        if mobile:
            country = country or self.env.ref('base.pk')
            partner = Partner.search([('mobile', '=', mobile), ('country_code_id', '=', country.id)], limit=1)
            if partner:
                return partner
        if email and not cnic and not mobile:
            return Partner.search([('email', '=ilike', email.strip())], limit=1)
        return Partner.browse()

    @api.model
    def _import_find_or_create_partner(self, name, mobile='', country=None, cnic='', email='', tag_ids=()):
        """Return (partner, error). An existing contact gets the missing tags;
        otherwise a new Draft profile is created. Errors (e.g. a constraint of
        Profile Management) are returned instead of aborting the whole import."""
        try:
            with self.env.cr.savepoint():
                partner = self._import_find_partner(mobile, country, cnic, email)
                if partner:
                    missing = [tag for tag in tag_ids if tag not in partner.category_id.ids]
                    if missing:
                        partner.write({'category_id': [(4, tag) for tag in missing]})
                    return partner, ''
                if not (name or mobile or cnic or email):
                    return self.browse(), _('No donor name, mobile, CNIC or email.')
                partner = self.sudo().create({
                    'name': name or _('Donor %s') % (mobile or cnic or email),
                    'mobile': mobile or False,
                    'country_code_id': (country or self.env.ref('base.pk')).id,
                    'cnic_no': cnic or False,
                    'email': email or False,
                    'category_id': [(6, 0, list(tag_ids))],
                })
                return partner, ''
        except (UserError, ValidationError) as error:
            return self.browse(), str(error.args[0] if error.args else error)
