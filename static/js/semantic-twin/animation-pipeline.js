/**
 * AnimationController — Prompt → Requirement → Decision → Code → Runtime → Deps → Concepts
 */

export class AnimationController {
  constructor({ onStep, onComplete, reducedMotion = false } = {}) {
    this.steps = [];
    this.index = -1;
    this.timer = null;
    this.playing = false;
    this.onStep = onStep || (() => {});
    this.onComplete = onComplete || (() => {});
    this.reducedMotion = reducedMotion ||
      (typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  load(steps) {
    this.stop();
    this.steps = Array.isArray(steps) ? steps.slice() : [];
    this.index = -1;
  }

  play() {
    if (!this.steps.length) return;
    this.playing = true;
    if (this.index < 0) this.index = 0;
    this._runCurrent();
  }

  pause() {
    this.playing = false;
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }

  stop() {
    this.pause();
    this.index = -1;
  }

  step() {
    this.pause();
    if (this.index < 0) this.index = 0;
    else this.index = Math.min(this.index + 1, this.steps.length - 1);
    this._emit();
  }

  skipTo(kind) {
    const i = this.steps.findIndex((s) => s.kind === kind);
    if (i >= 0) {
      this.pause();
      this.index = i;
      this._emit();
    }
  }

  _runCurrent() {
    if (!this.playing || this.index < 0 || this.index >= this.steps.length) {
      this.playing = false;
      this.onComplete();
      return;
    }
    this._emit();
    const step = this.steps[this.index];
    const ms = this.reducedMotion ? 0 : (step.duration_ms || 800);
    if (ms <= 0) {
      this.index += 1;
      if (this.index >= this.steps.length) {
        this.playing = false;
        this.onComplete();
      } else {
        this._runCurrent();
      }
      return;
    }
    this.timer = setTimeout(() => {
      this.index += 1;
      if (this.index >= this.steps.length) {
        this.playing = false;
        this.onComplete();
      } else {
        this._runCurrent();
      }
    }, ms);
  }

  _emit() {
    const step = this.steps[this.index];
    if (step) this.onStep(step, this.index, this.steps.length);
  }
}

export default AnimationController;
