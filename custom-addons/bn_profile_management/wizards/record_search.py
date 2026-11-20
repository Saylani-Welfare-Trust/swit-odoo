from odoo import _, models, fields, api
from odoo.exceptions import UserError, ValidationError

import re

cnic_pattern = r'^\d{5}-\d{7}-\d{1}$'


donee_registration_selection = [
    ('student', 'Student'),
    ('welfare', 'Welfare'),
    ('microfinance', 'Microfinance'),
    ('medical', 'Medical'),
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


class RecordSearch(models.TransientModel):
    _name = 'record.search'
    _description = "Record Search"


    registration_id = fields.Char('Registration ID')
    mobile_no = fields.Char('Mobile No.', size=10)
    cnic_no = fields.Char('CNIC No.', size=15)
    
    country_code_id = fields.Many2one('res.country', string="Country Code")
    microfinance_scheme_id = fields.Many2one('microfinance.scheme', string="Microfinance Scheme")

    search_type = fields.Selection(selection=search_type_selection, string="Search Type", default="registration_id")
    donee_registration_type = fields.Selection(selection=donee_registration_selection, string="Donee Registration Type")
    registration_type = fields.Selection(selection=registration_type_selection, string="Registration Type", default="donee")

    # The programme to register for: a tag with a Record Search code. A
    # module's Record Search menu passes its code (default_program_code), e.g.
    # Sadqa e Jariya. The other menus keep using donee_registration_type.
    program_id = fields.Many2one(
        'res.partner.category', string='Register For',
        domain="[('registration_program_code', '!=', False), ('registration_program_active', '=', True), "
               "('registration_role', '=', registration_type)]")
    program_kind = fields.Selection(related='program_id.registration_kind')
    program_locked = fields.Boolean('Programme set by the menu')

    is_welfare = fields.Boolean('Is Welfare')
    is_medical = fields.Boolean('Is Medical')
    is_microfinance = fields.Boolean('Is Microfinance')
    category = fields.Selection(selection=[('individual', 'Individual'), ('institution', 'Institution')], string="Category", default="individual")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        code = self.env.context.get('default_program_code')
        if not code:
            return res
        program = self.env['res.partner.category']._record_search_program(code)
        if not program:
            raise UserError(_('No tag has the Record Search code "%s": upgrade the module of this '
                              'programme.') % code)
        if not program.registration_program_active:
            raise UserError(_('The programme "%s" is disabled.') % program.name)
        res['program_id'] = program.id
        res['registration_type'] = program.registration_role
        res['program_locked'] = True
        if program.registration_kind != 'choose':
            res['category'] = program.registration_kind
        return res

    @api.onchange('registration_type')
    def _onchange_registration_type(self):
        if self.program_id and self.program_id.registration_role != self.registration_type:
            self.program_id = False

    @api.onchange('program_id')
    def _onchange_program_id(self):
        if self.program_id.registration_kind in ('individual', 'institution'):
            self.category = self.program_id.registration_kind


    @api.constrains('cnic_no')
    def _check_cnic_format(self):
        for record in self:
            if record.cnic_no:
                if not re.match(cnic_pattern, record.cnic_no):
                    raise ValidationError("Invalid CNIC format. Please use XXXXX-XXXXXXX-X")
                parts = record.cnic_no.split('-')
                if len(parts[0]) != 5 or len(parts[1]) != 7 or len(parts[2]) != 1:
                    raise ValidationError("Invalid CNIC format. Ensure the parts have the correct number of digits.")

    def is_valid_cnic_format(self, cnic):
        return bool(re.fullmatch(r'\d{5}-\d{7}-\d', cnic))

    @api.onchange('cnic_no')
    def _onchange_cnic_no(self):
        if self.cnic_no and self.search_type == 'cnic_no':
            cleaned_cnic = re.sub(r'[^0-9]', '', self.cnic_no)
            if len(cleaned_cnic) >= 13:
                self.cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:12]}-{cleaned_cnic[12:]}"
            elif len(cleaned_cnic) > 5:
                self.cnic_no = f"{cleaned_cnic[:5]}-{cleaned_cnic[5:]}"
            
            if not self.is_valid_cnic_format(self.cnic_no):
                raise ValidationError('Invalid CNIC No. format ( acceptable format XXXXX-XXXXXXX-X )')

    def action_search(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Confirmation',
            'res_model': 'confirm.search',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_profile_management.confirm_search_view_form').id,
            'context': {
                'default_search_type': self.search_type,
                'default_registration_id': self.registration_id,
                'default_country_code_id': self.country_code_id.id,
                'default_mobile_no': self.mobile_no,
                'default_cnic_no': self.cnic_no,
                'default_registration_type': self.registration_type,
                'default_donee_registration_type': self.donee_registration_type,
                'default_program_id': self.program_id.id,
                'default_microfinance_scheme_id': self.microfinance_scheme_id.id,
                'default_category': self.category,
                # carried on to the profile popup, see action_change_request
                'from_record_search': True,
                'is_welfare': self.is_welfare,
                'is_microfinance': self.is_microfinance,
                
            },
            'target': 'new',
        }