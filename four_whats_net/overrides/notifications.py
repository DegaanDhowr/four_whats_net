import frappe
from frappe import _
from frappe.email.doctype.notification.notification import Notification, get_context, json
import requests
import pytz
from datetime import datetime

class ERPGulfNotification(Notification):
    def validate(self):
        self.validate_custom_settings()
        super(ERPGulfNotification, self).validate()

    def validate_custom_settings(self):
        if self.enabled:
            if self.channel == "4Whats.net":
                self.validate_hormuud_sms_settings()
            elif self.channel == "SMSHormuud":
                self.validate_four_whats_settings()

    def validate_hormuud_sms_settings(self):
        settings = frappe.get_doc("Hormuud SMS Configuration")
        if not settings.api_url or not settings.username or not settings.password:
            frappe.throw(_("Please configure Hormuud SMS settings to send SMS messages"))

    def validate_four_whats_settings(self):
        settings = frappe.get_doc("Four Whats Net Configuration")
        if not settings.token or not settings.api_url or not settings.instance_id:
            frappe.throw(_("Please configure 4Whats.net settings to send WhatsApp messages"))

    def send(self, doc):
        context = get_context(doc)
        context = {"doc": doc, "alert": self, "comments": None}
        if doc.get("_comments"):
            context["comments"] = json.loads(doc.get("_comments"))

        if self.is_standard:
            self.load_standard_properties(context)

        try:
            if self.channel == "SMSHormuud":
                self.send_hormuud_sms(doc, context)
            elif self.channel == "4Whats.net":
                self.send_whatsapp_msg(doc, context)
        except Exception:
            frappe.log_error(title="Failed to send notification", message=frappe.get_traceback())

        super(ERPGulfNotification, self).send(doc)

    def send_hormuud_sms(self, doc, context):
        settings = frappe.get_doc("Hormuud SMS Configuration")
        recipients = self.get_receiver_list(doc, context)
        receiver_numbers = []
    
        for recipient in recipients:
            number = frappe.render_template(recipient, context)
            message = frappe.render_template(self.message, context)
            phone_number = self.get_receiver_phone_number(number)
            
            # Check if the phone number is invalid (None or empty)
            if not phone_number:
                frappe.log_error(
                    message=f"Invalid phone number: {number}. The number is empty or could not be parsed.",
                    title="Invalid Phone Number"
                )
                continue  # Skip sending if the phone number is empty or invalid
            
            # Check if the phone number doesn't start with "252"
            if not phone_number.startswith("252"):
                frappe.log_error(
                    message=f"Invalid phone number: {phone_number}. The number doesn't start with Somalia's country code '252'.",
                    title="Invalid Phone Number"
                )
                continue  # Skip sending if the number doesn't start with "252"
    
            # Additional validation check for Somalia phone number (must be 12 digits long, starting with 252)
            if len(phone_number) != 12:
                frappe.log_error(
                    message=f"Invalid phone number: {phone_number}. It must be 12 digits long.",
                    title="Invalid Phone Number"
                )
                continue  # Skip if the number doesn't match the length requirement
            frappe.msgprint("Numberka Wax Loo diri rabo waa ", phone_number)
            receiver_numbers.append(phone_number)
            self.send_sms(settings, phone_number, message)
            self.create_message_sms(phone_number, message)
    
        # Log a message showing which phone numbers the SMS was sent to
        if receiver_numbers:
            frappe.msgprint(_(f"Hormuud SMS sent to {', '.join(receiver_numbers)}"))
        else:
            frappe.msgprint(_("No valid phone numbers to send SMS to."))



    def send_whatsapp_msg(self, doc, context):
        settings = frappe.get_doc("Four Whats Net Configuration")
        recipients = self.get_receiver_list(doc, context)
        receiver_numbers = []
        for recipient in recipients:
            number = frappe.render_template(recipient, context)
            message = frappe.render_template(self.message, context)
            phone_number = self.get_receiver_phone_number(number)
            
            # Skip sending if phone number is invalid
            if not phone_number:
                continue
            
            receiver_numbers.append(phone_number)
            self.send_whatsapp(settings, phone_number, message, doc)
            self.create_message_record(phone_number, message)
        frappe.msgprint(_(f"WhatsApp message sent to {', '.join(receiver_numbers)}"))


    def get_receiver_phone_number(self, number):
        # Clean and normalize the phone number
        phone_number = number.replace("+", "").replace("-", "").replace(" ", "")  # Remove unwanted characters
        
        # Handle different formats of phone numbers
        if phone_number.startswith("00"):
            phone_number = phone_number[2:]  # Remove international dial prefix
        elif phone_number.startswith("0"):
            if len(phone_number) == 10:  # Assume local number format (for Somalia)
                phone_number = "252" + phone_number[1:]  # Add Somalia's country code
                
        # Full list of valid country codes
        country_codes = {
            "Afghanistan": "93", "Albania": "355", "Algeria": "213", "Andorra": "376", "Angola": "244", 
            "Antigua and Barbuda": "1-268", "Argentina": "54", "Armenia": "374", "Australia": "61", 
            "Austria": "43", "Azerbaijan": "994", "Bahamas": "1-242", "Bahrain": "973", "Bangladesh": "880", 
            "Barbados": "1-246", "Belarus": "375", "Belgium": "32", "Belize": "501", "Benin": "229", 
            "Bhutan": "975", "Bolivia": "591", "Bosnia and Herzegovina": "387", "Botswana": "267", "Brazil": "55", 
            "Brunei": "673", "Bulgaria": "359", "Burkina Faso": "226", "Burundi": "257", "Cabo Verde": "238", 
            "Cambodia": "855", "Cameroon": "237", "Canada": "1", "Central African Republic": "236", "Chad": "235", 
            "Chile": "56", "China": "86", "Colombia": "57", "Comoros": "269", "Congo (Congo-Brazzaville)": "242", 
            "Congo (Democratic Republic)": "243", "Costa Rica": "506", "Croatia": "385", "Cuba": "53", 
            "Cyprus": "357", "Czech Republic": "420", "Denmark": "45", "Djibouti": "253", "Dominica": "1-767", 
            "Dominican Republic": "1-809", "Ecuador": "593", "Egypt": "20", "El Salvador": "503", "Equatorial Guinea": "240", 
            "Eritrea": "291", "Estonia": "372", "Eswatini": "268", "Ethiopia": "251", "Fiji": "679", 
            "Finland": "358", "France": "33", "Gabon": "241", "Gambia": "220", "Georgia": "995", 
            "Germany": "49", "Ghana": "233", "Greece": "30", "Grenada": "1-473", "Guatemala": "502", 
            "Guinea": "224", "Guinea-Bissau": "245", "Guyana": "592", "Haiti": "509", "Honduras": "504", 
            "Hungary": "36", "Iceland": "354", "India": "91", "Indonesia": "62", "Iran": "98", 
            "Iraq": "964", "Ireland": "353", "Israel": "972", "Italy": "39", "Jamaica": "1-876", 
            "Japan": "81", "Jordan": "962", "Kazakhstan": "7", "Kenya": "254", "Kiribati": "686", 
            "Korea (North)": "850", "Korea (South)": "82", "Kuwait": "965", "Kyrgyzstan": "996", 
            "Laos": "856", "Latvia": "371", "Lebanon": "961", "Lesotho": "266", "Liberia": "231", 
            "Libya": "218", "Liechtenstein": "423", "Lithuania": "370", "Luxembourg": "352", 
            "Madagascar": "261", "Malawi": "265", "Malaysia": "60", "Maldives": "960", "Mali": "223", 
            "Malta": "356", "Marshall Islands": "692", "Mauritania": "222", "Mauritius": "230", 
            "Mexico": "52", "Micronesia": "691", "Moldova": "373", "Monaco": "377", "Mongolia": "976", 
            "Montenegro": "382", "Morocco": "212", "Mozambique": "258", "Myanmar": "95", 
            "Namibia": "264", "Nauru": "674", "Nepal": "977", "Netherlands": "31", "New Zealand": "64", 
            "Nicaragua": "505", "Niger": "227", "Nigeria": "234", "North Macedonia": "389", "Norway": "47", 
            "Oman": "968", "Pakistan": "92", "Palau": "680", "Panama": "507", "Papua New Guinea": "675", 
            "Paraguay": "595", "Peru": "51", "Philippines": "63", "Poland": "48", "Portugal": "351", 
            "Qatar": "974", "Romania": "40", "Russia": "7", "Rwanda": "250", "Saint Kitts and Nevis": "1-869", 
            "Saint Lucia": "1-758", "Saint Vincent and the Grenadines": "1-784", "Samoa": "685", 
            "San Marino": "378", "Sao Tome and Principe": "239", "Saudi Arabia": "966", "Senegal": "221", 
            "Serbia": "381", "Seychelles": "248", "Sierra Leone": "232", "Singapore": "65", 
            "Slovakia": "421", "Slovenia": "386", "Solomon Islands": "677", "Somalia": "252", 
            "South Africa": "27", "South Sudan": "211", "Spain": "34", "Sri Lanka": "94", "Sudan": "249", 
            "Suriname": "597", "Sweden": "46", "Switzerland": "41", "Syria": "963", "Taiwan": "886", 
            "Tajikistan": "992", "Tanzania": "255", "Thailand": "66", "Timor-Leste": "670", 
            "Togo": "228", "Tonga": "676", "Trinidad and Tobago": "1-868", "Tunisia": "216", 
            "Turkey": "90", "Turkmenistan": "993", "Tuvalu": "688", "Uganda": "256", "Ukraine": "380", 
            "United Arab Emirates": "971", "United Kingdom": "44", "United States": "1", "Uruguay": "598", 
            "Uzbekistan": "998", "Vanuatu": "678", "Vatican City": "39", "Venezuela": "58", 
            "Vietnam": "84", "Yemen": "967", "Zambia": "260", "Zimbabwe": "263"
        }
    
        # Check if the phone number starts with any valid country code
        for code in country_codes.values():
            if phone_number.startswith(code):
                # Check if the phone number is at least 11 digits long
                if len(phone_number) > 10:
                    return phone_number
                else:
                    frappe.log_error(
                        message=f"Invalid phone number: {phone_number}. Number must be more than 10 digits.",
                        title="Invalid Phone Number"
                    )
                    return None  # Return None to skip this phone number
        
        # If no valid country code, prepend "252" (Somalia's country code)
        phone_number = "252" + phone_number
        
        # Validate phone number length (must be more than 10 digits after prepending the country code)
        if len(phone_number) <= 10:
            frappe.log_error(
                message=f"Invalid phone number: {phone_number}. Number must be more than 10 digits.",
                title="Invalid Phone Number"
            )
            return None  # Return None to skip this phone number
        
        return phone_number

    def send_sms(self, settings, phone_number, message):
        try:
            access_token = self.get_access_token()
            if not access_token:
                frappe.throw("Access token is not available.")

            url = "https://smsapi.hormuud.com/api/SendSMS"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            }
            payload = {"mobile": phone_number, "message": message}

            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            response_data = response.json()

            if response_data.get("ResponseMessage") != "SUCCESS!.":
                frappe.log_error(response_data, "SMS API Response Error")
        except requests.exceptions.RequestException as e:
            frappe.log_error(frappe.get_traceback(), _("Failed to send SMS via Hormuud API"))
            frappe.throw(f"Failed to send SMS: {str(e)}")

    def send_whatsapp(self, settings, phone_number, message, doc):
        # Retrieve the API URL from settings
        api_url = settings.api_url  # Assuming settings.api_url contains the base URL
        session = settings.instance_id
        
        # Construct the full URL by appending the specific endpoint
        url = f"{api_url}/api/sendText"
        
        # Fetch the doctype and document name dynamically
        document_name = doc.name
        document_doctype = doc.doctype
        
        # Fetch the attached files related to the document, dynamically using the doctype and name
        file_records = frappe.get_all(
            'File', 
            filters={'attached_to_name': document_name, 'attached_to_doctype': document_doctype}, 
            fields=['file_url', 'file_name', 'file_size', 'file_type', 'attached_to_name', 'attached_to_doctype']
        )
        
        # Filter for PDF files specifically
        pdf_file = next((file for file in file_records if file['file_type'] == 'PDF'), None)
        
        if pdf_file:
            # If a PDF file is found, extract necessary details
            file_url = pdf_file['file_url']
            file_type = pdf_file['file_type']
            file_name = pdf_file['file_name']
            attached_to_name = pdf_file['attached_to_name']
            attached_to_doctype = pdf_file['attached_to_doctype']
            
            # Log the document details for debugging purposes
            frappe.log_error(f"Sending file from Document: {attached_to_doctype} - {attached_to_name}", "WhatsApp Notification")
            
            # Prepare the data payload to send the file
            file_data = {
                "session": session,
                "caption": message,  # You can modify this if you want a custom caption for the file
                "chatId": f"{phone_number}@c.us",
                "file": {
                    "file_type": file_type,  # Correct field to indicate file type
                    "filename": file_name,
                    "url": file_url
                }
            }
    
            # Change endpoint for sending files
            url = f"{api_url}/api/sendFile"  
            data = json.dumps(file_data)
        else:
            # If no file is found (or no PDF), only send text
            data = json.dumps({
                "chatId": f"{phone_number}@c.us",  # Append @c.us to the phone number
                "reply_to": None,
                "text": message,
                "linkPreview": True,
                "session": session
            })
        
        # Set the headers to specify that we're sending JSON data
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            # Send the POST request with the JSON data and headers
            response = requests.post(url, data=data, headers=headers)
            
            # Raise an error if the response status code is not successful
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            # Log the error and raise an exception
            frappe.log_error(frappe.get_traceback(), _("Failed to send WhatsApp message"))
            frappe.throw(f"Failed to send WhatsApp message: {str(e)}")

    def create_message_record(self, phone, message):
        """Create a new record in the Four Whats Messages doctype."""
        try:
            # # Clean the phone number by removing existing country codes or duplicates
            # phone = phone.strip().replace("+", "").replace("-", "").replace(" ", "")  # Remove unwanted characters
            
            # # Remove existing country code if it starts with "252"
            # if phone.startswith("252"):
            #     phone = phone[3:]
            
            # # Remove leading zero if present
            # if phone.startswith("0"):
            #     phone = phone[1:]
            
            # # Add the correct country code
            # phone = f"+252{phone}"

            # Create the new doctype record
            doc = frappe.get_doc({
                "doctype": "Four Whats Messages",
                "phone": phone,
                "receiver_name": message,  # Adjust this field to map to the correct value
            })
            doc.insert(ignore_permissions=True)
            frappe.db.commit()

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), _("Failed to create Four Whats Messages record"))

    def create_message_sms(self, phone, message):
        """Create a record in the Hormuud SMS Messages doctype."""
        try:
            doc = frappe.get_doc({
                "doctype": "Hormuud SMS Messages",
                "phone_number": phone,
                "messege": message
            })
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), _("Failed to create Hormuud SMS Messages record"))
    def get_access_token(self):
        sms_settings = frappe.get_doc("Hormuud SMS Configuration")
        if not sms_settings.token or self.is_access_token_expired():
            return self.get_token()
        return sms_settings.token

    def get_token(self):
        sms_settings = frappe.get_doc("Hormuud SMS Configuration")
        payload = {
            "grant_type": sms_settings.grant_type,
            "username": sms_settings.username,
            "password": sms_settings.password,
        }
        try:
            response = requests.post(
                f"{sms_settings.api_url}",
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()
            sms_settings.db_set("token", token_data.get("access_token"), commit=True)
            sms_settings.db_set("expiry_date", token_data.get(".expires"), commit=True)
            return token_data.get("access_token")
        except Exception as e:
            frappe.throw(f"Failed to fetch access token: {str(e)}")

    def is_access_token_expired(self):
        sms = frappe.get_doc("Hormuud SMS Configuration")
        if not sms.expiry_date:
            return True
        format = "%a, %d %b %Y %H:%M:%S %Z"
        expiry_datetime = datetime.strptime(sms.expiry_date, format).replace(tzinfo=pytz.UTC)
        return datetime.now(pytz.UTC) > expiry_datetime
