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
            phone_number = self.format_phone_number(number)
            receiver_numbers.append(phone_number)
            self.send_sms(settings, phone_number, message)
            self.create_message_sms(phone_number, message)
        frappe.msgprint(_(f"Hormuud SMS sent to {', '.join(receiver_numbers)}"))

    def send_whatsapp_msg(self, doc, context):
        settings = frappe.get_doc("Four Whats Net Configuration")
        recipients = self.get_receiver_list(doc, context)
        receiver_numbers = []
        for recipient in recipients:
            number = frappe.render_template(recipient, context)
            message = frappe.render_template(self.message, context)
            phone_number = self.format_phone_number(number)
            receiver_numbers.append(phone_number)
            self.send_whatsapp(settings, phone_number, message)
            self.create_message_record(phone_number, message)
        frappe.msgprint(_(f"WhatsApp message sent to {', '.join(receiver_numbers)}"))

    def format_phone_number(self, number):
        phone_number = number.replace("+", "").replace("-", "").strip()
        if phone_number.startswith("252"):
            return f"+{phone_number}"
        if phone_number.startswith("0"):
            phone_number = phone_number[1:]
        return f"+252{phone_number}"

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

    def send_whatsapp(self, settings, phone_number, message):
        url = f"{settings.api_url}/sendMessage/?instanceid={settings.instance_id}&token={settings.token}&phone={phone_number}&body={message}"
        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            frappe.log_error(frappe.get_traceback(), _("Failed to send WhatsApp message"))
            frappe.throw(f"Failed to send WhatsApp message: {str(e)}")

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
