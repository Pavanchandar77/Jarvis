import { SparkOSShell } from './shell.js';

export { SparkOSShell } from './shell.js';
export { SparkOSClient } from './api-client.js';

export function mountSparkOS(el, opts = {}) {
  const mount = typeof el === 'string' ? document.querySelector(el) : el;
  if (!mount) throw new Error('Spark OS mount not found');
  return new SparkOSShell(mount, opts);
}

if (typeof document !== 'undefined') {
  const boot = () => {
    const root = document.getElementById('spark-os-root');
    if (!root) return;
    const params = new URLSearchParams(location.search);
    mountSparkOS(root, { twinId: params.get('twin') || undefined });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
}
