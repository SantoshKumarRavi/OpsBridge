import Keycloak from 'keycloak-js';
export interface OpsBridgeAuthConfig {
  url?: string;
  realm?: string;
  clientId?: string;
  tenantFallback?: string;
}
type KeycloakClient=InstanceType<typeof Keycloak>;
export class OpsBridgeAuth {
  private client: KeycloakClient | null = null;
  constructor(private readonly config: OpsBridgeAuthConfig) { if(config.url&&config.realm&&config.clientId)this.client=new Keycloak({url:config.url,realm:config.realm,clientId:config.clientId}); }
  get enabled(){return this.client!==null;}
  get authenticated(){return this.client?.authenticated===true;}
  get displayName(){return this.client?.tokenParsed?.name??this.client?.tokenParsed?.preferred_username??'Demo user';}
  async initialize(){if(!this.client)return false;return await this.client.init({onLoad:'login-required',pkceMethod:'S256',checkLoginIframe:false});}
  async headers(tenantFallback=this.config.tenantFallback??'demo-tenant'): Promise<Record<string, string>> {
    if(this.client?.authenticated){if(this.client.isTokenExpired(20))await this.client.updateToken(30);return {'Authorization':`Bearer ${this.client.token}`,'X-Tenant-Id':String(this.client.tokenParsed?.tenant_id??tenantFallback)};}
    return {'X-Tenant-Id':tenantFallback};
  }
  login(){return this.client?.login({redirectUri:window.location.href});}
  logout(){return this.client?.logout({redirectUri:window.location.origin});}
}
export function createOpsBridgeAuth(config:OpsBridgeAuthConfig){return new OpsBridgeAuth(config);}
