from odoo import models, fields


class SadqaJariyaMasjid(models.Model):
    _name = 'sadqa.jariya.masjid'
    _description = 'Masjid Application Details'

    application_id = fields.Many2one('sadqa.jariya', string='Application', required=True, ondelete='cascade')

    # Masjid Inquiry Form (مساجد انکوائری فارم)
    # General Information
    date = fields.Date(string='Date')
    masjid_name = fields.Char(string='Masjid Name')
    address = fields.Text(string='Address')
    imam_name = fields.Char(string='Imam Name')
    imam_contact = fields.Char(string='Imam Contact No.')
    mutawalli_name = fields.Char(string='Mutawalli Name')
    mutawalli_contact = fields.Char(string='Mutawalli Contact No.')
    account_title = fields.Char(string='Account Title')
    account_number = fields.Char(string='Account Number')
    account_cnic = fields.Char(string='Account CNIC')

    # Masjid Statistics
    masjid_area = fields.Char(string='Masjid Area')
    constructed_area = fields.Char(string='Constructed Area')
    current_support = fields.Char(string='Current Support')

    # Number of Worshippers
    people_in_jamat_fajr = fields.Integer(string='People in Jamat for Fajr')
    people_in_jamat_zuhr = fields.Integer(string='People in Jamat for Zuhr')
    people_in_jamat_asr = fields.Integer(string='People in Jamat for Asr')
    people_in_jamat_maghrib = fields.Integer(string='People in Jamat for Maghrib')
    people_in_jamat_isha = fields.Integer(string='People in Jamat for Isha')
    people_in_jamat_jumma = fields.Integer(string='People in Jamat for Jumma')

    # Education & Dars
    dars_schedule = fields.Char(string='Dars Schedule')
    book_name = fields.Char(string='Book Name')
    participants_count = fields.Integer(string='Dars Participants')

    # Number of Students
    students_nazra = fields.Integer(string='Nazra Students')
    students_hifz = fields.Integer(string='Hifz Students')
    students_adults = fields.Integer(string='Adult Students')
    students_total = fields.Integer(string='Total Students')

    # Financial & Miscellaneous
    imam_other_engagements = fields.Text(string="Imam's Other Engagements")
    other_income_sources = fields.Text(string='Government / Other Income Sources')
    monthly_masjid_support = fields.Float(string='Monthly Support by Masjid')

    # Masjid form key in the portal export (institutional contract) -> field
    _portal_form_fields = {
        'date': 'date',
        'masjidName': 'masjid_name',
        'address': 'address',
        'imamName': 'imam_name',
        'imamContact': 'imam_contact',
        'mutawalliName': 'mutawalli_name',
        'mutawalliContact': 'mutawalli_contact',
        'accountTitle': 'account_title',
        'accountNumber': 'account_number',
        'cnicNumber': 'account_cnic',
        'masjidArea': 'masjid_area',
        'constructedArea': 'constructed_area',
        'currentSupport': 'current_support',
        'worshippersFajr': 'people_in_jamat_fajr',
        'worshippersDhuhr': 'people_in_jamat_zuhr',
        'worshippersAsr': 'people_in_jamat_asr',
        'worshippersMaghrib': 'people_in_jamat_maghrib',
        'worshippersIsha': 'people_in_jamat_isha',
        'worshippersJumuah': 'people_in_jamat_jumma',
        'darsSchedule': 'dars_schedule',
        'bookName': 'book_name',
        'participantsCount': 'participants_count',
        'studentsNazra': 'students_nazra',
        'studentsHifz': 'students_hifz',
        'studentsAdults': 'students_adults',
        'studentsTotal': 'students_total',
        'imamOtherEngagements': 'imam_other_engagements',
        'otherIncomeSources': 'other_income_sources',
        'monthlyMasjidSupport': 'monthly_masjid_support',
    }
