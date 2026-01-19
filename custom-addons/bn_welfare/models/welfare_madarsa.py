from odoo import models, fields, api

class WelfareMadrasa(models.Model):
    _name = 'welfare.madrasa'
    _description = 'Madrasa Application Details'
    
    welfare_id = fields.Many2one('welfare', string='Welfare Application', required=True, ondelete='cascade')
    
    # Madrasa Info
    madarsa_name = fields.Char(string='Madrasa Name')
    city = fields.Char(string='City')
    district = fields.Char(string='District')
    total_teaching_staff = fields.Integer(string='Total Teaching Staff')
    total_salary_teaching_staff = fields.Float(string='Total Salary for Teaching Staff')
    total_non_teaching_staff = fields.Integer(string='Total Non-Teaching Staff')
    total_salary_non_teaching_staff = fields.Float(string='Total Salary for Non-Teaching Staff')
    location_link = fields.Char(string='Location Link')
    address = fields.Text(string='Address')
    tanzeem_ilhaaq = fields.Char(string='Tanzeem Ilhaaq')
    other_tanzeem_name = fields.Char(string='Other Tanzeem Name')
    province = fields.Char(string='Province')
    
    # Registration Info
    established_since = fields.Char(string='Established Since')
    ilhaaq_no = fields.Char(string='Ilhaaq No')
    registration_number = fields.Char(string='Registration Number')
    ilhaq_docs_pictures = fields.Text(string='Ilhaq Documents Pictures URLs')
    
    # Students Information
    non_resident_students = fields.Integer(string='Non-Resident Students')
    resident_students = fields.Integer(string='Resident Students')
    resident_nazra_students = fields.Integer(string='Resident Nazra Students')
    non_resident_nazra_students = fields.Integer(string='Non-Resident Nazra Students')
    resident_hifz_students = fields.Integer(string='Resident Hifz Students')
    non_resident_hifz_students = fields.Integer(string='Non-Resident Hifz Students')
    
    # Classes
    classes_oola = fields.Boolean(string='Classes Oola')
    classes_saania = fields.Boolean(string='Classes Saania')
    classes_salisa = fields.Boolean(string='Classes Salisa')
    classes_rabia = fields.Boolean(string='Classes Rabia')
    classes_khameesa = fields.Boolean(string='Classes Khameesa')
    classes_sadisa = fields.Boolean(string='Classes Sadisa')
    classes_dora_hadees = fields.Boolean(string='Classes Dora Hadees')
    classes_takhassus = fields.Boolean(string='Classes Takhassus')
    
    # Student Counts
    total_oola_students = fields.Integer(string='Total Oola Students')
    total_saania_students = fields.Integer(string='Total Saania Students')
    total_salisa_students = fields.Integer(string='Total Salisa Students')
    total_rabia_students = fields.Integer(string='Total Rabia Students')
    total_khameesa_students = fields.Integer(string='Total Khameesa Students')
    total_sadisa_students = fields.Integer(string='Total Sadisa Students')
    total_dora_hadees_students = fields.Integer(string='Total Dora Hadees Students')
    total_takhassus_students = fields.Integer(string='Total Takhassus Students')
    
    # Aims & Objectives
    objective_text = fields.Text(string='Aims and Objectives')
    
    # Construction Info (for madrasa-construction)
    area_of_madarsa = fields.Char(string='Area of Madrasa')
    value_amount_of_land_area = fields.Char(string='Value Amount of Land')
    constructed_area_estimate = fields.Char(string='Constructed Area Estimate')
    type_of_work = fields.Char(string='Type of Work')
    
    # Construction Details
    construction_iron_rods = fields.Char(string='Iron Rods')
    construction_cement_sacks = fields.Char(string='Cement Sacks')
    construction_labour_wage = fields.Char(string='Labour/Wage per Sq. Ft.')
    construction_explain_other = fields.Text(string='Explain Other Material')
    
    # Construction Pictures
    constructed_area_pictures = fields.Text(string='Constructed Area Pictures URLs')
    land_documents_pictures = fields.Text(string='Land Documents Pictures URLs')
    
    # Fund Info
    current_fund_of_madarsa = fields.Float(string='Current Fund of Madrasa')
    monthly_fund_collection = fields.Float(string='Monthly Fund Collection')
    expected_amount_from_saylani = fields.Float(string='Expected Amount from Saylani')
    ever_received_from_saylani = fields.Boolean(string='Ever Received from Saylani')
    amount_received_from_saylani = fields.Float(string='Amount Received from Saylani')
    ever_received_from_ngo = fields.Boolean(string='Ever Received from NGO')
    amount_received_from_ngo = fields.Float(string='Amount Received from NGO')
    
    # Other Help Info (for madarsa-others)
    other_help_info = fields.Text(string='Other Help Info')
    
    # Account Details
    account_cnic = fields.Char(string='Account CNIC')
    account_title = fields.Char(string='Account Title')
    account_number = fields.Char(string='Account Number')
    account_type = fields.Char(string='Account Type')

    subcategory = fields.Char(string='Subcategory')