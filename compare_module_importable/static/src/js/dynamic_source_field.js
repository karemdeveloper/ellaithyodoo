/** @odoo-module **/

import { Component, onWillStart, useEffect, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { session } from "@web/session";

export class CompareDynamicSourceField extends Component {
    static template = "compare_module_importable.DynamicSourceField";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ loading: false, options: [], query: "", legacyLabels: [] });
        this.loadedCompanyId = null;
        onWillStart(() => this.props.readonly ? undefined : this.loadOptions());
        useEffect(
            () => {
                if (this.props.readonly) {
                    return;
                }
                this.ensureLegacyValue();
                const companyId = this.companyId();
                if (this.loadedCompanyId === null || companyId !== this.loadedCompanyId) {
                    this.loadOptions();
                }
            },
            () => [
                this.props.readonly,
                this.companyId(),
                this.props.record.data[this.props.name],
                this.legacyValue(),
            ]
        );
    }

    get value() {
        const configuredValue = this.props.record.data[this.props.name];
        if (configuredValue) {
            return String(configuredValue);
        }
        return this.legacyValue();
    }

    legacyValue() {
        const legacySource = this.props.record.data.x_source_id;
        return Array.isArray(legacySource) ? (legacySource[1] || "") : "";
    }

    async ensureLegacyValue() {
        if (!this.props.record.data[this.props.name] && this.legacyValue()) {
            await this.props.record.update({
                [this.props.name]: this.legacyValue(),
            });
        }
    }

    companyId() {
        const recordCompany = this.props.record.data.x_company_id;
        if (Array.isArray(recordCompany)) {
            return Number(recordCompany[0]) || false;
        }
        if (recordCompany && typeof recordCompany === "object") {
            return Number(recordCompany.id || recordCompany.resId || false) || false;
        }
        const contextCompany = session.user_context?.allowed_company_ids?.[0];
        const currentCompany = session.user_companies?.current_company;
        if (contextCompany) {
            return Number(contextCompany);
        }
        if (typeof currentCompany === "number") {
            return currentCompany;
        }
        return Number(currentCompany?.id || currentCompany?.company_id || false) || false;
    }

    display(value) {
        if (Array.isArray(value)) {
            return value[1] || "";
        }
        if (value === false || value === null || value === undefined) {
            return "";
        }
        return String(value).trim();
    }

    unique(values) {
        return [...new Set(values.map((value) => this.display(value)).filter(Boolean))]
            .sort((first, second) => first.localeCompare(second));
    }

    parseValues(value) {
        if (!value) {
            return [];
        }
        if (Array.isArray(value)) {
            return this.unique(value);
        }
        try {
            const parsed = JSON.parse(value);
            if (Array.isArray(parsed)) {
                return this.unique(parsed);
            }
        } catch (_jsonError) {
            // Compatibility with values entered before JSON storage was introduced.
        }
        return this.unique(String(value).split(/[,\n]/));
    }

    mergeDomain(companyId) {
        return companyId
            ? [["x_company_id", "=", companyId], ["x_active", "=", true]]
            : [["x_active", "=", true]];
    }

    async mergeGroups(companyId) {
        return this.orm.searchRead(
            "x_compare.source.merge.group",
            this.mergeDomain(companyId),
            ["x_name", "x_source_ids", "x_source_names"],
            { limit: 1000 }
        );
    }

    async applyNamedMergeGroups(values, companyId) {
        const groups = await this.mergeGroups(companyId);
        const mergeNameLookup = {};
        for (const group of groups) {
            for (const sourceName of this.parseValues(group.x_source_names)) {
                mergeNameLookup[sourceName] = group.x_name;
            }
        }
        return values.map((value) => mergeNameLookup[this.display(value)] || value);
    }

    async sourceMetadata(companyId) {
        const configDomain = companyId ? [["x_company_id", "=", companyId]] : [];
        const configurations = await this.orm.searchRead(
            "x_compare.configuration",
            configDomain,
            ["x_source_field_id"],
            { limit: 1 }
        );
        const sourceFieldId = configurations[0]?.x_source_field_id?.[0];
        if (!sourceFieldId) {
            return { name: "source_id", ttype: "many2one", relation: "utm.source" };
        }
        const fields = await this.orm.searchRead(
            "ir.model.fields",
            [["id", "=", sourceFieldId]],
            ["name", "ttype", "relation"],
            { limit: 1 }
        );
        return fields[0] || { name: "source_id", ttype: "many2one", relation: "utm.source" };
    }

    async many2oneOptions(metadata, companyId) {
        let records = [];
        try {
            records = await this.orm.searchRead(
                metadata.relation,
                [],
                ["id", "display_name"],
                { limit: 100000, order: "id asc" }
            );
        } catch (_displayNameError) {
            records = await this.orm.searchRead(
                metadata.relation,
                [],
                ["id", "name"],
                { limit: 100000, order: "id asc" }
            );
        }

        const groups = await this.mergeGroups(companyId);
        const mergeLookup = {};
        const mergeNameLookup = {};
        for (const group of groups) {
            for (const sourceId of group.x_source_ids || []) {
                mergeLookup[sourceId] = group.x_name;
            }
            for (const sourceName of this.parseValues(group.x_source_names)) {
                mergeNameLookup[sourceName] = group.x_name;
            }
        }
        return records.map((record) => {
            const label = record.display_name || record.name;
            return mergeLookup[record.id] || mergeNameLookup[label] || label;
        });
    }

    async selectionOptions(metadata) {
        const definition = await this.orm.call(
            "crm.lead",
            "fields_get",
            [[metadata.name]],
            { attributes: ["selection"] }
        );
        return (definition?.[metadata.name]?.selection || []).map((entry) => entry[1]);
    }

    async charOptions(metadata, companyId) {
        const domain = [[metadata.name, "!=", false]];
        if (companyId) {
            domain.push(["company_id", "in", [companyId, false]]);
        }
        try {
            const groups = await this.orm.readGroup(
                "crm.lead",
                domain,
                [metadata.name],
                [metadata.name],
                { lazy: false, limit: 10000 }
            );
            return groups.map((group) => group[metadata.name]);
        } catch (_readGroupError) {
            const leads = await this.orm.searchRead(
                "crm.lead",
                domain,
                [metadata.name],
                { limit: 100000 }
            );
            return leads.map((lead) => lead[metadata.name]);
        }
    }

    async loadOptions() {
        const companyId = this.companyId();
        this.loadedCompanyId = companyId;
        this.state.loading = true;
        try {
            const metadata = await this.sourceMetadata(companyId);
            let values = [];
            if (metadata.ttype === "many2one" && metadata.relation) {
                values = await this.many2oneOptions(metadata, companyId);
            } else if (metadata.ttype === "selection") {
                values = await this.applyNamedMergeGroups(
                    await this.selectionOptions(metadata),
                    companyId
                );
            } else {
                values = await this.applyNamedMergeGroups(
                    await this.charOptions(metadata, companyId),
                    companyId
                );
            }
            this.state.options = this.unique([...values, this.value]);
        } catch (error) {
            console.error("Unable to load configured CRM sources", error);
            this.state.options = this.unique([this.value]);
            this.notification.add(
                "The configured CRM sources could not be loaded. You can still keep the existing source value.",
                { type: "warning" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    async onChange(event) {
        await this.props.record.update({
            [this.props.name]: event.target.value || false,
        });
    }
}

export class CompareDynamicSourcesField extends CompareDynamicSourceField {
    static template = "compare_module_importable.DynamicSourcesField";

    setup() {
        super.setup();
        onWillStart(() => this.props.readonly ? this.loadOptions() : undefined);
    }

    get selectedValues() {
        return this.parseValues(this.props.record.data[this.props.name]);
    }

    get displayValues() {
        return this.selectedValues.length ? this.selectedValues : this.state.legacyLabels;
    }

    get filteredOptions() {
        const query = this.state.query.trim().toLowerCase();
        if (!query) {
            return this.state.options;
        }
        return this.state.options.filter((option) => option.toLowerCase().includes(query));
    }

    legacyValue() {
        return this.legacySourceIds().join(",");
    }

    legacySourceIds() {
        const legacySources = this.props.record.data.x_source_ids;
        if (Array.isArray(legacySources)) {
            if (legacySources.every((value) => Number.isInteger(value))) {
                return legacySources;
            }
            const commandIds = [];
            for (const command of legacySources) {
                if (Array.isArray(command) && command[0] === 6 && Array.isArray(command[2])) {
                    commandIds.push(...command[2]);
                }
            }
            return commandIds;
        }
        const records = legacySources?.records || [];
        if (records.length) {
            return records.map((record) => record.resId).filter(Boolean);
        }
        return legacySources?.currentIds || legacySources?.resIds || [];
    }

    async legacySourceLabels() {
        const legacySources = this.props.record.data.x_source_ids;
        const recordLabels = (legacySources?.records || [])
            .map((record) => record.data?.display_name || record.data?.name)
            .filter(Boolean);
        if (recordLabels.length) {
            return this.unique(recordLabels);
        }
        const ids = this.legacySourceIds();
        if (!ids.length) {
            return [];
        }
        const records = await this.orm.searchRead(
            "utm.source",
            [["id", "in", ids]],
            ["id", "name"],
            { limit: 100000, order: "id asc" }
        );
        return this.unique(records.map((record) => record.name));
    }

    async ensureLegacyValue() {
        if (this.props.record.data[this.props.name]) {
            return;
        }
        const labels = await this.legacySourceLabels();
        this.state.legacyLabels = labels;
        if (!this.props.readonly && labels.length) {
            await this.props.record.update({
                [this.props.name]: JSON.stringify(labels),
            });
        }
    }

    async rawMany2oneOptions(metadata) {
        try {
            const records = await this.orm.searchRead(
                metadata.relation,
                [],
                ["display_name"],
                { limit: 100000, order: "id asc" }
            );
            return records.map((record) => record.display_name);
        } catch (_displayNameError) {
            const records = await this.orm.searchRead(
                metadata.relation,
                [],
                ["name"],
                { limit: 100000, order: "id asc" }
            );
            return records.map((record) => record.name);
        }
    }

    async loadOptions() {
        const companyId = this.companyId();
        this.loadedCompanyId = companyId;
        this.state.loading = true;
        try {
            const legacyLabels = this.selectedValues.length ? [] : await this.legacySourceLabels();
            this.state.legacyLabels = legacyLabels;

            if (this.props.readonly) {
                this.state.options = this.unique([...this.selectedValues, ...legacyLabels]);
                return;
            }

            if (!this.selectedValues.length && legacyLabels.length) {
                await this.props.record.update({
                    [this.props.name]: JSON.stringify(legacyLabels),
                });
            }

            const metadata = await this.sourceMetadata(companyId);
            let values = [];
            if (metadata.ttype === "many2one" && metadata.relation) {
                values = await this.rawMany2oneOptions(metadata);
            } else if (metadata.ttype === "selection") {
                values = await this.selectionOptions(metadata);
            } else {
                values = await this.charOptions(metadata, companyId);
            }
            this.state.options = this.unique([
                ...values,
                ...this.selectedValues,
                ...legacyLabels,
            ]);
        } catch (error) {
            console.error("Unable to load configured CRM sources for merge groups", error);
            this.state.options = this.unique([...this.selectedValues, ...this.state.legacyLabels]);
            this.notification.add(
                "The configured CRM sources could not be loaded for this merge group.",
                { type: "warning" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    isSelected(option) {
        return this.selectedValues.includes(option);
    }

    async onToggle(event) {
        const source = event.currentTarget.dataset.source;
        const selected = new Set(this.selectedValues);
        if (event.currentTarget.checked) {
            selected.add(source);
        } else {
            selected.delete(source);
        }
        const values = this.unique([...selected]);
        await this.props.record.update({
            [this.props.name]: values.length ? JSON.stringify(values) : false,
        });
    }
}

registry.category("fields").add("compare_dynamic_source", {
    component: CompareDynamicSourceField,
    supportedTypes: ["char"],
});

registry.category("fields").add("compare_dynamic_sources", {
    component: CompareDynamicSourcesField,
    supportedTypes: ["text"],
});
