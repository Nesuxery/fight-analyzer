import { useEffect, useSyncExternalStore } from "react";
import { frameAt, frameTime } from "./geometry";

export interface ClockSnapshot {
  time: number;
  playing: boolean;
  rate: number;
}

/** What the playback controls, timeline and panels need from a clock. */
export interface Clock {
  readonly time: number;
  readonly playing: boolean;
  readonly rate: number;
  readonly duration: number;
  readonly fps: number;
  subscribe: (fn: () => void) => () => void;
  getSnapshot: () => ClockSnapshot;
  play(): void;
  pause(): void;
  toggle(): void;
  seek(seconds: number): void;
  skip(deltaS: number): void;
  stepFrames(frames: number): void;
  setRate(rate: number): void;
}

/**
 * Playback clock shared by the video stage, timeline and stat panels.
 * Canvas layers read `time` every animation frame; React components get a
 * throttled snapshot (UI_HZ) so panels do not re-render 60 times a second.
 */
export class PlaybackClock implements Clock {
  static readonly UI_HZ = 12;

  time = 0;
  playing = false;
  rate = 1;
  readonly duration: number;
  readonly fps: number;

  private listeners = new Set<() => void>();
  private snapshot: ClockSnapshot = { time: 0, playing: false, rate: 1 };
  private raf = 0;
  private lastTick = 0;
  private lastNotify = 0;

  constructor(duration: number, fps: number) {
    this.duration = duration;
    this.fps = fps;
  }

  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };

  getSnapshot = () => this.snapshot;

  play() {
    if (this.playing) return;
    if (this.time >= this.duration) this.time = 0;
    this.playing = true;
    this.lastTick = performance.now();
    this.raf = requestAnimationFrame(this.tick);
    this.notify();
  }

  pause() {
    if (!this.playing) return;
    this.playing = false;
    cancelAnimationFrame(this.raf);
    this.notify();
  }

  toggle() {
    if (this.playing) this.pause();
    else this.play();
  }

  seek(seconds: number) {
    this.time = Math.min(Math.max(seconds, 0), this.duration);
    this.notify();
  }

  skip(deltaS: number) {
    this.seek(this.time + deltaS);
  }

  stepFrames(frames: number) {
    this.pause();
    const frame = Math.round(this.time * this.fps) + frames;
    this.seek(frame / this.fps);
  }

  setRate(rate: number) {
    this.rate = rate;
    this.notify();
  }

  dispose() {
    cancelAnimationFrame(this.raf);
    this.listeners.clear();
  }

  private tick = (now: number) => {
    if (!this.playing) return;
    this.time += ((now - this.lastTick) / 1000) * this.rate;
    this.lastTick = now;
    if (this.time >= this.duration) {
      this.time = this.duration;
      this.playing = false;
      this.notify();
      return;
    }
    if (now - this.lastNotify >= 1000 / PlaybackClock.UI_HZ) this.notify();
    this.raf = requestAnimationFrame(this.tick);
  };

  private notify() {
    this.lastNotify = performance.now();
    this.snapshot = { time: this.time, playing: this.playing, rate: this.rate };
    this.listeners.forEach((fn) => fn());
  }
}

export function useClock(clock: Clock): ClockSnapshot {
  return useSyncExternalStore(clock.subscribe, clock.getSnapshot);
}

/** Stop the clock when the owning screen unmounts. */
export function useDisposeClock(clock: { dispose(): void }) {
  useEffect(() => () => clock.dispose(), [clock]);
}

/** mm:ss or mm:ss.t; truncates (never rounds up to "00:60.0"). */
export function formatClock(seconds: number, withTenths = false): string {
  const tenths = Math.floor(Math.max(0, seconds) * 10 + 1e-6);
  const m = Math.floor(tenths / 600);
  const rest = tenths - m * 600;
  const sec = withTenths
    ? `${String(Math.floor(rest / 10)).padStart(2, "0")}.${rest % 10}`
    : String(Math.floor(rest / 10)).padStart(2, "0");
  return `${String(m).padStart(2, "0")}:${sec}`;
}

export type SyncMode = "frame-callback" | "fallback";

/**
 * Clock driven by a real <video> element. The element is the source of truth:
 * `time` is the media time of the frame actually presented on screen, taken
 * from requestVideoFrameCallback, so the overlay, the panels and the picture
 * always refer to the same frame, whatever the playback rate or after a seek.
 * Frame listeners (the overlay canvas) run once per presented frame and never
 * otherwise: when the video stops, drawing stops.
 *
 * Fallback (no requestVideoFrameCallback): `currentTime` is followed every
 * animation frame while playing and on seek/pause/load. It can be up to a frame
 * off during playback; when paused it is exact.
 */
export class VideoClock implements Clock {
  rate = 1;
  mode: SyncMode = "frame-callback";
  readonly duration: number;
  readonly fps: number;
  readonly frameCount: number;
  private video: HTMLVideoElement | null = null;
  private presented = 0;
  private listeners = new Set<() => void>();
  private frameListeners = new Set<(time: number) => void>();
  private snapshot: ClockSnapshot = { time: 0, playing: false, rate: 1 };
  private handle = 0;
  private raf = 0;
  private detach: (() => void) | null = null;

  constructor(duration: number, fps: number) {
    this.duration = duration;
    this.fps = fps;
    this.frameCount = Math.max(1, Math.round(duration * fps));
  }

  get time() {
    return this.presented;
  }

  /** Index of the presented frame. */
  get frame() {
    return frameAt(this.presented, this.fps, this.frameCount);
  }

  get playing() {
    return this.video ? !this.video.paused && !this.video.ended : false;
  }

  attach = (video: HTMLVideoElement | null) => {
    if (video === this.video) return;
    this.detach?.();
    this.video = video;
    if (!video) return;
    const present = (time: number) => {
      this.presented = time;
      this.frameListeners.forEach((fn) => fn(time));
      this.notify();
    };
    const supported = typeof video.requestVideoFrameCallback === "function";
    this.mode = supported ? "frame-callback" : "fallback";
    let poll = () => {};
    if (supported) {
      const onFrame = (_now: number, meta: VideoFrameCallbackMetadata) => {
        present(meta.mediaTime);
        this.handle = video.requestVideoFrameCallback(onFrame);
      };
      this.handle = video.requestVideoFrameCallback(onFrame);
    } else {
      poll = () => {
        if (video.currentTime !== this.presented) present(video.currentTime);
        if (!video.paused && !video.ended) this.raf = requestAnimationFrame(poll);
      };
    }
    const onState = (e: Event) => {
      if (e.type === "ratechange") this.rate = video.playbackRate;
      if (!supported) {
        if (e.type === "play") this.raf = requestAnimationFrame(poll);
        else if (video.currentTime !== this.presented) {
          present(video.currentTime);
          return;
        }
      }
      this.notify();
    };
    const events = ["play", "pause", "seeked", "loadeddata", "ratechange", "ended"];
    events.forEach((e) => video.addEventListener(e, onState));
    this.detach = () => {
      events.forEach((e) => video.removeEventListener(e, onState));
      if (supported && typeof video.cancelVideoFrameCallback === "function") video.cancelVideoFrameCallback(this.handle);
      cancelAnimationFrame(this.raf);
    };
  };

  /** Called with the media time of every presented frame. */
  onFrame(fn: (time: number) => void): () => void {
    this.frameListeners.add(fn);
    return () => this.frameListeners.delete(fn);
  }

  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };

  getSnapshot = () => this.snapshot;

  play() {
    void this.video?.play();
  }

  pause() {
    this.video?.pause();
  }

  toggle() {
    if (this.playing) this.pause();
    else this.play();
  }

  /** Show the frame containing `seconds` (the middle of its interval, so it lands exactly). */
  seek(seconds: number) {
    if (!this.video) return;
    const frame = Math.min(Math.max(0, Math.floor(seconds * this.fps + 1e-3)), this.frameCount - 1);
    this.video.currentTime = frameTime(frame, this.fps);
  }

  skip(deltaS: number) {
    this.seek(this.presented + deltaS);
  }

  stepFrames(frames: number) {
    this.pause();
    this.seek((this.frame + frames) / this.fps);
  }

  setRate(rate: number) {
    this.rate = rate;
    if (this.video) this.video.playbackRate = rate;
    this.notify();
  }

  dispose() {
    this.detach?.();
    this.listeners.clear();
    this.frameListeners.clear();
  }

  private notify() {
    this.snapshot = { time: this.presented, playing: this.playing, rate: this.rate };
    this.listeners.forEach((fn) => fn());
  }
}
