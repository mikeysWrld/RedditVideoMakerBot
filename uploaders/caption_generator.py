"""Generate captions using ChatGPT/OpenAI API."""

import os
from typing import Optional
from rich.console import Console

from utils import settings
from utils.console import print_substep

console = Console()


class CaptionGenerator:
    """Generate engaging captions for social media posts using OpenAI."""

    def __init__(self):
        self.api_key = settings.config.get("settings", {}).get("tts", {}).get("openai_api_key", "")
        self.api_url = settings.config.get("settings", {}).get("tts", {}).get("openai_api_url", "https://api.openai.com/v1/")
        
        if not self.api_key:
            raise ValueError("OpenAI API key not found in config.toml")

    def generate_caption(
        self,
        title: str,
        subreddit: str,
        reddit_id: str,
        platform: str = "general"
    ) -> str:
        """
        Generate a caption for social media post.
        
        Args:
            title: The Reddit post title
            subreddit: The subreddit name
            reddit_id: The Reddit post ID
            platform: Platform type (instagram, tiktok, youtube, or general)
        
        Returns:
            Generated caption string
        """
        try:
            import requests
            
            # Platform-specific instructions
            platform_instructions = {
                "instagram": "Create an engaging Instagram Reels caption (max 2200 chars). Include relevant hashtags. Make it catchy and engaging.",
                "tiktok": "Create a catchy TikTok caption (max 150 chars). Use trending style, emojis, and hooks.",
                "youtube": "Create a YouTube Shorts title and description. Title should be under 100 chars, description can be longer with hashtags.",
                "general": "Create an engaging social media caption with relevant hashtags."
            }
            
            instruction = platform_instructions.get(platform, platform_instructions["general"])
            
            prompt = f"""You are a social media content creator. {instruction}

Reddit Post Title: {title}
Subreddit: r/{subreddit}

Create a compelling caption that:
1. Hooks the viewer in the first line
2. Summarizes the key point or intrigue
3. Includes relevant hashtags (3-5 hashtags)
4. Is appropriate for {platform if platform != 'general' else 'social media'}

Only return the caption text, nothing else."""

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "gpt-4o-mini",  # Using a cheaper model for captions
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert social media content creator who writes engaging, viral-worthy captions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 300,
                "temperature": 0.8
            }
            
            response = requests.post(
                f"{self.api_url}chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                caption = response.json()["choices"][0]["message"]["content"].strip()
                print_substep(f"Generated {platform} caption using ChatGPT", style="green")
                return caption
            else:
                print_substep(f"ChatGPT API error: {response.text}", style="yellow")
                # Fallback to simple caption
                return self._generate_fallback_caption(title, subreddit)
                
        except Exception as e:
            print_substep(f"Error generating caption: {str(e)}", style="yellow")
            return self._generate_fallback_caption(title, subreddit)

    def _generate_fallback_caption(self, title: str, subreddit: str) -> str:
        """Generate a simple fallback caption if API fails."""
        hashtags = f"#{subreddit} #reddit #redditstories #shorts"
        return f"{title}\n\n{hashtags}"

