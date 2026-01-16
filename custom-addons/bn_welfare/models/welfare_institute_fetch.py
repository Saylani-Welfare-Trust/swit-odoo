from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
# import pyrequests
import base64
import logging
import json


class WelfareInstitutionFetchLog(models.Model):

    _name = 'welfare.institution.fetch.log'
    _description = 'Institution Application Fetch Log'
    _order = 'fetch_date desc'

    fetch_date = fields.Datetime('Fetch Date', default=fields.Datetime.now, readonly=True)
    record_count = fields.Integer('Records Fetched', readonly=True)
    record_ids = fields.Many2many('welfare', 'welfare_fetch_log_rel', 'log_id', 'welfare_id', string='Fetched Welfare Records')
    sync = fields.Boolean('Sync')
    
    def send_welfare_sync_to_portal(self, welfare_record, endpoint_url, auth_key):
        """Send applicationId and odooId to the portal endpoint for a welfare record."""
        payload = {
            "applicationId": welfare_record.old_system_id,
            "odooId": str(welfare_record.id)
        }
        data = json.loads(json.dumps(payload, default=str))

        headers = {
            'x-odoo-auth-key': auth_key,
            'Content-Type': 'application/json'
        }
        # raise UserError(f"Payload: {data} headers: {headers} endpoint: {endpoint_url}")
        try:

            response = requests.post(endpoint_url, json=data, headers=headers, timeout=30)
            response.raise_for_status()
            # raise UserError(f"Response: {response.text} only data {response.json().get('data', [])}")
            # return {'_id': '68df61d0de766806173de562', 'syncedToOdoo': True, 'category': 'masjid', 'subCategory': 'masjid-wages', 'province': 'Punjab', 'form': {'category': 'masjid', 'subcategory': 'masjid-wages', 'applicantInformation': {'name': 'Ipsa ullam nulla am', 'designation': 'Voluptate iste omnis', 'phoneNumber': 'Eaque unde modi veli', 'whatsappNumber': 'Ad sed veritatis qui', 'applicantLocationLink': 'https://www.nad.ca'}, 'committeeMembers': [{}, {}, {}], 'masjidInfo': {'masjidName': 'TEST_MASJID_RECORD_2', 'city': 'Ullamco fuga Conseq', 'district': 'Sint quibusdam sit ', 'totalNummberOfStaff': '40', 'totalSalaryExpenseForStaff': '47', 'locationLink': 'https://www.hyrudexat.ws', 'address': 'Ut dolor enim soluta', 'province': 'Punjab'}, 'prayersInfo': {'fajr': 'Yes', 'zuhr': 'No', 'asr': 'Yes', 'maghrib': 'No', 'isha': 'Yes', 'jumma': 'No'}, 'expenditureInfo': {'monthlyFundOfMasjid': '9', 'funcofmajidFromBoxes': '74', 'shopswithinMasjidPremises': 'No', 'totalexpenditure': '14'}, 'fundInfo': {'howMuchamountareyouexpectingfromSaylani': '33', 'everReceivedFromSaylani': 'No', 'everReceivedFromNGO': 'Yes', 'amountReceivedFromNGO': '23'}, 'accountDetails': {'accountCnic': 'Ut non ex laudantium', 'accountTitle': 'Temporibus consequat', 'accountNumber': 'Irure dolor providen', 'accountType': 'UBL OMNI'}}, 'status': 'hod-review', 'token': 'PUN-20251003-0037', 'inquiryReport': {'images': [], 'verified': False}, 'submittedBy': '68beab1622daff30a9a44ad7', 'lastUpdatedBy': '68beab1622daff30a9a44ad7', 'inquiryReports': [{'status': 'completed', 'images': [], 'verified': False, 'officerId': '68e4da8dd497ae9e1660e445', '_id': '68df6491de766806173de5dc', 'createdAt': '2025-10-03T05:52:17.584Z', 'updatedAt': '2025-10-03T05:52:25.311Z', 'content': 'abcde'}], 'hodReviews': [{'comments': '', '_id': '68df6491de766806173de5dd'}], 'trusteeReviews': [{'comments': '', '_id': '68df6491de766806173de5de'}], 'fundingPlans': [], 'createdAt': '2025-10-03T05:40:32.879Z', 'updatedAt': '2026-01-02T11:27:09.434Z', '__v': 1, 'syncedFromOdoo': False, 'odooId': 41}
            return response.json().get('data', [])
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to sync welfare record {welfare_record.id} to portal: {e}")
            return None    
    
    def action_view_fetched_records(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Fetched Welfare Records',
            'res_model': 'welfare',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.record_ids.ids)],
            'target': 'current',
        }
        
    def download_image(self, url):
        try:
            if url and url.startswith('http'):
                img_resp = requests.get(url, timeout=20)
                if img_resp.status_code == 200:
                    return base64.b64encode(img_resp.content)
        except Exception:
            pass
        return None
        
    @api.model
    def fetch_institution_applications(self):
        company = self.env.company
        endpoint = company.welfare_institution_endpoint
        base_url = company.welfare_instituiton_url
        url = f"{base_url}{endpoint}"
        headers = {
            'x-odoo-auth-key': f'{company.odoo_auth_institution_key}',
            'Content-Type': 'application/json'
        }
        try:
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json().get('data', [])
        except Exception as e:
            raise UserError(f"Institution fetch failed: {str(e)}")
        
        created_ids = []
        Employee = self.env['hr.employee']
        Partner = self.env['res.partner']
        Welfare = self.env['welfare']
        all_synced = True

        for rec in data:
            submitted = rec.get('submittedBy', {})
            raw_cnic = submitted.get('cnic')
            if raw_cnic and raw_cnic.isdigit() and len(raw_cnic) == 13:
                formatted_cnic = f"{raw_cnic[:5]}-{raw_cnic[5:12]}-{raw_cnic[12:]}"
            else:
                formatted_cnic = ''
                
            cnic = formatted_cnic
            partner = None
            if cnic:
                partner = Partner.search([('cnic_no', '=', cnic)], limit=1)
            if not partner:
                # Download CNIC images if available
                cnic_front_url = submitted.get('cnicFront')
                cnic_back_url = submitted.get('cnicBack')
                profile_image_url = submitted.get('profileImage')

                cnic_front_image = self.download_image(cnic_front_url)
                cnic_back_image = self.download_image(cnic_back_url)
                profile_image = self.download_image(profile_image_url)  
                # Create new Donee
                partner_vals = {
                    'image_1920': profile_image,
                    'name': submitted.get('fullname') or rec.get('form', {}).get('applicantInformation', {}).get('name', 'Unknown'),
                    'cnic_no': cnic,
                    'mobile': submitted.get('whatsapp') or submitted.get('phoneNumber'),
                    'email': submitted.get('email'),
                    'cnic_front_image': cnic_front_image,
                    'cnic_back_image': cnic_back_image,
                    'category_id': [(6, 0, [self.env.ref('bn_profile_management.donee_partner_category').id]), 
                                    (6, 0, [self.env.ref('bn_profile_management.welfare_partner_category').id])
                                    ],
                }
                partner = Partner.create(partner_vals)

            # Inquiry Officer (from inquiryReports[0].officerId)
            inquiry_officer = None
            inquiry_reports = rec.get('inquiryReports', [])
            officer_data = None
            if inquiry_reports:
                officer_data = inquiry_reports[0].get('officerId')
            if officer_data:
                officer_email = officer_data.get('email')
                officer_name = officer_data.get('fullname')
                # Try to find by email first, then by name
                if officer_email:
                    inquiry_officer = Employee.search([('work_email', '=', officer_email)], limit=1)
                if not inquiry_officer and officer_name:
                    inquiry_officer = Employee.search([('name', '=', officer_name)], limit=1)
                if not inquiry_officer:
                    # Create new employee
                    emp_vals = {
                        'name': officer_name or 'Unknown',
                        'work_email': officer_email,
                        'category_ids': [(6, 0, [self.env.ref('bn_welfare.inquiry_officer_hr_employee_category').id])],
                    }
                    inquiry_officer = Employee.create(emp_vals)

            vals = {
                'donee_id': partner.id if partner else False,
                'employee_id': inquiry_officer.id if inquiry_officer else False,
                'old_system_id': rec.get('_id'),
                'designation': rec.get('form', {}).get('applicantInformation', {}).get('designation'),
                'institute_name': rec.get('form', {}).get('madrasaInfo', {}).get('madarsaName'),
                'company_address': rec.get('form', {}).get('madrasaInfo', {}).get('address'),
                'aid_from_other_organization': 'yes' if rec.get('form', {}).get('fundInfo', {}).get('everReceivedFromSaylani', '').lower() == 'yes' else 'no',
                'monthly_income': float(rec.get('form', {}).get('fundInfo', {}).get('amountReceivedFromSaylani', 0) or 0),
                'bank_account': 'yes' if rec.get('form', {}).get('accountDetails', {}).get('accountType') else 'no',
                'bank_name': rec.get('form', {}).get('accountDetails', {}).get('accountTitle'),
                'account_no': rec.get('form', {}).get('accountDetails', {}).get('accountNumber'),
                'state': 'inquiry',
                'portal_application_id': rec.get('token'),
                'hod_remarks': rec.get('hodReviews', [{}])[0].get('comments', ''),
            }
            welfare = Welfare.create(vals)
            created_ids.append(welfare.id)
            # Send sync to portal for each created welfare record
            sync_endpoint = f"{base_url}{company.mark_institution_application_endpoint}"
            
            sync_applications= self.send_welfare_sync_to_portal(
                welfare_record=welfare,
                endpoint_url=sync_endpoint,
                auth_key=company.odoo_auth_institution_key
            )
            # raise UserError(str(sync_applications))
            response_status = sync_applications.get("syncedToOdoo", False ) # type: ignore
            if response_status:
                welfare.write({'is_synced': True})
            else:
                all_synced = False  # Mark as not fully synced if any fail

        
        log = self.create({
            'record_count': len(created_ids),
            'record_ids': [(6, 0, created_ids)]
            ,
        })
        if all_synced and created_ids:
            
            log.sync = True        
        return log