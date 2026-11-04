from odoo import models, fields

from .portal_keys import camel_key

# Construction form fields, the portal export sends them camelCased (form_date -> formDate)
CONSTRUCTION_FORM_FIELDS = (
    'form_date', 'app_date', 'institute_name', 'address', 'admin_name', 'admin_contact', 'admin_qualification',
    'is_committee', 'is_trust', 'trust_name',
    'has_waqf_deed', 'site_price', 'total_area', 'constructed_area', 'capacity_musalli', 'capacity_students',
    'population_area', 'actual_attendance', 'closest_masjid', 'closest_madrasah', 'maslak', 'economic_status',
    'students_dars_nizami', 'students_hifz', 'students_tajweed', 'students_nazra', 'students_residential',
    'students_day_scholars', 'total_students',
    'total_estimate', 'cost_iron_steel', 'cost_cement', 'cost_labor', 'current_work', 'remaining_work',
)


class SadqaJariyaConstruction(models.Model):
    _name = 'sadqa.jariya.construction'
    _description = 'Construction Application Details'

    application_id = fields.Many2one('sadqa.jariya', string='Application', required=True, ondelete='cascade')

    # Basic Information
    form_date = fields.Date(string='Form Date')
    app_date = fields.Date(string='Application Date')
    institute_name = fields.Char(string='Institute Name')
    address = fields.Text(string='Address')
    admin_name = fields.Char(string='Mohtamim / Administrator')
    admin_contact = fields.Char(string='Contact')
    admin_qualification = fields.Char(string='Educational Qualification')
    is_committee = fields.Boolean(string='Committee Formed')
    is_trust = fields.Boolean(string='Registered Trust')
    trust_name = fields.Char(string='Trust Name')

    # Site Details
    has_waqf_deed = fields.Boolean(string='Waqf Deed of the Site')
    site_price = fields.Float(string='Site Price')
    total_area = fields.Char(string='Total Area')
    constructed_area = fields.Char(string='Constructed Area')
    capacity_musalli = fields.Integer(string='Capacity (Musalli)')
    capacity_students = fields.Integer(string='Capacity (Students)')
    population_area = fields.Char(string='Population')
    actual_attendance = fields.Integer(string='Actual Attendance')
    closest_masjid = fields.Char(string='Closest Masjid')
    closest_madrasah = fields.Char(string='Closest Madrasah')
    maslak = fields.Char(string='Maslak')
    economic_status = fields.Char(string='Economic Status')

    # Student & Worshipper Breakdown
    students_dars_nizami = fields.Integer(string='Dars-e-Nizami')
    students_hifz = fields.Integer(string='Hifz')
    students_tajweed = fields.Integer(string='Tajweed')
    students_nazra = fields.Integer(string='Nazra')
    students_residential = fields.Integer(string='Residential')
    students_day_scholars = fields.Integer(string='Day Scholars')
    total_students = fields.Integer(string='Total Students')

    # Construction Details
    total_estimate = fields.Float(string='Total Estimate')
    cost_iron_steel = fields.Float(string='Iron / Steel')
    cost_cement = fields.Float(string='Cement')
    cost_labor = fields.Float(string='Labor')
    current_work = fields.Text(string='Current Work')
    remaining_work = fields.Text(string='Remaining Work')

    _portal_form_fields = {camel_key(name): name for name in CONSTRUCTION_FORM_FIELDS}
