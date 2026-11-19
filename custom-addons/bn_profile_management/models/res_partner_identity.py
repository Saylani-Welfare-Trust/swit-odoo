# -*- coding: utf-8 -*-
import re

from odoo import api, models


class ResPartner(models.Model):
    """Finding the existing contact of a person (CNIC, Registration ID or
    mobile with its phone code), so a programme reuses it and only adds its
    tags instead of creating a second contact."""
    _inherit = 'res.partner'

    @api.model
    def _normalize_mobile(self, mobile):
        """The 10-digit form stored on contacts (3001234567): drops spaces,
        dashes, a leading 0 or the country code."""
        digits = re.sub(r'\D', '', mobile or '')
        return digits[-10:] if len(digits) >= 10 else (mobile or '').strip()

    @api.model
    def _find_person(self, mobile=None, country=None, cnic=None, registration_id=None):
        """The existing contact of a person: by CNIC, then Registration ID,
        then mobile + phone code. Empty when none."""
        Partner = self.sudo().with_context(active_test=True)
        if cnic:
            partner = Partner.search([('cnic_no', '=', cnic.strip())], limit=1)
            if partner:
                return partner.sudo(False)
        if registration_id:
            code = registration_id.strip()
            partner = Partner.search(['|', ('primary_registration_id', '=', code),
                                      ('secondary_registration_id', '=', code)], limit=1)
            if partner:
                return partner.sudo(False)
        if mobile:
            country_id = country.id if hasattr(country, 'id') else country
            partner = Partner.search([
                ('mobile', '=', self._normalize_mobile(mobile)), ('parent_id', '=', False),
                ('country_code_id', '=', country_id or self.env.ref('base.pk').id)], limit=1)
            if partner:
                return partner.sudo(False)
        return self.browse()

    def _add_person_tags(self, tags):
        """Give an existing person the tags of a new role / programme (never
        removes any)."""
        tag_ids = tags.ids if hasattr(tags, 'ids') else list(tags or [])
        for partner in self:
            missing = [tag for tag in tag_ids if tag not in partner.category_id.ids]
            if missing:
                partner.sudo().write({'category_id': [(4, tag) for tag in missing]})

    @api.model
    def _find_or_create_person(self, vals, tags=()):
        """The contact of the person described by ``vals``: the existing one
        (with the missing ``tags`` added), else a new one."""
        vals = dict(vals)
        if vals.get('mobile'):
            vals['mobile'] = self._normalize_mobile(vals['mobile'])
        partner = self._find_person(mobile=vals.get('mobile'), country=vals.get('country_code_id'),
                                    cnic=vals.get('cnic_no'))
        if partner:
            partner._add_person_tags(tags)
            return partner
        tag_ids = tags.ids if hasattr(tags, 'ids') else list(tags or [])
        if tag_ids:
            vals['category_id'] = [(6, 0, list(set(tag_ids) | set(self._category_ids_of(vals))))]
        return self.create(vals)

    @api.model
    def _category_ids_of(self, vals):
        ids = set()
        for command in vals.get('category_id') or []:
            if isinstance(command, (list, tuple)) and command[0] == 6:
                ids |= set(command[2])
            elif isinstance(command, (list, tuple)) and command[0] == 4:
                ids.add(command[1])
        return ids
