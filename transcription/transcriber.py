import os
import openai
from typing import Optional, Dict
import tempfile
import requests
import subprocess
import shutil

# Check if ffmpeg is available
FFMPEG_AVAILABLE = shutil.which('ffmpeg') is not None
if FFMPEG_AVAILABLE:
    print("✅ ffmpeg is available - video transcription ready!")
else:
    print("⚠️  ffmpeg not available - video transcription will fail")

# Try to import video processing libraries (optional now)
try:
    from moviepy.editor import VideoFileClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

class VideoTranscriber:
    def __init__(self, openai_api_key: str):
        self.client = openai.OpenAI(api_key=openai_api_key)
        self.temp_dir = "temp_downloads"
        os.makedirs(self.temp_dir, exist_ok=True)

    def transcribe_video_from_url(self, video_url: str, post_id: str) -> Optional[Dict]:
        """
        Download video, extract audio, transcribe with Whisper, then cleanup
        """
        video_path = None
        audio_path = None

        try:
            # Step 1: Download video
            print(f"Downloading video for post {post_id}...")
            video_path = self._download_video(video_url, post_id)
            if not video_path:
                return None

            # Step 2: Extract audio
            print(f"Extracting audio from video {post_id}...")
            audio_path = self._extract_audio(video_path, post_id)
            if not audio_path:
                return None

            # Step 3: Transcribe audio
            print(f"Transcribing audio for post {post_id}...")
            transcript_result = self._transcribe_audio(audio_path)
            if not transcript_result:
                return None

            # Step 4: Get video metadata
            duration = self._get_video_duration(video_path)

            return {
                "post_id": post_id,
                "transcript": transcript_result["text"],
                "duration": duration,
                "language": transcript_result.get("language", "unknown"),
                "confidence": "whisper_default"  # Whisper doesn't return confidence scores
            }

        except Exception as e:
            print(f"Error transcribing video {post_id}: {str(e)}")
            return None

        finally:
            # Always cleanup temp files
            self._cleanup_files([video_path, audio_path])

    def _download_video(self, video_url: str, post_id: str) -> Optional[str]:
        """Download video to temporary location"""
        try:
            response = requests.get(video_url, stream=True)
            response.raise_for_status()

            video_path = os.path.join(self.temp_dir, f"{post_id}.mp4")

            with open(video_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return video_path

        except Exception as e:
            print(f"Error downloading video: {str(e)}")
            return None

    def _extract_audio(self, video_path: str, post_id: str) -> Optional[str]:
        """Extract audio from video file using ffmpeg"""
        if not FFMPEG_AVAILABLE:
            print(f"⚠️  Cannot extract audio from {post_id} - ffmpeg not available")
            return None

        try:
            audio_path = os.path.join(self.temp_dir, f"{post_id}.mp3")

            # Use ffmpeg to extract audio directly
            command = [
                'ffmpeg',
                '-i', video_path,      # input video file
                '-vn',                 # no video (audio only)
                '-acodec', 'mp3',      # audio codec
                '-ar', '44100',        # audio rate
                '-ac', '2',            # audio channels
                '-ab', '192k',         # audio bitrate
                '-y',                  # overwrite output file if exists
                audio_path
            ]

            # Run ffmpeg command
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0 and os.path.exists(audio_path):
                print(f"✅ Audio extracted successfully for {post_id}")
                return audio_path
            else:
                print(f"❌ ffmpeg failed for {post_id}: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            print(f"❌ Audio extraction timed out for {post_id}")
            return None
        except Exception as e:
            print(f"❌ Error extracting audio: {str(e)}")
            return None

    def _transcribe_audio(self, audio_path: str) -> Optional[Dict]:
        """Transcribe audio using OpenAI Whisper"""
        try:
            with open(audio_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json"
                )

            return {
                "text": transcript.text,
                "language": transcript.language if hasattr(transcript, 'language') else "unknown"
            }

        except Exception as e:
            print(f"Error transcribing audio: {str(e)}")
            return None

    def _get_video_duration(self, video_path: str) -> int:
        """Get video duration in seconds using ffmpeg"""
        if not FFMPEG_AVAILABLE:
            return 0

        try:
            # Use ffprobe (part of ffmpeg) to get duration
            command = [
                'ffprobe',
                '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                video_path
            ]

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0 and result.stdout.strip():
                duration = float(result.stdout.strip())
                return int(duration)
            else:
                return 0

        except Exception:
            return 0

    def _cleanup_files(self, file_paths: list):
        """Clean up temporary files"""
        for file_path in file_paths:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"Cleaned up {file_path}")
                except Exception as e:
                    print(f"Error cleaning up {file_path}: {str(e)}")

    def transcribe_post_batch(self, video_posts: list) -> Dict:
        """Transcribe multiple video posts"""
        results = {
            "success": [],
            "failed": [],
            "total_processed": 0
        }

        for post in video_posts:
            print(f"\nProcessing post {post['post_id']}...")
            results["total_processed"] += 1

            transcript_result = self.transcribe_video_from_url(
                post["media_url"],
                post["post_id"]
            )

            if transcript_result:
                # Add original post data to result
                transcript_result.update({
                    "original_post": post
                })
                results["success"].append(transcript_result)
                print(f"✓ Successfully transcribed post {post['post_id']}")
            else:
                results["failed"].append({
                    "post_id": post["post_id"],
                    "media_url": post["media_url"],
                    "error": "Transcription failed"
                })
                print(f"✗ Failed to transcribe post {post['post_id']}")

        print(f"\nBatch transcription complete:")
        print(f"- Success: {len(results['success'])}")
        print(f"- Failed: {len(results['failed'])}")
        print(f"- Total: {results['total_processed']}")

        return results