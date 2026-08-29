app_name = "pra"
app_title = "Pra"
app_publisher = "Safdar Ali"
app_description = "App to integrate PRA (Punjab Revenue Authority) POS Fiscalization."
app_email = "safdar211@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Document Events
# ---------------
# Uses doc_events (not override_doctype_class) deliberately: this app is designed
# to coexist on the same site as other Sales Invoice integrations (e.g. the fbr
# app), and only one app's override_doctype_class for a given doctype can win at a
# time. doc_events fires alongside any such override, regardless of which app owns
# the base controller class.

doc_events = {
	"Sales Invoice": {
		"on_submit": "pra.document_controllers.sales_invoice.on_submit",
	}
}

# Scheduled Tasks
# ---------------

# scheduler_events = {}
