export const MAX_IMAGE_BYTES = 10 * 1024 * 1024;

const IMAGE_MIME_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

export function validateImageFile(file: File | null): string | null {
  if (!file) {
    return "Please provide a photo.";
  }

  if (!IMAGE_MIME_TYPES.has(file.type)) {
    return "Image must be JPEG, PNG, or WebP.";
  }

  if (file.size > MAX_IMAGE_BYTES) {
    return "Image must be 10 MB or smaller.";
  }

  return null;
}
