import os
import json
from datetime import datetime
from typing import List, Dict, Optional
from apify_client import ApifyClient
import time
import re

class InstagramScraper:
    def __init__(self, apify_token: str):
        self.client = ApifyClient(apify_token)
        self.actor_id = "apify/instagram-scraper"  # Popular Instagram scraper

    def scrape_profile(self, username: str, max_posts: int = 50) -> Dict:
        """
        Scrape Instagram profile and posts using Apify
        """
        print(f"Starting scrape for @{username}...")

        # Configure the scraper for Instagram profile posts
        run_input = {
            "directUrls": [f"https://www.instagram.com/{username}/"],
            "resultsType": "posts",
            "resultsLimit": max_posts,
            "searchType": "user",
            "searchLimit": 1
        }

        try:
            # Run the actor
            run = self.client.actor(self.actor_id).call(run_input=run_input)

            # Get results
            results = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                results.append(item)

            print(f"Successfully scraped {len(results)} posts from @{username}")
            return {
                "username": username,
                "scraped_at": datetime.now().isoformat(),
                "posts": self._process_posts(results),
                "profile_data": self._extract_profile_data(results)
            }

        except Exception as e:
            print(f"Error scraping @{username}: {str(e)}")
            raise e

    def _process_posts(self, raw_posts: List[Dict]) -> List[Dict]:
        """Process raw Apify results into our format"""
        processed_posts = []

        for post in raw_posts:
            try:
                processed_post = {
                    "post_id": post.get("id") or post.get("shortCode"),
                    "post_type": self._determine_post_type(post),
                    "caption_text": post.get("caption", ""),
                    "media_url": self._get_media_url(post),
                    "post_date": self._parse_date(post.get("timestamp")),
                    "likes": post.get("likesCount", 0),
                    "comments": post.get("commentsCount", 0),
                    "views": post.get("videoViewCount", 0),
                    "hashtags": self._extract_hashtags(post.get("caption", "")),
                    "mentions": self._extract_mentions(post.get("caption", "")),
                    "duration": post.get("videoDurationInSeconds", 0),
                    "engagement_rate": self._calculate_engagement_rate(post)
                }
                processed_posts.append(processed_post)

            except Exception as e:
                print(f"Error processing post {post.get('id', 'unknown')}: {str(e)}")
                continue

        return processed_posts

    def _determine_post_type(self, post: Dict) -> str:
        """Determine if post is image, video, carousel, etc."""
        if post.get("videoUrl"):
            return "video"
        elif post.get("displayUrl"):
            if post.get("isVideo", False):
                return "video"
            else:
                return "image"
        elif post.get("sidecarMedias"):
            return "carousel"
        else:
            return "image"

    def _get_media_url(self, post: Dict) -> str:
        """Extract the primary media URL"""
        if post.get("videoUrl"):
            return post["videoUrl"]
        elif post.get("displayUrl"):
            return post["displayUrl"]
        elif post.get("thumbnailUrl"):
            return post["thumbnailUrl"]
        else:
            return ""

    def _parse_date(self, timestamp) -> Optional[str]:
        """Parse Instagram timestamp to ISO format"""
        if not timestamp:
            return None

        try:
            if isinstance(timestamp, str):
                # Try parsing ISO format
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                # Assume it's a Unix timestamp
                dt = datetime.fromtimestamp(timestamp)

            return dt.isoformat()
        except:
            return None

    def _extract_hashtags(self, caption: str) -> List[str]:
        """Extract hashtags from caption"""
        if not caption:
            return []

        hashtag_pattern = r'#(\w+)'
        hashtags = re.findall(hashtag_pattern, caption.lower())
        return list(set(hashtags))  # Remove duplicates

    def _extract_mentions(self, caption: str) -> List[str]:
        """Extract @mentions from caption"""
        if not caption:
            return []

        mention_pattern = r'@(\w+)'
        mentions = re.findall(mention_pattern, caption.lower())
        return list(set(mentions))  # Remove duplicates

    def _calculate_engagement_rate(self, post: Dict) -> float:
        """Calculate basic engagement rate"""
        likes = post.get("likesCount", 0)
        comments = post.get("commentsCount", 0)

        # We don't have follower count per post, so we'll calculate this later
        # For now, just return likes + comments
        return float(likes + comments)

    def _extract_profile_data(self, posts: List[Dict]) -> Dict:
        """Extract profile information from posts data"""
        if not posts:
            return {}

        # Get profile data from first post (Apify usually includes this)
        first_post = posts[0]

        return {
            "display_name": first_post.get("ownerFullName", ""),
            "bio": "",  # Not always available in posts
            "follower_count": first_post.get("ownerFollowersCount", 0),
            "verified": first_post.get("isOwnerVerified", False)
        }

class InstagramPostProcessor:
    """Process Instagram posts for video content extraction"""

    def __init__(self, temp_dir: str = "temp_downloads"):
        self.temp_dir = temp_dir
        os.makedirs(temp_dir, exist_ok=True)

    def extract_video_posts(self, posts: List[Dict]) -> List[Dict]:
        """Filter and return only video posts that need transcription"""
        video_posts = []

        for post in posts:
            if post["post_type"] == "video" and post["media_url"]:
                video_posts.append(post)

        print(f"Found {len(video_posts)} video posts for transcription")
        return video_posts

    def download_video(self, media_url: str, post_id: str) -> Optional[str]:
        """Download video temporarily for transcription"""
        import requests

        try:
            response = requests.get(media_url, stream=True)
            response.raise_for_status()

            file_path = os.path.join(self.temp_dir, f"{post_id}.mp4")

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"Downloaded video for post {post_id}")
            return file_path

        except Exception as e:
            print(f"Error downloading video {post_id}: {str(e)}")
            return None

    def cleanup_temp_files(self):
        """Clean up temporary video files"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            os.makedirs(self.temp_dir, exist_ok=True)
            print("Cleaned up temporary video files")