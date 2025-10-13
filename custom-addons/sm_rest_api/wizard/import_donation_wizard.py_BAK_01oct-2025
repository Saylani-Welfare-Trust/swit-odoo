# default
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timezone
import requests
import json
from urllib.parse import urlparse
import logging

_logger = logging.getLogger(__name__)

class ImportDonationWizard(models.TransientModel):
    _name = 'import.donation.wizard'
    _description = 'Import Donation Wizard'

    start_date = fields.Datetime(string='Start Date', default=fields.Date.today())
    end_date = fields.Datetime(string='End Date', default=fields.Date.today())

    def action_import_donation_wizard(self):
        # conversion_rate = 1.0
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError("Start Date must be earlier than or equal to End Date.")
        domain = []
        if self.start_date:
            start_date = self.start_date.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
            domain.append(('start_date', '=', start_date))
        if self.end_date:
            end_date = self.end_date.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
            domain.append(('end_date', '=', end_date))
        donation_authorization = self.env['donation.authorization'].sudo().search([], limit=1)
        if donation_authorization:
            if donation_authorization.url and donation_authorization.client_id and donation_authorization.client_secret:
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                parsed_url = urlparse(base_url)
                host = parsed_url.hostname
                url = f'{donation_authorization.url}/api/odoo/auth'
                payload = json.dumps({
                    "ClientID": donation_authorization.client_id,
                    "ClientSecret": donation_authorization.client_secret
                })
                headers = {
                    'Origin': f'{base_url}',
                    'x-forwarded-for': f'{host}',
                    'Content-Type': 'application/json'
                }
                response = requests.post(url, headers=headers, data=payload)
                if response.status_code != 200:
                    raise ValidationError(f"External API error ({response.status_code}): {response.text}")
                try:
                    result = response.json()
                    if 'token' in result:
                        token = result['token']
                        url_donation = f'{donation_authorization.url}/api/odoo/donationInfo'
                        if self.start_date and self.end_date:
                            start_date1 = self.start_date.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
                            end_date1 = self.end_date.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
                            payload_donation = json.dumps({
                                "status": 'success',
                                "startDate": start_date1,
                                "endDate": end_date1
                            })
                        elif self.start_date:
                            start_date2 = self.start_date.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
                            payload_donation = json.dumps({
                                "status": 'success',
                                "startDate": start_date2
                            })
                        elif self.end_date:
                            end_date2 = self.end_date.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
                            payload_donation = json.dumps({
                                "status": 'success',
                                "endDate": end_date2
                            })
                        else:
                            payload_donation = json.dumps({
                                "status": 'success'
                            })
                        headers_donation = {
                            'Origin': f'{base_url}',
                            'x-forwarded-for': f'{host}',
                            'Content-Type': 'application/json',
                            'authorization': f'bearer {token}'
                        }
                        response_donation = requests.post(url_donation, headers=headers_donation, data=payload_donation)
                        if response_donation.status_code != 200:
                            raise ValidationError(f"External API error ({response_donation.status_code}): {response_donation.text}")
                        try:
                            result_donation = response_donation.json()
                            if 'donationsInfo' in result_donation:
                                # Initialize variables for journal entry
                                journal = self.env['account.journal'].search([('name', 'ilike', 'Bank')], limit=1)
                                config_bank = self.env['config.bank'].search([('name', '=', 'Website API')], limit=1)
                                journal_lines = []
                                new_donations = []
                                
                                for donation_info in result_donation['donationsInfo']:
                                    donation_data = self.env['donation.data'].sudo().search([('import_id', '=', donation_info.get('_id', ''))])
                                    if donation_data:
                                        # Existing donation update logic remains the same
                                        if donation_info.get('createdAt', ''):
                                            created_at_iso_date = donation_info.get('createdAt', '')
                                            created_at_clean_date = created_at_iso_date.split('.')[0]
                                            created_at_clean_date = created_at_clean_date.replace('T', ' ')
                                            created_at_parsed_date = datetime.strptime(created_at_clean_date,
                                                                                       '%Y-%m-%d %H:%M:%S')
                                        else:
                                            created_at_parsed_date = None
                                        if donation_info.get('updatedAt', ''):
                                            updated_at_iso_date = donation_info.get('updatedAt', '')
                                            updated_at_clean_date = updated_at_iso_date.split('.')[0]
                                            updated_at_clean_date = updated_at_clean_date.replace('T', ' ')
                                            updated_at_parsed_date = datetime.strptime(updated_at_clean_date,
                                                                                       '%Y-%m-%d %H:%M:%S')
                                        else:
                                            updated_at_parsed_date = None
                                        
                                        conversion_currency = self.env['res.currency'].search(
                                            [('name', '=', donation_info.get('currency', ''))], limit=1
                                        )
                                        conversion_rate = 1.0  # default

                                        if conversion_currency and conversion_currency.rate_ids:
                                            latest_rate = conversion_currency.rate_ids.sorted(
                                                lambda r: r.name, reverse=True
                                            )[0]
                                            conversion_rate = latest_rate.inverse_company_rate
                                        val_write = {
                                            "status": donation_info.get('status', 'draft'),
                                            "remarks": donation_info.get('remarks', ''),
                                            "total_amount": donation_info.get('total_amount', 0),
                                            "donor": donation_info.get('donor', ''),
                                            "donation_type": donation_info.get('donation_type', ''),
                                            "donation_from": donation_info.get('donation_from', ''),
                                            "dn_number": donation_info.get('DN_Number', ''),
                                            "subscription_interval": donation_info.get('subscriptionInterval', ''),
                                            "is_recurring": donation_info.get('isRecurring', False),
                                            "response_code": donation_info.get('response_code', ''),
                                            "response_description": donation_info.get('response_description', ''),
                                            "currency": donation_info.get('currency', ''),
                                            "referer": donation_info.get('referer', ''),
                                            "website": donation_info.get('website', ''),
                                            "account_source": donation_info.get('account_source', ''),
                                            "conversion_rate": conversion_rate,
                                            "bank_charges": donation_info.get('bank_charges', 0),
                                            "bank_charges_in_text": donation_info.get('bank_charges_in_text', ''),
                                            "blinq_notification_number": donation_info.get('blinq_notification_number', ''),
                                            "created_at": created_at_parsed_date,
                                            "updated_at": updated_at_parsed_date,
                                            "donation_id": donation_info.get('donation_id', ''),
                                            "invoice_id": donation_info.get('invoice_id', ''),
                                            "transaction_id": donation_info.get('transaction_id', ''),
                                        }
                                        if 'donor_details' in donation_info:
                                            donor_details = donation_info['donor_details']
                                            val_write.update({
                                                "name": donor_details.get('name', ''),
                                                "phone": donor_details.get('phone', ''),
                                                "email": donor_details.get('email', ''),
                                                "cnic": donor_details.get('cnic', ''),
                                                "country": donor_details.get('country', ''),
                                                "ip_address": donor_details.get('ipAddress', ''),
                                                "subscription_for_news": donor_details.get('subscriptionForNews', False),
                                                "subscription_for_whatsapp": donor_details.get('subscriptionForWhatsapp', False),
                                                "subscription_for_sms": donor_details.get('subscriptionForSms', False),
                                                "qurbani_country": donor_details.get('qurbaniCountry', ''),
                                                "qurbani_city": donor_details.get('qurbaniCity', ''),
                                                "qurbani_day": donor_details.get('qurbaniDay', ''),
                                            })

                                        if 'items' in donation_info:
                                            items = []
                                            for items_lines in donation_info.get('items', []):
                                                types = items_lines.get('type', {})
                                                item = items_lines.get('item', {})
                                                types_name = types.get('en', {}).get('name', '') if isinstance(types, dict) else ''
                                                item_name = item.get('en', {}).get('name', '') if isinstance(item, dict) else ''
                                                items.append({
                                                    "donation_type": items_lines.get('donationType', ''),
                                                    "total": items_lines.get('total', 0),
                                                    "price": items_lines.get('price', 0),
                                                    "price_id": items_lines.get('price_id', 0),
                                                    "qty": items_lines.get('qty', 0),
                                                    "type": types_name,
                                                    "item": item_name,
                                                    "donation_no": items_lines.get('donationNo', 0),
                                                    "is_priced_item": items_lines.get('isPricedItem', False),
                                                })
                                            val_write.update({
                                                'donation_item_ids': [(5, 0, 0)] + [(0, 0, line) for line in items]
                                            })
                                        donation_data.write(val_write)
                                    else:
                                        # New donation creation logic
                                        items_list = []
                                        for items_lines in donation_info.get('items', []):
                                            types = items_lines.get('type', {})
                                            item = items_lines.get('item', {})
                                            types_name = types.get('en', {}).get('name', '') if isinstance(types, dict) else ''
                                            item_name = item.get('en', {}).get('name', '') if isinstance(item, dict) else ''
                                            
                                            items_list.append({
                                                "donation_type": items_lines.get('donationType', ''),
                                                "total": items_lines.get('total', 0),
                                                "price": items_lines.get('price', 0),
                                                "price_id": items_lines.get('price_id', 0),
                                                "qty": items_lines.get('qty', 0),
                                                "type": types_name,
                                                "item": item_name,
                                                "donation_no": items_lines.get('donationNo', 0),
                                                "is_priced_item": items_lines.get('isPricedItem', False),
                                            })
                                        
                                        if donation_info.get('createdAt', ''):
                                            created_at_iso_date = donation_info.get('createdAt', '')
                                            created_at_clean_date = created_at_iso_date.split('.')[0]
                                            created_at_clean_date = created_at_clean_date.replace('T', ' ')
                                            created_at_parsed_date = datetime.strptime(created_at_clean_date, '%Y-%m-%d %H:%M:%S')
                                        else:
                                            created_at_parsed_date = None
                                        if donation_info.get('updatedAt', ''):
                                            updated_at_iso_date = donation_info.get('updatedAt', '')
                                            updated_at_clean_date = updated_at_iso_date.split('.')[0]
                                            updated_at_clean_date = updated_at_clean_date.replace('T', ' ')
                                            updated_at_parsed_date = datetime.strptime(updated_at_clean_date, '%Y-%m-%d %H:%M:%S')
                                        else:
                                            updated_at_parsed_date = None

                                        conversion_currency = self.env['res.currency'].search(
                                            [('name', '=', donation_info.get('currency', ''))], limit=1
                                        )
                                        conversion_rate = 1.0  # default

                                        if conversion_currency and conversion_currency.rate_ids:
                                            latest_rate = conversion_currency.rate_ids.sorted(
                                                lambda r: r.name, reverse=True
                                            )[0]
                                            conversion_rate = latest_rate.inverse_company_rate

                                        val_create = {
                                            "import_id": donation_info.get('_id', ''),
                                            "status": donation_info.get('status', 'draft'),
                                            "remarks": donation_info.get('remarks', ''),
                                            "total_amount": donation_info.get('total_amount', 0),
                                            "total_amount_local": str(float(donation_info.get('total_amount', 0))*conversion_rate) if donation_info.get('currency', '') != 'PKR' else donation_info.get('total_amount', 0),
                                            "donor": donation_info.get('donor', ''),
                                            "donation_type": donation_info.get('donation_type', ''),
                                            "donation_from": donation_info.get('donation_from', ''),
                                            "dn_number": donation_info.get('DN_Number', ''),
                                            "subscription_interval": donation_info.get('subscriptionInterval', ''),
                                            "is_recurring": donation_info.get('isRecurring', False),
                                            "response_code": donation_info.get('response_code', ''),
                                            "response_description": donation_info.get('response_description', ''),
                                            "currency": donation_info.get('currency', ''),
                                            "referer": donation_info.get('referer', ''),
                                            "website": donation_info.get('website', ''),
                                            "account_source": donation_info.get('account_source', ''),
                                            "conversion_rate": conversion_rate,
                                            "bank_charges": donation_info.get('bank_charges', 0),
                                            "bank_charges_in_text": donation_info.get('bank_charges_in_text', ''),
                                            "blinq_notification_number": donation_info.get('blinq_notification_number', ''),
                                            "created_at": created_at_parsed_date,
                                            "updated_at": updated_at_parsed_date,
                                            "donation_id": donation_info.get('donation_id', ''),
                                            "invoice_id": donation_info.get('invoice_id', ''),
                                            "transaction_id": donation_info.get('transaction_id', ''),
                                        }
                                        if 'donor_details' in donation_info:
                                            donor_details = donation_info['donor_details']
                                            val_create.update({
                                                "name": donor_details.get('name', ''),
                                                "phone": donor_details.get('phone', ''),
                                                "email": donor_details.get('email', ''),
                                                "cnic": donor_details.get('cnic', ''),
                                                "country": donor_details.get('country', ''),
                                                "ip_address": donor_details.get('ipAddress', ''),
                                                "subscription_for_news": donor_details.get('subscriptionForNews', False),
                                                "subscription_for_whatsapp": donor_details.get('subscriptionForWhatsapp', False),
                                                "subscription_for_sms": donor_details.get('subscriptionForSms', False),
                                                "qurbani_country": donor_details.get('qurbaniCountry', ''),
                                                "qurbani_city": donor_details.get('qurbaniCity', ''),
                                                "qurbani_day": donor_details.get('qurbaniDay', ''),
                                            })

                                            phone = donor_details.get('phone', '')

                                            if phone:
                                                if len(phone) != 10:
                                                    diff = len(phone) - 10
                                                    phone = phone[diff:] 

                                            partner = self.env['res.partner'].sudo().search([('mobile', '=', phone)], limit=1)

                                            if not partner:
                                                partner_vals = {
                                                    'name': donor_details.get('name', 'Unknown Donor'),
                                                    'phone': donor_details.get('phone', ''),
                                                    'mobile': phone,
                                                    'email': donor_details.get('email', ''),
                                                    'street': donor_details.get('address', ''),
                                                    'country_id': self.env['res.country'].search([
                                                        ('name', '=', donor_details.get('country', ''))
                                                    ], limit=1).id,
                                                    'phone_code_id': self.env['res.country'].search([('currency_id', '=', conversion_currency.id)], limit=1).id,
                                                    'registration_category': 'donor',
                                                    'is_donee': False,
                                                }

                                                partner_obj = self.env['res.partner'].sudo().create(partner_vals)

                                                partner_obj.action_validate()
                                                partner_obj.action_register()

                                                val_create['partner_id'] = partner_obj.id

                                        # Create ORM commands for items
                                        orm_items = []
                                        for item in items_list:
                                            orm_items.append((0, 0, {
                                                "donation_type": item.get('donation_type', ''),
                                                "total": item.get('total', 0),
                                                "price": item.get('price', 0),
                                                "price_id": item.get('price_id', 0),
                                                "qty": item.get('qty', 0),
                                                "type": item.get('type', ''),
                                                "item": item.get('item', ''),
                                                "donation_no": item.get('donation_no', 0),
                                                "is_priced_item": item.get('is_priced_item', False),
                                            }))
                                        val_create.update({
                                            'donation_item_ids': orm_items
                                        })

                                        donation_data = self.env['donation.data'].sudo().create(val_create)
                                        new_donations.append(donation_data)

                                        # Prepare journal lines for this donation
                                        if config_bank and journal:
                                            currency_name = donation_info.get('currency', '')
                                            conversion_currency = self.env['res.currency'].search(
                                                [('name', '=', currency_name)], limit=1
                                            )
                                            if not conversion_currency:
                                                raise ValidationError(f"Currency {currency_name} not found for donation {donation_data.import_id}")
                                                continue
                                            
                                            debit_account_line = config_bank.currency_debit_ids.filtered(
                                                lambda x: x.currency_id.name == currency_name
                                            )
                                            if not debit_account_line:
                                                raise ValidationError(f"Debit account not found for currency {currency_name}")
                                            
                                            debit_account_id = debit_account_line.account_id.id
                                            company_currency = self.env.company.currency_id
                                            is_foreign_currency = conversion_currency != company_currency
                                            
                                            for item in items_list:
                                                product_name = f"{item.get('donation_type', '')}{item.get('item', '')}{item.get('type', '')}"
                                                config_line = config_bank.config_bank_line_ids.filtered(
                                                    lambda x: x.name == product_name
                                                )
                                                if not config_line:
                                                    raise ValidationError(f"Config line not found for product {product_name}")
                                                
                                                credit_account = config_line.account_id
                                                if not credit_account:
                                                    raise ValidationError(f"Credit account not found for product {product_name}")
                                                
                                                analytic_account_id = config_line.analytic_plan_id.id
                                                item_total = float(item.get('total', 0))
                                                conversion_rate = donation_data.conversion_rate
                                                item_total_base = item_total * float(conversion_rate) if is_foreign_currency else item_total
                                                
                                                analytic_distribution = {}
                                                if analytic_account_id:
                                                    analytic_distribution = {str(analytic_account_id): 100}
                                                
                                                # Add debit line (Bank)
                                                journal_lines.append((0, 0, {
                                                    'account_id': debit_account_id,
                                                    'currency_id': conversion_currency.id if is_foreign_currency else company_currency.id,
                                                    'amount_currency': item_total_base if is_foreign_currency else item_total,
                                                    'name': f'Donation {donation_data.import_id}: {product_name}',
                                                    'debit': item_total_base,
                                                }))
                                                
                                                # Add credit line (Income)
                                                journal_lines.append((0, 0, {
                                                    'account_id': credit_account.id,
                                                    'currency_id': conversion_currency.id if is_foreign_currency else company_currency.id,
                                                    'amount_currency': -item_total_base if is_foreign_currency else -item_total,
                                                    'name': f'Donation {donation_data.import_id}: {product_name}',
                                                    'credit': item_total_base,
                                                    'analytic_distribution': analytic_distribution,
                                                }))
                                
                                # Create single journal entry after processing all donations
                                if journal_lines and config_bank and journal:
                                    try:
                                        journal_entry_vals = {
                                            'move_type': 'entry',
                                            'ref': f"Donation Import {fields.Datetime.now()}",
                                            'date': fields.Date.today(),
                                            'journal_id': journal.id,
                                            'line_ids': journal_lines,
                                        }
                                        
                                        journal_entry = self.env['account.move'].create(journal_entry_vals)
                                        journal_entry.action_post()
                                        
                                        # Link the journal entry to all new donations
                                        for donation in new_donations:
                                            donation.journal_entry_id = journal_entry.id
                                            
                                    except Exception as e:
                                        raise ValidationError("Journal Entry creation failed: %s", str(e))
                                
                            else:
                                raise ValidationError(f"Invalid Donations Info")
                        except requests.exceptions.RequestException as e:
                            raise ValidationError(f"Request failed: {str(e)}")
                        except ValueError as ve:
                            raise ValidationError(f"Invalid JSON received. Raw response:\n\n{ve}\n{response_donation.text}")
                    else:
                        raise ValidationError('Token not found in the response. Please try again or contact support.')
                except requests.exceptions.RequestException as e:
                    raise ValidationError(f"Request failed: {str(e)}")
                except ValueError:
                    raise ValidationError(f"Invalid JSON received. Raw response:\n{response.text}")
            else:
                raise ValidationError("Missing URL, Client ID, or Client Secret in Donation Authorization settings.")
        else:
            raise ValidationError("No donation authorization record found.")
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    

