/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";

export class SlaTicker extends Component {
    setup() {
        console.log("%c[SLA Ticker] setup() called", "color: green;");

        try {
            console.log("%c[SLA Ticker] Props received:", "color: #00aaff;", this.props);

            this.state = useState({ seconds: this.initialSeconds() });

            onMounted(() => {
                console.log("%c[SLA Ticker] Mounted successfully", "color: #00cc00;");
                this.startTimer();
            });

            onWillUnmount(() => {
                console.log("%c[SLA Ticker] Unmounting...", "color: orange;");
                clearInterval(this.timerInterval);
            });
        } catch (err) {
            console.error("%c[SLA Ticker] Error in setup:", "color: red;", err);
        }
    }

    initialSeconds() {
        try {
            console.log("%c[SLA Ticker] Calculating initial seconds...", "color: purple;");

            const value =
                this.props && this.props.value && typeof this.props.value === "string"
                    ? this.props.value
                    : "00:00:00";

            console.log("%c[SLA Ticker] Raw value received:", "color: #ff8800;", value);

            const parts = value.split(":").map((x) => parseInt(x || 0));
            const [h, m, s] = parts.length === 3 ? parts : [0, 0, 0];
            const total = h * 3600 + m * 60 + s;

            console.log("%c[SLA Ticker] Parsed to seconds:", "color: #ff00ff;", total);
            return total;
        } catch (err) {
            console.error("%c[SLA Ticker] Error in initialSeconds():", "color: red;", err);
            return 0;
        }
    }

    startTimer() {
        console.log("%c[SLA Ticker] Starting timer...", "color: cyan;");
        this.timerInterval = setInterval(() => {
            this.state.seconds++;
        }, 1000);
    }

    get formattedTime() {
        const hours = Math.floor(this.state.seconds / 3600);
        const minutes = Math.floor((this.state.seconds % 3600) / 60);
        const seconds = this.state.seconds % 60;
        const formatted = `${hours.toString().padStart(2, "0")}:${minutes
            .toString()
            .padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
        console.log("%c[SLA Ticker] Formatted time:", "color: gray;", formatted);
        return formatted;
    }
}

SlaTicker.template = "crm_customization.SlaTickerTemplate";
registry.category("fields").add("sla_ticker", SlaTicker);
