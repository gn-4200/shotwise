from pathlib import Path

from shotwise.providers.base import Job, ProviderError, Result

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]


class YouTubePublisher:
    """pip install -e '.[publish]'. OAuth desktop client in secrets/youtube_client.json."""

    def __init__(self, name, cfg):
        self.name, self.cfg = name, cfg
        self.secrets = Path(cfg.params.get("client_secrets", "secrets/youtube_client.json"))
        self.token = Path(cfg.params.get("token", "secrets/youtube_token.json"))
        self.detail = ""

    def _creds(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        creds = Credentials.from_authorized_user_file(str(self.token), SCOPES) if self.token.exists() else None
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                creds = InstalledAppFlow.from_client_secrets_file(str(self.secrets), SCOPES).run_local_server(port=0)
            self.token.parent.mkdir(parents=True, exist_ok=True)
            self.token.write_text(creds.to_json())
        return creds

    def healthcheck(self) -> bool:
        if not self.secrets.exists():
            self.detail = f"missing {self.secrets}"
            return False
        return True

    def run(self, job: Job) -> Result:
        if not self.secrets.exists():
            raise ProviderError("unavailable", f"{self.name}: missing {self.secrets}", retryable=False)
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except ImportError:
            raise ProviderError("unavailable", "google-api-python-client not installed (pip install -e '.[publish]')", retryable=False)
        yt = build("youtube", "v3", credentials=self._creds())
        p = job.params
        body = {
            "snippet": {"title": p["title"], "description": p["description"], "tags": p.get("tags", []),
                        "categoryId": self.cfg.params.get("category_id", "1")},
            "status": {"privacyStatus": p.get("privacy", "private"), "selfDeclaredMadeForKids": False,
                       "containsSyntheticMedia": bool(p.get("synthetic_media", True))},   # the AI disclosure
        }
        media = MediaFileUpload(str(job.inputs["video"]), chunksize=8 * 1024 * 1024, resumable=True)
        request = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            _, response = request.next_chunk()
        if p.get("playlist_id"):
            yt.playlistItems().insert(part="snippet", body={"snippet": {
                "playlistId": p["playlist_id"],
                "resourceId": {"kind": "youtube#video", "videoId": response["id"]}}}).execute()
        return Result(data={"video_id": response["id"], "url": f"https://youtu.be/{response['id']}"}, units=1)
