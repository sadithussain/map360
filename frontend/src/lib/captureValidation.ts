export const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
export const MAX_VIDEO_BYTES = 50 * 1024 * 1024;
export const MAX_VIDEO_DURATION_SECONDS = 5;
export const REQUIRED_IMAGE_COUNT = 3;

const IMAGE_MIME_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
]);

const VIDEO_MIME_TYPES = new Set(["video/mp4", "video/webm"]);

export function validateImageFiles(files: File[]): string | null {
  if (files.length !== REQUIRED_IMAGE_COUNT) {
    return `Please provide exactly ${REQUIRED_IMAGE_COUNT} images.`;
  }

  for (const file of files) {
    if (!IMAGE_MIME_TYPES.has(file.type)) {
      return "Images must be JPEG, PNG, or WebP.";
    }
    if (file.size > MAX_IMAGE_BYTES) {
      return "Each image must be 10 MB or smaller.";
    }
  }

  return null;
}

export function validateVideoFile(file: File | null): string | null {
  if (!file) {
    return "Please provide a video file.";
  }

  if (!VIDEO_MIME_TYPES.has(file.type)) {
    return "Video must be MP4 or WebM.";
  }

  if (file.size > MAX_VIDEO_BYTES) {
    return "Video must be 50 MB or smaller.";
  }

  return null;
}

export function readVideoDuration(file: File): Promise<number> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "metadata";

    video.onloadedmetadata = () => {
      URL.revokeObjectURL(url);
      resolve(video.duration);
    };

    video.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Unable to read video metadata."));
    };

    video.src = url;
  });
}

export async function validateVideoDuration(file: File): Promise<string | null> {
  try {
    const duration = await readVideoDuration(file);
    if (!Number.isFinite(duration) || duration <= 0) {
      return "Unable to determine video duration.";
    }
    if (duration > MAX_VIDEO_DURATION_SECONDS + 0.25) {
      return `Video must be ${MAX_VIDEO_DURATION_SECONDS} seconds or shorter.`;
    }
    return null;
  } catch {
    return "Unable to read video metadata.";
  }
}
