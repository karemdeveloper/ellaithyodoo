from odoo import http
from odoo.http import request
from markupsafe import escape


class EllaithyPosSalaryExport(http.Controller):
    @http.route('/ellaithy_pos/salary_export', type='http', auth='user')
    def salary_export(self, ids=None, **kw):
        user = request.env.user
        if not (user.has_group('ellaithy_pos.group_ellaithy_pos_operator') or user.has_group('ellaithy_pos.group_ellaithy_pos_admin')):
            return request.not_found()
        domain = [('state', '=', 'done'), ('settlement_type', '=', 'salary')]
        if ids:
            try:
                selected = [int(x) for x in ids.split(',') if x.strip()]
            except Exception:
                selected = []
            if selected:
                domain.append(('id', 'in', selected))
        orders = request.env['ellaithy.pos.order'].sudo().search(domain, order='request_date desc')
        rows = []
        for o in orders:
            rows.append('<tr>' + ''.join([
                f'<td>{escape(o.name or "")}</td>',
                f'<td>{escape(o.requester_id.name or "")}</td>',
                f'<td>{escape(o.branch_id.display_name or "")}</td>',
                f'<td>{escape(o.warehouse_id.name or "")}</td>',
                f'<td>{o.request_date or ""}</td>',
                f'<td>{o.amount_total:.2f}</td>',
                f'<td>{"Paid" if o.salary_paid else "On Salary"}</td>',
                f'<td>{o.salary_paid_date or ""}</td>',
            ]) + '</tr>')
        html = '''<html><head><meta charset="utf-8"></head><body><table border="1">
        <tr><th>Order</th><th>Requester</th><th>Branch</th><th>Warehouse</th><th>Date</th><th>Total</th><th>Salary Status</th><th>Paid Date</th></tr>%s
        </table></body></html>''' % ''.join(rows)
        headers = [
            ('Content-Type', 'application/vnd.ms-excel; charset=utf-8'),
            ('Content-Disposition', 'attachment; filename="salary_orders.xls"'),
        ]
        return request.make_response(html, headers=headers)
