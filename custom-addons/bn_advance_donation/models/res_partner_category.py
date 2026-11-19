import logging

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

DONOR_ACCOUNT_CODE = 'donor_account'
# set once the donors already using Advance Donation were given the tag
DONOR_ACCOUNT_TAGGED_PARAM = 'bn_advance_donation.donor_account_tagged'


def donor_account_domain(model):
    """Donors registered for Advance Donation (Donor + Donor Account tags)."""
    return model.env['res.partner']._tag_domain('donor') + [
        ('category_id.registration_program_code', '=', DONOR_ACCOUNT_CODE)]


class ResPartnerCategory(models.Model):
    _inherit = 'res.partner.category'

    @api.model
    def _setup_donor_account_program(self):
        """Run on every install / upgrade: the "Donor Account" tag is the
        programme of the Advance Donation Record Search (donor side). A tag
        of that name made by hand is reused; an administrator's later changes
        to the tag are kept."""
        tag = self._record_search_program(DONOR_ACCOUNT_CODE)
        if not tag:
            Category = self.sudo()
            tag = Category.search([('name', '=ilike', 'Donor Account'),
                                   ('registration_program_code', '=', False)], limit=1)
            vals = {'registration_program_code': DONOR_ACCOUNT_CODE, 'registration_role': 'donor'}
            if tag:
                tag.write(vals)
            else:
                tag = Category.create(dict(vals, name='Donor Account'))
        self._tag_active_donors(tag)

    @api.model
    def _tag_active_donors(self, tag):
        """Once: the donors who already have an advance donation or a receipt
        get the Donor and Donor Account tags, so they can still be chosen on an
        advance donation. New donors get them from Record Search."""
        params = self.env['ir.config_parameter'].sudo()
        if params.get_param(DONOR_ACCOUNT_TAGGED_PARAM):
            return
        Partner = self.env['res.partner'].sudo()
        donors = Partner
        for model in ('advance.donation', 'advance.donation.receipt'):
            for (partner,) in self.env[model].sudo()._read_group([('donor_id', '!=', False)], ['donor_id']):
                donors |= partner
        tags = tag.sudo() | self.env.ref('bn_profile_management.donor_partner_category')
        tagged, skipped = 0, []
        for partner in donors:
            missing = tags - partner.category_id
            if not missing:
                continue
            try:
                with self.env.cr.savepoint():
                    partner._profile_write({'category_id': [(4, t.id) for t in missing]})
                tagged += 1
            except (UserError, ValidationError) as error:
                # e.g. a duplicate person: left for Record Search
                skipped.append('%s (%s): %s' % (partner.display_name, partner.id, error.args[0]))
        _logger.info('Donor Account: %s existing donors tagged.', tagged)
        if skipped:
            _logger.warning('Donor Account: %s donors not tagged, use Record Search for them:\n%s',
                            len(skipped), '\n'.join(skipped))
        params.set_param(DONOR_ACCOUNT_TAGGED_PARAM, fields.Datetime.now())
