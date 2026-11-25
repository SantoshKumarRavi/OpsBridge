import { createApp } from 'vue'; import { createOpsBridgeAuth } from '../../../packages/auth-client/src/index'; import App from './App.vue'; import './style.css';
const auth=createOpsBridgeAuth({url:import.meta.env.VITE_KEYCLOAK_URL,realm:'opsbridge',clientId:'opsbridge-integrations',tenantFallback:'demo-tenant'});
void auth.initialize().then(()=>createApp(App,{auth}).mount('#app')).catch(error=>{console.error('Identity provider could not be initialized.',error);document.getElementById('app')!.textContent='Sign-in service is unavailable.';});
