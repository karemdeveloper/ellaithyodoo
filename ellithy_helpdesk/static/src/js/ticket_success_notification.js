/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.effectService = useService("effect");
    },

    async saveButtonClicked(params = {}) {
        const isNewRecord = !this.model.root.resId;

        const saved = await super.saveButtonClicked(...arguments);

        if (saved && this.props.resModel === "helpdesk.ticket" && isNewRecord) {
            this.effectService.add({
                type: "rainbow_man",
                message: "Done! Your ticket has been created successfully",
                fadeout: "fast",
            });
        }
        return saved;
    },
});