/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";
import { SalesAccessDashboard } from "./sales_access_dashboard";

export class CompareDashboard extends Component {
    static template = "compare_module.CompareDashboard";
    static components = { SalesAccessDashboard };
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        const now = new Date(); const prev = new Date(now.getFullYear(), now.getMonth()-1, 1);
        const requestedTab = this.props?.action?.context?.default_tab; const defaultTab = ["charts", "analytics"].includes(requestedTab) ? requestedTab : "compare";
        this.state = useState({activeTab:defaultTab, loading:true, firstYear:prev.getFullYear(), firstMonth:prev.getMonth()+1, secondYear:now.getFullYear(), secondMonth:now.getMonth()+1, data:null,analyticsSource:"all",analyticsBranch:"all",analyticsMetric:"leads"});
        this.months=[[1,"Jan"],[2,"Feb"],[3,"Mar"],[4,"Apr"],[5,"May"],[6,"Jun"],[7,"Jul"],[8,"Aug"],[9,"Sep"],[10,"Oct"],[11,"Nov"],[12,"Dec"]];
        this.years=Array.from({length:7},(_,i)=>now.getFullYear()-5+i);
        onWillStart(()=>this.loadData());
    }
    setTab(tab){ this.state.activeTab = tab; }
    currentCompanyId(){
        const contextCompany = session.user_context?.allowed_company_ids?.[0];
        const currentCompany = session.user_companies?.current_company;
        if (contextCompany) return Number(contextCompany);
        if (typeof currentCompany === "number") return currentCompany;
        if (currentCompany && typeof currentCompany === "object") {
            return Number(currentCompany.id || currentCompany.company_id || false) || false;
        }
        return false;
    }
    iso(y,m,d=1){ return `${y}-${String(m).padStart(2,"0")}-${String(d).padStart(2,"0")} 00:00:00`; }
    nextMonth(y,m){ return m===12?[y+1,1]:[y,m+1]; }
    display(v,fallback="Not entered"){ if(Array.isArray(v)) return v[1]||fallback; if(v===false||v===null||v===undefined||v==="") return fallback; return String(v); }
    async loadData(){
        this.state.loading=true;
        try{
            const companyId=this.currentCompanyId();
            const configs=await this.orm.searchRead("x_compare.configuration", companyId?[["x_company_id","=",companyId]]:[], ["x_branch_field_id","x_profile_field_id","x_source_field_id","x_exclude_walk_in","x_walk_in_text"], {limit:1});
            const cfg=configs[0]||{};
            const fieldIds=[cfg.x_branch_field_id?.[0],cfg.x_profile_field_id?.[0],cfg.x_source_field_id?.[0]].filter(Boolean);
            const fieldRows=fieldIds.length?await this.orm.searchRead("ir.model.fields",[["id","in",fieldIds]],["name","field_description","ttype","relation"],{}):[];
            const fieldMap=Object.fromEntries(fieldRows.map(r=>[r.id,r]));
            const branchMeta=cfg.x_branch_field_id?fieldMap[cfg.x_branch_field_id[0]]:null;
            const profileMeta=cfg.x_profile_field_id?fieldMap[cfg.x_profile_field_id[0]]:null;
            const sourceMeta=cfg.x_source_field_id?fieldMap[cfg.x_source_field_id[0]]:null;
            const branchField=branchMeta?.name||null;
            const profileField=profileMeta?.name||null;
            const sourceField=sourceMeta?.name||"source_id";
            let sourceSelectionMap={};
            if(sourceMeta?.ttype==="selection"){
                try{
                    const definition=await this.orm.call("crm.lead","fields_get",[[sourceField]],{attributes:["selection"]});
                    sourceSelectionMap=Object.fromEntries((definition?.[sourceField]?.selection||[]).map(([value,label])=>[value,label]));
                }catch(_ignored){ sourceSelectionMap={}; }
            }
            const [fy2,fm2]=this.nextMonth(this.state.firstYear,this.state.firstMonth); const [sy2,sm2]=this.nextMonth(this.state.secondYear,this.state.secondMonth);
            const starts=[this.iso(this.state.firstYear,this.state.firstMonth),this.iso(this.state.secondYear,this.state.secondMonth)].sort();
            const ends=[this.iso(fy2,fm2),this.iso(sy2,sm2)].sort();
            const fields=["create_date","source_id","team_id","stage_id"];
            if(branchField&&!fields.includes(branchField))fields.push(branchField);
            if(profileField&&!fields.includes(profileField))fields.push(profileField);
            if(sourceField&&!fields.includes(sourceField))fields.push(sourceField);
            const domain=[["create_date",">=",starts[0]],["create_date","<",ends[1]]]; if(companyId) domain.push(["company_id","in",[companyId,false]]);
            const leads=await this.orm.searchRead("crm.lead",domain,fields,{limit:100000});
            const wonStages=await this.orm.searchRead("crm.stage",[["is_won","=",true]],["id"],{}); const wonIds=new Set(wonStages.map(x=>x.id));
            const mergeGroups=await this.orm.searchRead("x_compare.source.merge.group",companyId?[["x_company_id","=",companyId],["x_active","=",true]]:[["x_active","=",true]],["x_name","x_source_ids","x_source_names"],{limit:1000});
            const parseSourceNames=value=>{if(!value)return[];if(Array.isArray(value))return value;try{const parsed=JSON.parse(value);if(Array.isArray(parsed))return parsed;}catch(_ignored){}return String(value).split(/[,\n]/).map(item=>item.trim()).filter(Boolean);};
            const mergeLookup={},mergeNameLookup={}; for(const g of mergeGroups){for(const id of (g.x_source_ids||[]))mergeLookup[id]=g.x_name;for(const name of parseSourceNames(g.x_source_names))mergeNameLookup[name]=g.x_name;}
            let sourceReferenceRows=[];
            if(sourceMeta?.ttype==="many2one" && sourceMeta.relation){
                try{
                    sourceReferenceRows=await this.orm.searchRead(sourceMeta.relation,[],["id","display_name"],{limit:100000,order:"id asc"});
                }catch(_error){
                    try{ sourceReferenceRows=await this.orm.searchRead(sourceMeta.relation,[],["id","name"],{limit:100000,order:"id asc"}); }catch(_ignored){ sourceReferenceRows=[]; }
                }
            }else if(!sourceMeta || sourceField==="source_id"){
                sourceReferenceRows=await this.orm.searchRead("utm.source",[],["id","name"],{limit:100000,order:"name asc"});
            }
            const referenceColumns=sourceReferenceRows.map(r=>{
                const label=this.display(r.display_name||r.name);
                return mergeLookup[r.id]||mergeNameLookup[label]||label;
            });
            const selectionColumns=Object.values(sourceSelectionMap).map(label=>mergeNameLookup[label]||label);
            const sourceColumns=[...new Set([...referenceColumns,...selectionColumns].filter(Boolean))];
            const costs=await this.orm.searchRead("x_compare.marketing.cost",companyId?[["x_company_id","=",companyId],"|","&",["x_cost_year","=",this.state.firstYear],["x_cost_month","=",String(this.state.firstMonth)],"&",["x_cost_year","=",this.state.secondYear],["x_cost_month","=",String(this.state.secondMonth)]]:["|","&",["x_cost_year","=",this.state.firstYear],["x_cost_month","=",String(this.state.firstMonth)],"&",["x_cost_year","=",this.state.secondYear],["x_cost_month","=",String(this.state.secondMonth)]],["x_source_name","x_source_id","x_platform_name","x_cost_year","x_cost_month","x_cost","x_currency_id"],{limit:100000});
            const firstStart=new Date(this.state.firstYear,this.state.firstMonth-1,1), firstEnd=new Date(fy2,fm2-1,1), secondStart=new Date(this.state.secondYear,this.state.secondMonth-1,1), secondEnd=new Date(sy2,sm2-1,1);
            const period=l=>{const d=new Date(String(l.create_date).replace(" ","T")+"Z"); return d>=firstStart&&d<firstEnd?"first":d>=secondStart&&d<secondEnd?"second":null;};
            const branch=l=>this.display(branchField?l[branchField]:l.team_id,"Unknown");
            const profile=l=>this.display(profileField?l[profileField]:false,"Not entered");
            const source=l=>{
                const value=l[sourceField];
                if(value===false||value===null||value===undefined||value==="") return "Not entered";
                if(Array.isArray(value)){
                    const id=value[0], label=this.display(value);
                    return mergeLookup[id]||mergeNameLookup[label]||label;
                }
                if(sourceMeta?.ttype==="selection"){
                    const label=sourceSelectionMap[value]||this.display(value);
                    return mergeNameLookup[label]||label;
                }
                const label=this.display(value);
                return mergeNameLookup[label]||label;
            };
            const matrix=(items,getter,title,key,seedColumns=[])=>{const values={}; const columnsSet=new Set(seedColumns); for(const l of items){const p=period(l); if(!p)continue; const b=branch(l),c=getter(l); columnsSet.add(c); values[b]??={}; values[b][c]??={first:0,second:0,diff:0}; values[b][c][p]++;} const columns=[...columnsSet]; const branches=Object.keys(values); for(const b of branches)for(const c of columns){values[b][c]??={first:0,second:0,diff:0}; values[b][c].diff=values[b][c].second-values[b][c].first;} columns.sort((a,b)=>{const bTotal=branches.reduce((sum,x)=>sum+values[x][b].first+values[x][b].second,0); const aTotal=branches.reduce((sum,x)=>sum+values[x][a].first+values[x][a].second,0); return bTotal-aTotal||String(a).localeCompare(String(b));}); branches.sort((a,b)=>columns.reduce((sum,c)=>sum+values[b][c].second-values[a][c].second,0)); return {key,title,values,columns,branches};};
            const won=leads.filter(l=>wonIds.has(l.stage_id?.[0])); const walk=(cfg.x_walk_in_text||"walk-in").toLowerCase(); const wonSource=(cfg.x_exclude_walk_in&&profileField)?won.filter(l=>!profile(l).toLowerCase().includes(walk)):won;
            const counts={first:{},second:{}}, wonCounts={first:{},second:{}}; for(const l of leads){const p=period(l);if(p){const s=source(l);counts[p][s]=(counts[p][s]||0)+1;}} for(const l of won){const p=period(l);if(p){const s=source(l);wonCounts[p][s]=(wonCounts[p][s]||0)+1;}}
            const configuredSourceLookup={};
            for(const row of sourceReferenceRows){
                const label=this.display(row.display_name||row.name);
                configuredSourceLookup[label]=mergeLookup[row.id]||mergeNameLookup[label]||label;
            }
            const costMap={}; let currencySymbol=""; for(const c of costs){const sid=c.x_source_id?.[0], rawSource=c.x_source_name||this.display(c.x_source_id), s=configuredSourceLookup[rawSource]||mergeLookup[sid]||mergeNameLookup[rawSource]||rawSource, platform=c.x_platform_name||"Not entered", k=`${s}|||${platform}`; costMap[k]??={source:s,platform,first:0,second:0}; const p=(c.x_cost_year===this.state.firstYear&&String(c.x_cost_month)===String(this.state.firstMonth))?"first":"second"; costMap[k][p]+=Number(c.x_cost||0); currencySymbol=currencySymbol||c.x_currency_id?.[1]||"";}
            const allSources=new Set([...Object.keys(counts.first),...Object.keys(counts.second),...Object.keys(wonCounts.first),...Object.keys(wonCounts.second)]); for(const s of allSources){if(!Object.values(costMap).some(r=>r.source===s))costMap[`${s}|||Not entered`]={source:s,platform:"Not entered",first:0,second:0};}
            const marketing_rows=Object.values(costMap).map(r=>{const fl=counts.first[r.source]||0,sl=counts.second[r.source]||0,fw=wonCounts.first[r.source]||0,sw=wonCounts.second[r.source]||0,fc=r.first,sc=r.second; const f_cpl=fl?fc/fl:0,s_cpl=sl?sc/sl:0,f_cpwl=fw?fc/fw:0,s_cpwl=sw?sc/sw:0; return {...r,first_cost:fc,second_cost:sc,first_leads:fl,second_leads:sl,first_won:fw,second_won:sw,first_cpl:f_cpl,second_cpl:s_cpl,first_cpwl:f_cpwl,second_cpwl:s_cpwl,cost_diff:sc-fc,cpl_diff:s_cpl-f_cpl,cpwl_diff:s_cpwl-f_cpwl};}).sort((a,b)=>(b.first_cost+b.second_cost)-(a.first_cost+a.second_cost));
            const mt=marketing_rows.reduce((t,r)=>{t.first_cost+=r.first_cost;t.second_cost+=r.second_cost;t.first_leads+=r.first_leads;t.second_leads+=r.second_leads;t.first_won+=r.first_won;t.second_won+=r.second_won;return t;},{first_cost:0,second_cost:0,first_leads:0,second_leads:0,first_won:0,second_won:0});
            mt.first_cpl=mt.first_leads?mt.first_cost/mt.first_leads:0; mt.second_cpl=mt.second_leads?mt.second_cost/mt.second_leads:0;
            mt.first_cpwl=mt.first_won?mt.first_cost/mt.first_won:0; mt.second_cpwl=mt.second_won?mt.second_cost/mt.second_won:0;
            mt.cost_diff=mt.second_cost-mt.first_cost; mt.cpl_diff=mt.second_cpl-mt.first_cpl; mt.cpwl_diff=mt.second_cpwl-mt.first_cpwl;
            const marketing_total=mt;
            this.state.data={first_title:`${this.months[this.state.firstMonth-1][1]} ${this.state.firstYear}`,second_title:`${this.months[this.state.secondMonth-1][1]} ${this.state.secondYear}`,currency_symbol:currencySymbol,profile_configured:!!profileField,branch_configured:!!branchField,source_configured:!!sourceMeta,source_field_label:sourceMeta?.field_description||"CRM Source Field",matrices:[matrix(leads,profile,"Lead Assignment Allocations by Profile Type","profile"),matrix(leads,source,"Lead Inflow Intake Routing Channels (Origin Sources)","source",sourceColumns),matrix(wonSource,source,"Won Leads by Source Channels","won_source",sourceColumns),matrix(won,profile,"Won Leads by Profile Type","won_profile")],marketing_rows,marketing_total,stats:{branches:new Set(leads.map(branch)).size,leads:leads.length,won:won.length,sources:new Set(leads.map(source)).size}};
        }catch(e){console.error(e);this.notification.add(e.message||"Unable to load comparison data.",{type:"danger"});this.state.data=null;}finally{this.state.loading=false;}
    }
    analyticsMatrix(key){return this.state.data?.matrices?.find(m=>m.key===key);}
    analyticsSources(){return this.analyticsMatrix("source")?.columns||[];}
    analyticsBranches(){return this.analyticsMatrix("source")?.branches||[];}
    analyticsValue(key,branch,source,period){
        const m=this.analyticsMatrix(key);if(!m)return 0;
        const branches=branch==="all"?m.branches:[branch];
        const sources=source==="all"?m.columns:[source];
        return branches.reduce((total,b)=>total+sources.reduce((sum,c)=>sum+(m.values?.[b]?.[c]?.[period]||0),0),0);
    }
    analyticsRows(key,dimension){
        const m=this.analyticsMatrix(key);if(!m)return [];
        const entries=(dimension==="source"?m.columns:m.branches).map(name=>{
            const branch=dimension==="branch"?name:this.state.analyticsBranch;
            const source=dimension==="source"?name:this.state.analyticsSource;
            const first=this.analyticsValue(key,branch,source,"first");
            const second=this.analyticsValue(key,branch,source,"second");
            return {name,first,second,delta:second-first};
        });
        return entries.filter(r=>r.first||r.second).sort((a,b)=>b.second-a.second).slice(0,15);
    }
    analyticsMax(rows){return Math.max(1,...rows.map(r=>Math.max(r.first,r.second)));}
    analyticsWidth(value,max){return `${Math.max(0,Math.min(100,100*value/max))}%`;}
    analyticsRate(n,d){return d?(100*n/d).toFixed(2)+"%":"0.00%";}
    analyticsChange(ev,key){this.state[key]=ev.target.value;}
    analyticsSpend(period){
        const rows=this.state.data?.marketing_rows||[];
        return rows.filter(r=>this.state.analyticsSource==="all"||r.source===this.state.analyticsSource)
            .reduce((sum,r)=>sum+Number(r[`${period}_cost`]||0),0);
    }
    scrollMatrix(ev,direction){const card=ev.currentTarget.closest(".cmp-card"); const wrap=card?.querySelector(".cmp-table-wrap"); if(wrap) wrap.scrollBy({left:direction*700,behavior:"smooth"});}
    onFilterChange(ev,key){this.state[key]=Number(ev.target.value);} cell(m,b,c){return m.values?.[b]?.[c]||{first:0,second:0,diff:0};} branchTotal(m,b,p){return m.columns.reduce((s,c)=>s+this.cell(m,b,c)[p],0);} columnTotal(m,c,p){return m.branches.reduce((s,b)=>s+this.cell(m,b,c)[p],0);} grandTotal(m,p){return m.branches.reduce((s,b)=>s+this.branchTotal(m,b,p),0);} percentDiff(f,s){return f?((s-f)/f)*100:0;} formatNumber(v){return new Intl.NumberFormat().format(v||0);} formatMoney(v){return new Intl.NumberFormat(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}).format(v||0);} diffClass(v,inverse=false){if(!v)return"cmp-neutral";return(inverse?v<0:v>0)?"cmp-positive":"cmp-negative";}
}
registry.category("actions").add("compare_module_importable.CompareDashboard",CompareDashboard);
