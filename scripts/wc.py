#!/usr/bin/env python3
"""
wc.py — WooCommerce CLI for madkrab.com

Requires env vars:
  WC_CONSUMER_KEY
  WC_CONSUMER_SECRET
  WC_SITE_URL

Usage:
  python3 scripts/wc.py <resource> <action> [id] [options]

Resources & Actions:
  products  list                          List all products
  products  get      <id>                 Get a single product
  products  create   <json_file>          Create product from JSON file
  products  update   <id> <json_file>     Update product from JSON file
  products  delete   <id>                 Permanently delete a product

  variations list    <product_id>         List variations for a product
  variations get     <product_id> <v_id>  Get a single variation
  variations create  <product_id> <file>  Create variation from JSON file
  variations update  <product_id> <v_id> <file>
  variations delete  <product_id> <v_id>  Delete a variation

  orders    list     [--status <s>]       List orders (default: any)
  orders    get      <id>                 Get a single order
  orders    update   <id> <json_file>     Update order from JSON file

  customers list                          List customers
  customers get      <id>                 Get a single customer

  categories list                         List product categories
  categories create  <json_file>          Create category from JSON file

  reports   sales                         Sales report
  reports   top-sellers                   Top selling products

Options:
  --json      Output raw JSON instead of formatted summary
  --status    Filter by status (orders: pending, processing, completed, any)
  --per-page  Number of results (default: 50)
"""

import sys, os, json, urllib.request, urllib.parse

# ── Auth ────────────────────────────────────────────────────────────────────

def get_env():
    key    = os.environ.get("WC_CONSUMER_KEY")
    secret = os.environ.get("WC_CONSUMER_SECRET")
    base   = os.environ.get("WC_SITE_URL", "").rstrip("/")
    if not all([key, secret, base]):
        print("Error: WC_CONSUMER_KEY, WC_CONSUMER_SECRET, WC_SITE_URL must be set.")
        sys.exit(1)
    return key, secret, base

def wc_url(base, path, params=None):
    key, secret, _ = get_env()
    p = {"consumer_key": key, "consumer_secret": secret, "per_page": "50"}
    if params:
        p.update(params)
    return f"{base}/wp-json/wc/v3/{path}?{urllib.parse.urlencode(p)}"

def api(method, path, body=None, params=None):
    key, secret, base = get_env()
    url = wc_url(base, path, params)
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 Chrome/120.0"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()}")
        sys.exit(1)

def load_json_file(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {path}: {e}")
        sys.exit(1)

# ── Formatters ───────────────────────────────────────────────────────────────

def fmt_products(products):
    print(f"\n  {'ID':<6} {'STATUS':<10} {'STOCK':<12} {'PRICE':<10} {'TYPE':<10} NAME")
    print("  " + "─" * 75)
    for p in products:
        price = "$" + p["price"] if p.get("price") else "—"
        print(f"  {p['id']:<6} {p['status']:<10} {p.get('stock_status','—'):<12} {price:<10} {p['type']:<10} {p['name']}")
    print()

def fmt_product(p):
    print(f"\n  ID:           {p['id']}")
    print(f"  Name:         {p['name']}")
    print(f"  Type:         {p['type']}")
    print(f"  Status:       {p['status']}")
    print(f"  Price:        ${p['price']}" if p.get("price") else "  Price:        —")
    print(f"  Stock:        {p.get('stock_status','—')}")
    print(f"  SKU:          {p.get('sku') or '—'}")
    cats = ", ".join(c["name"] for c in p.get("categories", []))
    print(f"  Categories:   {cats or '—'}")
    tags = ", ".join(t["name"] for t in p.get("tags", []))
    print(f"  Tags:         {tags or '—'}")
    attrs = p.get("attributes", [])
    for a in attrs:
        opts = ", ".join(a.get("options", []))
        print(f"  Attr [{a['name']}]: {opts}")
    desc = p.get("short_description", "").replace("<p>","").replace("</p>","").strip()
    if desc:
        print(f"  Short desc:   {desc}")
    print(f"  URL:          {p.get('permalink','—')}")
    print()

def fmt_variations(variations, product_id):
    print(f"\n  Variations for product {product_id}:")
    print(f"  {'V_ID':<6} {'STOCK':<12} {'PRICE':<10} ATTRIBUTES")
    print("  " + "─" * 60)
    for v in variations:
        attrs = ", ".join(f"{a['name']}={a['option']}" for a in v.get("attributes", []))
        price = "$" + v["price"] if v.get("price") else "—"
        print(f"  {v['id']:<6} {v.get('stock_status','—'):<12} {price:<10} {attrs}")
    print()

def fmt_orders(orders):
    print(f"\n  {'ID':<6} {'STATUS':<14} {'TOTAL':<10} {'DATE':<12} CUSTOMER")
    print("  " + "─" * 70)
    for o in orders:
        name = f"{o['billing'].get('first_name','')} {o['billing'].get('last_name','')}".strip()
        date = o.get("date_created", "")[:10]
        print(f"  {o['id']:<6} {o['status']:<14} ${o['total']:<9} {date:<12} {name or '—'}")
    print()

def fmt_order(o):
    print(f"\n  ID:       {o['id']}")
    print(f"  Status:   {o['status']}")
    print(f"  Total:    ${o['total']}")
    print(f"  Date:     {o.get('date_created','')[:10]}")
    b = o.get("billing", {})
    print(f"  Customer: {b.get('first_name','')} {b.get('last_name','')} <{b.get('email','')}>")
    print(f"  Items:")
    for item in o.get("line_items", []):
        print(f"    - {item['name']} x{item['quantity']}  ${item['total']}")
    print()

def fmt_customers(customers):
    print(f"\n  {'ID':<6} {'NAME':<25} EMAIL")
    print("  " + "─" * 60)
    for c in customers:
        name = f"{c.get('first_name','')} {c.get('last_name','')}".strip()
        print(f"  {c['id']:<6} {name:<25} {c.get('email','—')}")
    print()

def fmt_categories(cats):
    print(f"\n  {'ID':<6} {'COUNT':<8} NAME")
    print("  " + "─" * 40)
    for c in cats:
        print(f"  {c['id']:<6} {c.get('count',0):<8} {c['name']}")
    print()

# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_products(args, raw):
    action = args[0] if args else "list"

    if action == "list":
        data = api("GET", "products")
        if raw: print(json.dumps(data, indent=2))
        else: fmt_products(data)

    elif action == "get":
        pid = args[1]
        data = api("GET", f"products/{pid}")
        if raw: print(json.dumps(data, indent=2))
        else: fmt_product(data)

    elif action == "create":
        body = load_json_file(args[1])
        data = api("POST", "products", body=body)
        print(f"  Created product ID {data['id']}: {data['name']}")

    elif action == "update":
        pid, body = args[1], load_json_file(args[2])
        data = api("PUT", f"products/{pid}", body=body)
        print(f"  Updated product {pid}: {data['name']}")

    elif action == "delete":
        pid = args[1]
        data = api("DELETE", f"products/{pid}?force=true")
        print(f"  Deleted product {pid}: {data['name']}")

def cmd_variations(args, raw):
    action = args[0] if args else "list"

    if action == "list":
        pid = args[1]
        data = api("GET", f"products/{pid}/variations")
        if raw: print(json.dumps(data, indent=2))
        else: fmt_variations(data, pid)

    elif action == "get":
        pid, vid = args[1], args[2]
        data = api("GET", f"products/{pid}/variations/{vid}")
        if raw: print(json.dumps(data, indent=2))
        else: print(json.dumps(data, indent=2))

    elif action == "create":
        pid, body = args[1], load_json_file(args[2])
        data = api("POST", f"products/{pid}/variations", body=body)
        print(f"  Created variation {data['id']} for product {pid}")

    elif action == "update":
        pid, vid, body = args[1], args[2], load_json_file(args[3])
        data = api("PUT", f"products/{pid}/variations/{vid}", body=body)
        print(f"  Updated variation {vid} for product {pid}")

    elif action == "delete":
        pid, vid = args[1], args[2]
        api("DELETE", f"products/{pid}/variations/{vid}?force=true")
        print(f"  Deleted variation {vid} from product {pid}")

def cmd_orders(args, raw, status=None):
    action = args[0] if args else "list"
    params = {}
    if status:
        params["status"] = status

    if action == "list":
        data = api("GET", "orders", params=params if params else None)
        if raw: print(json.dumps(data, indent=2))
        else: fmt_orders(data)

    elif action == "get":
        oid = args[1]
        data = api("GET", f"orders/{oid}")
        if raw: print(json.dumps(data, indent=2))
        else: fmt_order(data)

    elif action == "update":
        oid, body = args[1], load_json_file(args[2])
        data = api("PUT", f"orders/{oid}", body=body)
        print(f"  Updated order {oid}: status={data['status']}")

def cmd_customers(args, raw):
    action = args[0] if args else "list"

    if action == "list":
        data = api("GET", "customers")
        if raw: print(json.dumps(data, indent=2))
        else: fmt_customers(data)

    elif action == "get":
        cid = args[1]
        data = api("GET", f"customers/{cid}")
        if raw: print(json.dumps(data, indent=2))
        else: print(json.dumps(data, indent=2))

def cmd_categories(args, raw):
    action = args[0] if args else "list"

    if action == "list":
        data = api("GET", "products/categories")
        if raw: print(json.dumps(data, indent=2))
        else: fmt_categories(data)

    elif action == "create":
        body = load_json_file(args[1])
        data = api("POST", "products/categories", body=body)
        print(f"  Created category {data['id']}: {data['name']}")

def cmd_reports(args, raw):
    action = args[0] if args else "sales"

    if action == "sales":
        data = api("GET", "reports/sales")
        if raw: print(json.dumps(data, indent=2))
        else:
            for r in data:
                print(f"\n  Total sales:   ${r.get('total_sales','0')}")
                print(f"  Net revenue:   ${r.get('net_revenue','0')}")
                print(f"  Orders:        {r.get('total_orders','0')}")
                print(f"  Items sold:    {r.get('total_items','0')}")
                print(f"  Customers:     {r.get('total_customers','0')}")
            print()

    elif action == "top-sellers":
        data = api("GET", "reports/top_sellers")
        if raw: print(json.dumps(data, indent=2))
        else:
            print(f"\n  {'RANK':<6} {'SOLD':<8} PRODUCT")
            print("  " + "─" * 40)
            for i, p in enumerate(data, 1):
                print(f"  {i:<6} {p.get('quantity','—'):<8} {p.get('title','—')}")
            print()

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__)
        sys.exit(0)

    raw    = "--json"   in args
    status = None
    if "--status" in args:
        idx = args.index("--status")
        status = args[idx + 1]
        args = [a for a in args if a not in ("--status", status)]
    args = [a for a in args if a != "--json"]

    resource = args[0]
    rest     = args[1:]

    dispatch = {
        "products":   lambda: cmd_products(rest, raw),
        "variations": lambda: cmd_variations(rest, raw),
        "orders":     lambda: cmd_orders(rest, raw, status),
        "customers":  lambda: cmd_customers(rest, raw),
        "categories": lambda: cmd_categories(rest, raw),
        "reports":    lambda: cmd_reports(rest, raw),
    }

    if resource not in dispatch:
        print(f"Unknown resource '{resource}'. Run with --help for usage.")
        sys.exit(1)

    dispatch[resource]()

if __name__ == "__main__":
    main()
