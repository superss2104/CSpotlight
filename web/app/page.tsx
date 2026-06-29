"use client"; //Run directly in browser and not the server since actions like upload, event handling, navigation are required.

import { useState } from "react"; //useState allows us to add state to our component.
import { useRouter } from "next/navigation"; //Next.js router to handle client-side navigation.
import HeroSection from "@/components/HeroSection"; //The top section of the page with the title and description.
import UploadZone from "@/components/UploadZone"; //The section where the user can upload a video.
import SettingsPanel from "@/components/SettingsPanel"; //The section where the user can change the settings.
import HowItWorks from "@/components/HowItWorks"; //The section that explains how the app works.
import { uploadVideo, startProcessing } from "@/lib/api"; //uploadVideo and startProcessing are functions that are used to upload the video and start the processing.
import { DEFAULT_SETTINGS } from "@/types"; //DEFAULT_SETTINGS is an object that contains the default settings.
import type { ProcessingSettings } from "@/types"; //ProcessingSettings is an interface that contains the processing settings.

export default function Home() {
  const router = useRouter(); // useRouter is a hook that is used to handle client-side navigation.
  const [settings, setSettings] = useState<ProcessingSettings>(DEFAULT_SETTINGS); //settings is a state variable that is used to store the processing settings.
  
  const [uploading, setUploading] = useState(false); //useState(false) creates a state variable initialized to false and returns both the current value (uploading) and a setter function (setUploading) that can update that value and trigger a UI re-render.
  const [uploadProgress, setUploadProgress] = useState(0); 
  const [error, setError] = useState<string | null>(null); 

  const handleFileSelected = async (file: File) => {
    try {
      setUploading(true);
      setError(null);
      setUploadProgress(0);

      const uploadRes = await uploadVideo(file, (percent) => {
        setUploadProgress(percent); //The second parameter is optional and is being used for callback, in this case to continuously update the upload progress.
      });

      setUploadProgress(100);

      await startProcessing(uploadRes.job_id, settings);

      router.push(`/results/${uploadRes.job_id}`);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "An unexpected error occurred during upload.");
      setUploading(false);
    }
  };

  return (
    <div className="flex min-h-[calc(100vh-4rem-100px)] flex-col items-center px-100">
      <HeroSection />
      
      <div className="w-full max-w-4xl space-y-10 pb-1">
        <UploadZone 
          onFileSelected={handleFileSelected}
          uploading={uploading}
          uploadProgress={uploadProgress}
          error={error}
        />  
        {/* Render the UploadZone component */}
        
        <div className="opacity-90">
          <SettingsPanel 
            settings={settings}
            onSettingsChange={setSettings}
            disabled={uploading}
          />
        </div>
      </div>

      <HowItWorks />
    </div>
  );
}
