### PRA POS Fiscalization

App to integrate PRA (Punjab Revenue Authority) POS Software Fiscal Device (IMS) with ERPNext Sales Invoices, based on PRAL's "Technical Specification for Data Sharing through Software Fiscal Device with PRA" (v1.2).

Invoices are posted directly to PRA's hosted IMS endpoint (the "Web Client to post data from Cloud" flow documented by PRAL), so no local Windows fiscal device / IMS installer is required on the server.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app pra
```

### Setup

1. Register the business/branch on the PRA portal (https://reg.pra.punjab.gov.pk/) to obtain a **POS ID** and **Token**.
2. Create a **Pra Settings Item** for the Company with the POS ID, Token and Environment (Sandbox/Production).
3. Ask PRA (eims@pra.punjab.gov.pk) to whitelist this server's public IP for the PNTN/POS ID (required before Production posting will succeed).
4. Set `custom_pct_code` on each Item that should be fiscalized (PCT/HS classification code from the 2nd Schedule of the PSTS Act 2012).
5. Enable **Post to PRA** on a Sales Invoice to fiscalize it on submit.

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/pra
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
