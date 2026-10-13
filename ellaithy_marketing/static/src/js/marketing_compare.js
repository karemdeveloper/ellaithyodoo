/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class MarketingCompare extends Component {
    static template = "ellaithy_marketing.MarketingCompare";
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        const now = new Date();
        const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1);
        this.months = Array.from({length:12}, (_,i)=>({id:i+1,name:new Date(2024,i,1).toLocaleString("en",{month:"long"})}));
        this.years = Array.from({length:11}, (_,i)=>now.getFullYear()-8+i);
        this.dimensions = [
            {id:"source",name:"Marketing Source"}, {id:"branch",name:"Branch"},
            {id:"campaign",name:"Campaign"}, {id:"channel",name:"Medium / Channel"},
            {id:"salesperson",name:"Salesperson"}, {id:"team",name:"Sales Team"},
            {id:"stage",name:"Stage"}
        ];
        this.state = useState({
            loading:false, filters:{}, baselineYear:prev.getFullYear(), baselineMonth:prev.getMonth()+1,
            targetYear:now.getFullYear(), targetMonth:now.getMonth()+1,
            company_id:"",source_id:"",campaign_id:"",team_id:"",user_id:"",
            stage_id:"",lead_type:"",dimension:"source",branch:"",source:"",search:"",
            baseline:null,target:null,error:""
        });
        onWillStart(async()=> {
            try {
                this.state.filters = await this.orm.call("ellaithy.marketing.dashboard","get_filters",[]);
                await this.refresh();
            } catch(e) { this.state.error = e.message || "Unable to load comparison"; }
        });
    }
    selected(a,b) { return String(a ?? "") === String(b ?? ""); }
    set(ev,key) { this.state[key] = ev.target.value; }
    dates(year,month) {
        const from = `${year}-${String(month).padStart(2,"0")}-01`;
        const to = new Date(year,month,0);
        return {date_from:from,date_to:`${year}-${String(month).padStart(2,"0")}-${String(to.getDate()).padStart(2,"0")}`};
    }
    async refresh() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const shared = {};
            for(const k of ["company_id","source_id","campaign_id","team_id","user_id","stage_id","lead_type"]) {
                if(this.state[k]) shared[k] = this.state[k];
            }
            shared.group_by = this.state.dimension;
            const a = this.dates(Number(this.state.baselineYear),Number(this.state.baselineMonth));
            const b = this.dates(Number(this.state.targetYear),Number(this.state.targetMonth));
            const [baseline,target] = await Promise.all([
                this.orm.call("ellaithy.marketing.dashboard","get_dashboard",[],{...shared,...a}),
                this.orm.call("ellaithy.marketing.dashboard","get_dashboard",[],{...shared,...b})
            ]);
            this.state.baseline = baseline;
            this.state.target = target;
        } catch(e) {
            this.state.error = e.message || "Could not load comparison";
            this.notification.add(this.state.error,{type:"danger"});
        } finally { this.state.loading = false; }
    }
    num(v) { return Number(v || 0).toLocaleString(undefined,{maximumFractionDigits:2}); }
    pct(a,b) { return b ? `${this.num((a/b)*100)}%` : "—"; }
    diff(a,b) { return Number(b||0)-Number(a||0); }
    metric(name) {
        const a = this.state.baseline?.totals || {}, b = this.state.target?.totals || {};
        return {first:Number(a[name]||0),second:Number(b[name]||0),delta:this.diff(a[name],b[name])};
    }
    get rows() {
        const a = this.state.baseline?.by_dimension || [];
        const b = this.state.target?.by_dimension || [];
        const m = new Map();
        for(const r of a) m.set(r.name,{name:r.name,first:r.leads||0,second:0,wonFirst:r.won||0,wonSecond:0,lostFirst:r.lost||0,lostSecond:0});
        for(const r of b) {
            if(!m.has(r.name)) m.set(r.name,{name:r.name,first:0,second:0,wonFirst:0,wonSecond:0,lostFirst:0,lostSecond:0});
            const row=m.get(r.name); row.second=r.leads||0; row.wonSecond=r.won||0; row.lostSecond=r.lost||0;
        }
        const search=this.state.search.toLowerCase();
        const rows=[...m.values()].filter(r=>r.name.toLowerCase().includes(search));
        rows.sort((x,y)=>(y.second-x.second)||(y.first-x.first));
        return rows;
    }
    get sourceRows() {
        const a=this.state.baseline?.by_source||[], b=this.state.target?.by_source||[];
        const map=new Map();
        for(const r of a) map.set(r.name,{name:r.name,first:r.leads,second:0,wonFirst:r.won,wonSecond:0});
        for(const r of b) {
            if(!map.has(r.name)) map.set(r.name,{name:r.name,first:0,second:0,wonFirst:0,wonSecond:0});
            const item=map.get(r.name);item.second=r.leads;item.wonSecond=r.won;
        }
        return [...map.values()].sort((x,y)=>y.second-x.second);
    }
    get branchRows() {
        const a=this.state.baseline?.by_branch||[],b=this.state.target?.by_branch||[];
        const map=new Map();
        for(const r of a) map.set(r.name,{name:r.name,first:r.leads,second:0,wonFirst:r.won,wonSecond:0});
        for(const r of b) {
            if(!map.has(r.name)) map.set(r.name,{name:r.name,first:0,second:0,wonFirst:0,wonSecond:0});
            const item=map.get(r.name);item.second=r.leads;item.wonSecond=r.won;
        }
        return [...map.values()].sort((x,y)=>y.second-x.second);
    }
    exportCsv() {
        const rows=[["Dimension","Baseline Leads","Target Leads","Change","Baseline Won","Target Won","Baseline Lost","Target Lost"]];
        for(const r of this.rows) rows.push([r.name,r.first,r.second,r.second-r.first,r.wonFirst,r.wonSecond,r.lostFirst,r.lostSecond]);
        const csv="\ufeff"+rows.map(row=>row.map(v=>`"${String(v??"").replaceAll('"','""')}"`).join(",")).join("\r\n");
        const blob=new Blob([csv],{type:"text/csv;charset=utf-8"});
        const url=URL.createObjectURL(blob);
        const a=document.createElement("a");a.href=url;a.download="marketing_monthly_comparison.csv";a.click();
        setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
}
registry.category("actions").add("ellaithy_marketing.compare",MarketingCompare);
