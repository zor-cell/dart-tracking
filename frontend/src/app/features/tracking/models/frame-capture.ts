const DEFAULT_JPEG_QUALITY = 0.85;

/** Grabs the current video frame as a JPEG blob via an off-screen canvas. */
export function captureFrameAsJpeg(
  video: HTMLVideoElement,
  canvas: HTMLCanvasElement,
  quality = DEFAULT_JPEG_QUALITY,
): Promise<Blob> {
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;

  const context = canvas.getContext('2d');
  if (!context) {
    return Promise.reject(new Error('Canvas 2D context nicht verfügbar'));
  }
  context.drawImage(video, 0, 0);

  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('JPEG-Erstellung fehlgeschlagen'))),
      'image/jpeg',
      quality,
    );
  });
}
