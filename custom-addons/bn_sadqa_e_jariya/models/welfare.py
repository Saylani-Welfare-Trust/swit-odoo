from odoo import models, fields


class Welfare(models.Model):
    _inherit = 'welfare'

    institution_category = fields.Selection([
        ('masjid', 'Masjid'),
        ('madrasa', 'Madrasa'),
    ], string='Institution Category')

    subcategory = fields.Char(string='Subcategory')

    # Relationships
    committee_member_ids = fields.One2many(
        'welfare.committee.member',
        'welfare_id',
        string='Committee Members'
    )

    teacher_ids = fields.One2many(
        'welfare.teacher',
        'welfare_id',
        string='Teachers'
    )

    inquiry_report_ids = fields.One2many(
        'welfare.inquiry.report',
        'welfare_id',
        string='Inquiry Reports'
    )

    masjid_id = fields.One2many(
        'welfare.masjid',
        'welfare_id',
        string='Masjid Details'
    )

    madrasa_id = fields.One2many(
        'welfare.madrasa',
        'welfare_id',
        string='Madrasa Details'
    )

    def _parse_form_data(self, rec):
        """Parse form data based on category"""
        form_data = rec.get('form', {})
        category = rec.get('category')
        subcategory = rec.get('subCategory')

        data = {
            'institution_category': category,
            'subcategory': subcategory,
        }

        if category == 'masjid':
            data.update(self._parse_masjid_data(form_data))
        elif category == 'madrasa':
            data.update(self._parse_madrasa_data(form_data))

        return data

    def _parse_masjid_data(self, form_data):
        """Parse masjid specific data"""
        masjid_info = form_data.get('masjidInfo', {})
        prayers_info = form_data.get('prayersInfo', {})
        fund_info = form_data.get('fundInfo', {})
        account_details = form_data.get('accountDetails', {})

        return {
            'institute_name': masjid_info.get('masjidName'),
            'company_address': masjid_info.get('address'),
            'city': masjid_info.get('city'),
            'district': masjid_info.get('district'),
        }

    def _parse_madrasa_data(self, form_data):
        """Parse madrasa specific data"""
        madrasa_info = form_data.get('madrasaInfo', {})
        fund_info = form_data.get('fundInfo', {})
        account_details = form_data.get('accountDetails', {})

        return {
            'institute_name': madrasa_info.get('madarsaName'),
            'company_address': madrasa_info.get('address'),
            'city': madrasa_info.get('city'),
            'district': madrasa_info.get('district'),
        }
