from odoo import api, fields, models
from collections import defaultdict
import itertools
import logging

_logger = logging.getLogger(__name__)

class AttachmentSecurity(models.Model):
    """Enhanced security for attachments in API context"""
    _inherit = "ir.attachment"
    
    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """Enhanced search method with additional security checks for API access"""
        # If bypassing security or counting, use original search
        if self.env.context.get('bypass_attachment_security') or count:
            return super(AttachmentSecurity, self).search(
                args, offset=offset, limit=limit, order=order, count=count
            )
            
        # Get original results
        orig_records = super(AttachmentSecurity, self).search(
            args, offset=offset, limit=limit, order=order
        )
        
        # If no results, return original results
        if not orig_records:
            return orig_records
            
        # Get attachment records
        result = set(orig_records.ids)
        ids = set(orig_records.ids)
        
        # Group attachments by model and resource
        model_attachments = defaultdict(lambda: defaultdict(set))
        binary_fields_attachments = set()
        
        # Query to get attachment metadata
        query = """
            SELECT id, res_model, res_id, res_field
            FROM ir_attachment
            WHERE id IN %s
        """
        self.env.cr.execute(query, [tuple(ids)])
        
        # Process query results
        for row in self.env.cr.dictfetchall():
            if not row['res_model'] or not row['res_id']:
                continue
                
            model_attachments[row['res_model']][row['res_id']].add(row['id'])
            
            if row['res_field']:
                binary_fields_attachments.add(row['id'])
                
        # Remove binary field attachments
        if binary_fields_attachments:
            ids.difference_update(binary_fields_attachments)
            
        # Perform batch access rights checking
        for res_model, targets in model_attachments.items():
            if res_model not in self.env:
                continue
                
            if not self.env[res_model].check_access_rights('read', False):
                ids.difference_update(itertools.chain(*targets.values()))
                continue
                
            # Check access rules on records
            target_ids = list(targets.keys())
            allowed = self.env[res_model].search([('id', 'in', target_ids)])
            allowed_ids = set(allowed.ids)
            
            for res_id in targets:
                if res_id not in allowed_ids:
                    ids.difference_update(targets[res_id])
                    
        # Update result set
        result = list(ids)
        
        # Handle pagination limit consistency
        if limit and len(orig_records) == limit and len(result) < len(orig_records):
            additional_records = self.search(
                args,
                offset=offset + len(orig_records),
                limit=limit - len(result),
                order=order,
            )
            if additional_records:
                return self.browse(result + additional_records.ids)
            
        return self.browse(result) 