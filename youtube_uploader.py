import os
import sys
import logging
import argparse
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

logger = logging.getLogger("timelapse")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRETS_FILE = "client_secrets.json"
TOKEN_FILE = "token.json"


def get_authenticated_service():
    """
    Authenticate and return the YouTube API service object.
    Loads credentials from token.json if it exists.
    Returns None if credentials cannot be loaded.
    """
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            logger.error(f"Error loading {TOKEN_FILE}: {e}")
            return None

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info("Refreshing YouTube OAuth credentials...")
                creds.refresh(Request())
                with open(TOKEN_FILE, "w") as token:
                    token.write(creds.to_json())
                logger.info("Successfully refreshed credentials.")
            except Exception as e:
                logger.error(f"Failed to refresh YouTube credentials: {e}")
                return None
        else:
            logger.error("No valid YouTube credentials (token.json) found. Please run the setup command: python youtube_uploader.py --setup")
            return None

    try:
        service = build("youtube", "v3", credentials=creds)
        return service
    except Exception as e:
        logger.error(f"Failed to build YouTube service: {e}")
        return None


def run_oauth_setup():
    """
    Run the OAuth flow to generate token.json.
    Can be run locally or headless.
    """
    print("=" * 60)
    print("           YOUTUBE TIMELAPSE UPLOADER OAUTH SETUP")
    print("=" * 60)
    
    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"ERROR: '{CLIENT_SECRETS_FILE}' not found in the current directory!")
        print("\nTo set up YouTube uploads, you must:")
        print("1. Go to Google Cloud Console (https://console.cloud.google.com/)")
        print("2. Create a new project.")
        print("3. Enable the 'YouTube Data API v3' for your project.")
        print("4. Configure the OAuth Consent Screen (External, add your email as a Test User!).")
        print("5. Go to Credentials -> Create Credentials -> OAuth client ID.")
        print("6. Choose Application Type: 'Desktop App'.")
        print("7. Download the credentials JSON and save it as 'client_secrets.json' in this folder.")
        print("=" * 60)
        return False

    print("Found client_secrets.json. Starting authorization flow...")
    print("\nNOTE: Since you might be running this on a headless Linux server:")
    print("- If a browser doesn't open automatically, look for a URL printed in the console.")
    print("- Copy and paste that URL into a browser on your local PC.")
    print("- After granting permissions, your browser will redirect to localhost (it might show an error).")
    print("- Copy the full redirection URL from the browser's address bar and paste it here if prompted.")
    print("- Alternatively, you can run this setup on your Windows PC first to generate token.json,")
    print("  and then copy token.json to your Linux server!")
    print("-" * 60)

    try:
        # Standard Desktop App Flow
        flow = InstalledAppFlow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES
        )
        
        # run_local_server will print a authorization URL and listen on a local port.
        # open_browser=True will attempt to launch a local browser.
        # If running on a headless server, it will fail with a webbrowser.Error.
        # We catch that exception and fall back to open_browser=False.
        try:
            creds = flow.run_local_server(
                port=0,
                authorization_prompt_message="Open this URL in a browser on any machine: \n{url}",
                success_message="Authorization complete! You can close this tab and return to the terminal.",
                open_browser=True
            )
        except Exception as browser_err:
            # Dynamically find a free local port to make the instructions extremely precise
            port = 8080
            try:
                import socket
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('', 0))
                    port = s.getsockname()[1]
            except Exception:
                pass

            print("\n[INFO] Local browser could not be opened (expected on headless Linux servers).")
            print("Falling back to headless console mode. The script will start a local redirect server.")
            print("-" * 60)
            print("INSTRUCTIONS FOR HEADLESS SERVER AUTHENTICATION:")
            print("1. Copy the authorization URL printed below and open it in your local PC's browser.")
            print("2. Log in and grant permissions.")
            print(f"3. Your browser will try to redirect to 'http://localhost:{port}/?code=...' and fail.")
            print("4. This is normal! Since the redirect port is local to this server, you have two options:")
            print("   Option A (Easiest): Run this setup script on your local Windows PC first,")
            print("             generate 'token.json' there, and then copy it to your Linux server!")
            print("   Option B (SSH Tunnel): Open a terminal on your local Windows PC and run this SSH port forward command:")
            print(f"             ssh -L {port}:localhost:{port} your_server_username@your_server_ip")
            print("             Then, refresh the failed browser page on your local PC. It will authorize instantly!")
            print("-" * 60)
            
            creds = flow.run_local_server(
                port=port,
                authorization_prompt_message="Open this URL in a browser on any machine: \n{url}",
                success_message="Authorization complete! You can close this tab and return to the terminal.",
                open_browser=False
            )
        
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
            
        print("\nSUCCESS! Successfully saved credentials to token.json.")
        print("The uploader is now authorized to upload videos to your YouTube channel!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\nERROR: OAuth flow failed: {e}")
        print("\nIf you are stuck, the absolute easiest solution is:")
        print("1. Put 'client_secrets.json', 'youtube_uploader.py', and 'requirements.txt' on your local Windows PC.")
        print("2. Run 'pip install -r requirements.txt' and 'python youtube_uploader.py --setup'.")
        print("3. Complete the login in your browser to generate 'token.json'.")
        print("4. Copy 'token.json' back to this Linux server directory, and you are ready to go!")
        print("=" * 60)
        return False


def upload_video(file_path, title, description, privacy_status="unlisted"):
    """
    Upload a video file to YouTube with progress reporting.
    Returns: (video_id, video_url) if successful, or None if failed.
    """
    if not os.path.exists(file_path):
        logger.error(f"Cannot upload video: File {file_path} does not exist.")
        return None

    service = get_authenticated_service()
    if not service:
        logger.error("Skipping YouTube upload because API service could not be authenticated.")
        return None

    logger.info(f"Initializing YouTube upload for {file_path}...")
    
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["timelapse", "nature", "automation"],
            "categoryId": "22"  # Category 22 is "People & Blogs"
        },
        "status": {
            "privacyStatus": privacy_status,  # "private", "public", or "unlisted"
            "selfDeclaredMadeForKids": False
        }
    }

    # Resumable media upload in chunks of 5MB
    media = MediaFileUpload(
        file_path,
        mimetype="video/mp4",
        chunksize=5 * 1024 * 1024,
        resumable=True
    )

    request = service.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    error_count = 0
    max_errors = 5
    
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                logger.info(f"YouTube Upload Progress: {progress}%")
        except HttpError as e:
            if e.resp.status in [500, 502, 503, 504]:
                error_count += 1
                if error_count > max_errors:
                    logger.error(f"YouTube upload failed: Too many server errors ({e.resp.status})")
                    raise e
                logger.warning(f"YouTube server error {e.resp.status}, retrying chunk...")
            else:
                logger.error(f"YouTube API HttpError during upload: {e}")
                return None
        except Exception as e:
            logger.error(f"Unexpected error during YouTube chunk upload: {e}")
            return None

    video_id = response.get("id")
    video_url = f"https://youtu.be/{video_id}"
    logger.info(f"YouTube Upload complete! Video ID: {video_id} | Link: {video_url}")
    return video_id, video_url


if __name__ == "__main__":
    # Setup logger for standalone script run
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    parser = argparse.ArgumentParser(description="YouTube Timelapse Uploader CLI helper")
    parser.add_argument("--setup", action="store_true", help="Run the initial OAuth authentication flow to link your channel")
    parser.add_argument("--upload", type=str, help="Upload a video file")
    parser.add_argument("--title", type=str, default="Test Timelapse", help="Title for the uploaded video")
    parser.add_argument("--desc", type=str, default="A test timelapse upload", help="Description for the uploaded video")
    parser.add_argument("--privacy", type=str, choices=["public", "private", "unlisted"], default="unlisted", help="Privacy status")
    
    args = parser.parse_args()
    
    if args.setup:
        run_oauth_setup()
    elif args.upload:
        # Check if authenticated
        service = get_authenticated_service()
        if not service:
            print("Authentication failed. Run standard CLI setup first: python youtube_uploader.py --setup")
            sys.exit(1)
        upload_video(args.upload, args.title, args.desc, args.privacy)
    else:
        parser.print_help()
