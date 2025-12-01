#!/usr/bin/env python
import math
import os
import sys
from os import name
from pathlib import Path
from subprocess import Popen
from typing import Dict, NoReturn

import toml
from prawcore import ResponseException
from rich.console import Console
from rich.table import Table

from reddit.subreddit import get_subreddit_threads
from utils import settings
from utils.cleanup import cleanup
from utils.console import print_markdown, print_step, print_substep
from utils.ffmpeg_install import ffmpeg_install
from utils.id import extract_id
from utils.version import checkversion
from video_creation.background import (
    chop_background,
    download_background_audio,
    download_background_video,
    get_background_config,
)
from video_creation.final_video import make_final_video
from video_creation.screenshot_downloader import get_screenshots_of_reddit_posts
from video_creation.voices import save_text_to_mp3

console = Console()

__VERSION__ = "3.4.0"


def load_subreddits_config():
    """Load the subreddits configuration file."""
    directory = Path().absolute()
    subreddits_file = f"{directory}/subreddits.toml"
    
    try:
        return toml.load(subreddits_file)
    except FileNotFoundError:
        print_substep(
            "subreddits.toml not found. Using default config.toml settings.",
            style="yellow"
        )
        return None
    except toml.TomlDecodeError as e:
        print_substep(f"Error reading subreddits.toml: {e}", style="red")
        return None


def select_subreddit():
    """Display a menu for the user to select which subreddit to use."""
    subreddits_config = load_subreddits_config()
    
    if not subreddits_config or "subreddits" not in subreddits_config:
        print_substep("No subreddits configured. Using config.toml settings.", style="yellow")
        return None
    
    subreddits = subreddits_config["subreddits"]
    
    if not subreddits:
        print_substep("No subreddits found in subreddits.toml", style="yellow")
        return None
    
    # Create a nice table display
    table = Table(title="🎬 Select a Subreddit", show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", style="bold green")
    table.add_column("Subreddit", style="magenta")
    table.add_column("Mode", style="blue")
    
    subreddit_list = list(subreddits.items())
    
    for idx, (key, sub_config) in enumerate(subreddit_list, 1):
        mode = "Story Mode" if sub_config.get("storymode", False) else "Comments"
        table.add_row(
            str(idx),
            sub_config.get("name", key),
            f"r/{sub_config.get('subreddit', key)}",
            mode
        )
    
    # Add option to use config.toml default
    table.add_row(
        "0",
        "Use config.toml default",
        f"r/{settings.config['reddit']['thread']['subreddit']}",
        "Default"
    )
    
    console.print("\n")
    console.print(table)
    console.print("\n")
    
    while True:
        try:
            choice = input("Enter the number of the subreddit you want to use (or 0 for default): ").strip()
            choice_num = int(choice)
            
            if choice_num == 0:
                print_substep("Using default config.toml settings", style="blue")
                return None
            elif 1 <= choice_num <= len(subreddit_list):
                selected_key, selected_config = subreddit_list[choice_num - 1]
                print_substep(
                    f"Selected: {selected_config.get('name', selected_key)} (r/{selected_config.get('subreddit', selected_key)})",
                    style="bold green"
                )
                return selected_config
            else:
                print_substep(f"Please enter a number between 0 and {len(subreddit_list)}", style="red")
        except ValueError:
            print_substep("Please enter a valid number", style="red")


def apply_subreddit_config(subreddit_config):
    """Apply the selected subreddit configuration to settings."""
    if subreddit_config is None:
        return
    
    # Update the reddit thread settings
    if "subreddit" in subreddit_config:
        settings.config["reddit"]["thread"]["subreddit"] = subreddit_config["subreddit"]
    if "min_comments" in subreddit_config:
        settings.config["reddit"]["thread"]["min_comments"] = subreddit_config["min_comments"]
    if "max_comment_length" in subreddit_config:
        settings.config["reddit"]["thread"]["max_comment_length"] = subreddit_config["max_comment_length"]
    if "min_comment_length" in subreddit_config:
        settings.config["reddit"]["thread"]["min_comment_length"] = subreddit_config["min_comment_length"]
    
    # Update storymode settings
    if "storymode" in subreddit_config:
        settings.config["settings"]["storymode"] = subreddit_config["storymode"]
    if "storymodemethod" in subreddit_config:
        settings.config["settings"]["storymodemethod"] = subreddit_config["storymodemethod"]
    if "storymode_max_length" in subreddit_config:
        settings.config["settings"]["storymode_max_length"] = subreddit_config["storymode_max_length"]


print(
    """
██████╗ ███████╗██████╗ ██████╗ ██╗████████╗    ██╗   ██╗██╗██████╗ ███████╗ ██████╗     ███╗   ███╗ █████╗ ██╗  ██╗███████╗██████╗
██╔══██╗██╔════╝██╔══██╗██╔══██╗██║╚══██╔══╝    ██║   ██║██║██╔══██╗██╔════╝██╔═══██╗    ████╗ ████║██╔══██╗██║ ██╔╝██╔════╝██╔══██╗
██████╔╝█████╗  ██║  ██║██║  ██║██║   ██║       ██║   ██║██║██║  ██║█████╗  ██║   ██║    ██╔████╔██║███████║█████╔╝ █████╗  ██████╔╝
██╔══██╗██╔══╝  ██║  ██║██║  ██║██║   ██║       ╚██╗ ██╔╝██║██║  ██║██╔══╝  ██║   ██║    ██║╚██╔╝██║██╔══██║██╔═██╗ ██╔══╝  ██╔══██╗
██║  ██║███████╗██████╔╝██████╔╝██║   ██║        ╚████╔╝ ██║██████╔╝███████╗╚██████╔╝    ██║ ╚═╝ ██║██║  ██║██║  ██╗███████╗██║  ██║
╚═╝  ╚═╝╚══════╝╚═════╝ ╚═════╝ ╚═╝   ╚═╝         ╚═══╝  ╚═╝╚═════╝ ╚══════╝ ╚═════╝     ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
"""
)
print_markdown(
    "### Thanks for using this tool! Feel free to contribute to this project on GitHub! If you have any questions, feel free to join my Discord server or submit a GitHub issue. You can find solutions to many common problems in the documentation: https://reddit-video-maker-bot.netlify.app/"
)
checkversion(__VERSION__)

reddit_id: str
reddit_object: Dict[str, str | list]


def main(POST_ID=None, skip_subreddit_selection=False) -> None:
    global reddit_id, reddit_object
    
    # Ask user which subreddit to use (unless skipped or POST_ID is provided)
    if not skip_subreddit_selection and not POST_ID:
        selected_subreddit = select_subreddit()
        apply_subreddit_config(selected_subreddit)
    
    reddit_object = get_subreddit_threads(POST_ID)
    reddit_id = extract_id(reddit_object)
    print_substep(f"Thread ID is {reddit_id}", style="bold blue")
    length, number_of_comments = save_text_to_mp3(reddit_object)
    length = math.ceil(length)
    get_screenshots_of_reddit_posts(reddit_object, number_of_comments)
    bg_config = {
        "video": get_background_config("video"),
        "audio": get_background_config("audio"),
    }
    download_background_video(bg_config["video"])
    download_background_audio(bg_config["audio"])
    chop_background(bg_config, length, reddit_object)
    video_path = make_final_video(number_of_comments, length, reddit_object, bg_config)
    
    # Social media upload prompt
    try:
        from uploaders.social_manager import SocialManager
        from utils.id import extract_id
        
        social_manager = SocialManager()
        subreddit = settings.config["reddit"]["thread"]["subreddit"]
        title = reddit_object.get("thread_title", "Reddit Video")
        reddit_id = extract_id(reddit_object)
        
        if video_path and os.path.exists(video_path):
            social_manager.prompt_upload(
                subreddit=subreddit,
                video_path=video_path,
                title=title,
                reddit_id=reddit_id
            )
    except ImportError as e:
        print_substep(f"Social media upload not available: {e}", style="yellow")
    except Exception as e:
        print_substep(f"Error during social media upload: {e}", style="yellow")


def run_many(times) -> None:
    for x in range(1, times + 1):
        print_step(
            f'on the {x}{("th", "st", "nd", "rd", "th", "th", "th", "th", "th", "th")[x % 10]} iteration of {times}'
        )
        # Ask for subreddit selection on each iteration
        selected_subreddit = select_subreddit()
        apply_subreddit_config(selected_subreddit)
        main(skip_subreddit_selection=True)
        Popen("cls" if name == "nt" else "clear", shell=True).wait()


def shutdown() -> NoReturn:
    if "reddit_id" in globals():
        print_markdown("## Clearing temp files")
        cleanup(reddit_id)

    print("Exiting...")
    sys.exit()


if __name__ == "__main__":
    supported_minors = [10, 11, 12, 13]
    if sys.version_info.major != 3 or sys.version_info.minor not in supported_minors:
        versions = ", ".join(f"3.{minor}" for minor in supported_minors)
        print(
            f"Hey! Congratulations, you've made it so far (which is pretty rare with no supported Python version). "
            f"Unfortunately, this program currently supports Python {versions}. "
            "Please install one of those versions and try again."
        )
        sys.exit()
    ffmpeg_install()
    directory = Path().absolute()
    config = settings.check_toml(
        f"{directory}/utils/.config.template.toml", f"{directory}/config.toml"
    )
    config is False and sys.exit()

    if (
        not settings.config["settings"]["tts"]["tiktok_sessionid"]
        or settings.config["settings"]["tts"]["tiktok_sessionid"] == ""
    ) and config["settings"]["tts"]["voice_choice"] == "tiktok":
        print_substep(
            "TikTok voice requires a sessionid! Check our documentation on how to obtain one.",
            "bold red",
        )
        sys.exit()
    try:
        if config["reddit"]["thread"]["post_id"]:
            # When using specific post IDs, still ask for subreddit selection once
            print_step("You have specific post IDs configured. Select subreddit settings to apply:")
            selected_subreddit = select_subreddit()
            apply_subreddit_config(selected_subreddit)
            
            for index, post_id in enumerate(config["reddit"]["thread"]["post_id"].split("+")):
                index += 1
                print_step(
                    f'on the {index}{("st" if index % 10 == 1 else ("nd" if index % 10 == 2 else ("rd" if index % 10 == 3 else "th")))} post of {len(config["reddit"]["thread"]["post_id"].split("+"))}'
                )
                main(post_id, skip_subreddit_selection=True)
                Popen("cls" if name == "nt" else "clear", shell=True).wait()
        elif config["settings"]["times_to_run"]:
            run_many(config["settings"]["times_to_run"])
        else:
            main()
    except KeyboardInterrupt:
        shutdown()
    except ResponseException:
        print_markdown("## Invalid credentials")
        print_markdown("Please check your credentials in the config.toml file")
        shutdown()
    except Exception as err:
        config["settings"]["tts"]["tiktok_sessionid"] = "REDACTED"
        config["settings"]["tts"]["elevenlabs_api_key"] = "REDACTED"
        config["settings"]["tts"]["openai_api_key"] = "REDACTED"
        print_step(
            f"Sorry, something went wrong with this version! Try again, and feel free to report this issue at GitHub or the Discord community.\n"
            f"Version: {__VERSION__} \n"
            f"Error: {err} \n"
            f'Config: {config["settings"]}'
        )
        raise err
