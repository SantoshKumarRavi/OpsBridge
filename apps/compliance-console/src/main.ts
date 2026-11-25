import 'zone.js';
import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';
import { createOpsBridgeAuth } from '../../../packages/auth-client/src/index';
import { createOpsBridgeClient, type CaseDecisionInput, type OnboardingCase } from '@opsbridge/api-client';

const API = 'http://localhost:8080/api/v1';
const auth = createOpsBridgeAuth({ url: (window as any).__OPSBRIDGE_KEYCLOAK_URL__, realm: 'opsbridge', clientId: 'opsbridge-compliance', tenantFallback: 'demo-tenant' });
const api = createOpsBridgeClient({ baseUrl: API, getHeaders: () => auth.headers() });
interface ReviewCase { id: string; name: string; role: string; issue: string; status: string }

@Component({
  selector: 'opsbridge-root', standalone: true, imports: [CommonModule],
  template: `
    <div class="layout">
      <aside><h2><i>O</i> opsbridge</h2><p>COMPLIANCE</p><a class="active">Review queue</a><a>Policies</a><a>Audit log</a><a>Organization</a><footer><b>DEMO WORKSPACE</b><br>Compliance team</footer></aside>
      <main>
        <header><div><small>WORKFORCE / COMPLIANCE</small><h1>Review queue</h1></div><button (click)="refresh()">Refresh queue</button></header>
        <section class="summary"><article><small>OPEN REVIEWS</small><b>{{cases().length}}</b></article><article><small>POLICY EXCEPTIONS</small><b>{{exceptions()}}</b></article><article><small>AVERAGE AGE</small><b>—</b></article></section>
        <section class="panel"><h2>Cases requiring your attention</h2><p>AI suggestions are advisory. Review source evidence before deciding.</p><div class="case" *ngFor="let c of cases()"><div><b>{{c.name}}</b><small>{{c.role}} · {{c.id}}</small></div><span>{{c.issue}}</span><button (click)="decide(c,'approve')">Approve</button><button class="secondary" (click)="decide(c,'request_changes')">Request changes</button></div><div class="empty" *ngIf="cases().length===0">No cases are awaiting review.</div></section>

        <section class="panel voice-panel">
          <h2>Voice contact consent and suppression</h2>
          <p>Record verified consent evidence or a caller suppression request. Changes are tenant-scoped and audited.</p>
          <form (submit)="saveVoicePolicy($event)">
            <label>Phone number in E.164 format<input name="phoneNumber" autocomplete="tel" [value]="phoneNumber()" (input)="phoneNumber.set($any($event.target).value)" placeholder="+12025550100" required></label>
            <div class="form-row">
              <label>Consent status<select name="consentStatus" [value]="consentStatus()" (change)="consentStatus.set($any($event.target).value)"><option value="unknown">Unknown</option><option value="granted">Granted</option><option value="revoked">Revoked</option></select></label>
              <label>Consent recorded at<input name="consentRecordedAt" type="datetime-local" [value]="consentRecordedAt()" (input)="consentRecordedAt.set($any($event.target).value)"></label>
            </div>
            <div class="form-row">
              <label>Consent source<input name="consentSource" [value]="consentSource()" (input)="consentSource.set($any($event.target).value)" placeholder="Signed onboarding form"></label>
              <label>Evidence reference<input name="consentReference" [value]="consentReference()" (input)="consentReference.set($any($event.target).value)" placeholder="Internal record ID"></label>
            </div>
            <label class="check"><input name="suppressed" type="checkbox" [checked]="suppressed()" (change)="suppressed.set($any($event.target).checked)"> Suppress this number from outbound calls</label>
            <label>Suppression reason<input name="suppressionReason" [value]="suppressionReason()" (input)="suppressionReason.set($any($event.target).value)" placeholder="Required when suppression is enabled"></label>
            <div class="actions"><button type="button" class="secondary" (click)="loadVoicePolicy()">Load saved policy</button><button type="submit">Save audited policy</button><button type="button" class="secondary" (click)="checkVoiceEligibility()">Check call eligibility</button></div>
          </form>
          <p class="result" *ngIf="eligibility()" aria-live="polite">{{eligibility()}}</p>
          <p class="note">The form records operator-entered evidence details; it does not independently verify the evidence or provide a regulatory compliance determination.</p>
        </section>
        <div class="disclaimer">Human decision required · All case and voice policy changes are recorded in audit history.</div>
        <div class="toast" *ngIf="message()" aria-live="polite">{{message()}}</div>
      </main>
    </div>`,
  styles: [`
    *{box-sizing:border-box}body{margin:0;font-family:Arial;color:#18302a;background:#f5f8f6}.layout{display:grid;grid-template-columns:230px 1fr;min-height:100vh}aside{background:#112d27;color:#e5f0e9;padding:24px 20px;display:flex;flex-direction:column}aside h2{font-size:17px;margin:0 0 38px}i{font-style:normal;color:#16382c;background:#c5ef90;border-radius:7px;padding:7px;margin-right:6px}aside p,small{font-size:10px;letter-spacing:.08em;color:#53665b}aside p{color:#b6c7be}aside a{padding:12px;border-radius:6px;color:#c5d4cc;font-size:13px}.active{background:#27473c;color:#cff7a7}aside footer{margin-top:auto;font-size:11px;line-height:1.8;color:#b6c7be}main{padding:38px 5vw;max-width:1500px}header{display:flex;justify-content:space-between;align-items:center}h1{font-size:26px;margin:6px 0 20px}button{border:0;background:#183c33;color:#e7ffd8;padding:10px 14px;border-radius:6px;cursor:pointer}.secondary{background:#f0f3f1;color:#52675c}.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:10px 0 20px}.summary article,.panel{background:white;border:1px solid #e4ebe6;border-radius:9px;padding:18px}.summary small,.summary b{display:block}.summary b{font-size:24px;margin-top:8px}.panel{margin-bottom:16px}.panel h2{font-size:16px;margin-top:0}.panel p{font-size:12px;color:#586b60}.case{display:flex;flex-wrap:wrap;gap:10px;align-items:center;border-top:1px solid #edf1ee;padding:14px 0;font-size:12px}.case>div{flex:1;min-width:150px}.case small{display:block;margin-top:5px;letter-spacing:0}.case span{color:#78551f;min-width:150px}.empty,.disclaimer{font-size:12px;color:#56695d;padding:14px 0}.disclaimer{color:#4f6958}.toast{background:#edf7ed;color:#376a42;padding:12px;margin-top:15px;border-radius:7px;font-size:12px}.voice-panel form{display:grid;gap:14px;max-width:800px}.form-row{display:grid;grid-template-columns:1fr 1fr;gap:14px}.voice-panel label{display:grid;gap:6px;color:#42594e;font-size:12px;font-weight:600}.voice-panel input:not([type=checkbox]),.voice-panel select{width:100%;border:1px solid #cdd9d1;border-radius:6px;padding:10px;font:inherit;color:#18302a}.voice-panel .check{display:flex;align-items:center;gap:8px}.actions{display:flex;gap:8px;flex-wrap:wrap}.result{font-weight:700;color:#28583a}.note{border-top:1px solid #edf1ee;padding-top:12px}@media(max-width:700px){.layout{grid-template-columns:1fr}aside{display:none}main{padding:24px 14px}.case button{flex:1}.form-row{grid-template-columns:1fr}}
  `],
})
class App {
  cases = signal<ReviewCase[]>([]);
  message = signal('');
  phoneNumber = signal('');
  consentStatus = signal<'unknown' | 'granted' | 'revoked'>('unknown');
  consentRecordedAt = signal('');
  consentSource = signal('');
  consentReference = signal('');
  suppressed = signal(false);
  suppressionReason = signal('');
  eligibility = signal('');

  constructor() { void this.refresh(); }
  exceptions() { return this.cases().filter(c => c.issue !== 'Awaiting document review').length; }

  async refresh() {
    try {
      const data = await api.listCases({ status: 'review_required' });
      this.cases.set(data.items.map((row: OnboardingCase) => {
        const warning = row.documents.flatMap(document => document.warnings ?? []).find((value): value is string => typeof value === 'string');
        return { id: row.id, name: row.worker_name, role: row.role || 'Unspecified role', issue: warning ?? 'Awaiting document review', status: row.status };
      }));
      this.message.set('Queue refreshed from the compliance service.');
    } catch {
      this.message.set('The compliance service is unavailable. Start the local services to load the queue.');
    }
  }

  async saveVoicePolicy(event: Event) {
    event.preventDefault();
    const recordedAt = this.consentRecordedAt() ? new Date(this.consentRecordedAt()).toISOString() : null;
    const body = {
      phoneNumber: this.phoneNumber(), consentStatus: this.consentStatus(), consentRecordedAt: recordedAt,
      consentSource: this.consentSource(), consentReference: this.consentReference(),
      suppressed: this.suppressed(), suppressionReason: this.suppressionReason(),
    };
    try {
      const response = await fetch(`${API}/voice/contacts`, { method: 'PUT', headers: { 'Content-Type': 'application/json', ...await auth.headers() }, body: JSON.stringify(body) });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result === 'object' ? JSON.stringify(result) : 'Policy could not be saved.');
      this.message.set('Voice contact policy saved and audited.');
      await this.checkVoiceEligibility();
    } catch (error) {
      this.message.set(error instanceof Error ? error.message : 'Could not save voice contact policy.');
    }
  }

  async loadVoicePolicy() {
    if (!this.phoneNumber()) { this.message.set('Enter a phone number first.'); return; }
    try {
      const params = new URLSearchParams({ phoneNumber: this.phoneNumber() });
      const response = await fetch(`${API}/voice/contacts?${params}`, { headers: await auth.headers() });
      const result = await response.json();
      if (response.status === 404) { this.message.set('No saved policy exists for this number in the active tenant.'); return; }
      if (!response.ok) throw new Error('The saved policy could not be loaded.');
      this.consentStatus.set(result.consentStatus);
      if (result.consentRecordedAt) {
        const localDate = new Date(result.consentRecordedAt);
        localDate.setMinutes(localDate.getMinutes() - localDate.getTimezoneOffset());
        this.consentRecordedAt.set(localDate.toISOString().slice(0, 16));
      } else this.consentRecordedAt.set('');
      this.consentSource.set(result.consentSource ?? '');
      this.consentReference.set(result.consentReference ?? '');
      this.suppressed.set(Boolean(result.suppressed));
      this.suppressionReason.set(result.suppressionReason ?? '');
      this.message.set('Saved tenant policy loaded.');
    } catch (error) {
      this.message.set(error instanceof Error ? error.message : 'The saved policy could not be loaded.');
    }
  }

  async checkVoiceEligibility() {
    if (!this.phoneNumber()) { this.eligibility.set('Enter a phone number first.'); return; }
    try {
      const params = new URLSearchParams({ phoneNumber: this.phoneNumber() });
      const response = await fetch(`${API}/voice/contacts/eligibility?${params}`, { headers: await auth.headers() });
      const result = await response.json();
      if (!response.ok) throw new Error('Eligibility could not be checked.');
      this.eligibility.set(result.eligible ? 'Eligible for a call during the tenant calling window.' : `Not eligible for outbound calling: ${result.reason}.`);
    } catch (error) {
      this.eligibility.set(error instanceof Error ? error.message : 'Eligibility could not be checked.');
    }
  }

  async decide(c: ReviewCase, decision: CaseDecisionInput['decision']) {
    const reason = window.prompt(decision === 'approve' ? 'Record the approval reason:' : 'Record why changes are needed:');
    if (!reason?.trim()) return;
    try {
      await api.decideCase(c.id, { decision, reason });
      this.message.set(`Decision recorded for ${c.name}.`);
      await this.refresh();
    } catch (error) {
      this.message.set(error instanceof Error ? error.message : 'Could not record the decision.');
    }
  }
}

void auth.initialize().then(() => bootstrapApplication(App)).catch(error => {
  console.error('Identity provider could not be initialized.', error);
  document.querySelector('opsbridge-root')!.textContent = 'Sign-in service is unavailable.';
});
