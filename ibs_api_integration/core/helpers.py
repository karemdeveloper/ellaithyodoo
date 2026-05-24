import ast
import datetime
import json
import werkzeug.wrappers
from odoo.http import request

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return str(obj)

def success_response(data=None, status=200, pagination=None):
    """Create a successful API response"""
    if data is None:
        data = []
    response = {"status": True, "data": data}
    
    # Add pagination metadata if provided
    if pagination:
        response["pagination"] = pagination
        
    return werkzeug.wrappers.Response(
        status=status,
        content_type="application/json; charset=utf-8",
        response=json.dumps(response, default=json_serial),
    )

def error_response(error_type, message, status=400):
    """Create an error API response"""
    response = {
        "status": False,
        "error": {
            "type": error_type,
            "message": message,
        }
    }
    return werkzeug.wrappers.Response(
        status=status,
        content_type="application/json; charset=utf-8",
        response=json.dumps(response, default=json_serial),
    )

def parse_request_params(domain=None, fields=None, offset=0, limit=None, order=None, page_size=None, page_number=None, lang=None, populate=None):
    """Parse and validate request parameters"""
    expressions = []
    populate_config = {}
    
    if domain:
        tuple_representation = ast.literal_eval(domain)
        list_representation = list(tuple_representation)
        expressions = list_representation
    if fields:
        fields = fields.split(",")
    if page_size:
        limit = int(page_size)
    if page_number and page_size:
        offset = (int(page_number) * int(page_size)) - int(page_size)
    if offset:
        offset = int(offset)
    if lang:
        lang = lang
    
    # Parse populate parameter - simplified version
    if populate:
        populate_config = _parse_populate_config(populate)
    
    return [expressions, fields, offset, limit, order, lang, populate_config]

def convert_images_to_urls(records_data, model_name, image_fields=None, base_url=None):
    """Convert image fields from base64 to URLs using Odoo's native image handling
    
    This properly handles both database-stored and filestore-stored images.
    Uses Odoo's /web/image endpoint which automatically handles:
    - File access from filestore or database
    - Image resizing and caching
    - Proper MIME types and headers
    - Access control and security
    """
    import logging
    _logger = logging.getLogger(__name__)
    _logger.info(f"convert_images_to_urls called for model {model_name} with {len(records_data) if records_data else 0} records")
    
    if not records_data:
        return records_data
    
    # Auto-detect common image fields if not specified
    if image_fields is None:
        image_fields = ['image', 'image_1920', 'image_1024', 'image_512', 'image_256', 'image_128', 
                       'avatar', 'photo', 'picture', 'logo', 'icon']
    
    # Get base URL from request if not provided
    if base_url is None:
        if request and request.httprequest:
            base_url = f"{request.httprequest.scheme}://{request.httprequest.host}"
        else:
            base_url = "http://localhost:8069"  # fallback
    
    for record in records_data:
        record_id = record.get('id')
        if not record_id:
            continue
            
        for field_name in image_fields:
            if field_name in record and record[field_name]:
                # Use Odoo's standard /web/image endpoint
                # This endpoint automatically handles:
                # - filestore vs database storage
                # - image resizing (if field like image_1920, image_512, etc.)
                # - caching headers
                # - access control
                image_url = f"{base_url}/web/image?model={model_name}&id={record_id}&field={field_name}"
                
                # Add additional URL parameters for better caching and performance
                # Add unique parameter to help with browser caching
                image_url += f"&unique={record.get('write_date', record.get('create_date', ''))}"
                
                record[f"{field_name}_url"] = image_url
                _logger.info(f"Created image URL for {field_name}: {image_url}")
                
                # Always remove base64 data when converting to URLs to save bandwidth
                # The URL provides the image access, no need for base64 data
                original_length = len(str(record[field_name])) if record[field_name] else 0
                record[field_name] = None
                _logger.info(f"Removed base64 data for {field_name} (original length: {original_length})")
    
    return records_data

def process_image_fields_in_populated_data(records_data, populate_config, base_url=None):
    """Process image fields in populated foreign records
    
    This handles image URL conversion for populated relational fields,
    properly handling both filestore and database-stored images.
    """
    if not populate_config:
        return records_data
    
    # Get base URL from request if not provided
    if base_url is None:
        if request and request.httprequest:
            base_url = f"{request.httprequest.scheme}://{request.httprequest.host}"
        else:
            base_url = "http://localhost:8069"  # fallback
    
    # Common image fields to check for
    image_fields = ['image', 'image_1920', 'image_1024', 'image_512', 'image_256', 'image_128', 
                   'avatar', 'photo', 'picture', 'logo', 'icon']
    
    for record in records_data:
        for field_name in _get_populate_field_names(populate_config):
            if field_name in record and isinstance(record[field_name], dict):
                # This is a populated many2one field
                populated_record = record[field_name]
                populated_id = populated_record.get('id')
                
                if populated_id:
                    # Determine the model name for the populated field
                    # Handle both _id suffix (many2one) and other patterns
                    if field_name.endswith('_id'):
                        model_name = field_name[:-3]  # Remove '_id'
                    else:
                        model_name = field_name
                    
                    # Handle special model name mappings
                    model_name_mappings = {
                        'user': 'res.users',
                        'partner': 'res.partner',
                        'customer': 'res.partner',
                        'vendor': 'res.partner',
                        'company': 'res.company'
                    }
                    model_name = model_name_mappings.get(model_name, model_name)
                    
                    for img_field in image_fields:
                        if img_field in populated_record and populated_record[img_field]:
                            # Use standard Odoo image URL with caching
                            image_url = f"{base_url}/web/image?model={model_name}&id={populated_id}&field={img_field}"
                            
                            # Add unique parameter for cache busting
                            unique_param = populated_record.get('write_date', populated_record.get('create_date', ''))
                            if unique_param:
                                image_url += f"&unique={unique_param}"
                                
                            populated_record[f"{img_field}_url"] = image_url
                            
                            # Remove base64 data when converting to URLs
                            populated_record[img_field] = None
            
            elif field_name in record and isinstance(record[field_name], list):
                # This is a populated one2many or many2many field
                # Determine model name from field name
                if field_name.endswith('_ids'):
                    model_name = field_name[:-4]  # Remove '_ids'
                else:
                    model_name = field_name
                    
                for populated_record in record[field_name]:
                    if isinstance(populated_record, dict):
                        populated_id = populated_record.get('id')
                        if populated_id:
                            for img_field in image_fields:
                                if img_field in populated_record and populated_record[img_field]:
                                    # Use standard Odoo image URL
                                    image_url = f"{base_url}/web/image?model={model_name}&id={populated_id}&field={img_field}"
                                    
                                    # Add unique parameter for cache busting
                                    unique_param = populated_record.get('write_date', populated_record.get('create_date', ''))
                                    if unique_param:
                                        image_url += f"&unique={unique_param}"
                                        
                                    populated_record[f"{img_field}_url"] = image_url
                                    
                                    # Remove base64 data when converting to URLs
                                    populated_record[img_field] = None
    
    return records_data

def _get_populate_field_names(populate_config):
    """Extract field names from populate config, handling both old and new formats"""
    if not populate_config:
        return []
    
    field_names = []
    for field_name, field_config in populate_config.items():
        field_names.append(field_name)
    
    return field_names

def _parse_populate_config(populate_string):
    """Parse populate parameter into a configuration supporting nested population
    
    Supports syntax like:
    - Basic: field1:sub1,sub2|field2:sub3,sub4  
    - Nested: field1:field2:sub1,sub2|field3:sub3,sub4
    
    Returns dict with structure:
    {
        'field_name': {
            'fields': ['field1', 'field2'],  # Direct fields to populate
            'nested': {
                'nested_field': ['sub1', 'sub2']  # Nested field to populate
            }
        }
    }
    """
    config = {}
    
    for field_config in populate_string.split("|"):
        if ":" in field_config:
            parts = field_config.split(":")
            field_name = parts[0].strip()
            
            if len(parts) == 2:
                # Basic populate: field_name:field1,field2
                field_list = parts[1]
                field_list_clean = [field.strip() for field in field_list.split(",")]
                config[field_name] = {
                    'fields': field_list_clean,
                    'nested': {}
                }
            elif len(parts) == 3:
                # Nested populate: field_name:nested_field:sub1,sub2
                nested_field = parts[1].strip()
                nested_field_list = parts[2]
                nested_field_list_clean = [field.strip() for field in nested_field_list.split(",")]
                config[field_name] = {
                    'fields': None,  # Will populate all fields of the main relation
                    'nested': {
                        nested_field: nested_field_list_clean
                    }
                }
            else:
                # More than 3 parts - not supported yet, treat as basic
                field_list = ":".join(parts[1:])
                field_list_clean = [field.strip() for field in field_list.split(",")]
                config[field_name] = {
                    'fields': field_list_clean,
                    'nested': {}
                }
        else:
            # No colon - populate all fields
            config[field_config.strip()] = {
                'fields': None,
                'nested': {}
            }
    
    return config

def populate_foreign_fields(records_data, model_obj, populate_config):
    """Populate foreign fields efficiently with minimal database queries
    
    Now supports nested population with the format:
    field_name:nested_field:sub1,sub2
    """
    if not populate_config or not records_data:
        return records_data
    
    # Get field definitions once to avoid repeated calls
    field_definitions = model_obj.fields_get()
    
    for field_name, field_config in populate_config.items():
        if not _is_valid_relational_field(field_name, field_definitions):
            continue
            
        field_def = field_definitions[field_name]
        
        # Collect all foreign IDs efficiently
        foreign_ids = _collect_foreign_ids(records_data, field_name, field_def['type'])
        if not foreign_ids:
            continue
        
        # Extract configuration
        if isinstance(field_config, dict):
            requested_fields = field_config.get('fields')
            nested_config = field_config.get('nested', {})
        else:
            # Backward compatibility - if it's a list, treat as old format
            requested_fields = field_config
            nested_config = {}
        
        # Fetch and populate the related data
        try:
            related_lookup = _fetch_related_data(model_obj, field_def['relation'], foreign_ids, requested_fields)
            
            # Handle nested population if specified
            if nested_config:
                _populate_nested_fields(related_lookup, model_obj, field_def['relation'], nested_config)
            
            _update_records_with_related_data(records_data, field_name, field_def['type'], related_lookup)
        except Exception as e:
            # Skip this field if there's an error, but log it for debugging
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f"Error populating field {field_name}: {str(e)}")
            continue
    
    return records_data

def _is_valid_relational_field(field_name, field_definitions):
    """Check if field exists and is relational"""
    if field_name not in field_definitions:
        return False
    
    field_def = field_definitions[field_name]
    field_type = field_def.get('type')
    related_model = field_def.get('relation')
    
    return field_type in ['many2one', 'one2many', 'many2many'] and related_model

def _collect_foreign_ids(records_data, field_name, field_type):
    """Collect all foreign IDs from records for a specific field"""
    foreign_ids = set()
    
    for record in records_data:
        field_value = record.get(field_name)
        if not field_value:
            continue
            
        if field_type == 'many2one':
            foreign_id = _extract_id_from_many2one(field_value)
            if foreign_id:
                foreign_ids.add(foreign_id)
        elif field_type in ['one2many', 'many2many']:
            if isinstance(field_value, list):
                foreign_ids.update(field_value)
    
    return foreign_ids

def _extract_id_from_many2one(field_value):
    """Extract ID from many2one field value (handles both [id, name] and id formats)"""
    if isinstance(field_value, (list, tuple)) and len(field_value) >= 1:
        return field_value[0]
    elif isinstance(field_value, int):
        return field_value
    return None

def _fetch_related_data(model_obj, related_model, foreign_ids, requested_fields):
    """Fetch related records and return as lookup dictionary"""
    related_model_obj = model_obj.env[related_model]
    related_records = related_model_obj.sudo().browse(list(foreign_ids))
    
    # Read the related records
    if requested_fields is None:
        # Read all fields if none specified
        related_data = related_records.read()
    else:
        # Make a copy of requested_fields to avoid modifying the original
        fields_to_read = list(requested_fields)
        
        # Ensure 'id' is always included for the lookup to work
        if 'id' not in fields_to_read:
            fields_to_read.insert(0, 'id')
            
        try:
            # Debug: Log what fields we're trying to read
            import logging
            _logger = logging.getLogger(__name__)
            _logger.info(f"Attempting to read fields {fields_to_read} from model {related_model}")
            
            # Always read all fields first to ensure we get everything
            all_data = related_records.read()
            
            # Then filter to only the requested fields if specified
            if len(fields_to_read) < len(all_data[0]) if all_data else False:
                # Only filter if we actually requested specific fields
                related_data = []
                for record in all_data:
                    filtered_record = {}
                    for field in fields_to_read:
                        if field in record:
                            filtered_record[field] = record[field]
                    related_data.append(filtered_record)
            else:
                related_data = all_data
                
            _logger.info(f"Successfully read {len(related_data)} records with fields: {list(related_data[0].keys()) if related_data else 'none'}")
                
        except Exception as e:
            # If there's an error with specific fields, try reading all fields
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f"Error reading fields from {related_model}: {str(e)}")
            _logger.warning("Falling back to reading all fields")
            related_data = related_records.read()
    
    # Return as lookup dictionary for efficient access
    return {record['id']: record for record in related_data}

def _populate_nested_fields(related_lookup, parent_model_obj, related_model_name, nested_config):
    """Populate nested fields within already fetched related records"""
    if not nested_config or not related_lookup:
        return
    
    # Convert related_lookup values to a list for processing
    related_records = list(related_lookup.values())
    
    # Get the related model object
    related_model_obj = parent_model_obj.env[related_model_name]
    
    # Create a simple populate config for the nested fields
    nested_populate_config = {}
    for nested_field, nested_field_list in nested_config.items():
        nested_populate_config[nested_field] = {
            'fields': nested_field_list,
            'nested': {}
        }
    
    # Use the populate function recursively on the related records
    populate_foreign_fields(related_records, related_model_obj, nested_populate_config)

def _update_records_with_related_data(records_data, field_name, field_type, related_lookup):
    """Update original records with populated foreign field data"""
    for record in records_data:
        field_value = record.get(field_name)
        if not field_value:
            continue
        
        if field_type == 'many2one':
            foreign_id = _extract_id_from_many2one(field_value)
            if foreign_id and foreign_id in related_lookup:
                record[field_name] = related_lookup[foreign_id]
                
        elif field_type in ['one2many', 'many2many']:
            if isinstance(field_value, list):
                populated_records = [
                    related_lookup[fid] 
                    for fid in field_value 
                    if fid in related_lookup
                ]
                if populated_records:
                    record[field_name] = populated_records 