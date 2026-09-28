from . import models
from . import wizards
from . import reports


def post_init_hook(env):
    """Seed the Profile Management configuration for the two tags that already
    have hand-built screens today (Donor, Donee), mirroring their current
    hardcoded visibility exactly, so behaviour is unchanged right after
    upgrading - and, from then on, both are fully admin-configurable like any
    other tag.
    """
    Field = env['ir.model.fields']
    Page = env['profile.management.page']

    def field_ids(names):
        return Field.search([('model', '=', 'res.partner'), ('name', 'in', names)]).ids

    def page_ids(technical_names):
        return Page.search([('technical_name', 'in', technical_names)]).ids

    from .models.res_partner_category import CURATED_PROFILE_FIELDS
    all_curated = field_ids(CURATED_PROFILE_FIELDS)

    donor = env.ref('bn_profile_management.donor_partner_category', raise_if_not_found=False)
    if donor and not donor.is_profile_type:
        action = env.ref('bn_profile_management.donor_profile_management_action', raise_if_not_found=False)
        menu = env.ref('bn_profile_management.donor_profile_management_menu', raise_if_not_found=False)
        donor.write({
            'is_profile_type': True,
            'profile_list_field_ids': [(6, 0, all_curated)],
            'profile_form_field_ids': [(6, 0, all_curated)],
            'profile_search_field_ids': [(6, 0, all_curated)],
            'profile_page_ids': [(6, 0, page_ids(['general_info', 'donation']))],
            # Already has a hand-built menu/action - point config at it so the
            # write-triggered sync updates it in place instead of creating a
            # duplicate (sync only creates a new one when this is empty).
            'profile_action_id': action.id if action else False,
            'profile_menu_id': menu.id if menu else False,
        })

    donee = env.ref('bn_profile_management.donee_partner_category', raise_if_not_found=False)
    if donee and not donee.is_profile_type:
        action = env.ref('bn_profile_management.donee_profile_management_action', raise_if_not_found=False)
        menu = env.ref('bn_profile_management.donee_profile_management_menu', raise_if_not_found=False)
        donee.write({
            'is_profile_type': True,
            'profile_list_field_ids': [(6, 0, all_curated)],
            'profile_form_field_ids': [(6, 0, all_curated)],
            'profile_search_field_ids': [(6, 0, all_curated)],
            'profile_page_ids': [(6, 0, page_ids(['general_info', 'welfare', 'microfinance', 'medical']))],
            'profile_action_id': action.id if action else False,
            'profile_menu_id': menu.id if menu else False,
        })
