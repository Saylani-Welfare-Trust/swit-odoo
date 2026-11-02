from odoo import models, fields, api

class WelfareMasjid(models.Model):
    _name = 'welfare.masjid'
    _description = 'Masjid Application Details'
    
    welfare_id = fields.Many2one('welfare', string='Welfare Application', required=True, ondelete='cascade')
    
    # Masjid Info
    masjid_name = fields.Char(string='Masjid Name')
    city = fields.Char(string='City')
    district = fields.Char(string='District')
    total_number_of_staff = fields.Integer(string='Total Number of Staff')
    total_salary_expense_for_staff = fields.Float(string='Total Salary Expense for Staff')
    location_link = fields.Char(string='Location Link')
    address = fields.Text(string='Address')
    province = fields.Char(string='Province')
    masjid_pictures = fields.Text(string='Masjid Picture URLs')
    
    # Prayers Info
    fajr = fields.Boolean(string='Fajr')
    zuhr = fields.Boolean(string='Zuhr')
    asr = fields.Boolean(string='Asr')
    maghrib = fields.Boolean(string='Maghrib')
    isha = fields.Boolean(string='Isha')
    jumma = fields.Boolean(string='Jumma')
    people_in_jamat_jumma = fields.Integer(string='People in Jamat for Jumma')
    people_in_jamat_fajr = fields.Integer(string='People in Jamat for Fajr')
    people_in_jamat_zuhr = fields.Integer(string='People in Jamat for Zuhr')
    people_in_jamat_asr = fields.Integer(string='People in Jamat for Asr')
    people_in_jamat_maghrib = fields.Integer(string='People in Jamat for Maghrib')
    people_in_jamat_isha = fields.Integer(string='People in Jamat for Isha')
    
    # Construction Info (for masjid-construction)
    area_of_masjid = fields.Float(string='Area of Masjid')
    constructed_area_of_masjid = fields.Float(string='Constructed Area of Masjid')
    value_amount_of_land = fields.Float(string='Value Amount of Land')
    remaining_work = fields.Text(string='Remaining Work')
    
    # Construction Details
    iron_rods = fields.Char(string='Iron Rods')
    cement_sacks = fields.Char(string='Cement Sacks')
    labour_wage_per_sqft = fields.Char(string='Labour/Wage per Sq. Ft.')
    explain_other_material = fields.Text(string='Explain Other Material')
    
    # Construction Pictures
    constructed_area_pictures = fields.Text(string='Constructed Area Pictures URLs')
    land_documents_pictures = fields.Text(string='Land Documents Pictures URLs')
    
    # Expenditure Info (for masjid-wages)
    monthly_fund_of_masjid = fields.Float(string='Monthly Fund of Masjid')
    func_of_masjid_from_boxes = fields.Float(string='Func of Masjid from Boxes')
    shops_within_masjid_premises = fields.Boolean(string='Shops within Masjid Premises')
    total_expenditure = fields.Float(string='Total Expenditure')
    
    # Fund Info
    expected_amount_from_saylani = fields.Float(string='Expected Amount from Saylani')
    ever_received_from_saylani = fields.Boolean(string='Ever Received from Saylani')
    amount_received_from_saylani = fields.Float(string='Amount Received from Saylani')
    ever_received_from_ngo = fields.Boolean(string='Ever Received from NGO')
    amount_received_from_ngo = fields.Float(string='Amount Received from NGO')
    
    # Other Help Info (for masjid-others)
    other_help_info = fields.Text(string='Other Help Info')
    
    # Account Details
    account_cnic = fields.Char(string='Account CNIC')
    account_title = fields.Char(string='Account Title')
    account_number = fields.Char(string='Account Number')
    account_type = fields.Char(string='Account Type')
    
    subcategory = fields.Char(string='Subcategory')