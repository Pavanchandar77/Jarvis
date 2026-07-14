/**
 * Semantic Twin explorer entry — mount into #semantic-twin-root or body.
 */
import { SemanticTwinExplorer } from './explorer.js';

export { SemanticTwinExplorer } from './explorer.js';
export { TwinApiClient } from './api-client.js';
export { AnimationController } from './animation-pipeline.js';
export { GraphRenderer } from './graph-renderer.js';
export { NodePanel } from './node-panel.js';
export { VIEWING_MODES, STORY_STAGES } from './view-modes.js';

export function mountSemanticTwin(el, opts = {}) {
  const mount = typeof el === 'string' ? document.querySelector(el) : el;
  if (!mount) throw new Error('Semantic Twin mount element not found');
  const explorer = new SemanticTwinExplorer(mount, opts);
  explorer.init();
  return explorer;
}

// Auto-mount when page has the root
if (typeof document !== 'undefined') {
  const boot = () => {
    const root = document.getElementById('semantic-twin-root');
    if (root) {
      const params = new URLSearchParams(location.search);
      mountSemanticTwin(root, { twinId: params.get('twin') || undefined });
    }
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
}
