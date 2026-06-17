from odoo import models, fields


donee_registration_selection = [
    ('student', 'Student'),
    ('welfare', 'Welfare'),
    ('medical', 'Medical'),
    ('microfinance', 'Microfinance'),
]

registration_type_selection = [
    ('donee', 'Donee'),
    ('donor', 'Donor'),
]

search_type_selection = [
    ('registration_id', 'Registration ID'),
    ('cnic_no', 'CNIC No.'),
    ('mobile_no', 'Mobile No.'),
]


class ConfirmSearch(models.TransientModel):
    _name = 'confirm.search'
    _description = "Confirm Search"

    registration_id = fields.Char('Registration ID')
    mobile_no = fields.Char('Mobile No.', size=10)
    cnic_no = fields.Char('CNIC No.', size=15)

    country_code_id = fields.Many2one('res.country', string="Country Code")
    microfinance_scheme_id = fields.Many2one(
        'microfinance.scheme',
        string="Microfinance Scheme"
    )

    search_type = fields.Selection(
        selection=search_type_selection,
        string="Search Type",
        default="registration_id"
    )

    donee_registration_type = fields.Selection(
        selection=donee_registration_selection,
        string="Donee Registration Type"
    )

    registration_type = fields.Selection(
        selection=registration_type_selection,
        string="Registration Type",
        default="donee"
    )

    category = fields.Selection(
        selection=[
            ('individual', 'Individual'),
            ('institution', 'Institution')
        ],
        string="Category",
        default="individual"
    )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_categories(self):
        return {
            'donee': self.env.ref(
                'bn_profile_management.donee_partner_category'
            ).id,
            'donor': self.env.ref(
                'bn_profile_management.donor_partner_category'
            ).id,
            'individual': self.env.ref(
                'bn_profile_management.individual_partner_category'
            ).id,
            'institution': self.env.ref(
                'bn_profile_management.coorporate_institute_partner_category'
            ).id,
            'student': self.env.ref(
                'bn_profile_management.student_partner_category'
            ).id,
            'medical': self.env.ref(
                'bn_profile_management.medical_partner_category'
            ).id,
            'welfare': self.env.ref(
                'bn_profile_management.welfare_partner_category'
            ).id,
            'microfinance': self.env.ref(
                'bn_profile_management.microfinance_partner_category'
            ).id,
        }

    def _partner_form_action(
        self,
        res_id=False,
        context=None,
        domain='[]'
    ):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'form',
            'view_id': self.env.ref(
                'bn_profile_management.profile_management_view_form'
            ).id,
            'domain': domain,
            'res_id': res_id,
            'context': context or {},
            'target': 'new',
        }

    def _get_donee_category_ids(self):
        cats = self._get_categories()

        category_ids = [
            cats['donee'],
            cats['individual']
            if self.category == 'individual'
            else cats['institution']
        ]

        if self.donee_registration_type:
            category_ids.append(cats[self.donee_registration_type])

        return category_ids

    # -------------------------------------------------------------------------
    # Donee
    # -------------------------------------------------------------------------

    def return_donee_form(self, donee=None):
        category_ids = self._get_donee_category_ids()

        domain = (
            "[('category_id.name', '=', 'Donee'), "
            "('category_id.name', '=', 'Individual'), "
            "('category_id.name', '=', 'Microfinance')]"
            if self.donee_registration_type == 'microfinance'
            else '[("category_id.name", "in", ["Donee"])]'
        )

        if donee:
            donee.category_id = [(6, 0, category_ids)]
            self.env.cr.commit()

            ctx = {}
            if self.donee_registration_type == 'microfinance':
                ctx['microfinance_scheme_id'] = self.microfinance_scheme_id.id

            return self._partner_form_action(
                res_id=donee.id,
                context=ctx,
                domain=domain
            )

        ctx = {
            'default_category_id': [(6, 0, category_ids)],
            'default_cnic_no': self.cnic_no,
            'default_mobile': self.mobile_no,
            'default_country_code_id': self.country_code_id.id,
        }

        if self.donee_registration_type == 'microfinance':
            ctx['microfinance_scheme_id'] = self.microfinance_scheme_id.id

        return self._partner_form_action(
            context=ctx,
            domain=domain
        )

    # -------------------------------------------------------------------------
    # Donor
    # -------------------------------------------------------------------------

    def _return_donor_form(self, donor=None):
        cats = self._get_categories()

        if donor:
            return self._partner_form_action(
                res_id=donor.id,
                domain='[("category_id.name", "in", ["Donor"])]'
            )

        return self._partner_form_action(
            domain='[("category_id.name", "in", ["Donor"])]',
            context={
                'default_category_id': [
                    (
                        6,
                        0,
                        [cats['donor'], cats['individual']]
                    )
                ],
                'default_cnic_no': self.cnic_no,
                'default_mobile': self.mobile_no,
                'default_country_code_id': self.country_code_id.id,
            }
        )

    # -------------------------------------------------------------------------
    # Main Action
    # -------------------------------------------------------------------------

    def action_confirm(self):
        partner = None

        if self.registration_type == 'donee':

            if self.search_type == 'registration_id':
                partner = self.env['res.partner'].search([
                    ('primary_registration_id', '=', self.registration_id),
                    ('category_id.name', 'in', ['Donee'])
                ], limit=1)

            elif self.search_type == 'cnic_no':
                partner = self.env['res.partner'].search([
                    ('cnic_no', '=', self.cnic_no),
                    ('category_id.name', 'in', ['Donee'])
                ], limit=1)

            else:
                partner = self.env['res.partner'].search([
                    ('country_code_id', '=', self.country_code_id.id),
                    ('mobile', '=', self.mobile_no),
                    ('category_id.name', 'in', ['Donee'])
                ], limit=1)

            return self.return_donee_form(partner)

        # Donor
        if self.search_type == 'registration_id':
            partner = self.env['res.partner'].search([
                ('primary_registration_id', '=', self.registration_id),
                ('category_id.name', 'in', ['Donor'])
            ], limit=1)

        elif self.search_type == 'cnic_no':
            partner = self.env['res.partner'].search([
                ('cnic_no', '=', self.cnic_no),
                ('category_id.name', 'in', ['Donor'])
            ], limit=1)

        else:
            partner = self.env['res.partner'].search([
                ('phone_code_id', '=', self.phone_code_id.id),
                ('mobile', '=', self.mobile_no),
                ('category_id.name', 'in', ['Donor'])
            ], limit=1)

        return self._return_donor_form(partner)