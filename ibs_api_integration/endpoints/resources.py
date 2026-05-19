import ast
import json
import werkzeug.urls

from odoo import http
from odoo.addons.ibs_api_integration.core.helpers import success_response, error_response, parse_request_params, populate_foreign_fields, convert_images_to_urls, process_image_fields_in_populated_data, _get_populate_field_names
from odoo.addons.ibs_api_integration.core.security import require_token
from odoo.exceptions import AccessError
from odoo.http import request

_resource_routes = [
    "/api/v1/resources/<model>", 
    "/api/v1/resources/<model>/<id>"
]

_resource_action_routes = [
    "/api/v1/resources/<model>/<id>/<action>"
]

class ResourceEndpoint(http.Controller):
    """Resource endpoints for API access"""
    
    def __init__(self):
        self._model = "ir.model"
        
    @require_token
    @http.route(_resource_action_routes, type="http", auth="none", methods=["POST"], csrf=False)
    def call_resource_action(self, model=None, id=None, action=None, **payload):
        """Call a method/action on a resource
        
        Args:
            model: The model name
            id: The record ID
            action: The method name to call
            payload: Method arguments
        """
        if not id or not action:
            return error_response("missing_params", "Record ID and action name are required", 400)
        
        try:
            model_obj = request.env[self._model].sudo().search([("model", "=", model)], limit=1)
            
            if not model_obj:
                return error_response(
                    "model_not_available",
                    f"The model {model} is not available or not enabled for API access",
                    404
                )
            
            # Get the record
            record = request.env[model_obj.model].browse(int(id))
            
            if not record.exists():
                return error_response("record_not_found", f"Record with ID {id} not found", 404)
            
            # Check if method exists
            if not hasattr(record, action) or action.startswith('_'):
                return error_response(
                    "method_not_found",
                    f"Method {action} not found or is private",
                    404
                )
            
            # Get the method
            method = getattr(record, action)
            
            # Check if it's callable
            if not callable(method):
                return error_response(
                    "not_callable",
                    f"{action} is not a callable method",
                    400
                )
            
            # Get request body for POST data
            request_body = request.httprequest.data.decode()
            args = {}
            request_context = {}
            if request_body:
                try:
                    args = json.loads(request_body)
                except:
                    args = {}

            if isinstance(args, dict):
                request_context = args.pop("__context", {}) or {}
                if request_context and not isinstance(request_context, dict):
                    return error_response("invalid_parameters", "context must be a JSON object", 400)
            else:
                args = {}

            if request_context:
                record = record.with_context(**request_context)
            
            # Call the method
            result = method(**args) if args else method()
            
            # Return the result
            return success_response({
                "action": action,
                "record_id": int(id),
                "result": result if not isinstance(result, dict) else result
            })
            
        except AccessError as e:
            return error_response("access_error", f"Access error: {e.name}", 403)
        except Exception as e:
            return error_response("server_error", str(e), 500)

    @require_token
    @http.route(_resource_routes, type="http", auth="none", methods=["GET"], csrf=False)
    def get_resource(self, model=None, id=None, **payload):
        """Retrieve resources from the specified model
        
        Args:
            model: The model name to query
            id: Specific record ID to retrieve
            payload: Additional parameters including:
                - domain: Search domain
                - fields: Fields to retrieve
                - offset: Number of records to skip
                - limit: Maximum number of records to return
                - order: Sort order
                - page_size: Number of records per page
                - page_number: Page number to retrieve
                - populate: Foreign field population config
                  Format: field_name:field1,field2|other_field:field3
                  Example: user_id:name,email|partner_id:name,phone
                  For all fields: user_id|partner_id
        """
        try:
            ioc_name = model
            model = request.env[self._model].sudo().search([("model", "=", model)], limit=1)
            
            if model:
                domain, fields, offset, limit, order, lang, populate_config = parse_request_params(**payload)
                
                # Check for image URL conversion parameter
                # Handle both 'image_urls' and 'convert_images' parameters
                image_urls_param = payload.get('image_urls', payload.get('convert_images', 'false'))
                convert_images = str(image_urls_param).lower() in ['true', '1', 'yes', 'on']
                
                if id:
                    domain = [("id", "=", int(id))]
                
                Model = request.env[model.model]
                
                if lang:
                    # Set language context if provided
                    Model = Model.with_context(lang=lang)
                
                # For single record requests, we don't need pagination
                if id:
                    records = Model.search(domain, offset=offset, limit=limit, order=order)
                    
                    if not records:
                        return success_response([])
                        
                    # Prepare fields for reading
                    read_fields = fields
                    if populate_config and fields:
                        # Add populate fields to read_fields to ensure they're available
                        populate_fields = _get_populate_field_names(populate_config)
                        read_fields = list(set(fields + populate_fields))
                        
                    data = records.read(fields=read_fields)
                    
                    # Populate foreign fields if requested
                    if populate_config:
                        data = populate_foreign_fields(data, Model, populate_config)
                        # Process images in populated data
                        if convert_images:
                            data = process_image_fields_in_populated_data(data, populate_config)
                    
                    # Convert images to URLs if requested
                    if convert_images:
                        data = convert_images_to_urls(data, model.model)

                    # Filter final output to requested fields if specified and populated
                    if fields and populate_config:
                        filtered_data = []
                        for record in data:
                            filtered_record = {}
                            for field in fields:
                                if field in record:
                                    filtered_record[field] = record[field]
                            for pop_field in _get_populate_field_names(populate_config):
                                if pop_field in record:
                                    filtered_record[pop_field] = record[pop_field]
                            if convert_images:
                                for field in record:
                                    if field.endswith('_url'):
                                        filtered_record[field] = record[field]
                            filtered_data.append(filtered_record)
                        data = filtered_data

                    return success_response(data)

                # For list requests, include pagination metadata
                total_count = Model.search_count(domain)
                records = Model.search(domain, offset=offset, limit=limit, order=order)
                
                if not records:
                    # Return empty list with pagination metadata
                    pagination = {
                        "total_count": total_count,
                        "page_size": limit or 0,
                        "current_page": int(offset / limit) + 1 if limit else 1,
                        "num_pages": int(total_count / limit) + (1 if total_count % limit else 0) if limit else 1,
                        "next": None,
                        "previous": None
                    }
                    return success_response([], pagination=pagination)
                    
                # Prepare fields for reading
                read_fields = fields
                if populate_config and fields:
                    # Add populate fields to read_fields to ensure they're available
                    populate_fields = _get_populate_field_names(populate_config)
                    read_fields = list(set(fields + populate_fields))
                    
                data = records.read(fields=read_fields)
                
                # Populate foreign fields if requested
                if populate_config:
                    data = populate_foreign_fields(data, Model, populate_config)
                    # Process images in populated data
                    if convert_images:
                        data = process_image_fields_in_populated_data(data, populate_config)
                
                # Convert images to URLs if requested
                if convert_images:
                    data = convert_images_to_urls(data, model.model)

                # Filter final output to requested fields if specified and populated
                if fields and populate_config:
                    filtered_data = []
                    for record in data:
                        filtered_record = {}
                        for field in fields:
                            if field in record:
                                filtered_record[field] = record[field]
                        for pop_field in _get_populate_field_names(populate_config):
                            if pop_field in record:
                                filtered_record[pop_field] = record[pop_field]
                        if convert_images:
                            for field in record:
                                if field.endswith('_url'):
                                    filtered_record[field] = record[field]
                        filtered_data.append(filtered_record)
                    data = filtered_data

                # Build pagination metadata
                current_page = int(offset / limit) + 1 if limit else 1
                num_pages = int(total_count / limit) + (1 if total_count % limit else 0) if limit else 1
                
                # Generate next/previous page URLs
                base_url = request.httprequest.url.split('?')[0]
                query_params = dict(request.httprequest.args)
                
                # Update parameters for next page
                next_url = None
                if current_page < num_pages:
                    next_params = query_params.copy()
                    if 'page_number' in payload:
                        next_params['page_number'] = str(current_page + 1)
                    else:
                        next_params['offset'] = str(offset + limit)
                    next_url = f"{base_url}?{werkzeug.urls.url_encode(next_params)}"
                
                # Update parameters for previous page
                prev_url = None
                if current_page > 1:
                    prev_params = query_params.copy()
                    if 'page_number' in payload:
                        prev_params['page_number'] = str(current_page - 1)
                    else:
                        prev_params['offset'] = str(max(0, offset - limit))
                    prev_url = f"{base_url}?{werkzeug.urls.url_encode(prev_params)}"
                
                pagination = {
                    "total_count": total_count,
                    "page_size": limit or len(data),
                    "current_page": current_page,
                    "num_pages": num_pages,
                    "next": next_url,
                    "previous": prev_url
                }
                
                return success_response(data, pagination=pagination)
            else:
                return error_response(
                    "model_not_available", 
                    f"The model {ioc_name} is not available or not enabled for API access",
                    404
                )
        except AccessError as e:
            return error_response("access_error", f"Access error: {e.name}", 403)
        except Exception as e:
            return error_response("server_error", str(e), 500)
            
    @require_token
    @http.route(_resource_routes, type="http", auth="none", methods=["PATCH"], csrf=False)
    def update_resource(self, model=None, id=None, **payload):
        """Update an existing resource
        
        Args:
            model: The model name to update a record in
            id: The record ID to update
            payload: Updated record data in request body
        """
        if not id:
            return error_response("missing_id", "Record ID is required for update operations", 400)
            
        fields = payload.get("fields")
        populate_param = payload.get("populate")
        # Check for image URL conversion parameter
        image_urls_param = payload.get('image_urls', payload.get('convert_images', 'false'))
        convert_images = str(image_urls_param).lower() in ['true', '1', 'yes', 'on']
        request_model = model
        
        if not fields:
            fields = []
        else:
            fields = fields.split(",")
        
        # Parse populate config
        populate_config = {}
        if populate_param:
            from odoo.addons.ibs_api_integration.core.helpers import _parse_populate_config
            populate_config = _parse_populate_config(populate_param)
            
        # Get request body
        payload_body = request.httprequest.data.decode()
        
        try:
            model = request.env[self._model].sudo().search([("model", "=", model)], limit=1)
            
            if model:
                try:
                    values = json.loads(payload_body)

                    if isinstance(values, dict):
                        request_context = values.pop("__context", {}) or {}
                        if request_context and not isinstance(request_context, dict):
                            raise ValueError("context must be a JSON object")
                    else:
                        request_context = {}
                    
                    # Handle many2many and one2many fields
                    for k, v in values.items():
                        if isinstance(v, list):
                            values[k] = [(6, 0, v)]
                    
                    # Find the resource to update
                    resource_env = request.env[model.model].with_context(**request_context) if request_context else request.env[model.model]
                    resource = resource_env.browse(int(id))
                    
                    if not resource.exists():
                        return error_response("record_not_found", f"Record with ID {id} not found", 404)
                    
                    # Update the resource
                    resource.write(values)
                    
                except Exception as e:
                    request.env.cr.rollback()
                    return error_response("invalid_parameters", str(e), 400)
                else:
                    # Prepare fields for reading
                    read_fields = fields
                    if populate_config and fields:
                        # Add populate fields to read_fields to ensure they're available
                        populate_fields = _get_populate_field_names(populate_config)
                        read_fields = list(set(fields + populate_fields))
                    
                    data = resource.read(fields=read_fields)
                    
                    # Populate foreign fields if requested
                    if populate_config:
                        from odoo.addons.ibs_api_integration.core.helpers import populate_foreign_fields
                        data = populate_foreign_fields(data, request.env[model.model], populate_config)
                        # Process images in populated data
                        if convert_images:
                            data = process_image_fields_in_populated_data(data, populate_config)
                    
                    # Convert images to URLs if requested
                    if convert_images:
                        data = convert_images_to_urls(data, model.model)

                    # Filter final output if needed
                    if fields and populate_config:
                        filtered_data = []
                        for record in data:
                            filtered_record = {}
                            for field in fields:
                                if field in record:
                                    filtered_record[field] = record[field]
                            for pop_field in _get_populate_field_names(populate_config):
                                if pop_field in record:
                                    filtered_record[pop_field] = record[pop_field]
                            if convert_images:
                                for field in record:
                                    if field.endswith('_url'):
                                        filtered_record[field] = record[field]
                            filtered_data.append(filtered_record)
                        data = filtered_data

                    return success_response(data)
            return error_response(
                "model_not_available",
                f"The model {request_model} is not available or not enabled for API access",
                404
            )
        except Exception as e:
            return error_response("server_error", str(e), 500)

    @require_token
    @http.route(_resource_routes, type="http", auth="none", methods=["POST"], csrf=False)
    def create_resource(self, model=None, id=None, **payload):
        """Create a new resource
        
        Args:
            model: The model name to create a record in
            payload: Record data in request body
        """
        fields = payload.get("fields")
        populate_param = payload.get("populate")
        # Check for image URL conversion parameter
        image_urls_param = payload.get('image_urls', payload.get('convert_images', 'false'))
        convert_images = str(image_urls_param).lower() in ['true', '1', 'yes', 'on']
        request_model = model
        
        if not fields:
            fields = []
        else:
            fields = fields.split(",")
        
        # Parse populate config
        populate_config = {}
        if populate_param:
            from odoo.addons.ibs_api_integration.core.helpers import _parse_populate_config
            populate_config = _parse_populate_config(populate_param)
            
        # Get request body
        payload_body = request.httprequest.data.decode()
        
        try:
            model = request.env[self._model].sudo().search([("model", "=", model)], limit=1)
            
            if model:
                try:
                    values = json.loads(payload_body)

                    request_context = {}
                    if isinstance(values, dict):
                        request_context = values.pop("__context", {}) or {}
                        if request_context and not isinstance(request_context, dict):
                            raise ValueError("context must be a JSON object")
                    
                    def normalize_relations(val_dict):
                        for k, v in list(val_dict.items()):
                            if isinstance(v, list) and all(isinstance(x, int) for x in v):
                                val_dict[k] = [(6, 0, v)]
                        return val_dict
                    
                    ModelEnv = request.env[model.model].with_context(**request_context) if request_context else request.env[model.model]
                    # Support both single dict and list of dicts
                    if isinstance(values, list):
                        values = [normalize_relations(v) for v in values]
                        resource = ModelEnv.create(values)
                    elif isinstance(values, dict):
                        values = normalize_relations(values)
                        resource = ModelEnv.create(values)
                    else:
                        raise ValueError("Request body must be an object or a list of objects")
                except Exception as e:
                    request.env.cr.rollback()
                    return error_response("invalid_parameters", str(e), 400)
                else:
                    # Prepare fields for reading
                    read_fields = fields
                    if populate_config and fields:
                        # Add populate fields to read_fields to ensure they're available
                        populate_fields = _get_populate_field_names(populate_config)
                        read_fields = list(set(fields + populate_fields))
                    
                    data = resource.read(fields=read_fields)
                    
                    # Populate foreign fields if requested
                    if populate_config:
                        from odoo.addons.ibs_api_integration.core.helpers import populate_foreign_fields
                        data = populate_foreign_fields(data, request.env[model.model], populate_config)
                        # Process images in populated data
                        if convert_images:
                            data = process_image_fields_in_populated_data(data, populate_config)
                    
                    # Convert images to URLs if requested
                    if convert_images:
                        data = convert_images_to_urls(data, model.model)

                    # Filter final output if needed
                    if fields and populate_config:
                        filtered_data = []
                        for record in data:
                            filtered_record = {}
                            for field in fields:
                                if field in record:
                                    filtered_record[field] = record[field]
                            for pop_field in _get_populate_field_names(populate_config):
                                if pop_field in record:
                                    filtered_record[pop_field] = record[pop_field]
                            if convert_images:
                                for field in record:
                                    if field.endswith('_url'):
                                        filtered_record[field] = record[field]
                            filtered_data.append(filtered_record)
                        data = filtered_data
                    
                    return success_response(data)
            return error_response(
                "model_not_available", 
                f"The model {request_model} is not available or not enabled for API access",
                404
            )
        except Exception as e:
            return error_response("server_error", str(e), 500)
            
    @require_token
    @http.route(_resource_routes, type="http", auth="none", methods=["DELETE"], csrf=False)
    def delete_resource(self, model=None, id=None, **payload):
        """Delete a resource
        
        Args:
            model: The model name to delete a record from
            id: The record ID to delete
        """
        if not id:
            return error_response("missing_id", "Record ID is required for delete operations", 400)
            
        request_model = model
        
        try:
            model = request.env[self._model].sudo().search([("model", "=", model)], limit=1)
            
            if model:
                try:
                    # Find the resource to delete
                    resource = request.env[model.model].browse(int(id))
                    
                    if not resource.exists():
                        return error_response("record_not_found", f"Record with ID {id} not found", 404)
                    
                    # Delete the resource
                    resource.unlink()
                    
                except Exception as e:
                    request.env.cr.rollback()
                    return error_response("delete_error", str(e), 400)
                else:
                    return success_response({"message": f"Record {id} deleted successfully", "deleted_id": int(id)})
            return error_response(
                "model_not_available", 
                f"The model {request_model} is not available or not enabled for API access",
                404
            )
        except Exception as e:
            return error_response("server_error", str(e), 500)