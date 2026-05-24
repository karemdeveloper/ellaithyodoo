# IBS API Integration — Technical Documentation

**Module:** `ibs_api_integration`  
**Version:** 18.0  
**Author:** ibs  
**Website:** <https://ibs-egy.com/>

---

## Table of Contents

1. [Overview](#1-overview)
2. [Authentication](#2-authentication)
3. [Response Envelope](#3-response-envelope)
4. [Resources Endpoint](#4-resources-endpoint)
5. [Query Parameters](#5-query-parameters)
6. [Error Reference](#6-error-reference)
7. [Examples — Sale Orders](#7-examples--sale-orders)
8. [Examples — Contacts](#8-examples--contacts)
9. [Examples — Products](#9-examples--products)
10. [Converting to PDF](#10-converting-to-pdf)

---

## 1. Overview

The **IBS API Integration** module exposes every Odoo model through a secure,
token-authenticated REST API. It supports standard CRUD operations, flexible
field selection, server-side filtering (domain), pagination, relational-field
population, and on-the-fly image URL conversion.

**Base URL:** `http://<your-odoo-host>:8069`  
**API prefix:** `/api/v1`  
**Content-Type:** `application/json`

---

## 2. Authentication

### 2.1 Obtain a Token

**POST** `/api/v1/auth/token`

Credentials are passed as **HTTP headers** (not in the body) so they are
never captured by web-server access logs.

| Header     | Required | Description              |
|------------|----------|--------------------------|
| `db`       | Yes      | Odoo database name       |
| `username` | Yes      | Odoo user login          |
| `password` | Yes      | Odoo user password       |

**Response 200**

```json
{
  "status": true,
  "data": {
    "uid": 2,
    "company_id": 1,
    "partner_id": 3,
    "employee_id": null,
    "access_token": "ibs_T4bCd8..."
  }
}
```

> Tokens are valid for **30 days**. Requesting a new token while one is still
> valid returns the existing token rather than creating a duplicate.

---

### 2.2 Use the Token

Add the token to every protected request via the `Authorization` header:

```
Authorization: Bearer ibs_T4bCd8...
```

---

### 2.3 Revoke a Token

**DELETE** `/api/v1/auth/token?access_token=<token>`

| Parameter      | Where        | Description           |
|----------------|--------------|-----------------------|
| `access_token` | Query string | Token to invalidate   |

**Response 200**

```json
{
  "status": true,
  "data": { "message": "Token successfully revoked", "revoked": true }
}
```

---

## 3. Response Envelope

### 3.1 Success

```json
{
  "status": true,
  "data": [ ... ],
  "pagination": { ... }
}
```

`data` is always an array (even for single-record requests).  
`pagination` is only present on list endpoints.

### 3.2 Error

```json
{
  "status": false,
  "error": {
    "type": "record_not_found",
    "message": "Record with ID 99 not found"
  }
}
```

### 3.3 Pagination Object

```json
{
  "total_count": 150,
  "page_size": 20,
  "current_page": 2,
  "num_pages": 8,
  "next": "http://localhost:8069/api/v1/resources/sale.order?page_number=3&page_size=20",
  "previous": "http://localhost:8069/api/v1/resources/sale.order?page_number=1&page_size=20"
}
```

---

## 4. Resources Endpoint

All model CRUD operations share the base route pattern:

```
/api/v1/resources/<model>
/api/v1/resources/<model>/<id>
/api/v1/resources/<model>/<id>/<action>
```

`<model>` is the Odoo technical model name (e.g. `sale.order`, `res.partner`,
`product.product`).

All routes require a valid `Authorization: Bearer <token>` header.

---

### 4.1 GET — List Records

**GET** `/api/v1/resources/<model>`

Returns a paginated list of records. Supports all query parameters described
in [Section 5](#5-query-parameters).

---

### 4.2 GET — Single Record

**GET** `/api/v1/resources/<model>/<id>`

Returns a single-element array for the record with the given ID.

**Response 200**

```json
{
  "status": true,
  "data": [
    { "id": 42, "name": "S00042", "state": "sale", ... }
  ]
}
```

---

### 4.3 POST — Create Record

**POST** `/api/v1/resources/<model>`

Request body must be a JSON object (single record) or a JSON array (batch
create). Field values follow standard Odoo ORM conventions.

**Many2many / One2many fields** accept a plain array of IDs — the API
automatically converts them to Odoo's `(6, 0, ids)` write command.

**Body (single)**

```json
{
  "partner_id": 7,
  "order_line": [
    { "product_id": 1, "product_uom_qty": 2, "price_unit": 150.00 }
  ]
}
```

**Body (batch)**

```json
[
  { "partner_id": 7, "name": "Order A" },
  { "partner_id": 9, "name": "Order B" }
]
```

**Optional context key:** pass `__context` inside the body to set Odoo context:

```json
{
  "__context": { "mail_notrack": true },
  "partner_id": 7
}
```

---

### 4.4 PATCH — Update Record

**PATCH** `/api/v1/resources/<model>/<id>`

Request body is a JSON object containing only the fields to update.

```json
{ "state": "cancel" }
```

Returns the updated record (with the same optional field selection, populate,
and image_urls parameters as GET).

---

### 4.5 DELETE — Delete Record

**DELETE** `/api/v1/resources/<model>/<id>`

**Response 200**

```json
{
  "status": true,
  "data": { "message": "Record 42 deleted successfully", "deleted_id": 42 }
}
```

---

### 4.6 POST — Call Model Action

**POST** `/api/v1/resources/<model>/<id>/<action>`

Calls a public (non-underscore-prefixed) method on the record.

```
POST /api/v1/resources/sale.order/42/action_confirm
```

Pass method arguments as a JSON body:

```json
{ "send_email": true }
```

**Response 200**

```json
{
  "status": true,
  "data": {
    "action": "action_confirm",
    "record_id": 42,
    "result": true
  }
}
```

---

## 5. Query Parameters

### 5.1 `domain`

Odoo search domain in Python list syntax. URL-encode the value.

```
?domain=[('state','=','sale')]
?domain=[('amount_total','>',1000),('state','in',['sale','done'])]
?domain=[('partner_id.country_id.code','=','EG')]
```

| Operator | Meaning                    |
|----------|----------------------------|
| `=`      | Equal                      |
| `!=`     | Not equal                  |
| `>`      | Greater than               |
| `<`      | Less than                  |
| `>=`     | Greater than or equal      |
| `<=`     | Less than or equal         |
| `like`   | Contains (case-sensitive)  |
| `ilike`  | Contains (case-insensitive)|
| `in`     | In list                    |
| `not in` | Not in list                |

---

### 5.2 `fields`

Comma-separated list of field names to return. Omit to get all fields.

```
?fields=id,name,state,amount_total,partner_id,date_order
```

---

### 5.3 Pagination

**Offset / Limit style**

```
?offset=0&limit=20
?offset=20&limit=20
```

**Page style** (preferred for UIs)

```
?page_size=20&page_number=1
?page_size=20&page_number=2
```

Both styles return a `pagination` object in the response.

---

### 5.4 `order`

Sort expression, same as Odoo `search()`.

```
?order=date_order desc
?order=name asc
?order=amount_total desc,name asc
```

---

### 5.5 `populate`

Resolve relational fields (Many2one, One2many, Many2many) into full nested
objects instead of raw IDs.

**Syntax**

```
field_name[:sub_field1,sub_field2][|other_field[:...]]
```

| Example                                              | Effect                                                  |
|------------------------------------------------------|---------------------------------------------------------|
| `partner_id`                                         | All fields of the related partner                       |
| `partner_id:name,email,phone`                        | Only name, email, phone from partner                    |
| `order_line:product_id,product_uom_qty,price_unit`   | Specific fields from each order line                    |
| `partner_id:name,email\|order_line:product_id,price_unit` | Multiple fields in one request                     |
| `partner_id:user_ids:name,login`                     | Nested: partner → users → name & login                 |

**Without populate (default)**

```json
{ "partner_id": [7, "Azure Interior"] }
```

**With `?populate=partner_id:name,email,phone`**

```json
{
  "partner_id": {
    "id": 7,
    "name": "Azure Interior",
    "email": "azure@example.com",
    "phone": "+1 (555) 555-5555"
  }
}
```

---

### 5.6 `image_urls` / `convert_images`

Convert binary image fields to URL strings instead of returning raw base64.

```
?image_urls=true
?convert_images=true
```

Accepted truthy values: `true`, `1`, `yes`, `on`.

The API replaces each image field value with `null` and adds a `<field>_url`
key pointing to Odoo's `/web/image` endpoint (which handles filestore,
resizing, caching, and access control automatically).

**Before**

```json
{ "image_1920": "base64_encoded_data_..." }
```

**After**

```json
{
  "image_1920": null,
  "image_1920_url": "http://localhost:8069/web/image?model=res.partner&id=7&field=image_1920&unique=2025-05-01+12:00:00"
}
```

Detected image field names: `image`, `image_1920`, `image_1024`, `image_512`,
`image_256`, `image_128`, `avatar`, `photo`, `picture`, `logo`, `icon`.

---

### 5.7 `lang`

Return translatable field values in the specified language.

```
?lang=ar_001
?lang=en_US
?lang=fr_FR
```

---

## 6. Error Reference

| `error.type`          | HTTP | Cause                                         |
|-----------------------|------|-----------------------------------------------|
| `missing_authorization` | 401 | No `Authorization` header sent               |
| `invalid_authorization` | 401 | Header not in `Bearer <token>` format        |
| `invalid_token`       | 401  | Token not found in the database               |
| `expired_token`       | 401  | Token exists but has passed its 30-day expiry |
| `access_denied`       | 401  | Wrong username or password at login           |
| `access_error`        | 403  | User lacks permission on the model/record     |
| `model_not_available` | 404  | Model name not found in `ir.model`            |
| `record_not_found`    | 404  | Record ID does not exist                      |
| `method_not_found`    | 404  | Action name not found or is private (`_`)     |
| `not_callable`        | 400  | Action exists but is not a method             |
| `missing_params`      | 400  | Required parameters absent                    |
| `missing_id`          | 400  | ID required but not provided (PATCH/DELETE)   |
| `invalid_parameters`  | 400  | Malformed JSON body or bad field values        |
| `delete_error`        | 400  | Record cannot be deleted (constraint)         |
| `server_error`        | 500  | Unexpected server-side exception              |

---

## 7. Examples — Sale Orders

### 7.1 Get All Confirmed Orders (Paginated)

```
GET /api/v1/resources/sale.order
    ?domain=[('state','=','sale')]
    &fields=id,name,state,amount_total,partner_id,date_order
    &page_size=10
    &page_number=1
    &order=date_order desc
Authorization: Bearer ibs_...
```

### 7.2 Get Orders with Customer Details (Populate)

```
GET /api/v1/resources/sale.order
    ?fields=id,name,state,amount_total,partner_id,order_line
    &populate=partner_id:name,email,phone|order_line:product_id,product_uom_qty,price_unit
    &page_size=5
    &page_number=1
Authorization: Bearer ibs_...
```

**Response excerpt**

```json
{
  "status": true,
  "data": [
    {
      "id": 1,
      "name": "S00001",
      "state": "sale",
      "amount_total": 1500.0,
      "partner_id": {
        "id": 7,
        "name": "Azure Interior",
        "email": "azure@example.com",
        "phone": "+1 (555) 555-5555"
      },
      "order_line": [
        {
          "id": 11,
          "product_id": [1, "Laptop"],
          "product_uom_qty": 2.0,
          "price_unit": 750.0
        }
      ]
    }
  ],
  "pagination": {
    "total_count": 42,
    "page_size": 5,
    "current_page": 1,
    "num_pages": 9,
    "next": "http://localhost:8069/api/v1/resources/sale.order?page_number=2&page_size=5",
    "previous": null
  }
}
```

### 7.3 Create a Sale Order

```
POST /api/v1/resources/sale.order
Authorization: Bearer ibs_...
Content-Type: application/json

{
  "partner_id": 7,
  "order_line": [
    { "product_id": 1, "product_uom_qty": 3, "price_unit": 500.00 },
    { "product_id": 2, "product_uom_qty": 1, "price_unit": 200.00 }
  ]
}
```

### 7.4 Confirm a Sale Order

```
POST /api/v1/resources/sale.order/42/action_confirm
Authorization: Bearer ibs_...
```

### 7.5 Update Order State

```
PATCH /api/v1/resources/sale.order/42
Authorization: Bearer ibs_...
Content-Type: application/json

{ "note": "Urgent delivery requested." }
```

### 7.6 Delete a Draft Order

```
DELETE /api/v1/resources/sale.order/42
Authorization: Bearer ibs_...
```

---

## 8. Examples — Contacts

### 8.1 Get All Companies

```
GET /api/v1/resources/res.partner
    ?domain=[('is_company','=',true)]
    &fields=id,name,email,phone,country_id
    &page_size=20&page_number=1
Authorization: Bearer ibs_...
```

### 8.2 Get Partners with Country Details (Nested Populate)

```
GET /api/v1/resources/res.partner
    ?fields=id,name,email,country_id
    &populate=country_id:name,code
    &page_size=10&page_number=1
Authorization: Bearer ibs_...
```

### 8.3 Get Partners with Profile Images as URLs

```
GET /api/v1/resources/res.partner
    ?fields=id,name,image_1920
    &image_urls=true
    &page_size=10&page_number=1
Authorization: Bearer ibs_...
```

---

## 9. Examples — Products

### 9.1 Get All Products with Images

```
GET /api/v1/resources/product.product
    ?fields=id,name,list_price,categ_id,image_1920
    &image_urls=true
    &page_size=20&page_number=1
Authorization: Bearer ibs_...
```

### 9.2 Filter Products by Category and Price

```
GET /api/v1/resources/product.product
    ?domain=[('categ_id.name','ilike','office'),('list_price','<',500)]
    &fields=id,name,list_price,default_code
    &order=list_price asc
    &page_size=50&page_number=1
Authorization: Bearer ibs_...
```

### 9.3 Get Product with Category and Supplier Info

```
GET /api/v1/resources/product.template
    ?fields=id,name,list_price,categ_id,seller_ids
    &populate=categ_id:name,complete_name|seller_ids:name,price
    &page_size=10&page_number=1
Authorization: Bearer ibs_...
```

---

## 10. Converting to PDF

This document is authored in Markdown. To generate a styled PDF:

**Using Pandoc (recommended)**

```bash
pandoc IBS_API_Documentation.md \
  -o IBS_API_Documentation.pdf \
  --pdf-engine=wkhtmltopdf \
  --toc \
  -V geometry:margin=2cm
```

**Using VS Code**

Install the *Markdown PDF* extension, open this file, and run
`Markdown PDF: Export (pdf)` from the Command Palette.

**Using a browser**

Open the rendered Markdown preview in your browser and use
**File → Print → Save as PDF**. Enable "Background graphics" for best results.
