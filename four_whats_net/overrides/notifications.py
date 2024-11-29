import frappe
from frappe import _
from frappe.email.doctype.notification.notification import Notification, get_context, json
import requests
import pytz
from datetime import datetime, timedelta


class HormuudSMSNotification(Notification):

    def validate(self):
        # frappe.msgprint("Notification Hormuud Dirsami Rabo SMS Token Validate wye")
        self.validate_hormuud_sms_settings()
        super(HormuudSMSNotification, self).validate()

    def validate_hormuud_sms_settings(self):
        settings = frappe.get_doc("Hormuud SMS Configuration")
        if self.enabled and self.channel == "SMSHormuud":
            if not settings.api_url or not settings.username or not settings.password:
                frappe.throw(_("Please configure Hormuud SMS settings to send SMS messages"))

    def send(self, doc):
        context = get_context(doc)
        context = {"doc": doc, "alert": self, "comments": None}
        if doc.get("_comments"):
            context["comments"] = json.loads(doc.get("_comments"))

        if self.is_standard:
            self.load_standard_properties(context)

        try:
            if self.channel == 'SMSHormuud':
                self.send_hormuud_sms(doc, context)
        except:
            frappe.log_error(title='Failed to send notification', message=frappe.get_traceback())
        super(HormuudSMSNotification, self).send(doc)

    def send_hormuud_sms(self, doc, context):
        settings = frappe.get_doc("Hormuud SMS Configuration")
        recipients = self.get_receiver_list(doc, context)
        receiver_numbers = []
        for recipient in recipients:
            number = frappe.render_template(recipient, context)
            message = frappe.render_template(self.message, context)
            phone_number = self.format_phone_number(number)
            receiver_numbers.append(phone_number)
            self.send_sms(settings, phone_number, message)
            self.create_message_record(phone_number, message)
        frappe.msgprint(_(f"Hormuud SMS sent to {', '.join(receiver_numbers)}"))

    def format_phone_number(self, number):
        """Format the phone number to include the correct country code."""
        phone_number = number.replace("+", "").replace("-", "").strip()
        if phone_number.startswith("252"):
            return f"+{phone_number}"
        if phone_number.startswith("0"):
            phone_number = phone_number[1:]
        return f"+252{phone_number}"

    def send_sms(self, settings, phone_number, message):
        # frappe.msgprint("Preparing to send SMS via Hormuud API...")
        try:
            access_token = self.get_access_token()  # Get the valid access token
            if not access_token:
                frappe.throw("Access token is not available.")

            # Hormuud API endpoint for sending SMS
            url = "https://smsapi.hormuud.com/api/SendSMS"

            # Headers required for the API
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            }

            # Payload structure for the API request
            payload = {
                "mobile": phone_number,  # Use the field 'mobile' as in the working example
                "message": message
            }

            # Debugging message for transparency
            # frappe.msgprint(f"Sending SMS to {phone_number} with message: {message}")

            # Send the POST request
            response = requests.post(url, json=payload, headers=headers)

            # Handle the response
            response.raise_for_status()  # Raise an error for HTTP issues
            response_data = response.json()  # Parse the JSON response

            # Check for successful response from API
            if response_data.get('ResponseMessage') == "SUCCESS!.":
                print(f"SMS successfully sent to {phone_number}")
            else:
                frappe.msgprint(f"Failed to send SMS to {phone_number}: {response_data.get('ResponseMessage')}")
                frappe.log_error(response_data, "SMS API Response Error")

        except requests.exceptions.RequestException as e:
            frappe.log_error(frappe.get_traceback(), _("Failed to send SMS via Hormuud API"))
            frappe.throw(f"Failed to send SMS due to an error: {e.response.text if e.response else str(e)}")


    def create_message_record(self, phone, message):
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

    def is_access_token_expired(self):
        """Check if the access token is expired."""
        sms = frappe.get_doc("Hormuud SMS Configuration")
        format = "%a, %d %b %Y %H:%M:%S %Z"
        gmt_timezone = pytz.timezone('GMT')
        mogadishu_timezone = pytz.timezone('Africa/Mogadishu')

        if not sms.expiry_date:
            return True  # If expire_date is not set, assume the token is expired

        expire_datetime = datetime.strptime(sms.expiry_date, format)
        gmt_expire_datetime = gmt_timezone.localize(expire_datetime)
        mogadishu_expire_datetime = gmt_expire_datetime.astimezone(mogadishu_timezone)

        current_datetime = datetime.now(mogadishu_timezone)
        # print("current time",current_datetime)
        # print("expire time",mogadishu_expire_datetime)

        return mogadishu_expire_datetime < current_datetime

    def get_access_token(self):
        """Get a valid access token, refreshing if necessary."""
        sms_settings = frappe.get_doc("Hormuud SMS Configuration")
        if not sms_settings.token or self.is_access_token_expired():
            return self.get_token()
        # frappe.msgprint("access token wuu jiray waana "+ sms_settings.token)
        return sms_settings.token

    def get_token(self):
        """Fetch a new access token from the Hormuud SMS API."""
        sms_settings = frappe.get_doc("Hormuud SMS Configuration")
        payload = {
            "grant_type": sms_settings.grant_type,
            "username": sms_settings.username,
            "password": sms_settings.password
        }
        try:
            response = requests.post(
                f"{sms_settings.api_url}",
                data=payload,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            response.raise_for_status()
            token_data = response.json()
            sms_settings.db_set("token", token_data.get("access_token"), commit=True)
            sms_settings.db_set("issue_date", token_data.get(".issued"), commit=True)
            # expires_in = int(token_data.get("expires_in", 3600))
            expire_date = token_data.get(".expires")
            sms_settings.db_set("expiry_date", expire_date, commit=True)
            return token_data.get("access_token")
        except Exception as e:
            frappe.throw(f"Failed to fetch access token: {str(e)}")


class ERPGulfNotification(Notification):
    
    def validate(self):
        self.validate_four_whats_settings()
        super(ERPGulfNotification, self).validate()
    
    def validate_four_whats_settings(self):
        settings = frappe.get_doc("Four Whats Net Configuration")
        if self.enabled and self.channel == "4Whats.net":
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
            if self.channel == '4Whats.net':
                self.send_whatsapp_msg(doc, context)
        except:
            frappe.log_error(title='Failed to send notification', message=frappe.get_traceback())
        super(ERPGulfNotification, self).send(doc)
        
    
    def send_whatsapp_msg(self, doc, context):
        settings = frappe.get_doc("Four Whats Net Configuration")
        recipients = self.get_receiver_list(doc, context)
        receiverNumbers = []
        for receipt in recipients:
            number = receipt
            if "{" in number:
                number = frappe.render_template(receipt, context)
            message=frappe.render_template(self.message, context)        
            phoneNumber = self.get_receiver_phone_number(number)
            receiverNumbers.append(phoneNumber)
            url = f"{settings.api_url}/sendMessage/?instanceid={settings.instance_id}&token={settings.token}&phone={phoneNumber}&body={message}"
            response = requests.get(url)

            # Save the message details to the "Four Whats Messages" doctype
            self.create_message_record(phoneNumber, message)
        frappe.msgprint(_(f"Whatsapp message sent to {','.join(receiverNumbers)}"))
    
    def get_receiver_phone_number(self, number):
        phoneNumber = number.replace("+","").replace("-","")
        if phoneNumber.startswith("+") == True:
            phoneNumber = phoneNumber[1:]
        elif phoneNumber.startswith("00") == True:
            phoneNumber = phoneNumber[2:]
        elif phoneNumber.startswith("0") == True:
            if len(phoneNumber) == 10:
                phoneNumber = "252" + phoneNumber[1:]
        else:
            if len(phoneNumber) < 10: 
                phoneNumber ="252" + phoneNumber
        if phoneNumber.startswith("0") == True:
            phoneNumber = phoneNumber[1:]
        
        return phoneNumber   
    
    def create_message_record(self, phone, message):
        """Create a new record in the Four Whats Messages doctype."""
        try:
            # Clean the phone number by removing existing country codes or duplicates
            phone = phone.strip().replace("+", "").replace("-", "").replace(" ", "")  # Remove unwanted characters
            
            # Remove existing country code if it starts with "252"
            if phone.startswith("252"):
                phone = phone[3:]
            
            # Remove leading zero if present
            if phone.startswith("0"):
                phone = phone[1:]
            
            # Add the correct country code
            phone = f"+252{phone}"

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
