import frappe
import requests

SANDBOX_URL = "https://ims.pral.com.pk/ims/sandbox/api/Live/PostData"
PRODUCTION_URL = "https://ims.pral.com.pk/ims/production/api/Live/PostData"


class PRAFiscalAPI:
	"""Thin wrapper around PRA's hosted IMS 'PostData' endpoint.

	PRAL's spec (section 7.2.2 "Web Client to post data from Cloud") documents this
	direct, Bearer-token-authenticated POST as the integration path for a hosted
	server component - as opposed to the local Windows fiscal device meant for
	desktop POS clients. Section 12 confirms this by describing "Hosting Server
	Whitelisting" for exactly this scenario.
	"""

	def __init__(self, settings):
		self.settings = settings
		settings_doc = frappe.get_doc("Pra Settings Item", self.settings.get("name"))
		self.token = settings_doc.get_password("token")

		environment = self.settings.get("environment")
		if environment == "production":
			self.url = PRODUCTION_URL
		elif environment == "sandbox":
			self.url = SANDBOX_URL
		else:
			frappe.throw("Please select a valid environment in Pra Settings Item")

	def init_request(self):
		self.headers = {
			"Content-Type": "application/json",
			"Authorization": f"Bearer {self.token}",
		}
		self.session = requests.Session()
		self.session.headers.update(self.headers)

	def post_invoice(self, data):
		"""POST the invoice model to PRA and return the parsed JSON response."""
		self.init_request()

		try:
			response = self.session.post(
				self.url,
				json=data,
				timeout=30,
			)
		except requests.exceptions.RequestException as e:
			frappe.log_error(
				title="PRA Fiscalization API Connection Error",
				message=str(e),
			)
			frappe.throw("Unable to connect to PRA Fiscalization API")

		if response.status_code != 200:
			frappe.log_error(
				title="PRA Fiscalization API Error",
				message=response.text,
			)
			frappe.throw(f"Error in PRA Fiscalization API: {response.text}")

		return response.json()
