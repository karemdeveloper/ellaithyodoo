/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

/**
 * Widget button to open existing customer without saving current form
 * Bypasses all field validations
 */
class OpenExistingCustomerButton extends Component {
    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.dialog = useService("dialog");
    }

    get isVisible() {
        try {
            const record = this.props.record;
            if (!record || !record.data) {
                return false;
            }
            const customerAlreadyExistId = record.data.customer_already_exist_id;
            return customerAlreadyExistId && Array.isArray(customerAlreadyExistId) && customerAlreadyExistId[0];
        } catch (error) {
            console.error("Error in isVisible:", error);
            return false;
        }
    }

    get customerName() {
        try {
            const record = this.props.record;
            if (!record || !record.data) {
                return "Existing Customer";
            }
            const customerAlreadyExistId = record.data.customer_already_exist_id;
            if (customerAlreadyExistId && Array.isArray(customerAlreadyExistId) && customerAlreadyExistId[1]) {
                return customerAlreadyExistId[1];
            }
            return "Existing Customer";
        } catch (error) {
            console.error("Error in customerName:", error);
            return "Existing Customer";
        }
    }

    async onClick(ev) {
        try {
            // Prevent any default form behavior
            if (ev) {
                ev.preventDefault();
                ev.stopPropagation();
            }

            const record = this.props.record;
            if (!record || !record.data) {
                return;
            }
            const customerAlreadyExistId = record.data.customer_already_exist_id;
            
            if (!customerAlreadyExistId || !Array.isArray(customerAlreadyExistId) || !customerAlreadyExistId[0]) {
                return;
            }

            const customerId = customerAlreadyExistId[0];
            const customerName = customerAlreadyExistId[1] || "existing customer";

            // Show confirmation dialog
            this.dialog.add(ConfirmationDialog, {
                title: "Open Existing Customer",
                body: `This will discard the current form and open ${customerName}. Continue?`,
                confirm: async () => {
                    // Force close current form without saving by navigating directly
                    window.location.href = `/odoo/contacts/${customerId}`;
                },
                cancel: () => {},
            });
        } catch (error) {
            console.error("Error in onClick:", error);
        }
    }
}

OpenExistingCustomerButton.template = "crm_customization.OpenExistingCustomerButton";
OpenExistingCustomerButton.props = {
    ...standardFieldProps,
};

registry.category("fields").add("open_existing_customer_button", {
    component: OpenExistingCustomerButton,
});

