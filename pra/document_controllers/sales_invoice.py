import frappe
import pyqrcode
from decimal import Decimal, ROUND_HALF_UP
from frappe.utils import cint, flt, get_datetime

from pra.api import PRAFiscalAPI

# Free-text PRA "PaymentMode" keywords -> PRA integer code (section 7 Invoice Model).
# Longest/most specific keywords should be checked before generic ones.
PRA_PAYMENT_MODE_KEYWORDS = [
	("cheque", 6),
	("check", 6),
	("gift voucher", 3),
	("voucher", 3),
	("loyalty", 4),
	("card", 2),
	("cash", 1),
]

PRA_QR_VERIFICATION_URL = "https://reg.pra.punjab.gov.pk/IMSFiscalReport/SearchPOSInvoice_Report.aspx?PRAInvNo={}"


def on_submit(doc, method=None):
	"""Hooked via doc_events (not override_doctype_class) so this app can coexist
	with other Sales Invoice integrations installed on the same site."""

	if not doc.get("custom_post_to_pra"):
		return

	settings = get_settings_item(doc.company)
	if not settings:
		frappe.throw(f"No Pra Settings Item found for company {doc.company}. Please configure it first.")

	data = get_mapped_data(doc, settings)

	log = frappe.new_doc("Pra Request Log")
	log.sales_invoice = doc.name
	log.request_data = frappe.as_json(data, indent=4)
	log.insert(ignore_permissions=True)

	frappe.db.set_value("Sales Invoice", doc.name, "custom_usin", data.get("USIN"))

	api = PRAFiscalAPI(settings)

	try:
		response = api.post_invoice(data)
	except Exception as e:
		log.error = str(e)
		log.save(ignore_permissions=True)
		frappe.log_error(title="PRA Fiscalization API Exception", message=str(e))
		frappe.throw(f"Error while submitting invoice to PRA: {e}")

	log.response_data = frappe.as_json(response, indent=4)

	if str(response.get("Code")) == "100" and response.get("InvoiceNumber"):
		log.save(ignore_permissions=True)

		pra_invoice_no = str(response.get("InvoiceNumber"))
		frappe.db.set_value("Sales Invoice", doc.name, "custom_pra_invoice_no", pra_invoice_no)

		safe_name = doc.name.replace("/", "-")
		verification_url = PRA_QR_VERIFICATION_URL.format(pra_invoice_no)
		qr = pyqrcode.create(verification_url)
		qr.svg(frappe.get_site_path() + "/public/files/" + safe_name + "_pra_qrcode.svg", scale=8)
		frappe.db.set_value(
			"Sales Invoice", doc.name, "custom_pra_qr_code", "/files/" + safe_name + "_pra_qrcode.svg"
		)

		frappe.msgprint("Invoice successfully submitted to PRA.")
	else:
		log.save(ignore_permissions=True)
		frappe.log_error(
			title="PRA Fiscalization API Error",
			message=frappe.as_json(response, indent=4),
		)
		frappe.throw(f"Error in PRA Fiscalization: {response.get('Response') or response}")


def get_settings_item(company):
	if not company:
		return None

	doc_name = frappe.db.get_value("Pra Settings Item", {"company": company}, "name")
	if not doc_name:
		return None

	return frappe.get_doc("Pra Settings Item", doc_name).as_dict()


def get_mapped_data(doc, settings):
	items = get_items(doc)
	invoice_type = get_invoice_type(doc)

	total_sale_value = round_half_up(sum(flt(i["SaleValue"]) for i in items))
	total_tax_charged = round_half_up(sum(flt(i["TaxCharged"]) for i in items))
	total_discount = round_half_up(sum(flt(i["Discount"]) for i in items))
	total_bill_amount = round_half_up(total_sale_value + total_tax_charged - total_discount)
	total_quantity = round_half_up(sum(flt(i["Quantity"]) for i in items))

	data = {
		"InvoiceNumber": "",
		"POSID": cint(settings.get("pos_id")),
		"USIN": get_usin(doc.name),
		"RefUSIN": get_usin(doc.return_against) if invoice_type != 1 and doc.get("return_against") else None,
		"DateTime": get_pra_datetime(doc),
		"BuyerName": doc.customer_name or "",
		"BuyerPNTN": doc.tax_id or "",
		"BuyerCNIC": get_buyer_cnic(doc),
		"BuyerPhoneNumber": doc.contact_mobile or "",
		"TotalQuantity": total_quantity,
		"TotalSaleValue": total_sale_value,
		"TotalTaxCharged": total_tax_charged,
		"Discount": total_discount,
		"FurtherTax": 0,
		"TotalBillAmount": total_bill_amount,
		"PaymentMode": derive_payment_mode(doc),
		"InvoiceType": invoice_type,
		"Items": items,
	}
	return data


def get_items(doc):
	tax_rate = 0
	try:
		if doc.taxes:
			tax_rate = flt(doc.taxes[0].rate)
	except (IndexError, AttributeError):
		tax_rate = 0

	invoice_type = get_invoice_type(doc)
	ref_usin = get_usin(doc.return_against) if invoice_type != 1 and doc.get("return_against") else None

	items = []
	for item in doc.items:
		pct_code = item.get("custom_pct_code")
		if not pct_code:
			frappe.throw(f"Please set PCT Code for item {item.item_code} before posting to PRA")

		sale_value = round_half_up(item.amount)
		discount = round_half_up(item.get("discount_amount") or 0)
		tax_charged = round_half_up(sale_value * (tax_rate / 100)) if tax_rate else 0
		total_amount = round_half_up(sale_value + tax_charged)

		items.append(
			{
				"ItemCode": item.item_code,
				"ItemName": item.item_name,
				"PCTCode": pct_code,
				"Quantity": round_half_up(item.qty),
				"TaxRate": tax_rate,
				"SaleValue": sale_value,
				"Discount": discount,
				"FurtherTax": 0,
				"TaxCharged": tax_charged,
				"TotalAmount": total_amount,
				"InvoiceType": invoice_type,
				"RefUSIN": ref_usin,
			}
		)

	return items


def derive_payment_mode(doc):
	"""Map ERPNext payment info to PRA's PaymentMode int.
	1 Cash, 2 Card, 3 Gift Voucher, 4 Loyalty Card, 5 Mixed, 6 Cheque.
	"""
	rows = [p for p in (doc.get("payments") or []) if flt(p.amount) > 0]

	codes = set()
	for row in rows:
		mode_name = (row.mode_of_payment or "").strip().lower()
		code = 1
		for keyword, mapped_code in PRA_PAYMENT_MODE_KEYWORDS:
			if keyword in mode_name:
				code = mapped_code
				break
		codes.add(code)

	if doc.get("redeem_loyalty_points") and flt(doc.get("loyalty_amount")) > 0:
		codes.add(4)

	if not codes:
		# No payment breakup available (e.g. invoice booked on credit) - PRA has no
		# "on account" code, so default conservatively to Cash.
		return 1

	if len(codes) == 1:
		return codes.pop()

	return 5


def get_invoice_type(doc):
	if doc.get("is_return"):
		return 3
	if doc.get("is_debit_note"):
		return 2
	return 1


def get_usin(invoice_name):
	return (invoice_name or "").replace("/", "-")[:50]


def get_buyer_cnic(doc):
	if not doc.customer:
		return ""
	return frappe.db.get_value("Customer", doc.customer, "custom_cnic") or ""


def get_pra_datetime(doc):
	dt = get_datetime(f"{doc.posting_date} {doc.posting_time or '00:00:00'}")
	return dt.strftime("%Y-%m-%d %H:%M:%S.") + f"{dt.microsecond // 1000:03d}"


def round_half_up(value, digits=2):
	q = Decimal(10) ** -digits
	return float(Decimal(str(value or 0)).quantize(q, rounding=ROUND_HALF_UP))
