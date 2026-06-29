"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import ProcessingStatus from "@/components/ProcessingStatus";
import ClipCard from "@/components/ClipCard";
import { pollUntilDone } from "@/lib/api";
import type { JobStatusResponse } from "@/types";

export default function ResultsPage() {
  const params = useParams(); // Used to dynamically retrieve the jobId from the URL.
  const jobId = params.jobId as string;
  
  const [status, setStatus] = useState<JobStatusResponse | null>(null);

  useEffect(() => { //Use effect is used to run something once the UI loads. 
    if (!jobId) return;

    // Start polling immediately on mount
    let isMounted = true;
    
    pollUntilDone(
      jobId,
      (newStatus) => {
        if (isMounted) setStatus(newStatus);
      },
      1500 // Poll every 1.5s
    ).catch((err) => {
      console.error("Polling failed:", err);
      if (isMounted) {
        setStatus({
          job_id: jobId,
          status: "failed",
          error: "CONNECTION LOST. PIPELINE TELEMETRY UNAVAILABLE.",
        });
      }
    });

    return () => {
      isMounted = false; // Cleanup function that prevents state updates after the component unmounts.
    };
  }, [jobId]);

  return (
    <div className="flex min-h-[calc(100vh-4rem-100px)] flex-col items-center px-6 py-12 w-full">
      {/* Header */}
      <div className="mb-8 w-full max-w-6xl text-left border-b border-zinc-800 pb-4">
        <h1 className="text-2xl font-black uppercase tracking-widest text-zinc-100">
          Match Analysis Results
        </h1>
        <p className="mt-1 text-xs font-mono text-zinc-500 uppercase">
          SESSION ID: <span className="text-orange-500">{jobId}</span>
        </p>
      </div>

      {/* Status Card */}
      <ProcessingStatus status={status} />

      {/* Results List */}
      {status?.status === "completed" && status.result && (
        <div className="mt-8 w-full max-w-6xl">
          <div className="mb-4 flex items-center justify-between border-b border-zinc-800 pb-2">
            <h2 className="text-sm font-bold uppercase tracking-widest text-zinc-300">
              EXTRACTED HIGHLIGHTS
            </h2>
            <Link
              href="/"
              className="px-4 py-1 text-xs font-bold uppercase tracking-widest text-orange-500 border border-orange-500/50 rounded-sm hover:bg-orange-500 hover:text-zinc-900 transition-colors"
            >
              Analyze New Match
            </Link>
          </div>

          {status.result.clip_count === 0 ? (
            <div className="border border-dashed border-zinc-700 bg-zinc-900/50 p-12 text-center rounded-sm">
              <p className="text-sm font-mono uppercase text-zinc-500">
                NO SIGNIFICANT HIGHLIGHTS DETECTED WITH CURRENT PARAMETERS.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <div className="hidden sm:flex text-[10px] font-bold uppercase tracking-widest text-zinc-500 px-4 py-2 bg-zinc-900/50 border border-zinc-800 rounded-sm">
                <div className="w-24 text-center">DURATION</div>
                <div className="flex-1">HIGHLIGHT METADATA</div>
                <div className="w-32 text-center">ACTION</div>
              </div>

              {status.result.clips.map((clip) => (
                <ClipCard key={clip.name} clip={clip} jobId={jobId} /> //map the result to their respective clip cards
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
