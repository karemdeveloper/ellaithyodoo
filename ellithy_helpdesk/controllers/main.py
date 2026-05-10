from odoo import http
from odoo.http import request
import json
import traceback


class DynamicsRestHelpdeskController(http.Controller):

    @http.route('/api/helpdesk/create_refund_ticket', type='http', auth='none', methods=['POST'], csrf=False)
    def create_ticket_rest(self, **kwargs):
        headers = {'Content-Type': 'application/json'}

        api_key = request.httprequest.headers.get('X-Api-Key')
        if api_key != "AX-Odoo-Secure-Key-2026":
            return request.make_response(json.dumps({'error': 'Unauthorized'}), headers=headers, status=401)

        try:
            body = request.httprequest.data
            data = json.loads(body) if body else {}

            notes = data.get('notes', '')
            description = data.get('description', 'REST API Request from Dynamics AX')

            user_admin = request.env['res.users'].sudo().browse(2)

            team = request.env['helpdesk.team'].with_user(user_admin).sudo().search([
                ('name', 'ilike', 'Accounting')
            ], limit=1)

            if not team:
                return request.make_response(json.dumps({'error': 'Accounting team not found'}), headers=headers,
                                             status=404)

            task_type = request.env['helpdesk.task.type'].with_user(user_admin).sudo().search([
                ('name', 'ilike', 'Refund'),
                ('team_id', '=', team.id)
            ], limit=1)

            ticket_name = task_type.name if task_type else "Refund Request (REST)"
            stage_obj = team._determine_stage()[team.id] if team else False

            # new_ticket = request.env['helpdesk.ticket'].with_user(user_admin).sudo().with_context(
            #     is_api_request=True).create({
            #     'name': ticket_name,
            #     'team_id': team.id,
            #     'task_type_id': task_type.id if task_type else False,
            #     'notes': notes,
            #     'description': description,
            #     'stage_id': stage_obj.id if stage_obj else False,
            # })

            new_ticket = request.env['helpdesk.ticket'].with_user(user_admin).sudo().create({
                'name': ticket_name,
                'team_id': team.id,
                'task_type_id': task_type.id if task_type else False,
                'notes': notes,
                'description': description,
                'stage_id': stage_obj.id if stage_obj else False,
            })

            response_data = {
                'id': new_ticket.id,
                'status': 'success',
                'message': 'Ticket created via REST API'
            }
            return request.make_response(json.dumps(response_data), headers=headers, status=201)

        except Exception as e:
            error_msg = {'error': str(e)}
            return request.make_response(json.dumps(error_msg), headers=headers, status=500)




# from odoo import http
# from odoo.http import request
# import traceback
#
# class DynamicsHelpdeskController(http.Controller):
#
#     @http.route('/api/helpdesk/create_refund_ticket', type='json', auth='none', methods=['POST'], csrf=False)
#     def create_ticket_from_ax(self, **post):
#         api_key_from_ax = request.httprequest.headers.get('X-Api-Key')
#         actual_api_key = "AX-Odoo-Secure-Key-2026"
#
#         if api_key_from_ax != actual_api_key:
#             return {'status': 'error', 'message': 'Unauthorized'}
#
#         try:
#             user_admin = request.env['res.users'].sudo().browse(2)
#
#             team = request.env['helpdesk.team'].with_user(user_admin).sudo().search([('name', '=', 'Accounting')],
#                                                                                     limit=1)
#
#             if not team:
#                 return {'status': 'error', 'message': 'Team Accounting not found'}
#
#             task_type = request.env['helpdesk.task.type'].with_user(user_admin).sudo().search([
#                 ('name', '=', 'Refund'),
#                 ('team_id', '=', team.id)
#             ], limit=1)
#
#             notes = post.get('notes', '')
#             description = post.get('description', 'Automated request from Dynamics AX')
#             stage_obj = team._determine_stage()[team.id] if team else False
#
#             new_ticket = request.env['helpdesk.ticket'].with_user(user_admin).sudo().with_context(
#                 is_api_request=True).create({
#                 'name': task_type.name,
#                 'team_id': team.id,
#                 'task_type_id': task_type.id,
#                 'notes': notes,
#                 'description': description,
#                 'user_id': False,
#                 'stage_id': stage_obj.id if stage_obj else False,
#             })
#
#             return {
#                 'status': 'success',
#                 'ticket_id': new_ticket.id,
#                 'message': 'Ticket created successfully.'
#             }
#
#         except Exception as e:
#             print("!!!!!!!!!! FINAL FIX TRACEBACK !!!!!!!!!!")
#             traceback.print_exc()
#             return {'status': 'error', 'message': str(e)}
#

# from odoo import http
# from odoo.http import request
# import json
#
#
# class DynamicsHelpdeskController(http.Controller):
#
#     @http.route('/api/helpdesk/create_ticket', type='json', auth='none', methods=['POST'], csrf=False)
#     def create_ticket_from_ax(self, **post):
#         try:
#             team = request.env['helpdesk.team'].sudo().search([('name', '=', 'Accounting')], limit=1)
#
#             if not team:
#                 return {
#                     'status': 'error',
#                     'message': 'Target team "Accounting" not found in Odoo.'
#                 }
#
#             data = request.jsonrequest.get('params', {})
#
#             task_type_id = data.get('task_type_id')
#             notes = data.get('notes')
#             description = data.get('description', 'Created from Dynamics AX')
#
#             if not task_type_id:
#                 return {
#                     'status': 'error',
#                     'message': 'Missing required field: task_type_id'
#                 }
#
#             ticket_values = {
#                 'team_id': team.id,
#                 'task_type_id': int(task_type_id),
#                 'notes': notes,
#                 'description': description,
#             }
#
#             new_ticket = request.env['helpdesk.ticket'].sudo().create(ticket_values)
#
#             return {
#                 'status': 'success',
#                 'message': 'Ticket created successfully',
#                 'odoo_ticket_id': new_ticket.id,
#                 'ticket_subject': new_ticket.name
#             }
#
#         except Exception as e:
#             return {
#                 'status': 'error',
#                 'message': str(e)
#             }