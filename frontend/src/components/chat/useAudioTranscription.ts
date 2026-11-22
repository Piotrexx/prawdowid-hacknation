"use client";

import { useRef, useState } from "react";

export type AudioPhase =
  | { phase: "idle" }
  | { phase: "loading_model"; progress: number }
  | { phase: "transcribing"; progress: number }
  | { phase: "done"; text: string }
  | { phase: "error"; message: string };

// Cache the pipeline promise so the model loads only once per page session.
let _pipelinePromise: Promise<unknown> | null = null;

async function getPipeline(onModelProgress: (p: number) => void) {
  if (_pipelinePromise) return _pipelinePromise;
  _pipelinePromise = (async () => {
    const { pipeline, env } = await import("@xenova/transformers");
    env.allowLocalModels = false;
    return pipeline("automatic-speech-recognition", "Xenova/whisper-tiny", {
      progress_callback: (data: { status: string; progress?: number }) => {
        if ((data.status === "downloading" || data.status === "loading") && data.progress != null) {
          onModelProgress(Math.round(data.progress));
        }
      },
    });
  })();
  return _pipelinePromise;
}

async function decodeAudioFile(file: File): Promise<Float32Array> {
  const arrayBuffer = await file.arrayBuffer();
  const AudioContext = window.AudioContext || (window as unknown as { webkitAudioContext: typeof window.AudioContext }).webkitAudioContext;
  const ctx = new AudioContext({ sampleRate: 16000 });
  const decoded = await ctx.decodeAudioData(arrayBuffer);
  await ctx.close();
  // Mix down to mono if needed
  if (decoded.numberOfChannels === 1) return decoded.getChannelData(0);
  const left = decoded.getChannelData(0);
  const right = decoded.getChannelData(1);
  const mono = new Float32Array(left.length);
  for (let i = 0; i < left.length; i++) mono[i] = (left[i] + right[i]) / 2;
  return mono;
}

export function useAudioTranscription() {
  const [status, setStatus] = useState<AudioPhase>({ phase: "idle" });
  const cancelRef = useRef(false);

  const isProcessing = status.phase === "loading_model" || status.phase === "transcribing";

  async function transcribe(file: File) {
    cancelRef.current = false;
    setStatus({ phase: "loading_model", progress: 0 });

    try {
      const pipe = await getPipeline((p) => {
        if (!cancelRef.current) setStatus({ phase: "loading_model", progress: p });
      }) as (audio: Float32Array, opts: Record<string, unknown>) => Promise<{ text: string }>;

      if (cancelRef.current) return;
      setStatus({ phase: "transcribing", progress: 0 });

      const audioData = await decodeAudioFile(file);
      if (cancelRef.current) return;

      // Estimate total chunks for progress (Whisper processes 30s chunks).
      const durationSeconds = audioData.length / 16000;
      const totalChunks = Math.max(1, Math.ceil(durationSeconds / 30));
      let chunksDone = 0;

      const result = await pipe(audioData, {
        language: "polish",
        task: "transcribe",
        chunk_length_s: 30,
        stride_length_s: 5,
        callback_function: () => {
          chunksDone++;
          if (!cancelRef.current) {
            setStatus({ phase: "transcribing", progress: Math.min(99, Math.round((chunksDone / totalChunks) * 100)) });
          }
        },
      });

      if (cancelRef.current) return;
      setStatus({ phase: "done", text: result.text.trim() });
    } catch (err) {
      _pipelinePromise = null; // reset on error so user can retry
      if (cancelRef.current) return;
      const message = err instanceof Error ? err.message : "Nieznany błąd transkrypcji";
      setStatus({ phase: "error", message });
    }
  }

  function reset() {
    cancelRef.current = true;
    setStatus({ phase: "idle" });
  }

  return { status, transcribe, reset, isProcessing };
}
