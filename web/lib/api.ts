/**
 * CSpotlight API client.
 *
 * Typed wrapper around fetch() for all backend communication.
 * Single source of truth — all API calls go through here.
 */

import type {
  JobStatusResponse,
  ProcessingSettings,
  ProcessResponse,
  UploadResponse,
  DEFAULT_SETTINGS,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(body.detail || "Unknown error", res.status);
  }
  return res.json();
}
  export async function uploadVideo(
    file: File,
    onProgress?: (percent: number) => void
  ): Promise<UploadResponse> {   //the parameters of uploadVideo are file of type File and an optional parameter called onProgress which is of type void function, and that function accepts a percent (which is a number) as a parameter and returns nothing
    // Use XMLHttpRequest for upload progress tracking.
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append("file", file);

      xhr.open("POST", `${API_BASE}/upload`); //Prepare HTTP request to be sent to the backend (POST Request)

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) {
          const percent = Math.round((event.loaded / event.total) * 100);
          onProgress(percent); //callback called when progress is made (Update progress bar)
        }
      };

      xhr.onload = () => { //Run after upload completes or fails
        if (xhr.status >= 200 && xhr.status < 300) { //Check if request was successful 
          resolve(JSON.parse(xhr.responseText));
        } else { //If request failed 
          try {
            const body = JSON.parse(xhr.responseText);
            reject(new ApiError(body.detail || "Upload failed", xhr.status));
          } catch {
            reject(new ApiError("Upload failed", xhr.status));
          }
        }
      };

      xhr.onerror = () => reject(new ApiError("Network error", 0));
      xhr.send(formData);
    });
  }

  export async function startProcessing(
    jobId: string,
    settings: ProcessingSettings
  ): Promise<ProcessResponse> {
    const res = await fetch(`${API_BASE}/process`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: jobId,
        settings,
      }),
    });
    return handleResponse<ProcessResponse>(res);
  }

  export async function getJobStatus(
    jobId: string
  ): Promise<JobStatusResponse> {
    const res = await fetch(`${API_BASE}/results/${jobId}`);
    return handleResponse<JobStatusResponse>(res);
  }

  export function getDownloadUrl(jobId: string, clipName: string): string {
    return `${API_BASE}/download/${jobId}/${clipName}`;
  }

  export async function pollUntilDone(
    jobId: string,
    onUpdate?: (status: JobStatusResponse) => void,
    intervalMs: number = 2000
  ): Promise<JobStatusResponse> {
    while (true) {
      const status = await getJobStatus(jobId);
      onUpdate?.(status);

      if (status.status === "completed" || status.status === "failed") {
        return status;
      }

      await new Promise((r) => setTimeout(r, intervalMs));
    }
  }
