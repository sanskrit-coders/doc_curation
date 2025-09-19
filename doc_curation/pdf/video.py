import cv2
import numpy as np
from collections import deque
import os

def extract_book_pages(video_path, output_dir="extracted_pages"):
  """
  Extract still images of book pages from a video where pages are flipped every ~1 second
  """

  # Create output directory
  os.makedirs(output_dir, exist_ok=True)

  # Open video
  cap = cv2.VideoCapture(video_path)
  fps = cap.get(cv2.CAP_PROP_FPS)

  # Parameters
  motion_threshold = 1e7  # Adjust based on video resolution/sensitivity
  stability_frames = int(fps * 0.3)  # Wait 0.3s after motion stops
  frame_buffer = deque(maxlen=stability_frames + 5)

  frame_count = 0
  page_count = 0
  motion_detected = True
  stable_count = 0
  prev_frame_gray = None

  print(f"Processing video at {fps:.1f} FPS...")

  while True:
    ret, frame = cap.read()
    if not ret:
      break

    frame_count += 1

    # Convert to grayscale for motion detection
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Store frame in buffer
    frame_buffer.append((gray.copy(), frame_count))

    if prev_frame_gray is not None:
      # Calculate frame difference
      diff = cv2.absdiff(prev_frame_gray, gray)
      motion_score = np.sum(diff)

      if motion_score > motion_threshold:
        motion_detected = True
        stable_count = 0
      else:
        if motion_detected:
          stable_count += 1

          # If stable for required frames, extract the best frame
          if stable_count >= stability_frames:
            best_frame = select_best_frame(frame_buffer, stability_frames)
            if best_frame is not None:
              page_filename = f"{output_dir}/page_{page_count:03d}.jpg"
              cv2.imwrite(page_filename, best_frame)
              print(f"Extracted page {page_count} at frame {frame_count}")
              page_count += 1

            motion_detected = False
            stable_count = 0

    prev_frame_gray = gray

    # Progress indicator
    if frame_count % (int(fps) * 5) == 0:  # Every 5 seconds
      print(f"Processed {frame_count} frames, extracted {page_count} pages")

  cap.release()
  print(f"Extraction complete! {page_count} pages saved to '{output_dir}'")
  return page_count


def select_best_frame(frame_buffer, stability_frames):
  """
  Select the best quality frame from the stable period
  Uses Laplacian variance to measure image sharpness
  """
  print(f"Selecting best frame from {len(frame_buffer)} frames")
  if len(frame_buffer) < stability_frames:
    return None

  # Analyze frames from the stable period (most recent frames)
  candidates = list(frame_buffer)[-stability_frames:]
  best_frame = None
  best_score = -1

  for gray, frame_num in candidates:
    # Calculate Laplacian variance (higher = sharper)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    sharpness = laplacian.var()

    if sharpness > best_score:
      best_score = sharpness
      best_frame = gray

  return best_frame


if __name__ == "__main__":
  video_file = "IMG_2639.MOV"
  pages1 = extract_book_pages(video_file)