from odoo import models, fields

# Flood Inquiry Institute Form keys sent by the portal, same as the field names
FLOOD_FORM_KEYS = (
    'form_date', 'app_date',
    'institute_name', 'address', 'mohtamim_mutawalli', 'contact_number', 'short_intro',
    'count_oula', 'count_sania', 'count_salisa', 'count_rabia', 'count_khamisa', 'count_sadisa', 'count_dawra',
    'count_nazra', 'count_hifz', 'count_tajweed', 'count_others', 'count_residential', 'count_non_residential',
    'total_students',
    'attendance_fajr', 'attendance_dhuhr', 'attendance_asr', 'attendance_maghrib', 'attendance_isha',
    'attendance_jummah', 'attendance_eidain',
    'status_before_flood', 'status_after_flood',
    'total_estimate', 'estimate_iron_steel', 'estimate_cement', 'estimate_labor', 'current_work', 'remaining_work',
    'officer_report', 'officer_name', 'officer_contact', 'final_decision',
)


class WelfareFlood(models.Model):
    _name = 'welfare.flood'
    _description = 'Flood Affected Institute Application Details'

    welfare_id = fields.Many2one('welfare', string='Welfare Application', required=True, ondelete='cascade')

    # Header
    form_date = fields.Date(string='Form Date')
    app_date = fields.Date(string='Application Date')

    # Institute Information
    institute_name = fields.Char(string='Institute Name')
    address = fields.Text(string='Address')
    mohtamim_mutawalli = fields.Char(string='Mohtamim / Mutawalli')
    contact_number = fields.Char(string='Contact Number')
    short_intro = fields.Text(string='Short Introduction')

    # Madaris Information
    count_oula = fields.Integer(string='Oula')
    count_sania = fields.Integer(string='Sania')
    count_salisa = fields.Integer(string='Salisa')
    count_rabia = fields.Integer(string='Rabia')
    count_khamisa = fields.Integer(string='Khamisa')
    count_sadisa = fields.Integer(string='Sadisa')
    count_dawra = fields.Integer(string='Dawra')
    count_nazra = fields.Integer(string='Nazra')
    count_hifz = fields.Integer(string='Hifz')
    count_tajweed = fields.Integer(string='Tajweed')
    count_others = fields.Integer(string='Others')
    count_residential = fields.Integer(string='Residential')
    count_non_residential = fields.Integer(string='Non-Residential')
    total_students = fields.Integer(string='Total Students')

    # Masajid Information
    attendance_fajr = fields.Integer(string='Fajr')
    attendance_dhuhr = fields.Integer(string='Dhuhr')
    attendance_asr = fields.Integer(string='Asr')
    attendance_maghrib = fields.Integer(string='Maghrib')
    attendance_isha = fields.Integer(string='Isha')
    attendance_jummah = fields.Integer(string='Jummah')
    attendance_eidain = fields.Integer(string='Eidain')

    # Flood Assessment
    status_before_flood = fields.Text(string='Before the Flood')
    status_after_flood = fields.Text(string='After the Flood')

    # Construction Details
    total_estimate = fields.Float(string='Total Estimate')
    estimate_iron_steel = fields.Float(string='Iron / Steel')
    estimate_cement = fields.Float(string='Cement')
    estimate_labor = fields.Float(string='Labor')
    current_work = fields.Text(string='Current Work')
    remaining_work = fields.Text(string='Remaining Work')

    # Official Inquiry & Decision
    officer_report = fields.Text(string='Inquiry Officer Report')
    officer_name = fields.Char(string='Inquiry Officer Name')
    officer_contact = fields.Char(string='Inquiry Officer Contact')
    final_decision = fields.Text(string='Final Decision')

    _portal_form_fields = {key: key for key in FLOOD_FORM_KEYS}
